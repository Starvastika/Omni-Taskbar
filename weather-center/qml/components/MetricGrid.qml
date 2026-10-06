import QtQuick
import QtQuick.Layouts
GridLayout {
 id:grid;property var items:[];property bool dashboard:false
 columns:Math.max(1,Math.floor(width/(weather.uiState.prefs.density==="compact"?195:235)));columnSpacing:10;rowSpacing:10
 Repeater {model:grid.items;MetricCard {required property var modelData;metric:modelData;dashboard:grid.dashboard;Layout.fillWidth:true;Layout.minimumWidth:140;Layout.preferredHeight:implicitHeight}}
}
