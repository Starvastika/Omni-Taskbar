import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import TimeCenter 1.0
ColumnLayout {
    id:root;property bool compact:false;spacing:12
    TimerEditor {id:timerEditor}
    function seconds() {return hours.value*3600+minutes.value*60+secondsField.value}
    function rows() {let rows=bridge.timers.slice(), f=bridge.state.prefs.timerFilter;if(f!=="All")rows=rows.filter(t=>t.status===f.toLowerCase());if(bridge.state.prefs.timerSort==="Name")rows.sort((a,b)=>a.label.localeCompare(b.label));if(bridge.state.prefs.timerSort==="Remaining")rows.sort((a,b)=>a.display.localeCompare(b.display));return rows}
    Flow {Layout.fillWidth:true;spacing:8
        TextField {id:label;width:compact?150:220;placeholderText:"Timer name"}
        Row {spacing:3
            TCSpinBox {id:hours;from:0;to:8760;value:0;editable:true;textFromValue:function(value,locale){return String(value).padStart(2,"0")};valueFromText:function(text,locale){return Number(text)};width:100;ToolTip.text:"Hours";ToolTip.visible:hovered}
            Label {text:":";height:40;verticalAlignment:Text.AlignVCenter}
            TCSpinBox {id:minutes;from:0;to:59;value:5;editable:true;textFromValue:function(value,locale){return String(value).padStart(2,"0")};valueFromText:function(text,locale){return Number(text)};width:90;ToolTip.text:"Minutes";ToolTip.visible:hovered}
            Label {text:":";height:40;verticalAlignment:Text.AlignVCenter}
            TCSpinBox {id:secondsField;from:0;to:59;value:0;editable:true;textFromValue:function(value,locale){return String(value).padStart(2,"0")};valueFromText:function(text,locale){return Number(text)};width:90;ToolTip.text:"Seconds";ToolTip.visible:hovered}
        }
        TCButton {text:"Start";highlighted:true;enabled:root.seconds()>0;onClicked:bridge.act("timer",JSON.stringify({op:"add",label:label.text,seconds:root.seconds(),repeat:autoRepeat.checked,sound:sound.currentText}))}
        TCSwitch {id:autoRepeat;visible:!compact;text:"Auto-repeat"}
        TCCombo {id:sound;visible:!compact;model:["Default","Silent","SystemExclamation","SystemAsterisk","SystemHand"];implicitWidth:160}
        TCButton {visible:!compact;text:"Save preset";enabled:root.seconds()>0;onClicked:bridge.act("timerPreset",JSON.stringify({op:"add",name:label.text||"Custom",seconds:root.seconds()}))}
    }
    Flow {visible:!compact;Layout.fillWidth:true;spacing:6
        Repeater {model:bridge.state.timerPresets;TCButton {required property var modelData;required property int index;text:modelData.name;onClicked:bridge.act("timer",JSON.stringify({op:"add",label:modelData.name,seconds:modelData.seconds}));ToolTip.text:"Start preset · right-click to remove";ToolTip.visible:hovered
            MouseArea {anchors.fill:parent;acceptedButtons:Qt.RightButton;onClicked:presetMenu.popup()}
            TCMenu {id:presetMenu;MenuItem {text:"Remove preset";onTriggered:bridge.act("timerPreset",JSON.stringify({op:"delete",index:index}))}}
        }}
    }
    RowLayout {visible:!compact
        TCCombo {model:["All","Running","Paused","Completed"];currentIndex:model.indexOf(bridge.state.prefs.timerFilter);onActivated:bridge.act("pref",JSON.stringify({key:"timerFilter",value:currentText}))}
        TCCombo {model:["Created","Name","Remaining"];currentIndex:model.indexOf(bridge.state.prefs.timerSort);onActivated:bridge.act("pref",JSON.stringify({key:"timerSort",value:currentText}))}
        TCSwitch {text:"Detailed";checked:bridge.state.prefs.timerDetailed;onToggled:bridge.act("pref",JSON.stringify({key:"timerDetailed",value:checked}))}
    }
    ListView {Layout.fillWidth:true;Layout.fillHeight:true;Layout.minimumHeight:120;model:StableModel {source:root.rows()}clip:true;spacing:8
        Label {anchors.centerIn:parent;visible:parent.count===0;text:"No timers in this view. Set HH : MM : SS above.";color:Theme.muted}
        delegate:Rectangle {
            id:card;required property var rowData;width:ListView.view.width;height:compact||!bridge.state.prefs.timerDetailed?106:150;radius:8;color:"#212121";border.color:"#3d3d3d"
            function op(action,extra) {bridge.act("timer",JSON.stringify({id:rowData.id,op:action,seconds:extra||0}))}
            MouseArea {anchors.fill:parent;acceptedButtons:Qt.RightButton;onClicked:mouse=>menu.popup(card,mouse.x,mouse.y)}
            ColumnLayout {anchors.fill:parent;anchors.margins:12;spacing:6
                RowLayout {Label {text:card.rowData.label;Layout.fillWidth:true;font.bold:true;elide:Text.ElideRight}Label {text:card.rowData.display;font.pixelSize:26;font.family:"Consolas"}Label {text:card.rowData.status+(card.rowData.repeat?" · ↻":"");color:Theme.muted}}
                ProgressBar {Layout.fillWidth:true;value:card.rowData.progress}
                Flow {Layout.fillWidth:true;spacing:5
                    TCButton {text:card.rowData.status==="running"?"Pause":"Resume";onClicked:card.op(card.rowData.status==="running"?"pause":"resume")}
                    TCButton {text:"+10s";onClicked:card.op("extend",10)}
                    TCButton {text:"Reset";onClicked:card.op("reset")}
                    TCButton {id:moreButton;text:"More ▾";onClicked:menu.popup(moreButton,0,moreButton.height)}
                    Repeater {model:!compact&&bridge.state.prefs.timerDetailed?[30,60,300,600]:[];TCButton {required property int modelData;text:modelData<60?"+30s":"+"+modelData/60+"m";onClicked:card.op("extend",modelData)}}
                }
            }
            TCMenu {id:menu;objectName:"timerMoreMenu"
                MenuItem {text:"TIME ADJUSTMENT";enabled:false}
                MenuItem {objectName:"timerPlus10";text:"+10 seconds";onTriggered:card.op("extend",10)}
                MenuItem {text:"+30 seconds";onTriggered:card.op("extend",30)}
                MenuItem {text:"+1 minute";onTriggered:card.op("extend",60)}
                MenuItem {text:"+5 minutes";onTriggered:card.op("extend",300)}
                MenuItem {text:"+10 minutes";onTriggered:card.op("extend",600)}
                MenuItem {text:"−10 seconds";enabled:card.rowData.remainingSeconds>=11&&card.rowData.duration>10;onTriggered:card.op("extend",-10)}
                MenuItem {text:"−30 seconds";enabled:card.rowData.remainingSeconds>=31&&card.rowData.duration>30;onTriggered:card.op("extend",-30)}
                MenuItem {text:"−1 minute";enabled:card.rowData.remainingSeconds>=61&&card.rowData.duration>60;onTriggered:card.op("extend",-60)}
                MenuSeparator {}
                MenuItem {objectName:"timerPauseResume";text:card.rowData.status==="running"?"Pause":"Resume";onTriggered:card.op(card.rowData.status==="running"?"pause":"resume")}
                MenuItem {text:"Restart";onTriggered:card.op("restart")}
                MenuItem {text:"Reset (paused)";onTriggered:card.op("reset")}
                MenuItem {objectName:"timerDuplicate";text:"Duplicate (paused)";onTriggered:card.op("duplicate")}
                MenuItem {objectName:"timerEdit";text:"Rename / Edit…";onTriggered:timerEditor.edit(card.rowData)}
                MenuItem {objectName:"timerDelete";text:"Delete";onTriggered:card.op("delete")}
                MenuItem {text:"Auto-repeat";checkable:true;checked:card.rowData.repeat;onTriggered:card.op("repeat")}
                MenuSeparator {}
                MenuItem {text:"Save duration as preset";onTriggered:bridge.act("timerPreset",JSON.stringify({op:"add",name:card.rowData.label,seconds:card.rowData.duration}))}
                MenuItem {text:"Alert sound…";onTriggered:timerEditor.edit(card.rowData)}
                MenuItem {text:"Completion behavior…";onTriggered:timerEditor.edit(card.rowData)}
                MenuItem {text:"Keep alert until dismissed";checkable:true;checked:true;enabled:false}
                MenuItem {text:"Detailed timer editor…";onTriggered:timerEditor.edit(card.rowData)}
            }
        }
        ScrollBar.vertical:TCScrollBar {}
    }
}
