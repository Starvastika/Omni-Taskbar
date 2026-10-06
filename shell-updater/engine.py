"""Release-only updater. Standard library; never imported onto the GUI thread."""
from __future__ import annotations
import contextlib,datetime as dt,hashlib,json,os,re,shutil,stat,subprocess,sys,time,urllib.error,urllib.parse,urllib.request,uuid,zipfile
from pathlib import Path,PurePosixPath
MODES=('automatic','check','manual')
MAX_DOWNLOAD=768*1024*1024
MAX_EXPANDED=1536*1024*1024
FORBIDDEN={'data','cache','weather-cache','logs','exports','.git','.venv','__pycache__','stable-v1','.validation'}

def atomic(path,value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
 try:
  with temp.open('w',encoding='utf-8') as stream:json.dump(value,stream,indent=2,ensure_ascii=True,allow_nan=False);stream.flush();os.fsync(stream.fileno())
  os.replace(temp,path)
 finally:
  with contextlib.suppress(FileNotFoundError):temp.unlink()
def read(path,default=None):
 try:return json.loads(Path(path).read_text('utf-8'))
 except FileNotFoundError:return {} if default is None else default
def semver(value):
 if not isinstance(value,str) or not re.fullmatch(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)',value):raise ValueError('Invalid stable semantic version')
 return tuple(map(int,value.split('.')))
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as stream:
  for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()
def safe_name(name):
 if not isinstance(name,str) or not name or '\\' in name or ':' in name or '\0' in name:raise ValueError('Unsafe package path')
 p=PurePosixPath(name)
 if p.is_absolute() or any(x in ('','..','.') for x in name.split('/')):raise ValueError('Unsafe package path')
 if any(x.casefold() in FORBIDDEN for x in p.parts):raise ValueError('Personal/runtime data in package')
 if any(x.rstrip(' .')!=x or x.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(1,10)),*(f'LPT{i}' for i in range(1,10))} for x in p.parts):raise ValueError('Unsafe Windows filename')
 return p.as_posix()
def validate_manifest(value):
 if not isinstance(value,dict):raise ValueError('Invalid release manifest')
 semver(value.get('version'));semver(value.get('minimum_updater_version'))
 if value.get('channel')!='stable' or value.get('requires_windows_restart') is not False:raise ValueError('Unsupported release policy')
 if not re.fullmatch(r'[a-f0-9]{64}',str(value.get('sha256',''))):raise ValueError('Missing release checksum')
 if value.get('asset')!=f"yasb-shell-{value['version']}.zip":raise ValueError('Release asset/version mismatch')
 if value.get('requires_shell_restart') is not True:raise ValueError('Unsupported restart policy')
 return value

class Network:
 def __init__(self,opener=None):self.opener=opener or urllib.request.urlopen
 def get(self,url,limit=4*1024*1024,etag=None):
  if urllib.parse.urlsplit(url).scheme!='https':raise ValueError('HTTPS required')
  headers={'User-Agent':'YASB-Shell-Updater/1','Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'}
  if etag:headers['If-None-Match']=etag
  for attempt in range(2):
   try:
    with self.opener(urllib.request.Request(url,headers=headers),timeout=15) as reply:
     if urllib.parse.urlsplit(reply.geturl()).scheme!='https':raise ValueError('Insecure redirect')
     body=reply.read(limit+1)
     if len(body)>limit:raise ValueError('Response exceeds limit')
     return body,reply.headers.get('ETag','')
   except urllib.error.HTTPError as exc:
    code=exc.code;exc.close()
    if code==304:return None,etag or ''
    if code not in (429,500,502,503,504) or attempt:raise
   except (TimeoutError,urllib.error.URLError):
    if attempt:raise
   time.sleep(.4)
  raise OSError('Network unavailable')
 def download(self,url,path):
  if urllib.parse.urlsplit(url).scheme!='https':raise ValueError('HTTPS required')
  with self.opener(urllib.request.Request(url,headers={'User-Agent':'YASB-Shell-Updater/1'}),timeout=20) as reply,Path(path).open('wb') as stream:
   if urllib.parse.urlsplit(reply.geturl()).scheme!='https':raise ValueError('Insecure redirect')
   count=0;deadline=time.monotonic()+300
   while chunk:=reply.read(1024*1024):
    count+=len(chunk)
    if count>MAX_DOWNLOAD or time.monotonic()>deadline:raise ValueError('Download exceeds size/time limit')
    stream.write(chunk)
   stream.flush();os.fsync(stream.fileno())

