import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
TCScrollView {
    id:scroll;contentWidth:availableWidth
    ColumnLayout {width:scroll.availableWidth;spacing:16
        Label {text:"Make Time Center yours";font.pixelSize:28}
        Repeater {model:[
            {title:"Appearance & precision",items:[['hour24','24-hour clock'],['seconds','Show seconds'],['precision','Stopwatch precision',['Seconds','Tenths','Hundredths','Milliseconds'],[0,1,2,3]],['dateFormat','Date format',['Long','ISO']],['density','City density',['Detailed','Compact']],['reduceMotion','Reduce motion'],['animationMs','Open animation',['180 ms','210 ms','240 ms'],[180,210,240]]]},
            {title:"Map",items:[['mapDay','Day / night'],['mapTwilight','Twilight bands'],['mapTerminator','Solar terminator'],['mapGrid','Graticule'],['mapLabels','Pin labels'],['mapLegend','Marker legend'],['mapFollow','Follow selected city'],['mapSun','Labelled subsolar point'],['mapCoordinates','Cursor coordinates'],['mapDefaultZoom','Reset zoom',['1×','2×','3×'],[1,2,3]]]},
            {title:"Calendar",items:[['calendarView','Default / current view',['Month','Week','Day / Agenda','Year']],['weeks','ISO week numbers'],['weekends','Weekend shading'],['weekStart','Week starts',['Monday','Sunday'],[0,6]]]},
            {title:"Timers & alarms",items:[['sound','Play alert sound'],['alertSound','Default sound',['SystemExclamation','SystemAsterisk','SystemHand','Silent']],['snoozeMinutes','Default snooze',['1 minute','5 minutes','10 minutes','15 minutes','30 minutes'],[1,5,10,15,30]],['completion','Completion behavior',['Show panel','Alert on next open']],['timerDetailed','Detailed timer cards']]},
            {title:"World clocks",items:[['citySort','Default sort',['Custom','Name','UTC offset','Local time']],['cityFilter','Filter',['All','Favorites','Day','Night','Same date']],['citySolar','Sunrise / sunset mini details']]}
        ]
            Card {id:section;required property var modelData;title:modelData.title.toUpperCase();Layout.fillWidth:true;Layout.preferredHeight:body.implicitHeight+60
                ColumnLayout {id:body;anchors.left:parent.left;anchors.right:parent.right;spacing:10
                    Repeater {model:section.modelData.items
                        RowLayout {id:setting;required property var modelData;Layout.fillWidth:true;spacing:18
                            Label {text:setting.modelData[1];Layout.fillWidth:true;color:"#d3d3d3"}
                            TCSwitch {visible:setting.modelData.length===2;checked:!!bridge.state.prefs[setting.modelData[0]];onToggled:bridge.act("pref",JSON.stringify({key:setting.modelData[0],value:checked}))}
                            TCCombo {visible:setting.modelData.length>2;Layout.preferredWidth:240;model:setting.modelData[2]||[];currentIndex:(setting.modelData[3]||setting.modelData[2]||[]).indexOf(bridge.state.prefs[setting.modelData[0]]);onActivated:bridge.act("pref",JSON.stringify({key:setting.modelData[0],value:(setting.modelData[3]||setting.modelData[2])[currentIndex]}))}
                        }
                    }
                }
            }
        }
        Card {title:"QUICK TOOLS";Layout.fillWidth:true;Layout.preferredHeight:quick.implicitHeight+70
            Flow {id:quick;anchors.left:parent.left;anchors.right:parent.right;spacing:6
                Repeater {model:["Today","UTC Now","Copy local time","Copy ISO","5m timer","25m focus","Stopwatch","New Alarm","Planner","Set Home","Reset Map","Toggle day/night","Toggle seconds","12/24h","Settings"]
                    CheckBox {required property string modelData;text:modelData;checked:bridge.state.quickTools.indexOf(modelData)>=0;onToggled:{let a=bridge.state.quickTools.slice();if(checked&&a.indexOf(modelData)<0)a.push(modelData);if(!checked)a=a.filter(x=>x!==modelData);bridge.act("quickTools",JSON.stringify({items:a}))}}
                }
            }
        }
        Label {text:"All preferences save locally. Holiday overlays and external calendar accounts are not enabled.\nMap twilight is a sampled solar-elevation band; detailed street tiles and 3D globe remain outside this pass.";color:Theme.muted;wrapMode:Text.WordWrap;Layout.fillWidth:true}
    }
}
