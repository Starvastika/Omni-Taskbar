"""Trusted embedded setup helper. User data never enters program replacement."""
import argparse,contextlib,hashlib,json,os,shutil,subprocess,sys,time,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
sys.path.insert(0,str(Path(__file__).resolve().parent))
from omni_layout import child_environment
from engine import atomic,read,WindowsLifecycle,Updater,semver
PRODUCT='Omni Taskbar'
def checked_path(value):
 p=Path(value).absolute()
 for item in (p,*p.parents):
  if item.is_symlink() or item.is_junction():raise ValueError('Reparse point in installation path')
 return p.resolve()
def ownership(root,data,required=False):
 root=checked_path(root);data=checked_path(data)
 if root==data or root.is_relative_to(data) or data.is_relative_to(root):raise ValueError('Program and user data must be separate')
 marker=read(root/'omni-installed.json');owner=read(data/'.omni-owner.json')
 if marker:
  if marker.get('product')!=PRODUCT or Path(marker.get('user_root','')).resolve()!=data:raise ValueError('Installation ownership mismatch')
  if not owner or owner.get('product')!=PRODUCT or owner.get('id')!=marker.get('id') or Path(owner.get('program_root','')).resolve()!=root:raise ValueError('Data ownership mismatch')
 elif required:raise ValueError('Owned installation required')
 return root,data

def verify(root):
 root=Path(root);inventory=read(root/'installation-files.json')
 if inventory.get('product')!=PRODUCT:raise ValueError('Installer inventory missing')
 for name,digest in inventory['files'].items():
  target=root/name
  if not target.resolve().is_relative_to(root.resolve()) or target.is_symlink() or target.is_junction():raise ValueError('Unsafe installed path')
  if hashlib.sha256(target.read_bytes()).hexdigest()!=digest:raise ValueError('Installed file verification failed: '+name)
 return inventory
def configure(root,data,mode):
 root,data=ownership(root,data);data.mkdir(parents=True,exist_ok=True)
 marker=read(root/'omni-installed.json');owner=read(data/'.omni-owner.json')
 if owner and owner.get('product')!=PRODUCT:raise ValueError('User directory belongs to another product')
 token=owner.get('id') or str(uuid.uuid4())
 atomic(root/'omni-installed.json',{'product':PRODUCT,'id':token,'user_root':str(data)})
 atomic(data/'.omni-owner.json',{'product':PRODUCT,'id':token,'program_root':str(root)})
 os.environ.update(child_environment(root,data))
 if not (data/'config.yaml').exists():
  value=(root/'distribution/defaults/config.yaml').read_text('utf-8').replace('{install_root}',str(root))
  (data/'config.yaml').write_text(value,'utf-8')
 if not (data/'styles.css').exists():shutil.copy2(root/'distribution/defaults/styles.css',data/'styles.css')
 (data/'helpers').mkdir(exist_ok=True)
 python=root/'runtime/python/python.exe';atomic(data/'helpers/runtime-settings.json',{'python':str(python)})
 settings={'LhmTask':None,'YasbCli':str(root/'.runtime/yasb-2.0.7/yasbc.exe')}
 for name,title in (('time','TimeCenter'),('weather','WeatherCenter')):
  settings[title+'Python']=str(python.with_name('pythonw.exe'));settings[title+'Script']=str(root/(name+'-center/app/main.py'));settings[title+'Pid']=str(data/(name+'-center/data/host.json'))
 atomic(data/'helpers/watchdog-settings.json',settings)
 if read(data/'shell-updater/data/manual-maintenance.json').get('exit'):
  (data/'shell-updater/data/manual-maintenance.json').unlink()
 engine=Updater(root)
 if not engine.state.get('mode'):engine.mode(mode)
 return token
def maintenance(data,owner,enabled):
 path=Path(data)/'shell-updater/data/maintenance.json'
 if enabled:atomic(path,{'owner':int(owner),'created':time.time(),'expires':time.time()+1800})
 else:
  with contextlib.suppress(FileNotFoundError):path.unlink()