class Updater:
 def __init__(self,root,network=None,lifecycle=None):
  self.root=Path(root).resolve();self.data=self.root/'shell-updater/data';self.data.mkdir(parents=True,exist_ok=True)
  self.network=network or Network();self.lifecycle=lifecycle or WindowsLifecycle(self.root)
  self.version=read(self.root/'version.json');semver(self.version['version'])
  self.state=read(self.data/'state.json',{'mode':None,'status':'Choose an update mode','attention':False,'last_checked':0})
  self.state['current_version']=self.version['version']
 def save(self):atomic(self.data/'state.json',self.state)
 def log(self,event):
  path=self.data/'updater.log'
  if path.exists() and path.stat().st_size>65536:os.replace(path,path.with_suffix('.log.old'))
  with path.open('a',encoding='utf-8') as stream:stream.write(dt.datetime.now(dt.UTC).isoformat()+' '+event+'\n')
 def repository(self):
  value=self.version.get('repository')
  if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',value):raise ValueError('GitHub release repository has not been configured')
  return value
 def mode(self,value):
  if value not in MODES:raise ValueError('Unknown update mode')
  self.state['mode']=value;self.save()
  if value=='automatic' and self.state.get('available') and not self.state.get('staged_version') and self.state.get('latest_version')!=self.state.get('failed_version'):return self.stage()
  return self.state
 def check(self,manual=False):
  if not manual:
   if self.state.get('mode') not in ('automatic','check'):return self.state
   if time.time()-self.state.get('last_checked',0)<max(6*3600,self.state.get('backoff_seconds',0)):return self.state
  try:
   repo=self.repository();base=f'https://api.github.com/repos/{repo}/releases/latest'
   body,etag=self.network.get(base,etag=self.state.get('etag'))
   if body is None:release=self.state.get('release')
   else:release=json.loads(body)
   if not isinstance(release,dict) or release.get('draft') or release.get('prerelease'):raise ValueError('No stable release')
   assets=release.get('assets',[])
   def asset(name):
    found=[x for x in assets if x.get('name')==name]
    if len(found)!=1:raise ValueError('Release asset missing or ambiguous')
    url=found[0].get('browser_download_url','')
    expected=f'https://github.com/{repo}/releases/download/'
    if not url.startswith(expected):raise ValueError('Asset outside configured repository')
    return url
   raw,_=self.network.get(asset('release-manifest.json'),limit=65536);manifest=validate_manifest(json.loads(raw))
   if release.get('tag_name')!='v'+manifest['version']:raise ValueError('Release tag/version mismatch')
   if semver(manifest['minimum_updater_version'])>semver(self.version['updater_version']):raise ValueError('This release requires a newer updater')
   available=semver(manifest['version'])>semver(self.version['version'])
   self.state.update({'last_checked':time.time(),'etag':etag,'release':release,'latest_version':manifest['version'],'manifest':manifest,
                      'download_url':asset(manifest['asset']),'notes':str(release.get('body') or '')[:100000],
                      'available':available,'backoff_seconds':0})
   self.state['attention']=bool(available or self.state.get('staged_version') or self.state.get('failure'))
   self.state['status']=f"Version {manifest['version']} is available" if available else "You're up to date"
   self.log('check available' if available else 'check current');self.save()
   if available and self.state.get('mode')=='automatic' and manifest['version']!=self.state.get('failed_version'):return self.stage()
  except Exception as exc:
   self.state.update({'last_checked':time.time(),'backoff_seconds':min(86400,max(21600,self.state.get('backoff_seconds',10800)*2)),
                      'status':"Couldn't check for updates",'error':type(exc).__name__+': '+str(exc)[:240]})
   self.log('check failed '+type(exc).__name__);self.save()
  return self.state
 def stage(self):
  manifest=validate_manifest(self.state.get('manifest'))
  if semver(manifest['version'])<=semver(self.version['version']):raise ValueError('Release is not newer')
  temp=self.data/('download-'+uuid.uuid4().hex+'.zip');candidate=self.data/('candidate-'+uuid.uuid4().hex)
  try:
   self.state.update(status='Downloading '+manifest['version'],busy=True);self.save();self.log('download')
   self.network.download(self.state['download_url'],temp)
   if sha(temp)!=manifest['sha256']:raise ValueError('Checksum mismatch')
   inventory=self.extract(temp,candidate,manifest['version']);self.log('verified')
   staging=self.data/'staged'
   if staging.exists():shutil.rmtree(staging)
   os.replace(candidate,staging)
   self.state.update({'status':manifest['version']+' is ready to install','staged_version':manifest['version'],
                      'staged_manifest':manifest,'staged_inventory':inventory,'requires_restart':True,'attention':True,'busy':False,'failure':False})
   self.save();self.log('staged')
  except Exception as exc:
   self.fail('Update could not be staged',exc)
  finally:
   with contextlib.suppress(FileNotFoundError):temp.unlink()
   if candidate.exists():shutil.rmtree(candidate)
  return self.state
 def extract(self,archive,target,version):
  target=Path(target);target.mkdir(parents=True)
  with zipfile.ZipFile(archive) as package:
   entries=package.infolist();names=[];size=0
   for item in entries:
    if item.is_dir():continue
    name=safe_name(item.filename);names.append(name.casefold());size+=item.file_size
    if stat.S_ISLNK(item.external_attr>>16):raise ValueError('Symlink in package')
    if item.flag_bits&1:raise ValueError('Encrypted archive')
   if len(names)!=len(set(names)) or len(names)>12000 or size>MAX_EXPANDED:raise ValueError('Invalid package size/duplicates')
   inventory=json.loads(package.read('package-files.json'))
   if not isinstance(inventory,dict) or inventory.get('version')!=version or not isinstance(inventory.get('files'),dict):raise ValueError('Invalid package inventory')
   if set(names)!={n.casefold() for n in inventory['files']}|{'package-files.json'}:raise ValueError('Unlisted package content')
   for name,digest in inventory['files'].items():
    name=safe_name(name);content=package.read(name)
    if hashlib.sha256(content).hexdigest()!=digest:raise ValueError('Package file checksum mismatch')
    destination=target/name;destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(content)
   (target/'package-files.json').write_text(json.dumps(inventory),'utf-8')
   meta=read(target/'version.json')
   if meta.get('version')!=version:raise ValueError('Package version mismatch')
   self.validate_inventory(inventory)
   self.validate_code(target,inventory)
  return inventory
 def validate_inventory(self,inventory):
  for name in inventory['files']:
   safe_name(name)
   if not self.shipped(name):raise ValueError('Package attempts to replace user configuration or unowned files')
 def validate_code(self,folder,inventory):
  for name in inventory['files']:
   if name.endswith('.py'):compile((folder/name).read_text('utf-8'),name,'exec')
  library=folder/'.runtime/yasb-2.0.7/lib/library.zip'
  if library.exists():
   import importlib.util
   with zipfile.ZipFile(library) as archive:
    for name in ('core/bar.pyc','core/topbar_hover.pyc','core/widgets/yasb/open_meteo.pyc','core/widgets/yasb/power_menu.pyc'):
     if archive.read(name)[:4]!=importlib.util.MAGIC_NUMBER:raise ValueError('Runtime bytecode ABI mismatch')
    if archive.testzip() is not None:raise ValueError('Runtime archive damaged')
 def shipped(self,name):
  if name in ('version.json','CHANGELOG.md','README.md','THIRD_PARTY_NOTICES.md'):return True
  if name=='.runtime/yasb-2.0.7/lib/library.zip':return True
  if name.startswith(('weather-center/app/','weather-center/services/','weather-center/qml/','weather-center/assets/','weather-center/vendor/',
                      'time-center/app/','time-center/services/','time-center/qml/','time-center/map/',
                      'shell-updater/','distribution/defaults/','distribution/licenses/','helpers/application_command_bar/','helpers/active_app_center/')):
   return not name.endswith(('.log','.pyc','.tmp')) and 'tests' not in PurePosixPath(name).parts
  return name in ('helpers/yasb-watchdog.ps1','helpers/watchdog-maintenance.ps1','weather-center/toggle.vbs','weather-center/toggle.ps1',
                  'time-center/toggle.vbs','time-center/requirements.txt','distribution/register-startup.ps1','distribution/uninstall.ps1',
                  'weather-center/Launcher.exe','weather-center/Launcher.cpp','weather-center/build-launcher.ps1','distribution/runtime-base.json')
 def verify_stage(self):
  folder=self.data/'staged';inventory=read(folder/'package-files.json');version=self.state.get('staged_version')
  if inventory.get('version')!=version or not version:raise ValueError('Incomplete staged update')
  self.validate_inventory(inventory)
  for name,digest in inventory['files'].items():
   if sha(folder/name)!=digest:raise ValueError('Staged file damaged')
  if read(folder/'version.json').get('version')!=version:raise ValueError('Staged version mismatch')
  return folder,inventory
 def fail(self,status,exc):
  self.state.update({'status':status,'error':type(exc).__name__+': '+str(exc)[:240],'attention':True,'failure':True,'busy':False})
  self.save();self.log('failure '+type(exc).__name__)
 def destination(self,name):
  target=self.root/name
  if target.is_symlink() or any(p.is_symlink() for p in target.parents if p!=self.root.parent):raise ValueError('Symlink/reparse destination')
  if not target.resolve().is_relative_to(self.root):raise ValueError('Destination outside installation')
  return target
 def replace(self,source,target):
  target=Path(target);target.parent.mkdir(parents=True,exist_ok=True);temp=target.with_name(target.name+'.update-tmp')
  try:shutil.copy2(source,temp);os.replace(temp,target)
  finally:
   with contextlib.suppress(FileNotFoundError):temp.unlink()
 def migrate(self,old,new):
  # Versioned additive migrations preserve unknown options; never replace live config.
  from migrations import migrate
  migrate(self.root,old,new)
 def apply(self,natural=False):
  if natural and self.state.get('mode')!='automatic':return self.state
  if self.state.get('failure') or self.state.get('transaction'):
   # A journal is recovered, never blindly re-applied in a restart loop.
   if self.state.get('transaction'):return self.recover()
   return self.state
  try:folder,inventory=self.verify_stage()
  except Exception as exc:self.fail('Staged update is incomplete',exc);return self.state
  previous=self.version['version'];new=inventory['version'];backup=self.data/'rollback'/uuid.uuid4().hex;backup.mkdir(parents=True)
  records={}
  try:
   if hasattr(self.lifecycle,'prepare'):self.lifecycle.prepare()
   shutil.copy2(Path(__file__),self.data/'recovery_runner.py')
   # Journal/lease precede stopping anything. Crash recovery can restore each copied file.
   self.state.update({'transaction':{'backup':str(backup.relative_to(self.data)),'records':records,'previous':previous,'target':new,'expected':getattr(self.lifecycle,'expected',{})},
                      'status':'Installing '+new,'attention':True,'busy':True,'recovery_attempted':False});self.save()
   self.maintenance(True);self.lifecycle.stop()
   for name in list(inventory['files'])+['config.yaml','styles.css','shell-updater/data/migrations.json']:
    target=self.destination(name);existed=target.exists()
    if existed:(backup/name).parent.mkdir(parents=True,exist_ok=True);shutil.copy2(target,backup/name)
    records[name]=existed
    # Persist the restoration record before replacing this file.
    self.state['transaction']['records']=records;self.save()
    if name in inventory['files']:self.replace(folder/name,target)
   self.migrate(previous,new);self.log('migration complete');self.lifecycle.start()
   if not self.lifecycle.health():raise RuntimeError('New shell failed health check')
   self.version=read(self.root/'version.json')
   self.state['last_success']={**self.state['transaction'],'installed_at':time.time()}
   self.state.update({'current_version':new,'available':False,'staged_version':None,'requires_restart':False,'attention':False,'failure':False,
                      'status':'Updated to '+new,'last_update_result':'success','rollback_version':previous,'busy':False})
   self.state.pop('transaction',None);self.save();self.log('health success')
   shutil.rmtree(folder);self.prune_backups(backup)
  except Exception as exc:
   self.log('apply failed '+type(exc).__name__)
   if self.state.get('transaction'):self.rollback(exc)
   else:self.fail('Update failed before apply',exc)
  finally:self.maintenance(False)
  return self.state
 def maintenance(self,enabled):
  path=self.data/'maintenance.json'
  if enabled:atomic(path,{'owner':os.getpid(),'created':time.time(),'expires':time.time()+1200})
  else:
   with contextlib.suppress(FileNotFoundError):path.unlink()
 def rollback(self,cause):
  transaction=self.state['transaction'];backup=(self.data/transaction['backup']).resolve()
  if not backup.is_relative_to(self.data/'rollback'):raise ValueError('Invalid rollback journal')
  if hasattr(self.lifecycle,'expected'):self.lifecycle.expected=transaction.get('expected',{})
  self.lifecycle.stop()
  for name,existed in reversed(list(transaction['records'].items())):
   target=self.destination(name)
   if existed:self.replace(backup/name,target)
   else:
    with contextlib.suppress(FileNotFoundError):target.unlink()
  self.lifecycle.start();healthy=self.lifecycle.health();previous=transaction['previous']
  self.state.pop('transaction',None)
  self.state.update({'current_version':previous,'last_update_result':'rolled_back' if healthy else 'rollback_needs_attention',
                    'failed_version':transaction['target'],
                    'staged_version':None,'requires_restart':False,'busy':False,'failure':True,'attention':True,
                    'status':('Update failed. Restored '+previous) if healthy else 'Rollback restored files; shell needs attention',
                    'error':type(cause).__name__+': '+str(cause)[:240]})
  self.save();self.log('rollback healthy' if healthy else 'rollback health failed')
 def recover(self):
  self.state['recovery_attempted']=True;self.save()
  self.maintenance(True)
  try:self.rollback(RuntimeError('Interrupted update recovered from journal'))
  finally:self.maintenance(False)
  return self.state
 def rollback_recent(self):
  previous=self.state.get('last_success')
  if not previous or self.state.get('failure') or time.time()-previous.get('installed_at',0)>600 or previous.get('target')!=self.version['version']:
   return self.state
  self.state['transaction']=previous;self.save();self.maintenance(True)
  try:self.rollback(RuntimeError('Repeated shell startup crashes after update'))
  finally:self.maintenance(False)
  return self.state
 def prune_backups(self,keep):
  folder=self.data/'rollback'
  for p in folder.iterdir():
   if p!=keep and p.is_dir():shutil.rmtree(p)

