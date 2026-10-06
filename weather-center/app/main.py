"""One hidden shell host; user-scoped Qt named-pipe IPC, no per-click Python."""
import argparse,ctypes,hashlib,json,logging,os,site,sys,time
from ctypes import wintypes
from logging.handlers import RotatingFileHandler
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
# Charts rasterize in a bounded worker; native QML textures render independently.
# No Python paint virtual runs on Qt's render thread.
os.environ.setdefault('QSG_RENDER_LOOP','threaded')
sys.path.insert(0,str(ROOT/'vendor'))
site.addsitedir(str(ROOT.parent/'time-center/.venv/Lib/site-packages'))
NAME='YasbWeatherCenter-'+hashlib.sha256(str(ROOT).casefold().encode()).hexdigest()[:16]
from PySide6.QtCore import QLockFile,QTimer,QUrl,Qt,qInstallMessageHandler
from PySide6.QtNetwork import QLocalServer,QLocalSocket
def send(command):
 s=QLocalSocket();s.connectToServer(NAME)
 if not s.waitForConnected(300):return None
 s.write((json.dumps(command)+'\n').encode());s.waitForBytesWritten(400);raw=b'';end=time.monotonic()+3
 while time.monotonic()<end:
  if s.bytesAvailable() or s.waitForReadyRead(150):
   raw+=bytes(s.readAll())
   if b'\n' in raw:return json.loads(raw.split(b'\n')[0])
 return {'error':'Host response timed out'}
