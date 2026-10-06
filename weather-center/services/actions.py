"""Validated user actions; no live shell/state mutation outside Weather Center."""
import copy,datetime as dt,json,re
from zoneinfo import ZoneInfo
from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication,QDesktopServices
from services.state import location,discover_yasb,DEFAULT_CARDS
from services.settings import validate
from services.presentation import forecast_presentation,LABELS
from services.layers import LAYERS
from services.datasets import PRESENTATION_PREFS
class Actions:
 def searchLocations(self,query):
  query=query.strip();self._search_gen+=1;gen=self._search_gen;self.http.cancel('search')
  local=[dict(x,kind='location') for x in self.state['locations']+self.state['recent'] if query.casefold() in (' '.join([x['name'],x['region'],x['country']])).casefold()]
  commands=[('Overview',0),('Hourly / metrics',1),('Daily',2),('Radar / wind map',3),('Precipitation / storms',4),('Wind / pressure',5),('Air / PM2.5',6),('Sun / sky',7),('Marine',8),('History / climate',9),('Models / confidence',10),('Locations / set home',11),('Official alerts',12),('Weather Lab',13),('Settings / Celsius / units',14)]
  actions=[{'kind':'page','name':n,'page':p,'region':'Page / action'} for n,p in commands if query.casefold() in n.casefold()]
  for key,title in LABELS.items():
   if query and query.casefold() in (key+' '+title).casefold():actions.append({'kind':'metric','name':title,'key':key,'region':'Add to hourly chart'})
  for v,n in [('C','Celsius'),('F','Fahrenheit')]:
   if query and query.casefold() in n.casefold():actions.append({'kind':'unit','name':n,'value':v,'region':'Temperature setting'})
  for l in LAYERS:
   if query and query.casefold() in (l['id']+' '+l['name']).casefold():actions.append({'kind':'layer','name':l['name'],'value':l['id'],'region':'Map layer · '+('available' if l['available'] else 'unsupported')})
  for key,label in [('refresh','Refresh weather'),('home','Set Home to selected location'),('save','Save selected location'),('rawCopy','Copy raw provider JSON')]:
   if query and query.casefold() in label.casefold():actions.append({'kind':'action','name':label,'value':key,'region':'Action'})
  from services.settings import LABELS as settingsLabels
  for key,label in settingsLabels.items():
   if query and query.casefold() in label.casefold():actions.append({'kind':'page','name':label,'page':14,'region':'Setting'})
  coords=re.fullmatch(r'\s*([-+]?\d+(?:\.\d+)?)\s*[, ]\s*([-+]?\d+(?:\.\d+)?)\s*',query)
  if coords:
   try:local.insert(0,dict(location({'lat':float(coords[1]),'lon':float(coords[2])},True),kind='location'))
   except ValueError:pass
  self._results=(actions+local)[:50];self.searchChanged.emit()
  if len(query)<2 or coords:return
  def done(found,reply):
   if gen!=self._search_gen:return
   seen={x.get('id') for x in local};self._results=(actions+local+[dict(x,kind='location') for x in found if x['id'] not in seen])[:50];self.searchChanged.emit()
   if reply.get('error'):self.status_text('Search offline · saved/recent locations remain available')
  self.providers.geocode(query,done)
 def select(self,data):
  if not data:raise ValueError('Location unavailable')
  loc=location(data,data.get('temporary',True));self.state['selected']=loc;self.state['recent']=[loc]+[x for x in self.state['recent'] if x['id']!=loc['id']][:19]
  self.generation+=1;self.http.cancel('selected');self.store.save()
  self.clearDatasets();self._advanced={};self._forecast={};self._air={};self.advancedChanged.emit();self.http.cancel('advanced');self.http.cancel('history');self.http.cancel('alerts');self.persist();self.publish();self.loadSelected();self.ensurePage()
 def action(self,action,data):
  if action=='hide':self.hideRequested.emit();return
  if action=='page':
   self.state['page']=max(0,min(14,int(data['value'])));self.persist();self.ensurePage()
   if self.state['page']==11:self.searchLocations('')
   return
  if action=='refresh':
   self.loadSelected(True)
   if self.state['page']==8:self.fetchAdvanced('marine',True)
   elif self.state['page']==10:
    for kind in ('models','ensemble')+(('runs',) if 'runs' in self._datasets else ()):self.fetchAdvanced(kind,True)
   elif self.state['page']==12:self.fetchAlerts(True)
   elif self.state['page']==9 and self._datasets.get('history',{}).get('period'):self.fetchAdvanced('history',True,self._datasets['history']['period'])
   else:self.ensurePage()
   return
  if action=='searchSelect':
   if data['kind']=='page':self.action('page',{'value':data['page']})
   elif data['kind']=='metric':self.action('chart',{'key':data['key']});self.action('page',{'value':1})
   elif data['kind']=='unit':self.action('pref',{'key':'temperature','value':data['value']})
   elif data['kind']=='layer':self.action('page',{'value':3});self.action('mapAction',{'op':'layer','value':data['value']})
   elif data['kind']=='action':self.action(data['value'],{})
   else:self.select(data)
   return
  if action=='select':self.select(data if 'lat' in data else self.store.find(data['id']));return
  if action in ('save','home','favorite','remove','rename','reorder'):
   loc=location(data.get('location') or self.state['selected']);saved=self.store.find(data.get('id',loc['id']))
   if action in ('save','home','favorite') and not saved:loc['temporary']=False;self.state['locations'].append(loc);saved=loc
   if action=='home':self.state['homeId']=saved['id'];self.status_text('Home saved · selected location is shared with the taskbar')
   elif action=='favorite':saved['favorite']=not saved['favorite']
   elif action=='rename':
    if not saved:raise ValueError('Save this location before renaming')
   saved['name']=str(data['name']).strip()[:100] or saved['name']
   if saved and saved['id']==self.state['selected'].get('id') and action=='rename':
    self.state['selected']['name']=saved['name'];self.store.save();self.publish()
   elif action=='remove':
    if data['id']==self.state['homeId']:raise ValueError('Set another Home before removing this location')
    self.state['locations']=[x for x in self.state['locations'] if x['id']!=data['id']]
   elif action=='reorder':
    items=self.state['locations'];i=next(i for i,x in enumerate(items) if x['id']==data['id']);j=max(0,min(len(items)-1,i+int(data['delta'])));items.insert(j,items.pop(i))
  elif action=='pref':
   key=data['key'];self.state['prefs'][key]=validate(key,data['value']);self.http.setOffline(self.state['prefs'].get('offline',False))
   if key=='refreshMinutes':self.compactTimer.setInterval(max(1,int(self.state['prefs'][key]))*60000)
   if key in ('offline','temperature'):
    from services.compact import publish
    publish(self)
   if key in PRESENTATION_PREFS|{'model','aqi','notableTemperature','precipThreshold'}:self.schedulePublish()
   if key in ('model','forecastDays'):self.loadSelected(True)
   elif key in PRESENTATION_PREFS:self.reformatDatasets()
   self.ensurePage()
   if self._map:self._map.preferencesChanged(key)
  elif action=='chart':
   keys=self.state['chart']['series'];key=data['key']
   if data.get('remove'):
    if key in keys:keys.remove(key)
   elif key not in keys:keys.append(key)
  elif action=='chartPreset':self.state['chart']={'preset':data['value'],'series':{'Simple':['temperature_2m','precipitation'],'Standard':['temperature_2m','apparent_temperature','precipitation','wind_speed_10m'],'Meteorology':['temperature_2m','dew_point_2m','precipitation','wind_gusts_10m','pressure_msl','cloud_cover']}[data['value']]}
  elif action=='dashboard':
   d=self.state['dashboard'];key=data.get('key');op=data['op']
   if op=='restore':d.update({'cards':list(DEFAULT_CARDS),'hidden':[],'expanded':[]})
   elif op in ('hidden','expanded'):
    if key in d[op]:d[op].remove(key)
    else:d[op].append(key)
   elif op=='move':i=d['cards'].index(key);j=max(0,min(len(d['cards'])-1,i+int(data['delta'])));d['cards'].insert(j,d['cards'].pop(i))
   elif op=='pin':
    if key not in d['cards']:d['cards'].append(key)
    if key in d['hidden']:d['hidden'].remove(key)
   elif op in ('primary','miniLayer'):
    d[op]=data['value']
    if op=='miniLayer' and self._map:self._map.loadPreview()
   self.dataChanged.emit()
  elif action=='layout':self.state['layout'][data['key']]=max(.2,min(.85,float(data['value'])))
  elif action=='map':
   if 'zoom' in data:data['zoom']=max(1,min(128,float(data['zoom'])))
   if 'x' in data:data['x']=(float(data['x'])+.5)%1-.5
   if 'y' in data:data['y']=max(-.5,min(.5,float(data['y'])))
   self.state['map'].update(data)
  elif action=='mapAction':
   if self._map:self._map.action(data)
  elif action=='metricMap':
   field=self.metricLayer(data['key'])
   if not field:raise ValueError('No supported sampled map layer for this metric')
   self.state['page']=3;self.state['map']['layer']=field;self.ensurePage()
   if self._map:self._map.action({'op':'layer','value':field})
  elif action=='inspect':self.select({'lat':data['lat'],'lon':data['lon'],'temporary':True})
  elif action=='history':
   start=dt.date.fromisoformat(data['start']);end=dt.date.fromisoformat(data['end'])
   if end<start or (end-start).days>730:raise ValueError('Choose an ordered range of at most two years')
   if end>dt.date.today()-dt.timedelta(days=5):raise ValueError('ERA5 can lag; end date must be at least 5 days ago')
   self.fetchAdvanced('history',bool(data.get('force',False)),{'start':start.isoformat(),'end':end.isoformat()});return
  elif action=='solarDate':self.calculateSolar(data['value']);return
  elif action=='advancedRefresh':self.fetchAlerts(True) if data['kind']=='alerts' else self.fetchAdvanced(data['kind'],bool(data.get('force',True)));return
  elif action=='compare':self.compare(data['ids']);return
  elif action=='copy':QGuiApplication.clipboard().setText(str(data['text']));self.status_text('Copied');return
  elif action=='rawCopy':QGuiApplication.clipboard().setText(json.dumps({'metadata':self.metadata,'forecast':self._forecast.get('data'),'air':self._air.get('data')},indent=2));self.status_text('Copied raw provider data');return
  elif action=='export':
   folder=getattr(self,'data_root',self.root)/'exports';folder.mkdir(exist_ok=True);name=re.sub(r'[^a-zA-Z0-9_-]','_',data.get('name','weather'));path=folder/(name+'.csv');path.write_text(str(data['text']),'utf-8-sig');self.status_text('Exported '+str(path));return
  elif action=='open':
   target=data['url']
   if target.startswith('https://'):QDesktopServices.openUrl(QUrl(target))
   elif target=='logs':QDesktopServices.openUrl(QUrl.fromLocalFile(str(getattr(self,'data_root',self.root)/'logs')))
   return
  elif action=='clearCache':self.http.clear();self.status_text('Weather cache cleared · saved settings retained');return
  elif action=='calculate':
   from services.lab import calculate
   try:self._advanced['lab']=calculate(data,self.state['selected'].get('zone','UTC'))
   except (ValueError,KeyError,OverflowError) as exc:self._advanced['lab']={'result':'Invalid input · '+str(exc),'formula':'No value calculated','source':''}
   self.advancedChanged.emit();return
  elif action=='resetWeather':
   if data.get('confirmed') is not True:raise ValueError('Confirm Weather Center reset in Settings')
   from services.state import default_state
   self.writer.submit(getattr(self,'data_root',self.root)/'data/state.before-reset.json',self.state);self.clearDatasets();self.store.state=default_state(discover_yasb(self.root));self._advanced={};self._forecast={};self._air={};self.persist();self.publish();self.loadSelected();return
  elif action=='syncHome':
   home=discover_yasb(self.root)
   if not home:raise ValueError('YASB has no explicit saved weather location')
   self.select(home);self.action('home',{});return
  else:raise ValueError('Unknown action '+action)
  self.persist();self.advancedChanged.emit()
 def compare(self,ids):
  self._compare=[];self.http.cancel('compare')
  for identity in list(dict.fromkeys(ids))[:6]:
   loc=self.store.find(identity)
   if not loc:continue
   item={'id':identity,'location':loc,'summary':{'temperature':'Loading'},'rows':[]};self._compare.append(item);bundles={}
   def update(item=item,loc=loc,bundles=bundles):
    view=forecast_presentation(bundles.get('forecast',{}),bundles.get('air',{}),loc,self.state['prefs']);air_by_epoch={r['epoch']:r for r in view['airRows']}
    for r in view['hourly']:
     a=air_by_epoch.get(r['epoch'],{});r['values'].update(a.get('values',{}));r['formatted'].update(a.get('formatted',{}))
    item.update({'summary':view['summary'],'rows':view['hourly']});self.advancedChanged.emit()
   def done(reply,bundles=bundles,update=update):bundles['forecast']=reply;update()
   def air_done(reply,bundles=bundles,update=update):bundles['air']=reply;update()
   self.providers.forecast(loc,self.state['prefs'],done,False,'compare')
   self.providers.air(loc,air_done,False,'compare')
  self.advancedChanged.emit()
