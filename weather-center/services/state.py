"""Weather-owned versioned state, validation and one coalescing atomic writer."""
import copy,json,logging,math,os,threading,time,hashlib
from pathlib import Path
from zoneinfo import ZoneInfo

DEFAULT_PREFS={'temperature':'C','wind':'km/h','pressure':'hPa','precipitation':'mm','visibility':'km','hour24':True,'density':'comfortable','reduceMotion':False,'highContrast':False,'palette':'colorblind','advanced':False,'forecastDays':16,'horizon':48,'model':'best_match','aqi':'us_aqi','offline':False,'distance':'metric','dateFormat':'ddd dd MMM','autoRefresh':True,'refreshMinutes':15,'cacheMB':96,'lineWidth':2,'notableTemperature':5,'precipThreshold':50,'mapGrid':True,'mapDay':True,'mapLabels':True,'mapPins':True,'mapHome':True,'defaultZoom':1,'defaultLayer':'radar','radarSmooth':True,'radarSnow':False,'rememberMap':True,'mapOpacity':.7,'radarSpeed':1500}
DEFAULT_CARDS=['relative_humidity_2m','dew_point_2m','wind_speed_10m','wind_gusts_10m','pressure_msl','visibility','cloud_cover','precipitation','precipitation_probability','uv_index','us_aqi','pm2_5']
def location(data,temporary=False):
 lat=float(data.get('lat',data.get('latitude')));lon=float(data.get('lon',data.get('longitude')))
 if not math.isfinite(lat) or not math.isfinite(lon) or not -90<=lat<=90:raise ValueError('Invalid coordinates')
 lon=(lon+180)%360-180;zone=data.get('zone',data.get('timezone'))
 if not zone or zone=='auto':
  import tzfpy
  zone=tzfpy.get_tz(lon,lat) or 'UTC'
 ZoneInfo(zone)
 country=data.get('country','');region=data.get('region',data.get('admin1',''))
 identity=data.get('id') or hashlib.sha256(f'{lat:.5f},{lon:.5f}'.encode()).hexdigest()[:16]
 return {'id':str(identity),'name':str(data.get('name') or f'{lat:.3f}°, {lon:.3f}°'),'region':str(region),'country':str(country),'countryCode':data.get('countryCode',data.get('country_code','')),'lat':lat,'lon':lon,'zone':zone,'elevation':data.get('elevation'),'providerId':data.get('providerId',data.get('geonames_id')),'favorite':bool(data.get('favorite',False)),'temporary':temporary}
def discover_yasb(root):
 """Read the actual widget's explicit saved record; never modify YASB data."""
 import yaml
 try:config=yaml.safe_load((Path(os.environ.get('YASB_CONFIG_HOME',str(root.parent)))/'config.yaml').read_text('utf-8'))
 except (OSError,ValueError):return None
 name=next((n for n,w in config['widgets'].items() if w['type']=='yasb.open_meteo.OpenMeteoWidget'),None)
 if not name:return None
 path=Path(os.environ['LOCALAPPDATA'])/'YASB/weather.json'
 try:
  data=json.loads(path.read_text('utf-8'));record=data.get(name)
  return location(record) if record and record.get('latitude') is not None else None
 except (OSError,ValueError,TypeError,KeyError):return None
def default_state(home=None):
 return {'schema':1,'homeId':home['id'] if home else '', 'selected':home or {},'locations':[home] if home else [],'recent':[],'prefs':copy.deepcopy(DEFAULT_PREFS),'dashboard':{'cards':list(DEFAULT_CARDS),'hidden':[],'expanded':[],'primary':'temperature_2m','miniLayer':'radar'},'map':{'zoom':1.,'x':0.,'y':0.,'layer':'radar'},'chart':{'series':['temperature_2m','apparent_temperature','precipitation'],'preset':'Standard'},'layout':{'mapSplit':.72,'locationSplit':.62},'page':0}
class AtomicWriter:
 def __init__(self):
  self.pending={};self.condition=threading.Condition();self.closing=False
  self.thread=threading.Thread(target=self.run,name='weather-storage',daemon=True);self.thread.start()
 def submit(self,path,data,immutable=False):
  # Provider/cache payloads are immutable after acquisition. User state still
  # takes a snapshot, so later edits cannot leak into an in-flight atomic write.
  snapshot=data if immutable else copy.deepcopy(data)
  with self.condition:self.pending[Path(path)]=snapshot;self.condition.notify()
 def run(self):
  while True:
   with self.condition:
    while not self.pending and not self.closing:self.condition.wait()
    if not self.pending:return
    path=next(iter(self.pending));data=self.pending.pop(path)
   try:
    path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix(path.suffix+'.tmp')
    if isinstance(data,bytes):
     with temp.open('wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
    else:
     with temp.open('w',encoding='utf-8') as f:json.dump(data,f,ensure_ascii=False,indent=2,allow_nan=False);f.flush();os.fsync(f.fileno())
    os.replace(temp,path)
   except Exception:logging.exception('Atomic write failed; previous file retained')
 def close(self):
  with self.condition:self.closing=True;self.condition.notify()
  self.thread.join(timeout=10)
class StateStore:
 def __init__(self,root,writer,data_root=None):
  self.root=Path(root);self.path=Path(data_root or root)/'data/state.json';self.writer=writer;self.warning=''
  home=discover_yasb(self.root);self.state=default_state(home)
  if self.path.exists():
   try:
    raw=json.loads(self.path.read_text('utf-8'))
    if not isinstance(raw,dict) or raw.get('schema',1)>1:raise ValueError('Unsupported state schema')
    self.state.update(raw)
    for key in ('prefs','dashboard','map','chart','layout'):self.state[key]={**default_state(home)[key],**raw.get(key,{})}
    self.state['locations']=[location(x) for x in raw.get('locations',[])]
    self.state['recent']=[location(x,True) for x in raw.get('recent',[])][:20]
    self.state['selected']=location(raw['selected'],raw['selected'].get('temporary',False)) if raw.get('selected') else (home or {})
    self.state['page']=max(0,min(14,int(self.state['page'])))
    m=self.state['map'];m['zoom']=max(1,min(128,float(m['zoom'])));m['x']=(float(m['x'])+.5)%1-.5;m['y']=max(-.5,min(.5,float(m['y'])))
    if not all(math.isfinite(m[k]) for k in ('zoom','x','y')):raise ValueError('Invalid map state')
    from services.settings import validate
    for key in DEFAULT_PREFS:
     try:self.state['prefs'][key]=validate(key,self.state['prefs'][key])
     except (ValueError,TypeError):self.state['prefs'][key]=copy.deepcopy(DEFAULT_PREFS[key]);self.warning='Invalid Weather preference recovered; remaining saved data retained'
    self.state['schema']=1
    if not self.state['prefs']['rememberMap']:self.state['map'].update({'zoom':self.state['prefs'].get('defaultZoom',1),'x':0.,'y':0.,'layer':self.state['prefs'].get('defaultLayer','radar')})
   except (OSError,ValueError,TypeError,KeyError) as exc:
    # Keep one exact original recovery file; never silently overwrite it.
    recovery=self.path.with_name('state.corrupt.json')
    if not recovery.exists():recovery.write_bytes(self.path.read_bytes())
    self.state=default_state(home);self.warning='Weather state recovered; original retained as state.corrupt.json'
    logging.warning('State recovery: %s',exc)
 def save(self):self.writer.submit(self.path,self.state)
 def find(self,identity):return next((x for x in self.state['locations'] if x['id']==identity),None)
