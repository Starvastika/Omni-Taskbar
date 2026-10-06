"""Wrapped Mercator base; bounded real radar tiles and labeled model samples."""
import threading,math,json,time,datetime as dt,hashlib
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from collections import OrderedDict
from services.work import WorkQueue
from urllib.parse import urlparse,parse_qs
from PySide6.QtCore import QObject,QTimer,Signal,Qt,QRectF
from PySide6.QtGui import QImage,QPainter,QPainterPath,QColor,QPen
from PySide6.QtQuick import QQuickImageProvider
from astral import sun
from services.layers import LAYERS,layer,color,colors,AIR,MARINE
from services.providers import url,FORECAST
from services.units import pretty,convert,stamp
def grayscale(image):
 image=image.convertToFormat(QImage.Format_RGBA8888);buf=image.bits()
 for i in range(0,image.sizeInBytes(),4):
  shade=(buf[i]*54+buf[i+1]*183+buf[i+2]*19)//256;buf[i]=buf[i+1]=buf[i+2]=shade
 return image
def radar_frame_index(previous,index,current):
 if not current:return 0
 if previous and 0<=index<len(previous)-1:
  return min(range(len(current)),key=lambda i:abs(current[i]['time']-previous[index]['time']))
 return len(current)-1
@lru_cache(maxsize=8)
def radar_legend(root,palette,snow=False):
 table=json.loads((root/'assets/radar-palette.json').read_text('utf-8'));out=[]
 for kind,part in [('Rain',table[:128])]+([('Snow',table[128:])] if snow else []):
  lookup={r['dbz']:r['rgba'] for r in part}
  for v in (0,15,25,35,45,55,65):
   rgba=lookup[v];c=QColor(rgba[:7])
   if palette=='grayscale':shade=(c.red()*54+c.green()*183+c.blue()*19)//256;c=QColor(shade,shade,shade)
   out.append({'value':v,'color':c.name(),'type':kind})
 return out
def wrap(lon):return (float(lon)+180)%360-180
def mx(lon):return (wrap(lon)+180)/360
def my(lat):
 lat=max(-85.05112878,min(85.05112878,float(lat)));r=math.radians(lat);return (1-math.asinh(math.tan(r))/math.pi)/2
def latitude(y):return math.degrees(math.atan(math.sinh(math.pi*(1-2*y))))
def tile_plan(width,height,zoom,x,y):
 span=max(1,min(width,height)*zoom);z=max(0,min(7,int(math.log2(max(256,span)/256))))
 while True:
  n=2**z;left=(.5-x-width/(2*span))*n;right=(.5-x+width/(2*span))*n;top=max(0,(.5-y-height/(2*span))*n);bottom=min(n-1e-8,(.5-y+height/(2*span))*n)
  xs=range(math.floor(left),math.floor(right)+1);ys=range(max(0,math.floor(top)),min(n-1,math.floor(bottom))+1)
  unique={(i%n,j) for i in xs for j in ys}
  if len(unique)<=12 or z==0:break
  z-=1
 return z,sorted(unique)
