import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
ScrollView {
    clip:true
    Component.onCompleted:if(contentItem&&contentItem.boundsBehavior!==undefined)contentItem.boundsBehavior=Flickable.StopAtBounds
    ScrollBar.vertical:TCScrollBar {}
    ScrollBar.horizontal:TCScrollBar {}
}
