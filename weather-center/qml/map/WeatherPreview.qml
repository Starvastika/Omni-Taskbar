import QtQuick
import QtQuick.Controls
Item {
 id:root;clip:true;property var preview:weather.previewData;property real span:preview.span||8192
 property real homeX:(weather.uiState.selected.lon+180)/360;property real homeY:(1-Math.asinh(Math.tan(weather.uiState.selected.lat*Math.PI/180))/Math.PI)/2
 Rectangle {anchors.fill:parent;color:"#1b1b1b"}
 Item {id:base;x:root.width/2-root.homeX*root.span;y:root.height/2-root.homeY*root.span;width:root.span;height:root.span
  ClippedMapImage {viewport:root;worldX:base.x;worldY:base.y;span:root.span;source:weather.mapData.land}
 }
 Image {source:root.preview.radar||"";x:root.width/2+((root.preview.x||0)-root.homeX)*root.span;y:root.height/2+((root.preview.y||0)-root.homeY)*root.span;width:256;height:256;opacity:weather.uiState.prefs.mapOpacity;smooth:true}
 Image {source:root.preview.coverage||"";x:root.width/2+((root.preview.x||0)-root.homeX)*root.span;y:root.height/2+((root.preview.y||0)-root.homeY)*root.span;width:256;height:256;opacity:.45}
 Rectangle {anchors.centerIn:parent;width:16;height:16;radius:8;color:"#fff";border.color:"#222";border.width:2}
 Label {x:root.width/2+15;y:root.height/2;text:weather.uiState.selected.name;color:"#fff";style:Text.Outline;styleColor:"#111"}
 Label {anchors.bottom:parent.bottom;anchors.left:parent.left;anchors.margins:8;text:root.preview.time||"Radar preview loading / unavailable";color:"#ddd";style:Text.Outline;styleColor:"#111"}
}
