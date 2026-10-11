import QtQuick
import "Messages.js" as Messages
import "Styles.js" as Styles

// The newer clocks: a numbered card per train on a black screen. Service alerts
// take turns with the trains on the last line. The MTA's design is 1920x480
// with two lines.
Rectangle {
    id: root

    required property var board
    required property url bulletsUrl
    required property string staleMessage

    readonly property var colors: Styles.colors.new

    // As many lines as fit at the real clocks' proportions (2 on their ~3.5:1
    // screens, 4 at 16:9), up to 10 on tall portrait screens.
    readonly property int lines: width > 0 && height > 0
        ? Math.max(1, Math.min(10, Math.round(height / (width / 7)))) : 2
    readonly property string message: board.stale ? staleMessage : ""
    readonly property real messageHeight: message ? Math.min(height * 0.1, width * 0.035) : 0
    readonly property real rowHeight: (height - messageHeight) / lines

    color: colors.background

    // One delegate per line, kept as trains come and go, so the last line can animate its rotation
    Repeater {
        model: root.lines

        Loader {
            id: line

            required property int index
            readonly property var train: root.board.rows[index]

            y: index * root.rowHeight
            width: root.width
            height: root.rowHeight
            active: !!train
            sourceComponent: NewRow {
                train: line.train
                colors: root.colors
                bulletsUrl: root.bulletsUrl
                animated: root.lines > 1 && line.index === root.lines - 1
            }
        }
    }

    // A service alert in place of the last line: a white card with a yellow bar where the number was
    Item {
        visible: root.board.message !== ""
        y: (root.lines - 1) * root.rowHeight + root.rowHeight * 0.04
        width: root.width
        height: root.rowHeight * 0.92

        Rectangle {
            width: root.rowHeight * 0.5
            height: parent.height
            radius: root.rowHeight * 0.06
            color: root.colors.alertBar
        }

        Rectangle {
            x: root.rowHeight * 0.4
            width: parent.width - x
            height: parent.height
            radius: root.rowHeight * 0.06
            color: root.colors.alertCard

            Text {
                anchors.fill: parent
                anchors.leftMargin: root.rowHeight * 0.18
                anchors.rightMargin: root.rowHeight * 0.18
                verticalAlignment: Text.AlignVCenter
                textFormat: Text.StyledText
                text: Messages.styled(root.board.message, root.bulletsUrl, Math.round(font.pixelSize * 0.95))
                wrapMode: Text.WordWrap
                elide: Text.ElideRight
                // Two lines at the design's size, or three smaller ones for a long alert
                readonly property bool lengthy: root.board.message.length > 70
                maximumLineCount: lengthy ? 3 : 2
                font.family: "Roboto"
                font.pixelSize: root.rowHeight * (lengthy ? 0.23 : 0.32)
                color: root.colors.alertText
            }
        }
    }

    // Stale data warning across the bottom
    Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: root.messageHeight
        visible: root.message !== ""
        color: root.colors.messageBackground

        Text {
            anchors.fill: parent
            anchors.leftMargin: parent.height * 0.4
            anchors.rightMargin: parent.height * 0.4
            verticalAlignment: Text.AlignVCenter
            text: root.message
            elide: Text.ElideRight
            font.family: "Roboto"
            font.weight: Font.Medium
            font.pixelSize: parent.height * 0.55
            color: root.colors.messageText
        }
    }
}
