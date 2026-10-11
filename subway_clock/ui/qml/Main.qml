import QtQuick

// Draws a Board from the core (clock.board) in its style. No train logic here:
// which trains appear on which line is decided in Python. Each style's board
// works out how many lines fit the screen (and whether to group them by
// direction), and that goes back to the core.
Item {
    id: root

    required property QtObject clock

    readonly property string stale: "Live train times are delayed. Times shown may be out of date."

    Loader {
        id: style
        anchors.fill: parent
        sourceComponent: root.clock.board.style !== "new" ? classicBoard
            : root.height > root.width * 1.3 ? newPortraitBoard : newBoard
    }

    Component {
        id: classicBoard
        ClassicBoard { board: root.clock.board; bulletsUrl: root.clock.bulletsUrl; staleMessage: root.stale }
    }

    Component {
        id: newBoard
        NewBoard { board: root.clock.board; bulletsUrl: root.clock.bulletsUrl; staleMessage: root.stale }
    }

    Component {
        id: newPortraitBoard
        NewPortraitBoard { board: root.clock.board; bulletsUrl: root.clock.bulletsUrl; staleMessage: root.stale }
    }

    // Tell the core the layout whenever the style's board is replaced or resized.
    function sendLayout() {
        if (style.item && style.item.lines > 0)
            clock.setLayout(style.item.lines, style.item.grouped === true)
    }

    Connections {
        target: style
        function onLoaded() { root.sendLayout() }
    }

    Connections {
        target: style.item
        function onLinesChanged() { root.sendLayout() }
    }
}
