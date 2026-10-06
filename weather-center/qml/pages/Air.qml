import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
DataPanel {
 title:"Air / Atmosphere"
 explanation:"CAMS model via Open-Meteo (~11 km Europe / ~45 km global), not a local air-quality monitor. Pollen is only returned in supported European coverage. AQI standards use different scales. Missing fields remain unavailable."
 metricKeys:["us_aqi","european_aqi","pm2_5","pm10","ozone","nitrogen_dioxide","sulphur_dioxide","carbon_monoxide","dust","aerosol_optical_depth","alder_pollen","birch_pollen","grass_pollen","mugwort_pollen","olive_pollen","ragweed_pollen"]
 dataModel:weather.airRowsModel
 freshness:weather.airSummary
 dataSeries:weather.metrics.filter(m=>metricKeys.indexOf(m.key)>=0).map(m=>({key:m.key,label:m.label,unit:m.unit}))
 chartKeys:[weather.uiState.prefs.aqi,"pm2_5","pm10"]
 RowLayout {Label {text:"AQI standard"}WCombo {model:["US AQI","European AQI"];currentIndex:weather.uiState.prefs.aqi==="us_aqi"?0:1;onActivated:weather.act("pref",JSON.stringify({key:"aqi",value:currentIndex===0?"us_aqi":"european_aqi"}))}}
 Label {text:"Atmospheric context";font.pixelSize:21}
 MetricGrid {Layout.fillWidth:true;items:weather.metrics.filter(m=>["relative_humidity_2m","dew_point_2m","vapour_pressure_deficit","visibility","cloud_cover_low","cloud_cover_mid","cloud_cover_high","pressure_msl"].indexOf(m.key)>=0)}
 Flow {Layout.fillWidth:true;Layout.preferredHeight:implicitHeight;spacing:6;Repeater {model:dataSeries;WButton {required property var modelData;text:modelData.label;highlighted:chartKeys.indexOf(modelData.key)>=0;onClicked:chartKeys=chartKeys.indexOf(modelData.key)>=0?chartKeys.filter(k=>k!==modelData.key):chartKeys.concat([modelData.key])}}}
}
