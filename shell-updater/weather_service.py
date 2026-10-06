"""Event-driven reader of Weather Center's authoritative state and derived data."""
import copy,hashlib,json,os,time,sys
from pathlib import Path
from PyQt6.QtCore import QObject,QFileSystemWatcher,QTimer,QProcess,pyqtSignal
from PyQt6.QtNetwork import QLocalSocket

sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from omni_layout import program_root,user_root,runtime_python
ROOT=program_root()
def identity(location):
 return tuple((location or {}).get(key) for key in ('id','lat','lon','zone'))
class SharedWeather(QObject):
 changed=pyqtSignal(dict)
 _instance=None
 @classmethod
 def instance(cls):
  if cls._instance is None:cls._instance=cls()
  return cls._instance
 def __init__(self,root=ROOT,parent=None):
  super().__init__(parent);self.root=Path(root);self.folder=user_root(self.root)/'weather-center/data';self.folder.mkdir(parents=True,exist_ok=True)
  self.snapshot={};self.digest='';self.watcher=QFileSystemWatcher([str(self.folder)],self)
  self.watcher.directoryChanged.connect(self.schedule)
  self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.setInterval(40);self.timer.timeout.connect(self.read)
  self.age=QTimer(self);self.age.setInterval(60000);self.age.timeout.connect(lambda:self.changed.emit(copy.deepcopy(self.snapshot)))
  self.sockets=set();self.launches=set();self.read()
 def schedule(self,*_):self.timer.start()
 def read(self):
  try:
   state=json.loads((self.folder/'state.json').read_text('utf-8'));loc=state.get('selected') or {}
  except (OSError,ValueError):loc=(self.snapshot.get('location') or {})
  try:projection=json.loads((self.folder/'compact.json').read_text('utf-8'))
  except (OSError,ValueError):projection={}
  if identity(projection.get('location'))!=identity(loc):projection={}
  value={**projection,'location':loc}
  if loc:
   if not self.age.isActive():self.age.start()
  else:self.age.stop()
  encoded=json.dumps(value,sort_keys=True);digest=hashlib.sha256(encoded.encode()).hexdigest()
  if digest!=self.digest:self.digest=digest;self.snapshot=value;self.changed.emit(copy.deepcopy(value))
 def open(self,locations=False):
  root=self.root/'weather-center';name='YasbWeatherCenter-'+hashlib.sha256(str(root).casefold().encode()).hexdigest()[:16]
  socket=QLocalSocket(self);self.sockets.add(socket)
  command='locations' if locations else 'toggle'
  done=[False]
  def cleanup():
   self.sockets.discard(socket);socket.deleteLater()
  def fallback(*_):
   if done[0]:return
   done[0]=True;socket.abort();cleanup()
   try:
    python=runtime_python(self.root).with_name('pythonw.exe')
    QProcess.startDetached(str(python),[str(root/'app/main.py'),'--locations' if locations else '--toggle'],str(root))
   except (OSError,ValueError,KeyError):pass
  def connected():
   if done[0]:return
   if os.name=='nt':
    # Same explicit-click foreground handoff as the existing native launcher.
    import ctypes
    from ctypes import wintypes as W
    pid=W.DWORD();query=ctypes.windll.kernel32.GetNamedPipeServerProcessId
    query.argtypes=[W.HANDLE,ctypes.POINTER(W.DWORD)];query.restype=W.BOOL
    if query(W.HANDLE(int(socket.socketDescriptor())),ctypes.byref(pid)):
     ctypes.windll.user32.AllowSetForegroundWindow(pid.value)
   done[0]=True;socket.write((json.dumps({'command':command,'reply':False})+'\n').encode());socket.flush();socket.disconnectFromServer()
  socket.connected.connect(connected);socket.errorOccurred.connect(fallback);socket.disconnected.connect(cleanup)
  socket.connectToServer(name)
  QTimer.singleShot(500,lambda:fallback() if not done[0] else None)
