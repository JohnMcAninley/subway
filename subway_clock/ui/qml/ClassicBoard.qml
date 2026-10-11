import QtQuick
import "Styles.js" as Styles

// The classic LCD clock: lines of "1. (bullet) Destination   3 min" over a
// strip with the time and scrolling service alerts.
Rectangle {
    id: root

    required property var board
    required property url bulletsUrl
    required property string staleMessage
    required property var startup

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

    // Before there are trains to show: what the clock is doing on the first line, with how
    // far along it is where the minutes go, and a second line under it
    Repeater {
        model: root.startup.state === "ready" ? [] : [
            { text: root.startup.title,
              value: root.startup.state === "loading" && root.startup.progress >= 0
                     ? Math.round(root.startup.progress * 100) + "%" : "" },
            { text: root.startup.detail, value: "" },
        ].slice(0, root.lines)

        Item {
            required property var modelData
            required property int index

            y: index * root.rowHeight
            width: root.width
            height: root.rowHeight

            Text {
                anchors.left: parent.left
                anchors.leftMargin: root.fontSize * 0.3
                anchors.right: value.left
                anchors.rightMargin: root.fontSize * 0.3
                anchors.verticalCenter: parent.verticalCenter
                text: modelData.text
                elide: Text.ElideRight
                font.family: "Roboto"
                font.pixelSize: root.fontSize
                color: root.colors.text
            }

            Text {
                id: value
                anchors.right: parent.right
                anchors.rightMargin: root.fontSize * 0.3
                anchors.verticalCenter: parent.verticalCenter
                text: modelData.value
                font.family: "Roboto"
                font.pixelSize: root.fontSize
                color: root.colors.text
            }
        }
    }

    StatusStrip {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: root.statusHeight
        colors: root.colors
        bulletsUrl: root.bulletsUrl
        messages: (root.board.stale ? [root.staleMessage] : []).concat(root.board.messages)
    }
}
