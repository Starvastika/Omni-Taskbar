import copy,hashlib,io,json,os,sys,tempfile,unittest,urllib.error,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT.parent/'weather-center/vendor'),str(ROOT.parent/'tools')]
from engine import Updater,Network,atomic,read,sha,safe_name,validate_manifest,semver,lock
from migrations import migrate
from release_package import privacy

class Response(io.BytesIO):
 def __init__(self,data,url,etag='one'):super().__init__(data);self.url=url;self.headers={'ETag':etag}
 def geturl(self):return self.url
class FixtureHTTP:
 def __init__(self,release,manifest,archive):
  self.calls=[];self.release=release;self.manifest=manifest;self.archive=archive;self.failure=None;self.cached=False
 def __call__(self,request,timeout):
  url=request.full_url;self.calls.append((url,dict(request.header_items()),timeout))
  if self.failure:raise self.failure
  if url.endswith('/latest'):
   if self.cached:raise urllib.error.HTTPError(url,304,'cached',{},None)
   data=json.dumps(self.release).encode()
  elif url.endswith('release-manifest.json'):data=json.dumps(self.manifest).encode()
  else:data=self.archive
  return Response(data,url)
class Lifecycle:
 def __init__(self,health=(True,)):self.calls=[];self.answers=list(health);self.expected={'time':True,'weather':True}
 def prepare(self):self.calls.append('prepare')
 def stop(self):self.calls.append('stop')
 def start(self):self.calls.append('start')
 def health(self):self.calls.append('health');return self.answers.pop(0) if len(self.answers)>1 else self.answers[0]

def fixture(version='1.0.1',extra=None):
 files={'version.json':json.dumps({'version':version,'updater_version':'1.0.0','channel':'stable','yasb_version':'2.0.7','repository':'example/shell'}).encode(),
        'README.md':b'new program'}
 if extra:files.update(extra)
 inventory={'version':version,'files':{n:hashlib.sha256(v).hexdigest() for n,v in files.items()}}
 buf=io.BytesIO()
 with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
  for name,value in files.items():z.writestr(name,value)
  z.writestr('package-files.json',json.dumps(inventory))
 archive=buf.getvalue();manifest={'version':version,'minimum_updater_version':'1.0.0','channel':'stable',
  'asset':f'yasb-shell-{version}.zip','sha256':hashlib.sha256(archive).hexdigest(),'requires_shell_restart':True,'requires_windows_restart':False}
 base=f'https://github.com/example/shell/releases/download/v{version}/'
 release={'tag_name':'v'+version,'draft':False,'prerelease':False,'body':'Changes <script>not executed</script>',
          'assets':[{'name':manifest['asset'],'browser_download_url':base+manifest['asset']},
                    {'name':'release-manifest.json','browser_download_url':base+'release-manifest.json'}]}
 return FixtureHTTP(release,manifest,archive)

