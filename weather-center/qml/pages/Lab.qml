import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"
WPage {
 id:root;property var calculation:weather.lab||{};property var units:["°C","°F","m/s","km/h","mph","knots","hPa","kPa","mmHg","inHg","km","mi","mm/h","in/h","mm","in"]
 property string tool:"Dew point"
 Label {text:"Weather Lab";font.pixelSize:24;font.bold:true}
 Label {text:"Local calculations are labeled and use explicit inputs. They do not replace provider data, measurements or official alerts.";color:"#aaa";wrapMode:Text.Wrap;Layout.fillWidth:true}
 RowLayout {WInput {id:coords;Layout.preferredWidth:340;placeholderText:"Coordinates · latitude, longitude";onAccepted:weather.search(text)}WButton {text:"Find / inspect";onClicked:{weather.search(coords.text);weather.act("page",JSON.stringify({value:11}))}}}
 WCombo {Layout.preferredWidth:280;model:["Dew point","Relative humidity","Wind chill","Heat index","Humidex","Snow-water equivalent","Beaufort","Timestamp","Unit conversion"];onActivated:root.tool=currentText}
 Label {text:({"Dew point":"A: air temperature °C   B: relative humidity %","Relative humidity":"A: air temperature °C   B: dew point °C","Wind chill":"A: air temperature °C   B: wind km/h","Heat index":"A: air temperature °C   B: relative humidity %","Humidex":"A: air temperature °C   B: dew point °C","Snow-water equivalent":"A: snow depth cm   B: snow:water ratio (you supply the assumption)","Beaufort":"A: wind m/s","Timestamp":"A: Unix seconds (UTC epoch)","Unit conversion":"A: value; select compatible source/target units"})[root.tool];color:"#ccc";wrapMode:Text.Wrap;Layout.fillWidth:true}
 RowLayout {WInput {id:a;text:"20";placeholderText:"A";validator:DoubleValidator {}}WInput {id:b;visible:root.tool!=="Beaufort"&&root.tool!=="Timestamp"&&root.tool!=="Unit conversion";text:"60";placeholderText:"B";validator:DoubleValidator {}}WCombo {id:from;visible:root.tool==="Unit conversion";model:root.units}WCombo {id:to;visible:from.visible;model:root.units;currentIndex:1}WButton {text:"Calculate";onClicked:weather.act("calculate",JSON.stringify({tool:root.tool,a:a.text,b:b.text,from:from.currentText,to:to.currentText}))}}
 Label {text:root.calculation.result||"Choose a tool and calculate";font.pixelSize:27;wrapMode:Text.Wrap;Layout.fillWidth:true}
 Label {text:"CALCULATED · "+(root.calculation.formula||"Formula and applicability will appear here.");color:"#aaa";wrapMode:Text.Wrap;Layout.fillWidth:true}
 RowLayout {WButton {text:"Formula source";enabled:!!root.calculation.source;onClicked:weather.act("open",JSON.stringify({url:root.calculation.source}))}WButton {text:"Copy calculation";onClicked:weather.act("copy",JSON.stringify({text:JSON.stringify(root.calculation,null,2)}))}WButton {text:"Copy raw weather JSON";onClicked:weather.act("rawCopy","{}")}}
 Label {text:"Provider metadata / raw field inspector";font.pixelSize:22}
 TextArea {text:JSON.stringify(weather.metadata,null,2);readOnly:true;selectByMouse:true;wrapMode:TextEdit.Wrap;Layout.fillWidth:true;color:"#ccc";background:Rectangle {color:"#222";radius:8}}
 Label {text:"Current normalized fields · raw provider unit preserved";font.bold:true}
 Repeater {model:weather.metrics;Label {required property var modelData;text:modelData.key+" = "+modelData.value+"  |  raw: "+modelData.rawValue+" "+modelData.rawUnit+"  |  "+modelData.source;color:"#aaa";wrapMode:Text.Wrap;Layout.fillWidth:true}}
}
