"""Release gates run after packaging, before any GitHub release upload."""
import json,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'shell-updater'));sys.path.insert(0,str(ROOT/'tools'))
from engine import Updater,read,sha,validate_manifest
from release_package import sources,privacy
def validate():
 manifest=validate_manifest(read(ROOT/'dist/release-manifest.json'));archive=ROOT/'dist'/manifest['asset']
 assert sha(archive)==manifest['sha256'];assert read(ROOT/'version.json')['version']==manifest['version']
 privacy(sources(ROOT))
 validator=object.__new__(Updater);validator.root=ROOT
 with tempfile.TemporaryDirectory() as tmp:
  inventory=validator.extract(archive,Path(tmp)/'extract',manifest['version'])
  assert 'weather-center/services/compact.py' in inventory['files']
  assert 'shell-updater/engine.py' in inventory['files']
  assert '.runtime/yasb-2.0.7/lib/library.zip' in inventory['files']
  assert 'omni_layout.py' in inventory['files']
  assert 'LICENSE' in inventory['files']
  for name in ('time-center/qml/Theme.js','time-center/qml/MapGeometry.js','weather-center/qml/components/Theme.js'):
   assert name in inventory['files']
 print('Release version, SHA-256, privacy, inventory, extraction and required components PASS')
if __name__=='__main__':validate()
