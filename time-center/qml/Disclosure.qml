import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
ColumnLayout {
    id:root;property string title:"";property bool expanded:true
    default property alias contents:body.data
    spacing:8
    TCButton {text:(root.expanded?"⌄  ":"›  ")+root.title;Layout.fillWidth:true;onClicked:root.expanded=!root.expanded}
    ColumnLayout {id:body;visible:root.expanded;Layout.fillWidth:true;spacing:8}
}
