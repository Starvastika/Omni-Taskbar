"""Version-two preferences and richer, local-only time/calendar utilities."""
import calendar
import copy
import datetime as dt
import math
import shutil
import statistics
import time
from functools import lru_cache
from services.timezones import zone as ZoneInfo

PREFS = {
    'precision':2, 'weekStart':0, 'weekends':True, 'calendarView':'Month',
    'dateFormat':'Long', 'density':'Detailed', 'reduceMotion':False, 'animationMs':210,
    'citySort':'Custom', 'cityFilter':'All', 'citySolar':False,
    'timerSort':'Created', 'timerFilter':'All', 'timerDetailed':True,
    'alarmSort':'Next', 'alarmFilter':'All', 'snoozeMinutes':5,
    'alertSound':'SystemExclamation', 'completion':'Show panel',
    'mapDay':True, 'mapTwilight':False, 'mapTerminator':True, 'mapGrid':True,
    'mapLabels':False, 'mapLegend':True, 'mapFollow':False, 'mapSun':True,
    'mapCoordinates':True, 'mapDefaultZoom':1, 'plannerStep':15, 'plannerZoom':80,
}
EXTRA = {'layout':{'worldSplit':.68,'worldVertical':.64,'calendarSplit':.68},
         'timerPresets':[{'name':f'{m}m','seconds':m*60} for m in (5,15,25,45,50,60,90)],
         'planner':{'ids':None,'groups':{},'workHours':{}},
         'quickTools':['Today','Copy ISO','5m timer','Stopwatch','New Alarm','Planner']}

def fill_missing(target,defaults):
    for key,value in defaults.items():
        if key not in target:target[key]=copy.deepcopy(value)
        elif isinstance(value,dict) and isinstance(target[key],dict):fill_missing(target[key],value)

def migrate(state,path):
    old=int(state.get('version',1))
    if old<2 and path.exists():
        backup=path.with_name('state.v1.before-refinement.json')
        if not backup.exists():
            with path.open('rb') as source,backup.open('xb') as out:shutil.copyfileobj(source,out)
    fill_missing(state,EXTRA);fill_missing(state['prefs'],PREFS)
    for timer in state['timers']:fill_missing(timer,{'repeat':False,'sound':'Default'})
    for alarm in state['alarms']:fill_missing(alarm,{'notes':'','snoozeMinutes':state['prefs']['snoozeMinutes'],'sound':'Default'})
    state['version']=max(old,2)
    return old<2

def precise(seconds,digits=2):
    digits=max(0,min(3,int(digits)));scale=10**digits
    units=max(0,int(seconds*scale));whole,fraction=divmod(units,scale)
    h,rest=divmod(whole,3600);m,s=divmod(rest,60)
    return f'{h:02}:{m:02}:{s:02}'+(f'.{fraction:0{digits}d}' if digits else '')

@lru_cache(maxsize=48)
def month_dates(year,month,weekstart):
    return tuple(d for week in calendar.Calendar(weekstart).monthdatescalendar(year,month) for d in week)

