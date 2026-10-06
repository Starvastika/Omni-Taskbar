"""Build only verified shipped files and public dependency archives, never live state."""
import hashlib,json,shutil,sys,zipfile,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'shell-updater')]
from release_package import sources,privacy,sanitized_library
from engine import sha,read
from prepare_installer_deps import CACHE,acquire
def clean(path):
 path=Path(path).resolve()
 if not path.is_relative_to((ROOT/'dist').resolve()):raise ValueError('Build cleanup outside dist')
 if path.exists():shutil.rmtree(path)
 path.mkdir(parents=True)
def build():
 from build_release_runtime import build as runtime
 runtime()
 image=ROOT/'dist/full-image';clean(image)
 native=ROOT/'.validation/omni-installer/native'
 msi=ROOT/'.validation/omni-installer/deps/yasb-2.0.7-x64.msi'
 expected=read(ROOT/'distribution/runtime-base.json')['native_msi_sha256']
 if not msi.exists():
  import urllib.request
  msi.parent.mkdir(parents=True,exist_ok=True);urllib.request.urlretrieve('https://github.com/amnweb/yasb/releases/download/v2.0.7/yasb-2.0.7-x64.msi',msi)
 if sha(msi)!=expected:raise ValueError('Upstream native runtime checksum mismatch')
 if not native.resolve().is_relative_to((ROOT/'.validation/omni-installer').resolve()) or native.is_symlink() or native.is_junction():raise ValueError('Unsafe native cache')
 # Re-extract every build: a mutable local cache cannot establish provenance.
 if native.exists():shutil.rmtree(native)
 from native_archive import extract
 extract(msi,native)
 shutil.copytree(native,image/'.runtime/yasb-2.0.7')
 (image/'.runtime/yasb-2.0.7/lib/library.zip').write_bytes(sanitized_library(ROOT/'distribution/runtime-overlay.zip'))
 files=sources(ROOT);privacy(files)
 for name,data in files.items():
  target=image/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
 python=image/'runtime/python';python.mkdir(parents=True)
 embed=acquire('python')
 with zipfile.ZipFile(embed) as z:z.extractall(python)
 (python/'python314._pth').write_text('python314.zip\n.\nsite-packages\n../../\nimport site\n','utf-8')
 wheels=json.loads((CACHE/'wheels.json').read_text('utf-8'))
 packages=python/'site-packages';packages.mkdir()
 for name,metadata in wheels.items():
  path=CACHE/'wheels'/name
  if sha(path)!=metadata['sha256']:raise ValueError('Dependency wheel changed')
  with zipfile.ZipFile(path) as z:z.extractall(packages)
 # Upstream wheel includes irrelevant Python 3.10 bytecode; ship readable source.
 for cache in packages.rglob('__pycache__'):
  if cache.resolve().is_relative_to(packages.resolve()):shutil.rmtree(cache)
 for p in native.glob('*.dll'):
  if p.name.startswith(('vcruntime','msvcp','concrt')):shutil.copy2(p,python/p.name)
 shutil.copy2(ROOT/'dist/Omni-Taskbar.exe',image/'Omni-Taskbar.exe')
 defaults=image/'distribution/defaults/config.yaml'
 text=defaults.read_text('utf-8').replace('exec wscript.exe "{install_root}\\time-center\\toggle.vbs"','exec "{install_root}\\Omni-Taskbar.exe" --time')
 defaults.write_text(text,'utf-8')
 notices=image/'distribution/licenses'
 shutil.copy2(python/'LICENSE.txt',notices/'Python-LICENSE.txt')
 for distinfo in packages.glob('*.dist-info'):
  for notice in distinfo.rglob('*'):
   if notice.is_file() and ('license' in notice.name.casefold() or 'copying' in notice.name.casefold()):
    folder=notices/distinfo.name;folder.mkdir(exist_ok=True);shutil.copy2(notice,folder/notice.name)
 inventory={p.relative_to(image).as_posix():sha(p) for p in image.rglob('*') if p.is_file()}
 (image/'installation-files.json').write_text(json.dumps({'product':'Omni Taskbar','version':read(ROOT/'version.json')['version'],'files':inventory},indent=2),'utf-8')
 # Consumer setup has no installer-time network or pip.
 print(json.dumps({'full_image_files':len(inventory),'uncompressed_bytes':sum(p.stat().st_size for p in image.rglob('*') if p.is_file())}))
 return image
if __name__=='__main__':build()
