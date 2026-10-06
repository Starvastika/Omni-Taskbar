import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
TCScrollView {
    id:root;property bool compact:false;property var city:bridge.selected;contentWidth:availableWidth
    ColumnLayout {width:root.availableWidth;spacing:root.compact?6:14
        Label {text:root.city.name||"Choose a city";font.pixelSize:root.compact?24:30;font.bold:true;wrapMode:Text.WordWrap;Layout.fillWidth:true}
        Label {text:root.city.region||"Windows timezone · no inferred location";color:Theme.muted;font.pixelSize:11;wrapMode:Text.WordWrap;Layout.fillWidth:true}
        Label {text:root.city.time||"";font.pixelSize:root.compact?32:42;font.family:"Consolas"}
        Label {text:(root.city.date||"")+"\n"+(root.city.abbreviation||"")+" · "+(root.city.offset||"")+" · "+(root.city.difference||"")+(root.city.dst?" · DST":"");color:"#c0c0c0";lineHeight:1.5;wrapMode:Text.WordWrap;Layout.fillWidth:true}
        Flow {Layout.fillWidth:true;spacing:5
            TCButton {text:root.city.id?(root.city.favorite?"★ Favorite":"☆ Favorite"):"Save location";onClicked:root.city.id?bridge.act("city",JSON.stringify({id:root.city.id,op:"favorite"})):bridge.act("addCity",JSON.stringify(root.city))}
            TCButton {text:"Set Home";enabled:!!root.city.id;onClicked:bridge.act("city",JSON.stringify({id:root.city.id,op:"home"}))}
            TCButton {text:"Focus map";onClicked:bridge.act("focus","{}")}
            TCButton {text:"More ▾";onClicked:actions.popup()}
        }
        Disclosure {visible:!root.compact;title:"TIME";Layout.fillWidth:true
            Label {text:(root.city.zone||"")+"\n"+(root.city.relation||"")+" relative to Home\n"+(root.city.solarState||"");color:"#bcbcbc";wrapMode:Text.WordWrap;Layout.fillWidth:true;lineHeight:1.6}
        }
        Disclosure {visible:!root.compact;title:"SOLAR";Layout.fillWidth:true
            Label {text:"Sunrise   "+(root.city.sunrise||"Location not set")+"\nSunset   "+(root.city.sunset||"—")+"\nDaylight   "+(root.city.dayLength||"—")+"\nNext   "+(root.city.nextSolar||"—")+"\nSolar noon   "+(root.city.noon||"—")+"\nSolar midnight   "+(root.city.midnight||"—")+"\nCivil twilight   "+(root.city.civilDawn||"—")+" / "+(root.city.civilDusk||"—")+"\nNautical   "+(root.city.nauticalDawn||"—")+" / "+(root.city.nauticalDusk||"—")+"\nAstronomical   "+(root.city.astronomicalDawn||"—")+" / "+(root.city.astronomicalDusk||"—")+"\nMoon phase   "+(root.city.moonPhase!==undefined?root.city.moonPhase+" / 28":"—");lineHeight:1.65;color:"#bbbbbb";wrapMode:Text.WordWrap;Layout.fillWidth:true}
        }
        Disclosure {visible:!root.compact;title:"COORDINATES";Layout.fillWidth:true
            Label {text:root.city.lat!==undefined&&root.city.lat!==null?root.city.lat.toFixed(5)+", "+root.city.lon.toFixed(5):"No coordinates for this timezone";color:"#bbbbbb"}
            TCButton {text:"Copy coordinates";enabled:root.city.lat!==undefined&&root.city.lat!==null;onClicked:bridge.act("copy",JSON.stringify({text:root.city.lat+", "+root.city.lon}))}
        }
    }
    TCMenu {id:actions
        MenuItem {text:"Copy time";onTriggered:bridge.act("copy",JSON.stringify({text:root.city.name+" · "+root.city.time+" "+root.city.zone}))}
        MenuItem {text:"Copy ISO date/time";onTriggered:bridge.act("copy",JSON.stringify({text:root.city.iso}))}
        MenuItem {text:"Open Planner";onTriggered:bridge.goPage(6)}
        MenuItem {text:"Remove saved city";enabled:!!root.city.id;onTriggered:bridge.act("city",JSON.stringify({id:root.city.id,op:"remove"}))}
        MenuItem {text:"Clear temporary inspection";enabled:!root.city.id;onTriggered:bridge.act("clearInspection","{}")}
    }
}