def prepare(root,data,owner):
 root,data=ownership(root,data)
 marker=read(root/'omni-installed.json');existing=bool(marker)
 if data.exists() and any(data.iterdir()) and not read(data/'.omni-owner.json') and any(p.name!='shell-updater' for p in data.iterdir()):
  raise ValueError('User directory contains data not owned by Omni Taskbar')
 if root.exists() and any(root.iterdir()) and not existing:raise ValueError('Installation folder is not an owned Omni Taskbar installation')
 if existing and marker.get('product')!=PRODUCT:raise ValueError('Another product owns this folder')
 os.environ.update(child_environment(root,data));maintenance(data,owner,True)
 backup=data/'shell-updater/data/installer-rollback'
 if backup.exists():
  assert backup.resolve().is_relative_to(data);shutil.rmtree(backup)
 journal={'existing':existing,'files':[],'previous':read(root/'version.json').get('version'),'mode':read(data/'shell-updater/data/state.json').get('mode'),'manual_previous':read(data/'shell-updater/data/manual-maintenance.json'),'watchdog_running':bool(read(data/'helpers/watchdog-host.json').get('pid'))}
 if existing:
  atomic(data/'shell-updater/data/manual-maintenance.json',{'manual':True,'exit':True})
  life=WindowsLifecycle(root);life.prepare();journal['expected']=life.expected.copy();journal['yasb_running']=life.running();life.stop()
  deadline=time.monotonic()+26
  while life.running(runtime=True) and time.monotonic()<deadline:time.sleep(.2)
  if life.running(runtime=True):raise RuntimeError('Owned embedded runtime is still in use; close its applications before repair')
  for p in root.rglob('*'):
   if not p.is_file() or p.name.startswith('unins') or p.name in ('omni-installed.json',):continue
   if p.is_symlink() or p.is_junction():raise ValueError('Unsafe existing program file')
   name=p.relative_to(root);target=backup/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target);journal['files'].append(name.as_posix())
  for name in ('config.yaml','styles.css'):
   if (data/name).exists():(backup/'@user').mkdir(exist_ok=True);shutil.copy2(data/name,backup/'@user'/name)
 atomic(data/'shell-updater/data/installer-journal.json',journal)
def restore_manual(data,journal):
 path=Path(data)/'shell-updater/data/manual-maintenance.json'
 if journal.get('manual_previous'):atomic(path,journal['manual_previous'])
 else:
  with contextlib.suppress(FileNotFoundError):path.unlink()

def rollback(root,data):
 root=Path(root);data=Path(data);journal=read(data/'shell-updater/data/installer-journal.json');backup=data/'shell-updater/data/installer-rollback'
 if journal.get('existing'):
  life=WindowsLifecycle(root)
  with contextlib.suppress(Exception):life.prepare();life.stop()
  current=read(root/'installation-files.json').get('files',{})
  for name in set(current)-set(journal['files']):
   target=root/name
   if target.resolve().is_relative_to(root.resolve()) and target.is_file():target.unlink()
  for name in journal['files']:
   target=root/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(backup/name,target)
  for name in ('config.yaml','styles.css'):
   if (backup/'@user'/name).exists():shutil.copy2(backup/'@user'/name,data/name)
  restore_manual(data,journal)
  if journal.get('watchdog_running'):register(root,data,start_now=True)
  if journal.get('yasb_running') or any(journal.get('expected',{}).values()):
   life.expected=journal.get('expected',{});life.start()
 else:
  life=WindowsLifecycle(root)
  with contextlib.suppress(Exception):life.prepare();life.stop()
  from native_taskbar import restore_native_cutover
  restore_native_cutover(root,data)

def finish(root,data,mode,owner,launch=True,startup=True):
 root,data=ownership(root,data)
 try:
  verify(root)
  previous=read(data/'shell-updater/data/installer-journal.json').get('previous')
  if previous and semver(read(root/'version.json')['version'])<semver(previous):raise ValueError('Use the same or newer installer to preserve migration compatibility')
  # Remove only obsolete owned release files, never unknown/custom program files.
  old=read(data/'shell-updater/data/installer-rollback/installation-files.json').get('files',{})
  new=read(root/'installation-files.json')['files']
  for name,digest in old.items():
   if name in new:continue
   target=root/name
   if checked_path(target).is_relative_to(root) and target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest()==digest:target.unlink()
  configure(root,data,mode)
  # Trusted shipped migrations only after complete inventory validation.
  sys.path.insert(0,str(root/'runtime/python/site-packages'));sys.path.insert(0,str(root/'shell-updater'))
  journal=read(data/'shell-updater/data/installer-journal.json')
  from migrations import migrate
  migrate(root,journal.get('previous') or read(root/'version.json')['version'],read(root/'version.json')['version'],data)
  if launch:
   life=WindowsLifecycle(root);life.expected={'time':True,'weather':True};life.start()
   if not life.health():raise RuntimeError('New shell health failed')
  restore_manual(data,journal)
  if startup:register(root,data,start_now=launch or bool(journal.get('watchdog_running')))
  # One rollback set only; discard successful setup copies, never user state.
  backup=data/'shell-updater/data/installer-rollback'
  if backup.exists():shutil.rmtree(backup)
  with contextlib.suppress(FileNotFoundError):(data/'shell-updater/data/installer-journal.json').unlink()
 except Exception:
  rollback(root,data);raise
 finally:maintenance(data,owner,False)

