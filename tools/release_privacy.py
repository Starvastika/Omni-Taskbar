"""Fail closed on local source/inventory secrets and developer paths before upload."""
import hashlib,json,re,subprocess,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'));sys.path.insert(0,str(ROOT/'shell-updater'))
from release_package import sources,privacy,sanitized_library
from engine import sha,safe_name

def validate():
 names=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=ROOT).decode().split('\0')
 files={n:(ROOT/n).read_bytes() for n in names if n and (ROOT/n).is_file()};privacy(files);privacy(sources(ROOT))
 forbidden={'data','logs','exports','cache','.validation','stable-v1','.git','.venv','__pycache__'}
 for name in files:
  if any(x in forbidden for x in Path(name).parts) or name in ('config.yaml','styles.css'):raise ValueError('Runtime state tracked: '+name)
 image=ROOT/'dist/full-image';inventory=json.loads((image/'installation-files.json').read_text())
 expected=set(inventory['files'])|{'installation-files.json'};actual={p.relative_to(image).as_posix() for p in image.rglob('*') if p.is_file()}
 if expected!=actual:raise ValueError('Full image contains unlisted files')
 needles=[str(Path.home()).encode(),str(Path.home()).encode('utf-16-le'),b'E:'+bytes((92,))+b'Downloads',b'E:'+bytes((47,))+b'Downloads']
 for name,digest in inventory['files'].items():
  # Only verified wheel/native inputs may contain upstream package data directories.
  if not name.startswith(('runtime/python/site-packages/','.runtime/yasb-2.0.7/')):safe_name(name)
  elif any(x in ('..','.validation','stable-v1','.git') for x in Path(name).parts):raise ValueError('Unsafe native inventory')
  p=image/name
  if sha(p)!=digest:raise ValueError('Image content changed: '+name)
  b=p.read_bytes()
  if any(n.lower() in b.lower() for n in needles):raise ValueError('Private developer path in image: '+name)
  if name.endswith('library.zip'):sanitized_library(p) # recursive code constants too
 font=json.loads((ROOT/'distribution/font-source.json').read_text())
 for name,digest in font['files'].items():
  if sha(ROOT/'distribution/fonts'/name)!=digest:raise ValueError('Verified font changed')
 print('Tracked/new source, explicit release inventory, image SHA/privacy and fonts PASS')
 return len(files),len(inventory['files'])
if __name__=='__main__':validate()
