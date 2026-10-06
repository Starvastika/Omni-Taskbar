import "Theme.js" as Theme
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import TimeCenter 1.0
ColumnLayout {
    id:root;spacing:12;property var cal:bridge.calendarData;property string view:bridge.state.prefs.calendarView
    function selectDate(iso) {let d=new Date(iso+"T12:00:00");bridge.calendarGo(d.getFullYear(),d.getMonth()+1,iso)}
    function move(delta) {let d=new Date(cal.selected+"T12:00:00");if(view==="Year")d.setFullYear(d.getFullYear()+delta);else if(view==="Month"){d.setDate(1);d.setMonth(cal.month-1+delta);d.setFullYear(cal.year+(cal.month-1+delta<0?-1:cal.month-1+delta>11?1:0))}else d.setDate(d.getDate()+delta*(view==="Week"?7:1));selectDate(Qt.formatDate(d,"yyyy-MM-dd"))}
    function day(delta) {let d=new Date(cal.selected+"T12:00:00");d.setDate(d.getDate()+delta);selectDate(Qt.formatDate(d,"yyyy-MM-dd"))}
    function setView(value) {bridge.act("pref",JSON.stringify({key:"calendarView",value:value}))}
    Flow {Layout.fillWidth:true;spacing:7
        Repeater {model:["Month","Week","Day / Agenda","Year"];TCButton {required property string modelData;text:modelData;highlighted:root.view===modelData;onClicked:root.setView(modelData)}}
        TCButton {text:"‹";onClicked:root.move(-1)}
        TCButton {text:"Today";onClicked:bridge.calendarToday()}
        TCButton {text:"›";onClicked:root.move(1)}
        TCCombo {id:month;model:["January","February","March","April","May","June","July","August","September","October","November","December"];currentIndex:root.cal.month-1;onActivated:root.selectDate(root.cal.year+"-"+String(currentIndex+1).padStart(2,"0")+"-01")}
        TCCombo {id:year;width:100;model:Array.from({length:301},(_,i)=>String(1900+i));currentIndex:root.cal.year-1900;onActivated:root.selectDate(currentText+"-"+String(root.cal.month).padStart(2,"0")+"-01")}
        TextField {id:jump;width:135;placeholderText:"YYYY-MM-DD";onAccepted:root.selectDate(text)}
        TCButton {text:"Go";onClicked:root.selectDate(jump.text)}
    }
    TCSplitView {id:split;Layout.fillWidth:true;Layout.fillHeight:true
        onResizingChanged:if(!resizing&&width>0)bridge.act("layout",JSON.stringify({key:"calendarSplit",value:left.width/width}))
        Item {id:left;
            Label {anchors.right:parent.right;anchors.top:parent.top;z:10;visible:bridge.calendarBusy;text:"Updating…";color:Theme.muted}
            SplitView.preferredWidth:split.width*bridge.state.layout.calendarSplit;SplitView.minimumWidth:540
            Loader {anchors.fill:parent;asynchronous:true;visible:root.view==="Month";property bool visited:false;active:visited
                onVisibleChanged:if(visible)visited=true
                Component.onCompleted:if(visible)visited=true
                sourceComponent:Component {TCScrollView {id:monthScroll;anchors.fill:parent;contentWidth:availableWidth
                ColumnLayout {width:monthScroll.availableWidth;spacing:12
                    Label {text:root.cal.title;font.pixelSize:28;font.bold:true}
                    GridLayout {columns:7;Layout.fillWidth:true;columnSpacing:5;rowSpacing:5
                        Repeater {model:root.cal.headers;Label {required property string modelData;text:modelData;Layout.fillWidth:true;horizontalAlignment:Text.AlignHCenter;color:Theme.muted}}
                        Repeater {model:StableModel {source:root.cal.cells}
                            Rectangle {id:cell;required property var rowData;property var modelData:rowData;required property int index;Layout.fillWidth:true;Layout.preferredHeight:100;Layout.minimumWidth:62;radius:8;color:modelData.selected?"#4b4b4b":modelData.weekend&&bridge.state.prefs.weekends?"#2a2a2a":"#222222";border.color:modelData.today?Theme.focus:"#3f3f3f";border.width:modelData.today?2:1
                                Label {anchors.top:parent.top;anchors.left:parent.left;anchors.margins:10;text:cell.modelData.day;font.pixelSize:22;color:cell.modelData.current?"#ebebeb":"#7b7b7b"}
                                Label {anchors.right:parent.right;anchors.top:parent.top;anchors.margins:6;text:bridge.state.prefs.weeks&&cell.index%7===0?"W"+cell.modelData.week:"";font.pixelSize:9;color:"#a3a3a3"}
                                Label {anchors.left:parent.left;anchors.bottom:parent.bottom;anchors.margins:9;text:(cell.modelData.note?"▤ Note\n":"")+(cell.modelData.alarms?"◷ "+cell.modelData.alarms+" event(s)":"");font.pixelSize:10;color:"#bfbfbf"}
                                MouseArea {anchors.fill:parent;acceptedButtons:Qt.LeftButton|Qt.RightButton;onClicked:mouse=>{root.selectDate(cell.modelData.date);if(mouse.button===Qt.RightButton)dateMenu.popup()}}
                            }
                        }
                    }
                }
            }}
            }
            Loader {anchors.fill:parent;asynchronous:true;visible:root.view==="Week";property bool visited:false;active:visited
                onVisibleChanged:if(visible)visited=true
                Component.onCompleted:if(visible)visited=true
                sourceComponent:Component {TCScrollView {id:weekScroll;anchors.fill:parent;contentWidth:Math.max(availableWidth,1120);contentHeight:1580
                Item {width:weekScroll.contentWidth;height:1580
                    Row {x:55;y:0;spacing:2
                        Repeater {model:StableModel {source:root.cal.weekDays}
                            Column {required property var rowData;property var modelData:rowData;width:(weekScroll.contentWidth-65)/7;spacing:4
                                TCButton {width:parent.width;text:modelData.title;highlighted:modelData.today;onClicked:root.selectDate(modelData.date)}
                                Label {width:parent.width;text:modelData.noteText?"▤ "+modelData.noteText:"";elide:Text.ElideRight;color:"#afafaf";font.pixelSize:10}
                            }
                        }
                    }
                    Repeater {model:24
                        Item {required property int index;x:0;y:65+index*62;width:weekScroll.contentWidth;height:62
                            Label {text:String(index).padStart(2,"0")+":00";color:Theme.muted;font.pixelSize:10}
                            Rectangle {x:55;width:parent.width-55;height:1;color:"#4c4c4c"}
                        }
                    }
                    Row {x:55;y:65;spacing:2
                        Repeater {model:StableModel {source:root.cal.weekDays}
                            Item {id:column;required property var rowData;property var modelData:rowData;width:(weekScroll.contentWidth-65)/7;height:1488
                                Rectangle {anchors.fill:parent;color:column.modelData.weekend&&bridge.state.prefs.weekends?"#10222222":"transparent"}
                                Repeater {model:24;Rectangle {required property int index;y:index*62;width:parent.width;height:61;color:(bridge.state.prefs.workStart<bridge.state.prefs.workEnd?(index>=bridge.state.prefs.workStart&&index<bridge.state.prefs.workEnd):(index>=bridge.state.prefs.workStart||index<bridge.state.prefs.workEnd))?"#254d4d4d":"transparent"}}
                                Repeater {model:column.modelData.events;Rectangle {required property var modelData;y:modelData.minute/60*62;width:parent.width-5;height:Math.max(28,label.implicitHeight+8);radius:4;color:"#575757";z:2
                                    Label {id:label;anchors.fill:parent;anchors.margins:4;text:modelData.time+"\n"+modelData.label;wrapMode:Text.WordWrap;font.pixelSize:10}
                                }}
                                Rectangle {visible:column.modelData.today;y:bridge.home.localSeconds/3600*62;width:parent.width;height:2;color:"#bebebe";z:4}
                            }
                        }
                    }
                }
            }}
            }
            Loader {anchors.fill:parent;asynchronous:true;visible:root.view==="Day / Agenda";property bool visited:false;active:visited
                onVisibleChanged:if(visible)visited=true
                Component.onCompleted:if(visible)visited=true
                sourceComponent:Component {ListView {id:agendaList;anchors.fill:parent;clip:true;spacing:18;model:root.cal.agenda;boundsBehavior:Flickable.StopAtBounds
                header:ColumnLayout {width:agendaList.width;spacing:18
                    Label {text:root.cal.fullDate;font.pixelSize:30;wrapMode:Text.WordWrap;Layout.fillWidth:true}
                    Label {text:root.cal.detail;wrapMode:Text.WordWrap;Layout.fillWidth:true;color:Theme.secondary}
                    TCButton {text:"＋ Alarm for this date";onClicked:bridge.newAlarm(root.cal.selected)}
                    Label {text:root.cal.note||"No note for this day. Add one in Date details.";Layout.fillWidth:true;wrapMode:Text.WordWrap;color:Theme.secondary}
                    Label {visible:agendaList.count===0;text:"Your agenda is clear.";color:Theme.muted;font.pixelSize:20}
                    Item {height:12}
                }
                delegate:Card {required property var modelData;width:agendaList.width;height:110;title:modelData.kind.toUpperCase()
                    Label {anchors.fill:parent;text:modelData.time+"  ·  "+modelData.label+(modelData.notes?"\n"+modelData.notes:"");wrapMode:Text.WordWrap;font.pixelSize:19}
                }
                footer:Label {width:agendaList.width;topPadding:18;text:"HOME SOLAR\nSunrise "+root.cal.solar.sunrise+"    Sunset "+root.cal.solar.sunset+"\nDaylight "+root.cal.solar.dayLength;lineHeight:1.7;color:Theme.secondary;wrapMode:Text.WordWrap}
                ScrollBar.vertical:TCScrollBar {}
            }}
            }
            Loader {anchors.fill:parent;asynchronous:true;visible:root.view==="Year";property bool visited:false;active:visited
                onVisibleChanged:if(visible)visited=true
                Component.onCompleted:if(visible)visited=true
                sourceComponent:Component {TCScrollView {id:yearScroll;anchors.fill:parent;contentWidth:availableWidth
                GridLayout {width:yearScroll.availableWidth;columns:Math.max(2,Math.floor(width/270));columnSpacing:12;rowSpacing:12
                    Repeater {model:StableModel {source:root.cal.yearMonths}
                        Rectangle {id:mini;required property var rowData;property var modelData:rowData;Layout.fillWidth:true;Layout.preferredHeight:260;color:"#262626";radius:9;border.color:"#474747"
                            ColumnLayout {anchors.fill:parent;anchors.margins:12
                                TCButton {text:mini.modelData.title;Layout.fillWidth:true;onClicked:{root.selectDate(root.cal.year+"-"+String(mini.modelData.month).padStart(2,"0")+"-01");root.setView("Month")}}
                                GridLayout {columns:7;Layout.fillWidth:true;Layout.fillHeight:true
                                    Repeater {model:StableModel {source:mini.modelData.cells}Rectangle {required property var rowData;property var modelData:rowData;Layout.fillWidth:true;Layout.fillHeight:true;radius:3;color:modelData.selected?"#565656":"transparent";border.color:modelData.today?Theme.focus:"transparent"
                                        Label {anchors.centerIn:parent;text:modelData.day;color:modelData.current?"#dcdcdc":"#686868";font.pixelSize:11}
                                        MouseArea {anchors.fill:parent;onClicked:{root.selectDate(modelData.date);root.setView("Month")}}
                                    }}
                                }
                            }
                        }
                    }
                }
            }}
            }
        }
        Card {title:"DATE DETAILS";SplitView.minimumWidth:290;SplitView.fillWidth:true;CalendarDetails {anchors.fill:parent}}
    }
    TCMenu {id:dateMenu
        MenuItem {text:"Add / edit note";onTriggered:root.setView("Day / Agenda")}
        MenuItem {text:"New alarm on this date";onTriggered:bridge.newAlarm(root.cal.selected)}
        MenuItem {text:"Copy ISO date";onTriggered:bridge.act("copy",JSON.stringify({text:root.cal.selected}))}
        MenuItem {text:"Today";onTriggered:bridge.calendarToday()}
    }
    Shortcut {sequence:"PgUp";enabled:root.visible&&bridge.modalCount===0&&!bridge.textEditing;onActivated:if(!bridge.editing())root.move(-1)}
    Shortcut {sequence:"PgDown";enabled:root.visible&&bridge.modalCount===0&&!bridge.textEditing;onActivated:if(!bridge.editing())root.move(1)}
    Shortcut {sequence:"Home";enabled:root.visible&&bridge.modalCount===0&&!bridge.textEditing;onActivated:if(!bridge.editing())bridge.calendarToday()}
    Shortcut {sequence:"Left";enabled:root.visible&&bridge.modalCount===0&&!bridge.textEditing;onActivated:if(!bridge.editing())root.day(-1)}
    Shortcut {sequence:"Right";enabled:root.visible&&bridge.modalCount===0&&!bridge.textEditing;onActivated:if(!bridge.editing())root.day(1)}
}
