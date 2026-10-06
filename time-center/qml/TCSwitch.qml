import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
Switch {
    id:control;implicitHeight:32;spacing:10;leftPadding:0;rightPadding:0
    indicator:Rectangle {implicitWidth:36;implicitHeight:20;x:0;y:(control.height-height)/2;radius:10;color:control.checked?"#787878":"#484848";border.color:control.activeFocus?"#f3f3f3":"#828282"
        Rectangle {x:control.checked?18:3;y:3;width:14;height:14;radius:7;color:control.checked?"#ffffff":"#b4b4b4";Behavior on x {NumberAnimation {duration:bridge.state.prefs.reduceMotion?0:100}}}
    }
    contentItem:Text {text:control.text;font:control.font;color:"#dcdcdc";leftPadding:46;verticalAlignment:Text.AlignVCenter}
}
