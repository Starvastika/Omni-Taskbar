import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
DataPanel {
 title:"Wind / Pressure"
 explanation:"Forecast-model wind, gusts and pressure. Wind direction indicates the direction the wind comes from. Multi-height fields depend on the selected model; unavailable variables are omitted."
 metricKeys:["wind_speed_10m","wind_direction_10m","wind_gusts_10m","wind_speed_80m","wind_speed_120m","pressure_msl","surface_pressure"]
 chartKeys:["wind_speed_10m","wind_gusts_10m","wind_direction_10m","pressure_msl"]
 RowLayout {Layout.fillWidth:true
  Rectangle {width:140;height:140;radius:70;color:"#252525";border.color:"#777"
   Label {anchors.horizontalCenter:parent.horizontalCenter;y:5;text:"N"}Label {anchors.centerIn:parent;text:"↑";font.pixelSize:65;rotation:(weather.metrics.find(m=>m.key==="wind_direction_10m")||{}).number||0}
   Label {anchors.bottom:parent.bottom;anchors.horizontalCenter:parent.horizontalCenter;anchors.bottomMargin:8;text:"FROM · ° TRUE";font.pixelSize:10;color:"#aaa"}
  }
  Label {Layout.fillWidth:true;text:weather.notable.filter(x=>x.indexOf("Pressure")>=0).join("\n")+"\nStrongest modeled gust in next 48 h: "+Math.max.apply(null,weather.hourly.slice(0,48).map(r=>r.values.wind_gusts_10m||0)).toFixed(1)+" "+weather.uiState.prefs.wind;color:"#ccc";wrapMode:Text.Wrap}
  WCombo {model:["km/h","m/s","mph","knots"];currentIndex:model.indexOf(weather.uiState.prefs.wind);onActivated:weather.act("pref",JSON.stringify({key:"wind",value:currentText}))}
  WButton {text:"Wind map →";onClicked:{weather.act("page",JSON.stringify({value:3}));weather.act("mapAction",JSON.stringify({op:"layer",value:"wind_speed_10m"}))}}
 }
}
