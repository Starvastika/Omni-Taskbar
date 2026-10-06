"""Cached-data meteogram with unit bands, night shading and precise inspection."""
import csv,io,math,time,weakref
from PySide6.QtCore import Property,Signal,Slot,QRectF,Qt,QTimer
from PySide6.QtQml import QJSValue
from PySide6.QtGui import QColor,QPen,QPainterPath,QFont,QImage,QPainter
from PySide6.QtQuick import QQuickItem
from shiboken6 import isValid

class PaintContext:
 def __init__(self,chart):
  self._width=chart.width();self._height=chart.height();self._part=chart.visibleRows();self._series=chart._series;self._keys=list(chart._keys);self._lineWidth=chart._lineWidth;self._palette=chart._palette
 def width(self):return self._width
 def height(self):return self._height
 def boundingRect(self):return QRectF(0,0,self._width,self._height)
 def visibleRows(self):return self._part

def display_points(part,key,span):
 """Pixel-scale first/min/max/last simplification, preserving gaps and peaks."""
 n=max(1,len(part)-1)
 if len(part)<=span*2:
  return [(j,row['values'].get(key)) for j,row in enumerate(part)]
 points=[];bucket=None;values=[]
 def flush():
  if values:
   chosen={values[0],values[-1],min(values,key=lambda x:x[1]),max(values,key=lambda x:x[1])}
   points.extend(sorted(chosen))
 for j,row in enumerate(part):
  value=row['values'].get(key)
  if value is None:flush();values=[];bucket=None;points.append((j,None));continue
  pixel=int(j/n*span)
  if bucket!=pixel:flush();values=[];bucket=pixel
  values.append((j,value))
 flush();return points

