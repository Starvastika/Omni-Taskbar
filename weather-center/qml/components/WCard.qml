import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
Rectangle {
 id:c;color:weather.uiState.prefs.highContrast?"#1a1a1a":"#222222";radius:10;border.color:weather.uiState.prefs.highContrast?"#eee":"#444"
 property string title:"";default property alias content:body.data
 ColumnLayout {anchors.fill:parent;anchors.margins:weather.uiState.prefs.density==="compact"?12:weather.uiState.prefs.density==="spacious"?20:16;spacing:10
  Label {text:c.title;visible:text.length>0;color:"#a9a9a9";font.pixelSize:11;font.bold:true;font.letterSpacing:1.2}
  Item {id:body;Layout.fillWidth:true;Layout.fillHeight:true}
 }
}
