import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
Button {
    id:control
    implicitWidth:Math.max(34,label.implicitWidth+24);implicitHeight:32
    padding:8;hoverEnabled:true
    contentItem:Text {id:label;text:control.text;font.family:"Segoe UI Variable";font.pixelSize:12;color:control.enabled?Theme.primary:Theme.disabled;horizontalAlignment:Text.AlignHCenter;verticalAlignment:Text.AlignVCenter}
    background:Rectangle {radius:6;color:control.down?"#595959":control.highlighted?Theme.selected:control.hovered?Theme.hover:Theme.elevated;border.color:control.highlighted?Theme.focus:Theme.border;Behavior on color {ColorAnimation {duration:bridge.state.prefs.reduceMotion?0:100}}}
}
