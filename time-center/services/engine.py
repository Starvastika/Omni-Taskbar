"""Offline timekeeping and atomic persistence; no UI or YASB dependencies."""
import calendar
import copy
import datetime as dt
import json
import logging
import math
import os
from pathlib import Path
import time
import uuid
from collections import OrderedDict
from services.timezones import zone as ZoneInfo
from astral import Observer, moon
from astral import sun
from tzlocal import get_localzone_name
from services.refinements import Refinements,migrate

UTC = dt.timezone.utc
def uid(): return uuid.uuid4().hex[:12]
def wall(): return time.time()
def duration(seconds):
    seconds=max(0,int(math.ceil(seconds)));h,seconds=divmod(seconds,3600);m,s=divmod(seconds,60)
    return f'{h:02}:{m:02}:{s:02}'

def resolve_local(value, zone):
    """First occurrence of an ambiguous local time; reject spring-forward gaps."""
    naive=dt.datetime.fromisoformat(value).replace(tzinfo=None)
    aware=naive.replace(tzinfo=ZoneInfo(zone),fold=0)
    if aware.astimezone(UTC).astimezone(aware.tzinfo).replace(tzinfo=None)!=naive:
        raise ValueError('That local time does not exist because clocks move forward. Choose another time.')
    return aware

def next_alarm(alarm, now):
    zone=ZoneInfo(alarm['zone']);local=dt.datetime.fromtimestamp(now,zone)
    for days in range(9):
        date=local.date()+dt.timedelta(days=days)
        if date.weekday() not in alarm['weekdays']:continue
        try:candidate=resolve_local(f'{date.isoformat()}T{alarm["time"]}',alarm['zone']).timestamp()
        except ValueError:continue
        if candidate>now:return candidate
    return None

