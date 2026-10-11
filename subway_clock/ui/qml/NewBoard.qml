import QtQuick
import "Messages.js" as Messages
import "Styles.js" as Styles

// The newer clocks: a numbered card per train on a dark screen. Service alerts
// take turns with the trains on the last line.
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

    Repeater {
        model: root.board.rows

        NewRow {
            required property var modelData
            required property int index

            y: index * root.rowHeight
            width: root.width
            height: root.rowHeight
            train: modelData
            colors: root.colors
            bulletsUrl: root.bulletsUrl
        }
    }

    // A service alert in place of the last line
    Rectangle {
        id: alert
        visible: root.board.message !== ""
        x: root.rowHeight * 0.4
        y: (root.lines - 1) * root.rowHeight + root.rowHeight * 0.08
        width: root.width - x - root.rowHeight * 0.1
        height: root.rowHeight * 0.84
        radius: root.rowHeight * 0.05
        color: root.colors.card

        Text {
            anchors.fill: parent
            anchors.leftMargin: root.rowHeight * 0.14
            anchors.rightMargin: root.rowHeight * 0.14
            anchors.topMargin: root.rowHeight * 0.06
            anchors.bottomMargin: root.rowHeight * 0.06
            verticalAlignment: Text.AlignVCenter
            textFormat: Text.StyledText
            text: Messages.styled(root.board.message, root.bulletsUrl, Math.round(font.pixelSize * 1.05))
            wrapMode: Text.WordWrap
            elide: Text.ElideRight
            maximumLineCount: 3
            font.family: "Roboto"
            font.weight: Font.Medium
            font.pixelSize: root.rowHeight * 0.17
            color: root.colors.text
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
