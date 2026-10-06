import QtQuick
import QtQuick.Controls
Menu {
 id:m;padding:6;margins:8;implicitWidth:290;implicitHeight:Math.min(contentItem.implicitHeight+12,Overlay.overlay?Overlay.overlay.height-24:600)
 onOpened:weather.modal(1);onClosed:weather.modal(-1)
 background:Rectangle {radius:8;color:"#252525";border.color:"#666"}
 contentItem:ListView {implicitHeight:contentHeight;model:m.contentModel;clip:true;currentIndex:m.currentIndex;onCurrentIndexChanged:if(currentIndex>=0)positionViewAtIndex(currentIndex,ListView.Contain);ScrollBar.vertical:ScrollBar {}}
 delegate:MenuItem {id:d;implicitHeight:34;contentItem:Text {text:d.text;color:d.enabled?"#eee":"#777";font:d.font;verticalAlignment:Text.AlignVCenter}background:Rectangle {radius:4;color:d.highlighted?"#454545":"transparent"}}
}
