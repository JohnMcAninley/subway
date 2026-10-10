import QtQuick
import "Themes.js" as Themes

// Draws a Board from the core (clock.board). No train logic here: which
// trains appear on which line is decided in Python.
Rectangle {
    id: root

    required property QtObject clock

    readonly property var board: clock.board
    readonly property var theme: Themes.themes[board.theme]

    // Two lines over a status strip. Text is sized from the width (as on the
    // real ~3.8:1 clocks) unless the screen is too short for it.
    readonly property real statusHeight: Math.min(height * 0.12, width * 0.04)
    readonly property real rowHeight: (height - statusHeight) / 2
    readonly property real fontSize: Math.min(rowHeight * 0.5, width * 0.057)

    color: theme.background

    Repeater {
        model: root.board.rows

        TrainRow {
            required property var modelData
            required property int index

            x: 0
            y: index * root.rowHeight
            width: root.width
            height: root.rowHeight
            train: modelData
            theme: root.theme
            fontSize: root.fontSize
            bulletsUrl: root.clock.bulletsUrl
        }
    }

    Rectangle {
        y: root.rowHeight - height / 2
        width: root.width
        height: Math.max(1, root.height * 0.004)
        color: root.theme.separator
        visible: root.board.rows.length > 1
    }

    StatusStrip {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: root.statusHeight
        theme: root.theme
        message: root.board.stale ? "Live train times are delayed. Times shown may be out of date." : ""
    }
}
