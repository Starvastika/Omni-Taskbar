import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
TCScrollView {
    id:scroll;contentWidth:availableWidth
    property var cal:bridge.calendarData
    ColumnLayout {width:scroll.availableWidth;spacing:14
        Label {text:scroll.cal.fullDate;wrapMode:Text.WordWrap;Layout.fillWidth:true;font.pixelSize:24;font.bold:true}
        Label {text:scroll.cal.selected+"\nISO week "+scroll.cal.isoWeek+" · Day "+scroll.cal.dayOfYear+"\n"+scroll.cal.remaining+" days remaining this year\n"+scroll.cal.daysFromToday+" days from Today";color:"#b4b4b4";lineHeight:1.5}
        Flow {Layout.fillWidth:true;spacing:6
            TCButton {text:"Copy date";onClicked:bridge.act("copy",JSON.stringify({text:scroll.cal.selected}))}
            TCButton {text:"＋ Alarm";onClicked:bridge.newAlarm(scroll.cal.selected)}
        }
        Label {text:"DATE NOTE";color:Theme.muted;font.letterSpacing:1.5}
        TextArea {id:note;Layout.fillWidth:true;Layout.preferredHeight:130;placeholderText:"A note for this day…";wrapMode:TextEdit.Wrap;text:scroll.cal.note}
        TCButton {text:"Save note";onClicked:bridge.act("note",JSON.stringify({date:scroll.cal.selected,text:note.text}))}
        Label {text:"DATE MATH";color:Theme.muted;font.letterSpacing:1.5}
        TextField {id:other;Layout.fillWidth:true;placeholderText:"Compare with YYYY-MM-DD"}
        Label {text:other.text?bridge.dateDifference(scroll.cal.selected,other.text):"Enter a date to compare";color:"#bbbbbb"}
        Label {text:"AGENDA";color:Theme.muted;font.letterSpacing:1.5}
        Label {visible:scroll.cal.agenda.length===0;text:"No scheduled alarms or timers";color:Theme.muted}
        Repeater {model:scroll.cal.agenda
            Label {required property var modelData;Layout.fillWidth:true;wrapMode:Text.WordWrap;text:modelData.time+"  "+modelData.kind+" · "+modelData.label+(modelData.notes?"\n"+modelData.notes:"");color:"#dadada"}
        }
        Label {text:"HOME SOLAR";color:Theme.muted;font.letterSpacing:1.5}
        Label {Layout.fillWidth:true;wrapMode:Text.WordWrap;lineHeight:1.6;color:"#bbbbbb";text:"Sunrise   "+scroll.cal.solar.sunrise+"\nSunset   "+scroll.cal.solar.sunset+"\nDaylight   "+scroll.cal.solar.dayLength+"\nCivil   "+(scroll.cal.solar.civilDawn||"—")+" / "+(scroll.cal.solar.civilDusk||"—")+"\nNautical   "+(scroll.cal.solar.nauticalDawn||"—")+" / "+(scroll.cal.solar.nauticalDusk||"—")+"\nAstronomical   "+(scroll.cal.solar.astronomicalDawn||"—")+" / "+(scroll.cal.solar.astronomicalDusk||"—")+"\nMoon phase   "+(scroll.cal.solar.moonPhase===undefined?"—":scroll.cal.solar.moonPhase+" / 28")}
    }
}
