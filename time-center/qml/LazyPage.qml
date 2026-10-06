import QtQuick
Loader {
    property int pageIndex:0
    property int selectedPage:0
    property bool visited:pageIndex===0
    active:visited
    onSelectedPageChanged:if(selectedPage===pageIndex)visited=true
    Component.onCompleted:if(selectedPage===pageIndex)visited=true
}
