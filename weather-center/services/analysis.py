"""Model comparison, honest ensemble statistics, history summaries and solar data."""
import datetime as dt,math,statistics,time
from collections import defaultdict
from zoneinfo import ZoneInfo
from astral import Observer,moon,sun,SunDirection
from services.presentation import rows,metrics,LABELS
from services.units import convert,stamp,pretty
from services.providers import MODELS
def solar(loc,date,prefs=None):
 day=dt.date.fromisoformat(date);zone=ZoneInfo(loc['zone'])
 # Geocoder elevation is altitude above sea level, not the observer's height
 # above their unobstructed local horizon. Do not silently treat it as the latter.
 o=Observer(loc['lat'],loc['lon'],0);values=[{'label':'Calculated local date','value':day.isoformat()+' · '+loc['zone']}];events={};fmt='%H:%M %Z' if not prefs or prefs.get('hour24',True) else '%I:%M %p %Z'
 for name,func,args in [('Sunrise',sun.sunrise,{}),('Sunset',sun.sunset,{}),('Civil dawn',sun.dawn,{'depression':6}),('Civil dusk',sun.dusk,{'depression':6}),('Nautical dawn',sun.dawn,{'depression':12}),('Nautical dusk',sun.dusk,{'depression':12}),('Astronomical dawn',sun.dawn,{'depression':18}),('Astronomical dusk',sun.dusk,{'depression':18}),('Solar noon',sun.noon,{})]:
  try:event=func(o,date=day,tzinfo=zone,**args);events[name]=event;value=event.strftime(fmt)
  except ValueError:value='No event at this latitude/date'
  values.append({'label':name,'value':value})
 if 'Sunrise' in events and 'Sunset' in events:
  duration=(events['Sunset'].timestamp()-events['Sunrise'].timestamp())/3600;values.append({'label':'Selected-date daylight','value':f'{duration:.2f} h'})
 else:values.append({'label':'Selected-date daylight','value':'No sunrise / sunset pair at this latitude/date'})
 for name,direction in [('Morning golden hour',SunDirection.RISING),('Evening golden hour',SunDirection.SETTING)]:
  try:
   start,end=sun.golden_hour(o,date=day,direction=direction,tzinfo=zone);value=start.strftime(fmt)+' → '+end.strftime(fmt)
  except ValueError:value='No event at this latitude/date'
  values.append({'label':name+' · −4° to +6°','value':value})
 for name,func in [('Moonrise',moon.moonrise),('Moonset',moon.moonset)]:
  try:event=func(o,date=day,tzinfo=zone);value=event.strftime(fmt) if event else 'No event on this local date'
  except ValueError:value='No event at this latitude/date'
  values.append({'label':name+' · calculated','value':value})
 now=dt.datetime.now(dt.UTC);values.extend([{'label':'Solar elevation now','value':f'{sun.elevation(o,now):.1f}°'},{'label':'Solar azimuth now','value':f'{sun.azimuth(o,now):.1f}°'},{'label':'Moon phase · Astral calculation','value':f'{moon.phase(day):.1f} / 28'}]);return values

def previous_runs_view(data,loc,prefs):
 result=rows(data,'hourly',loc,prefs);series=[];changes=[]
 for variable in ('temperature_2m','precipitation','wind_speed_10m','pressure_msl'):
  for offset in (0,1,2):
   key=variable if offset==0 else variable+'_previous_day'+str(offset)
   if key not in data.get('hourly',{}):continue
   unit=convert(0,data.get('hourly_units',{}).get(key,''),prefs,key)[1]
   series.append({'key':key,'label':LABELS[variable]+' · '+('current' if offset==0 else f'{offset*24} h lead-time archive'),'unit':unit,'variable':variable})
   if offset:
    change_key=key+'_change';changes.append({'key':change_key,'label':LABELS[variable]+f' · current minus {offset*24} h archive','unit':unit,'variable':variable})
    for row in result:
     v=row['values']
     if variable in v and key in v:v[change_key]=v[variable]-v[key]
 return {'rows':result,'series':series,'changeSeries':changes,'source':'NOAA GFS via Open-Meteo Previous Runs',
         'limitation':'Archives are fixed lead-time offsets before each valid timestamp, not complete snapshots of a single initialization. Missing archive values remain unavailable; differences are not forecast skill or observed error.'}
