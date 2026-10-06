"""Start only owned, hidden companions from a freshly extracted release."""
import sys,json,subprocess,tempfile,os,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'dist';OUT.mkdir(exist_ok=True)
sys.path.insert(0,str(ROOT/'shell-updater'))
from engine import Updater,read
results=[]
with tempfile.TemporaryDirectory(prefix='yasb-fresh-artifact-') as tmp:
 root=Path(tmp)/'shell';validator=object.__new__(Updater);validator.root=root
 manifest=read(ROOT/'dist/release-manifest.json');validator.extract(ROOT/'dist'/manifest['asset'],root,manifest['version'])
 (root/'config.yaml').write_text((root/'distribution/defaults/config.yaml').read_text('utf-8').replace('{install_root}',str(root)),'utf-8')
 env=dict(os.environ,PYTHONPATH=str(ROOT/'time-center/.venv/Lib/site-packages'),PYTHONIOENCODING='utf-8',LOCALAPPDATA=str(Path(tmp)/'local'))
 children=[]
 try:
  for name in ('time','weather'):
   script=root/(name+'-center/app/main.py')
   p=subprocess.Popen([sys.executable.replace('python.exe','pythonw.exe'),str(script)],env=env,creationflags=subprocess.CREATE_NO_WINDOW);children.append((name,p))
   healthy=False;end=time.monotonic()+8
   while time.monotonic()<end and p.poll() is None:
    r=subprocess.run([sys.executable,str(script),'--status'],capture_output=True,encoding='utf-8',env=env,timeout=5,creationflags=subprocess.CREATE_NO_WINDOW)
    try:status=json.loads(r.stdout)
    except ValueError:status={}
    if status.get('running') and status.get('pid')==p.pid:healthy=True;break
    time.sleep(.2)
   results.append({'case':name+' hidden host and real IPC from fresh extracted release','passed':healthy,'visible':status.get('visible')})
   print(name,'fresh extracted real host',healthy,flush=True);assert healthy
   log=root/(name+'-center/logs/'+name+'-center.log')
   if log.exists():assert not any(x in log.read_text('utf-8') for x in ('ERROR','is not a type','is not installed','ReferenceError','TypeError'))
  for name,p in children:
   r=subprocess.run([sys.executable,str(root/(name+'-center/app/main.py')),'--quit'],capture_output=True,encoding='utf-8',env=env,timeout=5,creationflags=subprocess.CREATE_NO_WINDOW)
   p.wait(timeout=10)
   results.append({'case':name+' fresh host exits through original IPC','passed':p.returncode==0})
 finally:
  for _,p in children:
   if p.poll() is None:p.terminate();p.wait(timeout=5)
(OUT/'fresh-companion-tests.json').write_text(json.dumps(results,indent=2),'utf-8')
print('Fresh extracted artifact cases',len(results))
