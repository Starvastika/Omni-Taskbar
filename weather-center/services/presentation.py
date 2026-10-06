"""UTC rows, source-aware metrics and weather presentation independent of QML."""
import datetime as dt,time,math
from zoneinfo import ZoneInfo
from services.units import convert,pretty,stamp,condition,date_label,column_converter,formatted_number
LABELS={'temperature_2m':'Temperature','apparent_temperature':'Feels like','relative_humidity_2m':'Humidity','dew_point_2m':'Dew point','precipitation':'Precipitation','precipitation_probability':'Rain probability','rain':'Rain','showers':'Showers','snowfall':'Snowfall','snow_depth':'Snow depth','pressure_msl':'Sea-level pressure','surface_pressure':'Surface pressure','cloud_cover':'Cloud cover','cloud_cover_low':'Low cloud','cloud_cover_mid':'Mid cloud','cloud_cover_high':'High cloud','visibility':'Visibility','uv_index':'UV index','cape':'CAPE','wind_speed_10m':'Wind','wind_direction_10m':'Wind direction','wind_gusts_10m':'Gust','wind_speed_80m':'Wind · 80 m','wind_speed_120m':'Wind · 120 m','shortwave_radiation':'Solar radiation · GHI','direct_normal_irradiance':'Solar radiation · DNI','diffuse_radiation':'Solar radiation · DHI','vapour_pressure_deficit':'Vapour pressure deficit','et0_fao_evapotranspiration':'Reference evapotranspiration','soil_temperature_0cm':'Soil temperature · surface','soil_temperature_6cm':'Soil temperature · 6 cm','soil_temperature_18cm':'Soil temperature · 18 cm','soil_temperature_54cm':'Soil temperature · 54 cm','soil_moisture_0_to_1cm':'Soil moisture · 0–1 cm','soil_moisture_1_to_3cm':'Soil moisture · 1–3 cm','soil_moisture_3_to_9cm':'Soil moisture · 3–9 cm','freezing_level_height':'Freezing level','us_aqi':'US AQI','european_aqi':'European AQI','pm2_5':'PM2.5','pm10':'PM10','ozone':'Ozone','nitrogen_dioxide':'Nitrogen dioxide','sulphur_dioxide':'Sulphur dioxide','carbon_monoxide':'Carbon monoxide','dust':'Dust','aerosol_optical_depth':'Aerosol optical depth','alder_pollen':'Alder pollen','birch_pollen':'Birch pollen','grass_pollen':'Grass pollen','mugwort_pollen':'Mugwort pollen','olive_pollen':'Olive pollen','ragweed_pollen':'Ragweed pollen','wave_height':'Wave height','wave_direction':'Wave direction','wave_period':'Wave period','wind_wave_height':'Wind wave height','wind_wave_direction':'Wind wave direction','wind_wave_period':'Wind wave period','swell_wave_height':'Swell height','swell_wave_direction':'Swell direction','swell_wave_period':'Swell period','swell_wave_peak_period':'Swell peak period','sea_surface_temperature':'Sea surface temperature','ocean_current_velocity':'Ocean current speed','ocean_current_direction':'Ocean current direction','sea_level_height_msl':'Modeled sea-level height'}
CORE={'temperature_2m','apparent_temperature','relative_humidity_2m','dew_point_2m','precipitation','precipitation_probability','rain','snowfall','snow_depth','pressure_msl','visibility','cloud_cover','wind_speed_10m','wind_direction_10m','wind_gusts_10m','uv_index','us_aqi','european_aqi','pm2_5','pm10'}
def rows(data,kind,loc,prefs):
 part=data.get(kind,{}) or {};units=data.get(kind+'_units',{}) or {};result=[];times=part.get('time',[])
 if not isinstance(times,list):times=[times]
 columns=[(key,series,*column_converter(units.get(key,''),prefs,key)) for key,series in part.items() if key!='time']
 for i,epoch in enumerate(times):
  if not isinstance(epoch,(int,float)):continue
  values={};formatted={}
  for key,series,conversion,unit in columns:
   value=(series[i] if i<len(series) else None) if isinstance(series,list) else series
   if isinstance(value,(int,float)):
    present=conversion(value);values[key]=present;formatted[key]=formatted_number(present,unit,value)
  result.append({'epoch':epoch,'label':stamp(epoch,loc['zone'],prefs['hour24']),'date':date_label(epoch,loc['zone'],prefs),'iso':dt.datetime.fromtimestamp(epoch,dt.UTC).isoformat(),'night':not bool(values.get('is_day',1)),'values':values,'formatted':formatted})
 return result
