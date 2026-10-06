"""Qt observable models and asynchronous orchestration; no QML networking."""
import copy,datetime as dt,json,logging,sys,time
from pathlib import Path
from zoneinfo import ZoneInfo
from PySide6.QtCore import QObject,Signal,Slot,Property,QTimer,qVersion
from services.state import StateStore,AtomicWriter
from services.http import HttpClient
from services.providers import Providers,MODELS
from services.presentation import forecast_presentation
from services.analysis import solar
from services.settings import setting_rows,SOURCES
from services.map import MapImages
from services.datasets import TTL,retain,present,freshness
from services.actions import Actions
from app.view_state import ViewState
from app.rows_model import RowsModel
from services.work import WorkQueue
from services.units import date_label,stamp
class Bridge(QObject,Actions):
 changed=Signal();dataChanged=Signal();summaryChanged=Signal();healthChanged=Signal();searchChanged=Signal();statusChanged=Signal();modalChanged=Signal();hideRequested=Signal();navigate=Signal(int);mapChanged=Signal();advancedChanged=Signal()
 @property
 def window(self):return getattr(self,'_window',None)
 @window.setter
 def window(self,value):
  self._window=value
  from app.charts import WeatherChart
  WeatherChart.attachHost(value)
 def __init__(self,root):
  super().__init__();self.root=Path(root);self.writer=AtomicWriter();self.store=StateStore(self.root,self.writer);self.images=MapImages();self._status=self.store.warning or 'Ready';self.visible=False;self._modal=0;self.window=None;self._results=[];self.generation=0;self._forecast={};self._air={};self._advanced={};self._compare=[];self._search_gen=0;self._map=None
  self.http=HttpClient(self.root/'data/weather-cache',self.writer);self.providers=Providers(self.http);self.http.healthChanged.connect(self.healthChanged)
  self._datasets={};self._datasetVersions={};self._datasetAttempts={};self._solarDate=None
  self._uiState=ViewState(self.state,self)
  self._advancedUi=ViewState({},self);self._advancedSeen={};self._advancedMetadata={};self._emptyAdvanced={};self._advancedModels={kind:RowsModel(self) for kind in TTL};self.advancedChanged.connect(self.syncAdvanced)
  self._rowModels={key:RowsModel(self) for key in ('hourly','allHourly','airRows')};self._dayModels={}
  self.work=WorkQueue(self);self._viewVersion=0;self._presentationVersion=0
  self.chartWork=WorkQueue(self,workers=1,limit=64,name='weather-charts')
  from app.charts import WeatherChart
  WeatherChart.imageStore=self.images;WeatherChart.renderWork=self.chartWork
  self._view=forecast_presentation({}, {},self.state['selected'] or {'zone':'UTC'},self.state['prefs'])
  self.saveTimer=QTimer(self);self.saveTimer.setSingleShot(True);self.saveTimer.setInterval(600);self.saveTimer.timeout.connect(self.store.save)
  self.tickTimer=QTimer(self);self.tickTimer.setInterval(60000);self.tickTimer.timeout.connect(self.tick)
  from services.compact import publish
  self.store.save()
  publish(self)
  self.compactTimer=QTimer(self);self.compactTimer.setInterval(max(1,int(self.state['prefs']['refreshMinutes']))*60000)
  self.compactTimer.timeout.connect(lambda:self.loadSelected() if self.state['prefs']['autoRefresh'] and not self.visible else None)
  self.compactTimer.start()
  QTimer.singleShot(800,self.loadSelected)
 @Property('QVariantMap',notify=changed)
 def state(self):return self.store.state
 @Property(QObject,constant=True)
 def uiState(self):return self._uiState
 @Property(QObject,constant=True)
 def advancedUi(self):return self._advancedUi
 @Slot(str,result=QObject)
 def advancedModel(self,kind):return self._advancedModels.get(kind)
 def syncAdvanced(self):
  changed=False
  for kind,model in self._advancedModels.items():
   value=self._advanced.get(kind,self._emptyAdvanced)
   if self._advancedSeen.get(kind) is not value:
    model.setRows(value.get('rows',[]));self._advancedSeen[kind]=value;self._advancedMetadata[kind]={k:v for k,v in value.items() if k!='rows'};changed=True
  if changed:self._advancedUi.sync(self._advancedMetadata)
 @Property(QObject,constant=True)
 def hourlyModel(self):return self._rowModels['hourly']
 @Property(QObject,constant=True)
 def allHourlyModel(self):return self._rowModels['allHourly']
 @Property(QObject,constant=True)
 def airRowsModel(self):return self._rowModels['airRows']
 @Property('QVariantList',notify=dataChanged)
 def hourlyPreview(self):return self._view['hourly'][:8]
 @Slot(int,result=QObject)
 def dayChartModel(self,index):
  index=max(0,min(15,index))
  if index not in self._dayModels:self._dayModels[index]=RowsModel(self)
  day=self._view['daily'][index]['date'] if 0<=index<len(self._view['daily']) else None
  self._dayModels[index].setRows([r for r in self._view['allHourly'] if r['date']==day] if day else [])
  return self._dayModels[index]
 @Property('QVariantMap',notify=summaryChanged)
 def summary(self):return self._view['summary']
 @Property('QVariantList',notify=dataChanged)
 def hourly(self):return self._view['hourly']
 @Property('QVariantList',notify=dataChanged)
 def allHourly(self):return self._view['allHourly']
 @Property('QVariantList',notify=dataChanged)
 def daily(self):return self._view['daily']
 @Property('QVariantList',notify=dataChanged)
 def minute(self):return self._view['minute']
 @Property('QVariantList',notify=dataChanged)
 def airRows(self):return self._view['airRows']
 @Property('QVariantList',notify=dataChanged)
 def metrics(self):return self._view['metrics']
 @Property('QVariantList',notify=dataChanged)
 def dashboardCards(self):
  lookup={m['key']:m for m in self.metrics};d=self.state['dashboard'];return [dict(lookup[k],expanded=k in d['expanded']) for k in d['cards'] if k in lookup and k not in d['hidden']]
 @Property('QVariantList',notify=dataChanged)
 def series(self):return self._view['series']
 @Property('QStringList',notify=dataChanged)
 def notable(self):return self._view['notable']
 @Property('QVariantMap',notify=dataChanged)
 def metadata(self):return self._view['metadata']
 @Property('QVariantMap',notify=advancedChanged)
 def advanced(self):return self._advanced
 @Property('QVariantMap',notify=advancedChanged)
 def marine(self):return self._advanced.get('marine',{})
 @Property('QVariantMap',notify=advancedChanged)
 def models(self):return self._advanced.get('models',{})
 @Property('QVariantMap',notify=advancedChanged)
 def ensemble(self):return self._advanced.get('ensemble',{})
 @Property('QVariantMap',notify=advancedChanged)
 def history(self):return self._advanced.get('history',{})
 @Property('QVariantMap',notify=advancedChanged)
 def runs(self):return self._advanced.get('runs',{})
 @Property('QVariantMap',notify=summaryChanged)
 def datasetAges(self):return {kind:{**freshness(kind,bundle),'location':self.summary['location']} for kind,bundle in self._datasets.items()}
 @Slot(str,result=str)
 def metricLayer(self,key):
  from services.layers import LAYERS
  return next((item['id'] for item in LAYERS if item['available'] and (item['id']==key or item['variable']==key)),'')
 @Property('QVariantMap',notify=advancedChanged)
 def alerts(self):return self._advanced.get('alerts',{})
 @Property('QVariantMap',notify=advancedChanged)
 def lab(self):return self._advanced.get('lab',{})
 @Property('QVariantList',notify=advancedChanged)
 def solar(self):return self._advanced.get('solar',[])
 @Property(str,notify=advancedChanged)
 def solarDate(self):return self._solarDate or dt.datetime.now(ZoneInfo(self.state['selected'].get('zone','UTC'))).date().isoformat()
 @Property('QVariantList',notify=advancedChanged)
 def comparisons(self):return self._compare
 @Property('QVariantList',notify=searchChanged)
 def results(self):return self._results
 @Property('QVariantList',notify=healthChanged)
 def providerStatus(self):return list(self.http.health.values())
 @Property('QVariantMap',notify=dataChanged)
 def airSummary(self):
  saved=self._air.get('saved',0);return {'location':self.summary['location'],'age':f'{int(max(0,time.time()-saved)//60)} min old' if saved else 'Not loaded','stale':self._air.get('stale',True) or time.time()-saved>1800,'error':self._air.get('error','')}
 @Property('QVariantList',constant=True)
 def settingsRows(self):return setting_rows()
 @Property('QVariantList',constant=True)
 def sources(self):return SOURCES
 @Property('QVariantList',constant=True)
 def modelChoices(self):return MODELS
 @Property(str,notify=statusChanged)
 def status(self):return self._status
 @Property(int,notify=modalChanged)
 def modalCount(self):return self._modal
 @Property('QVariantMap',notify=mapChanged)
 def mapData(self):return self._map.snapshot() if self._map else {'ready':False,'land':'','solar':'','alerts':'','tiles':[],'samples':[],'frames':[],'frame':0,'layers':[],'legend':'Map loads after the shell','coverage':'Radar coverage is not worldwide','status':'Loading offline map','playing':False,'frameLabel':'','sampleLegend':[]}
 @Property('QVariantMap',notify=mapChanged)
 def previewData(self):return getattr(self._map,'preview',{}) if self._map else {}
 @Slot(int)
 def modal(self,delta):self._modal=max(0,self._modal+delta);self.modalChanged.emit()
 def status_text(self,text):self._status=str(text);self.statusChanged.emit()
 def persist(self):self._uiState.sync(self.state);self.changed.emit();self.saveTimer.start()
 def publish(self):
  # Synchronous only for empty location boundaries and explicit fixture setup.
  self._viewVersion+=1
  self.adoptView(forecast_presentation(self._forecast,self._air,self.state['selected'] or {'zone':'UTC'},self.state['prefs']))
 def schedulePublish(self):
  self._viewVersion+=1;version=self._viewVersion;forecast=self._forecast;air=self._air;loc=copy.deepcopy(self.state['selected'] or {'zone':'UTC'});prefs=dict(self.state['prefs'])
  def adopt(value,error):
   if version!=self._viewVersion:return
   if error:self.status_text('Forecast display unavailable; previous data retained');return
   self.adoptView(value)
  self.work.submit('forecast',lambda:forecast_presentation(forecast,air,loc,prefs),adopt)
 def adoptView(self,view):
  self._view=view
  for key,model in self._rowModels.items():model.setRows(self._view[key])
  for index in self._dayModels:self.dayChartModel(index)
  self.dataChanged.emit();self.summaryChanged.emit()
  from services.compact import publish
  publish(self)
 def updateSummary(self):
  now=time.time();saved=self._forecast.get('saved',0);zone=self.state['selected'].get('zone','UTC');prefs=self.state['prefs'];s=self._view['summary']
  s.update({'age':f'{int(max(0,now-saved)//60)} min old' if saved else 'Not loaded','stale':self._forecast.get('stale',True) or now-saved>900,'localTime':date_label(now,zone,prefs)+' · '+stamp(now,zone,prefs['hour24'])});self.summaryChanged.emit()
 def setVisible(self,value):
  if self.visible==value:return
  self.visible=value
  if value:self.tickTimer.start();self.updateSummary();QTimer.singleShot(120,self.openWork)
  else:
   self.tickTimer.stop()
   if self._map:self._map.setVisible(False);self._map.setPreviewActive(False)
 def tick(self):
  if not self.visible:return
  self.updateSummary();p=self.state['prefs']
  if p['autoRefresh'] and time.time()-self._forecast.get('saved',0)>p['refreshMinutes']*60:self.loadSelected()
  if self._map:self._map.tick()
  self.ensurePage()
  if self.state['page'] in (0,12) and time.time()-self._advanced.get('alerts',{}).get('saved',time.time())>300:self.fetchAlerts()
  self.http.limitMB=p['cacheMB'];self.http.prune()
 def openWork(self):
  if self.visible:self.tick();self.ensurePage()
 def loadSelected(self,force=False):
  self.http.setOffline(self.state['prefs'].get('offline',False))
  loc=self.state['selected']
  if not loc:self.status_text('Choose a location · Ctrl+K');return
  self.generation+=1;generation=self.generation;self.http.cancel('selected');self.status_text('Refreshing '+loc['name']+' · cache remains usable');requestedModel=self.state['prefs']['model']
  def done(kind,value):
   if generation!=self.generation:return
   previous=self._forecast if kind=='forecast' else self._air
   if not value.get('data') and previous.get('data'):value={**previous,'stale':True,'error':value.get('error') or 'Provider unavailable; last successful data retained'}
   elif kind=='forecast':value={**value,'model':requestedModel}
   if kind=='forecast':self._forecast=value
   else:self._air=value
   self.schedulePublish();self.status_text(value.get('error') or ('Cached ' if value['cache'] else 'Updated ')+kind+' · '+loc['name'])
  self.providers.forecast(loc,self.state['prefs'],lambda v:done('forecast',v),force);self.providers.air(loc,lambda v:done('air',v),force)
 def ensurePage(self):
  page=self.state['page'];loc=self.state['selected']
  if self._map:self._map.setVisible(self.visible and page==3)
  if self._map:self._map.setPreviewActive(self.visible and page==0)
  if page==0 and self.visible and self._map is None:QTimer.singleShot(120,self.startPreview)
  if page==3 and self.visible:
   if self._map is None:
    from services.map import MapController
    self._map=MapController(self);self._map.start()
   self._map.setVisible(True)
  if not loc:return
  if page==7 and 'solar' not in self._advanced:self.calculateSolar(self._solarDate or dt.datetime.now(ZoneInfo(loc['zone'])).date().isoformat())
  if page==8 and self.datasetNeeded('marine'):self.fetchAdvanced('marine')
  if page==6 and self.state['prefs']['autoRefresh'] and not self.http.offline and time.time()-self._air.get('saved',0)>1800:self.loadSelected()
  if page==10:
   for kind in ('models','ensemble')+ (('runs',) if 'runs' in self._datasets else ()):
    if self.datasetNeeded(kind):self.fetchAdvanced(kind)
  if page in (0,12) and 'alerts' not in self._advanced:self.fetchAlerts()
 def startPreview(self):
  if not self.visible or self.state['page']!=0:return
  if self._map is None:
   from services.map import MapController
   self._map=MapController(self);self._map.start()
  self._map.setPreviewActive(True)
 def clearDatasets(self):
  self._presentationVersion+=1
  for kind in TTL:
   self._datasetVersions[kind]=self._datasetVersions.get(kind,0)+1
   self.http.cancel('history' if kind=='history' else 'advanced:'+kind)
  self._datasets.clear();self._datasetAttempts.clear();self._solarDate=None
 def reformatDatasets(self):
  self._presentationVersion+=1
  for kind,bundle in self._datasets.items():self.prepareDataset(kind,bundle,self.state['selected'],self._datasetVersions.get(kind,0))
  if self._solarDate:self.calculateSolar(self._solarDate)
  self.advancedChanged.emit();self.summaryChanged.emit()
 def prepareDataset(self,kind,bundle,loc,version,previous=None):
  loc=copy.deepcopy(loc);prefs=dict(self.state['prefs']);identity=loc['id'];presentation=self._presentationVersion
  def task():
   try:return bundle,present(kind,bundle,loc,prefs)
   except (ValueError,KeyError,TypeError,IndexError) as exc:
    logging.warning('Dataset %s parse failed: %s',kind,exc)
    fallback=retain(previous or {},{'data':None,'saved':0,'stale':True,'error':'Dataset parsing failed; previous data retained','source':bundle.get('source','')})
    return fallback,present(kind,fallback,loc,prefs)
  def adopt(value,error):
   if self.state['selected'].get('id')!=identity or self._datasetVersions.get(kind,0)!=version or presentation!=self._presentationVersion:return
   if error:self._advanced[kind]={**self._advanced.get(kind,{}),'loading':False,'error':'Dataset display unavailable; previous data retained'}
   else:self._datasets[kind],self._advanced[kind]=value
   self.advancedChanged.emit();self.summaryChanged.emit()
  self.work.submit('dataset:'+kind,task,adopt)
 def calculateSolar(self,date):
  result=solar(self.state['selected'],date,self.state['prefs']);self._solarDate=date;self._advanced['solar']=result;self.advancedChanged.emit()
 def datasetNeeded(self,kind):
  if self._advanced.get(kind,{}).get('loading'):return False
  if kind not in self._advanced:return True
  return bool(self.state['prefs']['autoRefresh'] and not self.http.offline and time.time()-self._datasets.get(kind,{}).get('saved',0)>TTL[kind] and time.time()-self._datasetAttempts.get(kind,0)>=300)
 def fetchAdvanced(self,kind,force=False,period=None):
  if kind not in TTL:raise ValueError('Unsupported advanced dataset')
  loc=copy.deepcopy(self.state['selected']);identity=loc['id'];version=self._datasetVersions.get(kind,0)+1;self._datasetVersions[kind]=version;self._datasetAttempts[kind]=time.time()
  previous=self._datasets.get(kind,{})
  self.http.cancel('history' if kind=='history' else 'advanced:'+kind)
  self._advanced[kind]={**self._advanced.get(kind,{}),'loading':True,'error':''};self.advancedChanged.emit()
  def done(value):
   if self.state['selected'].get('id')!=identity or self._datasetVersions.get(kind)!=version:return
   incoming={**value,'period':period} if kind=='history' and value.get('data') is not None else value
   bundle=retain(previous,incoming)
   self._datasets[kind]=bundle;self.prepareDataset(kind,bundle,loc,version,previous)
  if kind=='history':self.providers.history(loc,period['start'],period['end'],done,force)
  else:getattr(self.providers,kind)(loc,done,force)
 def fetchAlerts(self,force=False):
  from services.alerts import fetch_alerts
  loc=copy.deepcopy(self.state['selected']);identity=loc['id'];self._advanced['alerts']={'status':'Loading official alerts','items':[],'available':False};self.advancedChanged.emit()
  def done(value):
   if self.state['selected'].get('id')==identity:
    self._advanced['alerts']=value;self.advancedChanged.emit()
    if self._map and self.state['map']['layer']=='alerts':self._map.requestRender()
  fetch_alerts(self.http,loc,done,force)
 @Slot(str)
 def search(self,query):self.searchLocations(query)
 @Slot(str,str)
 def act(self,action,payload):
  try:self.action(action,json.loads(payload))
  except Exception as exc:self.status_text(str(exc));logging.warning('Action %s failed: %s',action,exc)
 @Slot(float,float,float,float,float)
 def viewport(self,width,height,zoom,x,y):
  if self._map:self._map.viewport(width,height,zoom,x,y)
 @Slot(result=str)
 def diagnostics(self):return json.dumps({'version':'1.1','python':sys.version,'Qt':qVersion(),'renderer':self.window.rendererInterface().graphicsApi().name if self.window else 'No window','providers':self.providerStatus,'requests':self.http.requests,'pending':len(self.http.flights),'cacheMiB':sum(p.stat().st_size for p in self.http.root.iterdir() if p.is_file())/1024**2,'latest':self.summary['refresh'],'datasets':self.datasetAges,'metadata':self.metadata},indent=2)
 def shutdown(self):
  self.compactTimer.stop();self.tickTimer.stop();self.saveTimer.stop();self.http.close()
  if self._map:self._map.close()
  self.work.close()
  self.chartWork.close()
  self.store.save();self.writer.close()
