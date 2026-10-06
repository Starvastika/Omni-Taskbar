import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
import "../charts"
WPage {
 id:page;property int selectedDay:0;property var comparison:[];property string mode:"Cards"
 RowLayout {Layout.fillWidth:true;Label {text:"DAILY OUTLOOK";font.pixelSize:22;font.bold:true;Layout.fillWidth:true}WCombo {model:["Cards","Compact list","Comparison table"];onActivated:page.mode=currentText}}
 GridLayout {Layout.fillWidth:true;columns:page.mode==="Cards"?Math.max(1,Math.floor(width/245)):1;columnSpacing:10;rowSpacing:10
  Repeater {model:weather.daily;Rectangle {required property var modelData;required property int index;Layout.fillWidth:true;Layout.preferredHeight:page.mode==="Cards"?170:80;color:page.selectedDay===index?"#383838":"#252525";radius:8;border.color:page.selectedDay===index?"#ddd":"#444"
   ColumnLayout {anchors.fill:parent;anchors.margins:12;spacing:5
    RowLayout {Layout.fillWidth:true;Label {text:modelData.date;font.bold:true;Layout.fillWidth:true}CheckBox {checked:page.comparison.indexOf(index)>=0;onClicked:{let ids=page.comparison.slice();let p=ids.indexOf(index);if(p>=0)ids.splice(p,1);else if(ids.length<4)ids.push(index);page.comparison=ids}ToolTip.text:"Select 2–4 days to compare";ToolTip.visible:hovered}}
    Label {text:modelData.icon+" "+modelData.max+" / "+modelData.min;font.pixelSize:18}
    Label {visible:page.mode==="Cards";text:modelData.condition+"\n"+modelData.rain+" · "+modelData.probability+"\nWind "+modelData.wind+" · UV "+modelData.uv;color:"#bbb";wrapMode:Text.Wrap;Layout.fillWidth:true}
    WButton {text:"Inspect day";implicitHeight:27;onClicked:page.selectedDay=index}
   }
  }}
 }
 WCard {title:"COMPARE SELECTED DAYS (2–4)";visible:page.comparison.length>1;Layout.fillWidth:true;Layout.preferredHeight:190
  RowLayout {anchors.fill:parent;Repeater {model:page.comparison;Column {required property int modelData;property var day:weather.daily[modelData];Layout.fillWidth:true;spacing:8;Label {text:parent.day.date;font.bold:true}Label {text:parent.day.min+" → "+parent.day.max}Label {text:"Rain "+parent.day.rain+" · Gust "+parent.day.gust;color:"#bbb"}Label {text:"UV "+parent.day.uv+" · Daylight "+parent.day.daylight;color:"#bbb"}}}}
 }
 WCard {title:weather.daily.length?weather.daily[Math.min(page.selectedDay,weather.daily.length-1)].date+" · DAY INSPECTOR":"DAY INSPECTOR";Layout.fillWidth:true;Layout.preferredHeight:520
  ColumnLayout {anchors.fill:parent
   Label {property var day:weather.daily.length?weather.daily[Math.min(page.selectedDay,weather.daily.length-1)]:({});text:"Sunrise "+(day.sunrise||"—")+"   Sunset "+(day.sunset||"—")+"   Daylight "+(day.daylight||"—");color:"#bbb"}
   Meteogram {Layout.fillWidth:true;Layout.fillHeight:true;dataset:weather.daily.length?weather.dayChartModel(Math.min(page.selectedDay,weather.daily.length-1)):[];horizon:24;keys:["temperature_2m","precipitation","wind_speed_10m"]}
  }
 }
 Label {text:"Daily provider fields";font.pixelSize:21}
 Flow {Layout.fillWidth:true;Layout.preferredHeight:implicitHeight;spacing:15
  Repeater {model:weather.daily.length?Object.keys(weather.daily[Math.min(page.selectedDay,weather.daily.length-1)].formatted):[];Label {required property string modelData;text:modelData+": "+weather.daily[Math.min(page.selectedDay,weather.daily.length-1)].formatted[modelData];color:"#aaa"}}
 }
}
