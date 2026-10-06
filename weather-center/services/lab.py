"""Explicitly calculated utilities, metric inputs and documented applicability."""
import math,datetime as dt
from services.units import stamp
def number(data,key,low=-1e6,high=1e6):
 value=float(data[key])
 if not math.isfinite(value) or not low<=value<=high:raise ValueError(f'{key} must be between {low} and {high}')
 return value
def calculate(data,zone):
 tool=data['tool'];a=number(data,'a');b=number(data,'b') if 'b' in data else 0
 result='';formula='';url=''
 if tool in ('Dew point','Relative humidity','Humidex'):
  if not -80<a<80:raise ValueError('Temperature must be between −80 and 80 °C')
  if tool=='Dew point':
   if not 0<b<=100:raise ValueError('Relative humidity must be greater than 0 and at most 100%')
   gamma=math.log(b/100)+17.26938819745534*a/(237.3+a);td=237.3*gamma/(17.26938819745534-gamma);result=f'{td:.2f} °C';formula='Magnus approximation: γ = ln(RH/100) + 17.26938819745534T/(237.3+T); Td = 237.3γ/(17.26938819745534−γ). Liquid-water approximation; limited accuracy below freezing.'
  elif tool=='Relative humidity':
   if not -100<b<=a:raise ValueError('Dew point must be at or below air temperature and above −100 °C')
   result=f'{100*math.exp(17.26938819745534*b/(237.3+b)-17.26938819745534*a/(237.3+a)):.2f} %';formula='Magnus saturation vapor-pressure ratio, 100 exp[17.26938819745534Td/(237.3+Td) − 17.26938819745534T/(237.3+T)].'
  else:
   if not -100<b<=a:raise ValueError('Dew point must not exceed temperature')
   vapor=6.11*math.exp(5417.7530*(1/273.16-1/(273.15+b)));result=f'{a+.5555*(vapor-10):.2f}';formula='Canadian humidex: H = T + 0.5555(e−10), e = 6.11 exp[5417.7530(1/273.16−1/(273.15+Td))]. Dimensionless perceived-heat index, not actual temperature.'
  url='https://www.weather.gov/media/epz/wxcalc/vaporPressure.pdf' if tool!='Humidex' else 'https://climate.weather.gc.ca/glossary_e.html#h'
 elif tool=='Wind chill':
  if a>10 or b<4.8:raise ValueError('Wind chill applies only at ≤10 °C and wind ≥4.8 km/h')
  if b>300:raise ValueError('Wind speed exceeds supported input range')
  result=f'{13.12+.6215*a-11.37*b**.16+.3965*a*b**.16:.2f} °C';formula='NWS / Canadian wind chill: 13.12 + 0.6215T − 11.37V^0.16 + 0.3965TV^0.16; T °C, V km/h. Calculated index.';url='https://www.weather.gov/media/epz/wxcalc/windChill.pdf'
 elif tool=='Heat index':
  if not 26.7<=a<=50 or not 0<=b<=100:raise ValueError('Rothfusz heat index requires temperature 26.7–50 °C and RH 0–100%; use air temperature outside this range')
  t=a*1.8+32;r=b;hi=-42.379+2.04901523*t+10.14333127*r-.22475541*t*r-.00683783*t*t-.05481717*r*r+.00122874*t*t*r+.00085282*t*r*r-.00000199*t*t*r*r
  if r<13 and 80<=t<=112:hi-=(13-r)/4*math.sqrt((17-abs(t-95))/17)
  if r>85 and 80<=t<=87:hi+=(r-85)/10*(87-t)/5
  result=f'{(hi-32)/1.8:.2f} °C';formula='NWS Rothfusz polynomial with low/high-humidity adjustments. For shaded, light-wind conditions; limited applicability. No health assessment.';url='https://www.wpc.ncep.noaa.gov/html/heatindex_equation.shtml'
 elif tool=='Snow-water equivalent':
  if a<0 or b<=0:raise ValueError('Snow depth must be ≥0 cm and snow:water ratio >0')
  result=f'{a*10/b:.2f} mm water';formula='SWE = snow depth × 10 / user-supplied snow:water ratio. Ratio is an assumption, not a sensor reading.'
 elif tool=='Beaufort':
  if a<0:raise ValueError('Wind must be non-negative m/s')
  boundaries=[.3,1.6,3.4,5.5,8,10.8,13.9,17.2,20.8,24.5,28.5,32.7];force=sum(a>=x for x in boundaries);names=['Calm','Light air','Light breeze','Gentle breeze','Moderate breeze','Fresh breeze','Strong breeze','Near gale','Gale','Strong gale','Storm','Violent storm','Hurricane force'];result=f'Force {force} · {names[force]}';formula='WMO Beaufort wind-speed bands (m/s). Descriptive conversion only.';url='https://weather.metoffice.gov.uk/guides/coast-and-sea/beaufort-scale'
 elif tool=='Timestamp':
  result=stamp(a,zone,True,True)+' | '+dt.datetime.fromtimestamp(a,dt.UTC).isoformat();formula='Unix seconds interpreted as UTC epoch, converted through the selected IANA timezone. No model run timestamp is invented.'
 elif tool=='Unit conversion':
  source=data['from'];target=data['to'];groups={'°C':('temperature',1,0),'°F':('temperature',5/9,-32*5/9),'m/s':('wind',1,0),'km/h':('wind',1/3.6,0),'mph':('wind',.44704,0),'knots':('wind',.514444444,0),'hPa':('pressure',1,0),'kPa':('pressure',10,0),'mmHg':('pressure',1/.750061683,0),'inHg':('pressure',1/.029529983,0),'km':('distance',1,0),'mi':('distance',1.609344,0),'mm/h':('rate',1,0),'in/h':('rate',25.4,0),'mm':('depth',1,0),'in':('depth',25.4,0)}
  sg,sf,so=groups[source];tg,tf,to=groups[target]
  if sg!=tg:raise ValueError('Choose units measuring the same quantity')
  result=f'{((a*sf+so)-to)/tf:.6g} {target}';formula='Exact affine unit conversion where defined. 1 inch = 25.4 mm; 1 mile = 1.609344 km.'
 else:raise ValueError('Unknown calculation')
 return {'result':result,'formula':formula,'source':url,'inputs':data,'calculated':True}
