import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
TCScrollView {
    id:scroll;contentWidth:availableWidth
    ColumnLayout {width:scroll.availableWidth;spacing:18
        Label {text:"TIME LAB";font.pixelSize:28}
        Label {text:"UTC now, epochs and exact elapsed-time calculations. Inputs without an offset use the timezone below.";color:"#b5b5b5";wrapMode:Text.WordWrap;Layout.fillWidth:true}
        TCCombo {id:mode;model:["Now","Difference","Add duration","Convert","Epoch"];Layout.preferredWidth:260}
        TextField {id:zone;Layout.fillWidth:true;text:bridge.home.zone;placeholderText:"Input/output IANA timezone"}
        TextField {id:first;visible:mode.currentText!=="Now";Layout.fillWidth:true;placeholderText:mode.currentText==="Epoch"?"Unix epoch value":"First datetime: YYYY-MM-DDTHH:MM:SS.mmm"}
        TextField {id:second;visible:mode.currentText==="Difference";Layout.fillWidth:true;placeholderText:"Second datetime: YYYY-MM-DDTHH:MM:SS.mmm"}
        TextField {id:otherZone;visible:mode.currentText==="Convert"||mode.currentText==="Difference";Layout.fillWidth:true;text:"UTC";placeholderText:"Other IANA timezone"}
        TextField {id:seconds;visible:mode.currentText==="Add duration";Layout.fillWidth:true;placeholderText:"Seconds to add or subtract (e.g. -90.250)"}
        TCSwitch {id:milliseconds;visible:mode.currentText==="Epoch";text:"Input is milliseconds"}
        Flow {Layout.fillWidth:true;spacing:8
            TCButton {text:"Calculate / refresh";highlighted:true;onClicked:result.text=bridge.utility(JSON.stringify({mode:mode.currentText,zone:zone.text,otherZone:otherZone.text,a:first.text,b:second.text,seconds:seconds.text,milliseconds:milliseconds.checked}))}
            TCButton {text:"Copy result";onClicked:bridge.act("copy",JSON.stringify({text:result.text}))}
        }
        TextArea {id:result;Layout.fillWidth:true;Layout.preferredHeight:260;readOnly:true;wrapMode:TextEdit.Wrap;text:bridge.utility('{"mode":"Now"}');font.family:"Consolas";font.pixelSize:18;selectByMouse:true}
        Label {text:"Differences and additions use elapsed UTC seconds across DST changes. Leap seconds are not modelled by Python datetime.";color:Theme.muted;wrapMode:Text.WordWrap;Layout.fillWidth:true}
    }
}
