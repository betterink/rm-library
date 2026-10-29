import QtQuick 2.15

Rectangle {
    id: button
    property string label: ""
    property real scaleFactor: 1
    signal clicked()
    height: 64 * scaleFactor
    color: area.pressed ? "#dddddd" : "white"
    border.color: enabled ? "black" : "#999999"
    border.width: 2
    opacity: enabled ? 1 : 0.45
    Text {
        anchors.centerIn: parent
        text: button.label
        font.pixelSize: 22 * button.scaleFactor
        color: "black"
    }
    MouseArea {
        id: area
        anchors.fill: parent
        onClicked: button.clicked()
    }
}
