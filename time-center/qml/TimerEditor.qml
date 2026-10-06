import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
Dialog {
    id:editor;objectName:"timerEditor";modal:true;parent:Overlay.overlay;anchors.centerIn:parent
    width:Math.min(620,parent.width-40);height:Math.min(600,parent.height-40);title:"Edit timer";closePolicy:Popup.CloseOnEscape
    property string editingId:""
    function setDuration(value) {hours.value=Math.floor(value/3600);minutes.value=Math.floor(value/60)%60;seconds.value=Math.floor(value)%60}
    function edit(timer) {editingId=timer.id;name.text=timer.label;setDuration(timer.duration);repeat.checked=timer.repeat;alertSound.currentIndex=Math.max(0,alertSound.model.indexOf(timer.sound||"Default"));open()}
    function payload() {return {op:"edit",id:editingId,label:name.text,seconds:hours.value*3600+minutes.value*60+seconds.value,repeat:repeat.checked,sound:alertSound.currentText}}
    onOpened:bridge.modal(1)
    onClosed:bridge.modal(-1)
    background:Rectangle {radius:10;color:Theme.surface;border.color:Theme.border}
    contentItem:TCScrollView {id:scroll;contentWidth:availableWidth
        ColumnLayout {width:scroll.availableWidth;spacing:14
            Label {text:"Timer name"}
            TextField {id:name;objectName:"timerEditorName";Layout.fillWidth:true;maximumLength:100}
            Label {text:"Hours : Minutes : Seconds"}
            RowLayout {
                TCSpinBox {id:hours;from:0;to:8760;editable:true;Layout.fillWidth:true}
                Label {text:":"}
                TCSpinBox {id:minutes;from:0;to:59;editable:true;Layout.fillWidth:true}
                Label {text:":"}
                TCSpinBox {id:seconds;from:0;to:59;editable:true;Layout.fillWidth:true}
            }
            TCCombo {Layout.fillWidth:true;model:bridge.state.timerPresets.map(p=>p.name);displayText:"Apply preset…";onActivated:editor.setDuration(bridge.state.timerPresets[currentIndex].seconds)}
            TCSwitch {id:repeat;text:"Auto-repeat"}
            Label {text:"Alert sound"}
            TCCombo {id:alertSound;Layout.fillWidth:true;model:["Default","Silent","SystemExclamation","SystemAsterisk","SystemHand"]}
            Label {text:"Completion behavior · shared by all timers and alarms";color:Theme.secondary}
            TCCombo {Layout.fillWidth:true;model:["Show panel","Alert on next open"];currentIndex:model.indexOf(bridge.state.prefs.completion);onActivated:bridge.act("pref",JSON.stringify({key:"completion",value:currentText}))}
            Label {text:"Completed alerts stay until dismissed. Changing duration resets remaining time; running timers keep running.";wrapMode:Text.WordWrap;Layout.fillWidth:true;color:Theme.muted}
        }
    }
    footer:DialogButtonBox {
        TCButton {text:"Cancel";onClicked:editor.close()}
        TCButton {objectName:"timerEditorSave";text:"Save timer";highlighted:true;enabled:editor.payload().seconds>0;onClicked:if(bridge.act("timer",JSON.stringify(editor.payload())))editor.close()}
    }
}
