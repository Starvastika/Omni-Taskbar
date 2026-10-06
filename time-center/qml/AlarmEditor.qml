import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
Dialog {
    id:editor;modal:true;parent:Overlay.overlay;anchors.centerIn:parent;width:Math.min(660,parent.width-50);height:Math.min(710,parent.height-70);title:editingId?"Edit alarm":"New alarm";closePolicy:Popup.CloseOnEscape
    property string editingId:""
    function payload() {let weekdays=[];if(repeat.checked)for(let i=0;i<7;i++)if(days.itemAt(i).checked)weekdays.push(i);return {id:editingId,label:label.text,date:date.text,time:clock.text,zone:zone.editText,weekdays:weekdays,notes:notes.text,snoozeMinutes:Number(snooze.currentText),sound:sound.currentText}}
    function updatePreview() {preview.text=repeat.checked&&!payload().weekdays.length?"Select at least one weekday":bridge.alarmPreview(JSON.stringify(payload()))}
    function create(day) {editingId="";label.text="";date.text=day||bridge.calendarData.selected;clock.text="09:00:00";zone.editText=bridge.home.zone;repeat.checked=false;notes.text="";snooze.currentIndex=[1,5,10,15,30].indexOf(bridge.state.prefs.snoozeMinutes);sound.currentIndex=0;open();updatePreview()}
    function edit(alarm) {editingId=alarm.id;label.text=alarm.label;date.text=alarm.date||bridge.calendarData.selected;clock.text=alarm.time||"09:00:00";zone.editText=alarm.zone;repeat.checked=alarm.weekdays.length>0;for(let i=0;i<7;i++)days.itemAt(i).checked=alarm.weekdays.indexOf(i)>=0;notes.text=alarm.notes||"";snooze.currentIndex=[1,5,10,15,30].indexOf(alarm.snoozeMinutes||5);sound.currentIndex=sound.model.indexOf(alarm.sound||"Default");open();updatePreview()}
    onOpened:bridge.modal(1)
    onClosed:bridge.modal(-1)
    background:Rectangle {radius:12;color:Theme.surface;border.color:"#606060"}
    contentItem:TCScrollView {id:editorScroll;contentWidth:availableWidth
        ColumnLayout {width:editorScroll.availableWidth;spacing:14
            Label {text:"Label";color:"#b2b2b2"}
            TextField {id:label;Layout.fillWidth:true;placeholderText:"Alarm name"}
            RowLayout {TextField {id:date;Layout.fillWidth:true;placeholderText:"YYYY-MM-DD";onTextEdited:editor.updatePreview()}TextField {id:clock;Layout.preferredWidth:150;placeholderText:"HH:MM:SS";onTextEdited:editor.updatePreview()}}
            Label {text:"Timezone · type an IANA zone, or choose one";color:"#b2b2b2"}
            ComboBox {id:zone;Layout.fillWidth:true;editable:true;model:bridge.zones;onEditTextChanged:if(editor.opened)editor.updatePreview();popup.onOpened:bridge.modal(1);popup.onClosed:bridge.modal(-1)}
            TCSwitch {id:repeat;text:"Repeat on weekdays";onToggled:editor.updatePreview()}
            Flow {Layout.fillWidth:true;spacing:4
                Repeater {id:days;model:["Mon","Tue","Wed","Thu","Fri","Sat","Sun"];CheckBox {required property string modelData;text:modelData;enabled:repeat.checked;checked:modelData!=="Sat"&&modelData!=="Sun";onToggled:editor.updatePreview()}}
            }
            TextArea {id:notes;Layout.fillWidth:true;Layout.preferredHeight:100;placeholderText:"Notes (optional)";wrapMode:TextEdit.Wrap}
            RowLayout {Label {text:"Snooze minutes"}TCCombo {id:snooze;model:["1","5","10","15","30"]}TCCombo {id:sound;model:["Default","Silent","SystemExclamation","SystemAsterisk","SystemHand"]}}
            Label {id:preview;Layout.fillWidth:true;wrapMode:Text.WordWrap;color:"#c5c5c5"}
            Label {text:"The host must be running. No wake-from-sleep guarantee.";color:Theme.muted}
        }
    }
    footer:DialogButtonBox {
        TCButton {text:"Cancel";onClicked:editor.close()}
        TCButton {text:"Save alarm";highlighted:true;onClicked:{editor.updatePreview();if(!preview.text.startsWith("Next:"))return;let p=editor.payload();p.op=editor.editingId?"edit":"add";if(bridge.act("alarm",JSON.stringify(p)))editor.close()}}
    }
}
