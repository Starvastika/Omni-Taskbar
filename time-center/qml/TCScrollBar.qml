import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
ScrollBar {
    id:bar;policy:ScrollBar.AsNeeded;interactive:true
    padding:2;implicitWidth:10;implicitHeight:10;minimumSize:.045
    contentItem:Rectangle {implicitWidth:6;implicitHeight:6;radius:3;color:bar.pressed?Theme.focus:"#7d7d7d";opacity:bar.active||bar.hovered?1:0;Behavior on opacity {NumberAnimation {duration:bridge.state.prefs.reduceMotion?0:180}}}
    background:Rectangle {color:"#242424";radius:4;opacity:bar.active?.65:0}
}