class WindowsLifecycle:
 def __init__(self,root):self.root=Path(root);self.expected={};self.log_offset=0
 def run(self,args,timeout=10):
  return subprocess.run(args,timeout=timeout,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),capture_output=True,encoding='utf-8',env=dict(os.environ,PYTHONIOENCODING='utf-8'))
 def python(self):
  config=read(self.root/'helpers/runtime-settings.json')
  return config.get('python') or sys.executable
 def status(self,name):
  try:
   r=self.run([self.python(),str(self.root/(name+'-center/app/main.py')),'--status'],5)
   return json.loads(r.stdout)
  except (OSError,ValueError,subprocess.TimeoutExpired):return {}
 def prepare(self):self.expected={name:bool(self.status(name).get('running')) for name in ('time','weather')}
 def stop(self):
  cli=self.root/'.runtime/yasb-2.0.7/yasbc.exe'
  if not self.expected:self.expected={name:bool(self.status(name).get('running')) for name in ('time','weather')}
  self.run([str(cli),'stop'])
  for name in ('time','weather'):
   if self.expected.get(name):self.run([self.python(),str(self.root/(name+'-center/app/main.py')),'--quit'],5)
  deadline=time.monotonic()+10
  while time.monotonic()<deadline:
   if not self.running() and all(not self.status(name).get('running') for name in self.expected if self.expected[name]):return
   time.sleep(.2)
  raise RuntimeError('Shell components did not exit cleanly')
 def start(self):
  log=self.root/'yasb.log';self.log_offset=log.stat().st_size if log.exists() else 0
  self.run([str(self.root/'.runtime/yasb-2.0.7/yasbc.exe'),'start'])
  for name,expected in self.expected.items():
   if expected:
    subprocess.Popen([self.python().replace('python.exe','pythonw.exe'),str(self.root/(name+'-center/app/main.py'))],
                     cwd=self.root,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 def running(self):
  import ctypes
  from ctypes import wintypes as W
  k=ctypes.windll.kernel32
  class Entry(ctypes.Structure):
   _fields_=[('size',W.DWORD),('usage',W.DWORD),('pid',W.DWORD),('heap',ctypes.c_size_t),('module',W.DWORD),('threads',W.DWORD),('parent',W.DWORD),('priority',W.LONG),('flags',W.DWORD),('exe',W.WCHAR*260)]
  k.CreateToolhelp32Snapshot.argtypes=[W.DWORD,W.DWORD];k.CreateToolhelp32Snapshot.restype=W.HANDLE
  k.Process32FirstW.argtypes=[W.HANDLE,ctypes.POINTER(Entry)];k.Process32NextW.argtypes=[W.HANDLE,ctypes.POINTER(Entry)]
  k.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];k.OpenProcess.restype=W.HANDLE
  k.QueryFullProcessImageNameW.argtypes=[W.HANDLE,W.DWORD,W.LPWSTR,ctypes.POINTER(W.DWORD)];k.CloseHandle.argtypes=[W.HANDLE]
  handle=k.CreateToolhelp32Snapshot(2,0);entry=Entry();entry.size=ctypes.sizeof(entry);found=False
  try:
   ok=k.Process32FirstW(handle,ctypes.byref(entry))
   while ok:
    if entry.exe.casefold()=='yasb.exe':
     process=k.OpenProcess(0x1000,False,entry.pid)
     if process:
      path=ctypes.create_unicode_buffer(32768);size=W.DWORD(32768)
      try:
       if k.QueryFullProcessImageNameW(process,0,path,ctypes.byref(size)) and path.value.casefold()==str(self.root/'.runtime/yasb-2.0.7/yasb.exe').casefold():found=True
      finally:k.CloseHandle(process)
    ok=k.Process32NextW(handle,ctypes.byref(entry))
  finally:k.CloseHandle(handle)
  return found
 def bar_count(self):
  import ctypes
  from ctypes import wintypes as W
  u=ctypes.windll.user32;u.GetWindowTextW.argtypes=[W.HWND,W.LPWSTR,ctypes.c_int];u.GetWindowThreadProcessId.argtypes=[W.HWND,ctypes.POINTER(W.DWORD)]
  k=ctypes.windll.kernel32;k.OpenProcess.restype=W.HANDLE;k.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD]
  k.QueryFullProcessImageNameW.argtypes=[W.HANDLE,W.DWORD,W.LPWSTR,ctypes.POINTER(W.DWORD)];k.CloseHandle.argtypes=[W.HANDLE]
  count=[0];expected=str(self.root/'.runtime/yasb-2.0.7/yasb.exe').casefold()
  callback=ctypes.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM)
  def visit(hwnd,_):
   text=ctypes.create_unicode_buffer(256);u.GetWindowTextW(hwnd,text,256)
   if text.value!='YasbBar':return True
   pid=W.DWORD();u.GetWindowThreadProcessId(hwnd,ctypes.byref(pid));handle=k.OpenProcess(0x1000,False,pid.value)
   if handle:
    path=ctypes.create_unicode_buffer(32768);size=W.DWORD(32768)
    if k.QueryFullProcessImageNameW(handle,0,path,ctypes.byref(size)) and path.value.casefold()==expected:count[0]+=1
    k.CloseHandle(handle)
   return True
  u.EnumWindows(callback(visit),0);return count[0]
 def health(self):
  deadline=time.monotonic()+35;stable=0
  while time.monotonic()<deadline:
   log=self.root/'yasb.log'
   if log.exists():
    with log.open('rb') as stream:stream.seek(self.log_offset);new=stream.read(1024*1024).decode('utf-8',errors='replace')
    if '[ERROR]' in new or 'Traceback' in new:return False
   good=self.bar_count()>=2 and all(self.status(name).get('running') for name in self.expected if self.expected[name])
   if good:
    stable+=1
    if stable>=3:return True
   else:stable=0
   time.sleep(.6)
  return False

