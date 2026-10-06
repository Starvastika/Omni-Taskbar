"""Real EXE-installed companions with release transport mocked, never live developer bars."""
import argparse,hashlib,io,json,os,sys,time,zipfile
from pathlib import Path

def run(root,data):
 root=Path(root).resolve();data=Path(data).resolve()
 assert (root/'omni-installed.json').is_file() and root!=Path.home()/'.config/yasb'
 os.environ.update(OMNI_PROGRAM_ROOT=str(root),OMNI_USER_ROOT=str(data),YASB_CONFIG_HOME=str(data),LOCALAPPDATA=str(data/'local'))
 sys.path[:0]=[str(root),str(root/'shell-updater')]
 from engine import Updater,Network,WindowsLifecycle,read,sha
 from omni_layout import child_environment
 results=[]
 def record(case,ok):
  print(case, bool(ok),flush=True);results.append({'case':case,'passed':bool(ok)});assert ok,case
 class CompanionLife(WindowsLifecycle):
  def running(self):return False
  def start(self):
   import subprocess
   for name in ('time','weather'):
    subprocess.Popen([self.python().replace('python.exe','pythonw.exe'),str(self.root/(name+'-center/app/main.py'))],env=child_environment(self.root,self.user_root),creationflags=subprocess.CREATE_NO_WINDOW)
  def health(self):
   end=time.monotonic()+8
   while time.monotonic()<end:
    if all(self.status(n).get('running') for n in ('time','weather')):return True
    time.sleep(.2)
   return False
 life=CompanionLife(root);life.expected={'time':True,'weather':True}
 class Response(io.BytesIO):
  def __init__(self,b,url):super().__init__(b);self.url=url;self.headers={}
  def geturl(self):return self.url
 def release(version,broken=False):
  meta=read(root/'version.json');meta['version']=version
  files={'shell-updater/mock_update_added.py':b'# Isolated added file ownership check\n','version.json':json.dumps(meta).encode(),'README.md':b'Isolated mock update'}
  if broken:files['weather-center/app/main.py']=b'raise RuntimeError("deliberate isolated health failure")\n'
  inventory={'version':version,'files':{n:hashlib.sha256(b).hexdigest() for n,b in files.items()}}
  buffer=io.BytesIO()
  with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as z:
   for name,b in files.items():z.writestr(name,b)
   z.writestr('package-files.json',json.dumps(inventory))
  archive=buffer.getvalue();asset='omni-taskbar-'+version+'-update.zip';base='https://github.com/Starvastika/Omni-Taskbar/releases/download/v'+version+'/'
  manifest={'version':version,'minimum_updater_version':'1.0.0','asset':asset,'sha256':hashlib.sha256(archive).hexdigest(),'channel':'stable','requires_shell_restart':True,'requires_windows_restart':False}
  info={'tag_name':'v'+version,'body':'Mock local release','draft':False,'prerelease':False,'assets':[{'name':n,'browser_download_url':base+n} for n in (asset,'release-manifest.json')]}
  def opener(request,timeout):
   url=request.full_url;return Response(json.dumps(info).encode() if url.endswith('/latest') else json.dumps(manifest).encode() if url.endswith('release-manifest.json') else archive,url)
  return Network(opener)
# Representative nonempty user preferences and a synthetic saved location.
 sys.path.insert(0,str(root/'weather-center'))
 from services.state import location
 weather=read(data/'weather-center/data/state.json');loc=location({'id':'installer-fixture','name':'Synthetic fixture','lat':51.5,'lon':-.1,'zone':'Europe/London'})
 weather.update(selected=loc,locations=[loc],homeId=loc['id']);weather['prefs']['offline']=True
 (data/'weather-center/data/state.json').write_text(json.dumps(weather,indent=2),'utf-8')
 state=read(data/'time-center/data/state.json');state['prefs']['hour24']=False;state['prefs']['sound']=False
 (data/'time-center/data/state.json').write_text(json.dumps(state,indent=2),'utf-8')
 state_files=[data/'config.yaml',data/'styles.css',data/'time-center/data/state.json',data/'weather-center/data/state.json']
 before={str(p):p.read_bytes() for p in state_files}
 (data/'update-inputs.json').write_text(json.dumps({p:b.decode('utf-8') for p,b in before.items()}),'utf-8')
 try:
  e=Updater(root,release('1.0.1'),life);e.mode('check');e.check(True);record('installed check mode keeps attention without staging',e.state['attention'] and not e.state.get('staged_version'))
  e.stage();record('verified stage keeps attention',e.state['attention'] and e.state['staged_version']=='1.0.1');e.apply()
  record('EXE-installed 1.0.0 to mock 1.0.1 with real companion IPC health',read(root/'version.json')['version']=='1.0.1' and e.state['last_update_result']=='success' and not e.state['attention'])
  life.prepare();life.stop()
  good=sha(root/'weather-center/app/main.py')
  e=Updater(root,release('1.0.2',True),life);e.mode('automatic');e.check(True);e.apply(True)
  record('broken 1.0.2 real host startup failure rolls back to 1.0.1',read(root/'version.json')['version']=='1.0.1' and e.state['last_update_result']=='rolled_back' and sha(root/'weather-center/app/main.py')==good and life.health())
  record('installation inventory follows successful update and rollback',read(root/'installation-files.json')['version']=='1.0.1' and 'shell-updater/mock_update_added.py' in read(root/'installation-files.json')['files'])
  record('rollback leaves persistent attention and no maintenance lease',e.state['attention'] and e.state['failure'] and not (e.data/'maintenance.json').exists())
  count=read(root/'version.json');e.apply(True);record('failed automatic release has no retry loop',read(root/'version.json')==count)
  for mode in ('automatic','check','manual'):e.mode(mode);record(mode+' persists in installed layout',Updater(root).state['mode']==mode)
  def equal(p,b):
   if not p.endswith('state.json'):return Path(p).read_bytes()==b
   old=json.loads(b);new=read(Path(p))
   # Time Center normally refreshes this persistence epoch on clean shutdown,
   # including when paused; all actual stopwatch values and user state must match.
   if 'stopwatch' in old and not old['stopwatch']['running']:
    old['stopwatch'].pop('anchor',None);new['stopwatch'].pop('anchor',None)
   return old==new
  record('config/styles exact and all companion user values preserved',all(equal(p,v) for p,v in before.items()))
 finally:
  life.prepare();life.stop()
 (data/'installed-update-tests.json').write_text(json.dumps(results,indent=2),'utf-8')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--data',required=True);a=p.parse_args();run(a.root,a.data)
