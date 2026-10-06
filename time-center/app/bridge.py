import copy
import calendar
import datetime as dt
import json
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import time
from PySide6.QtCore import QObject,Signal,Slot,Property,QTimer
from PySide6.QtGui import QGuiApplication
from services.engine import Engine,terminator,resolve_local,UTC
from services.search import search,inspect_point
from services.refinements import precise
from zoneinfo import available_timezones
from services.timezones import zone as ZoneInfo

class Bridge(QObject):
    changed=Signal();calendarChanged=Signal();searchChanged=Signal();mapChanged=Signal();plannerChanged=Signal();statusChanged=Signal()
    hideRequested=Signal();alertRaised=Signal(str);focusMap=Signal(float,float)
    workerDone=Signal(int,object,str)
    stopwatchChanged=Signal();modalChanged=Signal();focusChanged=Signal();navigate=Signal(int);alarmEditor=Signal(str)
    computeDone=Signal(str,int,object,str);busyChanged=Signal()
    mapAssetsChanged=Signal();mapWorkDone=Signal(object,object,str)
    clocksChanged=Signal();timersChanged=Signal();alarmsChanged=Signal();stopwatchDisplayChanged=Signal();planEpochChanged=Signal()
    def __init__(self,root):
        super().__init__();self.root=Path(root);self.engine=Engine(self.root/'data');self.panel_visible=False
        from services.persistence import AtomicWriter
        self.writer=AtomicWriter();self.engine.writer=self.writer
        initial=self.engine.snapshot();self._state=self.presentation_state(initial);today=dt.datetime.now().date();self._calendar=self.engine.calendar(today.year,today.month,today.isoformat())
        self._search=[];self._status='Ready';self._night=terminator(time.time());self._plan_ids=None;self._plan={}
        self.executor=ThreadPoolExecutor(max_workers=2,thread_name_prefix='time-center');self.generation=0;self.cache={};self.preview=None
        self.cachefile=self.root/'data/search-cache.json'
        try:self.cache=json.loads(self.cachefile.read_text('utf-8'))
        except (OSError,ValueError):pass
        from services.map_renderer import MapImages,MapRenderer
        self.mapImages=MapImages();self.mapRenderer=MapRenderer(self.root/'map/land.geojson')
        self.mapExecutor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='time-center-map')
        self._map_running=False;self._map_wanted=None;self._map_key=None;self._map_ready=False;self._map_version=0
        self._map_land='';self._map_solar='';self.mapWorkDone.connect(self.map_done)
        self.workerDone.connect(self.search_done)
        self.timer=QTimer(self);self.timer.setInterval(1000);self.timer.timeout.connect(self.tick);self.timer.start()
        self.last_minute=-1;self.last_day='';self.page=0;self._modal_count=0
        self._stopwatch=self.engine.stopwatch_snapshot()
        self._display=self._stopwatch['display'];self._live=initial;self._last_clock=-1;self._planner_dirty=True
        self.fast=QTimer(self);self.fast.setInterval(33);self.fast.timeout.connect(self.fast_tick)
        self._plan_ids=self.engine.state['planner']['ids']
        self._plan_epoch=time.time();self._plan={'epoch':self._plan_epoch,'rows':[],'reference':'','overlap':[]}
        from services.computations import Computations
        self._compute_gen={};self._busy=set();self.computeDone.connect(self.compute_done)
        self.computations=Computations(self.computeDone.emit)
        self._zones=sorted(available_timezones())
        QGuiApplication.instance().focusObjectChanged.connect(lambda obj:self.focusChanged.emit())
    @Property(bool,notify=focusChanged)
    def textEditing(self):return self.editing()
    @Property('QVariantMap',notify=stopwatchChanged)
    def stopwatch(self):return self._stopwatch
    @Property(str,notify=stopwatchDisplayChanged)
    def stopwatchDisplay(self):return self._display
    @Property('QVariantMap',notify=clocksChanged)
    def home(self):return self._live['home']
    @Property('QVariantMap',notify=clocksChanged)
    def selected(self):return self._live['selected']
    @Property('QVariantList',notify=clocksChanged)
    def cities(self):return self._live['cities']
    @Property('QVariantMap',notify=clocksChanged)
    def now(self):return {key:self._live[key] for key in ('utc','unix','iso','next')}
    @Property('QVariantList',notify=timersChanged)
    def timers(self):return self._live['timers']
    @Property('QVariantList',notify=alarmsChanged)
    def alarms(self):return self._live['alarms']
    @Property(int,notify=modalChanged)
    def modalCount(self):return self._modal_count
    @Property('QStringList',constant=True)
    def zones(self):return self._zones
    @Slot(int)
    def modal(self,delta):self._modal_count=max(0,self._modal_count+delta);self.modalChanged.emit()
    @Slot(result=bool)
    def editing(self):
        focus=QGuiApplication.focusObject()
        return bool(focus and (focus.property('cursorPosition') is not None))
    @Slot(int)
    def setPage(self,page):
        self.page=page;self.sync_fast()
        if self.panel_visible and page in (0,1):self.requestMap()
        if page==6 and self._planner_dirty:QTimer.singleShot(0,self.update_plan)
        if self.panel_visible:self.refresh_live(force=True)
    @Property(bool,notify=busyChanged)
    def calendarBusy(self):return 'calendar' in self._busy
    @Property(bool,notify=busyChanged)
    def plannerBusy(self):return 'planner' in self._busy
    def queue_compute(self,kind,work):
        engine=copy.copy(self.engine);engine.state=copy.deepcopy(self.engine.state);engine.solar_cache=dict(self.engine.solar_cache);engine.clock_cache={}
        generation=self._compute_gen.get(kind,0)+1;self._compute_gen[kind]=generation;self._busy.add(kind);self.busyChanged.emit()
        self.computations.submit(kind,generation,lambda:work(engine))
    @Slot(str,int,object,str)
    def compute_done(self,kind,generation,value,error):
        if generation!=self._compute_gen[kind]:return
        self._busy.discard(kind);self.busyChanged.emit()
        if error:self.status_text(error);logging.warning('%s calculation: %s',kind,error);return
        if kind=='calendar':self._calendar=value;self.calendarChanged.emit()
        elif kind=='planner':
            if value is None:self.status_text('No shared working interval in the next seven days.');return
            self._plan=value;self._planner_dirty=False
            if self._plan_epoch!=value['epoch']:self._plan_epoch=value['epoch'];self.planEpochChanged.emit()
            self.plannerChanged.emit()
    def update_plan(self,reference=None,minutes=None):
        reference=self._plan_epoch if reference is None else reference;ids=copy.deepcopy(self._plan_ids)
        # The reference line never waits for, or retransmits, the complete grid.
        if self._plan_epoch!=reference:self._plan_epoch=reference;self.planEpochChanged.emit()
        def calculate(engine):
            stamp=engine.find_overlap(reference,ids,minutes) if minutes is not None else reference
            return engine.planner(stamp,ids) if stamp is not None else None
        self.queue_compute('planner',calculate)
    def sync_fast(self):
        run=self.panel_visible and self.page in (0,4) and self.engine.state['stopwatch']['running']
        if run and not self.fast.isActive():self.fast.start()
        elif not run:self.fast.stop()
    def fast_tick(self):
        value=precise(self.engine.elapsed(),self.engine.state['prefs']['precision'])
        if value!=self._display:self._display=value;self.stopwatchDisplayChanged.emit()
    @Property('QVariantMap',notify=changed)
    def state(self):return self._state
    @Property('QVariantMap',notify=calendarChanged)
    def calendarData(self):return self._calendar
    @Property('QVariantList',notify=searchChanged)
    def results(self):return self._search
    @Property(str,notify=statusChanged)
    def status(self):return self._status
    @Property('QVariantMap',notify=mapChanged)
    def night(self):return self._night
    @Property(bool,notify=mapAssetsChanged)
    def mapReady(self):return self._map_ready
    @Property(str,notify=mapAssetsChanged)
    def mapLand(self):return self._map_land
    @Property(str,notify=mapAssetsChanged)
    def mapSolar(self):return self._map_solar
    @Slot()
    def requestMap(self):
        if not self.panel_visible:return
        prefs=self.engine.state['prefs'];flags={k:prefs[k] for k in ('mapGrid','mapDay','mapTwilight','mapTerminator')}
        key=(int(time.time()//60),tuple(flags.values()))
        self._map_wanted=(key,flags,dict(self._night))
        if key==self._map_key or self._map_running:return
        self.start_map()
    def start_map(self):
        key,flags,night=self._map_wanted;self._map_running=True
        future=self.mapExecutor.submit(self.mapRenderer.render,flags,night)
        def done(f):
            try:self.mapWorkDone.emit(key,f.result(),'')
            except Exception as exc:self.mapWorkDone.emit(key,None,str(exc))
        future.add_done_callback(done)
    @Slot(object,object,str)
    def map_done(self,key,images,error):
        self._map_running=False
        if key!=self._map_wanted[0]:self.start_map();return
        if error:logging.error('Map rendering: %s',error);self.status_text('Map unavailable; controls and clocks remain usable');return
        self.mapImages.install(images);self._map_key=key;self._map_ready=True;self._map_version+=1
        self._map_land='image://world/land?grid='+str(int(key[1][0]))
        self._map_solar='image://world/solar?v='+str(self._map_version);self.mapAssetsChanged.emit()
    @Property('QVariantMap',notify=plannerChanged)
    def plan(self):return self._plan
    @Property(float,notify=planEpochChanged)
    def planEpoch(self):return self._plan_epoch
    def status_text(self,text):self._status=str(text);self.statusChanged.emit()
    @staticmethod
    def presentation_state(snapshot):
        # Every QML property read converts the entire QVariantMap. Keep large
        # live collections on their dedicated properties, never under settings.
        return copy.deepcopy({key:snapshot[key] for key in ('prefs','map','layout','timerPresets','plannerSettings','quickTools','homeId','alerts')})
    def refresh(self):
        snapshot=self.engine.snapshot()
        state=self.presentation_state(snapshot);state['inspection']=copy.deepcopy(self.preview or {})
        if state!=self._state:self._state=state;self.changed.emit()
        self.refresh_live(force=True,snapshot=snapshot)
        self._stopwatch=self.engine.stopwatch_snapshot();self.stopwatchChanged.emit();self.fast_tick();self.sync_fast()
    def refresh_live(self,force=False,snapshot=None):
        current=snapshot or self.engine.snapshot()
        if self.preview:
            selected=self.engine.clock(self.preview,time.time());selected.update(self.engine.solar(self.preview,dt.datetime.now(dt.timezone.utc).astimezone(ZoneInfo(self.preview['zone'])).date()));current['selected']=selected
        self._live=current
        interval=int(time.time()) if self.engine.state['prefs']['seconds'] else int(time.time()//60)
        if force or interval!=self._last_clock:self._last_clock=interval;self.clocksChanged.emit()
        if force or self.page in (0,3):self.timersChanged.emit()
        if force or self.page==5:self.alarmsChanged.emit()
    @Slot(bool)
    def setVisible(self,value):
        self.panel_visible=value
        self.sync_fast()
        if value:
            self.refresh_live(force=True);self.fast_tick()
            if self.page in (0,1):self.requestMap()
            if self.page==6 and self._planner_dirty:self.update_plan()
    def tick(self):
        try:
            fired=self.engine.tick()
            if fired:
                self.refresh()
                if self.engine.state['prefs']['completion']=='Show panel':self.alertRaised.emit(' · '.join(fired))
                if self.engine.state['prefs']['sound']:
                    try:
                        import winsound
                        sound=self.engine.state['alerts'][-1].get('sound','Default')
                        if sound=='Default':sound=self.engine.state['prefs']['alertSound']
                        if sound!='Silent':winsound.PlaySound(sound,winsound.SND_ALIAS|winsound.SND_ASYNC)
                    except Exception:logging.exception('Sound unavailable; internal alerts remain active')
            if self.panel_visible:
                minute=int(time.time()//60)
                if self.engine.state['prefs']['seconds'] or minute!=self.last_minute or self.page in (0,3,5):self.refresh_live()
                if minute!=self.last_minute:
                    self._night=terminator(time.time());self.mapChanged.emit();self.last_minute=minute
                    if self.page in (0,1):self.requestMap()
                    today=dt.datetime.now(ZoneInfo(self.engine.homezone())).date().isoformat()
                    if today!=self.last_day:self.last_day=today;self.calendarGo(self._calendar['year'],self._calendar['month'],self._calendar['selected'])
        except Exception:logging.exception('Time service tick failed')
    @Slot(str)
    def searchCity(self,query):
        self.generation+=1;token=self.generation
        if len(query.strip())<2:self._search=[];self.searchChanged.emit();return
        self.status_text('Searching…')
        future=self.executor.submit(search,query,dict(self.cache))
        def complete(f):
            try:rows,status=f.result();self.workerDone.emit(token,{'query':query,'rows':rows},status)
            except Exception:self.workerDone.emit(token,{'query':query,'rows':[]},'Search unavailable; saved clocks remain usable')
        future.add_done_callback(complete)
    @Slot()
    def cancelSearch(self):
        self.generation+=1;self._search=[];self.searchChanged.emit()
    @Slot(int,object,str)
    def search_done(self,token,payload,status):
        if token!=self.generation:return
        self._search=payload['rows'];self.searchChanged.emit();self.status_text(status)
        if status.startswith('Map location') and self._search:
            self.preview={**self._search[0],'inspectionKind':'Inspected location'};self.refresh()
        if self._search and status=='Open-Meteo geocoding':
            from services.search import fold
            self.cache[fold(payload['query'])]=self._search
            while len(self.cache)>100:del self.cache[next(iter(self.cache))]
            import copy
            self.writer.submit(self.cachefile,copy.deepcopy(self.cache))
    @Slot(float,float)
    def inspectPoint(self,lon,lat):
        self.generation+=1;token=self.generation
        future=self.executor.submit(inspect_point,lon,lat)
        def done(f):
            try:self.workerDone.emit(token,{'query':'','rows':[f.result()]},'Map location — add to save or inspect its timezone')
            except Exception:self.workerDone.emit(token,{'query':'','rows':[]},'Unable to resolve this location')
        future.add_done_callback(done)
    @Slot(int,int,str)
    def calendarGo(self,year,month,selected):
        try:self.queue_compute('calendar',lambda engine:engine.calendar(year,month,selected))
        except ValueError:self.status_text('Choose a valid calendar date.')
    @Slot()
    def calendarToday(self):
        from zoneinfo import ZoneInfo
        today=dt.datetime.now(ZoneInfo(self.engine.homezone())).date()
        self.calendarGo(today.year,today.month,today.isoformat())
    @Slot(str,result=str)
    def alarmPreview(self,payload):
        try:
            p=json.loads(payload);stamp=self.engine.alarm_preview(p)
            return 'Next: '+dt.datetime.fromtimestamp(stamp,ZoneInfo(p.get('zone') or self.engine.homezone())).strftime('%a %d %b %Y · %H:%M:%S')
        except Exception as exc:return str(exc)
    @Slot(str,result=str)
    def utility(self,payload):
        try:return self.engine.utilities(json.loads(payload))
        except Exception as exc:return str(exc)
    @Slot(str,str,result=str)
    def dateDifference(self,a,b):
        try:return f'{(dt.date.fromisoformat(b)-dt.date.fromisoformat(a)).days:+d} days'
        except ValueError:return 'Use YYYY-MM-DD'
    @Slot(str)
    def newAlarm(self,date):self.alarmEditor.emit(date)
    @Slot(int)
    def goPage(self,page):self.navigate.emit(page)
    @Slot(str,str,result=bool)
    def act(self,action,payload='{}'):
        try:
            p=json.loads(payload or '{}');state=self.engine.state
            if action=='hide':self.hideRequested.emit();return
            if action=='addCity':self.engine.add_city(p);self.preview=None
            elif action=='preview':self.preview={**p,'inspectionKind':'Search result'}
            elif action=='clearInspection':self.preview=None;self._search=[];self.searchChanged.emit()
            elif action=='select':
                state['selected']=p['id'];self.preview=None;self.engine.save()
                c=self.engine.city()
                if state['prefs']['mapFollow'] and c and c.get('lat') is not None:self.focusMap.emit(c['lon'],c['lat'])
            elif action=='city':
                c=self.engine.city(p['id']);op=p['op']
                if c is None:return
                if op=='home':state['home']=c['id']
                elif op=='favorite':c['favorite']=not c['favorite']
                elif op=='remove':
                    state['cities'].remove(c)
                    if state['home']==c['id']:state['home']=None
                    if state['selected']==c['id']:state['selected']=state['cities'][0]['id'] if state['cities'] else None
                elif op in ('up','down'):
                    i=state['cities'].index(c);j=max(0,min(len(state['cities'])-1,i+(-1 if op=='up' else 1)));state['cities'][i],state['cities'][j]=state['cities'][j],state['cities'][i]
                self.engine.save()
            elif action=='focus':
                c=self.engine.city(p['id']) if p.get('id') else self.preview or self.engine.city()
                if c and c.get('lat') is not None:self.focusMap.emit(c['lon'],c['lat'])
                else:self.status_text('Select a city with map coordinates.')
            elif action=='pref':
                key=p['key'];value=p['value']
                if key not in state['prefs']:raise ValueError('Unknown preference')
                default=state['prefs'][key]
                if isinstance(default,bool):value=bool(value)
                elif isinstance(default,int):value=int(value)
                elif isinstance(default,float):value=float(value)
                else:value=str(value)
                if key in ('workStart','workEnd'):value=max(0,min(23,value))
                if key=='precision':value=max(0,min(3,value))
                if key=='weekStart' and value not in (0,6):raise ValueError('Week start must be Monday or Sunday')
                state['prefs'][key]=value;self.engine.save()
            elif action=='map':state['map'].update(zoom=max(1,min(12,float(p['zoom']))),x=(float(p['x'])+.5)%1-.5,y=max(-.5,min(.5,float(p['y']))));self.engine.save()
            elif action=='layout':state['layout'][p['key']]=max(.2,min(.85,float(p['value'])));self.engine.save()
            elif action=='quickTools':state['quickTools']=p['items'];self.engine.save()
            elif action=='timerPreset':
                if p['op']=='add':
                    seconds=float(p['seconds'])
                    if not 0<seconds<=31536000:raise ValueError('Preset duration must be positive, up to one year')
                    state['timerPresets'].append({'name':str(p['name'])[:60] or 'Preset','seconds':seconds})
                else:state['timerPresets'].pop(int(p['index']))
                self.engine.save()
            elif action=='plannerGroup':
                if p['op']=='save':state['planner']['groups'][p['name']]=p['ids']
                else:state['planner']['groups'].pop(p['name'],None)
                self.engine.save()
            elif action=='workHours':
                if p.get('reset'):state['planner']['workHours'].pop(p['id'],None)
                else:state['planner']['workHours'][p['id']]={'start':max(0,min(23,int(p['start']))),'end':max(0,min(23,int(p['end'])))}
                self.engine.save();self.update_plan()
            elif action=='findOverlap':self.update_plan(minutes=int(p.get('minutes',30)))
            elif action=='timer':self.engine.timer(p.pop('op'),p)
            elif action=='stopwatch':self.engine.stopwatch(p['op'])
            elif action=='alarm':
                op=p.pop('op')
                if op=='add':self.engine.add_alarm(p)
                else:self.engine.alarm_action(op,p)
            elif action=='note':state['notes'][p['date']]=str(p['text'])[:10000];self.engine.save()
            elif action=='planner':
                reference=resolve_local(p['date']+'T'+p['time'],p.get('zone') or self.engine.homezone()).timestamp()
                self._plan_ids=p.get('cities');self.update_plan(reference)
            elif action=='planEpoch':self._plan_ids=p.get('cities');self.update_plan(float(p['epoch']))
            elif action=='copy':QGuiApplication.clipboard().setText(str(p['text']));self.status_text('Copied to clipboard')
            elif action=='copyLaps':QGuiApplication.clipboard().setText('Lap\tTotal\tDuration\tChange\n'+'\n'.join(f'{l["n"]}\t{l["total"]}\t{l["duration"]}\t{l["delta"]}' for l in self.engine.stopwatch_snapshot()['laps']));self.status_text('Laps copied as tab-separated values')
            if action=='planner':state['planner']['ids']=self._plan_ids;self.engine.save()
            if action in ('note','timer','alarm','city') or (action=='pref' and p['key'] in ('weekStart','weekends','weeks')):
                self.calendarGo(self._calendar['year'],self._calendar['month'],self._calendar['selected'])
            if action in ('addCity','city','pref'):
                if action!='pref' or p['key'] in ('workStart','workEnd','hour24'):
                    self._planner_dirty=True
                    if self.panel_visible and self.page==6:self.update_plan()
            if action=='pref' and p['key'] in ('mapGrid','mapDay','mapTwilight','mapTerminator') and self.panel_visible and self.page in (0,1):self.requestMap()
            if action=='stopwatch':
                self._stopwatch=self.engine.stopwatch_snapshot();self.stopwatchChanged.emit();self.fast_tick();self.sync_fast()
            elif action not in ('copy','copyLaps','focus','planEpoch','findOverlap'):self.refresh()
            return True
        except Exception as exc:
            self.status_text(str(exc));logging.warning('Action %s: %s',action,exc)
            return False
    def shutdown(self):self.engine.save();self.writer.close();self.computations.close();self.mapExecutor.shutdown(wait=True,cancel_futures=True);self.executor.shutdown(wait=False,cancel_futures=True)
