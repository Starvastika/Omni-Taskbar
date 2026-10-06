import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
Menu {
    id:menu;padding:6;margins:8
    // Explicit MenuItems do not use delegate implicitWidth. Size the popup itself.
    implicitWidth:300
    implicitHeight:Math.min(contentItem.implicitHeight+topPadding+bottomPadding,Overlay.overlay?Overlay.overlay.height-24:640)
    contentItem:ListView {
        implicitHeight:contentHeight;model:menu.contentModel;clip:true
        interactive:contentHeight>height;boundsBehavior:Flickable.StopAtBounds
        currentIndex:menu.currentIndex
        onCurrentIndexChanged:if(currentIndex>=0)positionViewAtIndex(currentIndex,ListView.Contain)
        ScrollBar.vertical:TCScrollBar {}
    }
    onOpened:bridge.modal(1)
    onClosed:bridge.modal(-1)
    delegate:MenuItem {id:item;implicitWidth:235;implicitHeight:34
        contentItem:Text {text:item.text;color:item.enabled?"#ebebeb":"#7c7c7c";font:item.font;verticalAlignment:Text.AlignVCenter}
        background:Rectangle {radius:5;color:item.highlighted?"#464646":"transparent"}
    }
    background:Rectangle {radius:8;color:"#252525";border.color:"#5b5b5b"}
}
