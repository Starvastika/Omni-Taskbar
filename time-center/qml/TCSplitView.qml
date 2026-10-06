import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
SplitView {
    handle:Rectangle {implicitWidth:10;implicitHeight:10;color:SplitHandle.pressed?"#555555":"transparent"
        Rectangle {anchors.centerIn:parent;width:parent.width>10?40:3;height:parent.height>10?40:3;radius:2;color:SplitHandle.hovered?Theme.focus:"#545454"}
    }
}