def register(root,data,start_now=True):
 # One owning registration; never replace the live developer watchdog.
 import winreg
 name='Omni Taskbar'
 with winreg.CreateKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\CurrentVersion\Run') as key:
  winreg.SetValueEx(key,name,0,winreg.REG_SZ,'"'+str(Path(root)/'Omni-Taskbar.exe')+'" --start')
 python=Path(root)/'runtime/python/pythonw.exe';script=Path(root)/'shell-updater/watchdog_host.py'
 # Per-user fallback directly hosts the same watchdog/mutex without an extra process.
 with winreg.CreateKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\CurrentVersion\Run') as key:
  winreg.SetValueEx(key,'Omni Taskbar Watchdog',0,winreg.REG_SZ,'"'+str(python)+'" "'+str(script)+'"')
 if start_now:subprocess.Popen([str(python),str(script)],env=child_environment(root,data),creationflags=subprocess.CREATE_NO_WINDOW)
def uninstall(root,data,remove=False,startup=True):
 root,data=ownership(root,data,True);marker=read(root/'omni-installed.json');owner=read(data/'.omni-owner.json')
 if marker.get('product')!=PRODUCT or owner.get('id')!=marker.get('id') or Path(owner.get('program_root','')).resolve()!=root:raise ValueError('Uninstall ownership could not be verified')
 atomic(data/'shell-updater/data/manual-maintenance.json',{'manual':True,'exit':True})
 life=WindowsLifecycle(root);os.environ.update(child_environment(root,data))
 life.prepare();life.stop()
 deadline=time.monotonic()+26
 while life.running(runtime=True) and time.monotonic()<deadline:time.sleep(.2)
 if life.running(runtime=True):raise RuntimeError('Owned runtime did not exit; uninstall preserved files')
 from native_taskbar import restore_native_cutover
 restore_native_cutover(root,data)
 if startup:
  import winreg
  with winreg.CreateKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\CurrentVersion\Run') as key:
   for name in ('Omni Taskbar','Omni Taskbar Watchdog'):
    try:
     value,_=winreg.QueryValueEx(key,name)
     if str(root).casefold() in value.casefold():winreg.DeleteValue(key,name)
    except FileNotFoundError:pass
 # Remove updater-added source/assets too; Inno owns the original fixed image.
 # An unexpected/customized file is preserved rather than recursively deleted.
 checker=Updater(root);installed_files=read(root/'installation-files.json').get('files',{})
 for name,digest in installed_files.items():
  if not checker.shipped(name):continue
  target=checker.destination(name)
  if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest()==digest:target.unlink()
 with contextlib.suppress(FileNotFoundError):(root/'installation-files.json').unlink()
 # Remove only generated bytecode alongside inventoried program modules.
 parents={ (root/name).parent for name in installed_files if name.endswith('.py') }
 for parent in parents:
  cache=parent/'__pycache__'
  if cache.exists():
   checked_path(cache)
   for bytecode in cache.glob('*.pyc'):bytecode.unlink()
   with contextlib.suppress(OSError):cache.rmdir()
 # The owner marker authorizes only this product data directory.
 if remove:
  if data==root or data in Path.home().resolve().parents or data==Path.home().resolve() or data.parent==data or not data.name:raise ValueError('Unsafe data removal root')
  shutil.rmtree(data)
def main():
 p=argparse.ArgumentParser();p.add_argument('action',choices=('prepare','finish','uninstall','verify'));p.add_argument('--root',required=True);p.add_argument('--data');p.add_argument('--owner',type=int,default=os.getppid());p.add_argument('--mode',choices=('automatic','check','manual'),default='check');p.add_argument('--no-launch',action='store_true');p.add_argument('--no-startup',action='store_true');p.add_argument('--remove-data',action='store_true');a=p.parse_args()
 a.data=a.data or read(Path(a.root)/'omni-installed.json').get('user_root')
 if not a.data:return 1
 os.environ.update(child_environment(a.root,a.data))
 try:
  if a.action=='prepare':prepare(a.root,a.data,a.owner)
  elif a.action=='finish':finish(a.root,a.data,a.mode,a.owner,not a.no_launch,not a.no_startup)
  elif a.action=='uninstall':uninstall(a.root,a.data,a.remove_data,not a.no_startup)
  else:verify(a.root)
  return 0
 except Exception as exc:
  maintenance(a.data,a.owner,False)
  # Bounded private diagnostic, never credentials/user-state contents.
  atomic(Path(a.data)/'shell-updater/data/installer-error.json',{'error':type(exc).__name__,'message':str(exc)[:400]});return 1
if __name__=='__main__':raise SystemExit(main())
