import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
Rectangle {
 id:card;property var metric:({key:"",label:"",value:"",source:""});property bool dashboard:false
 color:weather.uiState.prefs.highContrast?"#1a1a1a":"#262626";radius:8;border.color:weather.uiState.prefs.highContrast?"#eee":focusArea.containsMouse?"#777":"#444";implicitHeight:(metric.expanded?155:108)+(weather.uiState.prefs.density==="compact"?-10:weather.uiState.prefs.density==="spacious"?15:0)
 ColumnLayout {anchors.fill:parent;anchors.margins:14;spacing:7
  Label {text:card.metric.label;color:"#aaa";font.pixelSize:12;elide:Text.ElideRight;Layout.fillWidth:true}
  Label {text:card.metric.value;font.pixelSize:22;font.bold:true;Layout.fillWidth:true;elide:Text.ElideRight}
  Label {visible:card.metric.expanded===true;text:card.metric.source+"\n"+card.metric.key;color:"#aaa";font.pixelSize:10;wrapMode:Text.Wrap;Layout.fillWidth:true}
 }
 MouseArea {id:focusArea;anchors.fill:parent;hoverEnabled:true;acceptedButtons:Qt.RightButton;onClicked:menu.popup()}
 ToolTip.visible:focusArea.containsMouse;ToolTip.text:metric.source+"\nRaw field: "+metric.key+"\nRight-click for chart, map, copy and dashboard actions"
 WMenu {id:menu
  MenuItem {text:"Add to hourly chart";onTriggered:{weather.act("chart",JSON.stringify({key:card.metric.key}));weather.act("page",JSON.stringify({value:1}))}}
  MenuItem {text:enabled?"Show sampled map":"No sampled map for this field";enabled:weather.metricLayer(card.metric.key)!=="";onTriggered:weather.act("metricMap",JSON.stringify({key:card.metric.key}))}
  MenuItem {text:"Copy value / source";onTriggered:weather.act("copy",JSON.stringify({text:card.metric.label+": "+card.metric.value+" · "+card.metric.source+" · "+card.metric.key}))}
  MenuItem {text:"Pin to dashboard";onTriggered:weather.act("dashboard",JSON.stringify({op:"pin",key:card.metric.key}))}
  MenuItem {text:"Compact / expanded";enabled:card.dashboard;onTriggered:weather.act("dashboard",JSON.stringify({op:"expanded",key:card.metric.key}))}
  MenuItem {text:"Move earlier";enabled:card.dashboard;onTriggered:weather.act("dashboard",JSON.stringify({op:"move",key:card.metric.key,delta:-1}))}
  MenuItem {text:"Move later";enabled:card.dashboard;onTriggered:weather.act("dashboard",JSON.stringify({op:"move",key:card.metric.key,delta:1}))}
  MenuItem {text:"Hide dashboard card";enabled:card.dashboard;onTriggered:weather.act("dashboard",JSON.stringify({op:"hidden",key:card.metric.key}))}
  MenuItem {text:"Units / metric sources";onTriggered:weather.act("page",JSON.stringify({value:14}))}
 }
}
