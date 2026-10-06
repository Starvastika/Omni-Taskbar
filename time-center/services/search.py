import json
import unicodedata
import urllib.parse
import urllib.request
from zoneinfo import available_timezones,ZoneInfo
from astral.geocoder import database,all_locations
import tzfpy

def fold(text):return ''.join(c for c in unicodedata.normalize('NFKD',text).casefold() if not unicodedata.combining(c))

def search(query,cache):
    query=query.strip();key=fold(query)
    if key in cache:return cache[key],'Cached results'
    terms=key.replace(',',' ').split()
    local=[{'name':c.name,'region':c.region,'zone':c.timezone,'lat':c.latitude,'lon':c.longitude} for c in all_locations(database()) if all(t in fold(c.name+' '+c.region+' '+c.timezone) for t in terms)]
    zones=[{'name':z.split('/')[-1].replace('_',' '),'region':'IANA timezone · location not set','zone':z,'lat':None,'lon':None} for z in sorted(available_timezones()) if key.replace(' ','_') in z.casefold()][:30]
    if '/' in query:return zones,'IANA timezone database (offline)'
    def fetch(name):
        url='https://geocoding-api.open-meteo.com/v1/search?'+urllib.parse.urlencode({'name':name,'count':100,'language':'en','format':'json'})
        req=urllib.request.Request(url,headers={'User-Agent':'YASB-Time-Center/1.0'})
        with urllib.request.urlopen(req,timeout=6) as response:return json.load(response).get('results',[])
    try:
        parts=[p.strip() for p in query.split(',') if p.strip()];name=parts[0];regions=parts[1:]
        results=fetch(name)
        if not results and len(parts)==1:
            words=query.split()
            for split in range(len(words)-1,0,-1):
                name=' '.join(words[:split]);regions=words[split:];results=fetch(name)
                if results:break
        if regions:results=[r for r in results if all(any(fold(str(r.get(f,''))).startswith(fold(term)) for f in ('admin1','admin2','admin3','admin4','country','country_code')) for term in regions)]
        results.sort(key=lambda r:(fold(r['name'])!=fold(name),-r.get('population',0)))
        rows=[{'name':r['name'],'region':', '.join(dict.fromkeys(x for x in [r.get('admin1'),r.get('country')] if x)),'zone':r['timezone'],'lat':r['latitude'],'lon':r['longitude']} for r in results if r.get('timezone')]
        return (rows or local or zones)[:30],'Open-Meteo geocoding' if rows else 'Local timezone/city database'
    except Exception:return (local or zones)[:30],'Search offline — saved clocks still work; showing local matches'

def inspect_point(lon,lat):
    lon=max(-180,min(180,float(lon)));lat=max(-89.9,min(89.9,float(lat)))
    zone=tzfpy.get_tz(lon,lat) or 'UTC';ZoneInfo(zone)
    return {'name':f'{abs(lat):.2f}°{"N" if lat>=0 else "S"}, {abs(lon):.2f}°{"E" if lon>=0 else "W"}','region':'Map location · offline timezone boundary lookup','lat':lat,'lon':lon,'zone':zone}
