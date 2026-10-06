import importlib.util,json,os,tempfile,sys,unittest,time,datetime as dt,site
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
site.addsitedir(str(ROOT/'time-center/.venv/Lib/site-packages'))
sys.path[:0]=[str(ROOT/'weather-center/vendor'),str(ROOT/'weather-center')]
from services.compact import project
from services.state import location,StateStore,AtomicWriter,default_state
class WeatherTests(unittest.TestCase):
 def setUp(self):
  self.selected=location({'id':'fixture','name':'Fixture','lat':0,'lon':0,'zone':'UTC'})
  self.state=default_state(self.selected);self.state['prefs']['offline']=True
 def test_projection_identity_and_offline(self):
  p=project(self.state,{'error':'offline'},4);self.assertEqual(p['location']['id'],'fixture');self.assertTrue(p['offline']);self.assertEqual(p['generation'],4)
 def test_projection_units_and_time(self):
  now=time.time();source={'current':{'time':now,'wind_speed_10m':10},'hourly':{'time':[now],'wind_speed_10m':[None]}}
  p=project(self.state,{'data':source},1);self.assertEqual(p['data']['current']['wind_speed_10m'],36)
  self.assertEqual(p['data']['current']['time'],dt.datetime.fromtimestamp(now,dt.UTC).strftime('%Y-%m-%dT%H:%M'))
  self.assertEqual(p['data']['hourly']['wind_speed_10m'],[None]);self.assertEqual(source['current']['wind_speed_10m'],10)
 def test_unconfigured_is_explicit(self):
  p=project(default_state(),{},0);self.assertFalse(p['location']);self.assertEqual(p['data'],{})
 def test_invalid_coordinates_rejected(self):
  with self.assertRaises(ValueError):location({'lat':100,'lon':0,'zone':'UTC'})
 def test_saved_locations_not_copied_into_projection(self):
  self.state['locations'].append(location({'name':'Private saved','lat':20,'lon':10,'zone':'UTC'}))
  self.assertNotIn('locations',project(self.state,{},1))
 def test_state_precedence_and_legacy_migration(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);weather=root/'weather-center';weather.mkdir();local=root/'local';(local/'YASB').mkdir(parents=True)
   (root/'config.yaml').write_text('widgets:\n  weather:\n    type: yasb.open_meteo.OpenMeteoWidget\n')
   (local/'YASB/weather.json').write_text(json.dumps({'weather':{'name':'Old','latitude':10,'longitude':10,'timezone':'UTC'}}))
   old=os.environ.get('LOCALAPPDATA');os.environ['LOCALAPPDATA']=str(local);writer=AtomicWriter()
   try:
    store=StateStore(weather,writer);self.assertEqual(store.state['selected']['name'],'Old')
    (weather/'data').mkdir();(weather/'data/state.json').write_text(json.dumps(self.state))
    store=StateStore(weather,writer);self.assertEqual(store.state['selected']['id'],'fixture');self.assertEqual(store.state['locations'],self.state['locations'])
   finally:
    writer.close()
    if old is None:os.environ.pop('LOCALAPPDATA',None)
    else:os.environ['LOCALAPPDATA']=old
if __name__=='__main__':unittest.main()
