import QtQuick
Item {
 id:crop
 required property Item viewport
 required property real worldX
 required property real worldY
 required property real span
 property string source:""
 property int rasterSize:2048
 property bool hardware:GraphicsInfo.api!==GraphicsInfo.Unknown&&GraphicsInfo.api!==GraphicsInfo.Software&&GraphicsInfo.api!==GraphicsInfo.Null
 property int leftPixel:Math.max(0,Math.min(rasterSize,Math.floor(-worldX/Math.max(1,span)*rasterSize)))
 property int topPixel:Math.max(0,Math.min(rasterSize,Math.floor(-worldY/Math.max(1,span)*rasterSize)))
 property int rightPixel:Math.max(0,Math.min(rasterSize,Math.ceil((viewport.width-worldX)/Math.max(1,span)*rasterSize)))
 property int bottomPixel:Math.max(0,Math.min(rasterSize,Math.ceil((viewport.height-worldY)/Math.max(1,span)*rasterSize)))
 x:leftPixel/rasterSize*span;y:topPixel/rasterSize*span
 width:Math.max(0,rightPixel-leftPixel)/rasterSize*span
 height:Math.max(0,bottomPixel-topPixel)/rasterSize*span
 visible:width>0&&height>0
 // Hardware keeps one canonical 2048 px texture and changes only transforms.
 // The software fallback keeps bounded raster crops; both share world geometry.
 Image {x:crop.hardware?-crop.x:0;y:crop.hardware?-crop.y:0
  width:crop.hardware?crop.span:crop.width;height:crop.hardware?crop.span:crop.height
  asynchronous:true;smooth:true;cache:true;retainWhileLoading:true
  source:crop.visible&&crop.source?(crop.hardware?crop.source:crop.source+(crop.source.indexOf("?")>=0?"&":"?")+"crop="+[crop.leftPixel,crop.topPixel,crop.rightPixel-crop.leftPixel,crop.bottomPixel-crop.topPixel].join(",")):""
 }
}
