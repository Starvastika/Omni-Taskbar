import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
Rectangle {
    id: card
    color: Theme.surface; radius: 12; border.color: Theme.border; border.width: 1
    property string title: ""
    default property alias contents: content.data
    ColumnLayout {
        anchors.fill: parent; anchors.margins: 16; spacing: 10
        Label { text: card.title; visible: text.length>0; color: Theme.muted; font.pixelSize: 11; font.letterSpacing: 1.5; font.bold: true }
        Item { id: content; Layout.fillWidth: true; Layout.fillHeight: true }
    }
}