class Refinements:
    def stopwatch_snapshot(self):
        sw=self.state['stopwatch'];digits=self.state['prefs']['precision']
        # Laps are append-only until reset; avoid rebuilding history on clock ticks.
        key=(digits,len(sw['laps']),sw['laps'][-1]['total'] if sw['laps'] else None)
        if getattr(self,'_lap_key',None)!=key:
            values=[lap['delta'] for lap in sw['laps']];laps=[]
            best=min(values) if values else 0;slowest=max(values) if values else 0
            for i,lap in enumerate(sw['laps']):
                difference=lap['delta']-(values[i-1] if i else lap['delta'])
                laps.append({'id':str(i+1),'n':i+1,'total':precise(lap['total'],digits),'duration':precise(lap['delta'],digits),
                             'delta':('+' if difference>=0 else '−')+precise(abs(difference),digits),
                             'best':lap['delta']==best,'slowest':lap['delta']==slowest})
            self._lap_stats={'laps':laps,'best':precise(best,digits) if values else '—',
                'slowest':precise(slowest,digits) if values else '—',
                'average':precise(statistics.mean(values),digits) if values else '—',
                'median':precise(statistics.median(values),digits) if values else '—'}
            self._lap_key=key
        elapsed=self.elapsed()
        return {'running':sw['running'],'elapsed':elapsed,'display':precise(elapsed,digits),**self._lap_stats}

    def alarm_preview(self,p):
        from services.engine import next_alarm,resolve_local
        zone=p.get('zone') or self.homezone();ZoneInfo(zone)
        dt.time.fromisoformat(p['time'])
        weekdays=p.get('weekdays',[])
        stamp=next_alarm({**p,'zone':zone},time.time()) if weekdays else resolve_local(p['date']+'T'+p['time'],zone).timestamp()
        if stamp is None or stamp<=time.time():raise ValueError('Choose a future date/time.')
        return stamp

    def occurrence_source(self):
        return (self.homezone(),tuple((a['id'],a['label'],a.get('next'),a['time'],tuple(a['weekdays']),a['zone'],a.get('notes','')) for a in self.state['alarms'] if a['enabled']),tuple((t['id'],t['label'],t['deadline']) for t in self.state['timers'] if t['status']=='running'))

    def events_on(self,date,source=None):
        source=self.occurrence_source() if source is None else source
        key=(date,source);cached=self.occurrence_cache.get(key)
        if cached is not None:self.occurrence_cache.move_to_end(key);return cached
        from services.engine import resolve_local
        homezone=ZoneInfo(self.homezone());events=[]
        for alarm in self.state['alarms']:
            if not alarm['enabled']:continue
            stamps=[]
            if alarm['weekdays']:
                first=dt.datetime.combine(date,dt.time(),homezone).astimezone(ZoneInfo(alarm['zone'])).date()
                for delta in range(3):
                    day=first+dt.timedelta(days=delta)
                    if day.weekday() not in alarm['weekdays']:continue
                    try:stamp=resolve_local(day.isoformat()+'T'+alarm['time'],alarm['zone']).timestamp()
                    except ValueError:continue
                    if dt.datetime.fromtimestamp(stamp,homezone).date()==date:stamps.append(stamp)
            elif alarm.get('next') and dt.datetime.fromtimestamp(alarm['next'],homezone).date()==date:stamps=[alarm['next']]
            for stamp in stamps:
                local=dt.datetime.fromtimestamp(stamp,homezone)
                events.append({'id':alarm['id'],'kind':'Alarm','label':alarm['label'],'time':local.strftime('%H:%M:%S'),'minute':local.hour*60+local.minute+local.second/60,'epoch':stamp,'notes':alarm.get('notes','')})
        for timer in self.state['timers']:
            local=dt.datetime.fromtimestamp(timer['deadline'],homezone)
            if timer['status']=='running' and local.date()==date:
                events.append({'id':timer['id'],'kind':'Timer','label':timer['label'],'time':local.strftime('%H:%M:%S'),'minute':local.hour*60+local.minute,'epoch':timer['deadline'],'notes':''})
        events.sort(key=lambda e:e['epoch']);self.occurrence_cache[key]=events
        while len(self.occurrence_cache)>256:self.occurrence_cache.popitem(last=False)
        return events

    def calendar(self,year,month,selected):
        year=max(1900,min(2200,int(year)));month=max(1,min(12,int(month)))
        today=dt.datetime.now(ZoneInfo(self.homezone())).date();chosen=dt.date.fromisoformat(selected)
        weekstart=self.state['prefs']['weekStart'];cache={};source=self.occurrence_source()
        def events(date):
            key=date.isoformat()
            if key not in cache:cache[key]=self.events_on(date,source)
            return cache[key]
        def cell(date,displaymonth,with_events=True):
            return {'date':date.isoformat(),'day':date.day,'current':date.month==displaymonth,'today':date==today,
                    'selected':date==chosen,'week':date.isocalendar().week,'weekend':date.weekday()>=5,
                    'note':bool(self.state['notes'].get(date.isoformat())), 'alarms':len(events(date)) if with_events else 0}
        cells=[cell(d,month) for d in month_dates(year,month,weekstart)]
        first=chosen-dt.timedelta(days=(chosen.weekday()-weekstart)%7)
        weekdays=[]
        for n in range(7):
            date=first+dt.timedelta(days=n)
            weekdays.append({**cell(date,date.month),'title':date.strftime('%a %d %b'),'events':events(date),'noteText':self.state['notes'].get(date.isoformat(),'')})
        months=[{'month':m,'title':calendar.month_name[m],'cells':[cell(d,m,False) for d in month_dates(year,m,weekstart)]} for m in range(1,13)]
        solar=self.solar(self.city(self.state['home']) if self.state['home'] else None,chosen)
        return {'title':f'{calendar.month_name[month]} {year}','year':year,'month':month,'cells':cells,'selected':selected,
                'fullDate':chosen.strftime('%A, %d %B %Y'),'detail':chosen.strftime('%A, %d %B %Y')+f' · ISO week {chosen.isocalendar().week} · Day {chosen.timetuple().tm_yday} · {(chosen-today).days:+d} days from today',
                'note':self.state['notes'].get(selected,''),'events':[e['time']+' · '+e['label'] for e in events(chosen)],
                'agenda':events(chosen),'weekDays':weekdays,'yearMonths':months,'solar':solar,
                'remaining':(dt.date(chosen.year,12,31)-chosen).days,'dayOfYear':chosen.timetuple().tm_yday,
                'isoWeek':chosen.isocalendar().week,'daysFromToday':(chosen-today).days,
                'headers':[calendar.day_abbr[(weekstart+i)%7] for i in range(7)]}

    def work_range(self,city):
        override=self.state['planner']['workHours'].get(city.get('id',''),{})
        return override.get('start',self.state['prefs']['workStart']),override.get('end',self.state['prefs']['workEnd'])

    def find_overlap(self,reference,ids,minutes):
        cities=[c for c in self.state['cities'] if ids is None or c['id'] in ids]
        if not any(c['zone']==self.homezone() for c in cities):cities.insert(0,{'name':'Home','zone':self.homezone()})
        minutes=max(15,min(120,int(minutes)));candidate=math.ceil(reference/900)*900
        for step in range(7*96):
            stamp=candidate+step*900;okay=True
            for city in cities:
                lo,hi=self.work_range(city);zone=ZoneInfo(city['zone'])
                for minute in range(minutes):
                    local=dt.datetime.fromtimestamp(stamp+minute*60,zone);h=local.hour+local.minute/60
                    if not (lo<=h<hi if lo<hi else h>=lo or h<hi):okay=False;break
                if not okay:break
            if okay:return stamp
        return None

    def utilities(self,p):
        from services.engine import resolve_local
        mode=p.get('mode','Now');zone=p.get('zone') or self.homezone();now=dt.datetime.now(ZoneInfo(zone))
        if mode=='Now':
            return f'UTC: {now.astimezone(dt.timezone.utc).isoformat(timespec="milliseconds")}\nUnix seconds: {now.timestamp():.3f}\nUnix milliseconds: {int(now.timestamp()*1000)}\nLocal RFC3339: {now.isoformat(timespec="milliseconds")}\nDay {now.timetuple().tm_yday} · ISO week {now.isocalendar().week}\nLeap year: {calendar.isleap(now.year)}'
        if mode=='Epoch':
            stamp=float(p['a'])/(1000 if p.get('milliseconds') else 1)
            return dt.datetime.fromtimestamp(stamp,ZoneInfo(zone)).isoformat(timespec='milliseconds')
        def parse(value,zone):
            parsed=dt.datetime.fromisoformat(value)
            return parsed if parsed.tzinfo else resolve_local(value,zone)
        first=parse(p['a'],zone)
        if mode=='Difference':
            second=parse(p['b'],p.get('otherZone') or zone);seconds=second.timestamp()-first.timestamp()
            return f'{seconds:+.3f} seconds\n{seconds/3600:+.6f} hours\n{seconds/86400:+.6f} elapsed days'
        if mode=='Add duration':return dt.datetime.fromtimestamp(first.timestamp()+float(p['seconds']),ZoneInfo(zone)).isoformat(timespec='milliseconds')
        if mode=='Convert':return first.astimezone(ZoneInfo(p['otherZone'])).isoformat(timespec='milliseconds')
        raise ValueError('Choose a utility.')
