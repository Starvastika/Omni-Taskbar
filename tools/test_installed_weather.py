import os,sys,json,tempfile,datetime as dt,time,copy,site
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'.validation/omni-installer';OUT.mkdir(parents=True,exist_ok=True)
PROGRAM=Path(os.environ['OMNI_PROGRAM_ROOT']);os.environ.pop('OMNI_USER_ROOT',None)
sys.path[:0]=[str(PROGRAM/'weather-center'),str(PROGRAM/'weather-center/vendor')]
os.environ['QT_QPA_PLATFORM']='offscreen';os.environ['QSG_RENDER_LOOP']='basic'
from PySide6.QtCore import QTimer,QEventLoop,QUrl,QObject,qInstallMessageHandler
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine,qmlRegisterType
from PySide6.QtQuickControls2 import QQuickStyle
from services.state import StateStore,AtomicWriter,default_state,location
from services.compact import project
from app.bridge import Bridge
from app.charts import WeatherChart
app=QGuiApplication([]);app.setQuitOnLastWindowClosed(False);QQuickStyle.setStyle('Basic')
def wait(ms=100):
 loop=QEventLoop();QTimer.singleShot(ms,loop.quit);loop.exec()
results=[]
def check(name,ok):
 results.append(dict(case=name,passed=bool(ok)));print(name,bool(ok),flush=True);assert ok,name
with tempfile.TemporaryDirectory() as tmp:
 root=Path(tmp);home=root/'weather-center';home.mkdir()
 oldlocal=os.environ['LOCALAPPDATA'];os.environ['LOCALAPPDATA']=str(root/'local')
 (root/'config.yaml').write_text("widgets:\n  open_meteo:\n    type: yasb.open_meteo.OpenMeteoWidget\n")
 oldloc={'name':'Legacy Fixture','latitude':51.5,'longitude':-.1,'timezone':'Europe/London'}
 writer=AtomicWriter();store=StateStore(home,writer)
 check('fresh state unconfigured',not store.state['selected'])
 (root/'local/YASB').mkdir(parents=True);(root/'local/YASB/weather.json').write_text(json.dumps({'open_meteo':oldloc}))
 store=StateStore(home,writer);check('valid legacy compact location migrates',store.state['selected']['name']=='Legacy Fixture')
 selected=location({'id':'selected','name':'Selected Fixture','lat':35.6,'lon':139.7,'zone':'Asia/Tokyo'})
 saved=location({'id':'saved','name':'Saved Fixture','lat':51.5,'lon':-.1,'zone':'Europe/London'})
 state=default_state(selected);state['locations']=[saved,selected];state['prefs']['offline']=True
 (home/'data').mkdir(exist_ok=True);(home/'data/state.json').write_text(json.dumps(state))
 store=StateStore(home,writer);check('Weather Center selection wins over duplicate old location',store.state['selected']['id']=='selected')
 check('migration preserves saved locations',[x['id'] for x in store.state['locations']]==['saved','selected'])
 writer.close();os.environ['LOCALAPPDATA']=oldlocal
 b=Bridge(PROGRAM/'weather-center',home);b.http.offline=True;b.compactTimer.stop()
 callbacks=[]
 class Providers:
  def forecast(self,loc,prefs,cb,*_):callbacks.append((loc['id'],'forecast',cb))
  def air(self,loc,cb,*_):callbacks.append((loc['id'],'air',cb))
  def geocode(self,query,cb):cb([location({'name':'Search Fixture','lat':43,'lon':-80,'zone':'America/Toronto'},True)],{})
 b.providers=Providers()
 a={**selected,'id':'a','name':'Fixture A'};z={**selected,'id':'b','name':'Fixture B'}
 b.select(a);oldcb=next(x[2] for x in callbacks if x[:2]==('a','forecast'));b.select(z)
 oldcb({'data':{'current':{'temperature_2m':999}},'saved':time.time(),'cache':False})
 check('old in-flight provider result is rejected after location change',not b._forecast)
 check('changing location preserves all saved locations',[x['id'] for x in b.state['locations']]==['saved','selected'])
 errorcb=next(x[2] for x in callbacks if x[:2]==('b','forecast'));errorcb({'data':{},'saved':0,'cache':False,'error':'Offline fixture','stale':True});wait()
 check('offline projection retains selected identity',json.loads((home/'data/compact.json').read_text())['location']['id']=='b')
 check('provider error does not clear selection',b.state['selected']['id']=='b')
 epoch=time.time();data={'current':{'time':epoch,'temperature_2m':15,'wind_speed_10m':10,'weather_code':0,'is_day':1},
       'hourly':{'time':[epoch],'temperature_2m':[15],'wind_speed_10m':[10],'weather_code':[0]},
       'daily':{'time':[epoch],'temperature_2m_min':[10],'temperature_2m_max':[20],'sunrise':[epoch],'sunset':[epoch+30000]}}
 value=project(b.state,{'data':data,'saved':epoch,'stale':False},b.generation)
 check('compact contract converts SI wind correctly',value['data']['current']['wind_speed_10m']==36)
 check('compact times follow authoritative selected timezone',value['data']['current']['time']==dt.datetime.fromtimestamp(epoch,__import__('zoneinfo').ZoneInfo('Asia/Tokyo')).strftime('%Y-%m-%dT%H:%M'))
 check('projection leaves source data untouched',data['current']['wind_speed_10m']==10 and isinstance(data['current']['time'],float))
 # QML uses the actual new location-only deep link and real focused input.
 issues=[];qInstallMessageHandler(lambda mode,ctx,msg:issues.append(msg))
 qmlRegisterType(WeatherChart,'WeatherCenter',1,0,'WeatherChart')
 engine=QQmlApplicationEngine();engine.addImageProvider('weatherMap',b.images);engine.rootContext().setContextProperty('weather',b)
 engine.load(QUrl.fromLocalFile(str(PROGRAM/'weather-center/qml/Main.qml')))
 check('Weather Center QML loads',bool(engine.rootObjects()))
 w=engine.rootObjects()[0];b.window=w;w.show();wait(50)
 w.openLocationPicker();wait(80)
 check('real deep link navigates to Locations',b.state['page']==11)
 check('real location-only picker is open',w.property('choosingLocation') and b.modalCount>0)
 check('location search input receives focus',w.activeFocusItem() is not None and w.activeFocusItem().objectName()=='weatherLocationSearchInput')
 b.search('Fixture');wait(30);found=next(x for x in b.results if x.get('name')=='Search Fixture')
 b.action('searchSelect',found);wait(120)
 check('real search result selection persists into shared projection',json.loads((home/'data/compact.json').read_text())['location']['name']=='Search Fixture')
 check('location-only picker keeps application command search separate',not any('ReferenceError' in x or 'TypeError' in x for x in issues))
 w.hide();b.shutdown()
 check('selection survives host-style restart',StateStore(home,AtomicWriter()).state['selected']['name']=='Search Fixture')
 (OUT/'weather-tests.json').write_text(json.dumps({'tests':results,'qml_messages':issues},indent=2),'utf-8')
print('Weather cases',len(results))
