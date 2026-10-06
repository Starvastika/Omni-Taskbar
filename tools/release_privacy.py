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
 # A public upstream binary can contain its publisher's build paths.
 # Admit this only with byte-for-byte provenance from verified public wheels,
 # never by username/path or package-specific exceptions.
 public_binaries={}
 cache=ROOT/'.validation/omni-installer/deps'
 for filename,record in json.loads((cache/'wheels.json').read_text('utf-8')).items():
  wheel=cache/'wheels'/filename
  if sha(wheel)!=record['sha256'] or not record['url'].startswith('https://files.pythonhosted.org/'):raise ValueError('Unverified public wheel')
  with zipfile.ZipFile(wheel) as z:
   for item in z.infolist():
    if item.filename.endswith(('.pyd','.dll')):public_binaries['runtime/python/site-packages/'+item.filename]=hashlib.sha256(z.read(item)).hexdigest()
 native=ROOT/'.validation/omni-installer/native'
 msi=cache/'yasb-2.0.7-x64.msi'
 if sha(msi)!=json.loads((ROOT/'distribution/runtime-base.json').read_text('utf-8'))['native_msi_sha256']:raise ValueError('Unverified upstream YASB')
 for binary in native.rglob('*'):
  if binary.is_file() and binary.suffix.lower() in ('.pyd','.dll','.exe'):
   public_binaries['.runtime/yasb-2.0.7/'+binary.relative_to(native).as_posix()]=sha(binary)
   if binary.parent==native and binary.name.startswith(('vcruntime','msvcp','concrt')):public_binaries['runtime/python/'+binary.name]=sha(binary)
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
  if any(n.lower() in b.lower() for n in needles) and public_binaries.get(name)!=digest:raise ValueError('Private developer path in image: '+name)
  if name.endswith('library.zip'):sanitized_library(p) # recursive code constants too
 font=json.loads((ROOT/'distribution/font-source.json').read_text())
 for name,digest in font['files'].items():
  if sha(ROOT/'distribution/fonts'/name)!=digest:raise ValueError('Verified font changed')
 print('Tracked/new source, explicit release inventory, image SHA/privacy and fonts PASS')
 return len(files),len(inventory['files'])
if __name__=='__main__':validate()
