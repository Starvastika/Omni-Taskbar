import QtQuick
import QtQuick.Controls
TextField {
 implicitHeight:weather.uiState.prefs.density==="compact"?32:weather.uiState.prefs.density==="spacious"?42:36;leftPadding:10;rightPadding:10;color:"#eee";placeholderTextColor:weather.uiState.prefs.highContrast?"#ccc":"#999";selectByMouse:true
 background:Rectangle {radius:6;color:"#1c1c1c";border.color:parent.activeFocus||weather.uiState.prefs.highContrast?"#eee":"#555"}
}
