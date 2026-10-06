import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import TimeCenter 1.0
ColumnLayout {
    id:root;spacing:14
    function rows() {let rows=bridge.alarms.slice(),f=bridge.state.prefs.alarmFilter;if(f!=="All")rows=rows.filter(a=>f==="Enabled"?a.enabled:!a.enabled);rows.sort(bridge.state.prefs.alarmSort==="Name"?(a,b)=>a.label.localeCompare(b.label):(a,b)=>(a.next||Infinity)-(b.next||Infinity));return rows}
    RowLayout {
        TCButton {text:"＋ New alarm";highlighted:true;onClicked:bridge.newAlarm(bridge.calendarData.selected)}
        TCCombo {model:["All","Enabled","Disabled"];currentIndex:model.indexOf(bridge.state.prefs.alarmFilter);onActivated:bridge.act("pref",JSON.stringify({key:"alarmFilter",value:currentText}))}
        TCCombo {model:["Next","Name"];currentIndex:model.indexOf(bridge.state.prefs.alarmSort);onActivated:bridge.act("pref",JSON.stringify({key:"alarmSort",value:currentText}))}
        Item {Layout.fillWidth:true}
        TCSwitch {text:"Alert sound";checked:bridge.state.prefs.sound;onToggled:bridge.act("pref",JSON.stringify({key:"sound",value:checked}))}
    }
    ListView {Layout.fillWidth:true;Layout.fillHeight:true;Layout.minimumHeight:250;clip:true;spacing:10;model:StableModel {source:root.rows()}
        Label {anchors.centerIn:parent;visible:parent.count===0;text:"No alarms in this view. Create one above.";color:Theme.muted}
        delegate:Rectangle {id:card;required property var rowData;width:ListView.view.width;height:130;color:"#232323";radius:10;border.color:"#414141"
            function op(action) {bridge.act("alarm",JSON.stringify({op:action,id:rowData.id}))}
            MouseArea {anchors.fill:parent;acceptedButtons:Qt.RightButton;onClicked:menu.popup()}
            RowLayout {anchors.fill:parent;anchors.margins:16;spacing:16
                ColumnLayout {Layout.fillWidth:true
                    Label {text:card.rowData.label;font.pixelSize:22;elide:Text.ElideRight;Layout.fillWidth:true}
                    Label {text:card.rowData.nextText+" · "+card.rowData.zone;wrapMode:Text.WordWrap;Layout.fillWidth:true;color:"#bababa"}
                    Label {text:card.rowData.countdown+" · "+(card.rowData.weekdays.length?card.rowData.weekdays.map(i=>["Mon","Tue","Wed","Thu","Fri","Sat","Sun"][i]).join(", "):"One time");color:"#b9b9b9"}
                    Label {visible:!!card.rowData.notes;text:card.rowData.notes||"";elide:Text.ElideRight;Layout.fillWidth:true;color:Theme.muted}
                }
                TCSwitch {checked:card.rowData.enabled;onToggled:card.op("toggle");ToolTip.text:checked?"Disable alarm":"Enable alarm";ToolTip.visible:hovered}
                TCButton {text:"Edit";onClicked:alarmEditor.edit(card.rowData)}
                TCButton {text:"More ▾";onClicked:menu.popup()}
            }
            TCMenu {id:menu
                MenuItem {text:card.rowData.enabled?"Disable":"Enable";onTriggered:card.op("toggle")}
                MenuItem {text:"Edit…";onTriggered:alarmEditor.edit(card.rowData)}
                MenuItem {text:"Snooze from now";onTriggered:card.op("snoozeAlarm")}
                MenuItem {text:"Duplicate disabled";onTriggered:card.op("duplicate")}
                MenuItem {text:"Delete…";onTriggered:{confirm.alarmId=card.rowData.id;confirm.open()}}
            }
        }
        ScrollBar.vertical:TCScrollBar {}
    }
    AlarmEditor {id:alarmEditor}
    Dialog {id:confirm;property string alarmId:"";title:"Delete this alarm?";modal:true;parent:Overlay.overlay;anchors.centerIn:parent;standardButtons:Dialog.Yes|Dialog.Cancel;onOpened:bridge.modal(1);onClosed:bridge.modal(-1);onAccepted:bridge.act("alarm",JSON.stringify({op:"delete",id:alarmId}));background:Rectangle {color:"#292929";radius:10;border.color:"#5b5b5b"}}
}
