import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
DataPanel {
 title:"Precipitation / Storms"
 explanation:"Modeled precipitation and atmospheric diagnostics. CAPE is available energy, not an official thunderstorm warning. Observed lightning and CIN are unavailable from the integrated sources. Radar coverage is regional."
 metricKeys:["precipitation","precipitation_probability","rain","showers","snowfall","snow_depth","freezing_level_height","cape","pressure_msl","cloud_cover_low","cloud_cover_mid","cloud_cover_high"]
 chartKeys:["precipitation","rain","showers","snowfall","precipitation_probability","cape"]
 Label {text:"Hourly accumulation (forecast, next 24 h): "+weather.hourly.slice(0,24).reduce((s,r)=>s+(r.values.precipitation||0),0).toFixed(1)+" "+(weather.uiState.prefs.precipitation==="mm"?"mm":"in");font.pixelSize:18}
 Label {text:weather.notable.join("\n");color:"#aaa";wrapMode:Text.Wrap;Layout.fillWidth:true}
 RowLayout {WButton {text:"Radar / actual frame timeline →";onClicked:{weather.act("page",JSON.stringify({value:3}));weather.act("mapAction",JSON.stringify({op:"layer",value:"radar"}))}}WButton {text:"Official alerts →";onClicked:weather.act("page",JSON.stringify({value:12}))}}
}
