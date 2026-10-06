"""Fresh EXE profile without system tools; safe local companion and updater checks."""
import argparse,copy,hashlib,io,json,marshal,os,subprocess,sys,time,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def run_test(program,data):
 program=Path(program).resolve();data=Path(data).resolve();python=program/'runtime/python/python.exe'
 env=dict(os.environ,OMNI_PROGRAM_ROOT=str(program),OMNI_USER_ROOT=str(data),YASB_CONFIG_HOME=str(data),
          PATH=os.environ['WINDIR']+'\\System32',PYTHONIOENCODING='utf-8',LOCALAPPDATA=str(data/'local'))
 output=ROOT/'.validation/omni-installer';results=[]
 def record(name,ok):
  results.append({'case':name,'passed':bool(ok)});print(name,bool(ok),flush=True);assert ok,name
 def call(args,timeout=12):
  return subprocess.run([str(python),*args],env=env,cwd=program,capture_output=True,encoding='utf-8',timeout=timeout,creationflags=subprocess.CREATE_NO_WINDOW)
 record('EXE supplies Python Qt timezone and weather dependencies',call(['-c','import PySide6,shiboken6,astral,tzdata,tzfpy,tzlocal,yaml,omni_layout']).returncode==0)
 children=[]
 try:
  for name in ('time','weather'):
   script=program/(name+'-center/app/main.py');p=subprocess.Popen([str(python.with_name('pythonw.exe')),str(script)],env=env,cwd=program,creationflags=subprocess.CREATE_NO_WINDOW);children.append((name,p))
   end=time.monotonic()+10;status={}
   while time.monotonic()<end:
    reply=call([str(script),'--status'])
    try:status=json.loads(reply.stdout)
    except ValueError:status={}
    if status.get('running'):break
    time.sleep(.2)
   record(name+' installed hidden host and IPC',status.get('running') and status.get('pid')==p.pid and not status.get('visible'))
  weather=json.loads((data/'weather-center/data/state.json').read_text('utf-8'));time_state=json.loads((data/'time-center/data/state.json').read_text('utf-8'))
  record('fresh Weather Center is unconfigured',not weather['selected'] and not weather['locations'])
  record('fresh Time Center has no private clocks alarms timers or planner',not time_state['cities'] and not time_state['alarms'] and not time_state['timers'] and not time_state['notes'])
  record('all state stays outside program directory',not any((program/(n+'-center/data')).exists() for n in ('time','weather')))
 finally:
  for name,p in children:
   call([str(program/(name+'-center/app/main.py')),'--quit']);p.wait(timeout=10)
 result=call(['-c','import sys;sys.path.insert(0,"shell-updater");from engine import Updater;from pathlib import Path;e=Updater(Path.cwd());print(e.repository(),e.state["mode"])'])
 record('public release source and chosen update policy survive install',result.returncode==0 and 'Starvastika/Omni-Taskbar check' in result.stdout)
 output.mkdir(parents=True,exist_ok=True);(output/'installed-layout-tests.json').write_text(json.dumps(results,indent=2),'utf-8')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--program',required=True);p.add_argument('--data',required=True);a=p.parse_args();run_test(a.program,a.data)
