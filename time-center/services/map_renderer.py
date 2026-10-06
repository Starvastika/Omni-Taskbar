"""Worker-side projected map cache; shared QImages for every horizontal copy."""
import json,math,threading
from pathlib import Path
from PySide6.QtCore import Qt,QRectF
from PySide6.QtGui import QImage,QPainter,QPainterPath,QColor,QPen
from PySide6.QtQuick import QQuickImageProvider

class MapImages(QQuickImageProvider):
    def __init__(self):
        super().__init__(QQuickImageProvider.Image);self.images={};self.lock=threading.Lock()
    def install(self,images):
        with self.lock:self.images.update(images)
    def requestImage(self,identity,size,requestedSize):
        with self.lock:image=self.images.get(identity.split('?')[0],QImage())
        size.setWidth(image.width());size.setHeight(image.height())
        return image

class MapRenderer:
    width=1536;height=768
    def __init__(self,path):self.path=Path(path);self.polygons=None;self.land={}
    def px(self,lon):return (lon+180)/360*self.width
    def py(self,lat):return (90-lat)/180*self.height
    def blank(self):
        image=QImage(self.width,self.height,QImage.Format_ARGB32_Premultiplied);image.fill(Qt.transparent);return image
    def geometry(self):
        if self.polygons is not None:return
        polygons=[]
        for feature in json.loads(self.path.read_text('utf-8'))['features']:
            g=feature['geometry'];items=g['coordinates'] if g['type']=='MultiPolygon' else [g['coordinates']]
            for poly in items:
                path=QPainterPath()
                for index,(lon,lat,*_) in enumerate(poly[0]):
                    if index:path.lineTo(self.px(lon),self.py(lat))
                    else:path.moveTo(self.px(lon),self.py(lat))
                path.closeSubpath();polygons.append(path)
        self.polygons=polygons
    def render(self,flags,night):
        self.geometry();grid=flags['mapGrid']
        if grid not in self.land:
            image=self.blank();p=QPainter(image);p.setRenderHint(QPainter.Antialiasing)
            if grid:
                p.setPen(QPen(QColor('#303030'),1))
                for lon in range(-180,181,30):p.drawLine(int(self.px(lon)),0,int(self.px(lon)),self.height)
                for lat in range(-60,61,30):p.drawLine(0,int(self.py(lat)),self.width,int(self.py(lat)))
            p.setPen(QPen(QColor('#777777'),.8));p.setBrush(QColor('#555555'))
            for path in self.polygons:p.drawPath(path)
            p.end();self.land[grid]=image
        solar=self.blank();p=QPainter(solar);p.setRenderHint(QPainter.Antialiasing)
        pts=night['points'];pole=90 if night['northNight'] else -90
        path=QPainterPath();path.moveTo(self.px(-180),self.py(pole))
        for lon,lat in pts:path.lineTo(self.px(lon),self.py(lat))
        path.lineTo(self.px(180),self.py(pole));path.closeSubpath()
        if flags['mapDay']:p.fillPath(path,QColor(7,7,7,158))
        if flags['mapTerminator']:
            line=QPainterPath();line.moveTo(self.px(pts[0][0]),self.py(pts[0][1]))
            for lon,lat in pts[1:]:line.lineTo(self.px(lon),self.py(lat))
            p.setPen(QPen(QColor(177,177,177,128),2));p.drawPath(line)
        if flags['mapTwilight']:
            sublon,decl=night['subsolar'];dec=math.radians(decl)
            for lat in range(-88,90,4):
                for lon in range(-177,180,6):
                    rad=math.radians(lat);elevation=math.degrees(math.asin(math.sin(rad)*math.sin(dec)+math.cos(rad)*math.cos(dec)*math.cos(math.radians(lon-sublon))))
                    if -18<elevation<0:
                        color=QColor(143,143,143,71) if elevation>-6 else QColor(112,112,112,56) if elevation>-12 else QColor(83,83,83,43)
                        p.fillRect(QRectF(self.px(lon-3),self.py(lat+2),self.width/60+.3,self.height/45+.3),color)
        p.end();return {'land':self.land[grid],'solar':solar}
