import json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from omni_layout import program_root,user_root,component_data,child_environment
class LayoutTests(unittest.TestCase):
 def test_explicit_program_root_is_authoritative_even_inside_another_installation(self):
  with tempfile.TemporaryDirectory() as tmp:
   first=Path(tmp)/'first';second=Path(tmp)/'second';first.mkdir();second.mkdir()
   (first/'omni-installed.json').write_text(json.dumps({'user_root':str(Path(tmp)/'first-data')}))
   with patch.dict(os.environ,{'OMNI_PROGRAM_ROOT':str(first)},clear=True):
    self.assertEqual(program_root(),first);self.assertEqual(program_root(second),second)
    self.assertEqual(user_root(first),Path(tmp)/'first-data');self.assertEqual(user_root(second),second)
    self.assertEqual(child_environment(second)['YASB_CONFIG_HOME'],str(second))
 def test_explicit_user_profile_routes_components_and_child_configuration(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)/'program';data=Path(tmp)/'data'
   with patch.dict(os.environ,{'OMNI_USER_ROOT':str(data)},clear=True):
    self.assertEqual(component_data('weather-center',root),data/'weather-center')
    self.assertEqual(child_environment(root)['YASB_CONFIG_HOME'],str(data))
 def test_legacy_checkout_paths_unchanged(self):
  with patch.dict(os.environ,{'USERPROFILE':str(Path.home())},clear=True):
   root=Path.home()/'.config/yasb';self.assertEqual(component_data('time-center'),root/'time-center')
