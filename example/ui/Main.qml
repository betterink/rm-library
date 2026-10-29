import QtQuick 2.15
import net.asivery.AppLoad 1.0

Rectangle {
    id: root
    width: 1620
    height: 2160
    color: "white"
    signal close()
    property real unit: Math.max(0.6, width / 900)
    property bool connected: false
    property bool waiting: false
    property bool stopping: false
    property string status: "Waiting for Kotlin backend…"
    property string backendInfo: "No response yet"
    property string counter: "0"

    // Closing the frontend intentionally keeps the backend alive. This lets us
    // verify AppLoad's existing background behaviour without concurrent terminate().
    function unloading() {
        startup.stop()
        replyTimeout.stop()
    }
    function request(type, contents) {
        waiting = true
        status = "Waiting for backend…"
        endpoint.sendMessage(type, contents)
        replyTimeout.restart()
    }
    Keys.onPressed: function(event) { event.accepted = true }
    Keys.onReleased: function(event) { event.accepted = true }
    focus: true

    AppLoad {
        id: endpoint
        applicationID: "ink.example.dev"
        onMessageReceived: function(type, contents) {
            if (type !== 101 && type !== 102 && type !== 103) return
            root.connected = true
            root.waiting = false
            startup.stop()
            replyTimeout.stop()
            if (type === 101) root.backendInfo = contents
            if (type === 102) root.counter = contents
            root.status = type === 103 ? "Backend stopping; AppLoad will close this view." : "Backend responded"
        }
    }
    Timer {
        id: startup
        interval: 500
        repeat: true
        running: true
        property int attempts: 0
        onTriggered: {
            attempts++
            endpoint.sendMessage(1, "hello")
            if (attempts >= 10) {
                stop()
                root.status = "No backend response. Check the xochitl journal, then retry."
            }
        }
    }
    Timer {
        id: replyTimeout
        interval: 5000
        onTriggered: {
            root.waiting = false
            root.status = "Response timed out. Check logs or close and relaunch."
        }
    }
    Flickable {
        anchors.fill: parent
        anchors.margins: 32 * root.unit
        contentHeight: content.height
        clip: true
        Column {
            id: content
            width: parent.width
            spacing: 18 * root.unit
            Text { text: "INK / APPLOAD CHECK"; font.pixelSize: 18 * root.unit }
            Text { text: "Hello, Paper Pro."; font.pixelSize: 42 * root.unit; font.bold: true }
            Text {
                width: parent.width
                text: "QML frontend + Kotlin/Native executable"
                font.pixelSize: 22 * root.unit
                wrapMode: Text.WordWrap
            }
            Rectangle { width: parent.width; height: 2; color: "black" }
            Text {
                width: parent.width
                text: root.status + "\n\n" + root.backendInfo
                font.pixelSize: 21 * root.unit
                wrapMode: Text.WrapAnywhere
            }
            Text { text: "Backend counter: " + root.counter; font.pixelSize: 32 * root.unit }
            ActionButton {
                width: parent.width; scaleFactor: root.unit
                label: "Ping Kotlin backend"
                enabled: !root.waiting && !root.stopping
                onClicked: root.request(1, "hello from QML — ✓")
            }
            ActionButton {
                width: parent.width; scaleFactor: root.unit
                label: "Increment counter"
                enabled: root.connected && !root.waiting && !root.stopping
                onClicked: root.request(2, "increment")
            }
            ActionButton {
                width: parent.width; scaleFactor: root.unit
                label: "Reset counter"
                enabled: root.connected && !root.waiting && !root.stopping
                onClicked: root.request(3, "reset")
            }
            ActionButton {
                width: parent.width; scaleFactor: root.unit
                label: "Close view · keep backend running"
                onClicked: root.close()
            }
            ActionButton {
                width: parent.width; scaleFactor: root.unit
                label: "Stop backend and close"
                enabled: root.connected && !root.waiting && !root.stopping
                onClicked: { root.stopping = true; root.request(9, "stop") }
            }
            Text {
                width: parent.width
                text: "Reopen after closing the view: the PID and counter should remain. Stop the backend to reset both. Counter state is in memory, not persisted to disk."
                font.pixelSize: 18 * root.unit
                wrapMode: Text.WordWrap
            }
        }
    }
}
