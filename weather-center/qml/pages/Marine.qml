import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
DataPanel {
 property var marine:weather.advancedUi.marine||{}
 title:"Marine"
 explanation:"MODELED DATA · Coastal-grid accuracy is limited. Not for navigation or a nautical almanac. Inland points may have no marine values. Wave, ocean-current and sea-level fields have different model coverage and horizons."
 dataModel:weather.advancedModel("marine");dataSeries:marine.series||[];dataMetrics:marine.metrics||[]
 freshness:weather.datasetAges.marine||({stale:true,age:"Not loaded",location:weather.summary.location})
 metricKeys:dataMetrics.map(m=>m.key);chartKeys:["wave_height","swell_wave_height","wind_wave_height","wave_period"]
 Label {text:marine.loading?"Loading marine model…":marine.supported?"Available model fields below · refreshed "+new Date(marine.saved*1000).toLocaleString():"Marine data unavailable at this point. Choose an offshore location in Locations or on the map.";color:"#ccc";wrapMode:Text.Wrap;Layout.fillWidth:true}
 Label {text:marine.error||"";color:"#e0c58a";wrapMode:Text.Wrap;Layout.fillWidth:true}
 WButton {text:"Refresh marine";onClicked:weather.act("advancedRefresh",JSON.stringify({kind:"marine"}))}
 Flow {Layout.fillWidth:true;Layout.preferredHeight:implicitHeight;spacing:6;Repeater {model:dataSeries;WButton {required property var modelData;text:modelData.label;highlighted:chartKeys.indexOf(modelData.key)>=0;onClicked:chartKeys=chartKeys.indexOf(modelData.key)>=0?chartKeys.filter(k=>k!==modelData.key):chartKeys.concat([modelData.key])}}}
}
