import QtQuick
import QtQuick.Controls
Switch {
 id:c;implicitHeight:32;spacing:10;leftPadding:0
 indicator:Rectangle {implicitWidth:36;implicitHeight:20;y:(c.height-height)/2;radius:10;color:c.checked?"#888":"#444";border.color:c.activeFocus?"#fff":"#999"
  Rectangle {x:c.checked?18:3;y:3;width:14;height:14;radius:7;color:"#eee"}
 }
 contentItem:Text {text:c.text;font:c.font;color:"#ddd";leftPadding:46;verticalAlignment:Text.AlignVCenter}
}
