import QtQuick
import "Styles.js" as Styles

// The classic LCD clock: lines of "1. (bullet) Destination   3 min" over a
// strip with the time and a message.
Rectangle {
    id: root

    required property var board
    required property url bulletsUrl
    required property string staleMessage

    readonly property var colors: Styles.colors.classic

    // As many lines as fit at the real clocks' proportions (2 on their ~3.8:1
    // screens, 4 at 16:9), up to 10 on tall portrait screens.
    readonly property real statusHeight: Math.min(height * 0.12, width * 0.04)
    readonly property int lines: width > 0 && height > 0
        ? Math.max(1, Math.min(10, Math.round((height - statusHeight) / (width / 8)))) : 2
    readonly property real rowHeight: (height - statusHeight) / lines
    // Text is sized from the width, so destinations fit, unless the lines are too short for it.
    readonly property real fontSize: Math.min(rowHeight * 0.5, width * 0.057)

    color: colors.background

    Repeater {
        model: root.board.rows

        ClassicRow {
            required property var modelData
            required property int index

            y: index * root.rowHeight
            width: root.width
            height: root.rowHeight
            train: modelData
            colors: root.colors
            fontSize: root.fontSize
            bulletsUrl: root.bulletsUrl
        }
    }

    // Separators between lines
    Repeater {
        model: root.lines - 1

        Rectangle {
            required property int index

            y: (index + 1) * root.rowHeight - height / 2
            width: root.width
            height: Math.max(1, root.fontSize * 0.02)
            color: root.colors.separator
        }
    }

    StatusStrip {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: root.statusHeight
        colors: root.colors
        message: root.board.stale ? root.staleMessage : ""
    }
}