class WeatherChart(QQuickItem):
 changed=Signal();inspectionChanged=Signal();rangeChanged=Signal();datasetChanged=Signal();imageChanged=Signal()
 imageStore=None;renderWork=None;host=None;instances=weakref.WeakSet()
 def __init__(self,parent=None):
  super().__init__(parent);self._rows=[];self._source=None;self._series=[];self._keys=['temperature_2m','apparent_temperature','precipitation'];self._horizon=48;self.start=0;self.count=48;self._inspection={};self._lineWidth=2;self._palette='colorblind'
  self._imageKey='chart-'+str(id(self));self._imageVersion=0;self._sourceUrl='';self._dirty=True;self._renderTimer=QTimer(self);self._renderTimer.setSingleShot(True);self._renderTimer.timeout.connect(self.renderImage)
  self.widthChanged.connect(self.update);self.heightChanged.connect(self.update);self.visibleChanged.connect(self.update);self.instances.add(self)
  key=self._imageKey;store=self.imageStore
  if store:self.destroyed.connect(lambda _=None:store.remove(key))
 @Property(str,notify=imageChanged)
 def renderSource(self):return self._sourceUrl
 @classmethod
 def attachHost(cls,window):
  cls.host=window
  if window:window.visibleChanged.connect(cls.refreshVisible)
  cls.refreshVisible()
 @classmethod
 def refreshVisible(cls):
  for chart in tuple(cls.instances):
   if isValid(chart):chart.update()
   else:cls.instances.discard(chart)
 def update(self):
  if not isValid(self):return
  self._dirty=True;self._imageVersion+=1
  window=self.host
  if self.imageStore is not None and self.renderWork is not None and self.isVisible() and window and window.isVisible() and self.width()>0 and self.height()>0:self._renderTimer.start(0)
 def renderImage(self):
  window=self.host
  if not self._dirty or not self.isVisible() or not window or not window.isVisible():return
  version=self._imageVersion;context=PaintContext(self);ratio=window.devicePixelRatio();self._dirty=False
  def render():
   image=QImage(max(1,round(context.width()*ratio)),max(1,round(context.height()*ratio)),QImage.Format_ARGB32_Premultiplied);image.setDevicePixelRatio(ratio);image.fill(Qt.transparent)
   painter=QPainter(image);painter.setRenderHint(QPainter.Antialiasing);WeatherChart.paint(context,painter);painter.end();return image
  def adopt(image,error):
   if error or not isValid(self) or version!=self._imageVersion:return
   self.imageStore.install(self._imageKey,image);self._sourceUrl='image://weatherMap/'+self._imageKey+'?v='+str(version);self.imageChanged.emit()
  self.renderWork.submit(self._imageKey,render,adopt)
 @Property('QVariant',notify=datasetChanged)
 def dataset(self):return self._source if self._source else self._rows
 @dataset.setter
 def dataset(self,value):
  if isinstance(value,QJSValue):value=value.toVariant()
  source=value if hasattr(value,'rowsChanged') and hasattr(value,'rows') else None
  if source is self._source and source is not None:return
  if self._source:
   try:self._source.rowsChanged.disconnect(self.sourceRowsChanged)
   except (RuntimeError,TypeError):pass
  self._source=source
  if source:source.rowsChanged.connect(self.sourceRowsChanged);self.sourceRowsChanged()
  else:self.rows=value or []
  self.datasetChanged.emit()
 def sourceRowsChanged(self):self.rows=self._source.rows
 @Property('QVariantList',notify=changed)
 def rows(self):return self._rows
 @rows.setter
 def rows(self,value):
  fresh=not self._rows;self._rows=value or []
  if fresh:self.start=0;self.count=self._horizon
  self.clamp();self.changed.emit();self.update()
 @Property('QVariantList',notify=changed)
 def series(self):return self._series
 @series.setter
 def series(self,value):self._series=value or [];self.changed.emit();self.update()
 @Property('QStringList',notify=changed)
 def keys(self):return self._keys
 @keys.setter
 def keys(self,value):self._keys=list(value or []);self.changed.emit();self.update()
 @Property(int,notify=changed)
 def horizon(self):return self._horizon
 @horizon.setter
 def horizon(self,value):self._horizon=max(6,int(value));self.count=self._horizon;self.clamp();self.changed.emit();self.update()
 @Property(int,notify=changed)
 def lineWidth(self):return self._lineWidth
 @lineWidth.setter
 def lineWidth(self,value):self._lineWidth=max(1,min(4,int(value)));self.changed.emit();self.update()
 @Property(str,notify=changed)
 def dataPalette(self):return self._palette
 @dataPalette.setter
 def dataPalette(self,value):self._palette=value;self.changed.emit();self.update()
 @Property('QVariantMap',notify=inspectionChanged)
 def inspection(self):return self._inspection
 @Property(str,notify=rangeChanged)
 def rangeLabel(self):
  part=self.visibleRows();return (part[0]['date']+' '+part[0]['label']+' → '+part[-1]['date']+' '+part[-1]['label']) if part else 'Waiting for provider data'
 def visibleRows(self):return self._rows[self.start:self.start+self.count]
 def clamp(self):self.count=max(6,min(max(6,len(self._rows)),int(self.count)));self.start=max(0,min(max(0,len(self._rows)-self.count),int(self.start)));self.rangeChanged.emit()
 @Slot(float)
 def zoom(self,factor):self.count=int(self.count*factor);self.clamp();self.update()
 @Slot(float)
 def pan(self,delta):self.start+=round(delta);self.clamp();self.update()
 @Slot()
 def reset(self):self.start=0;self.count=self._horizon;self.clamp();self.update()
 @Slot(float)
 def inspect(self,x):
  fraction=max(0,min(1,(x-58)/max(1,self.width()-78)));index=self.start+round(fraction*(min(self.count,len(self._rows)-self.start)-1))
  if not self._rows:return
  index=max(0,min(len(self._rows)-1,index));row=self._rows[index]
  position=58+(index-self.start)/max(1,min(self.count,len(self._rows)-self.start)-1)*(self.width()-78)
  if self._inspection.get('index')==index and self._inspection.get('x')==position and self._inspection.get('values') is row['values']:return
  self._inspection={**row,'index':index,'x':position};self.inspectionChanged.emit()
 @Slot(int)
 def step(self,delta):
  index=max(0,min(len(self._rows)-1,self._inspection.get('index',self.start)+delta))
  if index<self.start:self.start=index
  if index>=self.start+self.count:self.start=index-self.count+1
  self.clamp();self.update();self.inspect(58+(index-self.start)/max(1,self.count-1)*(self.width()-78))
 @Slot(result=str)
 def csv(self):
  out=io.StringIO();writer=csv.writer(out);writer.writerow(['UTC','Local','Date']+self._keys)
  for row in self.visibleRows():writer.writerow([row.get('iso',row['epoch']),row['label'],row['date']]+[row['values'].get(k,'') for k in self._keys])
  return out.getvalue()
 def paint(self,p):
  p.fillRect(self.boundingRect(),QColor('#1c1c1c'));p.setFont(QFont('Segoe UI',9));part=self.visibleRows()
  if not part:p.setPen(QColor('#aaa'));p.drawText(self.boundingRect(),Qt.AlignCenter,'Data loads independently · cached data appears immediately');return
  selected=[s for s in self._series if s['key'] in self._keys];units=[]
  for s in selected:
   if s.get('unit','') not in units:units.append(s.get('unit',''))
  units=units[:5];left=58;right=self.width()-20;top=30;bottom=self.height()-34;span=max(1,right-left);band=max(40,(bottom-top)/max(1,len(units)));n=max(1,len(part)-1)
  colors=['#f1f1f1','#e0bb58','#aabbd3','#cc9ec3','#8bc3a2','#e8ab8b'] if self._palette!='grayscale' else ['#fff','#bbb','#888','#ddd','#666','#aaa']
  # Adjacent hourly night rectangles have the same union. Paint each run once
  # rather than blending/re-uploading hundreds of overlapping strips.
  run=None
  for j in range(len(part)+1):
   night=j<len(part) and part[j].get('night')
   if night and run is None:run=j
   elif not night and run is not None:
    p.fillRect(QRectF(left+run/n*span,top,(j-run)*span/n+1,bottom-top),QColor('#252525'));run=None
  for band_index,unit in enumerate(units):
   members=[s for s in selected if s.get('unit','')==unit];vals=[r['values'][s['key']] for r in part for s in members if r['values'].get(s['key']) is not None]
   if not vals:continue
   lo=min(vals);hi=max(vals)
   if any(s['key'] in ('precipitation','rain','snowfall','showers') for s in members):lo=min(0,lo)
   bars=any(s['key'] in ('precipitation','rain','snowfall','showers') for s in members)
   pad=max(.5,(hi-lo)*.1);lo=0 if bars else lo-pad;hi+=pad;y0=top+band_index*band+12;y1=top+(band_index+1)*band-16
   p.setPen(QColor('#454545'))
   for q in range(4):y=y0+(y1-y0)*q/3;p.drawLine(int(left),int(y),int(right),int(y));p.setPen(QColor('#aaa'));p.drawText(QRectF(2,y-9,51,20),Qt.AlignRight|Qt.AlignVCenter,f'{hi-(hi-lo)*q/3:.1f}');p.setPen(QColor('#454545'))
   p.setPen(QColor('#aaa'));p.drawText(QRectF(left,y0-18,span,16),unit+' · '+', '.join(s['label'] for s in members))
   for s in members:
    index=selected.index(s);color=QColor(colors[index%len(colors)]);p.setPen(QPen(color,self._lineWidth,Qt.DashLine if index%3==2 else Qt.SolidLine));path=QPainterPath();started=False
    for j,value in display_points(part,s['key'],span):
     if value is None:started=False;continue
     x=left+j/n*span;y=y1-(value-lo)/(hi-lo)*(y1-y0)
     if s['key'] in ('precipitation','rain','showers','snowfall'):
      if value<=0:continue
      p.fillRect(QRectF(x-1,y,max(2,span/n*.65),max(0,y1-y)),QColor(color.red(),color.green(),color.blue(),130));continue
     if started:path.lineTo(x,y)
     else:path.moveTo(x,y);started=True
    p.drawPath(path)
  first=part[0]['epoch'];last=part[-1]['epoch'];now=time.time()
  if first<=now<=last:
   x=left+(now-first)/max(1,last-first)*span;p.setPen(QPen(QColor('#fff'),1,Qt.DotLine));p.drawLine(int(x),int(top),int(x),int(bottom));p.drawText(int(x)+4,18,'Now')
  p.setPen(QColor('#bbb'))
  for q in range(5):
   index=round(q*n/4);row=part[index];x=left+index/n*span;p.drawText(QRectF(max(0,min(self.width()-130,x-58)),bottom+7,130,24),Qt.AlignCenter,row['date']+' '+row['label'])
