import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "components"
ApplicationWindow {
 id:window;objectName:"weatherCenterWindow";visible:false;title:"Weather Center";width:1500;height:900
 flags:Qt.Tool|Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint
 color:weather.uiState.prefs.highContrast?"#101010":"#181818";font.family:"Segoe UI Variable";font.pixelSize:weather.uiState.prefs.density==="compact"?11:weather.uiState.prefs.density==="spacious"?14:12
 palette.window:color;palette.windowText:"#eee";palette.base:"#1c1c1c";palette.text:"#eee";palette.button:"#2d2d2d";palette.buttonText:"#eee";palette.highlight:"#ddd";palette.highlightedText:"#151515";palette.placeholderText:"#999"
 property var pages:["Overview","Hourly","Daily","Map","Precipitation / Storms","Wind / Pressure","Air / Atmosphere","Sun / Sky","Marine","History / Climate","Models / Confidence","Locations","Alerts","Weather Lab","Settings"]
 property bool editing:activeFocusItem&&activeFocusItem.cursorPosition!==undefined
 property bool choosingLocation:false
 function searchOpen(){choosingLocation=false;palette.open();weather.search("")}
 function openLocationPicker(){choosingLocation=true;weather.act("page",JSON.stringify({value:11}));palette.open();commandSearch.input.text="";weather.search("");commandSearch.input.forceActiveFocus()}
 onClosing:event=>{event.accepted=false;weather.act("hide","{}")}
 Shortcut {sequence:"Escape";enabled:weather.modalCount===0;onActivated:weather.act("hide","{}")}
 Shortcut {sequence:"Ctrl+K";onActivated:window.searchOpen()}
 Shortcut {sequence:"Ctrl+F";onActivated:window.searchOpen()}
 Shortcut {sequence:"Ctrl+R";onActivated:weather.act("refresh","{}")}
 Shortcut {sequence:"M";enabled:!window.editing&&weather.modalCount===0;onActivated:weather.act("page",JSON.stringify({value:3}))}
 Shortcut {sequence:"H";enabled:!window.editing&&weather.modalCount===0;onActivated:weather.act("page",JSON.stringify({value:0}))}
 Shortcut {sequence:"A";enabled:!window.editing&&weather.modalCount===0;onActivated:weather.act("page",JSON.stringify({value:12}))}
 Popup {id:palette;objectName:"weatherCommandPalette";parent:Overlay.overlay;x:(parent.width-width)/2;y:Math.max(25,(parent.height-height)/3);width:Math.min(760,parent.width-50);height:Math.min(550,parent.height-60);padding:16;modal:true;focus:true;closePolicy:Popup.CloseOnEscape|Popup.CloseOnPressOutside
  onOpened:{weather.modal(1);commandSearch.input.forceActiveFocus()}onClosed:weather.modal(-1)
  background:Rectangle {color:"#242424";radius:12;border.color:"#888"}
  contentItem:LocationSearch {id:commandSearch;locationsOnly:window.choosingLocation;onSelected:result=>{weather.act("searchSelect",JSON.stringify(result));palette.close()}}
 }
 ColumnLayout {anchors.fill:parent;anchors.margins:weather.uiState.prefs.density==="compact"?12:weather.uiState.prefs.density==="spacious"?22:18;spacing:weather.uiState.prefs.density==="compact"?10:14
  RowLayout {Layout.fillWidth:true
   ColumnLayout {spacing:2;Label {text:"WEATHER CENTER";font.pixelSize:23;font.bold:true;font.letterSpacing:2}Label {text:weather.summary.location;color:"#aaa"}}
   Item {Layout.fillWidth:true}
   WButton {text:"Search / Ctrl+K";onClicked:window.searchOpen()}
   WButton {text:"Refresh";onClicked:weather.act("refresh","{}")}
   WButton {id:closeButton;objectName:"weatherCloseButton";text:"Close ×";enabled:true;onClicked:weather.act("hide","{}")}
  }
  RowLayout {Layout.fillWidth:true;Layout.fillHeight:true;spacing:16
   Rectangle {Layout.preferredWidth:202;Layout.fillHeight:true;color:"#202020";radius:10;border.color:"#393939"
    ListView {anchors.fill:parent;anchors.margins:8;spacing:5;model:window.pages;clip:true;ScrollBar.vertical:ScrollBar {}
     delegate:WButton {required property string modelData;required property int index;width:ListView.view.width;text:modelData;highlighted:weather.uiState.page===index;onClicked:weather.act("page",JSON.stringify({value:index}))}
    }
   }
   Item {Layout.fillWidth:true;Layout.fillHeight:true
    Repeater {model:["Overview.qml","Hourly.qml","Daily.qml","MapPage.qml","Precipitation.qml","Wind.qml","Air.qml","Sun.qml","Marine.qml","History.qml","Models.qml","Locations.qml","Alerts.qml","Lab.qml","Settings.qml"]
     Loader {required property string modelData;required property int index;objectName:"weatherPageLoader_"+index;property bool visited:false;anchors.fill:parent;visible:weather.uiState.page===index;active:visited||visible;source:"pages/"+modelData;onVisibleChanged:if(visible)visited=true;asynchronous:true}
    }
   }
  }
  Label {text:weather.status;color:"#999";Layout.fillWidth:true;elide:Text.ElideRight}
 }
}
