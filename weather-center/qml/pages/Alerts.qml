import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
WPage {
 id:root;property var alerts:weather.alerts||{};property string period:"Active";property string severity:"All";property string source:"All"
 Label {text:"Official Alerts";font.pixelSize:24;font.bold:true}
 Label {text:root.alerts.status||"Loading official source…";font.pixelSize:20;wrapMode:Text.Wrap;Layout.fillWidth:true}
 Label {text:weather.summary.location+" · "+(root.alerts.coverage||"")+"\n"+(root.alerts.stale?"STALE / UNCONFIRMED · ":"")+"Latest successful feed: "+(root.alerts.saved?new Date(root.alerts.saved*1000).toISOString():"Never");color:"#aaa";wrapMode:Text.Wrap;Layout.fillWidth:true}
 RowLayout {WCombo {model:["Active","Recently expired","All"];onActivated:root.period=currentText}WCombo {model:["All","Extreme","Severe","Moderate","Minor","Not supplied"];onActivated:root.severity=currentText}WCombo {model:["All","ECCC","NWS"];onActivated:root.source=currentText}WButton {text:"Refresh official feed";onClicked:weather.act("advancedRefresh",JSON.stringify({kind:"alerts"}))}WButton {text:"Alert geometry →";onClicked:{weather.act("page",JSON.stringify({value:3}));weather.act("mapAction",JSON.stringify({op:"layer",value:"alerts"}))}}}
 Repeater {model:(root.alerts.items||[]).filter(a=>(root.period==="All"||a.active===(root.period==="Active"))&&(root.severity==="All"||a.severity===root.severity)&&(root.source==="All"||a.provider===root.source))
  Rectangle {required property var modelData;Layout.fillWidth:true;Layout.preferredHeight:body.implicitHeight+32;color:"#262626";radius:10;border.color:modelData.active?"#bbb":"#555"
   ColumnLayout {id:body;anchors.left:parent.left;anchors.right:parent.right;anchors.top:parent.top;anchors.margins:16;spacing:12
    Label {text:(modelData.active?"ACTIVE · ":"EXPIRED / ENDED · ")+modelData.title;font.pixelSize:21;font.bold:true;wrapMode:Text.Wrap;Layout.fillWidth:true}
    Label {text:modelData.source+"\nAffected area: "+modelData.area+"\nSeverity: "+modelData.severity+" · Urgency: "+modelData.urgency+" · Certainty: "+modelData.certainty+"\nIssued: "+modelData.issued+"\nEffective: "+modelData.effective+"\nExpires: "+modelData.expires;wrapMode:Text.Wrap;Layout.fillWidth:true;color:"#bbb"}
    TextArea {text:modelData.description;readOnly:true;textFormat:TextEdit.PlainText;wrapMode:TextEdit.Wrap;Layout.fillWidth:true;Layout.preferredHeight:Math.min(420,implicitHeight);background:Rectangle {color:"#202020";radius:6}selectByMouse:true;color:"#eee"}
    Label {text:"Official instructions: "+modelData.instructions;wrapMode:Text.Wrap;Layout.fillWidth:true;color:"#ccc"}
    RowLayout {WButton {text:"Official source";enabled:modelData.url.length>0;onClicked:weather.act("open",JSON.stringify({url:modelData.url}))}WButton {text:"Copy original wording";onClicked:weather.act("copy",JSON.stringify({text:modelData.title+"\n"+modelData.description+"\n"+modelData.instructions}))}}
   }
  }
 }
 Label {text:"Only official ECCC and NWS feeds are integrated. Other countries show unavailable. Recently expired items come from the provider or alerts previously seen here during the last day. Forecast CAPE / precipitation / wind thresholds are never used to manufacture alerts.";wrapMode:Text.Wrap;Layout.fillWidth:true;color:"#aaa"}
}
