import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
WPage {
 id:root;property var comparing:[];property int compareHour:0;property bool compact:false;property var contextLocation:weather.uiState.selected
 Label {text:"Locations";font.pixelSize:24;font.bold:true}
 Label {text:"Home, saved and recent locations belong to Weather Center. Compact YASB weather keeps its own location picker. Inspecting/searching does not change Home until you choose Set Home.";color:"#aaa";wrapMode:Text.Wrap;Layout.fillWidth:true}
 WSplit {id:split;Layout.fillWidth:true;Layout.preferredHeight:540;onResizingChanged:if(!resizing&&width>0)weather.act("layout",JSON.stringify({key:"locationSplit",value:savedPanel.width/width}))
  ColumnLayout {id:savedPanel;SplitView.preferredWidth:split.width*weather.uiState.layout.locationSplit;SplitView.minimumWidth:370
   RowLayout {Layout.fillWidth:true;Label {text:"Saved · "+weather.uiState.locations.length;font.pixelSize:20;Layout.fillWidth:true}WSwitch {text:"Compact";checked:root.compact;onToggled:root.compact=checked}}
   ListView {Layout.fillWidth:true;Layout.fillHeight:true;model:weather.uiState.locations;clip:true;spacing:7;ScrollBar.vertical:ScrollBar {}
    delegate:Rectangle {required property var modelData;required property int index;width:ListView.view.width;height:root.compact?62:112;color:modelData.id===weather.uiState.selected.id?"#393939":"#242424";radius:8;border.color:"#555"
     RowLayout {anchors.fill:parent;anchors.margins:12
      CheckBox {checked:root.comparing.indexOf(modelData.id)>=0;ToolTip.visible:hovered;ToolTip.text:"Compare 2–6 locations";onToggled:root.comparing=checked?root.comparing.concat([modelData.id]).slice(0,6):root.comparing.filter(x=>x!==modelData.id)}
      ColumnLayout {Layout.fillWidth:true;Label {text:(modelData.id===weather.uiState.homeId?"⌂ ":"")+(modelData.favorite?"★ ":"")+modelData.name;font.pixelSize:19;Layout.fillWidth:true;elide:Text.ElideRight}Label {text:modelData.region+" · "+modelData.country+"\n"+modelData.zone+" · "+modelData.lat.toFixed(3)+", "+modelData.lon.toFixed(3);color:"#aaa";visible:!root.compact;Layout.fillWidth:true;elide:Text.ElideRight}}
      WButton {text:"View";onClicked:weather.act("select",JSON.stringify({id:modelData.id}))}
      WButton {text:"⋯";onClicked:{root.contextLocation=modelData;locationMenu.popup()}}
     }
     TapHandler {acceptedButtons:Qt.RightButton;onTapped:{root.contextLocation=modelData;locationMenu.popup()}}
    }
   }
  }
  LocationSearch {locationsOnly:true;id:search;SplitView.fillWidth:true;SplitView.minimumWidth:300;onSelected:result=>{weather.act("searchSelect",JSON.stringify(result));if(result.kind==="location")weather.act("page",JSON.stringify({value:0}))}}
 }
 RowLayout {WButton {text:"Save selected";onClicked:weather.act("save","{}")}WButton {text:"Set selected as Home";onClicked:weather.act("home","{}")}WButton {text:"Import legacy YASB location";onClicked:weather.act("syncHome","{}")}WButton {text:"Compare "+root.comparing.length;enabled:root.comparing.length>=2;onClicked:weather.act("compare",JSON.stringify({ids:root.comparing}))}}
 Label {text:"Recent inspections";font.pixelSize:20}
 Flow {Layout.fillWidth:true;Layout.preferredHeight:implicitHeight;spacing:6;Repeater {model:weather.uiState.recent.slice(0,10);WButton {required property var modelData;text:modelData.name;onClicked:weather.act("select",JSON.stringify(modelData))}}}
 Label {text:"Comparison · synchronized UTC hourly timeline";visible:weather.comparisons.length>0;font.pixelSize:21}
 RowLayout {visible:weather.comparisons.length>0;Slider {Layout.fillWidth:true;from:0;to:71;stepSize:1;value:root.compareHour;onMoved:root.compareHour=Math.round(value)}Label {text:"+"+root.compareHour+" h";color:"#ccc"}}
 Repeater {model:weather.comparisons
  Rectangle {required property var modelData;property var row:modelData.rows[root.compareHour]||{};Layout.fillWidth:true;Layout.preferredHeight:120;color:"#252525";radius:8
   Column {anchors.fill:parent;anchors.margins:14;spacing:9;Label {text:modelData.location.name+" · "+modelData.location.region+" · "+modelData.location.country;font.pixelSize:20}Label {text:(row.date||"")+" "+(row.label||modelData.summary.localTime||"")+" · "+(row.iso||"")+"\nTemperature "+((row.formatted||{}).temperature_2m||"—")+" · Rain "+((row.formatted||{}).precipitation||"—")+" · Wind "+((row.formatted||{}).wind_speed_10m||"—")+" · AQI "+((row.formatted||{})[weather.uiState.prefs.aqi]||"Unavailable")+" · Daylight "+(modelData.summary.daylight||"—")+" · "+(modelData.summary.age||"");color:"#bbb";lineHeight:1.6}}
  }
 }
 WMenu {id:locationMenu
  MenuItem {text:"View weather";onTriggered:weather.act("select",JSON.stringify(root.contextLocation))}
  MenuItem {text:"Set Home";onTriggered:weather.act("home",JSON.stringify({location:root.contextLocation}))}
  MenuItem {text:"Favorite / unfavorite";onTriggered:weather.act("favorite",JSON.stringify({id:root.contextLocation.id,location:root.contextLocation}))}
  MenuItem {text:"Rename display label…";onTriggered:{renameInput.text=root.contextLocation.name;rename.open()}}
  MenuItem {text:"Move earlier";onTriggered:weather.act("reorder",JSON.stringify({id:root.contextLocation.id,delta:-1}))}
  MenuItem {text:"Move later";onTriggered:weather.act("reorder",JSON.stringify({id:root.contextLocation.id,delta:1}))}
  MenuItem {text:"Add to comparison";onTriggered:if(root.comparing.indexOf(root.contextLocation.id)<0)root.comparing=root.comparing.concat([root.contextLocation.id]).slice(0,6)}
  MenuItem {text:"Open on map";onTriggered:{weather.act("select",JSON.stringify(root.contextLocation));weather.act("page",JSON.stringify({value:3}))}}
  MenuItem {text:"Copy coordinates";onTriggered:weather.act("copy",JSON.stringify({text:root.contextLocation.lat+", "+root.contextLocation.lon}))}
  MenuItem {text:"Copy current selected conditions";onTriggered:weather.act("copy",JSON.stringify({text:JSON.stringify(weather.summary,null,2)}))}
  MenuItem {text:"Remove saved location";enabled:root.contextLocation.id!==weather.uiState.homeId;onTriggered:weather.act("remove",JSON.stringify({id:root.contextLocation.id}))}
 }
 Dialog {id:rename;title:"Rename location";modal:true;anchors.centerIn:Overlay.overlay;width:400;standardButtons:Dialog.Save|Dialog.Cancel;onOpened:weather.modal(1);onClosed:weather.modal(-1);onAccepted:weather.act("rename",JSON.stringify({id:root.contextLocation.id,name:renameInput.text}));contentItem:WInput {id:renameInput;selectByMouse:true}}
}
