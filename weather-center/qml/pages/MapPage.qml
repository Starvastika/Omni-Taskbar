import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../map"
ColumnLayout {
 id:mapPage;property var layerData:weather.mapData
 spacing:10
 RowLayout {Layout.fillWidth:true
  Label {text:"WORLD WEATHER MAP";font.pixelSize:21;font.bold:true;Layout.fillWidth:true}
  WCombo {Layout.preferredWidth:350;model:mapPage.layerData.layers.map(l=>l.name);currentIndex:mapPage.layerData.layers.findIndex(l=>l.id===weather.uiState.map.layer);onActivated:if(currentIndex>=0)weather.act("mapAction",JSON.stringify({op:"layer",value:mapPage.layerData.layers[currentIndex].id}))}
  WButton {text:"Refresh field";onClicked:weather.act("mapAction",JSON.stringify({op:"refresh"}))}
 }
 WSplit {id:split;Layout.fillWidth:true;Layout.fillHeight:true;onResizingChanged:if(!resizing&&width>0)weather.act("layout",JSON.stringify({key:"mapSplit",value:world.width/width}))
  WeatherMap {id:world;SplitView.preferredWidth:split.width*weather.uiState.layout.mapSplit;SplitView.minimumWidth:450}
  ScrollView {id:inspectorScroll;SplitView.fillWidth:true;SplitView.minimumWidth:270;clip:true;contentWidth:availableWidth
   ColumnLayout {width:inspectorScroll.availableWidth;spacing:12
    Label {text:weather.uiState.selected.temporary?"TEMPORARY INSPECTION":"SELECTED LOCATION";font.bold:true;color:"#aaa"}
    Label {text:weather.summary.location;font.pixelSize:23;wrapMode:Text.Wrap;Layout.fillWidth:true}
    Label {text:weather.summary.region+"\n"+weather.uiState.selected.zone+"\n"+Number(weather.uiState.selected.lat).toFixed(4)+"°, "+Number(weather.uiState.selected.lon).toFixed(4)+"°";color:"#bbb";lineHeight:1.6;wrapMode:Text.Wrap;Layout.fillWidth:true}
    Label {text:weather.summary.temperature+"\n"+weather.summary.condition;font.pixelSize:24}
    Label {text:(weather.summary.stale?"STALE · ":"")+weather.summary.age+"\n"+weather.summary.localTime+"\nAQI "+weather.summary.aqi;color:"#aaa";wrapMode:Text.Wrap;Layout.fillWidth:true}
    Flow {Layout.fillWidth:true;Layout.preferredHeight:implicitHeight;spacing:6;WButton {text:"Save location";onClicked:weather.act("save","{}")}WButton {text:"Set Home";onClicked:weather.act("home","{}")}WButton {text:"Hourly →";onClicked:weather.act("page",JSON.stringify({value:1}))}}
    Label {text:"Next hours";font.bold:true}
    Repeater {model:weather.hourlyPreview;Label {required property var modelData;text:modelData.label+"  "+(modelData.formatted.temperature_2m||"—")+" · "+(modelData.formatted.precipitation||"—");color:"#ccc"}}
    Label {text:mapPage.layerData.coverage;color:"#bbb";wrapMode:Text.Wrap;Layout.fillWidth:true}
    Label {text:mapPage.layerData.status;color:"#999";wrapMode:Text.Wrap;Layout.fillWidth:true}
   }
  }
 }
 Rectangle {Layout.fillWidth:true;Layout.preferredHeight:Math.max(105,colorLegend.implicitHeight+legendText.implicitHeight+52);color:"#252525";radius:8
  ColumnLayout {anchors.fill:parent;anchors.margins:10;spacing:5
   Label {id:legendText;text:mapPage.layerData.legend;Layout.fillWidth:true;wrapMode:Text.Wrap;color:"#ccc";font.pixelSize:11}
   Flow {id:colorLegend;visible:weather.uiState.map.layer!=="none"&&weather.uiState.map.layer!=="alerts"&&weather.uiState.map.layer!=="coverage";Layout.fillWidth:true;Layout.preferredHeight:implicitHeight;spacing:12
    Repeater {model:mapPage.layerData.sampleLegend;Row {required property var modelData;spacing:5;Rectangle {width:35;height:8;y:5;color:modelData.color}Label {text:(modelData.type?modelData.type+" ":"")+Number(modelData.value).toFixed(1);color:"#bbb"}}}
   }
   RowLayout {Label {text:"Opacity";color:"#aaa"}Slider {from:.1;to:1;value:weather.uiState.prefs.mapOpacity;onMoved:weather.act("pref",JSON.stringify({key:"mapOpacity",value:[.3,.5,.7,1].reduce((a,b)=>Math.abs(b-value)<Math.abs(a-value)?b:a)}))}}
  }
 }
 RowLayout {Layout.fillWidth:true;visible:mapPage.layerData.frames.length>0
  WButton {text:"◀";onClicked:weather.act("mapAction",JSON.stringify({op:"step",delta:-1}))}
  WButton {text:mapPage.layerData.playing?"Pause":"Play";enabled:mapPage.layerData.frames.length>0;onClicked:weather.act("mapAction",JSON.stringify({op:"play"}))}
  WButton {text:"▶";onClicked:weather.act("mapAction",JSON.stringify({op:"step",delta:1}))}
  Slider {Layout.fillWidth:true;from:0;to:Math.max(0,mapPage.layerData.frames.length-1);stepSize:1;value:mapPage.layerData.frame;onMoved:weather.act("mapAction",JSON.stringify({op:"frame",value:Math.round(value)}))}
  Label {text:mapPage.layerData.frameLabel;color:"#ccc"}WButton {text:"Now";onClicked:weather.act("mapAction",JSON.stringify({op:"now"}))}
  WCombo {model:["0.75s","1.5s","3s"];currentIndex:[750,1500,3000].indexOf(weather.uiState.prefs.radarSpeed);onActivated:weather.act("pref",JSON.stringify({key:"radarSpeed",value:[750,1500,3000][currentIndex]}))}
 }
 WButton {text:"Weather data by RainViewer · Natural Earth offline base";flat:true;onClicked:weather.act("open",JSON.stringify({url:"https://www.rainviewer.com/"}))}
}
