import QtQuick 2.15
import QtQuick.Window 2.15
import Ink.Benchmark 1.0

Window {
    id: window
    width: benchmarkFullscreen ? Screen.width : 900
    height: benchmarkFullscreen ? Screen.height : 1200
    visible: true
    visibility: benchmarkFullscreen ? Window.FullScreen : Window.Windowed
    color: "white"
    title: "Ink · standalone interaction benchmark"
    property int page: 0
    onPageChanged: {
        displayControl.setCanvasActive(page === 2)
        displayControl.requestCleanup()
    }
    property int quarterTurns: 0
    property real u: Math.max(0.65, surface.width / 900)
    Item {
    id: surface
    anchors.centerIn: parent
    width: window.quarterTurns % 2 ? window.height : window.width
    height: window.quarterTurns % 2 ? window.width : window.height
    rotation: window.quarterTurns * 90
    Column {
        id: header
        anchors.top: parent.top; anchors.left: parent.left; anchors.right: parent.right
        anchors.margins: 16 * window.u
        spacing: 12 * window.u
        Text { text: "INK · STANDALONE · NO APPLOAD / KOTLIN"; font.pixelSize: 20 * window.u }
        Row {
            width: parent.width; spacing: 8 * window.u
            Repeater {
                model: ["Scroll", "Drag", "Pen / canvas", "Rotate", "Exit"]
                Button {
                    required property string modelData
                    required property int index
                    width: (header.width - 32 * window.u) / 5
                    height: 54 * window.u
                    label: modelData
                    onClicked: {
                        if (index === 4) Qt.quit()
                        else if (index === 3) window.quarterTurns = (window.quarterTurns + 1) % 4
                        else window.page = index
                    }
                }
            }
        }
        Row {
            width: parent.width; spacing: 8 * window.u
            Button {
                width: (header.width - 8 * window.u) * 0.68
                height: 48 * window.u
                label: displayControl.status
                onClicked: if (displayControl.available) displayControl.enabled = !displayControl.enabled
            }
            Button {
                width: (header.width - 8 * window.u) * 0.32
                height: 48 * window.u
                label: "Clean display"
                onClicked: displayControl.cleanNow()
            }
        }
    }
    Item {
        id: body
        anchors.top: header.bottom; anchors.bottom: parent.bottom
        anchors.left: parent.left; anchors.right: parent.right
        anchors.margins: 16 * window.u
        ListView {
            id: list
            anchors.fill: parent; visible: window.page === 0
            clip: true; model: 200; reuseItems: true
            boundsBehavior: Flickable.StopAtBounds
            boundsMovement: Flickable.StopAtBounds
            pixelAligned: true
            onMovementStarted: displayControl.setMotionActive(true)
            onMovementEnded: displayControl.setMotionActive(false)
            onVisibleChanged: if (!visible) { cancelFlick(); displayControl.setMotionActive(false) }
            delegate: Item {
                required property int index
                width: list.width; height: 90 * window.u
                Text { anchors.verticalCenter: parent.verticalCenter; text: "Document " + (index + 1); font.pixelSize: 24 * window.u }
                Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: "black" }
            }
        }
        Rectangle {
            id: dragArea
            anchors.fill: parent; visible: window.page === 1
            color: "white"; border.color: "black"
            Text { x: 16; y: 16; text: "Drag the black square. No animation or IPC."; font.pixelSize: 20 * window.u }
            Rectangle {
                id: square
                x: 30; y: 100; width: 80 * window.u; height: width; color: "black"
                MouseArea {
                    anchors.fill: parent; drag.target: square
                    onPressed: displayControl.setMotionActive(true)
                    onReleased: displayControl.setMotionActive(false)
                    onCanceled: displayControl.setMotionActive(false)
                    drag.minimumX: 0; drag.maximumX: dragArea.width - square.width
                    drag.minimumY: 60 * window.u; drag.maximumY: dragArea.height - square.height
                }
            }
        }
        Item {
            anchors.fill: parent; visible: window.page === 2
            Column {
                id: penControls
                width: parent.width; spacing: 8 * window.u
                Text {
                    width: parent.width; wrapMode: Text.WordWrap; font.pixelSize: 18 * window.u
                    text: "Pen benchmark: compare sustained Pen mode against default. Pause after writing for software paint timing; this is not physical display latency."
                }
                Row {
                    width: parent.width; spacing: 8 * window.u
                    Button { width: (penControls.width - 8 * window.u) / 2; label: "Clear strokes"; onClicked: ink.clear() }
                    Button {
                        width: (penControls.width - 8 * window.u) / 2
                        label: ink.fingerEnabled ? "Finger / mouse: ON" : "Finger / mouse: OFF"
                        onClicked: ink.fingerEnabled = !ink.fingerEnabled
                    }
                }
                Button {
                    width: penControls.width
                    label: displayControl.canvasPenMode ? "Canvas: sustained Pen mode (tap to compare)" : "Canvas: default mode (tap to compare)"
                    onClicked: if (!ink.drawingActive) displayControl.canvasPenMode = !displayControl.canvasPenMode
                }
                Text {
                    width: parent.width; wrapMode: Text.WordWrap
                    text: ink.timingSummary
                    font.pixelSize: 16 * window.u
                }
                Text {
                    text: "Tablet events: " + ink.tabletEvents + " · strokes: " + ink.strokeCount
                    font.pixelSize: 18 * window.u
                }
            }
            Rectangle {
                anchors.top: penControls.bottom; anchors.topMargin: 12 * window.u
                anchors.bottom: parent.bottom; width: parent.width
                color: "white"; border.color: "black"; clip: true
                StrokeSurface {
                    id: ink; objectName: "strokeSurface"; anchors.fill: parent; anchors.margins: 2
                    onDrawingActiveChanged: displayControl.setInkActive(drawingActive)
                    onVisibleChanged: if (!visible) displayControl.setInkActive(false)
                }
            }
        }
    }
    }
}