@contextlib.contextmanager
def lock(folder):
 Path(folder).mkdir(parents=True,exist_ok=True)
 stream=(Path(folder)/'operation.lock').open('a+b')
 try:
  if os.name=='nt':
   import msvcrt
   if stream.tell()==0:stream.write(b'0');stream.flush()
   stream.seek(0);msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
  else:
   import fcntl
   fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
  yield
 finally:stream.close()

def main():
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--root',default=str(Path.home()/'.config/yasb'));p.add_argument('--action',choices=('check','background','stage','apply','install','auto','mode','recover','post-crash-rollback'),required=True);p.add_argument('--mode',choices=MODES);a=p.parse_args()
 try:
  with lock(Path(a.root)/'shell-updater/data'):
   engine=Updater(a.root)
   if engine.state.get('busy') and not engine.state.get('transaction'):
    engine.fail('Previous update operation was interrupted',RuntimeError('Interrupted staging/check'))
   if a.action=='check':value=engine.check(True)
   elif a.action=='background':value=engine.check(False)
   elif a.action=='stage':value=engine.stage()
   elif a.action=='apply':value=engine.apply()
   elif a.action=='install':
    if engine.state.get('failure'):engine.state['failure']=False;engine.save()
    value=engine.state if engine.state.get('staged_version') else engine.stage()
    if value.get('staged_version') and not value.get('failure'):value=engine.apply()
   elif a.action=='auto':value=engine.apply(True) if engine.state.get('staged_version') or engine.state.get('transaction') else engine.check()
   elif a.action=='recover':value=engine.recover() if engine.state.get('transaction') else engine.state
   elif a.action=='post-crash-rollback':value=engine.rollback_recent()
   else:value=engine.mode(a.mode)
   if sys.stdout:print(json.dumps({'ok':True,'state':value}))
  return 0
 except Exception as exc:
  if 'engine' in locals():
   with contextlib.suppress(OSError):engine.fail('Update operation failed; needs attention',exc)
  if sys.stdout:print(json.dumps({'ok':False,'error':type(exc).__name__+': '+str(exc)[:240]}))
  return 1
if __name__=='__main__':raise SystemExit(main())
