import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import native_taskbar
from engine import atomic
class CutoverTests(unittest.TestCase):
 def test_legacy_developer_shell_untouched(self):
  with tempfile.TemporaryDirectory() as tmp,patch.object(native_taskbar,'state') as state:
   native_taskbar.reserve_native_cutover(Path(tmp),Path(tmp));state.assert_not_called()
 def test_owned_one_shot_cutover_and_restore(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)/'program';data=Path(tmp)/'user';atomic(root/'omni-installed.json',{})
   current=[2];changes=[]
   def state(value=None):
    if value is not None:current[0]=value;changes.append(value)
    return current[0]
   with patch.object(native_taskbar,'state',side_effect=state):
    native_taskbar.reserve_native_cutover(root,data);native_taskbar.reserve_native_cutover(root,data)
    self.assertEqual(changes,[3]);native_taskbar.restore_native_cutover(root,data);self.assertEqual(changes,[3,2])
 def test_manual_user_preference_is_preserved_on_uninstall(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)/'program';data=Path(tmp)/'user';atomic(root/'omni-installed.json',{});atomic(data/'shell-updater/data/native-taskbar.json',{'previous':2,'applied':3})
   with patch.object(native_taskbar,'state',return_value=0) as state:
    native_taskbar.restore_native_cutover(root,data);self.assertEqual(state.call_count,1)
