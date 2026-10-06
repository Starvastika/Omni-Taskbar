import os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from engine import atomic
from installer_backend import configure
class RepairDataTests(unittest.TestCase):
 def test_missing_config_and_missing_styles_repaired_independently(self):
  with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{},clear=False):
   root=Path(tmp)/'program';data=Path(tmp)/'user'
   defaults=root/'distribution/defaults';defaults.mkdir(parents=True)
   (defaults/'config.yaml').write_text('install: "{install_root}"','utf-8');(defaults/'styles.css').write_text('default styles','utf-8')
   atomic(root/'version.json',{'version':'1.0.0','updater_version':'1.0.0','repository':'Starvastika/Omni-Taskbar'})
   configure(root,data,'check');(data/'styles.css').write_text('custom styles','utf-8');(data/'config.yaml').unlink()
   configure(root,data,'automatic');self.assertEqual((data/'styles.css').read_text(),'custom styles')
   config=(data/'config.yaml').read_bytes();(data/'styles.css').unlink();configure(root,data,'manual')
   self.assertEqual((data/'config.yaml').read_bytes(),config);self.assertEqual((data/'styles.css').read_text(),'default styles')
   self.assertEqual(__import__('json').loads((data/'shell-updater/data/state.json').read_text())['mode'],'check')
