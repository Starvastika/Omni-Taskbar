"""Clean-desktop CI gate for the real native bars/companion/watchdog startup."""
import argparse,json,os,sys,time,winreg
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--program',required=True);p.add_argument('--data',required=True);a=p.parse_args();root=Path(a.program).resolve();data=Path(a.data).resolve()
if os.environ.get('GITHUB_ACTIONS')!='true' and os.environ.get('OMNI_ISOLATED_DESKTOP')!='1':raise RuntimeError('Clean isolated desktop required')
sys.path[:0]=[str(root),str(root/'shell-updater')]
from engine import WindowsLifecycle,atomic,read
from omni_layout import child_environment
os.environ.update(child_environment(root,data));life=WindowsLifecycle(root);life.expected={'time':True,'weather':True}
life.start()
from installer_backend import register
register(root,data)
assert life.health(),'Two native bars and companion IPC must actually become healthy'
with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\CurrentVersion\Run') as key:
 for name in ('Omni Taskbar','Omni Taskbar Watchdog'):assert str(root).casefold() in winreg.QueryValueEx(key,name)[0].casefold()
# The installed watchdog, not a second test daemon, must report its own identity.
end=time.monotonic()+30
while time.monotonic()<end:
 log=data/'helpers/watchdog.log'
 if log.exists() and 'Watchdog started' in log.read_text('utf-8',errors='replace'):break
 time.sleep(.5)
else:raise RuntimeError('Installed watchdog did not start')
atomic(data/'shell-updater/data/manual-maintenance.json',{'manual':True})
life.prepare();life.stop()
print('Real native two-bar startup, companion IPC, owned autostart and watchdog passed')
# Physical fullscreen/Snap, tray/virtual desktop UI and app menus require the
# separately recorded interactive release matrix; this gate does not claim them.
