"""Documented provider adapters. All requests pass through the central client."""
import re,unicodedata
from urllib.parse import urlencode
from services.state import location
FORECAST='https://api.open-meteo.com/v1/forecast'
CURRENT=['temperature_2m','relative_humidity_2m','apparent_temperature','is_day','precipitation','rain','showers','snowfall','weather_code','cloud_cover','pressure_msl','surface_pressure','wind_speed_10m','wind_direction_10m','wind_gusts_10m']
HOURLY=CURRENT+['dew_point_2m','precipitation_probability','snow_depth','cloud_cover_low','cloud_cover_mid','cloud_cover_high','visibility','uv_index','cape','shortwave_radiation','direct_normal_irradiance','diffuse_radiation','et0_fao_evapotranspiration','vapour_pressure_deficit','soil_temperature_0cm','soil_temperature_6cm','soil_temperature_18cm','soil_temperature_54cm','soil_moisture_0_to_1cm','soil_moisture_1_to_3cm','soil_moisture_3_to_9cm','wind_speed_80m','wind_speed_120m','freezing_level_height']
DAILY=['weather_code','temperature_2m_max','temperature_2m_min','apparent_temperature_max','apparent_temperature_min','sunrise','sunset','daylight_duration','sunshine_duration','precipitation_sum','rain_sum','showers_sum','snowfall_sum','precipitation_probability_max','wind_speed_10m_max','wind_gusts_10m_max','wind_direction_10m_dominant','uv_index_max','shortwave_radiation_sum']
AIR=['us_aqi','european_aqi','pm2_5','pm10','ozone','nitrogen_dioxide','sulphur_dioxide','carbon_monoxide','dust','aerosol_optical_depth','uv_index','alder_pollen','birch_pollen','grass_pollen','mugwort_pollen','olive_pollen','ragweed_pollen']
MARINE=['wave_height','wave_direction','wave_period','wind_wave_height','wind_wave_direction','wind_wave_period','swell_wave_height','swell_wave_direction','swell_wave_period','swell_wave_peak_period','sea_surface_temperature','ocean_current_velocity','ocean_current_direction','sea_level_height_msl']
MODELS=[{'id':'best_match','name':'Best Match','region':'Worldwide; highest applicable resolution','resolution':'Model-dependent','horizon':'Up to 16 days'}, {'id':'ecmwf_ifs025','name':'ECMWF IFS 0.25°','region':'Global','resolution':'~25 km','horizon':'15 days'}, {'id':'gfs_seamless','name':'NOAA GFS / HRRR','region':'Global / North America','resolution':'3–25 km','horizon':'16 days'}, {'id':'gem_seamless','name':'ECCC GEM','region':'Global / Canada','resolution':'2.5–25 km','horizon':'10 days'}, {'id':'icon_seamless','name':'DWD ICON','region':'Global / Europe','resolution':'2–11 km','horizon':'7.5 days'}]
def url(endpoint,params):return endpoint+'?'+urlencode(params)
def coordinates(loc):return {'latitude':loc['lat'],'longitude':loc['lon'],'timezone':loc.get('zone','auto'),'timeformat':'unixtime'}
def fold(text):return ''.join(c for c in unicodedata.normalize('NFKD',text).casefold() if not unicodedata.combining(c))
class Providers:
 def __init__(self,http):self.http=http
 def forecast(self,loc,prefs,callback,force=False,group='selected'):
  params={**coordinates(loc),'current':','.join(CURRENT),'hourly':','.join(HOURLY),'daily':','.join(DAILY),'forecast_days':max(7,min(16,int(prefs['forecastDays']))),'past_days':1,'wind_speed_unit':'ms','minutely_15':'temperature_2m,precipitation,rain,snowfall,wind_speed_10m','forecast_minutely_15':24}
  if prefs['model']!='best_match':params['models']=prefs['model']
  self.http.request(url(FORECAST,params),900,callback,group,force)
 def air(self,loc,callback,force=False,group='selected'):
  p={**coordinates(loc),'current':','.join(AIR[:11]),'hourly':','.join(AIR),'forecast_days':5}
  self.http.request(url('https://air-quality-api.open-meteo.com/v1/air-quality',p),1800,callback,group,force)
 def marine(self,loc,callback,force=False):
  p={**coordinates(loc),'hourly':','.join(MARINE),'current':','.join(MARINE),'forecast_days':7,'cell_selection':'nearest','wind_speed_unit':'ms'}
  self.http.request(url('https://marine-api.open-meteo.com/v1/marine',p),3600,callback,'advanced:marine',force)
 def history(self,loc,start,end,callback,force=False):
  p={**coordinates(loc),'start_date':start,'end_date':end,'models':'era5','hourly':'temperature_2m,relative_humidity_2m,dew_point_2m,precipitation,snowfall,pressure_msl,wind_speed_10m','daily':'temperature_2m_max,temperature_2m_min,temperature_2m_mean,precipitation_sum,snowfall_sum,wind_speed_10m_max','wind_speed_unit':'ms'}
  self.http.request(url('https://archive-api.open-meteo.com/v1/archive',p),86400,callback,'history',force)
 def models(self,loc,callback,force=False):
  p={**coordinates(loc),'hourly':'temperature_2m,precipitation,wind_speed_10m,pressure_msl','forecast_days':7,'models':'ecmwf_ifs025,gfs_seamless,gem_seamless,icon_seamless','wind_speed_unit':'ms'}
  self.http.request(url(FORECAST,p),3600,callback,'advanced:models',force)
 def ensemble(self,loc,callback,force=False):
  p={**coordinates(loc),'hourly':'temperature_2m,precipitation,wind_speed_10m','forecast_days':7,'models':'gfs_seamless','wind_speed_unit':'ms'}
  self.http.request(url('https://ensemble-api.open-meteo.com/v1/ensemble',p),3600,callback,'advanced:ensemble',force)
 def runs(self,loc,callback,force=False):
  fields=[v+('_previous_day'+str(offset) if offset else '') for v in ('temperature_2m','precipitation','wind_speed_10m','pressure_msl') for offset in (0,1,2)]
  p={**coordinates(loc),'hourly':','.join(fields),'forecast_days':3,'past_days':0,'models':'gfs_seamless','wind_speed_unit':'ms'}
  self.http.request(url('https://previous-runs-api.open-meteo.com/v1/forecast',p),3600,callback,'advanced:runs',force)
 def geocode(self,query,callback):
  parts=[x.strip() for x in query.split(',') if x.strip()];name=parts[0] if parts else '';regions=parts[1:]
  def complete(result):
   rows=[]
   for record in (result.get('data') or {}).get('results',[]):
    if regions and not all(any(fold(term) in fold(str(record.get(f,''))) for f in ('admin1','admin2','admin3','admin4','country','country_code')) for term in regions):continue
    try:
     record=dict(record)
     record['providerId']=record.get('id');record.pop('id',None);rows.append(location(record,True))
    except (ValueError,TypeError):continue
   callback(rows,result)
  self.http.request(url('https://geocoding-api.open-meteo.com/v1/search',{'name':name,'count':50,'language':'en','format':'json'}),86400,complete,'search')
