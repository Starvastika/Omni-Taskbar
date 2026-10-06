import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../charts"
WPage {
 id:root;objectName:"weatherModelsPage";property var models:weather.advancedUi.models||{};property var ensemble:weather.advancedUi.ensemble||{};property var runs:weather.advancedUi.runs||{};property string variable:"temperature_2m";property bool members:false;property bool showRuns:false;property bool changes:false
 property var runSeries:(root.changes?(root.runs.changeSeries||[]):(root.runs.series||[])).filter(s=>s.variable===root.variable)
 property var modelSeries:weather.modelChoices.slice(1).map(m=>({key:root.variable+"_"+m.id,label:m.name,unit:(weather.series.find(s=>s.key===root.variable)||{}).unit||""}))
 Label {text:"Models / Confidence";font.pixelSize:24;font.bold:true}
 Label {text:"Deterministic disagreement and ensemble spread are uncertainty indicators, not accuracy percentages. Exact model initialization is not supplied by these endpoints; request/cache time is shown separately. The optional GFS archive compares fixed 24/48-hour lead times at aligned valid timestamps.";color:"#aaa";wrapMode:Text.Wrap;Layout.fillWidth:true}
 RowLayout {Label {text:"Preferred model"}WCombo {Layout.preferredWidth:240;model:weather.modelChoices.map(m=>m.name);currentIndex:weather.modelChoices.findIndex(m=>m.id===weather.uiState.prefs.model);onActivated:weather.act("pref",JSON.stringify({key:"model",value:weather.modelChoices[currentIndex].id}))}WButton {text:"Refresh comparison";onClicked:weather.act("advancedRefresh",JSON.stringify({kind:"models"}))}}
 Repeater {model:weather.modelChoices;Label {required property var modelData;text:modelData.name+" · "+modelData.region+" · "+modelData.resolution+" · "+modelData.horizon;color:"#aaa";wrapMode:Text.Wrap;Layout.fillWidth:true}}
 RowLayout {Label {text:"Deterministic overlays";font.pixelSize:21}WCombo {model:["Temperature","Precipitation","Wind","Pressure"];onActivated:root.variable=["temperature_2m","precipitation","wind_speed_10m","pressure_msl"][currentIndex]}}
 Label {text:root.models.loading?"Loading model comparison…":(root.models.error||root.models.heuristic||"");color:"#aaa";wrapMode:Text.Wrap;Layout.fillWidth:true}
 WCard {title:"MODEL COMPARISON · VALUES OMITTED WHEN MODEL HAS NO FIELD / HORIZON";Layout.fillWidth:true;Layout.preferredHeight:520;Meteogram {anchors.fill:parent;dataset:weather.advancedModel("models");series:root.modelSeries;keys:root.modelSeries.map(s=>s.key);horizon:168}}
 RowLayout {Label {text:"GFS ensemble · "+(root.ensemble.members||0)+" members";font.pixelSize:21}WSwitch {text:"Member spaghetti";checked:root.members;onToggled:root.members=checked}WButton {text:"Refresh ensemble";onClicked:weather.act("advancedRefresh",JSON.stringify({kind:"ensemble"}))}}
 Label {text:root.ensemble.loading?"Loading ensemble…":(root.ensemble.error||root.ensemble.heuristic||"");wrapMode:Text.Wrap;Layout.fillWidth:true;color:"#aaa"}
 WCard {title:"TEMPERATURE · MEAN / 10TH / 90TH PERCENTILES";Layout.fillWidth:true;Layout.preferredHeight:root.members?820:520;Meteogram {anchors.fill:parent;dataset:weather.advancedModel("ensemble");series:root.members?(root.ensemble.memberSeries||[]):(root.ensemble.series||[]);keys:series.map(s=>s.key);horizon:168}}
 Label {text:"Latest request: "+(root.models.saved?new Date(root.models.saved*1000).toISOString():"Not loaded")+" · "+(root.models.stale?"STALE":"cached/current")+"\nModel run: "+(root.models.run||"Unavailable");color:"#aaa";wrapMode:Text.Wrap;Layout.fillWidth:true}
 RowLayout {Label {text:"Previous forecasts · GFS archive";font.pixelSize:21}WButton {text:root.showRuns?"Refresh archive":"Load 24 / 48 h archive";onClicked:{weather.act("advancedRefresh",JSON.stringify({kind:"runs",force:root.showRuns}));root.showRuns=true}}WSwitch {text:"Show change";visible:root.showRuns;checked:root.changes;onToggled:root.changes=checked}}
 Label {visible:root.showRuns;text:root.runs.loading?"Loading archived forecast offsets…":(root.runs.error||root.runs.limitation||"Unavailable");color:"#aaa";wrapMode:Text.Wrap;Layout.fillWidth:true}
 WCard {visible:root.showRuns;title:root.changes?"CURRENT MINUS ARCHIVED FORECAST · NOT OBSERVED ERROR":"CURRENT / 24 H / 48 H LEAD-TIME ARCHIVE";Layout.fillWidth:true;Layout.preferredHeight:520;Meteogram {anchors.fill:parent;dataset:weather.advancedModel("runs");series:root.runSeries;keys:root.runSeries.map(s=>s.key);horizon:72}}
 Label {visible:root.showRuns;text:((weather.datasetAges.runs||{}).stale?"STALE · ":"")+((weather.datasetAges.runs||{}).age||"Not loaded")+" · "+(root.runs.source||"Open-Meteo Previous Runs")+"\n"+((root.runs.metadata||{}).endpoint||"");color:"#aaa";wrapMode:Text.Wrap;Layout.fillWidth:true}
}
