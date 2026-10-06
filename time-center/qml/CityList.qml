import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import TimeCenter 1.0
ColumnLayout {
    id:root;spacing:9;property var contextCity:({})
    function rows() {let rows=bridge.cities.slice(),prefs=bridge.state.prefs;rows=rows.filter(c=>prefs.cityFilter==="Favorites"?c.favorite:prefs.cityFilter==="Day"?c.solarState==="Day":prefs.cityFilter==="Night"?c.solarState==="Night":prefs.cityFilter==="Same date"?c.relation==="Today":true);if(prefs.citySort==="Name")rows.sort((a,b)=>a.name.localeCompare(b.name));else if(prefs.citySort==="UTC offset")rows.sort((a,b)=>a.offsetSeconds-b.offsetSeconds);else if(prefs.citySort==="Local time")rows.sort((a,b)=>a.localSeconds-b.localSeconds);return rows}
    StableModel {id:cityModel}
    function updateRows() {if(visible)cityModel.source=rows()}
    onVisibleChanged:updateRows()
    Component.onCompleted:updateRows()
    Connections {target:bridge;function onClocksChanged(){root.updateRows()}function onChanged(){root.updateRows()}}
    function cityAction(op) {bridge.act("city",JSON.stringify({id:contextCity.id,op:op}))}
    function focusSearch() {search.forceActiveFocus();search.selectAll()}
    TextField {id:search;Layout.fillWidth:true;placeholderText:"City, region, country or IANA zone";onTextEdited:{bridge.cancelSearch();debounce.restart()}}
    Timer {id:debounce;interval:320;onTriggered:bridge.searchCity(search.text)}
    ListView {Layout.fillWidth:true;Layout.preferredHeight:bridge.results.length?Math.min(165,Math.max(80,root.height*.25)):0;visible:bridge.results.length>0;clip:true;model:bridge.results;spacing:4
        delegate:ItemDelegate {required property var modelData;width:ListView.view.width;height:55
            contentItem:RowLayout {
                ColumnLayout {Layout.fillWidth:true;spacing:1
                    Label {text:modelData.name;font.bold:true;elide:Text.ElideRight;Layout.fillWidth:true}
                    Label {text:modelData.region+" · "+modelData.zone;color:Theme.muted;font.pixelSize:10;elide:Text.ElideRight;Layout.fillWidth:true}
                }
                TCButton {text:"＋";onClicked:bridge.act("addCity",JSON.stringify(modelData));ToolTip.text:"Save city";ToolTip.visible:hovered}
            }
            onClicked:bridge.act("preview",JSON.stringify(modelData))
        }
        ScrollBar.vertical:TCScrollBar {}
    }
    Flow {Layout.fillWidth:true;spacing:5
        TCCombo {width:125;model:["Custom","Name","UTC offset","Local time"];currentIndex:model.indexOf(bridge.state.prefs.citySort);onActivated:bridge.act("pref",JSON.stringify({key:"citySort",value:currentText}))}
        TCCombo {width:120;model:["All","Favorites","Day","Night","Same date"];currentIndex:model.indexOf(bridge.state.prefs.cityFilter);onActivated:bridge.act("pref",JSON.stringify({key:"cityFilter",value:currentText}))}
        TCButton {text:bridge.state.prefs.density;onClicked:bridge.act("pref",JSON.stringify({key:"density",value:bridge.state.prefs.density==="Compact"?"Detailed":"Compact"}))}
    }
    ListView {id:saved;Layout.fillWidth:true;Layout.fillHeight:true;Layout.minimumHeight:150;clip:true;model:cityModel;spacing:7
        Label {anchors.centerIn:parent;visible:saved.count===0;text:"No matching cities. Search above to add.";color:Theme.muted;font.pixelSize:11}
        delegate:Rectangle {id:card;required property var rowData;width:ListView.view.width;height:bridge.state.prefs.density==="Compact"?85:bridge.state.prefs.citySolar?154:137;radius:8;color:rowData.id===bridge.selected.id?Theme.selected:"#232323";border.color:rowData.id===bridge.selected.id?Theme.focus:"#414141"
            MouseArea {anchors.fill:parent;acceptedButtons:Qt.LeftButton|Qt.RightButton;onClicked:mouse=>{if(mouse.button===Qt.RightButton){root.contextCity=card.rowData;menu.popup()}else bridge.act("select",JSON.stringify({id:card.rowData.id}))}}
            ColumnLayout {anchors.fill:parent;anchors.margins:10;spacing:3
                RowLayout {Layout.fillWidth:true
                    Label {text:(card.rowData.id===bridge.state.homeId?"⌂ ":"")+(card.rowData.favorite?"★ ":"")+card.rowData.name;font.bold:true;Layout.fillWidth:true;elide:Text.ElideRight}
                    Label {text:card.rowData.time;font.pixelSize:18;font.family:"Consolas"}
                }
                Label {visible:bridge.state.prefs.density!=="Compact";text:card.rowData.region||"Timezone";color:"#a9a9a9";font.pixelSize:10;elide:Text.ElideRight;Layout.fillWidth:true}
                Label {text:card.rowData.abbreviation+" · "+card.rowData.offset+" · "+card.rowData.difference+(card.rowData.dst?" · DST":"");color:"#b7b7b7";font.pixelSize:10}
                Label {visible:bridge.state.prefs.density!=="Compact";text:card.rowData.zone+" · "+card.rowData.relation+"\n"+(card.rowData.solarState==="Day"?"☀ ":"☾ ")+card.rowData.solarState+" · "+card.rowData.date;color:"#b1b1b1";font.pixelSize:10;elide:Text.ElideRight;Layout.fillWidth:true}
                Label {visible:bridge.state.prefs.citySolar&&bridge.state.prefs.density!=="Compact";text:"↑ "+(card.rowData.sunrise||"—")+"    ↓ "+(card.rowData.sunset||"—");color:"#b0b0b0";font.pixelSize:10}
                RowLayout {
                    TCButton {text:"View";implicitHeight:25;onClicked:bridge.act("select",JSON.stringify({id:card.rowData.id}))}
                    TCButton {text:"Actions ▾";implicitHeight:25;onClicked:{root.contextCity=card.rowData;menu.popup()}}
                    Item {Layout.fillWidth:true}
                }
            }
        }
        ScrollBar.vertical:TCScrollBar {}
    }
    TCMenu {id:menu
        MenuItem {text:"Set Home";onTriggered:root.cityAction("home")}
        MenuItem {text:root.contextCity.favorite?"Remove favorite":"Favorite";onTriggered:root.cityAction("favorite")}
        MenuItem {text:"Focus map";onTriggered:{bridge.act("select",JSON.stringify({id:root.contextCity.id}));bridge.act("focus","{}")}}
        MenuItem {text:"Copy time";onTriggered:bridge.act("copy",JSON.stringify({text:root.contextCity.time+" "+root.contextCity.zone}))}
        MenuItem {text:"Copy full date/time";onTriggered:bridge.act("copy",JSON.stringify({text:root.contextCity.date+" "+root.contextCity.time+" "+root.contextCity.zone}))}
        MenuItem {text:"Copy ISO";onTriggered:bridge.act("copy",JSON.stringify({text:root.contextCity.iso}))}
        MenuItem {text:"Open Planner";onTriggered:bridge.goPage(6)}
        MenuSeparator {}
        MenuItem {text:"Move up in custom order";onTriggered:root.cityAction("up")}
        MenuItem {text:"Move down in custom order";onTriggered:root.cityAction("down")}
        MenuItem {text:"Remove";onTriggered:root.cityAction("remove")}
    }
}
