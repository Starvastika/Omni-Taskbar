import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
WPage {
 Label {text:"Settings / Sources";font.pixelSize:24;font.bold:true}
 Label {text:"Weather Center-owned preferences. Data stays in metric provider units internally and converts for display. Cached data remains available with a stale marker during outages.";wrapMode:Text.Wrap;Layout.fillWidth:true;color:"#aaa"}
 Repeater {model:weather.settingsRows
  RowLayout {required property var modelData;Layout.fillWidth:true
   Label {text:modelData.label;Layout.preferredWidth:340;wrapMode:Text.Wrap}
   WCombo {visible:modelData.type==="choice";Layout.preferredWidth:260;model:modelData.options.map(String);currentIndex:modelData.options.indexOf(weather.uiState.prefs[modelData.key]);onActivated:weather.act("pref",JSON.stringify({key:modelData.key,value:modelData.options[currentIndex]}))}
   WSwitch {visible:modelData.type==="toggle";checked:!!weather.uiState.prefs[modelData.key];onToggled:weather.act("pref",JSON.stringify({key:modelData.key,value:checked}))}
   WInput {visible:modelData.type==="number";Layout.preferredWidth:150;text:String(weather.uiState.prefs[modelData.key]);validator:DoubleValidator {bottom:0;top:100}onAccepted:weather.act("pref",JSON.stringify({key:modelData.key,value:Number(text)}))}
   Item {Layout.fillWidth:true}
  }
 }
 Label {text:"Dashboard / primary chart";font.pixelSize:21}
 RowLayout {WCombo {Layout.preferredWidth:310;model:weather.series.map(s=>s.label);currentIndex:weather.series.findIndex(s=>s.key===weather.uiState.dashboard.primary);onActivated:weather.act("dashboard",JSON.stringify({op:"primary",value:weather.series[currentIndex].key}))}WButton {text:"Restore dashboard";onClicked:weather.act("dashboard",JSON.stringify({op:"restore"}))}}
 RowLayout {Label {text:"Mini-map"}WCombo {model:["Radar","Radar coverage","Grayscale geography"];currentIndex:["radar","coverage","none"].indexOf(weather.uiState.dashboard.miniLayer);onActivated:weather.act("dashboard",JSON.stringify({op:"miniLayer",value:["radar","coverage","none"][currentIndex]}))}}
 Flow {Layout.fillWidth:true;Layout.preferredHeight:implicitHeight;spacing:6;Repeater {model:weather.metrics;WButton {required property var modelData;text:modelData.label;highlighted:weather.uiState.dashboard.cards.indexOf(modelData.key)>=0&&weather.uiState.dashboard.hidden.indexOf(modelData.key)<0;onClicked:weather.act("dashboard",JSON.stringify({op:highlighted?"hidden":"pin",key:modelData.key}))}}}
 Label {text:"Networking / diagnostics";font.pixelSize:21}
 RowLayout {WButton {text:"Refresh now";onClicked:weather.act("refresh","{}")}WButton {text:"Clear weather cache";onClicked:weather.act("clearCache","{}")}WButton {text:"Open logs";onClicked:weather.act("open",JSON.stringify({url:"logs"}))}WButton {text:"Copy diagnostics";onClicked:weather.act("copy",JSON.stringify({text:weather.diagnostics()}))}WButton {text:"Reset Weather Center…";onClicked:reset.open()}}
 Repeater {model:weather.providerStatus;Label {required property var modelData;text:modelData.provider+" · "+modelData.status+" · Last success: "+(modelData.lastSuccess?new Date(modelData.lastSuccess*1000).toISOString():"Never")+(modelData.error?" · "+modelData.error:"");color:"#bbb";wrapMode:Text.Wrap;Layout.fillWidth:true}}
 Label {text:"Data Sources / Attribution";font.pixelSize:23}
 Repeater {model:weather.sources;Rectangle {required property var modelData;Layout.fillWidth:true;Layout.preferredHeight:sourceBody.implicitHeight+30;color:"#252525";radius:8
  ColumnLayout {id:sourceBody;anchors.left:parent.left;anchors.right:parent.right;anchors.top:parent.top;anchors.margins:15;Label {text:modelData.name;font.pixelSize:18;font.bold:true}Label {text:modelData.data+"\n"+modelData.attribution;wrapMode:Text.Wrap;Layout.fillWidth:true;color:"#aaa"}WButton {text:"Official documentation / source";onClicked:weather.act("open",JSON.stringify({url:modelData.url}))}}
 }}
 TextArea {text:JSON.stringify(weather.metadata,null,2);Layout.fillWidth:true;readOnly:true;selectByMouse:true;wrapMode:TextEdit.Wrap;color:"#bbb";background:Rectangle {color:"#222"}}
 Dialog {id:reset;title:"Reset Weather Center?";width:450;modal:true;anchors.centerIn:Overlay.overlay;standardButtons:Dialog.Yes|Dialog.Cancel;onOpened:weather.modal(1);onClosed:weather.modal(-1);onAccepted:weather.act("resetWeather",JSON.stringify({confirmed:true}));Label {width:400;text:"This resets Weather Center preferences and saved locations. One recovery copy is retained in state.before-reset.json. YASB, Time Center and stable-v1 are untouched.";wrapMode:Text.Wrap}}
}
