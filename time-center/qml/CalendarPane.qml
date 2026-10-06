import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import TimeCenter 1.0
ColumnLayout {
    property bool compact:false
    property var cal:bridge.calendarData
    function go(delta) { let d=new Date(cal.year,cal.month-1+delta,1);bridge.calendarGo(d.getFullYear(),d.getMonth()+1,cal.selected) }
    RowLayout {
        Layout.fillWidth:true
        TCButton { text:"‹";onClicked:go(-1) }
        Label { text:cal.title;font.pixelSize:compact?14:24;Layout.fillWidth:true;font.bold:true }
        TCButton { text:"›";onClicked:go(1) }
        TCButton { text:"Today";onClicked:bridge.calendarToday() }
    }
    RowLayout { visible:!compact
        TCSpinBox { id:year;from:1900;to:2200;value:cal.year;editable:true }
        ComboBox { id:month;model:["January","February","March","April","May","June","July","August","September","October","November","December"];currentIndex:cal.month-1 }
        TCButton { text:"Go";onClicked:bridge.calendarGo(year.value,month.currentIndex+1,cal.selected) }
        CheckBox { text:"ISO weeks";checked:bridge.state.prefs.weeks;onToggled:bridge.act("pref",JSON.stringify({key:"weeks",value:checked})) }
    }
    GridLayout {
        Layout.fillWidth:true;Layout.fillHeight:true;columns:7;rowSpacing:4;columnSpacing:4
        Repeater { model:cal.headers;Label { required property string modelData;text:modelData;color:Theme.muted;Layout.fillWidth:true;horizontalAlignment:Text.AlignHCenter } }
        Repeater { model:StableModel {source:cal.cells}
            Rectangle {
                required property var rowData;property var modelData:rowData
                required property int index
                Layout.fillWidth:true;Layout.fillHeight:true;Layout.minimumHeight:compact?24:55
                radius:6;color:modelData.selected?"#494949":modelData.today?"#3c3c3c":"#1e1e1e";border.color:modelData.today?Theme.focus:"transparent"
                Label { anchors.centerIn:parent;text:modelData.day;font.pixelSize:compact?12:18;color:modelData.current?"#f1f1f1":"#737373" }
                Label { anchors.left:parent.left;anchors.top:parent.top;anchors.margins:3;font.pixelSize:8;color:"#7f7f7f";text:bridge.state.prefs.weeks&&index%7===0?modelData.week:"" }
                Rectangle { visible:modelData.note;width:4;height:4;radius:2;color:Theme.focus;anchors.bottom:parent.bottom;anchors.horizontalCenter:parent.horizontalCenter;anchors.bottomMargin:3 }
                MouseArea { anchors.fill:parent;onClicked:bridge.calendarGo(cal.year,cal.month,modelData.date) }
            }
        }
    }
    Label { text:cal.detail;wrapMode:Text.WordWrap;Layout.fillWidth:true;color:"#b1b1b1";font.pixelSize:compact?10:13 }
    Label { text:cal.events.join("\n") || "No alarms or timers on this day";visible:!compact;wrapMode:Text.WordWrap;Layout.fillWidth:true;color:Theme.muted }
    TextArea { id:note;visible:!compact;Layout.fillWidth:true;Layout.preferredHeight:70;placeholderText:"A local note for this date…";text:cal.note;wrapMode:TextEdit.Wrap }
    TCButton { visible:!compact;text:"Save date note";onClicked:bridge.act("note",JSON.stringify({date:cal.selected,text:note.text})) }
}
