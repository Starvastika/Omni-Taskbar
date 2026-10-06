"""Run actual setup/repair/upgrade/uninstall EXEs in an explicitly isolated target."""
import argparse,hashlib,json,os,subprocess,sys,time,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def run(setup,upgrade,fixture,shell=False):
 setup=Path(setup).resolve();upgrade=Path(upgrade).resolve();fixture=Path(fixture).resolve()
 if not fixture.is_relative_to((ROOT/'.validation').resolve()):raise ValueError('Fixture must stay under .validation')
 if shell and os.environ.get('GITHUB_ACTIONS')!='true' and os.environ.get('OMNI_ISOLATED_DESKTOP')!='1':raise ValueError('Full shell test requires a clean CI/isolated desktop, never a live developer shell')
 program=fixture/'program';data=fixture/'user-data';fixture.mkdir(parents=True,exist_ok=True)
 results=[]
 def record(case,ok):
  print(case,bool(ok),flush=True);results.append({'case':case,'passed':bool(ok)});assert ok,case
 def install(exe):
  args=[str(exe),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/NOICONS','/DIR='+str(program),'/DATA_DIR='+str(data),'/UPDATEMODE=check','/LOG='+str(fixture/'setup.log')]
  args+=['/NOLAUNCH=1']
  if not shell:args+=['/NOSTARTUP=1']
  result=subprocess.run(args,timeout=240)
  if result.returncode:
   error=data/'shell-updater/data/installer-error.json'
   print('Installer exit',result.returncode,error.read_text('utf-8') if error.exists() else (fixture/'setup.log').read_text('utf-8',errors='replace')[-2400:],flush=True)
  record('actual EXE install '+exe.name,result.returncode==0)
 def embedded(script,*args):
  env=dict(os.environ,PATH=os.environ['WINDIR']+'\\System32',OMNI_PROGRAM_ROOT=str(program),OMNI_USER_ROOT=str(data),YASB_CONFIG_HOME=str(data),LOCALAPPDATA=str(data/'local'))
  if script.endswith('test_installed_widgets.py'):env.update(YASB_NATIVE_RUNTIME=str(program/'.runtime/yasb-2.0.7'),QT_QPA_PLATFORM='offscreen')
  result=subprocess.run([str(program/'runtime/python/python.exe'),str(ROOT/script),*map(str,args)],env=env,timeout=240)
  record(script,result.returncode==0)
 install(setup)
 embedded('tools/test_installed_layout.py','--program',program,'--data',data)
 embedded('tools/test_installed_widgets.py')
 embedded('tools/test_installed_weather.py')
 if shell:embedded('tools/test_installed_shell.py','--program',program,'--data',data)
 originals={str(p):p.read_bytes() for p in (data/'config.yaml',data/'styles.css',data/'time-center/data/state.json',data/'weather-center/data/state.json')}
 (program/'README.md').write_text('corrupted shipped file','utf-8');install(setup)
 record('repair restores owned shipped file',(program/'README.md').read_bytes()==(ROOT/'README.md').read_bytes())
 record('repair preserves configuration and personal state',all(Path(p).read_bytes()==v for p,v in originals.items()))
 embedded('tools/test_installed_update.py','--root',program,'--data',data)
 shutil.copy2(data/'installed-update-tests.json',fixture/'installed-update-results.json')
 before={str(p):p.read_bytes() for p in (data/'config.yaml',data/'styles.css',data/'time-center/data/state.json',data/'weather-center/data/state.json')}
 mode=json.loads((data/'shell-updater/data/state.json').read_text())['mode'];install(upgrade)
 record('manual EXE upgrade owns version 1.0.1',json.loads((program/'version.json').read_text())['version']=='1.0.1')
 record('manual EXE upgrade preserves policy and user files',json.loads((data/'shell-updater/data/state.json').read_text())['mode']==mode and all(Path(p).read_bytes()==v for p,v in before.items()))
 def uninstall(remove=False):
  args=[str(program/'unins000.exe'),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART']
  if not shell:args+=['/NOSTARTUP=1']
  if remove:args+=['/REMOVEDATA=1']
  record('actual uninstall '+('explicit data removal' if remove else 'default preserves data'),subprocess.run(args,timeout=90).returncode==0)
 uninstall()
 record('default uninstall retains user data',all(Path(p).read_bytes()==v for p,v in before.items()))
 # Inno's uninstaller launches delayed self-deletion after its main process exits.
 deadline=time.monotonic()+20
 while program.exists() and any(p.is_file() for p in program.rglob('*')) and time.monotonic()<deadline:time.sleep(.2)
 left=[p.relative_to(program).as_posix() for p in program.rglob('*') if p.is_file()] if program.exists() else []
 print('Remaining program files after uninstall:',left,flush=True)
 record('default uninstall removes all owned program files',not left)
 install(upgrade);record('reinstall recognizes retained owned data',all(Path(p).read_bytes()==v for p,v in before.items()))
 uninstall(True);record('explicit removal deletes only owned data',not data.exists())
 (fixture/'matrix-results.json').write_text(json.dumps(results,indent=2),'utf-8')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--setup',required=True);p.add_argument('--upgrade',required=True);p.add_argument('--fixture',required=True);p.add_argument('--shell',action='store_true');a=p.parse_args();run(a.setup,a.upgrade,a.fixture,a.shell)
