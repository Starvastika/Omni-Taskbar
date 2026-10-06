import QtQuick
import QtQuick.Controls
import "Theme.js" as T
Button {
 id:c;implicitHeight:weather.uiState.prefs.density==="compact"?30:weather.uiState.prefs.density==="spacious"?40:34;implicitWidth:Math.max(34,t.implicitWidth+24);padding:8;hoverEnabled:true
 contentItem:Text {id:t;text:c.text;color:c.enabled?T.primary:"#777";font:c.font;horizontalAlignment:Text.AlignHCenter;verticalAlignment:Text.AlignVCenter;elide:Text.ElideRight}
 background:Rectangle {radius:6;color:c.down?"#595959":c.highlighted?"#454545":c.hovered?T.hover:T.elevated;border.color:c.activeFocus||c.highlighted||weather.uiState.prefs.highContrast?T.focus:T.border}
 Accessible.name:text
}
