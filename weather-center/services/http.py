"""One asynchronous HTTP/cache policy, deduplication and bounded concurrency."""
import hashlib,json,logging,time,sys
from collections import OrderedDict,deque
from pathlib import Path
from urllib.parse import urlparse
from PySide6.QtCore import QObject,QTimer,QUrl,Signal
from PySide6.QtNetwork import QNetworkAccessManager,QNetworkRequest,QNetworkReply
from services.work import WorkQueue

def resident_size(value):
 """Count owned Python objects once, including shared references, off the GUI."""
 seen=set()
 def size(item):
  identity=id(item)
  if identity in seen:return 0
  seen.add(identity);total=sys.getsizeof(item)
  if isinstance(item,dict):total+=sum(size(k)+size(v) for k,v in item.items())
  elif isinstance(item,(list,tuple)):total+=sum(size(v) for v in item)
  return total
 return size(value)

class HttpClient(QObject):
 healthChanged=Signal()
 def __init__(self,root,writer):
  super().__init__();self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True);self.writer=writer
  self.manager=QNetworkAccessManager(self);self.cache=OrderedDict();self.flights={};self.queue=deque();self.active=0;self.health={};self.requests=0;self.limitMB=96;self.closed=False;self.offline=False
  self.io=WorkQueue(self,workers=2,limit=56,name='weather-cache');self.loads={};self.cacheBytes=0;self.memoryLimit=32*1024**2
  self.misses=OrderedDict()
 def key(self,url):return hashlib.sha256(url.encode()).hexdigest()
 def cached(self,url,binary=False):
  key=self.key(url)
  if key in self.cache:self.cache.move_to_end(key);return self.cache[key]
  entry=self.readCache(url,binary)
  if entry:self.remember(key,entry)
  return entry
 def readCache(self,url,binary=False):
  key=self.key(url)
  try:
   entry=json.loads((self.root/(key+'.json')).read_text('utf-8'))
   if entry.get('url')!=url:return None
   if binary:entry['data']=(self.root/(key+'.bin')).read_bytes()
   entry['_residentBytes']=resident_size(entry);return entry
  except (OSError,ValueError):return None
 def remember(self,key,entry):
  self.misses.pop(key,None)
  old=self.cache.pop(key,None)
  if old:self.cacheBytes-=old.get('_residentBytes',0)
  self.cacheBytes+=entry.get('_residentBytes',0)
  self.cache[key]=entry;self.cache.move_to_end(key)
  while len(self.cache)>80 or self.cacheBytes>self.memoryLimit:
   _,old=self.cache.popitem(last=False);self.cacheBytes-=old.get('_residentBytes',0)
 def envelope(self,url,entry,ttl,error='',cache=True):
  return {'data':entry['data'],'saved':entry['saved'],'stale':time.time()-entry['saved']>ttl or bool(error),'error':error,'source':url,'cache':cache,'ageSeconds':max(0,time.time()-entry['saved'])}
 def request(self,url,ttl,callback,group='',force=False,binary=False):
  if self.closed:return
  key=self.key(url)
  if key in self.cache:
   self.cache.move_to_end(key);self.requestReady(url,ttl,callback,group,force,binary,self.cache[key]);return
  if time.monotonic()-self.misses.get(key,-100000)<30:
   self.requestReady(url,ttl,callback,group,force,binary,None);return
  if url in self.loads:self.loads[url]['callbacks'].append((group,callback,ttl,force));return
  if len(self.loads)+len(self.flights)>=48:
   callback({'data':None,'saved':0,'stale':True,'error':'Request queue is full; retry later','source':url,'cache':False});return
  item={'callbacks':[(group,callback,ttl,force)]};self.loads[url]=item
  def loaded(entry,error):
   if self.closed or self.loads.get(url) is not item:return
   self.loads.pop(url,None)
   if entry:self.remember(key,entry)
   else:
    self.misses[key]=time.monotonic();self.misses.move_to_end(key)
    while len(self.misses)>128:self.misses.popitem(last=False)
   for g,cb,t,f in tuple(item['callbacks']):self.requestReady(url,t,cb,g,f,binary,entry)
  self.io.submit('read:'+url,lambda:self.readCache(url,binary),loaded)
 def requestReady(self,url,ttl,callback,group,force,binary,entry):
  if self.closed:return
  if self.offline:
   callback(self.envelope(url,entry,ttl,'Offline mode · cached data') if entry else {'data':None,'saved':0,'stale':True,'error':'Offline mode · no cached data','source':url,'cache':False});return
  if entry:
   host=urlparse(url).hostname;previous=self.health.get(host,{});self.health[host]={'provider':host,'status':'Cached · stale' if time.time()-entry['saved']>ttl else 'Cached / available','lastSuccess':max(entry['saved'],previous.get('lastSuccess',0)),'error':''};self.healthChanged.emit()
   callback(self.envelope(url,entry,ttl))
   if not force and time.time()-entry['saved']<ttl:return
  if url in self.flights:self.flights[url]['callbacks'].append((group,callback));return
  if len(self.flights)>=48:
   if not entry:callback({'data':None,'saved':0,'stale':True,'error':'Request queue is full; retry later','source':url,'cache':False})
   return
  self.flights[url]={'url':url,'ttl':ttl,'callbacks':[(group,callback)],'binary':binary,'entry':entry,'attempt':0,'reply':None};self.queue.append(url);self.pump()
 def cancel(self,group):
  for url,item in tuple(self.loads.items()):
   item['callbacks']=[x for x in item['callbacks'] if x[0]!=group]
   if not item['callbacks']:self.loads.pop(url,None);self.io.cancel('read:'+url)
  for url,item in tuple(self.flights.items()):
   item['callbacks']=[x for x in item['callbacks'] if x[0]!=group]
   if not item['callbacks']:
    self.flights.pop(url,None)
    if item['reply']:item['reply'].abort()
 def setOffline(self,value):
  self.offline=bool(value)
  if not self.offline:self.pump();return
  pending=tuple(self.flights.items());self.flights.clear();self.queue.clear()
  for url,item in pending:
   if item['reply']:item['reply'].abort()
   entry=item['entry'];result=self.envelope(url,entry,item['ttl'],'Offline mode · cached data') if entry else {'data':None,'saved':0,'stale':True,'error':'Offline mode · no cached data','source':url,'cache':False}
   for _,callback in tuple(item['callbacks']):
    try:callback(result)
    except Exception:logging.exception('Offline callback failed')
 def pump(self):
  while self.active<4 and self.queue and not self.closed and not self.offline:
   url=self.queue.popleft();item=self.flights.get(url)
   if not item or item['reply'] is not None:continue
   request=QNetworkRequest(QUrl(url));request.setTransferTimeout(12000)
   # Consistent HTTP/1.1 transport avoids observed Qt HTTP/2 stream stalls.
   # Four bounded requests still run concurrently; caching/dedup remain central.
   request.setAttribute(QNetworkRequest.Http2AllowedAttribute,False)
   request.setRawHeader(b'User-Agent',b'YASB-Weather-Center/1.0 (personal Windows shell; Open-Meteo/ECCC/NWS client)')
   request.setRawHeader(b'Accept',b'image/png' if item['binary'] else b'application/json, application/geo+json')
   if item['entry']:
    for field,header in [('etag',b'If-None-Match'),('modified',b'If-Modified-Since')]:
     if item['entry'].get(field):request.setRawHeader(header,item['entry'][field].encode())
   reply=self.manager.get(request);item['reply']=reply;self.active+=1;self.requests+=1
   reply.finished.connect(lambda r=reply,u=url,i=item:self.finished(u,i,r))
 def finished(self,url,item,reply):
  self.active-=1;item['reply']=None
  if self.flights.get(url) is not item or self.closed:reply.deleteLater();self.pump();return
  code=reply.attribute(QNetworkRequest.HttpStatusCodeAttribute);raw=bytes(reply.readAll()) if reply.isOpen() else b''
  error='' if reply.error()==QNetworkReply.NoError or code==304 else reply.errorString()
  host=urlparse(url).hostname
  if error and (code in (429,500,502,503,504) or code is None) and item['attempt']<2 and not self.closed:
   item['attempt']+=1;delay=1500*2**(item['attempt']-1)
   if code==429:delay=max(delay,10000)
   reply.deleteLater();QTimer.singleShot(delay,lambda:self.retry(url,item));self.pump();return
  headers={'etag':bytes(reply.rawHeader('ETag')).decode(),'modified':bytes(reply.rawHeader('Last-Modified')).decode()};reply.deleteLater()
  def decode():
   if error:raise ValueError(error)
   payload=item['entry']['data'] if code==304 and item['entry'] else raw if item['binary'] else json.loads(raw)
   if isinstance(payload,dict) and payload.get('error'):raise ValueError(payload.get('reason','Provider returned an error'))
   entry={'url':url,'saved':time.time(),'data':payload,**headers};entry['_residentBytes']=resident_size(entry);return entry
  self.io.submit('decode:'+url,decode,lambda entry,exc:self.decoded(url,item,host,entry,exc));self.pump()
 def decoded(self,url,item,host,entry,exc):
  if self.closed or self.flights.get(url) is not item:return
  if exc is None:
   self.remember(self.key(url),entry);meta={k:v for k,v in entry.items() if not k.startswith('_') and (not item['binary'] or k!='data')}
   if item['binary']:self.writer.submit(self.root/(self.key(url)+'.bin'),entry['data'],immutable=True)
   self.writer.submit(self.root/(self.key(url)+'.json'),meta,immutable=True)
   result=self.envelope(url,entry,item['ttl'],cache=False);self.health[host]={'provider':host,'status':'Available','lastSuccess':entry['saved'],'error':''}
  else:
   error=str(exc);entry=item['entry'];result=self.envelope(url,entry,item['ttl'],error) if entry else {'data':None,'saved':0,'stale':True,'error':error,'source':url,'cache':False}
   previous=self.health.get(host,{});self.health[host]={'provider':host,'status':'Unavailable / cached fallback' if entry else 'Unavailable','lastSuccess':previous.get('lastSuccess',0),'error':error}
   logging.warning('Provider %s: %s',host,error[:240])
  self.flights.pop(url,None)
  for _,callback in tuple(item['callbacks']):
   try:callback(result)
   except Exception:logging.exception('Provider callback failed')
  self.healthChanged.emit();self.pump()
 def retry(self,url,item):
  if self.flights.get(url) is item:self.queue.append(url);self.pump()
 def prune(self):
  self.io.submit('prune',self.pruneFiles,lambda result,error:None)
 def pruneFiles(self):
  files=sorted((p for p in self.root.iterdir() if p.is_file() and p.suffix in ('.bin','.json')),key=lambda p:p.stat().st_mtime,reverse=True);total=0
  for p in files:
   total+=p.stat().st_size
   if total>self.limitMB*1024**2:
    try:p.unlink()
    except OSError:pass
 def clear(self):
  self.cache.clear();self.misses.clear();self.cacheBytes=0
  self.io.submit('clear',self.clearFiles,lambda result,error:None)
 def clearFiles(self):
  for p in self.root.iterdir():
   if p.is_file() and p.suffix in ('.bin','.json'):
    try:p.unlink()
    except OSError:pass
 def close(self):
  self.closed=True
  for item in tuple(self.flights.values()):
   if item['reply']:item['reply'].abort()
  self.flights.clear();self.queue.clear();self.loads.clear();self.io.close()
