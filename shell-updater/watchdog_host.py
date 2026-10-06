"""Console-free host of the existing four-component, bounded recovery policy."""
import ctypes as C,json,os,subprocess,sys,time
from ctypes import wintypes as W
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(Path(__file__).resolve().parent))
from omni_layout import user_root,child_environment
from engine import atomic
USER_ROOT=user_root(ROOT)
K=C.WinDLL('kernel32',use_last_error=True);A=C.WinDLL('advapi32',use_last_error=True)
def api(library,name,result,*args):
 f=getattr(library,name);f.restype=result;f.argtypes=list(args);return f
close=api(K,'CloseHandle',W.BOOL,W.HANDLE)
session=api(K,'ProcessIdToSessionId',W.BOOL,W.DWORD,C.POINTER(W.DWORD))
open_process=api(K,'OpenProcess',W.HANDLE,W.DWORD,W.BOOL,W.DWORD)
image=api(K,'QueryFullProcessImageNameW',W.BOOL,W.HANDLE,W.DWORD,W.LPWSTR,C.POINTER(W.DWORD))
times=api(K,'GetProcessTimes',W.BOOL,W.HANDLE,*([C.POINTER(W.FILETIME)]*4))
snapshot=api(K,'CreateToolhelp32Snapshot',W.HANDLE,W.DWORD,W.DWORD)
class Entry(C.Structure):
 _fields_=[('size',W.DWORD),('usage',W.DWORD),('pid',W.DWORD),('heap',C.c_size_t),('module',W.DWORD),('threads',W.DWORD),('parent',W.DWORD),('priority',W.LONG),('flags',W.DWORD),('exe',W.WCHAR*260)]
first=api(K,'Process32FirstW',W.BOOL,W.HANDLE,C.POINTER(Entry));next_process=api(K,'Process32NextW',W.BOOL,W.HANDLE,C.POINTER(Entry))
def user_sid():
 token=W.HANDLE();open_token=api(A,'OpenProcessToken',W.BOOL,W.HANDLE,W.DWORD,C.POINTER(W.HANDLE))
 get_token=api(A,'GetTokenInformation',W.BOOL,W.HANDLE,W.DWORD,C.c_void_p,W.DWORD,C.POINTER(W.DWORD))
 convert=api(A,'ConvertSidToStringSidW',W.BOOL,C.c_void_p,C.POINTER(W.LPWSTR))
 if not open_token(W.HANDLE(-1),8,C.byref(token)):raise C.WinError(C.get_last_error())
 try:
  size=W.DWORD();get_token(token,1,None,0,C.byref(size));buffer=C.create_string_buffer(size.value)
  if not get_token(token,1,buffer,size.value,C.byref(size)):raise C.WinError(C.get_last_error())
  sid=C.cast(buffer,C.POINTER(C.c_void_p))[0];text=W.LPWSTR()
  if not convert(sid,C.byref(text)):raise C.WinError(C.get_last_error())
  try:return text.value
  finally:api(K,'LocalFree',W.HANDLE,W.HANDLE)(C.cast(text,W.HANDLE))
 finally:close(token)
def info(pid,name=''):
 sess=W.DWORD();session(pid,C.byref(sess));handle=open_process(0x1000,False,pid)
 value={'pid':pid,'name':name.casefold(),'session':sess.value,'path':'','started':0}
 if not handle:return value
 try:
  path=C.create_unicode_buffer(32768);length=W.DWORD(len(path))
  if image(handle,0,path,C.byref(length)):value['path']=path.value.casefold()
  stamps=[W.FILETIME() for _ in range(4)]
  if times(handle,*(C.byref(x) for x in stamps)):
   value['started']=((stamps[0].dwHighDateTime<<32)|stamps[0].dwLowDateTime)/10000000-11644473600
 finally:close(handle)
 return value
def processes():
 handle=snapshot(2,0);entry=Entry();entry.size=C.sizeof(entry);result={}
 try:
  valid=first(handle,C.byref(entry))
  while valid:
   if entry.exe.casefold() in ('yasb.exe','librehardwaremonitor.exe','python.exe','pythonw.exe'):
    result[entry.pid]=info(entry.pid,entry.exe)
   valid=next_process(handle,C.byref(entry))
 finally:close(handle)
 return result
def read(path):
 try:return json.loads(Path(path).read_text('utf-8'))
 except (OSError,ValueError):return {}
def event(text):
 try:
  log=USER_ROOT/'helpers/watchdog.log'
  if log.exists() and log.stat().st_size>65536:os.replace(log,log.with_suffix('.log.old'))
  with log.open('a',encoding='utf-8') as f:f.write(time.strftime('%Y-%m-%dT%H:%M:%S%z')+' '+text+'\n')
 except OSError:pass