class Engine(Refinements):
    def __init__(self, folder):
        self.folder=Path(folder);self.folder.mkdir(parents=True,exist_ok=True);self.file=self.folder/'state.json'
        self.state={'version':1,'cities':[],'home':None,'selected':None,'prefs':{'hour24':True,'seconds':True,'sound':True,'weeks':True,'workStart':9,'workEnd':17},'timers':[],'alarms':[],'alerts':[],'notes':{},'map':{'zoom':1,'x':0,'y':0},'stopwatch':{'elapsed':0,'running':False,'laps':[],'anchor':None}}
        if self.file.exists():
            try:
                data=json.loads(self.file.read_text('utf-8'));self.state.update(data)
            except (OSError,ValueError):
                logging.exception('State could not be read; retained as state.corrupt.json')
                self.file.replace(self.folder/'state.corrupt.json')
        migrated=migrate(self.state,self.file)
        self.localzone=get_localzone_name();self.solar_cache={};self.clock_cache={};self.planner_cache=OrderedDict();self.occurrence_cache=OrderedDict()
        sw=self.state['stopwatch'];self.sw_base=sw['elapsed']
        if sw['running'] and sw.get('anchor'):self.sw_base+=max(0,wall()-sw['anchor'])
        self.sw_mono=time.perf_counter_ns()
        if migrated:self.save()

    def elapsed(self):return self.sw_base+((time.perf_counter_ns()-self.sw_mono)/1e9 if self.state['stopwatch']['running'] else 0)

    def save(self):
        data=copy.deepcopy(self.state);data['stopwatch']['elapsed']=self.elapsed();data['stopwatch']['anchor']=wall()
        if getattr(self,'writer',None):self.writer.submit(self.file,data);return
        temporary=self.file.with_suffix('.tmp')
        with temporary.open('w',encoding='utf-8') as f:json.dump(data,f,ensure_ascii=False,indent=2);f.flush();os.fsync(f.fileno())
        os.replace(temporary,self.file)

    def city(self, identity=None):return next((c for c in self.state['cities'] if c['id']==(identity or self.state['selected'])),None)
    def homezone(self):return (self.city(self.state['home']) or {}).get('zone',self.localzone) if self.state['home'] else self.localzone

    def add_city(self, city):
        ZoneInfo(city['zone'])
        key=(round(float(city.get('lat') or 0),4),round(float(city.get('lon') or 0),4),city['zone'])
        match=next((c for c in self.state['cities'] if (round(c.get('lat') or 0,4),round(c.get('lon') or 0,4),c['zone'])==key),None)
        if match:self.state['selected']=match['id'];self.save();return match
        item={**city,'id':uid(),'favorite':False};self.state['cities'].append(item);self.state['selected']=item['id'];self.save();return item

    def solar(self,city,date):
        if city is None or city.get('lat') is None:return {'sunrise':'Set Home city','sunset':'—','dayLength':'—','state':'Location not set'}
        key=(city['lat'],city['lon'],date.isoformat(),city['zone'])
        if key in self.solar_cache:return self.solar_cache[key]
        observer=Observer(city['lat'],city['lon']);zone=ZoneInfo(city['zone']);events={}
        for name,func,kwargs in [('sunrise',sun.sunrise,{}),('sunset',sun.sunset,{}),('civilDawn',sun.dawn,{'depression':6}),('civilDusk',sun.dusk,{'depression':6}),('nauticalDawn',sun.dawn,{'depression':12}),('nauticalDusk',sun.dusk,{'depression':12}),('astronomicalDawn',sun.dawn,{'depression':18}),('astronomicalDusk',sun.dusk,{'depression':18}),('noon',sun.noon,{}),('midnight',sun.midnight,{})]:
            try:events[name]=func(observer,date=date,tzinfo=zone,**kwargs)
            except ValueError:events[name]=None
        result={name:value.strftime('%H:%M') if value else 'No event (polar)' for name,value in events.items()}
        result['dayLength']=duration((events['sunset']-events['sunrise']).total_seconds()) if events['sunset'] and events['sunrise'] else 'Polar day / night'
        result['moonPhase']=round(moon.phase(date),1)
        result['eventEpochs']={k:v.timestamp() for k,v in events.items() if v}
        if len(self.solar_cache)>400:self.solar_cache.clear()
        self.solar_cache[key]=result;return result

    def clock(self,city,now):
        key=(city.get('id',city.get('zone')),int(now) if self.state['prefs']['seconds'] else int(now//60),self.homezone(),self.state['prefs']['hour24'],self.state['prefs']['dateFormat'],self.state['prefs']['seconds'])
        if key in self.clock_cache:return {**self.clock_cache[key],**{k:v for k,v in city.items() if k not in ('time','date')}}
        zone=city.get('zone',self.localzone);local=dt.datetime.fromtimestamp(now,ZoneInfo(zone));home=dt.datetime.fromtimestamp(now,ZoneInfo(self.homezone()))
        offset=int(local.utcoffset().total_seconds());diff=(local.utcoffset()-home.utcoffset()).total_seconds()/3600
        fmt=('%H:%M' if self.state['prefs']['hour24'] else '%I:%M')+(':%S' if self.state['prefs']['seconds'] else '')+('' if self.state['prefs']['hour24'] else ' %p')
        data={**city,'time':local.strftime(fmt),'date':local.strftime('%a, %d %b %Y'),'iso':local.isoformat(timespec='seconds'),'offset':f'UTC{"+" if offset>=0 else "−"}{abs(offset)//3600:02}:{abs(offset)%3600//60:02}','dst':bool(local.dst()),'difference':f'{diff:+g} h','relation':{-1:'Yesterday',0:'Today',1:'Tomorrow'}.get((local.date()-home.date()).days,local.date().isoformat()),'week':local.isocalendar().week,'day':local.timetuple().tm_yday,'zone':zone}
        if city.get('lat') is not None:
            elevation=sun.elevation(Observer(city['lat'],city['lon']),dt.datetime.fromtimestamp(now,UTC))
            data['solarState']='Day' if elevation>0 else 'Civil twilight' if elevation>-6 else 'Nautical twilight' if elevation>-12 else 'Astronomical twilight' if elevation>-18 else 'Night'
        else:data['solarState']='Location not set'
        data['abbreviation']=local.tzname();data['offsetSeconds']=offset;data['localSeconds']=local.hour*3600+local.minute*60+local.second
        if self.state['prefs']['dateFormat']=='ISO':data['date']=local.date().isoformat()
        if len(self.clock_cache)>max(100,3*len(self.state['cities'])):self.clock_cache.clear()
        self.clock_cache[key]=dict(data)
        return data

    def alert(self,kind,item,now):
        self.state['alerts'].append({'id':uid(),'kind':kind,'source':item['id'],'label':item['label'],'time':now,'sound':item.get('sound','Default')})
        self.state['alerts']=self.state['alerts'][-50:]

    def tick(self,now=None):
        now=wall() if now is None else now;fired=[]
        for timer in self.state['timers']:
            if timer['status']=='running' and now>=timer['deadline']:
                timer['status']='completed';timer['remaining']=0;self.alert('timer',timer,now);fired.append(timer['label'])
                if timer.get('repeat'):
                    cycles=int((now-timer['deadline'])//timer['duration'])+1
                    timer['deadline']+=cycles*timer['duration'];timer['remaining']=timer['duration'];timer['status']='running'
        for alarm in self.state['alarms']:
            if alarm['enabled'] and alarm.get('next') is not None and now>=alarm['next']:
                self.alert('alarm',alarm,now);fired.append(alarm['label'])
                if alarm['weekdays']:alarm['next']=next_alarm(alarm,now)
                else:alarm['enabled']=False;alarm['next']=None
        if fired:self.save()
        return fired

    def timer(self,action,p):
        now=wall()
        if action=='add':
            seconds=float(p['seconds'])
            if not math.isfinite(seconds) or not 0<seconds<=31536000:raise ValueError('Duration must be between one second and one year.')
            self.state['timers'].append({'id':uid(),'label':str(p.get('label') or 'Timer')[:100],'duration':seconds,'remaining':seconds,'deadline':now+seconds,'status':'running','repeat':bool(p.get('repeat',False)),'sound':p.get('sound','Default')})
        else:
            t=next(x for x in self.state['timers'] if x['id']==p['id'])
            if action=='delete':self.state['timers'].remove(t)
            elif action=='duplicate':self.state['timers'].append({**copy.deepcopy(t),'id':uid(),'label':t['label']+' copy','status':'paused','remaining':t['duration'],'deadline':now+t['duration']})
            elif action=='edit':
                seconds=float(p['seconds'])
                if not math.isfinite(seconds) or not 0<seconds<=31536000:raise ValueError('Duration must be positive and at most one year.')
                if seconds!=t['duration']:
                    t.update(duration=seconds,remaining=seconds,deadline=now+seconds)
                    if t['status']=='completed':t['status']='paused'
                t.update(label=str(p.get('label') or 'Timer')[:100],repeat=bool(p.get('repeat',False)),sound=p.get('sound','Default'))
            elif action=='repeat':t['repeat']=not t.get('repeat',False)
            elif action=='pause':
                if t['status']=='running':t['remaining']=max(0,t['deadline']-now);t['status']='paused'
            elif action=='resume':
                if t['status']=='completed':t['remaining']=t['duration']
                if t['status']!='running':t['deadline']=now+t['remaining'];t['status']='running'
            elif action in ('reset','restart'):
                t.update(remaining=t['duration'],deadline=now+t['duration'],status='running' if action=='restart' else 'paused')
            elif action=='extend':
                remaining=max(0,t['deadline']-now) if t['status']=='running' else t['remaining']
                extra=max(float(p['seconds']),1-remaining,1-t['duration']);t['duration']+=extra;t['remaining']=remaining+extra
                if t['status']=='running':t['deadline']+=extra
                elif t['status']=='completed':t['status']='paused'
        self.save()

    def stopwatch(self,action):
        sw=self.state['stopwatch'];elapsed=self.elapsed()
        if action=='start' and not sw['running']:self.sw_mono=time.perf_counter_ns();sw['running']=True
        elif action=='pause':self.sw_base=elapsed;sw['running']=False
        elif action=='lap' and sw['running']:
            previous=sw['laps'][-1]['total'] if sw['laps'] else 0;sw['laps'].append({'total':elapsed,'delta':elapsed-previous})
        elif action=='reset':sw['running']=False;sw['laps']=[];self.sw_base=0
        self.save()

    def add_alarm(self,p):
        zone=p.get('zone') or self.homezone();ZoneInfo(zone)
        weekdays=sorted(set(int(x) for x in p.get('weekdays',[]) if 0<=int(x)<=6))
        dt.time.fromisoformat(p['time'])
        a={'id':uid(),'label':str(p.get('label') or 'Alarm')[:100],'time':p['time'],'weekdays':weekdays,'zone':zone,'enabled':True,'date':p.get('date',''),'notes':str(p.get('notes',''))[:10000],'snoozeMinutes':int(p.get('snoozeMinutes',self.state['prefs']['snoozeMinutes'])),'sound':p.get('sound','Default')}
        a['next']=next_alarm(a,wall()) if weekdays else resolve_local(p['date']+'T'+p['time'],zone).timestamp()
        if a['next'] is None or a['next']<=wall():raise ValueError('Choose a future date/time.')
        self.state['alarms'].append(a);self.save();return a

    def alarm_action(self,action,p):
        if action in ('dismiss','snooze'):
            alert=next(x for x in self.state['alerts'] if x['id']==p['id'])
            if action=='snooze':
                source=next((a for a in self.state['alarms'] if a['id']==alert['source']),{})
                minutes=int(p.get('minutes',source.get('snoozeMinutes',self.state['prefs']['snoozeMinutes'])))
                self.state['alarms'].append({'id':uid(),'label':alert['label']+' (snooze)','time':'','weekdays':[],'zone':self.homezone(),'enabled':True,'next':wall()+minutes*60,'notes':'','snoozeMinutes':minutes,'sound':source.get('sound','Default')})
            self.state['alerts'].remove(alert)
        else:
            a=next(x for x in self.state['alarms'] if x['id']==p['id'])
            if action=='delete':self.state['alarms'].remove(a)
            elif action=='duplicate':self.state['alarms'].append({**copy.deepcopy(a),'id':uid(),'label':a['label']+' copy','enabled':False})
            elif action=='edit':
                replacement={**a,**p};replacement['next']=self.alarm_preview(replacement);replacement.pop('id',None)
                a.update(replacement)
            elif action=='snoozeAlarm':a['next']=wall()+a.get('snoozeMinutes',self.state['prefs']['snoozeMinutes'])*60;a['enabled']=True
            elif action=='toggle':
                turn_on=not a['enabled']
                if turn_on:
                    if a['weekdays']:a['next']=next_alarm(a,wall())
                    elif not a.get('next') or a['next']<=wall():raise ValueError('This one-time alarm has passed. Create a new alarm.')
                a['enabled']=turn_on
        self.save()

    def snapshot(self):
        now=wall();cities=[self.clock(c,now) for c in self.state['cities']]
        if self.state['prefs']['citySolar']:
            for c in cities:c.update(self.solar(c,dt.datetime.fromtimestamp(now,ZoneInfo(c['zone'])).date()))
        homecity=self.city(self.state['home']) if self.state['home'] else None
        home=self.clock(homecity or {'name':'Local time','zone':self.localzone},now)
        home.update(self.solar(homecity,dt.datetime.fromtimestamp(now,ZoneInfo(home['zone'])).date()))
        selected=self.city();selectedclock=self.clock(selected,now) if selected else dict(home)
        if selected:
            localdate=dt.datetime.fromtimestamp(now,ZoneInfo(selected['zone'])).date()
            selectedclock.update(self.solar(selected,localdate))
            future=[]
            for date in (localdate,localdate+dt.timedelta(days=1)):
                for kind,stamp in self.solar(selected,date).get('eventEpochs',{}).items():
                    if kind in ('sunrise','sunset') and stamp>now:future.append((stamp,kind))
            selectedclock['nextSolar']=min(future)[1]+' '+dt.datetime.fromtimestamp(min(future)[0],ZoneInfo(selected['zone'])).strftime('%a %H:%M') if future else 'No sunrise/sunset in next two days'
        timers=[]
        for t in self.state['timers']:
            remaining=max(0,t['deadline']-now) if t['status']=='running' else t['remaining']
            timers.append({**t,'remainingSeconds':remaining,'display':duration(remaining),'progress':max(0,min(1,1-remaining/t['duration']))})
        alarms=[{**a,'countdown':('in '+duration(a['next']-now)) if a['enabled'] and a.get('next') else 'Disabled','nextText':dt.datetime.fromtimestamp(a['next'],ZoneInfo(a['zone'])).strftime('%a %d %b %H:%M:%S') if a.get('next') else 'Finished'} for a in self.state['alarms']]
        next_events=[(t['deadline'],t['label']) for t in self.state['timers'] if t['status']=='running']+[(a['next'],a['label']) for a in self.state['alarms'] if a['enabled'] and a.get('next')]
        sw=self.state['stopwatch'];elapsed=self.elapsed()
        return {'home':home,'selected':selectedclock,'cities':cities,'timers':timers,'alarms':alarms,'alerts':self.state['alerts'],'prefs':self.state['prefs'],'map':self.state['map'],'layout':self.state['layout'],'timerPresets':self.state['timerPresets'],'plannerSettings':self.state['planner'],'quickTools':self.state['quickTools'],'homeId':self.state['home'],'stopwatch':self.stopwatch_snapshot(),'next':min(next_events)[1]+' · '+duration(min(next_events)[0]-now) if next_events else 'No upcoming alarms or timers','utc':dt.datetime.fromtimestamp(now,UTC).strftime('%H:%M:%S UTC'),'unix':int(now),'iso':dt.datetime.fromtimestamp(now,UTC).isoformat(timespec='seconds')}

    def planner(self,reference,ids):
        cities=list(self.state['cities']) if ids is None else [c for c in self.state['cities'] if c['id'] in ids]
        if not any(c['zone']==self.homezone() for c in cities):cities=[{'name':'Home','zone':self.homezone()},*cities]
        now=dt.datetime.fromtimestamp(reference,UTC);start=now.replace(hour=0,minute=0,second=0,microsecond=0);rows=[]
        key=(start.timestamp(),tuple((c.get('id'),c['name'],c['zone'],c.get('lat'),c.get('lon'),self.work_range(c)) for c in cities))
        cached=self.planner_cache.get(key)
        if cached is None:
            grids=[];overlap=[True]*24;hours=[start+dt.timedelta(hours=h) for h in range(24)]
            for c in cities:
                cells=[];zone=ZoneInfo(c['zone']);lo,hi=self.work_range(c)
                observer=Observer(c['lat'],c['lon']) if c.get('lat') is not None else None
                for h,utc in enumerate(hours):
                    local=utc.astimezone(zone);hour=local.hour
                    working=lo<=hour<hi if lo<hi else hour>=lo or hour<hi
                    overlap[h]=overlap[h] and working
                    solar=sun.elevation(observer,local)>0 if observer else None
                    cells.append({'hour':local.strftime('%H:%M'),'date':local.strftime('%d %b'),'working':working,'day':solar,'epoch':utc.timestamp()})
                grids.append(cells)
            cached=(grids,overlap);self.planner_cache[key]=cached
            while len(self.planner_cache)>8:self.planner_cache.popitem(last=False)
        else:self.planner_cache.move_to_end(key)
        grids,overlap=cached
        fmt='%a %d %b '+('%H:%M' if self.state['prefs']['hour24'] else '%I:%M %p')
        for c,cells in zip(cities,grids):
            selected=now.astimezone(ZoneInfo(c['zone']));rows.append({'name':c['name'],'zone':c['zone'],'time':selected.strftime(fmt),'cells':cells})
        return {'rows':rows,'overlap':overlap,'reference':now.isoformat(timespec='minutes'),'epoch':reference}

def terminator(now):
    utc=dt.datetime.fromtimestamp(now,UTC);century=sun.julianday_to_juliancentury(sun.julianday(utc))
    decl=sun.sun_declination(century);eot=sun.eq_of_time(century);minutes=utc.hour*60+utc.minute+utc.second/60
    sublon=((720-minutes-eot)/4+180)%360-180
    tangent=math.tan(math.radians(decl)) or 1e-9
    points=[[lon,math.degrees(math.atan(-math.cos(math.radians(lon-sublon))/tangent))] for lon in range(-180,181,2)]
    return {'points':points,'northNight':decl<0,'subsolar':[sublon,decl]}
