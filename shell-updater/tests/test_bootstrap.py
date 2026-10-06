import hashlib,json,sys,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import bootstrap,engine
from test_engine import fixture,Lifecycle
class BootstrapTests(unittest.TestCase):
 def setup_fixture(self,root):
  runtime=root/'.runtime/yasb-2.0.7';runtime.mkdir(parents=True);(runtime/'yasb.exe').write_text('owned runtime stand-in')
  python=root/'time-center/.venv/Scripts/python.exe';python.parent.mkdir(parents=True);python.write_text('owned dependency stand-in')
  http=fixture('1.0.0',{'distribution/defaults/config.yaml':b'widgets: {}\nroot: "{install_root}"\n',
   'distribution/defaults/styles.css':b'gray styles','distribution/register-startup.ps1':b'# fixture startup',
   'time-center/requirements.txt':b'fixture dependency\n'})
  archive=root/'fixture.zip';archive.write_bytes(http.archive);return archive,http.manifest
 def test_first_install_mode_defaults_and_delayed_startup(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);archive,manifest=self.setup_fixture(root);life=Lifecycle();calls=[]
   def runner(args,**kw):calls.append(args);return types.SimpleNamespace(returncode=0,stdout='False')
   with patch.object(engine,'WindowsLifecycle',lambda _:life),patch.object(bootstrap.subprocess,'run',runner):
    bootstrap.install(root,archive,manifest,'manual')
   self.assertEqual(engine.read(root/'shell-updater/data/state.json')['mode'],'manual')
   self.assertIn(str(root),(root/'config.yaml').read_text());self.assertEqual(life.calls,['start','health'])
   self.assertTrue(any('register-startup.ps1' in ' '.join(map(str,args)) for args in calls))
   self.assertIsNone(engine.read(root/'helpers/watchdog-settings.json')['LhmTask'])
 def test_first_install_health_failure_does_not_register_startup(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);archive,manifest=self.setup_fixture(root);life=Lifecycle((False,));calls=[]
   def runner(args,**kw):calls.append(args);return types.SimpleNamespace(returncode=0,stdout='False')
   with patch.object(engine,'WindowsLifecycle',lambda _:life),patch.object(bootstrap.subprocess,'run',runner),self.assertRaises(RuntimeError):
    bootstrap.install(root,archive,manifest,'check')
   self.assertEqual(life.calls,['start','health','stop'])
   self.assertFalse(any('register-startup.ps1' in ' '.join(map(str,args)) for args in calls))
   self.assertTrue(engine.read(root/'shell-updater/data/state.json')['attention'])
if __name__=='__main__':unittest.main()