class MapRenderer:
 size=2048
 def __init__(self,path):self.path=path;self.paths=None;self.borders=[];self.bases={}
 def blank(self):
  im=QImage(self.size,self.size,QImage.Format_ARGB32_Premultiplied);im.fill(Qt.transparent);return im
 def polygon(self,ring,continuous=False):
  p=QPainterPath();previous=None
  for i,c in enumerate(ring):
   x=(c[0]+180)/360*self.size;y=my(c[1])*self.size
   if continuous and previous is not None:x=previous+(x-previous+self.size/2)%self.size-self.size/2
   previous=x
   p.lineTo(x,y) if i else p.moveTo(x,y)
  p.closeSubpath();return p
 def render(self,prefs,alerts):
  if self.paths is None:
   self.paths=[]
   for f in json.loads(self.path.read_text('utf-8'))['features']:
    geom=f['geometry'];polygons=geom['coordinates'] if geom['type']=='MultiPolygon' else [geom['coordinates']]
    for poly in polygons:self.paths.append(self.polygon(poly[0]))
   borderfile=self.path.with_name('countries.geojson')
   if borderfile.exists():
    for f in json.loads(borderfile.read_text('utf-8'))['features']:
     geom=f['geometry'];polygons=geom['coordinates'] if geom['type']=='MultiPolygon' else [geom['coordinates']]
     for poly in polygons:self.borders.append(self.polygon(poly[0]))
  grid=prefs['mapGrid']
  if grid not in self.bases:
   image=self.blank();p=QPainter(image);p.setRenderHint(QPainter.Antialiasing)
   if grid:
    p.setPen(QPen(QColor('#333'),1))
    for lon in range(-180,181,30):p.drawLine(int((lon+180)/360*self.size),0,int((lon+180)/360*self.size),self.size)
    for lat in range(-60,61,30):p.drawLine(0,int(my(lat)*self.size),self.size,int(my(lat)*self.size))
   p.setPen(QPen(QColor('#808080'),1));p.setBrush(QColor('#555'))
   for path in self.paths:p.drawPath(path)
   p.setPen(QPen(QColor('#777'),.7));p.setBrush(Qt.NoBrush)
   for path in self.borders:p.drawPath(path)
   p.end();self.bases[grid]=image
  solar=self.blank();p=QPainter(solar)
  if prefs['mapDay']:
   utc=dt.datetime.now(dt.UTC);century=sun.julianday_to_juliancentury(sun.julianday(utc));decl=sun.sun_declination(century);minutes=utc.hour*60+utc.minute+utc.second/60;sublon=wrap((720-minutes-sun.eq_of_time(century))/4);dec=math.radians(decl)
   for py in range(0,self.size,32):
    lat=math.radians(latitude((py+16)/self.size))
    for px in range(0,self.size,32):
     lon=(px+16)/self.size*360-180;elevation=math.sin(lat)*math.sin(dec)+math.cos(lat)*math.cos(dec)*math.cos(math.radians(lon-sublon))
     if elevation<0:p.fillRect(px,py,32,32,QColor(0,0,0,110 if elevation<-.1 else 60))
  p.end();vector=self.blank();p=QPainter(vector);p.setRenderHint(QPainter.Antialiasing);p.setPen(QPen(QColor('#eee'),2));p.setBrush(QColor(210,210,210,70))
  for alert in alerts:
   geom=alert.get('geometry') or {};coords=geom.get('coordinates',[]);items=coords if geom.get('type')=='MultiPolygon' else [coords] if geom.get('type')=='Polygon' else []
   for poly in items:
    if poly:
     path=self.polygon(poly[0],True);path.setFillRule(Qt.OddEvenFill)
     for ring in poly[1:]:
      hole=self.polygon(ring,True);offset=round((path.boundingRect().center().x()-hole.boundingRect().center().x())/self.size)*self.size;path.addPath(hole.translated(offset,0))
     for shift in (-self.size,0,self.size):p.drawPath(path.translated(shift,0))
  p.end();return self.bases[grid],solar,vector
class MapImages(QQuickImageProvider):
 def __init__(self):super().__init__(QQuickImageProvider.Image,QQuickImageProvider.ForceAsynchronousImageLoading);self.images={};self.lock=threading.Lock()
 def install(self,key,image):
  with self.lock:self.images[key]=image
 def remove(self,key):
  with self.lock:self.images.pop(key,None)
 def requestImage(self,identity,size,requestedSize):
  with self.lock:image=self.images.get(identity.split('?')[0],QImage())
  query=parse_qs(identity.partition('?')[2]);crop=query.get('crop')
  if crop:
   try:
    x,y,w,h=map(int,crop[0].split(','))
    if x<0 or y<0 or w<=0 or h<=0 or x+w>image.width() or y+h>image.height():image=QImage()
    else:image=image.copy(x,y,w,h)
   except (ValueError,TypeError):image=QImage()
  size.setWidth(image.width());size.setHeight(image.height());return image
 def retain(self,keys):
  with self.lock:self.images={k:v for k,v in self.images.items() if k in keys or k in ('land','solar','alerts') or k.startswith(('chart-','preview-'))}

