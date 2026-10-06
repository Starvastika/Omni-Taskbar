"""Official point alerts. Provider wording retained; no forecast thresholds here."""
import datetime as dt,json,time
from pathlib import Path
from urllib.parse import urlparse
from services.providers import url
from services.units import stamp
def epoch(value):
 try:return dt.datetime.fromisoformat(str(value).replace('Z','+00:00')).timestamp()
 except (ValueError,TypeError):return None
def in_ring(lon,lat,ring):
 inside=False
 for a,b in zip(ring,ring[1:]+ring[:1]):
  if (a[1]>lat)!=(b[1]>lat) and lon<(b[0]-a[0])*(lat-a[1])/(b[1]-a[1])+a[0]:inside=not inside
 return inside
def contains(geometry,lon,lat):
 geom=geometry or {};polys=geom.get('coordinates',[]) if geom.get('type')=='MultiPolygon' else [geom.get('coordinates',[])] if geom.get('type')=='Polygon' else []
 return any(poly and in_ring(lon,lat,poly[0]) and not any(in_ring(lon,lat,hole) for hole in poly[1:]) for poly in polys)
_countries=None
def country(loc):
 code=loc.get('countryCode','').upper();name=loc.get('country','').casefold()
 if code:return code
 if name=='canada':return 'CA'
 if name in ('united states','united states of america','usa'):return 'US'
 global _countries
 if _countries is None:
  try:_countries=json.loads((Path(__file__).resolve().parents[1]/'assets/countries.geojson').read_text('utf-8'))['features']
  except (OSError,ValueError):_countries=[]
 for feature in _countries:
  if contains(feature['geometry'],loc['lon'],loc['lat']):
   props={k.upper():v for k,v in feature['properties'].items()};return props.get('ISO_A2_EH',props.get('ISO_A2',''))
 return ''
def normalize(feature,provider,zone,now=None):
 now=time.time() if now is None else now;p=feature.get('properties') or {}
 if provider=='ECCC':
  issued=p.get('publication_datetime');effective=p.get('validity_datetime');expires=p.get('expiration_datetime');title=p.get('alert_name_en') or p.get('alert_short_name_en') or 'Official Canadian alert';body=p.get('alert_text_en') or '';ended=str(p.get('status_en','')).casefold() in ('ended','cancelled','canceled','expired');severity='Not supplied';urgency='Not supplied';certainty=p.get('confidence_en') or 'Not supplied';instructions='Included in the original alert text when supplied';area=p.get('feature_name_en','');link=next((x['href'] for x in feature.get('links',[]) if x.get('rel')=='canonical' and x.get('href','').startswith('https://')), 'https://api.weather.gc.ca/collections/weather-alerts');source='Environment and Climate Change Canada';identity=feature.get('id') or p.get('feature_id') or title+str(issued)
 else:
  issued=p.get('sent');effective=p.get('effective');expires=p.get('expires');title=p.get('headline') or p.get('event') or 'Official US alert';body=p.get('description') or '';ended=p.get('messageType')=='Cancel';severity=p.get('severity') or 'Not supplied';urgency=p.get('urgency') or 'Not supplied';certainty=p.get('certainty') or 'Not supplied';instructions=p.get('instruction') or 'Not supplied';area=p.get('areaDesc','');link=p.get('@id') or feature.get('id') or 'https://www.weather.gov/';source='US National Weather Service';identity=p.get('id') or feature.get('id') or title+str(issued)
 exp=epoch(expires);active=not ended and (exp is None or exp>now);eff=epoch(effective)
 return {'id':str(identity),'title':title,'description':body,'instructions':instructions,'provider':provider,'source':source,'severity':severity,'urgency':urgency,'certainty':certainty,'area':area,'issued':stamp(epoch(issued),zone,True,True) if epoch(issued) else 'Not supplied','effective':stamp(eff,zone,True,True) if eff else 'Not supplied','expires':stamp(exp,zone,True,True) if exp else 'Not supplied','expiresEpoch':exp,'issuedEpoch':epoch(issued),'active':active,'upcoming':bool(eff and eff>now),'url':link if str(link).startswith('https://') else '', 'geometry':feature.get('geometry'),'original':p}
def fetch_alerts(http,loc,callback,force=False):
 code=country(loc);provider='ECCC' if code=='CA' else 'NWS' if code=='US' else None
 if not provider:callback({'available':False,'status':'Official alert coverage unavailable for this country / offshore point','items':[],'coverage':'Integrated sources cover Canada and the United States only. Offline country boundaries are coarse; choose a named location near borders.','source':'None'});return
 coverage='ECCC Canadian alert polygons, exact point-in-polygon filtering.' if provider=='ECCC' else 'NWS active alerts, official server point filter. Some alerts have no polygon.'
 history=http.root.parent/('alerts-'+loc['id']+'.json');old=[]
 try:old=json.loads(history.read_text('utf-8')).get('items',[])
 except (OSError,ValueError):pass
 collected=[];pages=[0];errors=[];saved=[0];stale=[False]
 if provider=='ECCC':
  d=.005;target=url('https://api.weather.gc.ca/collections/weather-alerts/items',{'f':'json','bbox':f"{loc['lon']-d},{loc['lat']-d},{loc['lon']+d},{loc['lat']+d}",'limit':200})
 else:target=url('https://api.weather.gov/alerts/active',{'point':f"{loc['lat']},{loc['lon']}"})
 def finish():
  now=time.time();items={a['id']:a for a in old if (a.get('expiresEpoch') or a.get('issuedEpoch') or 0)>now-86400}
  for feature in collected:
   if provider=='ECCC' and not contains(feature.get('geometry'),loc['lon'],loc['lat']):continue
   alert=normalize(feature,provider,loc['zone']);items[alert['id']]=alert
  for a in items.values():
   if a.get('expiresEpoch') and a['expiresEpoch']<=now:a['active']=False
  alerts=sorted(items.values(),key=lambda a:(not a['active'],{'Extreme':0,'Severe':1,'Moderate':2,'Minor':3}.get(a['severity'],4),-(a.get('issuedEpoch') or 0)))
  # A missing current NWS item is no longer confirmed active even before recorded expiry.
  current_ids={normalize(f,provider,loc['zone'])['id'] for f in collected}
  if not errors:
   for a in alerts:
    if a['id'] not in current_ids:a['active']=False
   http.writer.submit(history,{'items':alerts,'saved':saved[0]})
  available=not bool(errors);n=sum(a['active'] for a in alerts)
  callback({'available':available,'status':('Alert data unavailable · '+errors[0]) if errors else (f'{n} active official alert(s)' if n else 'No active official alerts at this location'),'items':alerts,'coverage':coverage,'source':provider,'stale':stale[0] or bool(errors),'saved':saved[0],'error':' · '.join(errors)})
 def done(reply):
  data=reply.get('data');saved[0]=max(saved[0],reply.get('saved',0));stale[0]|=reply.get('stale',True)
  if reply.get('error'):errors.append(reply['error'])
  if not isinstance(data,dict) or not isinstance(data.get('features'),list):
   errors.append('Official feed returned no valid feature collection');finish();return
  collected.extend(data['features']);pages[0]+=1
  link=next((x.get('href') for x in data.get('links',[]) if x.get('rel')=='next'),None)
  if link:
   if pages[0]>=4 or urlparse(link).hostname!=urlparse(target).hostname:errors.append('Alert result pagination incomplete');finish()
   else:http.request(link,300,done,'alerts',force)
  else:finish()
 http.request(target,300,done,'alerts',force)
