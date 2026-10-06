import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import TimeCenter 1.0
Item {
    id: map;objectName:"worldMap"
    property var cities: bridge.cities || []
    property var selected: bridge.selected || ({})
    property var night: bridge.night
    function canonical(value) {return ((value+.5)%1+1)%1-.5}
    function longitude(value) {return ((value+180)%360+360)%360-180}
    property real renderPanX:canonical(panX)
    property real worldSpan:Math.max(1,worldWidth*zoom)
    property int firstCopy:Math.floor(-width/(2*worldSpan)-renderPanX-.5)
    property int lastCopy:Math.ceil(width/(2*worldSpan)-renderPanX+.5)
    property real zoom: bridge.state.map.zoom || 1
    property real panX: bridge.state.map.x || 0
    property real panY: bridge.state.map.y || 0
    property var prefs:bridge.state.prefs
    property var inspection:bridge.state.inspection || ({})
    property real cursorLon:0
    property real cursorLat:0
    property real pendingLon:0
    property real pendingLat:0
    Timer {id:cursorUpdate;interval:100;onTriggered:{map.cursorLon=map.pendingLon;map.cursorLat=map.pendingLat}}
    property bool dayLayer:prefs.mapDay
    property bool twilightLayer:prefs.mapTwilight
    property bool terminatorLayer:prefs.mapTerminator
    property bool gridLayer:prefs.mapGrid
    property bool sunLayer:prefs.mapSun
    function resetView() {zoom=prefs.mapDefaultZoom;panX=0;panY=0;persist()}
    function fit(includeInspection) {
        let pins=cities.filter(c=>c.lat!==null&&c.lat!==undefined)
        if(includeInspection&&inspection.lat!==undefined)pins.push(inspection)
        if(!pins.length)return
        let lons=pins.map(c=>(longitude(c.lon)+360)%360).sort((a,b)=>a-b),lats=pins.map(c=>c.lat)
        let gap=-1,start=0
        for(let i=0;i<lons.length;i++){let next=i+1<lons.length?lons[i+1]:lons[0]+360;if(next-lons[i]>gap){gap=next-lons[i];start=next%360}}
        let minX=start,maxX=start+360-gap,minY=Math.min(...lats),maxY=Math.max(...lats)
        zoom=Math.max(1,Math.min(10,Math.min(width/(worldWidth*Math.max(20,maxX-minX)/360),height/(worldHeight*Math.max(15,maxY-minY)/180))*.78))
        let target=-(minX+maxX)/720;panX=target+Math.round(panX-target);panY=(minY+maxY)/360;persist()
    }
    function inspect() {if(Math.abs(cursorLon)<=180&&Math.abs(cursorLat)<=90)bridge.inspectPoint(cursorLon,cursorLat)}
    property bool ready: false
    property real worldWidth:Math.min(width,height*2)
    property real worldHeight:worldWidth/2
    clip: true
    function sx(lon,copy=0) { return width/2 + (lon/360+renderPanX+copy)*worldWidth*zoom }
    function sy(lat) { return height/2 + (-lat/180*worldHeight+panY*worldHeight)*zoom }
    function repaint() {if(visible)bridge.requestMap()}
    function constrain() { panY=Math.max(-.5,Math.min(.5,panY)) }
    function persist() { save.restart() }
    function focusCity(lon,lat) { zoom=3;let target=-longitude(lon)/360;panX=target+Math.round(panX-target);panY=lat/180;persist() }
    function zoomBy(factor) { zoom=Math.max(1,Math.min(12,zoom*factor));constrain();persist() }
    onNightChanged: if(visible)bridge.requestMap()
    onVisibleChanged: if(visible) Qt.callLater(repaint)
    Component.onCompleted: { ready=true;Qt.callLater(repaint) }
    Timer { id:save;interval:500;onTriggered:bridge.act("map",JSON.stringify({zoom:map.zoom,x:map.canonical(map.panX),y:map.panY})) }
    Connections { target:bridge;function onFocusMap(lon,lat) { map.focusCity(lon,lat) } }
    Rectangle { anchors.fill:parent;color:Theme.ocean;radius:8 }
    Label {anchors.centerIn:parent;visible:!bridge.mapReady;text:"Loading map…";color:Theme.muted}
    Repeater {
        model:Math.max(0,map.lastCopy-map.firstCopy+1)
        delegate:Item {
            required property int index
            x:map.sx(-180,map.firstCopy+index);y:map.sy(90);width:map.worldSpan;height:map.worldSpan/2
            Image {anchors.fill:parent;source:bridge.mapLand;cache:true;smooth:true;asynchronous:true}
            Image {anchors.fill:parent;source:bridge.mapSolar;cache:true;smooth:true;asynchronous:true}
        }
    }
    MouseArea {
        anchors.fill:parent;hoverEnabled:true;acceptedButtons:Qt.LeftButton|Qt.RightButton;cursorShape:pressed?Qt.ClosedHandCursor:Qt.OpenHandCursor
        property real lastX;property real lastY;property real startX;property real startY;property bool dragged:false
        onPressed: mouse=> { lastX=mouse.x;lastY=mouse.y;startX=mouse.x;startY=mouse.y;dragged=false }
        onPositionChanged: mouse=> { map.pendingLon=map.longitude(((mouse.x-map.width/2)/map.zoom/map.worldWidth-map.renderPanX)*360);map.pendingLat=-((mouse.y-map.height/2)/map.zoom/map.worldHeight-map.panY)*180;if(!cursorUpdate.running)cursorUpdate.start();if(pressed&&pressedButtons===Qt.LeftButton) { if(Math.abs(mouse.x-startX)+Math.abs(mouse.y-startY)>5)dragged=true;map.panX+=(mouse.x-lastX)/map.worldWidth/map.zoom;map.panY+=(mouse.y-lastY)/map.worldHeight/map.zoom;map.constrain();lastX=mouse.x;lastY=mouse.y } }
        onReleased: mouse=> {if(mouse.button===Qt.RightButton){map.cursorLon=map.longitude(((mouse.x-map.width/2)/map.zoom/map.worldWidth-map.renderPanX)*360);map.cursorLat=-((mouse.y-map.height/2)/map.zoom/map.worldHeight-map.panY)*180;mapMenu.popup()}else if(dragged)map.persist();else {map.cursorLon=map.longitude(((mouse.x-map.width/2)/map.zoom/map.worldWidth-map.renderPanX)*360);map.cursorLat=-((mouse.y-map.height/2)/map.zoom/map.worldHeight-map.panY)*180;map.inspect()}}
        onWheel: wheel=> {map.zoomBy(wheel.angleDelta.y>0?1.18:1/1.18);wheel.accepted=true}
    }
    StableModel {id:markerModel;source:map.cities}
    Repeater {
        model:Math.max(0,map.lastCopy-map.firstCopy+1)
        delegate:Item {
            id:copyGroup;required property int index;property int copyIndex:map.firstCopy+index
            anchors.fill:parent
    Repeater {
        model:markerModel
        delegate:Item {
            id:marker;objectName:"mapMarker";property string cityId:rowData.id;required property var rowData;property var modelData:rowData
            property bool chosen:modelData.id===map.selected.id
            property bool homeCity:modelData.id===bridge.state.homeId
            property string role:(homeCity?"Home · ":"")+(chosen?"Selected · ":"")+(modelData.favorite?"Favorite · ":"")+"Saved city"
            visible:modelData.lat!==null&&modelData.lat!==undefined
            x:map.sx(modelData.lon,copyGroup.copyIndex)-12;y:map.sy(modelData.lat)-12;width:24;height:24
            Rectangle {anchors.centerIn:parent;width:pin.containsMouse?38:marker.chosen?30:22;height:width;radius:width/2;color:"transparent";border.width:marker.chosen?2:1;border.color:pin.containsMouse||marker.chosen?Theme.focus:marker.homeCity?"#eeeeee":"transparent";}
            Rectangle {anchors.centerIn:parent;visible:marker.chosen;width:22;height:22;radius:11;color:"transparent";border.color:Theme.focus;border.width:1}
            Rectangle {anchors.centerIn:parent;width:marker.homeCity?20:marker.chosen?13:9;height:width;radius:width/2;color:marker.chosen?Theme.focus:"#d4d4d4";border.color:"#191919"}
            Label {anchors.centerIn:parent;visible:marker.homeCity;text:"⌂";font.bold:true;font.pixelSize:16;color:"#1e1e1e"}
            Label {visible:marker.modelData.favorite;text:"★";x:18;y:-9;font.pixelSize:13;color:"#e4e4e4"}
            Label {visible:map.prefs.mapLabels||marker.chosen||pin.containsMouse;x:30;y:3;text:marker.modelData.name;color:marker.chosen?"#d0d0d0":"#f1f1f1";font.pixelSize:11;style:Text.Outline;styleColor:"#141414"}
            MouseArea {id:pin;anchors.fill:parent;hoverEnabled:true;cursorShape:Qt.PointingHandCursor;onClicked:bridge.act("select",JSON.stringify({id:marker.modelData.id}))}
            ToolTip.visible:pin.containsMouse;ToolTip.text:role+"\n"+modelData.name+" · "+modelData.time+"\n"+modelData.zone
        }
    }
    Item {
        visible:map.inspection.lat!==undefined&&map.inspection.lat!==null
        x:map.sx(map.inspection.lon||0,copyGroup.copyIndex)-10;y:map.sy(map.inspection.lat||0)-10;width:20;height:20
        Rectangle {anchors.centerIn:parent;width:13;height:13;rotation:45;color:"transparent";border.color:"#f1f1f1"}
        Label {x:26;text:(map.inspection.inspectionKind||"Inspection")+" · "+(map.inspection.name||"");font.pixelSize:11;color:"#dbdbdb";style:Text.Outline;styleColor:"#212121"}
        MouseArea {id:temporaryHover;anchors.fill:parent;hoverEnabled:true;onClicked:mapMenu.popup()}
        ToolTip.visible:temporaryHover.containsMouse;ToolTip.text:"Temporary location — not saved. Use Save inspected location."
    }
    Label {
        visible:map.sunLayer&&map.night.subsolar!==undefined
        x:map.sx(map.night.subsolar?map.night.subsolar[0]:0,copyGroup.copyIndex)-10;y:map.sy(map.night.subsolar?map.night.subsolar[1]:0)-10
        text:"☀  Subsolar point";font.pixelSize:12;color:"#e7e7e7";style:Text.Outline;styleColor:"#212121"
        MouseArea {id:sunHover;anchors.fill:parent;hoverEnabled:true}
        ToolTip.visible:sunHover.containsMouse;ToolTip.text:"Sun directly overhead at this coordinate. This is not a city or your location."
    }
        }
    }
    Flow {anchors.right:parent.right;anchors.left:parent.left;anchors.top:parent.top;anchors.margins:12;spacing:5
        TCButton {text:"−";onClicked:map.zoomBy(1/1.4)}
        TCButton {text:"+";onClicked:map.zoomBy(1.4)}
        TCButton {text:map.zoom.toFixed(1)+"×";onClicked:map.resetView();ToolTip.text:"Reset map";ToolTip.visible:hovered}
        TCButton {text:"Fit saved";onClicked:map.fit(false)}
        TCButton {text:"Fit all pins";onClicked:map.fit(true)}
        TCButton {text:"Home";enabled:!!bridge.state.homeId;onClicked:bridge.act("focus",JSON.stringify({id:bridge.state.homeId}))}
        TCButton {text:"Focus selected";onClicked:bridge.act("focus","{}")}
        TCButton {text:"Map settings ▾";onClicked:settings.open()}
    }
    Rectangle {visible:map.prefs.mapLegend;anchors.left:parent.left;anchors.bottom:parent.bottom;anchors.margins:12;width:360;height:75;color:"#e6232323";radius:7
        Label {anchors.fill:parent;anchors.margins:9;text:"⌂ Home    ◉ Selected    • Saved    ★ Favorite\n◇ Hollow: temporary inspection / search\n☀ Subsolar point: Sun directly overhead";color:"#cdcdcd";font.pixelSize:11;lineHeight:1.4}
    }
    Label {anchors.right:parent.right;anchors.bottom:parent.bottom;anchors.margins:12;text:map.prefs.mapCoordinates&&Math.abs(map.cursorLat)<=90&&Math.abs(map.cursorLon)<=180?map.cursorLat.toFixed(2)+"°, "+map.cursorLon.toFixed(2)+"°  ·  Natural Earth":"Natural Earth · offline vectors";font.pixelSize:10;color:"#bababa"}
    Popup {id:settings;x:Math.max(10,map.width-width-12);y:54;width:290;padding:16;modal:false;closePolicy:Popup.CloseOnEscape|Popup.CloseOnPressOutside
        onOpened:bridge.modal(1)
        onClosed:bridge.modal(-1)
        background:Rectangle {radius:9;color:Theme.elevated;border.color:"#5e5e5e"}
        contentItem:ColumnLayout {spacing:8
            Repeater {model:[['mapDay','Day / night'],['mapTwilight','Twilight bands'],['mapTerminator','Solar terminator'],['mapGrid','Graticule'],['mapLabels','Pin labels'],['mapLegend','Marker legend'],['mapFollow','Follow selected'],['mapSun','Subsolar point'],['mapCoordinates','Cursor coordinates']]
                TCSwitch {required property var modelData;text:modelData[1];checked:map.prefs[modelData[0]];onToggled:bridge.act("pref",JSON.stringify({key:modelData[0],value:checked}))}
            }
            TCButton {text:"Reset map";onClicked:map.resetView()}
            TCButton {text:"Clear inspection";enabled:map.inspection.lat!==undefined;onClicked:bridge.act("clearInspection","{}")}
        }
    }
    TCMenu {id:mapMenu
        MenuItem {text:"Inspect this coordinate";onTriggered:map.inspect()}
        MenuItem {text:"Save inspected location";enabled:map.inspection.lat!==undefined;onTriggered:bridge.act("addCity",JSON.stringify(map.inspection))}
        MenuItem {text:"Clear inspection";onTriggered:bridge.act("clearInspection","{}")}
        MenuItem {text:"Reset map";onTriggered:map.resetView()}
    }
}
