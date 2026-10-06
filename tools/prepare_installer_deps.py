"""Verified official inputs; runs at build time, never on an end user's setup."""
import hashlib,json,subprocess,sys,urllib.request,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/'.validation/omni-installer/deps'
def acquire(kind):
 metadata=json.loads((ROOT/'distribution/dependencies.json').read_text('utf-8'))[kind]
 CACHE.mkdir(parents=True,exist_ok=True);target=CACHE/metadata['url'].rsplit('/',1)[-1]
 if not target.exists() or hashlib.sha256(target.read_bytes()).hexdigest()!=metadata['sha256']:
  urllib.request.urlretrieve(metadata['url'],target)
 if hashlib.sha256(target.read_bytes()).hexdigest()!=metadata['sha256']:raise ValueError('Official '+kind+' checksum mismatch')
 return target
def prepare():
 python=acquire('python');acquire('inno')
 wheels=CACHE/'wheels';wheels.mkdir(exist_ok=True)
 subprocess.run([sys.executable,'-m','pip','download','--only-binary=:all:','--dest',str(wheels),'-r',str(ROOT/'time-center/requirements.txt'),'PyYAML==6.0.3'],check=True)
 # Pin every wheel hash from the primary package index, not a private environment.
 inventory={}
 for wheel in wheels.glob('*.whl'):
  name,version=wheel.name.split('-')[:2]
  with urllib.request.urlopen(f'https://pypi.org/pypi/{name}/{version}/json',timeout=20) as r:metadata=json.load(r)
  record=next(x for x in metadata['urls'] if x['filename']==wheel.name)
  digest=hashlib.sha256(wheel.read_bytes()).hexdigest()
  if digest!=record['digests']['sha256']:raise ValueError('Wheel checksum mismatch')
  inventory[wheel.name]={'sha256':digest,'url':record['url'],'package':name,'version':version}
 (CACHE/'wheels.json').write_text(json.dumps(inventory,indent=2),'utf-8')
 print('Verified official Python, Inno and',len(inventory),'dependency wheels')
 return CACHE
if __name__=='__main__':prepare()
