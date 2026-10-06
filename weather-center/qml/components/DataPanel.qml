import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../charts"
WPage {
 id:root
 property string title:"";property string explanation:"";property var metricKeys:[];property var chartKeys:[];property var dataRows:null;property var dataModel:dataRows===null?weather.hourlyModel:dataRows;property var dataSeries:weather.series;property var dataMetrics:weather.metrics
 property var freshness:weather.summary
 default property alias extra:extras.data
 Label {text:root.title;font.pixelSize:24;font.bold:true}
 Label {text:root.explanation;wrapMode:Text.Wrap;Layout.fillWidth:true;color:"#aaa";lineHeight:1.4}
 Label {text:(root.freshness.stale?"STALE · ":"")+root.freshness.age+" · "+root.freshness.location+(root.freshness.error?" · "+root.freshness.error:"");color:"#bbb";wrapMode:Text.Wrap;Layout.fillWidth:true}
 MetricGrid {Layout.fillWidth:true;items:root.dataMetrics.filter(m=>root.metricKeys.indexOf(m.key)>=0)}
 WCard {title:"FORECAST PROFILE · DRAG / ZOOM / INSPECT / EXPORT";Layout.fillWidth:true;Layout.preferredHeight:root.chartKeys.length>4?620:510
  Meteogram {anchors.fill:parent;dataset:root.dataModel;series:root.dataSeries;keys:root.chartKeys}
 }
 ColumnLayout {id:extras;Layout.fillWidth:true;spacing:12}
}
