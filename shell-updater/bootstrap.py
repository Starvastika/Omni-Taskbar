"""Checksummed release bootstrap; dependencies and existing watchdog architecture."""
import argparse,contextlib,json,os,shutil,subprocess,sys,tempfile
from pathlib import Path
from engine import Updater,validate_manifest,read,atomic,sha,Network,lock
def run(args,timeout=600):
 if subprocess.run(args,timeout=timeout).returncode:raise RuntimeError('Dependency/setup command failed')
def install(root,archive,manifest,mode):
 root=Path(root).resolve();manifest=validate_manifest(manifest)
 if sys.version_info[:2]!=(3,14):raise RuntimeError('Python 3.14 required')
 if sha(archive)!=manifest['sha256']:raise ValueError('Release checksum mismatch')
 with tempfile.TemporaryDirectory(prefix='yasb-bootstrap-') as tmp:
  folder=Path(tmp);candidate=folder/'release';validator=object.__new__(Updater);validator.root=root
  inventory=validator.extract(archive,candidate,manifest['version'])
  if (root/'version.json').exists():
   engine=Updater(root)
   with contextlib.suppress(FileNotFoundError):shutil.rmtree(engine.data/'staged')
   shutil.copytree(candidate,engine.data/'staged')
   engine.state.update(staged_version=manifest['version'],staged_manifest=manifest,attention=True,available=True,mode=mode,failure=False)
   engine.save();engine.apply()
   if engine.state.get('last_update_result')!='success':raise RuntimeError(engine.state.get('status','Update failed'))
   return
  if (root/'config.yaml').exists():raise RuntimeError('An unversioned existing shell needs adoption; existing config was not overwritten')
  environment=root/'time-center/.venv'
  if not (environment/'Scripts/python.exe').exists():run([sys.executable,'-m','venv',str(environment)])
  run([str(environment/'Scripts/python.exe'),'-m','pip','install','-r',str(candidate/'time-center/requirements.txt')])
  runtime=root/'.runtime/yasb-2.0.7'
  if not (runtime/'yasb.exe').exists():
   network=Network();raw,_=network.get('https://api.github.com/repos/amnweb/yasb/releases/tags/v2.0.7')
   assets={x['name']:x['browser_download_url'] for x in json.loads(raw)['assets']}
   checks,_=network.get(assets['checksums.txt'],65536);name='yasb-2.0.7-x64.msi';expected=None
   for line in checks.decode().splitlines():
    if name in line:
     import re
     found=re.search(r'\b[a-fA-F0-9]{64}\b',line)
     if found:expected=found[0].lower()
   if not expected:raise ValueError('Official YASB checksum missing')
   pinned=read(candidate/'distribution/runtime-base.json')['native_msi_sha256']
   if expected!=pinned:raise ValueError('Official native runtime differs from the tested pinned dependency')
   installer=folder/name;network.download(assets[name],installer)
   if sha(installer)!=expected:raise ValueError('Official YASB checksum mismatch')
   from native_archive import extract
   image=folder/'native-runtime';extract(installer,image)
   runtime.parent.mkdir(parents=True,exist_ok=True);shutil.copytree(image,runtime,dirs_exist_ok=True)
  for name in inventory['files']:
   target=root/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(candidate/name,target)
  defaults=root/'distribution/defaults'
  (root/'config.yaml').write_text((defaults/'config.yaml').read_text('utf-8').replace('{install_root}',str(root)),'utf-8')
  shutil.copy2(defaults/'styles.css',root/'styles.css')
  python=str(Path(sys.executable).resolve());atomic(root/'helpers/runtime-settings.json',{'python':python})
  settings={'LhmTask':'LibreHardwareMonitor','YasbCli':str(runtime/'yasbc.exe')}
  available=subprocess.run(['powershell.exe','-NoProfile','-Command',"[bool](Get-ScheduledTask -TaskName LibreHardwareMonitor -ErrorAction SilentlyContinue)"],capture_output=True,text=True,timeout=15)
  if available.stdout.strip().casefold()!='true':settings['LhmTask']=None
  for name,title in (('time','TimeCenter'),('weather','WeatherCenter')):
   settings[title+'Python']=str(Path(python).with_name('pythonw.exe'));settings[title+'Script']=str(root/(name+'-center/app/main.py'));settings[title+'Pid']=str(root/(name+'-center/data/host.json'))
  atomic(root/'helpers/watchdog-settings.json',settings);engine=Updater(root);engine.mode(mode)
  setup=root/'distribution/register-startup.ps1'
  if not setup.exists():raise RuntimeError('Startup registration script missing')
  engine.maintenance(True)
  try:
   engine.lifecycle.expected={'time':True,'weather':True};engine.lifecycle.start()
   if not engine.lifecycle.health():
    engine.lifecycle.stop();engine.fail('Initial installation failed health; previous startup is unchanged',RuntimeError('Install health check failed'))
    raise RuntimeError('Installation failed health; new shell stopped, previous startup unchanged. Files retained for retry.')
   run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(setup)])
  finally:engine.maintenance(False)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--archive',required=True);p.add_argument('--manifest',required=True);p.add_argument('--mode',choices=('automatic','check','manual'),required=True);a=p.parse_args()
 try:
  with lock(Path(a.root)/'shell-updater/data'):install(a.root,a.archive,read(a.manifest),a.mode)
 except Exception as exc:print('Installation failed: '+str(exc),file=sys.stderr);raise SystemExit(1)
