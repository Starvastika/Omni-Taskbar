import json,sys,time,tempfile,copy,os,shutil,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'.validation/omni-installer';OUT.mkdir(parents=True,exist_ok=True)
PROGRAM=Path(os.environ['OMNI_PROGRAM_ROOT']);sys.path.insert(0,str(ROOT/'tools'))
import installed_native_runtime
sys.path.insert(0,str(PROGRAM/'shell-updater'))
os.environ.pop('OMNI_USER_ROOT',None)
from PyQt6.QtCore import QTimer,QEventLoop,Qt
from PyQt6.QtWidgets import QApplication,QWidget,QHBoxLayout,QPushButton,QLabel
from engine import atomic
from service import UpdateService
from weather_service import SharedWeather
app=QApplication([]);app.setQuitOnLastWindowClosed(False)
def wait(ms=100):
 loop=QEventLoop();QTimer.singleShot(ms,loop.quit);loop.exec()
results=[]
def check(name,ok,**details):
 results.append(dict(case=name,passed=bool(ok),**details));print(name,bool(ok),flush=True);assert ok,name
with tempfile.TemporaryDirectory() as tmp:
 root=Path(tmp);atomic(root/'version.json',{'version':'1.0.0','updater_version':'1.0.0','repository':'Starvastika/Omni-Taskbar'})
 updates=UpdateService(root,startup=False);UpdateService._instance=updates
 shutil.copy2(PROGRAM/'shell-updater/engine.py',root/'shell-updater/engine.py')
 shutil.copy2(PROGRAM/'omni_layout.py',root/'omni_layout.py')
 atomic(root/'helpers/runtime-settings.json',{'python':str(PROGRAM/'runtime/python/python.exe')})
 shared=SharedWeather(root);SharedWeather._instance=shared
 import core.widgets.yasb.power_menu as power
 power.get_windows_username=lambda:'Validation Account';power.get_user_email=lambda:None;power.get_user_avatar_path=lambda:None;power.get_account_type=lambda:'Standard user'
 actions=[]
 class Operations:
  def __init__(self,*_):pass
  def __getattr__(self,name):return lambda:actions.append(name)
 power.PowerOperations=Operations
 from core.validation.widgets.yasb.power_menu import PowerMenuConfig
 from core.validation.widgets.yasb.open_meteo import OpenMeteoWidgetConfig
 from core.widgets.yasb.open_meteo import OpenMeteoWidget
 import yaml
 config=yaml.safe_load((PROGRAM/'distribution/defaults/config.yaml').read_text('utf-8'))
 from core.validation.config import YasbConfig
 check('entire shipped configuration validates against native YASB 2.0.7 schema',bool(YasbConfig(**config)))
 check('only Omni release updater is enabled',config['update_check'] is False)
 host=QWidget(None,Qt.WindowType.Tool);host.setProperty('class','yasb-top-bar');host.resize(1200,34);host.move(0,0)
 from core.config import get_stylesheet
 host.setStyleSheet(get_stylesheet());layout=QHBoxLayout(host)
 p=power.PowerMenuWidget(PowerMenuConfig(**config['widgets']['power_menu']['options']));layout.addStretch();layout.addWidget(p)
 w=OpenMeteoWidget(OpenMeteoWidgetConfig(**config['widgets']['open_meteo']['options']));w.widget_name='open_meteo'
 layout.insertWidget(0,w);host.show();wait()
 check('fresh unconfigured weather label',any(l.text()=='Setup location' for l in w.findChildren(QLabel)))
 opened=[];shared.open=lambda choose=False:opened.append(choose)
 w.callback_left='weather_center'
 # Actual registered callback dispatch; no physical input claim.
 w._run_callback(w.callback_left)
 check('setup callback requests location deep link',opened==[True])
 from PyQt6.QtNetwork import QLocalServer
 pipe='YasbWeatherCenter-'+hashlib.sha256(str(root/'weather-center').casefold().encode()).hexdigest()[:16]
 server=QLocalServer();server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption);assert server.listen(pipe)
 received=[];connections=[]
 def accept():
  while server.hasPendingConnections():
   socket=server.nextPendingConnection();connections.append(socket)
   socket.readyRead.connect(lambda s=socket:received.append(json.loads(bytes(s.readAll()).split(b'\n')[0])))
 server.newConnection.connect(accept);SharedWeather.open(shared,True);wait(120)
 check('Setup location route crosses a real user-scoped native pipe',received==[{'command':'locations','reply':False}])
 server.close()
 loc={'id':'fixture-a','name':'Fixture A','lat':43.4,'lon':-80.5,'zone':'America/Toronto'}
 def write(loc,data=None,**extra):
  atomic(root/'weather-center/data/state.json',{'selected':loc,'locations':[loc]})
  atomic(root/'weather-center/data/compact.json',{'schema':1,'location':loc,'prefs':{'temperature':'C'},'data':data or {},**extra})
 write(loc,offline=True,error='offline');wait()
 check('configured offline never becomes Setup location',w._location_data['id']=='fixture-a' and any('Fixture A' in l.text() for l in w.findChildren(QLabel)))
 data={'current':{'time':'2026-10-05T12:00','temperature_2m':18,'weather_code':0,'is_day':1},
       'daily':{'time':['2026-10-05'],'temperature_2m_min':[10],'temperature_2m_max':[20],'weather_code':[0],'sunrise':['2026-10-05T07:00'],'sunset':['2026-10-05T19:00']},
       'hourly':{'time':['2026-10-05T12:00'],'temperature_2m':[18],'weather_code':[0],'wind_speed_10m':[5]}}
 write(loc,data,saved=time.time(),stale=False);wait()
 check('atomic forecast immediately reaches installed compact widget',w._has_valid_weather_data and '18' in w._weather_data['{temp}'])
 check('no stock independent fetcher',not w._shared_fetchers and not w._retry_timer.isActive())
 loc2={**loc,'id':'fixture-b','name':'Fixture B','zone':'Asia/Tokyo','lat':35.6,'lon':139.7}
 atomic(root/'weather-center/data/state.json',{'selected':loc2});wait()
 check('changing identity clears old forecast before new projection',w._location_data['id']=='fixture-b' and not w._has_valid_weather_data)
 write(loc2,{},error='provider failed');wait()
 check('provider error preserves configured identity',w._location_data['id']=='fixture-b' and any('Fixture B' in l.text() for l in w.findChildren(QLabel)))
 shared2=SharedWeather(root);check('new service reads persisted selection',shared2.snapshot['location']['id']=='fixture-b')
 write(loc2,data,saved=time.time(),stale=False);wait()
 moved={**loc2,'lat':34.1}
 atomic(root/'weather-center/data/state.json',{'selected':moved});wait()
 check('same ID with changed coordinates rejects old projection',not shared.snapshot.get('data') and not w._has_valid_weather_data and w._location_data['lat']==34.1)
 write(loc,data,saved=time.time(),stale=False);wait();w._toggle_card();wait()
 check('existing compact forecast popup still opens upward',w.dialog.isVisible() and w.dialog.y()<=w.mapToGlobal(w.rect().topLeft()).y())
 w.dialog.hide();p._show_popup_menu();wait()
 check('existing account popup still opens',p._popup.isVisible())
 main=[p._popup.layout().itemAt(i).widget() for i in range(p._popup.layout().count())]
 check('Taskbar Updates follows exact profile/Manage accounts before power group',main[0].property('class')=='profile-info' and main[1] is p.update_row and main[2].property('class')=='buttons')
 check('no red dot without unresolved update',p.update_dot.isHidden() and p.update_row_dot.isHidden())
 atomic(updates.folder/'state.json',{'mode':'manual','status':'Version 1.0.1 is available','available':True,'attention':True});wait()
 check('available state shows both persistent indicators',not p.update_dot.isHidden() and not p.update_row_dot.isHidden())
 p.switch_updates(True);wait()
 check('update view displays installed version',p.installed.text()=='Version 1.0.0' and p.install_button.isVisible())
 check('update popup remains downward',p._popup.y()>=p.mapToGlobal(p.rect().bottomLeft()).y())
 # No screenshots enter release inventory.
 p.switch_updates(False);p._popup.hide();p._show_popup_menu();wait()
 check('opening closing back never clears update indicator',updates.state['attention'] and not p.update_dot.isHidden())
 atomic(updates.folder/'state.json',{'mode':'automatic','status':'Ready to update','staged_version':'1.0.1','attention':True});wait();p.switch_updates(True)
 check('staged update uses Restart and Update Now',p.install_button.text()=='Restart & Update Now' and not p.update_dot.isHidden())
 atomic(updates.folder/'state.json',{'mode':'check','status':'Update failed. Restored 1.0.0','failure':True,'attention':True});wait()
 check('rollback state remains unresolved',not p.update_dot.isHidden() and not p.update_row_dot.isHidden())
 atomic(updates.folder/'state.json',{'mode':'manual','status':"You're up to date",'attention':False,'notes':'<script>must remain plain text</script>'});wait()
 check('manual policy stops cadence',not updates.cadence.isActive())
 p.toggle_notes();check('release notes are plain text',p.notes.toPlainText()=='<script>must remain plain text</script>')
 p.switch_updates(False)
 for frame in p._popup.findChildren(power.QFrame):
  if hasattr(frame,'_action'):frame._action()
 check('original six power action bindings retained safely',set(actions)=={'lock','signout','sleep','hibernate','restart','shutdown'})
 check('mode selector reflects persisted policy',p.mode.currentData()=='manual')
 heartbeat=[0];tick=QTimer();tick.setInterval(10);tick.timeout.connect(lambda:heartbeat.__setitem__(0,heartbeat[0]+1));tick.start()
 p.mode.activated.emit(p.mode.findData('manual'));end=time.monotonic()+5
 while updates.job is not None and time.monotonic()<end:wait(20)
 check('mode selector uses real isolated worker and persists',updates.job is None and json.loads((updates.folder/'state.json').read_text())['mode']=='manual' and not updates.state.get('failure'))
 updates.launch('check');end=time.monotonic()+45
 while updates.job is not None and time.monotonic()<end:wait(20)
 tick.stop()
 check('manual Check runs asynchronously while GUI heartbeat continues',updates.job is None and heartbeat[0]>3 and updates.state.get('last_checked',0)>0)
 p._popup.hide();host.hide();shared2.deleteLater();wait()
 (OUT/'widget-tests.json').write_text(json.dumps(results,indent=2),'utf-8')
print('Widget cases',len(results))
