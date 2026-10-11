import QtQuick
import "Styles.js" as Styles

// The newer clocks: a numbered card per train on a dark screen, with a
// message across the bottom only when there is one.
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
