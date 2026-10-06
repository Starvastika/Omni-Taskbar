import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import TimeCenter 1.0
ColumnLayout {
    id:root;property var ids:bridge.state.plannerSettings.ids || null;property var plan:bridge.plan;property real referenceEpoch:bridge.planEpoch;spacing:12
    StableModel {id:plannerRows;source:root.plan.rows}
    function convert() {bridge.act("planner",JSON.stringify({date:date.text,time:clock.text,zone:zone.currentText,cities:ids}))}
    function epoch(stamp) {bridge.act("planEpoch",JSON.stringify({epoch:stamp,cities:ids}))}
    function nudge(sign) {epoch(root.referenceEpoch+sign*bridge.state.prefs.plannerStep*60)}
    Flow {Layout.fillWidth:true;spacing:7
        TextField {id:date;width:130;text:bridge.home.iso.substring(0,10);placeholderText:"YYYY-MM-DD"}
        TextField {id:clock;width:95;text:"15:30";placeholderText:"HH:MM"}
        TCCombo {id:zone;width:230;model:[bridge.home.zone].concat(bridge.cities.map(c=>c.zone).filter((v,i,a)=>a.indexOf(v)===i&&v!==bridge.home.zone))}
        TCButton {text:"Convert";highlighted:true;onClicked:root.convert()}
        TCButton {text:"Copy table";onClicked:bridge.act("copy",JSON.stringify({text:"Place\tLocal date/time\tTimezone\n"+root.plan.rows.map(r=>r.name+"\t"+r.time+"\t"+r.zone).join("\n")}))}
        TCButton {text:"Cities & work hours ▾";onClicked:picker.open()}
        TCCombo {id:overlapDuration;width:110;model:["30m","1h","2h"]}
        TCButton {text:"Find next overlap";onClicked:bridge.act("findOverlap",JSON.stringify({minutes:[30,60,120][overlapDuration.currentIndex]}))}
    }
    RowLayout {Layout.fillWidth:true
        Label {text:bridge.plannerBusy?"Updating planner…":root.plan.reference;color:Theme.focus;font.pixelSize:20;Layout.fillWidth:true}
        Label {text:"Nudge";color:Theme.muted}
        TCButton {text:"‹";onClicked:root.nudge(-1)}
        TCCombo {model:["15m","30m","1h"];currentIndex:[15,30,60].indexOf(bridge.state.prefs.plannerStep);onActivated:bridge.act("pref",JSON.stringify({key:"plannerStep",value:[15,30,60][currentIndex]}));width:90}
        TCButton {text:"›";onClicked:root.nudge(1)}
        Label {text:"Timeline zoom";color:Theme.muted}
        Slider {from:50;to:160;value:bridge.state.prefs.plannerZoom;Layout.preferredWidth:160;onMoved:zoomSave.restart();id:zoom}
        Timer {id:zoomSave;interval:350;onTriggered:bridge.act("pref",JSON.stringify({key:"plannerZoom",value:Math.round(zoom.value)}))}
    }
    Slider {Layout.fillWidth:true;from:0;to:24-bridge.state.prefs.plannerStep/60;stepSize:bridge.state.prefs.plannerStep/60;value:(root.referenceEpoch%86400)/3600;onMoved:root.epoch(Math.floor(root.referenceEpoch/86400)*86400+value*3600)}
    Label {text:"Light gray: shared work hours · gray: work · dark: night · outlined: local midnight · thick line: selected time · white: now";color:Theme.muted;wrapMode:Text.WordWrap;Layout.fillWidth:true}
    TCScrollView {id:timeline;Layout.fillWidth:true;Layout.fillHeight:true;contentWidth:Math.max(availableWidth,24*bridge.state.prefs.plannerZoom);contentHeight:rows.implicitHeight
        ColumnLayout {id:rows;width:timeline.contentWidth;spacing:18
            Repeater {model:plannerRows
                ColumnLayout {id:row;required property var rowData;property var modelData:rowData;Layout.fillWidth:true;spacing:8
                    Label {text:row.modelData.name+" · "+row.modelData.time+" · "+row.modelData.zone;font.pixelSize:17}
                    Item {Layout.fillWidth:true;Layout.preferredHeight:80
                        Row {anchors.fill:parent;spacing:2
                            Repeater {model:StableModel {source:row.modelData.cells}
                                Rectangle {required property var rowData;property var modelData:rowData;required property int index;width:(timeline.contentWidth-46)/24;height:80;radius:5;color:root.plan.overlap[index]?"#565656":modelData.working?"#3f3f3f":modelData.day===null?"#2f2f2f":modelData.day?"#343434":"#1a1a1a";border.color:modelData.hour==="00:00"?"#b3b3b3":"transparent"
                                    Column {anchors.centerIn:parent;spacing:7
                                        Label {text:bridge.state.prefs.hour24?modelData.hour:(Number(modelData.hour.substring(0,2))%12||12)+modelData.hour.substring(2)+(Number(modelData.hour.substring(0,2))>=12?"p":"a");font.pixelSize:12}
                                        Label {text:modelData.date;font.pixelSize:10;color:"#b0b0b0"}
                                    }
                                    MouseArea {anchors.fill:parent;onClicked:root.epoch(modelData.epoch)}
                                }
                            }
                        }
                        Rectangle {x:((root.referenceEpoch%86400)/86400)*parent.width;width:2;height:parent.height;color:"#c3c3c3"}
                        Rectangle {visible:Math.floor(bridge.now.unix/86400)===Math.floor(root.referenceEpoch/86400);x:((bridge.now.unix%86400)/86400)*parent.width;width:1;height:parent.height;color:"#ffffff"}
                    }
                }
            }
        }
    }
    Popup {id:picker;parent:Overlay.overlay;anchors.centerIn:parent;width:660;height:Math.min(690,parent.height-70);padding:20;modal:true;closePolicy:Popup.CloseOnEscape|Popup.CloseOnPressOutside;onOpened:bridge.modal(1);onClosed:bridge.modal(-1);background:Rectangle {color:Theme.surface;radius:12;border.color:"#5b5b5b"}
        contentItem:TCScrollView {id:pickerScroll;contentWidth:availableWidth
            ColumnLayout {width:pickerScroll.availableWidth;spacing:14
                Label {text:"PLACES & WORK HOURS";font.pixelSize:21}
                TextField {id:filter;Layout.fillWidth:true;placeholderText:"Filter saved places…"}
                Flow {Layout.fillWidth:true;spacing:4
                    Repeater {model:bridge.cities.filter(c=>c.name.toLowerCase().includes(filter.text.toLowerCase()));CheckBox {required property var modelData;text:modelData.name;checked:root.ids===null||root.ids.indexOf(modelData.id)>=0;onToggled:{let a=root.ids===null?bridge.cities.map(c=>c.id):root.ids.slice();if(checked&&a.indexOf(modelData.id)<0)a.push(modelData.id);if(!checked)a=a.filter(x=>x!==modelData.id);root.ids=a;root.convert()}}}
                }
                Flow {Layout.fillWidth:true;spacing:6
                    TCButton {text:"Select all";onClicked:{root.ids=null;root.convert()}}
                    TextField {id:groupName;width:180;placeholderText:"Group name"}
                    TCButton {text:"Save group";enabled:groupName.text.trim().length>0;onClicked:bridge.act("plannerGroup",JSON.stringify({op:"save",name:groupName.text,ids:root.ids}))}
                }
                RowLayout {TCCombo {id:groups;Layout.fillWidth:true;model:Object.keys(bridge.state.plannerSettings.groups)}TCButton {text:"Load";enabled:groups.count>0;onClicked:{root.ids=bridge.state.plannerSettings.groups[groups.currentText] || null;root.convert()}}TCButton {text:"Remove";enabled:groups.count>0;onClicked:bridge.act("plannerGroup",JSON.stringify({op:"delete",name:groups.currentText}))}}
                Label {text:"Default working hours (every day)";color:"#b3b3b3"}
                RowLayout {TCSpinBox {from:0;to:23;value:bridge.state.prefs.workStart;onValueModified:bridge.act("pref",JSON.stringify({key:"workStart",value:value}))}Label {text:"to"}TCSpinBox {from:0;to:23;value:bridge.state.prefs.workEnd;onValueModified:bridge.act("pref",JSON.stringify({key:"workEnd",value:value}))}}
                Label {text:"Override for a saved city";color:"#b3b3b3"}
                TCCombo {id:workCity;Layout.fillWidth:true;model:bridge.cities.map(c=>c.name)}
                RowLayout {TCSpinBox {id:workStart;from:0;to:23;value:9}Label {text:"to"}TCSpinBox {id:workEnd;from:0;to:23;value:17}TCButton {text:"Apply override";enabled:workCity.count>0;onClicked:bridge.act("workHours",JSON.stringify({id:bridge.cities[workCity.currentIndex].id,start:workStart.value,end:workEnd.value}))}TCButton {text:"Reset";enabled:workCity.count>0;onClicked:bridge.act("workHours",JSON.stringify({id:bridge.cities[workCity.currentIndex].id,reset:true}))}}
                Label {Layout.fillWidth:true;wrapMode:Text.WordWrap;color:Theme.muted;text:JSON.stringify(bridge.state.plannerSettings.workHours)==="{}"?"No city overrides":bridge.cities.filter(c=>bridge.state.plannerSettings.workHours[c.id]).map(c=>c.name+": "+bridge.state.plannerSettings.workHours[c.id].start+"–"+bridge.state.plannerSettings.workHours[c.id].end).join(" · ")}
                TCButton {text:"Done";onClicked:picker.close()}
            }
        }
    }
    Shortcut {sequence:"Left";enabled:root.visible&&bridge.modalCount===0&&!bridge.textEditing;onActivated:if(!bridge.editing())root.nudge(-1)}
    Shortcut {sequence:"Right";enabled:root.visible&&bridge.modalCount===0&&!bridge.textEditing;onActivated:if(!bridge.editing())root.nudge(1)}
}
