"""Build and validate a complete offline consumer installer and separate updater."""
from pathlib import Path
import json
from build_installer import build as installer
from release_package import build as package
from validate_release import validate
from build_source_archive import build as source
from reproduce_runtime_base import verify
from engine import sha
from release_privacy import validate as privacy_gate
ROOT=Path(__file__).resolve().parents[1]
if __name__=='__main__':
 setup=installer();package();validate();privacy_gate()
 verify(ROOT/'.validation/omni-installer/native/lib/library.zip',ROOT/'dist/reproduced-base.zip')
 src=source();metadata=json.loads((ROOT/'version.json').read_text());update=ROOT/'dist'/('omni-taskbar-'+metadata['version']+'-update.zip')
 assets=[setup,update,src,ROOT/'dist/release-manifest.json']
 (ROOT/'dist/SHA256SUMS.txt').write_text(''.join(sha(p)+'  '+p.name+'\n' for p in assets),'utf-8')
 print('Full installer, compact update, corresponding source, manifest and checksums ready')
