import QtQuick
import QtQuick.Controls
ComboBox {
 id:c;implicitWidth:180;implicitHeight:weather.uiState.prefs.density==="compact"?30:weather.uiState.prefs.density==="spacious"?40:34;leftPadding:10;rightPadding:28
 contentItem:Text {text:c.displayText;color:"#eee";font:c.font;verticalAlignment:Text.AlignVCenter;elide:Text.ElideRight}
 indicator:Text {x:c.width-21;y:8;text:"⌄";color:"#ddd"}
 background:Rectangle {radius:6;color:"#292929";border.color:c.activeFocus||weather.uiState.prefs.highContrast?"#eee":"#555"}
 delegate:ItemDelegate {width:c.width;text:c.textRole?model[c.textRole]:modelData;highlighted:c.highlightedIndex===index;contentItem:Text {text:parent.text;color:parent.enabled?"#eee":"#888";verticalAlignment:Text.AlignVCenter;elide:Text.ElideRight}background:Rectangle {color:parent.highlighted?"#444":"#252525"}}
 popup:Popup {y:c.height+4;width:Math.max(c.width,220);padding:6;implicitHeight:Math.min(contentItem.implicitHeight+12,Math.max(80,Overlay.overlay.height-40));closePolicy:Popup.CloseOnEscape|Popup.CloseOnPressOutside
  onOpened:weather.modal(1);onClosed:weather.modal(-1)
  background:Rectangle {radius:8;color:"#252525";border.color:"#666"}
  contentItem:ListView {clip:true;implicitHeight:contentHeight;model:c.popup.visible?c.delegateModel:null;currentIndex:c.highlightedIndex;onCurrentIndexChanged:if(currentIndex>=0)positionViewAtIndex(currentIndex,ListView.Contain);ScrollBar.vertical:ScrollBar {}}
 }
}
