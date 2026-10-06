import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
ScrollView {
 id:scroll;clip:true;contentWidth:availableWidth;contentHeight:body.implicitHeight+20
 default property alias content:body.data
 ColumnLayout {id:body;width:scroll.availableWidth;spacing:weather.uiState.prefs.density==="compact"?10:weather.uiState.prefs.density==="spacious"?18:14}
}