def main():
 p=argparse.ArgumentParser();p.add_argument('--toggle',action='store_true');p.add_argument('--locations',action='store_true');p.add_argument('--status',action='store_true');p.add_argument('--hide',action='store_true');p.add_argument('--quit',action='store_true');p.add_argument('--command');p.add_argument('--data-root');a=p.parse_args()
 command=json.loads(a.command) if a.command else {'command':'locations' if a.locations else 'toggle' if a.toggle else 'hide' if a.hide else 'quit' if a.quit else 'status'}
 result=send(command)
 if result is not None:
  if sys.stdout:print(json.dumps(result,ensure_ascii=True))
  return 0
 if a.status or a.hide or a.quit or a.command:
  if sys.stdout:print('{"running":false}')
  return 1
 from PySide6.QtGui import QGuiApplication
 from PySide6.QtQml import QQmlApplicationEngine,qmlRegisterType
 from PySide6.QtQuickControls2 import QQuickStyle
 from app.bridge import Bridge
 from app.charts import WeatherChart
 (ROOT/'logs').mkdir(exist_ok=True);(ROOT/'data').mkdir(exist_ok=True)
 handler=RotatingFileHandler(ROOT/'logs/weather-center.log',maxBytes=262144,backupCount=2,encoding='utf-8');handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'));logging.basicConfig(level=logging.INFO,handlers=[handler])
 sys.excepthook=lambda k,e,t:logging.error('Unhandled exception',exc_info=(k,e,t))
 qInstallMessageHandler(lambda mode,ctx,msg:logging.warning('Qt: %s',msg))
 QQuickStyle.setStyle('Basic');app=QGuiApplication(sys.argv);app.setQuitOnLastWindowClosed(False);app.setApplicationName('YASB Weather Center')
 lock=QLockFile(str(ROOT/'data/host.lock'));lock.setStaleLockTime(0)
 if not lock.tryLock(0):send(command);return 0
 qmlRegisterType(WeatherChart,'WeatherCenter',1,0,'WeatherChart')
 bridge=Bridge(ROOT if not a.data_root else Path(a.data_root));engine=QQmlApplicationEngine();engine.addImageProvider('weatherMap',bridge.images);engine.rootContext().setContextProperty('weather',bridge)
 engine.load(QUrl.fromLocalFile(str(ROOT/'qml/Main.qml')))
 if not engine.rootObjects():logging.error('QML failed to load');bridge.shutdown();return 1
 window=engine.rootObjects()[0];bridge.window=window;u=ctypes.windll.user32
 u.GetForegroundWindow.restype=ctypes.c_void_p;u.SetForegroundWindow.argtypes=[ctypes.c_void_p];u.GetWindowThreadProcessId.argtypes=[ctypes.c_void_p,ctypes.c_void_p]
 previous=[None];toggles=[0];hideReason=['Starting hidden']
 def hide(reason='Requested'):
  hideReason[0]=reason
  window.hide();bridge.setVisible(False)
  if previous[0] and u.GetForegroundWindow()==int(window.winId()):u.SetForegroundWindow(previous[0])
 def show():
  previous[0]=u.GetForegroundWindow();area=app.primaryScreen().availableGeometry()
  # Keep clear of the edge-revealed top overlay without changing app-bar space.
  import yaml
  config=yaml.safe_load((ROOT.parent/'config.yaml').read_text('utf-8'));top=next((b for b in config['bars'].values() if b.get('enabled',True) and b['alignment']['position']=='top'),None)
  screen=app.primaryScreen().geometry()
  if top and area.top()==screen.top():area.adjust(0,int(top['dimensions']['height'])+int(top.get('padding',{}).get('top',0)),0,0)
  bottom=next((b for b in config['bars'].values() if b.get('enabled',True) and b['alignment']['position']=='bottom'),None)
  if bottom:area.setBottom(min(area.bottom(),screen.bottom()-int(bottom['dimensions']['height'])-int(bottom.get('padding',{}).get('bottom',0))))
  window.setGeometry(area);window.show();window.raise_();window.requestActivate();bridge.setVisible(True)
  target=int(window.winId());fg=u.GetForegroundWindow();thread=u.GetWindowThreadProcessId(fg,None) if fg else 0;current=ctypes.windll.kernel32.GetCurrentThreadId()
  attached=bool(thread and thread!=current and u.AttachThreadInput(current,thread,True))
  try:u.SetForegroundWindow(target)
  finally:
   if attached:u.AttachThreadInput(current,thread,False)
 def toggle():
  toggles[0]+=1;hide() if window.isVisible() else show()
 def fullscreen_focus():
  if not window.isVisible():return
  foreground=u.GetForegroundWindow()
  if not foreground or foreground==int(window.winId()):return
  u.GetClassNameW.argtypes=[wintypes.HWND,wintypes.LPWSTR,ctypes.c_int];name=ctypes.create_unicode_buffer(128);u.GetClassNameW(foreground,name,128)
  if name.value in ('Progman','WorkerW','Shell_TrayWnd','Shell_SecondaryTrayWnd','BackstopWindow'):return
  u.GetWindowRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)];rect=wintypes.RECT()
  if not u.GetWindowRect(foreground,ctypes.byref(rect)):return
  for screen in app.screens():
   g=screen.geometry()
   if all(abs(a-b)<=2 for a,b in zip((rect.left,rect.top,rect.right,rect.bottom),(g.left(),g.top(),g.right()+1,g.bottom()+1))) and g.intersects(window.geometry()):hide('Other fullscreen window received focus');return
 window.activeChanged.connect(lambda:QTimer.singleShot(0,fullscreen_focus))
 bridge.hideRequested.connect(hide)
 server=QLocalServer();server.setSocketOptions(QLocalServer.UserAccessOption);QLocalServer.removeServer(NAME)
 if not server.listen(NAME):logging.error('IPC failed: %s',server.errorString());return 1
 clients=set()
 def connected():
  while server.hasPendingConnections():
   s=server.nextPendingConnection();clients.add(s);buffers={s:b''}
   def read(socket=s,buffer=buffers):
    raw=buffer[socket]+bytes(socket.readAll())
    if len(raw)>131072:socket.disconnectFromServer();return
    if b'\n' not in raw:buffer[socket]=raw;return
    replyWanted=True
    try:
     msg=json.loads(raw.split(b'\n')[0]);cmd=msg.get('command','status')
     replyWanted=msg.get('reply',True)
     if cmd=='toggle':toggle()
     elif cmd=='locations':
      show();bridge.act('page',json.dumps({'value':11}));QTimer.singleShot(0,window.openLocationPicker)
     elif cmd=='hide':hide()
     elif cmd=='quit':QTimer.singleShot(80,lambda:app.exit(0))
     elif cmd=='action':bridge.act(msg['action'],json.dumps(msg.get('payload',{})))
     response={'running':True,'pid':os.getpid(),'visible':window.isVisible(),'geometry':[window.x(),window.y(),window.width(),window.height()],'page':bridge.state['page'],'summary':bridge.summary,'status':bridge.status,'providers':bridge.providerStatus,'toggleCount':toggles[0],'hideReason':hideReason[0],'renderer':window.rendererInterface().graphicsApi().name,'map':bridge.mapData if cmd=='status' else None,'state':bridge.state if cmd=='status' else None}
    except Exception as exc:response={'error':str(exc)}
    if replyWanted:socket.write((json.dumps(response,ensure_ascii=False)+'\n').encode());socket.flush()
    socket.disconnectFromServer()
   def disconnected(socket=s):
    clients.discard(socket)
    # Socket remains owned here; no shutdown callback against already-deleted objects.
    socket.deleteLater()
   s.readyRead.connect(read);s.disconnected.connect(disconnected)
 server.newConnection.connect(connected)
 pidfile=ROOT/'data/host.json';pidfile.write_text(json.dumps({'pid':os.getpid(),'started':time.time(),'executable':sys.executable,'baseExecutable':sys._base_executable,'script':str(Path(__file__).resolve())}),'utf-8')
 runtime={'pipe':NAME,'python':sys._base_executable.replace('python.exe','pythonw.exe'),'script':str(Path(__file__).resolve())}
 (ROOT/'runtime.json').write_text(json.dumps(runtime),'utf-8')
 def quit_cleanly():
  server.close()
  for s in tuple(clients):s.blockSignals(True);s.close()
  bridge.shutdown();lock.unlock()
  try:pidfile.unlink()
  except OSError:pass
  logging.info('Host stopped')
 app.aboutToQuit.connect(quit_cleanly);logging.info('Host started hidden; pid=%s',os.getpid())
 if a.toggle:QTimer.singleShot(0,show)
 if a.locations:QTimer.singleShot(0,lambda:(show(),bridge.act('page',json.dumps({'value':11})),window.openLocationPicker()))
 return app.exec()
if __name__=='__main__':raise SystemExit(main())
