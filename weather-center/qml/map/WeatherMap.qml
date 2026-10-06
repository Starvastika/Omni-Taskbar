import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
Item {
 id:map;objectName:"weatherMap";clip:true;focus:true
 property var layerData:weather.mapData
 property real zoom:weather.uiState.map.zoom;property real panX:weather.uiState.map.x;property real panY:weather.uiState.map.y
 property real canonicalX:((panX+.5)%1+1)%1-.5
 property real span:Math.max(1,Math.min(width,height)*zoom)
 property int firstCopy:Math.floor(-width/(2*span)-canonicalX-.5)
 property int lastCopy:Math.ceil(width/(2*span)-canonicalX+.5)
 property var selected:weather.uiState.selected
 property real cursorLat:0;property real cursorLon:0;property real pendingLat:0;property real pendingLon:0
 function lon(value){return ((value+180)%360+360)%360-180}
 function merc(lat){let r=Math.max(-85.05112878,Math.min(85.05112878,lat))*Math.PI/180;return (1-Math.log(Math.tan(Math.PI/4+r/2))/Math.PI)/2}
 function lat(value){return Math.atan(Math.sinh(Math.PI*(1-2*value)))*180/Math.PI}
 function sx(longitude,copy){return width/2+(longitude/360+canonicalX+copy)*span}
 function sy(latitude){return height/2+(merc(latitude)-.5+panY)*span}
 function refreshViewport(){if(visible)weather.viewport(width,height,zoom,canonicalX,panY)}
 function persist(){save.restart();viewportTimer.restart()}
 function constrain(){panY=Math.max(-.5,Math.min(.5,panY))}
 function zoomBy(factor){zoom=Math.max(1,Math.min(128,zoom*factor));constrain();persist()}
 function reset(){zoom=1;panX=0;panY=0;persist()}
 function focusLocation(location){if(location&&location.lat!==undefined){zoom=12;let target=-lon(location.lon)/360;panX=target+Math.round(panX-target);panY=.5-merc(location.lat);persist()}}
 function home(){focusLocation(weather.uiState.locations.find(c=>c.id===weather.uiState.homeId))}
 function fit(){
  let pins=weather.uiState.locations;if(!pins.length)return
  let xs=pins.map(c=>(lon(c.lon)+360)%360).sort((a,b)=>a-b),ys=pins.map(c=>merc(c.lat));let gap=-1,start=0
  for(let i=0;i<xs.length;i++){let next=i+1<xs.length?xs[i+1]:xs[0]+360;if(next-xs[i]>gap){gap=next-xs[i];start=next%360}}
  let lonSpan=Math.max(15,360-gap);let ySpan=Math.max(.06,Math.max(...ys)-Math.min(...ys));zoom=Math.max(1,Math.min(128,Math.min(width/Math.min(width,height)/(lonSpan/360),height/Math.min(width,height)/ySpan)*.75))
  let target=-(start+(360-gap)/2)/360;panX=target+Math.round(panX-target);panY=.5-(Math.max(...ys)+Math.min(...ys))/2;persist()
 }
 function inspectPoint(){if(Math.abs(cursorLat)<=85.05113)weather.act("inspect",JSON.stringify({lat:cursorLat,lon:cursorLon}))}
 function point(x,y){map.pendingLon=lon(((x-width/2)/span-canonicalX)*360);map.pendingLat=lat((y-height/2)/span+.5-panY)}
 onZoomChanged:viewportTimer.restart();onPanXChanged:viewportTimer.restart();onPanYChanged:viewportTimer.restart();onWidthChanged:viewportTimer.restart();onHeightChanged:viewportTimer.restart();onVisibleChanged:if(visible)viewportTimer.restart()
 Component.onCompleted:viewportTimer.restart()
 Timer {id:save;interval:600;onTriggered:weather.act("map",JSON.stringify({zoom:map.zoom,x:map.canonicalX,y:map.panY}))}
 Timer {id:viewportTimer;interval:150;onTriggered:map.refreshViewport()}
 Timer {id:hoverTimer;interval:100;onTriggered:{map.cursorLat=map.pendingLat;map.cursorLon=map.pendingLon}}
 Keys.onPressed:event=>{if(event.key===Qt.Key_Plus||event.key===Qt.Key_Equal){zoomBy(1.3);event.accepted=true}else if(event.key===Qt.Key_Minus){zoomBy(1/1.3);event.accepted=true}else if(event.key===Qt.Key_Home){home();event.accepted=true}}
 Rectangle {anchors.fill:parent;color:"#1b1b1b"}
 Label {anchors.centerIn:parent;text:"Loading offline geography…";visible:!map.layerData.ready;color:"#aaa"}
 Repeater {model:Math.max(0,map.lastCopy-map.firstCopy+1)
  delegate:Item {id:copy;required property int index;property int worldCopy:map.firstCopy+index;x:map.sx(-180,worldCopy);y:map.height/2+(-.5+map.panY)*map.span;width:map.span;height:map.span
   ClippedMapImage {viewport:map;worldX:copy.x;worldY:copy.y;span:map.span;source:map.layerData.land}
   ClippedMapImage {viewport:map;worldX:copy.x;worldY:copy.y;span:map.span;source:weather.uiState.prefs.mapDay?map.layerData.solar:""}
   Repeater {model:map.layerData.tiles
    delegate:Item {required property var modelData;x:modelData.x*copy.width;y:modelData.y*copy.height;width:modelData.width*copy.width;height:width
     Image {anchors.fill:parent;source:modelData.radar;visible:weather.uiState.map.layer==="radar";opacity:weather.uiState.prefs.mapOpacity;smooth:weather.uiState.prefs.radarSmooth;cache:true}
     Image {anchors.fill:parent;source:modelData.coverage;visible:weather.uiState.map.layer==="radar"||weather.uiState.map.layer==="coverage";opacity:weather.uiState.map.layer==="coverage"?.7:.35;cache:true}
    }
   }
   ClippedMapImage {viewport:map;worldX:copy.x;worldY:copy.y;span:map.span;source:weather.uiState.map.layer==="alerts"?map.layerData.alerts:"";opacity:weather.uiState.prefs.mapOpacity}
  }
 }
 MouseArea {id:gestures;anchors.fill:parent;acceptedButtons:Qt.LeftButton|Qt.RightButton;hoverEnabled:true;cursorShape:pressed?Qt.ClosedHandCursor:Qt.OpenHandCursor
  property real lastX;property real lastY;property real startX;property real startY;property bool dragged:false
  onPressed:mouse=>{lastX=startX=mouse.x;lastY=startY=mouse.y;dragged=false;map.forceActiveFocus()}
  onPositionChanged:mouse=>{map.point(mouse.x,mouse.y);if(!hoverTimer.running)hoverTimer.start();if(pressed&&pressedButtons===Qt.LeftButton){if(Math.abs(mouse.x-startX)+Math.abs(mouse.y-startY)>5)dragged=true;map.panX+=(mouse.x-lastX)/map.span;map.panY+=(mouse.y-lastY)/map.span;map.constrain();lastX=mouse.x;lastY=mouse.y}}
  onReleased:mouse=>{map.point(mouse.x,mouse.y);map.cursorLat=map.pendingLat;map.cursorLon=map.pendingLon;if(mouse.button===Qt.RightButton)context.popup();else if(dragged)map.persist();else map.inspectPoint()}
  onWheel:wheel=>{map.zoomBy(wheel.angleDelta.y>0?1.2:1/1.2);wheel.accepted=true}
 }
 Repeater {model:Math.max(0,map.lastCopy-map.firstCopy+1)
  delegate:Item {id:group;required property int index;property int copyIndex:map.firstCopy+index;anchors.fill:parent
   Repeater {model:map.layerData.samples
    delegate:Item {required property var modelData;x:map.sx(modelData.lon,group.copyIndex)-20;y:map.sy(modelData.lat)-20;width:40;height:40
     Rectangle {anchors.centerIn:parent;width:32;height:32;radius:16;color:modelData.color;opacity:weather.uiState.prefs.mapOpacity;border.color:"#ddd"}
     Label {anchors.centerIn:parent;text:modelData.direction!==null&&modelData.direction!==undefined?"↑":"•";rotation:modelData.direction||0;color:"#fff"}
     MouseArea {id:sampleHover;anchors.fill:parent;hoverEnabled:true;onClicked:weather.act("inspect",JSON.stringify({lat:modelData.lat,lon:modelData.lon}))}
     ToolTip.visible:sampleHover.containsMouse;ToolTip.text:modelData.text+"\nModeled point sample; not radar"
    }
   }
   Repeater {model:weather.uiState.locations.filter(l=>l.id===weather.uiState.homeId?weather.uiState.prefs.mapHome:weather.uiState.prefs.mapPins)
    delegate:Item {required property var modelData;property bool chosen:modelData.id===map.selected.id;property bool isHome:modelData.id===weather.uiState.homeId;x:map.sx(modelData.lon,group.copyIndex)-12;y:map.sy(modelData.lat)-12;width:24;height:24
     Rectangle {anchors.centerIn:parent;width:chosen?28:18;height:width;radius:width/2;color:isHome?"#ddd":chosen?"#fff":"#bbb";border.color:"#161616";border.width:2}
     Label {anchors.centerIn:parent;text:isHome?"⌂":chosen?"◉":"•";color:"#222"}
     Label {x:25;y:3;text:(modelData.favorite?"★ ":"")+modelData.name;visible:weather.uiState.prefs.mapLabels||chosen;color:"#eee";style:Text.Outline;styleColor:"#111"}
     MouseArea {id:pin;anchors.fill:parent;hoverEnabled:true;onClicked:weather.act("select",JSON.stringify({id:modelData.id}))}
     ToolTip.visible:pin.containsMouse;ToolTip.text:(isHome?"Home · ":"")+(chosen?"Selected · ":"")+modelData.name+" · "+modelData.region+" · "+modelData.zone
    }
   }
   Item {visible:map.selected.temporary===true;x:map.sx(map.selected.lon||0,group.copyIndex)-10;y:map.sy(map.selected.lat||0)-10;width:20;height:20
    Rectangle {anchors.centerIn:parent;width:16;height:16;rotation:45;color:"transparent";border.color:"#fff";border.width:2}
    Label {x:24;text:"Inspect · "+map.selected.name;color:"#eee";style:Text.Outline;styleColor:"#111"}
   }
  }
 }
 Flow {anchors.top:parent.top;anchors.left:parent.left;anchors.right:parent.right;anchors.margins:10;spacing:6
  WButton {text:"−";onClicked:map.zoomBy(1/1.4)}WButton {text:"+";onClicked:map.zoomBy(1.4)}WButton {text:"Reset";onClicked:map.reset()}
  WButton {text:"Home";onClicked:map.home()}WButton {text:"Focus selected";onClicked:map.focusLocation(map.selected)}WButton {text:"Fit saved";onClicked:map.fit()}
 }
 Label {anchors.bottom:parent.bottom;anchors.right:parent.right;anchors.margins:10;text:map.cursorLat.toFixed(3)+"°, "+map.cursorLon.toFixed(3)+"° · Natural Earth";color:"#ddd";style:Text.Outline;styleColor:"#111"}
 WMenu {id:context
  MenuItem {text:"Inspect here";onTriggered:map.inspectPoint()}
  MenuItem {text:"Save inspected location";enabled:!!map.selected.id;onTriggered:weather.act("save","{}")}
  MenuItem {text:"Set inspected location as Home";enabled:!!map.selected.id;onTriggered:weather.act("home","{}")}
  MenuItem {text:"Copy coordinates";onTriggered:weather.act("copy",JSON.stringify({text:map.cursorLat.toFixed(5)+", "+map.cursorLon.toFixed(5)}))}
  MenuItem {text:"Focus here";onTriggered:map.focusLocation({lat:map.cursorLat,lon:map.cursorLon})}
  MenuItem {text:"Open location details";onTriggered:weather.act("page",JSON.stringify({value:11}))}
  MenuItem {text:"Clear temporary inspection / return Home";onTriggered:{let home=weather.uiState.locations.find(c=>c.id===weather.uiState.homeId);if(home)weather.act("select",JSON.stringify({id:home.id}))}}
 }
}