class Tests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
  atomic(self.root/'version.json',{'version':'1.0.0','updater_version':'1.0.0','repository':'example/shell'})
  (self.root/'README.md').write_text('old program')
  (self.root/'config.yaml').write_text("unknown_custom: keep\nwidgets:\n  weather:\n    type: yasb.open_meteo.OpenMeteoWidget\n    options:\n      unknown: preserve\n      callbacks:\n        on_left: old\n")
  for center in ('time','weather'):
   atomic(self.root/(center+'-center/data/state.json'),{'personal':'preserve','saved':[1,2,3]})
  self.original={p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('state.json')}
  self.http=fixture();self.life=Lifecycle();self.engine=Updater(self.root,Network(self.http),self.life)
 def tearDown(self):self.temp.cleanup()
 def assert_data(self):
  for n,value in self.original.items():self.assertEqual((self.root/n).read_bytes(),value)
 def available(self,mode='check'):
  self.engine.mode(mode);self.engine.check(True);return self.engine
 def test_manual_has_no_background_network(self):
  self.engine.mode('manual');self.engine.check();self.assertEqual(self.http.calls,[])
 def test_unset_policy_has_no_background_network(self):
  self.engine.check();self.assertEqual(self.http.calls,[])
 def test_check_mode_notifies_without_download(self):
  self.available();self.assertTrue(self.engine.state['attention']);self.assertNotIn('staged_version',self.engine.state);self.assertEqual(len(self.http.calls),2)
 def test_manual_check_preserves_notification(self):
  self.available('manual');self.assertTrue(Updater(self.root).state['attention'])
 def test_automatic_stages_without_restarting(self):
  self.available('automatic');self.assertEqual(self.engine.state['staged_version'],'1.0.1');self.assertTrue(self.engine.state['attention']);self.assertEqual(self.life.calls,[])
 def test_switch_to_auto_stages_known_available(self):
  self.available('manual');self.engine.mode('automatic');self.assertEqual(self.engine.state.get('staged_version'),'1.0.1');self.assertEqual(self.life.calls,[])
 def test_switch_to_manual_keeps_staged_without_auto_apply(self):
  self.available('automatic');self.engine.mode('manual');self.engine.apply(True);self.assertEqual(read(self.root/'version.json')['version'],'1.0.0')
 def test_failed_release_is_not_automatically_restaged(self):
  self.available('automatic');self.life.answers=[False,True];self.engine.apply(True);self.http.calls.clear();self.engine.check(True)
  self.assertFalse(self.engine.state.get('staged_version'));self.assertEqual(len(self.http.calls),2);self.assertTrue(self.engine.state['attention'])
 def test_check_cadence(self):
  self.available();count=len(self.http.calls);self.engine.check();self.assertEqual(len(self.http.calls),count)
 def test_etag_reuses_release(self):
  self.available();self.http.cached=True;self.engine.check(True);self.assertIn('If-none-match',self.http.calls[-2][1])
 def test_mode_persists(self):
  for mode in ('manual','automatic','check'):
   self.engine.mode(mode);self.assertEqual(Updater(self.root).state['mode'],mode)
 def test_local_end_to_end_success(self):
  self.available();self.engine.stage();self.engine.apply()
  self.assertEqual(read(self.root/'version.json')['version'],'1.0.1');self.assertEqual(self.life.calls,['prepare','stop','start','health'])
  self.assertFalse(self.engine.state['attention']);self.assertFalse((self.engine.data/'maintenance.json').exists());self.assert_data()
 def test_automatic_next_restart_applies(self):
  self.available('automatic');self.engine.apply(True);self.assertEqual(self.engine.state['current_version'],'1.0.1')
 def test_check_mode_natural_restart_does_not_apply(self):
  self.available();self.engine.stage();self.engine.apply(True);self.assertEqual(read(self.root/'version.json')['version'],'1.0.0')
 def test_health_failure_rolls_back(self):
  self.available();self.engine.stage();self.life.answers=[False,True];before=(self.root/'config.yaml').read_bytes();self.engine.apply()
  self.assertEqual(read(self.root/'version.json')['version'],'1.0.0');self.assertEqual((self.root/'README.md').read_text(),'old program')
  self.assertEqual((self.root/'config.yaml').read_bytes(),before);self.assertEqual(self.engine.state['last_update_result'],'rolled_back')
  self.assertTrue(self.engine.state['attention']);self.assertNotIn('transaction',self.engine.state);self.assert_data()
 def test_recent_repeated_crash_rollback(self):
  self.available();self.engine.stage();self.engine.apply();self.engine.rollback_recent()
  self.assertEqual(read(self.root/'version.json')['version'],'1.0.0');self.assertTrue(self.engine.state['failure']);self.assert_data()
 def test_recent_crash_rollback_is_one_shot(self):
  self.available();self.engine.stage();self.engine.apply();self.engine.rollback_recent();count=len(self.life.calls)
  self.engine.rollback_recent();self.assertEqual(len(self.life.calls),count)
 def test_failure_does_not_restart_loop(self):
  self.available('automatic');self.life.answers=[False,True];self.engine.apply(True);count=len(self.life.calls);self.engine.apply(True);self.assertEqual(len(self.life.calls),count)
 def test_migration_failure_rolls_back(self):
  self.available();self.engine.stage();self.engine.migrate=lambda *_:(_ for _ in ()).throw(ValueError('migration fixture'))
  self.engine.apply();self.assertEqual(self.engine.state['last_update_result'],'rolled_back');self.assert_data()
 def test_missing_stage_fails_before_stop(self):
  self.available();self.engine.state['staged_version']='1.0.1';self.engine.apply();self.assertTrue(self.engine.state['failure']);self.assertEqual(self.life.calls,[])
 def test_damaged_stage_fails_before_stop(self):
  self.available();self.engine.stage();(self.engine.data/'staged/README.md').write_text('bad');self.engine.apply();self.assertEqual(self.life.calls,[])
 def test_checksum_mismatch(self):
  self.available();self.http.archive+=b'bad';self.engine.stage();self.assertTrue(self.engine.state['failure']);self.assertFalse((self.engine.data/'staged').exists())
 def test_corrupt_zip(self):
  self.available();self.http.archive=b'not zip';self.engine.state['manifest']['sha256']=hashlib.sha256(self.http.archive).hexdigest()
  self.engine.stage();self.assertTrue(self.engine.state['failure']);self.assertEqual(self.life.calls,[])
 def test_stage_disk_failure(self):
  self.available();self.engine.extract=lambda *_:(_ for _ in ()).throw(OSError('disk fixture'));self.engine.stage();self.assertTrue(self.engine.state['failure']);self.assert_data()
 def test_apply_disk_failure_restores(self):
  self.available();self.engine.stage();real=self.engine.replace;fired=[False]
  def fail(source,target):
   if not fired[0] and target.name=='README.md':fired[0]=True;raise OSError('write fixture')
   return real(source,target)
  self.engine.replace=fail;self.engine.apply();self.assertEqual(self.engine.state['last_update_result'],'rolled_back');self.assert_data()
 def test_github_unavailable_preserves_available(self):
  self.available();self.http.failure=urllib.error.URLError('offline fixture');self.engine.check(True);self.assertTrue(self.engine.state['attention']);self.assertTrue(self.engine.state['available'])
 def test_timeout_nonfatal(self):
  self.http.failure=TimeoutError('timeout fixture');self.engine.check(True);self.assertIn("Couldn't check",self.engine.state['status']);self.assert_data()
 def test_malformed_manifest(self):
  self.http.manifest['version']='unsafe';self.engine.check(True);self.assertNotIn('available',self.engine.state)
 def test_minimum_updater_version(self):
  self.http.manifest['minimum_updater_version']='2.0.0';self.engine.check(True);self.assertNotIn('available',self.engine.state)
 def test_tag_mismatch(self):
  self.http.release['tag_name']='v9.0.0';self.engine.check(True);self.assertNotIn('available',self.engine.state)
 def test_foreign_asset_rejected(self):
  self.http.release['assets'][0]['browser_download_url']='https://example.invalid/a';self.engine.check(True);self.assertNotIn('available',self.engine.state)
 def test_prerelease_rejected(self):
  self.http.release['prerelease']=True;self.engine.check(True);self.assertNotIn('available',self.engine.state)
 def test_no_repository_has_actionable_status(self):
  self.engine.version['repository']=None;self.engine.check(True);self.assertIn('not been configured',self.engine.state['error']);self.assertEqual(self.http.calls,[])
 def test_zip_slip_and_windows_names(self):
  for name in ('../evil','/evil','C:/evil','a\\evil','a/../evil','a/NUL.txt','a/trailing.','data/state.json'):
   with self.subTest(name=name),self.assertRaises(ValueError):safe_name(name)
 def test_user_config_cannot_be_packaged(self):
  self.http=fixture(extra={'config.yaml':b'overwrite'});self.engine.network=Network(self.http);self.available();self.engine.stage();self.assertTrue(self.engine.state['failure'])
 def test_user_state_cannot_be_packaged(self):
  self.http=fixture(extra={'weather-center/data/state.json':b'private'});self.engine.network=Network(self.http);self.available();self.engine.stage();self.assertTrue(self.engine.state['failure']);self.assert_data()
 def test_unowned_file_rejected(self):
  self.http=fixture(extra={'arbitrary.ps1':b'exec'});self.engine.network=Network(self.http);self.available();self.engine.stage();self.assertTrue(self.engine.state['failure'])
 def test_case_colliding_paths_rejected(self):
  self.http=fixture(extra={'readme.md':b'duplicate'});self.engine.network=Network(self.http);self.available();self.engine.stage();self.assertTrue(self.engine.state['failure'])
 def test_invalid_program_syntax_rejected_before_apply(self):
  self.http=fixture(extra={'shell-updater/module.py':b'invalid ! syntax'});self.engine.network=Network(self.http);self.available();self.engine.stage();self.assertTrue(self.engine.state['failure']);self.assertEqual(self.life.calls,[])
 def test_manifest_windows_restart_rejected(self):
  value=copy.deepcopy(self.http.manifest);value['requires_windows_restart']=True
  with self.assertRaises(ValueError):validate_manifest(value)
 def test_https_only(self):
  with self.assertRaises(ValueError):Network().get('http://localhost/test')
 def test_migrations_idempotent_preserve_unknown(self):
  migrate(self.root,'1.0.0','1.0.1');first=(self.root/'config.yaml').read_bytes();migrate(self.root,'1.0.0','1.0.1')
  self.assertEqual(first,(self.root/'config.yaml').read_bytes());self.assertIn(b'unknown_custom: keep',first);self.assertIn(b'unknown: preserve',first);self.assert_data()
 def test_lease_lifecycle(self):
  self.engine.maintenance(True);value=read(self.engine.data/'maintenance.json');self.assertEqual(value['owner'],os.getpid());self.engine.maintenance(False);self.assertFalse((self.engine.data/'maintenance.json').exists())
 def test_operation_lock(self):
  with lock(self.engine.data):
   with self.assertRaises(OSError):
    with lock(self.engine.data):pass
 def test_interrupted_transaction_recovery(self):
  backup=self.engine.data/'rollback/fixture';backup.mkdir(parents=True);(backup/'README.md').write_text('old program')
  (self.root/'README.md').write_text('partial new')
  self.engine.state['transaction']={'backup':'rollback/fixture','records':{'README.md':True},'previous':'1.0.0','target':'1.0.1','expected':self.life.expected}
  self.engine.save();self.engine.recover();self.assertEqual((self.root/'README.md').read_text(),'old program');self.assertTrue(self.engine.state['failure']);self.assert_data()
 def test_privacy_path_scan(self):
  with self.assertRaises(ValueError):privacy({'README.md':('C:'+chr(92)+'Users'+chr(92)+'Example'+chr(92)+'file').encode()})
 def test_semver_validation(self):
  for value in ('v1.0.0','1.0','01.0.0','1.0.0-beta'):
   with self.assertRaises(ValueError):semver(value)
if __name__=='__main__':unittest.main()