def model_view(data,loc,prefs):
 hourly=data.get('hourly',{});times=hourly.get('time',[]);result=[];series=[]
 for model in MODELS[1:]:
  key='temperature_2m_'+model['id'];values=hourly.get(key,[])
  if values:series.append({'key':key,'label':model['name'],'unit':'°F' if prefs['temperature']=='F' else '°C'})
 for i,epoch in enumerate(times):
  values={}
  for key,array in hourly.items():
   if key=='time' or i>=len(array) or array[i] is None:continue
   unit=data.get('hourly_units',{}).get(key,'');values[key]=convert(array[i],unit,prefs)[0]
  temps=[values[s['key']] for s in series if s['key'] in values]
  result.append({'epoch':epoch,'label':stamp(epoch,loc['zone'],prefs['hour24']),'date':dt.datetime.fromtimestamp(epoch,ZoneInfo(loc['zone'])).strftime('%a %d %b'),'night':False,'values':values,'formatted':{},'spread':max(temps)-min(temps) if temps else None})
 return {'rows':result,'series':series,'models':MODELS[1:],'source':'Open-Meteo deterministic model comparison','run':'Exact run initialization is not returned by this endpoint','heuristic':'Spread is max − min across available deterministic temperatures; it is model disagreement, not an accuracy probability.'}
def ensemble_view(data,loc,prefs):
 hourly=data.get('hourly',{});times=hourly.get('time',[]);members=[(k,v) for k,v in hourly.items() if k=='temperature_2m' or k.startswith('temperature_2m_member')];result=[]
 for i,epoch in enumerate(times):
  vals=sorted(convert(a[i],'°C',prefs)[0] for _,a in members if i<len(a) and a[i] is not None)
  if not vals:continue
  def percentile(q):
   pos=(len(vals)-1)*q;lo=int(pos);hi=min(lo+1,len(vals)-1);return vals[lo]+(vals[hi]-vals[lo])*(pos-lo)
  values={'mean':statistics.mean(vals),'p10':percentile(.1),'p90':percentile(.9),'min':vals[0],'max':vals[-1]}
  values.update({k:convert(a[i],'°C',prefs)[0] for k,a in members if i<len(a) and a[i] is not None})
  result.append({'epoch':epoch,'label':stamp(epoch,loc['zone'],prefs['hour24']),'date':dt.datetime.fromtimestamp(epoch,ZoneInfo(loc['zone'])).strftime('%a %d %b'),'night':False,'values':values,'formatted':{},'spread':values['p90']-values['p10']})
 unit='°F' if prefs['temperature']=='F' else '°C'
 return {'rows':result,'series':[{'key':k,'label':n,'unit':unit} for k,n in [('mean','Mean'),('p10','10th percentile'),('p90','90th percentile')]],'memberSeries':[{'key':k,'label':k,'unit':unit} for k,_ in members],'members':len(members),'source':'NOAA GFS ensemble via Open-Meteo','heuristic':'10–90% member percentile range, calculated by linear rank interpolation. Spread is not a guaranteed probability or accuracy score.'}
def history_view(data,loc,prefs):
 daily=rows(data,'daily',loc,prefs);hourly=rows(data,'hourly',loc,prefs);months=defaultdict(list)
 for row in daily:months[dt.datetime.fromtimestamp(row['epoch'],ZoneInfo(loc['zone'])).strftime('%Y-%m')].append(row)
 monthly=[]
 for month,items in sorted(months.items()):
  temps=[r['values']['temperature_2m_mean'] for r in items if 'temperature_2m_mean' in r['values']];rain=[r['values']['precipitation_sum'] for r in items if 'precipitation_sum' in r['values']]
  monthly.append({'month':month,'mean':round(statistics.mean(temps),2) if temps else None,'rain':round(sum(rain),2),'days':len(items)})
 vals=[r['values']['temperature_2m_mean'] for r in daily if 'temperature_2m_mean' in r['values']]
 stats={'days':len(daily),'mean':round(statistics.mean(vals),2) if vals else None,'min':min(vals) if vals else None,'max':max(vals) if vals else None,'rain':round(sum(r['values'].get('precipitation_sum',0) for r in daily),2)}
 years=defaultdict(list)
 for item in monthly:years[item['month'][5:]].append(item)
 pairs=[]
 for month,items in sorted(years.items()):
  if len(items)<2:continue
  a,b=items[-2:];pairs.append({'month':month,'first':a['month'],'second':b['month'],'firstMean':a['mean'],'secondMean':b['mean'],'temperatureDelta':round(b['mean']-a['mean'],2) if a['mean'] is not None and b['mean'] is not None else None,'rainDelta':round(b['rain']-a['rain'],2),'dayCounts':[a['days'],b['days']]})
 sorted_vals=sorted(vals)
 def quantile(q):
  if not sorted_vals:return None
  pos=(len(sorted_vals)-1)*q;lo=int(pos);hi=min(lo+1,len(sorted_vals)-1);return round(sorted_vals[lo]+(sorted_vals[hi]-sorted_vals[lo])*(pos-lo),2)
 return {'daily':daily,'rows':hourly,'monthly':monthly,'yearComparison':pairs,'percentiles':{'p10':quantile(.1),'p50':quantile(.5),'p90':quantile(.9)},'stats':stats,'source':'ERA5 reanalysis · ~0.25° (~25 km) · Open-Meteo','limitation':'Period statistics are reanalysis-derived, not official station records. No baseline anomaly is implied.'}