def launch(args,env=None):
 return subprocess.Popen(args,cwd=ROOT,env=env or child_environment(ROOT,USER_ROOT),creationflags=subprocess.CREATE_NO_WINDOW,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
def retry_delay(attempt):return min(300,30*2**min(4,attempt-1))
def lease_valid(lease,owner,now):
 return bool(lease.get('expires',0)>now and owner.get('path') and owner.get('started',0)>0 and owner['started']<=lease.get('created',0)+1)
def companion_valid(record,host,path,script,current,check_script=True):
 return bool(record and record.get('started',0)>0 and host.get('started',0)>0 and record.get('session')==current and record.get('path')==path.casefold() and
             abs(record.get('started',0)-host.get('started',0))<30 and
             (not check_script or host.get('script')==script))
def main():
 mutex=api(K,'CreateMutexW',W.HANDLE,C.c_void_p,W.BOOL,W.LPCWSTR)(None,False,'Local\\YASB-StableV1-'+user_sid())
 wait=api(K,'WaitForSingleObject',W.DWORD,W.HANDLE,W.DWORD)
 # Scheduler Stop may report Ready before the previous process releases its
 # mutex. A short kernel wait avoids dropping the immediately resumed task.
 owns=wait(mutex,5000) in (0,128)
 if not owns:close(mutex);return 0
 settings=read(USER_ROOT/'helpers/watchdog-settings.json');current=info(os.getpid())['session']
 states={name:{'next':0,'attempts':0,'seen':None,'pending':False} for name in ('yasb','LibreHardwareMonitor','TimeCenter','WeatherCenter')}
 data=USER_ROOT/'shell-updater/data'
 marker=USER_ROOT/'helpers/watchdog-host.json';atomic(marker,info(os.getpid()))
 try:
  event('Watchdog started in console-free host.')
  grace=time.monotonic()+15
  while time.monotonic()<grace:
   if read(data/'manual-maintenance.json').get('exit'):return 0
   time.sleep(min(.25,max(0,grace-time.monotonic())))
  while True:
   manual=read(data/'manual-maintenance.json')
   if manual.get('exit'):return 0
   if manual:time.sleep(8);continue
   lease=read(data/'maintenance.json');owner=info(int(lease.get('owner',0))) if lease.get('owner') else {}
   if lease_valid(lease,owner,time.time()):
    time.sleep(8);continue
   update=read(data/'state.json');recovery=data/'recovery_runner.py'
   if update.get('transaction'):
    if not update.get('recovery_attempted') and recovery.exists():
     child=launch([settings['TimeCenterPython'],str(recovery),'--root',str(ROOT),'--action','recover'])
     try:child.wait(timeout=60)
     except subprocess.TimeoutExpired:pass
    time.sleep(8);continue
   available=processes();now=time.time()
   for name,state in states.items():
    if name=='LibreHardwareMonitor' and not settings.get('LhmTask'):continue
    if name in ('TimeCenter','WeatherCenter'):
     host=read(settings.get(name+'Pid',''));record=available.get(host.get('pid'),{})
     running=companion_valid(record,host,settings.get(name+'Python',''),settings.get(name+'Script'),current,name=='WeatherCenter')
    else:
     running=any(p['session']==current and p['name']==(name+'.exe').casefold() for p in available.values())
    if running:
     if state['pending']:event(name+' recovered.');state['pending']=False
     if state['seen'] is None:state['seen']=now
     if now-state['seen']>=30:state['attempts']=0
     continue
    state['seen']=None
    if now<state['next']:continue
    state['attempts']+=1;delay=retry_delay(state['attempts']);state['next']=now+delay
    try:
     if name=='yasb':
      recent=update.get('last_success',{})
      if state['attempts']>=2 and not update.get('failure') and recent and now-recent.get('installed_at',0)<600 and recovery.exists():
       child=launch([settings['TimeCenterPython'],str(recovery),'--root',str(ROOT),'--action','post-crash-rollback'])
       try:child.wait(timeout=60)
       except subprocess.TimeoutExpired:pass
       continue
      launch([settings['YasbCli'],'start'])
     elif name in ('TimeCenter','WeatherCenter'):
      launch([settings[name+'Python'],settings[name+'Script']])
     else:
      powershell=Path(os.environ['WINDIR'])/'System32/WindowsPowerShell/v1.0/powershell.exe'
      launch([str(powershell),'-NoProfile','-NonInteractive','-Command','Start-ScheduledTask -TaskName $env:YASB_LHM_TASK_NAME'],env=dict(os.environ,YASB_LHM_TASK_NAME=settings['LhmTask']))
     state['pending']=True;event(name+' missing; restart requested (retry delay '+str(delay)+'s).')
    except Exception as exc:event(name+' launch failed: '+type(exc).__name__+'; bounded retry remains.')
   time.sleep(8)
 finally:
  if read(marker).get('pid')==os.getpid():
   try:marker.unlink()
   except FileNotFoundError:pass
  api(K,'ReleaseMutex',W.BOOL,W.HANDLE)(mutex);close(mutex)
if __name__=='__main__':
 try:raise SystemExit(main())
 except Exception as exc:event('Watchdog stopped: '+type(exc).__name__);raise
