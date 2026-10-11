import QtQuick
import "Messages.js" as Messages

// Bottom strip: the time in a box, then the messages scrolling past.
Rectangle {
    id: strip

    required property var colors
    required property url bulletsUrl
    property var messages: []

    // The board is republished every few seconds; as a string, the ticker only restarts when the text changes.
    readonly property string messageText: messages.join("
")

    color: colors.statusBackground

    Item {
        id: ticker
        anchors.left: timeBox.right
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        clip: true

        Row {
            id: scrolling
            anchors.verticalCenter: parent.verticalCenter

            // Pieces of text and bullets, with a gap after each message
            Repeater {
                model: strip.messageText.split("
").filter(m => m !== "")
                    .reduce((all, m) => all.concat(Messages.pieces(m), [{ text: "", bullet: "" }]), [])

                Row {
                    required property var modelData

                    Text {
                        visible: modelData.text !== ""
                        text: modelData.text
                        font.family: "Roboto"
                        font.pixelSize: strip.height * 0.6
                        color: strip.colors.statusText
                    }

                    Image {
                        visible: modelData.bullet !== ""
                        anchors.verticalCenter: parent.verticalCenter
                        width: strip.height * 0.62
                        height: width
                        sourceSize: Qt.size(width, height)
                        source: visible ? strip.bulletsUrl + "NYCS-bull-trans-" + modelData.bullet + ".svg" : ""
                    }

                    Item {
                        visible: modelData.text === "" && modelData.bullet === ""
                        width: strip.height * 3
                        height: 1
                    }
                }
            }

            // Scroll in from the right and out to the left, at a steady speed whatever the length.
            NumberAnimation on x {
                id: scroll
                from: ticker.width
                to: -scrolling.width
                duration: Math.max(1, (ticker.width + scrolling.width) / (strip.height * 4) * 1000)
                loops: Animation.Infinite
                running: scrolling.width > 0 && ticker.width > 0
            }
        }
    }

    Rectangle {
        id: timeBox
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        width: time.implicitWidth + strip.height * 0.8
        color: strip.colors.statusAccent

        Text {
            id: time
            anchors.centerIn: parent
            font.family: "Roboto"
            font.pixelSize: strip.height * 0.6
            color: strip.colors.statusText

            function update() { text = Qt.formatTime(new Date(), "h:mm AP") }
            Component.onCompleted: update()
            Timer { interval: 1000; running: true; repeat: true; onTriggered: time.update() }
        }
    }
}
