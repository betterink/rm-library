import QtQuick 2.15

Rectangle {
    id: button
    property string label: ""
    property real scaleFactor: 1
    signal clicked()
    height: 64 * scaleFactor
    // Avoid repainting the whole button gray on every press/release.
    color: "white"
    border.color: enabled ? "black" : "#999999"
    border.width: area.pressed ? 4 : 2
    Text {
        anchors.centerIn: parent
        text: button.label
        font.pixelSize: 22 * button.scaleFactor
        color: button.enabled ? "black" : "#777777"
    }
    MouseArea {
        id: area
        anchors.fill: parent
        onClicked: button.clicked()
    }
}