def metrics(data,loc,prefs,source,now=None):
 now=time.time() if now is None else now;hourly=data.get('hourly',{}) or {};times=hourly.get('time',[]);index=max(0,min(range(len(times)),key=lambda i:abs(times[i]-now))) if times else 0
 current=data.get('current',{}) or {};hu=data.get('hourly_units',{});cu=data.get('current_units',{});result=[]
 for key,title in LABELS.items():
  value=current.get(key);unit=cu.get(key,hu.get(key,''))
  if value is None and key in hourly:value=hourly[key][index] if index<len(hourly[key]) else None
  if value is None:continue
  present,punit=convert(value,unit,prefs,key)
  if present is None:continue
  result.append({'key':key,'label':title,'value':pretty(value,unit,prefs,key=key),'number':present,'unit':punit,'rawUnit':unit,'rawValue':value,'source':source,'advanced':key not in CORE})
 return result
def forecast_presentation(bundle,air,loc,prefs,now=None):
 now=time.time() if now is None else now;data=bundle.get('data') or {};aq=air.get('data') or {};zone=loc.get('zone','UTC');local=dt.datetime.fromtimestamp(now,ZoneInfo(zone))
 allrows=rows(data,'hourly',loc,prefs);airrows=rows(aq,'hourly',loc,prefs);air_by_epoch={r['epoch']:r for r in airrows}
 for row in allrows:
  air_row=air_by_epoch.get(row['epoch'],{})
  for key,value in air_row.get('values',{}).items():
   if key not in row['values']:row['values'][key]=value;row['formatted'][key]=air_row['formatted'][key]
 hourly=[r for r in allrows if r['epoch']>=now-3600];daily=[]
 for row in rows(data,'daily',loc,prefs):
  v=row['values'];f=row['formatted'];weather=condition(v.get('weather_code'))
  if dt.datetime.fromtimestamp(row['epoch'],ZoneInfo(zone)).date()<local.date():continue
  for key in ('sunrise','sunset'):
   if key in v:f[key]=stamp(v[key],zone,prefs['hour24'])
  daily.append({**row,'condition':weather[0],'icon':weather[1],'min':f.get('temperature_2m_min','—'),'max':f.get('temperature_2m_max','—'),'rain':f.get('precipitation_sum','Unavailable'),'probability':f.get('precipitation_probability_max','Unavailable'),'wind':f.get('wind_speed_10m_max','Unavailable'),'gust':f.get('wind_gusts_10m_max','Unavailable'),'uv':f.get('uv_index_max','Unavailable'),'sunrise':f.get('sunrise','Unavailable'),'sunset':f.get('sunset','Unavailable'),'daylight':f"{v.get('daylight_duration',0)/3600:.1f} h" if 'daylight_duration' in v else 'Unavailable'})
 wm=metrics(data,loc,prefs,'Open-Meteo · forecast model',now);am=metrics(aq,loc,prefs,'Open-Meteo / CAMS · air-quality model',now);metric_map={x['key']:x for x in wm+am};current=data.get('current',{})
 code=current.get('weather_code');c=condition(code);age=max(0,now-bundle.get('saved',0));stale=bool(bundle.get('stale',True)) or age>900
 summary={'location':loc.get('name','Choose a location'),'region':', '.join(x for x in (loc.get('region'),loc.get('country')) if x),'localTime':date_label(now,zone,prefs)+' · '+stamp(now,zone,prefs['hour24']),'temperature':metric_map.get('temperature_2m',{}).get('value','—'),'apparent':metric_map.get('apparent_temperature',{}).get('value','Unavailable'),'condition':c[0],'icon':c[1],'day':bool(current.get('is_day',1)),'high':daily[0]['max'] if daily else '—','low':daily[0]['min'] if daily else '—','age':f'{int(age//60)} min old' if bundle.get('saved') else 'Not loaded','stale':stale,'refresh':dt.datetime.fromtimestamp(bundle['saved'],dt.UTC).isoformat() if bundle.get('saved') else 'Never','model':bundle.get('model',prefs['model']),'provider':'Open-Meteo · modeled current conditions','error':bundle.get('error',''),'epoch':current.get('time'),'aqi':metric_map.get(prefs['aqi'],{}).get('value','Unavailable'),'sunrise':daily[0]['sunrise'] if daily else 'Unavailable','sunset':daily[0]['sunset'] if daily else 'Unavailable','daylight':daily[0]['daylight'] if daily else 'Unavailable'}
 notable=[]
 if len(hourly)>6:
  a=hourly[0]['values'];b=hourly[6]['values']
  if a.get('temperature_2m') is not None and b.get('temperature_2m') is not None:
   delta=b['temperature_2m']-a['temperature_2m'];threshold=prefs['notableTemperature']*(1.8 if prefs['temperature']=='F' else 1)
   if abs(delta)>=threshold:notable.append(f'Temperature {"rises" if delta>0 else "falls"} {abs(delta):.1f}° over the next 6 hours.')
  wet=next((r for r in hourly[:12] if r['values'].get('precipitation',0)>0),None)
  if wet:notable.append('Modeled precipitation at '+wet['date']+' '+wet['label']+'.')
  likely=next((r for r in hourly[:24] if r['values'].get('precipitation_probability',0)>=prefs['precipThreshold']),None)
  if likely:notable.append(f"Precipitation probability reaches your {prefs['precipThreshold']:.0f}% display threshold at {likely['label']} (model guidance).")
  if a.get('pressure_msl') is not None and b.get('pressure_msl') is not None:notable.append(f"Pressure trend over 6 h: {b['pressure_msl']-a['pressure_msl']:+.1f} {metric_map.get('pressure_msl',{}).get('unit','')}.")
 metadata={'endpoint':bundle.get('source',''),'model':bundle.get('model',prefs['model']),'sourceType':'Forecast model, not station observation','timezone':zone,'requestedCoordinates':[loc.get('lat'),loc.get('lon')],'gridCoordinates':[data.get('latitude'),data.get('longitude')],'elevation':data.get('elevation'),'generationTimeMs':data.get('generationtime_ms'),'modelRunTime':'Not supplied by this endpoint; generationtime_ms is processing duration','cacheTime':summary['refresh'],'units':data.get('hourly_units',{})}
 series=[{'key':k,'label':LABELS.get(k,k),'unit':convert(0,u,prefs,k)[1]} for k,u in data.get('hourly_units',{}).items() if k not in ('time','is_day','weather_code')]
 series.extend({'key':k,'label':LABELS.get(k,k)+' · CAMS','unit':convert(0,u,prefs,k)[1]} for k,u in aq.get('hourly_units',{}).items() if k!='time' and k not in data.get('hourly_units',{}) and any(r['values'].get(k) is not None for r in airrows))
 return {'summary':summary,'metrics':wm+am,'hourly':hourly,'daily':daily,'minute':rows(data,'minutely_15',loc,prefs),'airRows':airrows,'allHourly':allrows,'notable':notable,'metadata':metadata,'series':series}
