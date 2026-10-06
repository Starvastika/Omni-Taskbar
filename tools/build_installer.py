"""Generate Inno input from the single version source and verified full image."""
import argparse,json,hashlib,shutil,subprocess,sys,zipfile,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def build(compiler=None,fixture_version=None):
 from build_full_image import build as full
 from prepare_installer_deps import acquire
 from release_package import sources
 before={n:hashlib.sha256(b).hexdigest() for n,b in sources(ROOT).items()}
 image=full();version=json.loads((ROOT/'version.json').read_text())['version'];output=ROOT/'dist'
 if fixture_version:
  from engine import semver,sha
  semver(fixture_version);version=fixture_version
  meta=json.loads((image/'version.json').read_text());meta['version']=version;(image/'version.json').write_text(json.dumps(meta),'utf-8')
  inventory=json.loads((image/'installation-files.json').read_text());inventory['version']=version;inventory['files']['version.json']=sha(image/'version.json');(image/'installation-files.json').write_text(json.dumps(inventory,indent=2),'utf-8')
 builddir=output/'inno';builddir.mkdir(exist_ok=True)
 bootstrap=builddir/'bootstrap';bootstrap.mkdir(exist_ok=True)
 with zipfile.ZipFile(acquire('python')) as z:z.extractall(bootstrap)
 (bootstrap/'python314._pth').write_text('python314.zip\n.\nimport site\n','utf-8')
 for source in ('shell-updater/installer_backend.py','shell-updater/engine.py','shell-updater/native_taskbar.py','omni_layout.py'):
  shutil.copy2(ROOT/source,bootstrap/Path(source).name)
 definitions=[];extract=[]
 for p in bootstrap.iterdir():
  if not p.is_file():continue
  name='boot_'+p.name
  definitions.append(f'Source: "{p}"; DestName: "{name}"; Flags: dontcopy')
  extract.append(f"  ExtractTemporaryFile('{name}');")
  extract.append(f"  if not RenameFile(ExpandConstant('{{tmp}}\\{name}'), ExpandConstant('{{tmp}}\\{p.name}')) then RaiseException('Setup runtime extraction failed');")
 (builddir/'bootstrap-files.iss').write_text('\n'.join(definitions),'utf-8')
 (builddir/'bootstrap-extract.iss').write_text('\n'.join(extract),'utf-8')
 (builddir/'generated.iss').write_text(f'#define OmniVersion "{version}"\n#define ProjectRoot "{ROOT}"\n#define ImageFolder "{image}"\n#define OutputFolder "{output}"\n','utf-8')
 shutil.copy2(ROOT/'distribution/Omni-Taskbar.iss',builddir/'Omni-Taskbar.iss')
 compiler=Path(compiler or ROOT/'.validation/omni-installer/inno/ISCC.exe')
 with (builddir/'compiler.log').open('w',encoding='utf-8') as log:
  args=[str(compiler),str(builddir/'Omni-Taskbar.iss')]
  if fixture_version:args[1:1]=['/DOmniFixtureBuild=1']
  if os.environ.get('OMNI_INNO_SIGN_COMMAND'):args[1:1]=['/DOmniSignCommand=1','/Somnisign='+os.environ['OMNI_INNO_SIGN_COMMAND']]
  result=subprocess.run(args,stdout=log,stderr=subprocess.STDOUT)
 if result.returncode:
  print('\n'.join((builddir/'compiler.log').read_text('utf-8',errors='replace').splitlines()[-12:]))
  raise RuntimeError('Inno compiler failed')
 after={n:hashlib.sha256(b).hexdigest() for n,b in sources(ROOT).items()}
 if before!=after:raise RuntimeError('Source inputs changed during build; discard and rebuild')
 installer=output/f'Omni-Taskbar-Setup-{version}.exe'
 digest=hashlib.sha256(installer.read_bytes()).hexdigest()
 (output/'installer-build.json').write_text(json.dumps({'version':version,'asset':installer.name,'sha256':digest,'bytes':installer.stat().st_size,'signed':bool(os.environ.get('OMNI_INNO_SIGN_COMMAND'))},indent=2),'utf-8')
 print(json.dumps({'installer':installer.name,'bytes':installer.stat().st_size,'sha256':digest}))
 return installer
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--compiler');p.add_argument('--fixture-version');a=p.parse_args();build(a.compiler,a.fixture_version)
