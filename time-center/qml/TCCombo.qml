import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
ComboBox {
    id:control;implicitHeight:34;implicitWidth:160;leftPadding:10;rightPadding:30
    delegate:ItemDelegate {width:control.width;text:control.textRole?model[control.textRole]:modelData;highlighted:control.highlightedIndex===index;contentItem:Text {text:parent.text;color:"#efefef";elide:Text.ElideRight;verticalAlignment:Text.AlignVCenter}background:Rectangle {color:parent.highlighted?"#434343":"#252525"}}
    contentItem:Text {text:control.displayText;color:Theme.primary;font:control.font;verticalAlignment:Text.AlignVCenter;elide:Text.ElideRight}
    indicator:Text {x:control.width-22;y:8;text:"⌄";color:Theme.focus;font.pixelSize:16}
    background:Rectangle {radius:6;color:"#282828";border.color:control.activeFocus?Theme.focus:Theme.border}
    popup:Popup {y:control.height+4;width:control.width;implicitHeight:Math.min(contentItem.implicitHeight+12,320);padding:6
        onOpened:bridge.modal(1)
        onClosed:bridge.modal(-1)
        background:Rectangle {radius:8;color:"#252525";border.color:"#565656"}
        contentItem:ListView {clip:true;implicitHeight:contentHeight;model:control.popup.visible?control.delegateModel:null;currentIndex:control.highlightedIndex;ScrollBar.vertical:TCScrollBar {}}
    }
}
