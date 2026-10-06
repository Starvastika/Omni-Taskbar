import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../charts"
WPage {
 id:root;property var history:weather.advancedUi.history||{};property string heatKey:"temperature_2m_mean"
 property var heatValues:(root.history.daily||[]).map(r=>r.values[root.heatKey]||0)
 property real heatMin:heatValues.length?Math.min.apply(null,heatValues):0
 property real heatMax:heatValues.length?Math.max.apply(null,heatValues):0
 Label {text:"History / Climate";font.pixelSize:24;font.bold:true}
 Label {text:"ERA5 reanalysis · 0.25° (~25 km) · Period summaries are modeled gridded history, not official station records. No baseline anomaly or long-term climate normal is implied. Choose up to two years, ending at least 5 days ago.";wrapMode:Text.Wrap;Layout.fillWidth:true;color:"#aaa"}
 Label {visible:!!root.history.start;text:"Displayed period: "+root.history.start+" → "+root.history.end+" · "+((weather.datasetAges.history||{}).stale?"STALE · ":"")+((weather.datasetAges.history||{}).age||"Not loaded");wrapMode:Text.Wrap;Layout.fillWidth:true;color:"#bbb"}
 RowLayout {WInput {id:start;text:Qt.formatDate(new Date(Date.now()-35*86400000),"yyyy-MM-dd");placeholderText:"Start YYYY-MM-DD"}Label {text:"→"}WInput {id:end;text:Qt.formatDate(new Date(Date.now()-6*86400000),"yyyy-MM-dd");placeholderText:"End YYYY-MM-DD"}WButton {text:"Load range";enabled:!root.history.loading;onClicked:weather.act("history",JSON.stringify({start:start.text,end:end.text}))}Label {text:root.history.loading?"Loading cached / requested period…":(root.history.error||"");color:"#aaa";wrapMode:Text.Wrap;Layout.fillWidth:true}}
 Label {text:root.history.stats?"Period days: "+root.history.stats.days+" · daily-mean temperature min / mean / max: "+root.history.stats.min+" / "+root.history.stats.mean+" / "+root.history.stats.max+" · total precipitation: "+root.history.stats.rain:"Select dates and load a range.";color:"#ccc";wrapMode:Text.Wrap;Layout.fillWidth:true}
 WCard {title:"HISTORICAL HOURLY PROFILE";Layout.fillWidth:true;Layout.preferredHeight:560
  Meteogram {anchors.fill:parent;dataset:weather.advancedModel("history");series:weather.series;keys:["temperature_2m","precipitation","wind_speed_10m","pressure_msl"];horizon:168}
 }
 Label {text:"Monthly aggregation / year-over-year";font.pixelSize:21}
 Label {text:"Compare corresponding months below when both years are in the requested range. Partial months retain their actual day count. Temperature and precipitation use your selected units.";color:"#aaa";wrapMode:Text.Wrap;Layout.fillWidth:true}
 Repeater {model:root.history.monthly||[];Rectangle {required property var modelData;Layout.fillWidth:true;Layout.preferredHeight:40;radius:5;color:"#252525";Label {anchors.fill:parent;anchors.margins:10;text:modelData.month+" · "+modelData.days+" days   |   Mean "+modelData.mean+"   |   Precip. "+modelData.rain}}}
 Label {text:root.history.percentiles?"Daily-mean temperature percentiles within requested period: 10th "+root.history.percentiles.p10+" · median "+root.history.percentiles.p50+" · 90th "+root.history.percentiles.p90:"";color:"#aaa";wrapMode:Text.Wrap;Layout.fillWidth:true}
 Repeater {model:root.history.yearComparison||[];Label {required property var modelData;text:modelData.first+" → "+modelData.second+": mean temperature Δ "+modelData.temperatureDelta+" · precipitation Δ "+modelData.rainDelta+" · compared day counts "+modelData.dayCounts.join(" / ");color:"#ccc";wrapMode:Text.Wrap;Layout.fillWidth:true}}
 RowLayout {Label {text:"Daily heatmap";font.pixelSize:20}WCombo {model:["Temperature mean","Daily precipitation"];onActivated:root.heatKey=currentIndex===0?"temperature_2m_mean":"precipitation_sum"}}
 Label {text:"Darker = lower / lighter = higher within this requested period. Hover for exact value. This is a relative period scale, not a climate anomaly.";wrapMode:Text.Wrap;Layout.fillWidth:true;color:"#aaa"}
 Flow {Layout.fillWidth:true;Layout.preferredHeight:implicitHeight;spacing:3
  Repeater {model:root.history.daily||[];Rectangle {required property var modelData;property real v:modelData.values[root.heatKey]||0;property real light:.22+.6*(v-root.heatMin)/Math.max(.001,root.heatMax-root.heatMin);width:23;height:23;radius:3;color:Qt.rgba(light,light,light,1);border.color:"#666";ToolTip.visible:heatMouse.containsMouse;ToolTip.text:modelData.date+" · "+(modelData.formatted[root.heatKey]||"Unavailable");MouseArea {id:heatMouse;anchors.fill:parent;hoverEnabled:true}}
  }
 }
 WButton {text:"Copy daily CSV";onClicked:{let rows=root.history.daily||[];weather.act("copy",JSON.stringify({text:"UTC,date,temperature_mean,temperature_min,temperature_max,precipitation,wind_max\n"+rows.map(r=>[r.iso,r.date,r.values.temperature_2m_mean,r.values.temperature_2m_min,r.values.temperature_2m_max,r.values.precipitation_sum,r.values.wind_speed_10m_max].join(",")).join("\n")}))}}
}
