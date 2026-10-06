"""Installed shell entry; no console, external Python or resident installer."""
import argparse,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(Path(__file__).resolve().parent))
from omni_layout import user_root,child_environment,runtime_python
from engine import WindowsLifecycle,Updater
def main():
 p=argparse.ArgumentParser();p.add_argument('--start',action='store_true');p.add_argument('--stop',action='store_true');p.add_argument('--time',action='store_true');p.add_argument('--weather',action='store_true');p.add_argument('--updates',action='store_true');p.add_argument('--locations',action='store_true');a=p.parse_args()
 data=user_root(ROOT);os.environ.update(child_environment(ROOT,data))
 life=WindowsLifecycle(ROOT)
 if a.stop:life.prepare();life.stop();return
 if a.time or a.weather or a.locations:
  name='time' if a.time else 'weather'
  subprocess.Popen([str(runtime_python(ROOT).with_name('pythonw.exe')),str(ROOT/(name+'-center/app/main.py')),'--locations' if a.locations else '--toggle'],
   env=child_environment(ROOT,data),creationflags=subprocess.CREATE_NO_WINDOW);return
 state=Updater(ROOT)
 if state.state.get('transaction'):state.recover()
 elif state.state.get('mode')=='automatic' and state.state.get('staged_version') and not state.state.get('failure'):state.apply(True)
 else:
  life.expected={'time':True,'weather':True};life.start()
  if not life.health():raise RuntimeError('Omni Taskbar could not start; run setup to repair it')
 # Manual launch also starts the same mutex-protected watchdog. Login's own
 # registration may already own it; a duplicate exits without supervising.
 subprocess.Popen([str(runtime_python(ROOT).with_name('pythonw.exe')),str(ROOT/'shell-updater/watchdog_host.py')],env=child_environment(ROOT,data),creationflags=subprocess.CREATE_NO_WINDOW)
if __name__=='__main__':
 try:main()
 except Exception as exc:
  import ctypes
  ctypes.windll.user32.MessageBoxW(None,'Omni Taskbar could not start. Run the installer to repair it.','Omni Taskbar',0x10)
  raise
