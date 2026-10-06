import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
ColumnLayout {
 id:root;signal selected(var result)
 property alias input:searchInput
 property bool locationsOnly:false
 Label {visible:root.locationsOnly;text:"Choose a weather location";font.pixelSize:20;font.bold:true}
 Label {visible:root.locationsOnly;text:"Search a city or paste coordinates. Weather Center and the taskbar share this selection.";wrapMode:Text.WordWrap;Layout.fillWidth:true;color:"#aaa"}
 WInput {id:searchInput;objectName:"weatherLocationSearchInput";Layout.fillWidth:true;placeholderText:root.locationsOnly?"City, region, country · latitude, longitude":"City, region, country · postal code · latitude, longitude · command";onTextEdited:debounce.restart();onAccepted:if(results.count>0){root.selected(results.model[Math.max(0,results.currentIndex)])}Keys.onDownPressed:{results.forceActiveFocus();results.currentIndex=Math.max(0,results.currentIndex)} }
 Timer {id:debounce;interval:320;onTriggered:weather.search(searchInput.text)}
 ListView {id:results;Layout.fillWidth:true;Layout.fillHeight:true;clip:true;spacing:5;model:root.locationsOnly?weather.results.filter(x=>x.kind==="location"):weather.results;currentIndex:0;keyNavigationEnabled:true;ScrollBar.vertical:ScrollBar {}
  Keys.onReturnPressed:{if(currentIndex>=0)root.selected(model[currentIndex])}
  Keys.onEscapePressed:searchInput.forceActiveFocus()
  delegate:ItemDelegate {required property var modelData;required property int index;width:ListView.view.width;height:65;highlighted:ListView.isCurrentItem;onClicked:{results.currentIndex=index;root.selected(modelData)}
   contentItem:Column {spacing:5;Label {text:modelData.name;font.pixelSize:16;elide:Text.ElideRight;width:parent.width}Label {text:(modelData.region||"")+(modelData.country?" · "+modelData.country:"")+(modelData.lat!==undefined?" · "+Number(modelData.lat).toFixed(3)+", "+Number(modelData.lon).toFixed(3)+" · "+modelData.zone:"");color:"#aaa";elide:Text.ElideRight;width:parent.width}}
   background:Rectangle {color:parent.highlighted?"#424242":"#252525";radius:6;border.color:parent.activeFocus?"#ddd":"#444"}
  }
 }
}
