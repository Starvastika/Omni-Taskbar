import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
ApplicationWindow {
    id:window;objectName:"timeCenterWindow";visible:false;title:"Time Center";width:1440;height:900
    flags:Qt.Tool|Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint
    color:Theme.background;font.family:"Segoe UI Variable";font.pixelSize:12
    palette.window:Theme.background;palette.windowText:Theme.primary;palette.base:"#1a1a1a";palette.text:Theme.primary;palette.button:Theme.elevated;palette.buttonText:"#e9e9e9";palette.highlight:Theme.focus;palette.highlightedText:"#131313";palette.placeholderText:"#8f8f8f"
    property int page:0
    onPageChanged:bridge.setPage(page)
    function reveal() {closeAnimation.stop();content.opacity=0;content.y=12;window.show();window.raise();window.requestActivate();openAnimation.restart()}
    function conceal() {openAnimation.stop();closeAnimation.restart()}
    function quick(action) {
        if(action==="Today"){bridge.calendarToday();page=2}
        else if(action==="UTC Now")page=8
        else if(action==="Copy local time")bridge.act("copy",JSON.stringify({text:bridge.home.time+" "+bridge.home.zone}))
        else if(action==="Copy ISO")bridge.act("copy",JSON.stringify({text:bridge.now.iso}))
        else if(action==="5m timer"||action==="25m focus")bridge.act("timer",JSON.stringify({op:"add",seconds:action==="5m timer"?300:1500,label:action}))
        else if(action==="Stopwatch")page=4
        else if(action==="New Alarm")bridge.newAlarm(bridge.calendarData.selected)
        else if(action==="Planner")page=6
        else if(action==="Settings")page=7
        else if(action==="Set Home"&&bridge.selected.id)bridge.act("city",JSON.stringify({id:bridge.selected.id,op:"home"}))
        else if(action==="Reset Map"){page=0;homeLoader.item.resetMap()}
        else {let key=action==="Toggle day/night"?"mapDay":action==="Toggle seconds"?"seconds":"hour24";bridge.act("pref",JSON.stringify({key:key,value:!bridge.state.prefs[key]}))}
    }
    onClosing:close=>{close.accepted=false;bridge.act("hide","{}")}
    Shortcut {sequence:"Escape";enabled:bridge.modalCount===0;onActivated:bridge.act("hide","{}")}
    Shortcut {sequence:"Ctrl+K";enabled:bridge.modalCount===0;onActivated:{window.page=1;worldLoader.item.focusSearch()}}
    Connections {target:bridge;function onNavigate(page) {window.page=page}function onAlarmEditor(date) {globalAlarmEditor.create(date)}}
    AlarmEditor {id:globalAlarmEditor}
    ParallelAnimation {id:openAnimation
        NumberAnimation {target:content;property:"opacity";to:1;duration:bridge.state.prefs.reduceMotion?0:bridge.state.prefs.animationMs;easing.type:Easing.OutCubic}
        NumberAnimation {target:content;property:"y";to:0;duration:bridge.state.prefs.reduceMotion?0:bridge.state.prefs.animationMs;easing.type:Easing.OutCubic}
    }
    SequentialAnimation {id:closeAnimation;NumberAnimation {target:content;property:"opacity";to:0;duration:bridge.state.prefs.reduceMotion?0:150}ScriptAction {script:window.hide()}}
    Item {id:content;width:parent.width;height:parent.height
        ColumnLayout {anchors.fill:parent;anchors.margins:20;spacing:14
            RowLayout {Layout.fillWidth:true
                ColumnLayout {spacing:2;Label {text:"TIME CENTER";font.pixelSize:22;font.bold:true;font.letterSpacing:3}Label {text:"Your day, across the world";color:Theme.muted;font.pixelSize:11}}
                Item {Layout.fillWidth:true}
                Label {text:bridge.now.utc;color:Theme.muted;Layout.rightMargin:14}
                TCSwitch {text:"24-hour";checked:bridge.state.prefs.hour24;onToggled:bridge.act("pref",JSON.stringify({key:"hour24",value:checked}))}
                TCSwitch {text:"Seconds";checked:bridge.state.prefs.seconds;onToggled:bridge.act("pref",JSON.stringify({key:"seconds",value:checked}))}
                TCButton {text:"Close ×";onClicked:bridge.act("hide","{}")}
            }
            TCScrollView {Layout.fillWidth:true;Layout.preferredHeight:42;contentWidth:nav.implicitWidth;contentHeight:36;ScrollBar.vertical.policy:ScrollBar.AlwaysOff
                RowLayout {id:nav;spacing:7
                    Repeater {model:["Home","World","Calendar","Timers","Stopwatch","Alarms","Planner","Settings","Time Lab"];TCButton {required property string modelData;required property int index;text:modelData;highlighted:window.page===index;onClicked:window.page=index}}
                    Label {text:bridge.now.next;color:Theme.muted;Layout.leftMargin:18}
                }
            }
            Rectangle {Layout.fillWidth:true;Layout.preferredHeight:bridge.state.alerts.length?74:0;visible:bridge.state.alerts.length>0;color:"#444444";radius:8
                ListView {anchors.fill:parent;anchors.margins:8;orientation:ListView.Horizontal;spacing:16;model:bridge.state.alerts;clip:true
                    delegate:RowLayout {required property var modelData;height:58
                        Label {text:"● "+modelData.label;font.pixelSize:18}
                        TCCombo {id:snooze;model:["1m","5m","10m","15m","30m"];currentIndex:[1,5,10,15,30].indexOf(bridge.state.prefs.snoozeMinutes);implicitWidth:85}
                        TCButton {text:"Snooze";onClicked:bridge.act("alarm",JSON.stringify({op:"snooze",id:modelData.id,minutes:[1,5,10,15,30][snooze.currentIndex]}))}
                        TCButton {text:"Dismiss";onClicked:bridge.act("alarm",JSON.stringify({op:"dismiss",id:modelData.id}))}
                    }
                    ScrollBar.horizontal:TCScrollBar {}
                }
            }
            StackLayout {currentIndex:window.page;Layout.fillWidth:true;Layout.fillHeight:true
                LazyPage { id:homeLoader;pageIndex:0;selectedPage:window.page;sourceComponent:Component { PageFrame { function resetMap() {homeMap.resetView()}minimumWidth:1200;minimumHeight:1220
                    RowLayout {anchors.fill:parent;anchors.rightMargin:12;spacing:16
                        ColumnLayout {Layout.fillWidth:true;Layout.fillHeight:true;spacing:16
                            RowLayout {Layout.fillWidth:true;Layout.preferredHeight:280;spacing:16
                                Card {title:"HOME / LOCAL TIME";Layout.preferredWidth:340;Layout.fillHeight:true
                                    ColumnLayout {anchors.fill:parent;spacing:9
                                        Label {text:bridge.home.name;font.pixelSize:17;color:Theme.muted}
                                        Label {text:bridge.home.time;font.pixelSize:43;font.family:"Consolas"}
                                        Label {text:bridge.home.date;font.pixelSize:15}
                                        Label {text:bridge.home.zone+"\n"+bridge.home.offset+" · ISO week "+bridge.home.week+" · Day "+bridge.home.day;color:Theme.focus;font.pixelSize:11;lineHeight:1.6}
                                        Label {text:"↑ "+bridge.home.sunrise+"    ↓ "+bridge.home.sunset+"\nDaylight "+bridge.home.dayLength+"\nMoon "+(bridge.home.moonPhase===undefined?"—":bridge.home.moonPhase+" / 28");color:"#c0c0c0";font.pixelSize:11;wrapMode:Text.WordWrap;Layout.fillWidth:true;lineHeight:1.5}
                                        Item {Layout.fillHeight:true}
                                    }
                                }
                                Card {title:"WORLD SNAPSHOT";Layout.fillWidth:true;Layout.fillHeight:true;SelectedPane {anchors.fill:parent;compact:true}}
                            }
                            Card {title:"WORLD AT A GLANCE";Layout.fillWidth:true;Layout.preferredHeight:570;WorldMap {id:homeMap;anchors.fill:parent}}
                            RowLayout {Layout.fillWidth:true;Layout.fillHeight:true;Layout.minimumHeight:330;spacing:16
                                Card {title:"TIMERS · HH : MM : SS";Layout.fillWidth:true;Layout.fillHeight:true;TimerPane {anchors.fill:parent;compact:true}}
                                Card {title:"STOPWATCH";Layout.preferredWidth:360;Layout.fillHeight:true;StopwatchPane {anchors.fill:parent;compact:true}}
                            }
                        }
                        ColumnLayout {Layout.preferredWidth:410;Layout.minimumWidth:360;Layout.maximumWidth:410;Layout.fillHeight:true;spacing:16
                            Card {title:"WORLD CLOCKS";Layout.fillWidth:true;Layout.preferredHeight:570;CityList {anchors.fill:parent}}
                            Card {title:"CALENDAR";Layout.fillWidth:true;Layout.preferredHeight:400;CalendarPane {anchors.fill:parent;compact:true}}
                            Card {title:"QUICK TOOLS";Layout.fillWidth:true;Layout.fillHeight:true;Layout.minimumHeight:180
                                TCScrollView {id:quickScroll;anchors.fill:parent;contentWidth:availableWidth
                                    Flow {width:quickScroll.availableWidth;spacing:7
                                        Repeater {model:bridge.state.quickTools;TCButton {required property string modelData;text:modelData;onClicked:window.quick(modelData)}}
                                        TCButton {text:"Customize…";onClicked:window.page=7}
                                    }
                                }
                            }
                        }
                    }
                } } }
                LazyPage { id:worldLoader;pageIndex:1;selectedPage:window.page;sourceComponent:Component { PageFrame { function focusSearch() {worldCities.focusSearch()}minimumWidth:1080;minimumHeight:950
                    TCSplitView {id:worldSplit;anchors.fill:parent
                        onResizingChanged:if(!resizing&&width>0)bridge.act("layout",JSON.stringify({key:"worldSplit",value:worldLeft.width/width}))
                        TCSplitView {id:worldLeft;orientation:Qt.Vertical;SplitView.preferredWidth:worldSplit.width*bridge.state.layout.worldSplit;SplitView.minimumWidth:620
                            onResizingChanged:if(!resizing&&height>0)bridge.act("layout",JSON.stringify({key:"worldVertical",value:mapCard.height/height}))
                            Card {id:mapCard;title:"WORLD / DAY & NIGHT";SplitView.preferredHeight:worldLeft.height*bridge.state.layout.worldVertical;SplitView.minimumHeight:330;WorldMap {anchors.fill:parent}}
                            Card {title:"PLACES";SplitView.fillHeight:true;SplitView.minimumHeight:420;CityList {id:worldCities;anchors.fill:parent}}
                        }
                        Card {title:"SELECTED CITY";SplitView.fillWidth:true;SplitView.minimumWidth:330;SelectedPane {anchors.fill:parent}}
                    }
                } } }
                LazyPage { id:pageLoader2;pageIndex:2;selectedPage:window.page;sourceComponent:Component { PageFrame {minimumWidth:1000;minimumHeight:680;CalendarPage {anchors.fill:parent}} } }
                LazyPage { id:pageLoader3;pageIndex:3;selectedPage:window.page;sourceComponent:Component { PageFrame {minimumWidth:1020;minimumHeight:620;Card {anchors.fill:parent;title:"MULTI-TIMERS";TimerPane {anchors.fill:parent}}} } }
                LazyPage { id:pageLoader4;pageIndex:4;selectedPage:window.page;sourceComponent:Component { PageFrame {minimumWidth:900;minimumHeight:620;Card {anchors.fill:parent;title:"STOPWATCH";StopwatchPane {anchors.fill:parent}}} } }
                LazyPage { id:pageLoader5;pageIndex:5;selectedPage:window.page;sourceComponent:Component { PageFrame {minimumWidth:950;minimumHeight:600;Card {anchors.fill:parent;title:"ALARMS";AlarmPane {anchors.fill:parent}}} } }
                LazyPage { id:pageLoader6;pageIndex:6;selectedPage:window.page;sourceComponent:Component { PageFrame {minimumWidth:1020;minimumHeight:650;Card {anchors.fill:parent;title:"MEETING PLANNER";PlannerPane {anchors.fill:parent}}} } }
                LazyPage { id:pageLoader7;pageIndex:7;selectedPage:window.page;sourceComponent:Component { PageFrame {minimumWidth:850;minimumHeight:600;SettingsPane {anchors.fill:parent}} } }
                LazyPage { id:pageLoader8;pageIndex:8;selectedPage:window.page;sourceComponent:Component { PageFrame {minimumWidth:850;minimumHeight:600;Card {anchors.fill:parent;title:"PRECISE UTILITIES";TimeLab {anchors.fill:parent}}} } }
            }
            Label {text:bridge.status;Layout.fillWidth:true;elide:Text.ElideRight;color:Theme.muted;font.pixelSize:11}
        }
    }
}
