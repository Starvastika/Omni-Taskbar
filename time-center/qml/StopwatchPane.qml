import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import TimeCenter 1.0
ColumnLayout {
    id:root;property bool compact:false;spacing:14
    function command(op) {bridge.act("stopwatch",JSON.stringify({op:op}))}
    function toggle() {command(bridge.stopwatch.running?"pause":"start")}
    Label {text:bridge.stopwatchDisplay;font.pixelSize:compact?34:72;font.weight:Font.Light;Layout.alignment:Qt.AlignHCenter;font.family:"Consolas"}
    RowLayout {Layout.alignment:Qt.AlignHCenter
        TCButton {text:bridge.stopwatch.running?"Pause":"Start / resume";highlighted:true;onClicked:root.toggle()}
        TCButton {text:"Lap";enabled:bridge.stopwatch.running;onClicked:root.command("lap")}
        TCButton {text:"Reset";onClicked:root.command("reset")}
        TCButton {visible:!compact;text:"Copy laps";onClicked:bridge.act("copyLaps","{}")}
    }
    RowLayout {visible:!compact;Layout.alignment:Qt.AlignHCenter
        Label {text:"Precision";color:"#b0b0b0"}
        TCCombo {model:["HH:MM:SS","Tenths · .d","Hundredths · .dd","Milliseconds · .mmm"];currentIndex:bridge.state.prefs.precision;onActivated:bridge.act("pref",JSON.stringify({key:"precision",value:currentIndex}))}
        Label {text:"Space  start/pause     L  lap     R  reset";color:Theme.muted}
    }
    Label {visible:!compact;Layout.alignment:Qt.AlignHCenter;text:"Best "+bridge.stopwatch.best+"    Slowest "+bridge.stopwatch.slowest+"    Average "+bridge.stopwatch.average+"    Median "+bridge.stopwatch.median;color:"#afafaf"}
    Label {visible:!compact;text:"LAP                       TOTAL / SPLIT                       LAP DURATION                       CHANGE";color:Theme.muted;font.pixelSize:11}
    ListView {visible:!compact;Layout.fillWidth:true;Layout.fillHeight:true;Layout.minimumHeight:200;clip:true;spacing:4
        model:StableModel {source:bridge.stopwatch.laps}
        delegate:Rectangle {required property var rowData;width:ListView.view.width;height:42;radius:5;color:rowData.best?"#383838":"#212121"
            RowLayout {anchors.fill:parent;anchors.margins:10
                Label {text:rowData.n+(rowData.best?"  ★ best":rowData.slowest?"  slowest":"");Layout.preferredWidth:130;color:"#c1c1c1"}
                Label {text:rowData.total;Layout.fillWidth:true;font.family:"Consolas"}
                Label {text:rowData.duration;Layout.fillWidth:true;font.family:"Consolas"}
                Label {text:rowData.delta;Layout.fillWidth:true;font.family:"Consolas"}
            }
        }
        ScrollBar.vertical:TCScrollBar {}
    }
    Shortcut {sequence:"Space";enabled:root.visible&&!compact&&bridge.modalCount===0&&!bridge.textEditing;onActivated:if(!bridge.editing())root.toggle()}
    Shortcut {sequence:"L";enabled:root.visible&&!compact&&bridge.modalCount===0&&!bridge.textEditing;onActivated:if(!bridge.editing())root.command("lap")}
    Shortcut {sequence:"R";enabled:root.visible&&!compact&&bridge.modalCount===0&&!bridge.textEditing;onActivated:if(!bridge.editing())root.command("reset")}
}
