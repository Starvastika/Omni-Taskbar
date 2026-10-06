import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import WeatherCenter 1.0
import "../components"
ColumnLayout {
 id:root;property var rows:null;property var dataset:rows===null?weather.hourlyModel:rows;property var series:weather.series;property var keys:weather.uiState.chart.series;property int horizon:weather.uiState.prefs.horizon;property bool pinned:false
 property alias chart:chart
 property var inspection:chart.inspection
 RowLayout {Layout.fillWidth:true
  Label {text:chart.rangeLabel;color:"#aaa";Layout.fillWidth:true;elide:Text.ElideRight}
  WButton {text:"−";onClicked:chart.zoom(1.4)}WButton {text:"+";onClicked:chart.zoom(.7)}WButton {text:"Reset";onClicked:chart.reset()}
  WButton {text:"Copy CSV";onClicked:weather.act("copy",JSON.stringify({text:chart.csv()}))}
  WButton {text:"Export";onClicked:weather.act("export",JSON.stringify({name:"weather-chart",text:chart.csv()}))}
 }
 Item {Layout.fillWidth:true;Layout.preferredHeight:Math.max(285,root.keys.length>4?425:320)
  WeatherChart {id:chart;objectName:"weatherChart";anchors.fill:parent;dataset:root.dataset;series:root.series;keys:root.keys;horizon:root.horizon;lineWidth:weather.uiState.prefs.lineWidth;dataPalette:weather.uiState.prefs.palette
   Image {anchors.fill:parent;source:chart.renderSource;asynchronous:true;cache:false;retainWhileLoading:true;smooth:true}
  }
  Rectangle {x:root.inspection.x||0;y:20;height:parent.height-50;width:1;color:"#ddd";visible:root.inspection.index!==undefined}
  MouseArea {anchors.fill:parent;hoverEnabled:true;acceptedButtons:Qt.LeftButton|Qt.RightButton
   property real lastX;property real startX;property bool dragged:false
   onPressed:mouse=>{lastX=mouse.x;startX=mouse.x;dragged=false;forceActiveFocus()}
   onPositionChanged:mouse=>{if(pressed&&pressedButtons===Qt.LeftButton){if(Math.abs(mouse.x-startX)>5)dragged=true;if(dragged){chart.pan((lastX-mouse.x)/Math.max(1,width)*root.horizon);lastX=mouse.x}}else if(!root.pinned)chart.inspect(mouse.x)}
   onReleased:mouse=>{if(mouse.button===Qt.RightButton)chartMenu.popup();else if(!dragged){chart.inspect(mouse.x);root.pinned=!root.pinned}}
   onWheel:wheel=>{if(wheel.modifiers&Qt.ControlModifier){chart.zoom(wheel.angleDelta.y>0?.8:1.25);wheel.accepted=true}else wheel.accepted=false}
   Keys.onLeftPressed:chart.step(-1);Keys.onRightPressed:chart.step(1)
   Keys.onPressed:event=>{if(event.key===Qt.Key_Home){chart.reset();event.accepted=true}}
  }
 }
 Flow {Layout.fillWidth:true;Layout.preferredHeight:implicitHeight;spacing:12
  Repeater {model:root.series.filter(s=>root.keys.indexOf(s.key)>=0);Label {required property var modelData;required property int index;text:["━","┅","┈"][index%3]+" "+modelData.label+" ("+modelData.unit+")";color:weather.uiState.prefs.palette==="grayscale"?["#fff","#bbb","#888"][index%3]:["#f1f1f1","#e0bb58","#aabbd3","#cc9ec3","#8bc3a2","#e8ab8b"][index%6]}}
 }
 Label {Layout.fillWidth:true;wrapMode:Text.Wrap;color:"#bbb";text:root.inspection.index===undefined?"Hover to inspect · click pins a time · drag pans · Ctrl+wheel zooms · arrow keys step · dark bands are night":(root.pinned?"Pinned · ":"")+root.inspection.date+" "+root.inspection.label+" · "+root.keys.map(k=>k+": "+(root.inspection.formatted&&root.inspection.formatted[k]!==undefined?root.inspection.formatted[k]:root.inspection.values[k]===undefined?"Unavailable":Number(root.inspection.values[k]).toFixed(2))).join("   |   ")}
 WMenu {id:chartMenu
  MenuItem {text:"Reset zoom";onTriggered:chart.reset()}
  MenuItem {text:"Copy visible data";onTriggered:weather.act("copy",JSON.stringify({text:chart.csv()}))}
  MenuItem {text:"Copy inspected point";onTriggered:weather.act("copy",JSON.stringify({text:JSON.stringify(chart.inspection,null,2)}))}
  MenuItem {text:"Export CSV";onTriggered:weather.act("export",JSON.stringify({name:"weather-chart",text:chart.csv()}))}
  MenuItem {text:"Raw provider data";onTriggered:weather.act("rawCopy","{}")}
 }
}
