import QtQuick

// Bottom strip: the time in a box, then a message.
Rectangle {
    id: strip

    required property var theme
    property string message

    color: theme.statusBackground

    Rectangle {
        id: timeBox
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        width: time.implicitWidth + strip.height * 0.8
        color: strip.theme.statusAccent

        Text {
            id: time
            anchors.centerIn: parent
            font.family: "Roboto"
            font.pixelSize: strip.height * 0.6
            color: strip.theme.statusText

            function update() { text = Qt.formatTime(new Date(), "h:mm AP") }
            Component.onCompleted: update()
            Timer { interval: 1000; running: true; repeat: true; onTriggered: time.update() }
        }
    }

    Text {
        anchors.left: timeBox.right
        anchors.leftMargin: strip.height * 0.3
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        text: strip.message
        elide: Text.ElideRight
        font.family: "Roboto"
        font.pixelSize: strip.height * 0.6
        color: strip.theme.statusText
    }
}
