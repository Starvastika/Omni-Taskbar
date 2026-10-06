"""One in-YASB cached projection; network and apply run outside the GUI process."""
import json,sys,time,os
from pathlib import Path
from PyQt6.QtCore import QObject,QFileSystemWatcher,QTimer,QProcess,pyqtSignal

ROOT=Path.home()/'.config/yasb'
def interpreter(root):
 try:value=json.loads((Path(root)/'helpers/runtime-settings.json').read_text('utf-8')).get('python')
 except (OSError,ValueError):value=None
 result=Path(value) if value else Path.home()/'AppData/Local/Python/pythoncore-3.14-64/pythonw.exe'
 return str(result.with_name('pythonw.exe') if result.name.casefold()=='python.exe' else result)
class UpdateService(QObject):
 changed=pyqtSignal()
 _instance=None
 @classmethod
 def instance(cls):
  if cls._instance is None:cls._instance=cls()
  return cls._instance
 def __init__(self,root=ROOT,parent=None,startup=True):
  super().__init__(parent);self.root=Path(root);self.folder=self.root/'shell-updater/data';self.folder.mkdir(parents=True,exist_ok=True)
  self.state={};self.job=None;self.pending=None;self.watcher=QFileSystemWatcher([str(self.folder)],self)
  self.debounce=QTimer(self);self.debounce.setSingleShot(True);self.debounce.setInterval(50);self.debounce.timeout.connect(self.read)
  self.watcher.directoryChanged.connect(lambda *_:self.debounce.start())
  self.cadence=QTimer(self);self.cadence.setInterval(6*3600*1000);self.cadence.timeout.connect(self.background)
  self.read()
  if startup:QTimer.singleShot(1500,self.startup)
 @property
 def version(self):
  try:return json.loads((self.root/'version.json').read_text('utf-8'))['version']
  except (OSError,ValueError,KeyError):return 'Unavailable'
 def read(self):
  try:self.state=json.loads((self.folder/'state.json').read_text('utf-8'))
  except (OSError,ValueError):self.state={'status':'Choose an update mode','attention':False,'mode':None}
  if self.state.get('mode') in ('automatic','check'):self.cadence.start() if not self.cadence.isActive() else None
  else:self.cadence.stop()
  self.changed.emit()
 def startup(self):
  try:
   lease=json.loads((self.folder/'maintenance.json').read_text('utf-8'))
   if lease.get('expires',0)>time.time():QTimer.singleShot(1000,self.startup);return
  except (OSError,ValueError):pass
  if self.state.get('transaction') or self.state.get('busy'):self.launch('recover',detached=True)
  elif self.state.get('mode')=='automatic' and self.state.get('staged_version') and not self.state.get('failure'):self.launch('auto',detached=True)
  else:self.background()
 def background(self):
  if self.state.get('mode') in ('automatic','check'):self.launch('background')
 def launch(self,action,mode=None,detached=False):
  if self.job is not None or (self.state.get('busy') and action in ('install','apply','auto')):return False
  args=[str(self.root/'shell-updater/engine.py'),'--root',str(self.root),'--action',action]
  if mode:args+=['--mode',mode]
  if detached:
   ok,pid=QProcess.startDetached(interpreter(self.root),args,str(self.root))
   if ok:self.state.update(busy=True,status='Starting update…');self.changed.emit()
   return ok
  process=QProcess(self);self.job=process;process.setProgram(interpreter(self.root));process.setArguments(args)
  self.job_action=action
  process.finished.connect(self.finished);process.errorOccurred.connect(self.error)
  self.deadline=QTimer(process);self.deadline.setSingleShot(True);self.deadline.setInterval(15*60*1000);self.deadline.timeout.connect(process.kill)
  process.start();self.deadline.start();self.changed.emit();return True
 def error(self,*_):self.finished(-1)
 def finished(self,*_):
  process=self.job
  if process is None:return
  self.job=None
  raw=bytes(process.readAllStandardOutput())
  try:response=json.loads(raw)
  except ValueError:response={'ok':False,'error':'Update worker could not complete'}
  process.deleteLater();self.read()
  if response.get('ok') and self.job_action=='mode':QTimer.singleShot(0,self.background)
  if not response.get('ok'):
   self.state.update(status=response.get('error','Update failed'),attention=True,failure=True,busy=False)
   if not self.state.get('transaction'):
    try:
     path=self.folder/'state-ui-failure.tmp';path.write_text(json.dumps(self.state),'utf-8');os.replace(path,self.folder/'state.json')
    except OSError:pass
   self.changed.emit()
 def install(self):return self.launch('install',detached=True)