class MapController(QObject):
 rendered=Signal(object)
 def __init__(self,bridge):
  super().__init__(bridge);self.b=bridge;self.http=bridge.http;self.renderer=MapRenderer(bridge.root/'assets/land.geojson');self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='weather-map');self.rendered.connect(self.render_done);self.rendering=False;self.wanted=False;self.ready=False;self.version=0;self.visible=False;self.frames=[];self.host='';self.frame=0;self.tiles={};self.samples=[];self.coverage='Radar coverage is not worldwide · black mask means no radar';self.status='Loading offline map';self.lastSample=0;self.sampleKey=None;self.view=(700,550,1,0,0);self.generation=0;self._playing=False;self.sampleData=[];self.samplePoints=[];self.sampleFrames=[];self.sampleFrame=0
  self.sampleEnvelope={};self.viewTimer=QTimer(self);self.viewTimer.setSingleShot(True);self.viewTimer.setInterval(250);self.viewTimer.timeout.connect(self.loadViewport)
  self.decoder=WorkQueue(self,workers=1,limit=32,name='weather-tiles');self.decoded=OrderedDict();self.decodedBytes=0;self.decodedLimit=32*1024**2;self.tileTime=None;self._tilePending=0
  self.imageVersions={name:0 for name in ('land','solar','alerts')};self.imageKeys={};self._previewGeneration=0
  self.emitTimer=QTimer(self);self.emitTimer.setSingleShot(True);self.emitTimer.setInterval(35);self.emitTimer.timeout.connect(self.b.mapChanged)
  self.playTimer=QTimer(self);self.playTimer.timeout.connect(self.advance)
 def start(self):self.preview={};self.previewActive=False;self.requestRender();self.metadata()
 def metadata(self,force=False):
  def done(reply):
   data=reply.get('data') or {};host=data.get('host','')
   if host and not (urlparse(host).scheme=='https' and (urlparse(host).hostname or '').endswith('.rainviewer.com')):self.status='Radar returned an untrusted tile host';self.notify();return
   self.host=host;radar=data.get('radar',{});frames=[dict(f,kind='past') for f in radar.get('past',[])]+[dict(f,kind='nowcast') for f in radar.get('nowcast',[])];self.frame=radar_frame_index(self.frames,self.frame,frames);self.frames=frames
   self.status=('Radar metadata stale · ' if reply.get('stale') else '')+('No radar metadata available' if not frames else f'{len(frames)} provider frames · '+('past only; no nowcast supplied' if not radar.get('nowcast') else 'past + provider nowcast'))
   if reply.get('error'):self.status=reply['error']+' · forecast / offline base remain usable'
   self.notify()
   if self.visible:self.loadViewport()
   elif self.previewActive:self.loadPreview()
  self.http.request('https://api.rainviewer.com/public/weather-maps.json',600,done,'radar-meta',force)
 def setVisible(self,value):
  if self.visible==value:return
  self.visible=value
  if value:self.requestRender();self.viewTimer.start()
  else:self.playTimer.stop();self._playing=False;self.viewTimer.stop();self.generation+=1;self._tilePending=0;self.http.cancel('radar');self.http.cancel('samples');self.notify()
 def decodeTile(self,identity,reply,gray,callback):
  if identity in self.decoded:self.decoded.move_to_end(identity);callback(self.decoded[identity]);return
  if not reply.get('data'):callback(None);return
  def task():
   image=QImage.fromData(reply['data'])
   return grayscale(image) if gray and not image.isNull() else image
  def ready(image,error):
   if error or image is None or image.isNull():callback(None);return
   old=self.decoded.pop(identity,None)
   if old is not None:self.decodedBytes-=old.sizeInBytes()
   self.decoded[identity]=image;self.decodedBytes+=image.sizeInBytes()
   while self.decoded and self.decodedBytes>self.decodedLimit:
    _,old=self.decoded.popitem(last=False);self.decodedBytes-=old.sizeInBytes()
   callback(image)
  if not self.decoder.submit(identity,task,ready):callback(None)
 def setPreviewActive(self,value):
  if self.previewActive==value:return
  self.previewActive=value
  if value:self.loadPreview()
  else:self.http.cancel('preview')
 def loadPreview(self):
  if not self.previewActive or not self.frames or not self.host:return
  self._previewGeneration+=1;previewGeneration=self._previewGeneration
  loc=self.b.state['selected'];identity=loc['id'];z=5;n=2**z;x=int(mx(loc['lon'])*n)%n;y=int(my(loc['lat'])*n);frame=self.frames[-1];span=256*n;self.preview={'radar':'','coverage':'','x':x/n,'y':y/n,'span':span,'time':stamp(frame['time'],loc['zone'],True,True),'status':'One selected radar tile · surrounding gray areas are not radar imagery','legend':radar_legend(self.b.root,self.b.state['prefs']['palette'])}
  if self.b.state['dashboard']['miniLayer']=='none':self.preview.update({'time':'Offline geography','status':'Grayscale base only','legend':[]});self.notify();return
  for kind,endpoint in [('radar',f'{self.host}{frame["path"]}/256/{z}/{x}/{y}/2/1_0.png'),('coverage',f'{self.host}/v2/coverage/0/256/{z}/{x}/{y}/0/0_0.png')]:
   def done(reply,kind=kind):
    if identity!=self.b.state['selected']['id'] or not self.previewActive or previewGeneration!=self._previewGeneration:return
    def installed(image):
     if identity!=self.b.state['selected']['id'] or not self.previewActive or previewGeneration!=self._previewGeneration:return
     if image is not None:
      self.b.images.install('preview-'+kind,image)
      if kind!='radar' or self.b.state['dashboard']['miniLayer']=='radar':self.preview[kind]='image://weatherMap/preview-'+kind+'?t='+str(frame['time'])+'&palette='+self.b.state['prefs']['palette']
     if reply.get('error'):self.preview['status']='Radar preview unavailable · offline base remains usable'
     self.notify()
    self.decodeTile('preview-decode-'+kind+'-'+str(frame['time'])+'-'+str(z)+'-'+str(x)+'-'+str(y)+'-'+self.b.state['prefs']['palette'],reply,kind=='radar' and self.b.state['prefs']['palette']=='grayscale',installed)
   self.http.request(endpoint,86400 if kind=='radar' else 604800,done,'preview',binary=True)
  self.notify()
 def tick(self):
  if self.visible:
   self.requestRender()
   if self.b.state['prefs']['autoRefresh']:self.metadata()
 def requestRender(self):
  if self.rendering:self.wanted=True;return
  self.rendering=True;prefs=dict(self.b.state['prefs']);alerts=[a for a in (self.b.advanced.get('alerts') or {}).get('items',[]) if a.get('active') and (not a.get('expiresEpoch') or a['expiresEpoch']>time.time())] if self.b.state['map']['layer']=='alerts' else []
  f=self.pool.submit(self.renderer.render,prefs,alerts)
  def complete(f):
   try:self.rendered.emit(f.result())
   except Exception:self.rendered.emit(None)
  f.add_done_callback(complete)
 def render_done(self,result):
  self.rendering=False
  if result:
   for name,im in zip(('land','solar','alerts'),result):
    key=im.cacheKey()
    if self.imageKeys.get(name)!=key:
     self.b.images.install(name,im);self.imageKeys[name]=key;self.imageVersions[name]+=1
   self.version+=1;self.ready=True;self.notify()
  if self.wanted:self.wanted=False;self.requestRender()
 def preferencesChanged(self,key=None):
  if key is None or key in ('mapGrid','mapDay'):self.requestRender()
  if key is None or key in ('palette','radarSmooth','radarSnow'):self.viewTimer.start();self.loadPreview() if self.previewActive else None
  if key is None or key in ('palette','temperature','wind','pressure','precipitation','visibility','distance'):
   if layer(self.b.state['map']['layer'])['kind']=='samples':self.drawSamples()
  if self.playTimer.isActive():self.playTimer.setInterval(max(750,self.b.state['prefs']['radarSpeed']))
 def viewport(self,width,height,zoom,x,y):self.view=(width,height,zoom,(x+.5)%1-.5,y);self.viewTimer.start()
 def notify(self):
  if not self.emitTimer.isActive():self.emitTimer.start()
 def snapshot(self):
  definition=layer(self.b.state['map']['layer']);palette=self.b.state['prefs']['palette'];legend=''
  if definition['kind']=='samples':
   unit=convert(0,definition['unit'],self.b.state['prefs'],definition['variable'])[1];source='CAMS Global' if definition['variable'] in AIR else 'Open-Meteo marine models' if definition['variable'] in MARINE else 'NOAA GFS / HRRR seamless';saved=self.sampleEnvelope.get('saved',0);age=f'{int(max(0,time.time()-saved)//60)} min old' if saved else 'Not loaded';stale=self.sampleEnvelope.get('stale',True) or time.time()-saved>1800
   legend=definition['name']+' · '+unit+' · '+source+' · '+('STALE · ' if stale else '')+age+' · 15 modeled points, not a continuous raster. Exact run time is not supplied; missing points are omitted.'
  elif definition['kind']=='tiles':legend='Radar composite reflectivity · RainViewer · dBZ. Frame time is generation time, not each radar observation. Coverage varies.'
  elif definition['kind']=='coverage':legend='Radar coverage: transparent = covered; black = no radar. Transparent radar alone does not prove clear weather.'
  elif definition['kind']=='unsupported':legend=definition['provider']+' · this layer is disabled'
  elif definition['kind']=='vector':legend='Official alert geometry from ECCC / NWS for the selected location. Source text and freshness in Alerts; no worldwide completeness claim.'
  frames=[{'time':t,'kind':'forecast'} for t in self.sampleFrames] if definition['kind']=='samples' else self.frames if definition['kind'] in ('tiles','coverage') else [];frame=self.sampleFrame if definition['kind']=='samples' else self.frame
  label=stamp(frames[frame]['time'],self.b.state['selected'].get('zone','UTC'),True,True) if frames else 'No layer time'
  if definition['kind']=='tiles' and self.tiles and self.tileTime is not None:
   label=stamp(self.tileTime,self.b.state['selected'].get('zone','UTC'),True,True)+(' · updating requested frame' if frames and self.tileTime!=frames[frame]['time'] else '')
  return {'ready':self.ready,'land':f'image://weatherMap/land?v={self.imageVersions["land"]}' if self.ready else '', 'solar':f'image://weatherMap/solar?v={self.imageVersions["solar"]}' if self.ready else '', 'alerts':f'image://weatherMap/alerts?v={self.imageVersions["alerts"]}' if self.ready else '', 'tiles':list(self.tiles.values()),'samples':self.samples,'frames':[{'time':f['time'],'label':stamp(f['time'],self.b.state['selected'].get('zone','UTC'),True,True),'kind':f['kind']} for f in frames],'frame':frame,'layers':LAYERS,'legend':legend,'coverage':self.coverage,'status':self.status,'playing':self._playing,'frameLabel':label,'sampleLegend':radar_legend(self.b.root,palette,self.b.state['prefs']['radarSnow']) if definition['kind']=='tiles' else [{'value':convert(definition['min']+(definition['max']-definition['min'])*i/4,definition['unit'],self.b.state['prefs'],definition['variable'])[0],'color':c} for i,c in enumerate(colors(palette))]}
 def loadViewport(self):
  if not self.visible:return
  definition=layer(self.b.state['map']['layer'])
  if definition['kind'] in ('tiles','coverage'):self.loadTiles()
  elif definition['kind']=='samples':self.loadSamples()
  elif definition['kind']=='vector':
   if 'alerts' not in self.b.advanced:self.b.fetchAlerts()
   self.requestRender();self.notify()
  else:self.tiles={};self.samples=[];self.notify()
 def loadTiles(self):
  if not self.host or not self.frames:return
  self.generation+=1;gen=self.generation;self.http.cancel('radar');self.samples=[];z,coords=tile_plan(*self.view);n=2**z;frame=self.frames[self.frame];prefs=dict(self.b.state['prefs']);scheme=2;options=f"{1 if prefs['radarSmooth'] else 0}_{1 if prefs['radarSnow'] else 0}";keys=set();pending={};remaining=[len(coords)*2];self._tilePending=remaining[0]
  oldKeys={r['key'] for r in self.tiles.values()}|{r['coverage'].removeprefix('image://weatherMap/') for r in self.tiles.values() if r.get('coverage')}
  def complete():
   if gen!=self.generation:return
   remaining[0]-=1;self._tilePending=remaining[0]
   if remaining[0]==0:
    usable=any(r['radar'] for r in pending.values()) if self.b.state['map']['layer']=='radar' else any(r['coverage'] for r in pending.values())
    if usable or not self.tiles:self.tiles=pending;self.tileTime=frame['time'];self.b.images.retain(keys)
    else:self.status='Radar update unavailable · last decoded frame retained';self.b.images.retain(oldKeys)
    self.notify()
  for x,y in coords:
   identity=f'rt-{frame["time"]}-{z}-{x}-{y}-{scheme}-{options}-{prefs["palette"]}';coverage=f'cv-{z}-{x}-{y}';keys.update((identity,coverage));record={'key':identity,'x':x/n,'y':y/n,'width':1/n,'radar':'','coverage':''};pending[(x,y)]=record
   def radar_done(reply,record=record,identity=identity):
    if gen!=self.generation:return
    def installed(image):
     if gen!=self.generation:return
     if image is not None:
      self.b.images.install(identity,image);record['radar']='image://weatherMap/'+identity
     if reply.get('error'):self.status='Radar tile unavailable · cached forecast is unaffected'
     complete()
    self.decodeTile(identity,reply,prefs['palette']=='grayscale',installed)
   def coverage_done(reply,record=record,identity=coverage,x=x,y=y):
    if gen!=self.generation:return
    def installed(image):
     if gen!=self.generation:return
     if image is not None:
      self.b.images.install(identity,image);record['coverage']='image://weatherMap/'+identity;loc=self.b.state['selected'];px=mx(loc['lon'])*n;py=my(loc['lat'])*n
      if int(px)%n==x and int(py)==y:
       alpha=image.pixelColor(int((px%1)*(image.width()-1)),int((py%1)*(image.height()-1))).alpha();self.coverage='Selected point: no radar coverage · model precipitation still available' if alpha>128 else 'Selected point lies within the provider coverage mask · radar gaps remain possible'
     complete()
    self.decodeTile(identity,reply,False,installed)
   self.http.request(f'{self.host}{frame["path"]}/256/{z}/{x}/{y}/{scheme}/{options}.png',86400,radar_done,'radar',binary=True)
   self.http.request(f'{self.host}/v2/coverage/0/256/{z}/{x}/{y}/0/0_0.png',604800,coverage_done,'radar',binary=True)
  self.b.images.retain(keys|oldKeys)
 def loadSamples(self,force=False):
  width,height,zoom,x,y=self.view;definition=layer(self.b.state['map']['layer']);span=max(1,min(width,height)*zoom);points=[]
  for j in range(3):
   for i in range(5):
    px=.5-x+(i/4-.5)*width/span*.9;py=max(.001,min(.999,.5-y+(j/2-.5)*height/span*.9));points.append((latitude(py),wrap(px*360-180)))
  key=(definition['id'],tuple((round(a,2),round(b,2)) for a,b in points))
  if key==self.sampleKey and not force and self.sampleEnvelope.get('data') is not None and time.time()-self.sampleEnvelope.get('saved',0)<1800:return
  if time.time()-self.lastSample<(15 if force else 60):self.status='Sample field retained · bounded refresh cooldown';self.notify();return
  previous=self.sampleEnvelope if key==self.sampleKey else {};previousPoints=self.samplePoints;self.lastSample=time.time();self.sampleKey=key;self.http.cancel('samples');self.tiles={};variable=definition['variable'];endpoint='https://air-quality-api.open-meteo.com/v1/air-quality' if variable in AIR else 'https://marine-api.open-meteo.com/v1/marine' if variable in MARINE else FORECAST
  params={'latitude':','.join(str(round(a,4)) for a,b in points),'longitude':','.join(str(round(b,4)) for a,b in points),'forecast_days':2,'hourly':variable+(',wind_direction_10m' if variable in ('wind_speed_10m','wind_gusts_10m') else ''),'current':variable+(',wind_direction_10m' if variable in ('wind_speed_10m','wind_gusts_10m') else ''),'timeformat':'unixtime','timezone':'UTC'}
  if variable not in AIR:params['wind_speed_unit']='ms'
  if endpoint==FORECAST:params['models']='gfs_seamless'
  elif variable in AIR:params['domains']='cams_global'
  def done(reply):
   if key!=self.sampleKey:return
   from services.datasets import retain
   retained=reply.get('data') is None and previous.get('data') is not None;reply=retain(previous,reply)
   data=reply.get('data');items=data if isinstance(data,list) else [data] if data else []
   self.sampleEnvelope=reply;self.sampleData=items;self.samplePoints=previousPoints if retained else points;self.sampleFrames=(items[0].get('hourly',{}).get('time',[]) if items else []);self.sampleFrame=min(range(len(self.sampleFrames)),key=lambda i:abs(self.sampleFrames[i]-time.time())) if self.sampleFrames else 0
   self.drawSamples()
   self.status=reply.get('error') or f'{len(self.samples)}/15 valid modeled point samples · '+('STALE' if reply.get('stale') else 'cached / current request');self.notify()
  self.http.request(url(endpoint,params),1800,done,'samples',force)
 def drawSamples(self):
  definition=layer(self.b.state['map']['layer']);variable=definition['variable'];samples=[]
  for (lat,lon),item in zip(self.samplePoints,self.sampleData):
   h=item.get('hourly') or {};i=self.sampleFrame;array=h.get(variable,[]);value=array[i] if i<len(array) else None
   if value is None:continue
   unit=item.get('hourly_units',{}).get(variable,definition['unit']);directions=h.get('wind_direction_10m',[])
   samples.append({'lat':lat,'lon':lon,'value':value,'text':pretty(value,unit,self.b.state['prefs'],key=variable),'color':color(value,definition,self.b.state['prefs']['palette']),'direction':directions[i] if i<len(directions) else None,'epoch':self.sampleFrames[i] if i<len(self.sampleFrames) else None})
  self.samples=samples;self.notify()
 def action(self,data):
  op=data['op']
  if layer(self.b.state['map']['layer'])['kind']=='samples' and op in ('frame','step','now'):
   self.sampleFrame=max(0,min(len(self.sampleFrames)-1,int(data['value']))) if op=='frame' else (self.sampleFrame+int(data['delta']))%max(1,len(self.sampleFrames)) if op=='step' else min(range(len(self.sampleFrames)),key=lambda i:abs(self.sampleFrames[i]-time.time())) if self.sampleFrames else 0
   self.drawSamples();return
  if op=='layer':
   definition=layer(data['value'])
   if not definition['available']:self.b.status_text('Layer unavailable: '+definition['provider']);return
   self.b.state['map']['layer']=definition['id'];self._playing=False;self.playTimer.stop();self.sampleKey=None;self.sampleFrames=[];self.sampleData=[];self.sampleEnvelope={};self.tiles={};self.samples=[];self.loadViewport();self.notify();self.b.persist()
  elif op=='frame':self.frame=max(0,min(len(self.frames)-1,int(data['value'])));self.loadTiles();self.notify()
  elif op=='step':self.frame=(self.frame+int(data['delta']))%max(1,len(self.frames));self.loadTiles();self.notify()
  elif op=='now':self.frame=max(0,len(self.frames)-1);self.loadTiles();self.notify()
  elif op=='play':
   self._playing=not self._playing
   if self._playing and self.visible and (self.frames or self.sampleFrames):self.playTimer.start(max(750,self.b.state['prefs']['radarSpeed']))
   else:self.playTimer.stop()
   self.notify()
  elif op=='refresh':self.metadata(True) if layer(self.b.state['map']['layer'])['kind'] in ('tiles','coverage') else self.loadSamples(True)
 def advance(self):
  if not self.visible or self.b.state['prefs']['reduceMotion']:self.playTimer.stop();self._playing=False;self.notify();return
  if self._tilePending or any(group=='radar' for item in self.http.flights.values() for group,_ in item['callbacks']):return
  if layer(self.b.state['map']['layer'])['kind']=='samples':self.sampleFrame=(self.sampleFrame+1)%max(1,len(self.sampleFrames));self.drawSamples()
  else:self.frame=(self.frame+1)%max(1,len(self.frames));self.loadTiles();self.notify()
 def close(self):self.playTimer.stop();self.viewTimer.stop();self.pool.shutdown(wait=True,cancel_futures=True);self.decoder.close();self.decoded.clear();self.decodedBytes=0
