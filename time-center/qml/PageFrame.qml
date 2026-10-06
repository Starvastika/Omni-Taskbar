import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
TCScrollView {
    id:frame;property real minimumWidth:1080;property real minimumHeight:620
    default property alias contents:body.data
    contentWidth:Math.max(availableWidth,minimumWidth)
    contentHeight:Math.max(availableHeight,minimumHeight)
    Item {id:body;width:frame.contentWidth;height:frame.contentHeight}
}
