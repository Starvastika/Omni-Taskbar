"""Idempotent additive config migrations, independently versioned from user data."""
import json,sys
from pathlib import Path
from engine import atomic,read,semver

def migrate(root,old,new):
 root=Path(root);semver(old);semver(new)
 if semver(new)<semver(old):raise ValueError('Downgrade migration rejected')
 path=root/'shell-updater/data/migrations.json';state=read(path,{'applied':[]})
 # No wholesale config replacement. The first migration only removes the obsolete
 # weather exec callback; the supported shared callback is registered by our widget.
 if 'shared-weather-1' not in state['applied']:
  config=root/'config.yaml'
  if config.exists():
   sys.path.insert(0,str(root/'weather-center/vendor'))
   import yaml
   value=yaml.safe_load(config.read_text('utf-8'))
   for widget in value.get('widgets',{}).values():
    if widget.get('type')=='yasb.open_meteo.OpenMeteoWidget':
     widget.setdefault('options',{}).setdefault('callbacks',{})['on_left']='weather_center'
   config.write_text(yaml.safe_dump(value,allow_unicode=True,sort_keys=False),'utf-8')
  state['applied'].append('shared-weather-1')
 state['version']=new;atomic(path,state)
