"""Central presentation conversion from provider metric/SI values."""
import datetime as dt,math
from zoneinfo import ZoneInfo
from functools import lru_cache

@lru_cache(maxsize=8192)
def _date_label(epoch,zone,pattern):
 return dt.datetime.fromtimestamp(epoch,ZoneInfo(zone)).strftime(pattern)
def date_label(epoch,zone,prefs):
 pattern={'ddd dd MMM':'%a %d %b','yyyy-MM-dd':'%Y-%m-%d','MM/dd/yyyy':'%m/%d/%Y'}.get(prefs.get('dateFormat'),'%a %d %b')
 return _date_label(epoch,zone,pattern)

def column_converter(unit,prefs,key=''):
 """Resolve a column's conversion once; retain the canonical arithmetic order."""
 target=unit;transform=lambda v:v
 if unit=='°C' and prefs['temperature']=='F':target='°F';transform=lambda v:v*9/5+32
 elif unit=='m/s':
  target=prefs['wind'];factor={'m/s':1,'km/h':3.6,'mph':2.236936292,'knots':1.943844492}[target];transform=lambda v:v*factor
 elif unit=='hPa':
  target=prefs['pressure'];factor={'hPa':1,'kPa':.1,'mmHg':.750061683,'inHg':.029529983}[target];transform=lambda v:v*factor
 elif unit=='mm' and prefs['precipitation']=='in':target='in';transform=lambda v:v/25.4
 elif unit=='cm' and prefs['precipitation']=='in':target='in';transform=lambda v:v/2.54
 elif unit=='m' and key=='visibility':
  target='mi' if prefs['visibility']=='mi' else 'km';divisor=1609.344 if target=='mi' else 1000;transform=lambda v:v/divisor
 elif unit=='m' and prefs.get('distance')=='imperial':target='ft';transform=lambda v:v*3.280839895
 def apply(value):
  value=float(value)
  return transform(value) if math.isfinite(value) else None
 return apply,target

def formatted_number(value,unit,raw=None):
 if unit in ('iso8601','unixtime'):return str(raw)
 if value is None:return 'Unavailable'
 return (f'{value:.0f} {unit}' if unit in ('%','°','W/m²','J/kg','AQI') else f'{value:.1f} {unit}').strip()
def convert(value,unit,prefs,key=''):
 if value is None:return None,unit
 value=float(value)
 if not math.isfinite(value):return None,unit
 if unit=='°C' and prefs['temperature']=='F':return value*9/5+32,'°F'
 if unit=='m/s':
  target=prefs['wind'];return value*{'m/s':1,'km/h':3.6,'mph':2.236936292,'knots':1.943844492}[target],target
 if unit=='hPa':
  target=prefs['pressure'];return value*{'hPa':1,'kPa':.1,'mmHg':.750061683,'inHg':.029529983}[target],target
 if unit=='mm' and prefs['precipitation']=='in':return value/25.4,'in'
 if unit=='cm' and prefs['precipitation']=='in':return value/2.54,'in'
 if unit=='m' and key=='visibility':return (value/1609.344,'mi') if prefs['visibility']=='mi' else (value/1000,'km')
 if unit=='m' and prefs.get('distance')=='imperial':return value*3.280839895,'ft'
 return value,unit
def pretty(value,unit,prefs,precision=1,key=''):
 if value is None:return 'Unavailable'
 if unit in ('iso8601','unixtime'):return str(value)
 try:value,unit=convert(value,unit,prefs,key)
 except (ValueError,TypeError):return str(value)
 if value is None:return 'Unavailable'
 if unit in ('%','°','W/m²','J/kg','AQI'):precision=0
 return f'{value:.{precision}f} {unit}'.strip()
@lru_cache(maxsize=8192)
def stamp(epoch,zone,hour24=True,date=False):
 if epoch is None:return 'Unavailable'
 value=dt.datetime.fromtimestamp(float(epoch),ZoneInfo(zone))
 return value.strftime('%a %d %b · '+('%H:%M' if hour24 else '%I:%M %p')+' %Z') if date else value.strftime('%H:%M' if hour24 else '%I:%M %p')
CONDITIONS={0:('Clear sky','☀'),1:('Mainly clear','☀'),2:('Partly cloudy','⛅'),3:('Overcast','☁'),45:('Fog','≋'),48:('Rime fog','≋'),51:('Light drizzle','☂'),53:('Drizzle','☂'),55:('Heavy drizzle','☂'),56:('Freezing drizzle','❄'),57:('Heavy freezing drizzle','❄'),61:('Light rain','☂'),63:('Rain','☂'),65:('Heavy rain','☂'),66:('Freezing rain','❄'),67:('Heavy freezing rain','❄'),71:('Light snow','❄'),73:('Snow','❄'),75:('Heavy snow','❄'),77:('Snow grains','❄'),80:('Light showers','☂'),81:('Showers','☂'),82:('Violent showers','☂'),85:('Snow showers','❄'),86:('Heavy snow showers','❄'),95:('Thunderstorm','ϟ'),96:('Thunderstorm with hail','ϟ'),99:('Thunderstorm with heavy hail','ϟ')}
def condition(code):return CONDITIONS.get(code,('Condition unavailable','—'))
