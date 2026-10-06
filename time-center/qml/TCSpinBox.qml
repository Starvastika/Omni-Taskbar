import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
SpinBox {
    id:control;implicitWidth:96;implicitHeight:34;leftPadding:25;rightPadding:25
    down.indicator:Rectangle {x:0;y:0;width:24;height:control.height;color:control.down.pressed?"#5e5e5e":"#3a3a3a";radius:5
        Text {anchors.centerIn:parent;text:"−";color:"#d3d3d3";font.pixelSize:17}
    }
    up.indicator:Rectangle {x:control.width-width;y:0;width:24;height:control.height;color:control.up.pressed?"#5e5e5e":"#3a3a3a";radius:5
        Text {anchors.centerIn:parent;text:"+";color:"#d3d3d3";font.pixelSize:17}
    }
    background:Rectangle {radius:5;color:"#232323";border.color:control.activeFocus?Theme.focus:Theme.border}
}
