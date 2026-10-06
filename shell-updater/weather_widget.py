"""Extends the installed compact card; no second location picker or fetcher."""
exec('__YASB_BASE_CODE__')
import copy,json,sys,time
from pathlib import Path
sys.path.insert(0,str(Path.home()/'.config/yasb/shell-updater'))
from weather_service import SharedWeather,identity
_InstalledOpenMeteoWidget=OpenMeteoWidget
class OpenMeteoWidget(_InstalledOpenMeteoWidget):
 def __init__(self,config):
  super().__init__(config);self.shared=SharedWeather.instance()
  self.register_callback('weather_center',lambda:self.shared.open(not bool(self._location_data)))
  self.callback_left='weather_center';self.shared.changed.connect(self.adopt_shared)
 def _deferred_init(self):
  self._widget_id=get_widget_id(self);self.adopt_shared(self.shared.snapshot)
  _InstalledOpenMeteoWidget._pending_init_count=max(0,_InstalledOpenMeteoWidget._pending_init_count-1)
 def adopt_shared(self,value):
  loc=value.get('location') or {}
  old=identity(self._location_data);new=identity(loc)
  if old!=new:
   self._weather_data=None;self._has_valid_weather_data=False;self._hourly_data=[[] for _ in range(self.config.forecast_days)]
   dialog=getattr(self,'dialog',None)
   if dialog:dialog.hide()
  self._location_data=dict(loc,latitude=loc.get('lat'),longitude=loc.get('lon'),timezone=loc.get('zone')) if loc else None
  if not loc:self._set_label_text('Setup location');set_tooltip(self,'Choose a location in Weather Center');return
  self.config.units='imperial' if value.get('prefs',{}).get('temperature')=='F' else 'metric'
  data=copy.deepcopy(value.get('data') or {})
  if self.config.units=='imperial':
   for section in ('current','hourly','daily'):
    for key,val in list(data.get(section,{}).items()):
     if 'temperature' in key:
      data[section][key]=[None if x is None else x*9/5+32 for x in val] if isinstance(val,list) else None if val is None else val*9/5+32
     elif key.startswith(('wind_speed','wind_gust')):
      data[section][key]=[None if x is None else x/1.609344 for x in val] if isinstance(val,list) else None if val is None else val/1.609344
  if data.get('current',{}).get('temperature_2m') is not None and data.get('hourly') and data.get('daily'):
   self.process_weather_data(data)
   if value.get('offline') or value.get('error') or value.get('stale') or time.time()-value.get('saved',0)>900:
    if self._weather_data:self._weather_data['{temp}']+=' ·'
   self._update_label(True)
  else:self._set_label_text(loc['name']+' · '+('Offline' if value.get('offline') or value.get('error') else 'Loading…'))
  age=int(max(0,time.time()-value.get('saved',0))//60) if value.get('saved') else None
  status='Offline' if value.get('offline') else 'Weather unavailable' if value.get('error') else 'Stale' if value.get('stale') or (age is not None and age>15) else 'Current'
  set_tooltip(self,loc['name']+' · '+status+(' · '+str(age)+' min old' if age is not None else '')+'\n'+loc.get('zone','UTC'))
 def _start_weather_fetcher(self,*_,**__):pass
 def _show_location_setup(self):
  if getattr(self,'dialog',None):self.dialog.hide()
  self.shared.open(True)
 def reset_location(self,*_):self.shared.open(True)
