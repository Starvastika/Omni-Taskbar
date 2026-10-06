import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../charts"
WPage {
 RowLayout {Layout.fillWidth:true
  Label {text:"HOURLY METEOGRAM";font.pixelSize:22;font.bold:true;Layout.fillWidth:true}
  WCombo {model:["Simple","Standard","Meteorology"];currentIndex:model.indexOf(weather.uiState.chart.preset);onActivated:weather.act("chartPreset",JSON.stringify({value:currentText}))}
  WCombo {model:["24 h","48 h","72 h","7 d"];currentIndex:[24,48,72,168].indexOf(weather.uiState.prefs.horizon);onActivated:weather.act("pref",JSON.stringify({key:"horizon",value:[24,48,72,168][currentIndex]}))}
 }
 WCard {title:"TIME-ALIGNED FORECAST · SEPARATE SCALES BY UNIT";Layout.fillWidth:true;Layout.preferredHeight:590;Meteogram {anchors.fill:parent}}
 Label {text:"SERIES · Provider availability varies by model / location";font.bold:true;color:"#aaa"}
 Flow {Layout.fillWidth:true;Layout.preferredHeight:implicitHeight;spacing:7
  Repeater {model:weather.series;WButton {required property var modelData;text:modelData.label;highlighted:weather.uiState.chart.series.indexOf(modelData.key)>=0;onClicked:weather.act("chart",JSON.stringify({key:modelData.key,remove:highlighted}))}}
 }
 WCard {title:"HOURLY VALUES · LOCAL IANA TIME / UTC EPOCH AXIS";Layout.fillWidth:true;Layout.preferredHeight:400
  ListView {anchors.fill:parent;model:weather.hourlyModel;reuseItems:true;clip:true;ScrollBar.vertical:ScrollBar {}
   delegate:Rectangle {required property var rowData;property var modelData:rowData;required property int index;width:ListView.view.width;height:44;color:index%2?"#292929":"#222"
    RowLayout {anchors.fill:parent;anchors.margins:9;Label {text:modelData.date+" "+modelData.label;Layout.preferredWidth:190}Label {text:modelData.formatted.temperature_2m||"—";Layout.preferredWidth:100}Label {text:"Rain "+(modelData.formatted.precipitation||"—");Layout.preferredWidth:140}Label {text:"Wind "+(modelData.formatted.wind_speed_10m||"—");Layout.preferredWidth:140}Label {text:modelData.iso;color:"#aaa";Layout.fillWidth:true}}
   }
  }
 }
}
