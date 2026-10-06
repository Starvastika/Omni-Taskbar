import os,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from watchdog_host import retry_delay,lease_valid,companion_valid,user_sid,info
class WatchdogTests(unittest.TestCase):
 def test_bounded_original_backoff(self):
  self.assertEqual([retry_delay(i) for i in range(1,8)],[30,60,120,240,300,300,300])
 def test_dead_or_recycled_lease_owner_rejected(self):
  lease={'expires':200,'created':100}
  self.assertTrue(lease_valid(lease,{'path':'owned','started':90},150))
  self.assertFalse(lease_valid(lease,{'path':'owned','started':110},150))
  self.assertFalse(lease_valid(lease,{'path':'','started':90},150))
  self.assertFalse(lease_valid(lease,{'path':'owned','started':0},150))
  self.assertFalse(lease_valid(lease,{'path':'owned','started':90},210))
 def test_native_current_user_and_process_lifetime(self):
  self.assertTrue(user_sid().startswith('S-1-'))
  value=info(os.getpid());self.assertTrue(value['path']);self.assertGreater(value['started'],0)
 def test_companion_lifetime_script_session_validation(self):
  record={'path':'owned','session':1,'started':100};host={'started':100,'script':'expected'}
  self.assertTrue(companion_valid(record,host,'OWNED','expected',1))
  self.assertFalse(companion_valid(record,host,'other','expected',1))
  self.assertFalse(companion_valid(record,host,'owned','other',1))
  self.assertFalse(companion_valid(record,host,'owned','expected',2))
  self.assertFalse(companion_valid(record,{'started':1,'script':'expected'},'owned','expected',1))
if __name__=='__main__':unittest.main()
