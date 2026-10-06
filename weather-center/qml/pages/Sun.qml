import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../charts"
WPage {
 id:root
 Label {text:"Sun / Sky";font.pixelSize:24;font.bold:true}
 Label {text:"Astral 3.2 calculated events at the selected coordinates / IANA timezone. Golden hour uses −4° to +6° solar elevation. Moonrise/set are calculated, not observations. Missing polar events are reported explicitly; terrain and a raised observer horizon are not modeled.";color:"#aaa";wrapMode:Text.Wrap;Layout.fillWidth:true}
 RowLayout {WInput {id:date;objectName:"weatherSolarDate";text:weather.solarDate;placeholderText:"YYYY-MM-DD";onAccepted:weather.act("solarDate",JSON.stringify({value:text}))}WButton {text:"Calculate date";onClicked:weather.act("solarDate",JSON.stringify({value:date.text}))}Label {text:weather.uiState.selected.zone;color:"#aaa"}}
 GridLayout {columns:Math.max(1,Math.floor(width/300));Layout.fillWidth:true;rowSpacing:12;columnSpacing:12
  Repeater {model:weather.solar||[];Rectangle {required property var modelData;Layout.fillWidth:true;Layout.preferredHeight:140;color:"#252525";radius:8;border.color:weather.uiState.prefs.highContrast?"#eee":"#444";Column {anchors.fill:parent;anchors.margins:14;spacing:8;Label {text:modelData.label;color:"#aaa";width:parent.width;wrapMode:Text.Wrap}Label {text:modelData.value;font.pixelSize:16;width:parent.width;wrapMode:Text.Wrap}}}}
 }
 Label {text:"Today: sunrise "+weather.summary.sunrise+" · sunset "+weather.summary.sunset+" · daylight "+weather.summary.daylight;color:"#ccc"}
 MetricGrid {Layout.fillWidth:true;items:weather.metrics.filter(m=>["uv_index","shortwave_radiation","direct_normal_irradiance","diffuse_radiation","cloud_cover","cloud_cover_low","cloud_cover_mid","cloud_cover_high"].indexOf(m.key)>=0)}
 WCard {title:"SOLAR PROFILE · DARK SHADING INDICATES NIGHT";Layout.fillWidth:true;Layout.preferredHeight:510;Meteogram {anchors.fill:parent;keys:["uv_index","shortwave_radiation","cloud_cover"];horizon:24}}
}
