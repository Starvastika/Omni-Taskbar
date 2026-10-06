import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../charts"
import "../map"
WPage {
 WCard {title:"CURRENT CONDITIONS · FORECAST MODEL";Layout.fillWidth:true;Layout.preferredHeight:238
  RowLayout {anchors.fill:parent;spacing:30
   ColumnLayout {Layout.fillWidth:true;spacing:8
    Label {text:weather.summary.location;font.pixelSize:31;font.bold:true}
    Label {text:weather.summary.region+" · "+weather.summary.localTime;color:"#aaa"}
    Label {text:weather.summary.condition+" · "+(weather.summary.day?"Day":"Night");font.pixelSize:18}
    Label {text:"Feels like "+weather.summary.apparent+"   High "+weather.summary.high+"   Low "+weather.summary.low;color:"#ccc"}
    Label {text:(weather.summary.stale?"STALE · ":"")+weather.summary.age+" · "+weather.summary.provider+" · "+weather.summary.model;color:weather.summary.stale?"#e0c58a":"#aaa"}
   }
   Label {text:weather.summary.temperature;font.pixelSize:58;font.weight:Font.Light}
   Label {text:weather.summary.icon;font.pixelSize:74;color:"#ddd"}
  }
 }
 RowLayout {Layout.fillWidth:true;Label {text:"YOUR DASHBOARD";font.bold:true;color:"#aaa";Layout.fillWidth:true}WButton {text:"Customize";onClicked:weather.act("page",JSON.stringify({value:14}))}WButton {text:"Restore cards";onClicked:weather.act("dashboard",JSON.stringify({op:"restore"}))}}
 MetricGrid {Layout.fillWidth:true;items:weather.dashboardCards;dashboard:true}
 WCard {title:"NEXT HOURS / 15-MINUTE API SERIES";Layout.fillWidth:true;Layout.preferredHeight:165
  ColumnLayout {anchors.fill:parent
   Label {text:"Provider may interpolate outside native 15-minute model coverage. This is model guidance, not radar.";color:"#999";wrapMode:Text.Wrap;Layout.fillWidth:true}
   ListView {Layout.fillWidth:true;Layout.fillHeight:true;orientation:ListView.Horizontal;spacing:12;model:weather.minute.length?weather.minute.slice(0,6):weather.hourlyPreview.slice(0,6);clip:true;ScrollBar.horizontal:ScrollBar {}
    delegate:Column {required property var modelData;width:145;spacing:7;Label {text:modelData.label;font.bold:true}Label {text:modelData.formatted.temperature_2m||"Unavailable";font.pixelSize:19}Label {text:"Precip. "+(modelData.formatted.precipitation||"Unavailable");color:"#aaa"}}
   }
  }
 }
 WCard {title:"HOURLY AT A GLANCE";Layout.fillWidth:true;Layout.preferredHeight:450;Meteogram {anchors.fill:parent;keys:[weather.uiState.dashboard.primary,"precipitation"];horizon:24}}
 WCard {title:"DAILY OUTLOOK";Layout.fillWidth:true;Layout.preferredHeight:183
  ListView {anchors.fill:parent;orientation:ListView.Horizontal;spacing:14;model:weather.daily;clip:true;ScrollBar.horizontal:ScrollBar {}
   delegate:Column {required property var modelData;width:160;spacing:7;Label {text:modelData.date;font.bold:true}Label {text:modelData.icon+"  "+modelData.max;font.pixelSize:20}Label {text:modelData.min+" · "+modelData.condition;color:"#aaa";width:155;wrapMode:Text.Wrap}Label {text:modelData.rain+" · "+modelData.probability;color:"#bbb"}}
  }
 }
 RowLayout {Layout.fillWidth:true;spacing:14
  WCard {title:"SUN / SKY";Layout.fillWidth:true;Layout.preferredHeight:160;Label {anchors.fill:parent;text:"↑ "+weather.summary.sunrise+"     ↓ "+weather.summary.sunset+"\nDaylight "+weather.summary.daylight+"\nSolar details and twilight on Sun / Sky";color:"#ccc";lineHeight:1.8}}
  WCard {title:"AIR / FORECAST CONFIDENCE";Layout.fillWidth:true;Layout.preferredHeight:160;Label {anchors.fill:parent;text:(weather.uiState.prefs.aqi==="us_aqi"?"US AQI":"European AQI")+": "+weather.summary.aqi+"\nCAMS air-quality model · not a station measurement\nExplore model disagreement / ensemble spread in Models";color:"#ccc";lineHeight:1.8;wrapMode:Text.Wrap}}
 }
 WCard {title:"NOTABLE CHANGES · DERIVED MODEL GUIDANCE";Layout.fillWidth:true;Layout.preferredHeight:150;Label {anchors.fill:parent;text:weather.notable.length?weather.notable.join("\n"):"No threshold crossing identified in available forecast data.";color:"#ccc";lineHeight:1.7;wrapMode:Text.Wrap}}
 WCard {title:"OFFICIAL ALERTS";Layout.fillWidth:true;Layout.preferredHeight:120
  Column {anchors.fill:parent;spacing:8;Label {text:(weather.alerts||{}).status||"Loading official feed…";font.pixelSize:18}Label {text:((weather.alerts||{}).stale?"STALE / UNCONFIRMED · ":"")+((weather.alerts||{}).source||"");color:"#aaa"}}
 }
 WCard {title:"RADAR PREVIEW · WEATHER DATA BY RAINVIEWER";Layout.fillWidth:true;Layout.preferredHeight:350
  ColumnLayout {anchors.fill:parent;WeatherPreview {Layout.fillWidth:true;Layout.fillHeight:true}Label {text:weather.previewData.status||"Coverage is regional; black mask means no radar";color:"#aaa";wrapMode:Text.Wrap;Layout.fillWidth:true}
   RowLayout {visible:weather.uiState.dashboard.miniLayer==="radar";Label {text:"Reflectivity · dBZ";color:"#aaa"}Repeater {model:weather.previewData.legend||[];RowLayout {required property var modelData;Rectangle {width:28;height:8;color:modelData.color}Label {text:String(modelData.value);color:"#bbb"}}}}
   RowLayout {WButton {text:"Weather data by RainViewer";onClicked:weather.act("open",JSON.stringify({url:"https://www.rainviewer.com/"}))}WButton {text:"Full map / timeline →";onClicked:weather.act("page",JSON.stringify({value:3}))}}}
 }
 RowLayout {Layout.fillWidth:true;WButton {text:"Radar / map →";onClicked:weather.act("page",JSON.stringify({value:3}))}WButton {text:"Official alerts →";onClicked:weather.act("page",JSON.stringify({value:12}))}WButton {text:"Source details →";onClicked:weather.act("page",JSON.stringify({value:14}))}}
}
