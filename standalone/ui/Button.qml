import QtQuick 2.15
Rectangle {
    id: control
    property string label: ""
    signal clicked()
    implicitHeight: 54
    color: "white"
    border.color: "black"
    border.width: area.pressed ? 3 : 1
    Text { anchors.centerIn: parent; text: control.label; font.pixelSize: 18 }
    MouseArea { id: area; anchors.fill: parent; onClicked: control.clicked() }
}
