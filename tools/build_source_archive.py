"""Binary-adjacent corresponding source with explicit privacy-reviewed inputs."""
import hashlib,json,subprocess,urllib.request,zipfile
from pathlib import Path
from release_package import privacy
ROOT=Path(__file__).resolve().parents[1]
def build():
 metadata=json.loads((ROOT/'version.json').read_text());version=metadata['version'];cache=ROOT/'.validation/omni-installer/source-inputs';cache.mkdir(parents=True,exist_ok=True)
 files={}
 names=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=ROOT).decode().split('\0')
 forbidden={'.validation','.runtime','stable-v1','dist','.git','data','cache','logs','exports','__pycache__','.venv'}
 for name in names:
  if not name:continue
  p=ROOT/name
  if not p.is_file() or any(x in forbidden for x in p.relative_to(ROOT).parts):raise ValueError('Unsafe source input: '+name)
  if p.suffix.lower() in ('.pyc','.log','.pfx','.key','.pem'):raise ValueError('Private source input')
  files['omni/'+name]=p.read_bytes()
 privacy(files)
 for entry in json.loads((ROOT/'distribution/source-access.json').read_text()):
  if entry['name']=='Qt':continue # Exact complete official sources linked adjacent to binary release.
  path=cache/(entry['name'].replace('/','-')+'-'+entry['version']+'-source'+('.tar.xz' if entry['url'].endswith('.tar.xz') else '.tar.gz'))
  if not path.exists():urllib.request.urlretrieve(entry['url'],path)
  if hashlib.sha256(path.read_bytes()).hexdigest()!=entry['sha256']:raise ValueError('Corresponding source checksum mismatch')
  files['upstream/'+path.name]=path.read_bytes()
 output=ROOT/'dist'/('omni-taskbar-'+version+'-source.zip')
 with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
  for name,data in sorted(files.items()):
   info=zipfile.ZipInfo(name,(2026,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,data)
 print('Corresponding source archive',output.name,len(files),'files')
 return output
if __name__=='__main__':build()
