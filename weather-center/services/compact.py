"""Derived compact-bar projection. The selected location in StateStore owns identity."""
import copy,datetime as dt,time
from zoneinfo import ZoneInfo

def project(state,bundle,generation):
 loc=copy.deepcopy(state.get('selected') or {})
 data=copy.deepcopy(bundle.get('data') or {})
 zone=ZoneInfo(loc.get('zone','UTC'))
 def date(value,daily=False):
  if not isinstance(value,(int,float)):return value
  return dt.datetime.fromtimestamp(value,zone).strftime('%Y-%m-%d' if daily else '%Y-%m-%dT%H:%M')
 # Preserve the stock upward card's contract; source data remains SI/UTC.
 for section in ('current','hourly','daily'):
  block=data.get(section,{})
  for key in ('time','sunrise','sunset'):
   if key in block:
    block[key]=[date(x,section=='daily' and key=='time') for x in block[key]] if isinstance(block[key],list) else date(block[key])
  for key in list(block):
   if key.startswith('wind_speed') or key.startswith('wind_gust'):
    value=block[key]
    block[key]=[None if x is None else x*3.6 for x in value] if isinstance(value,list) else (None if value is None else value*3.6)
  units=data.get(section+'_units',{})
  for key in units:
   if key.startswith(('wind_speed','wind_gust')):units[key]='km/h'
   elif key in ('time','sunrise','sunset'):units[key]='iso8601'
  # Keep only the most recent current day's onward forecast in the compact card.
  if section in ('daily','hourly') and block.get('time'):
   today=dt.datetime.now(zone).strftime('%Y-%m-%d')
   indices=[i for i,t in enumerate(block['time']) if t[:10]>=today]
   limit=7 if section=='daily' else 7*24
   indices=indices[:limit]
   for key,value in list(block.items()):
    if isinstance(value,list):block[key]=[value[i] for i in indices if i<len(value)]
 return {'schema':1,'generation':generation,'location':loc,'prefs':{'temperature':state['prefs']['temperature']},
         'data':data,'saved':bundle.get('saved',0),'stale':bool(bundle.get('stale',True)),
         'error':str(bundle.get('error',''))[:300],'offline':bool(state['prefs'].get('offline')),'published':time.time()}

def publish(bridge):
 bridge.writer.submit(bridge.root/'data/compact.json',project(bridge.state,bridge._forecast,bridge.generation),immutable=True)
