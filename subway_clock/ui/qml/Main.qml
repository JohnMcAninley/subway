import QtQuick

// Draws a Board from the core (clock.board) in its style. No train logic here:
// which trains appear on which line is decided in Python. Each style's board
// works out how many lines fit the screen (and whether to group them by
// direction), and that goes back to the core. Until there is a board to draw
// (the first trains are still being fetched, or a first run is downloading
// the schedules), each style shows clock.startup.
Item {
    id: root

    required property QtObject clock

    readonly property string stale: "Live train times are delayed. Times shown may be out of date."

    Loader {
        id: style
        anchors.fill: parent
        sourceComponent: root.clock.board.style === "classic" ? classicBoard
            : root.clock.board.style === "led" ? ledBoard
            : root.height > root.width * 1.3 ? newPortraitBoard : newBoard
    }

    Component {
        id: classicBoard
        ClassicBoard {
            board: root.clock.board; bulletsUrl: root.clock.bulletsUrl; staleMessage: root.stale
            showStation: root.clock.showStation; startup: root.clock.startup
        }
    }

    Component {
        id: newBoard
        NewBoard {
            board: root.clock.board; bulletsUrl: root.clock.bulletsUrl; staleMessage: root.stale
            showStation: root.clock.showStation; startup: root.clock.startup
        }
    }

    Component {
        id: ledBoard
        LedBoard {
            board: root.clock.board; bulletsUrl: root.clock.bulletsUrl; staleMessage: root.stale
            showStation: root.clock.showStation; startup: root.clock.startup
        }
    }

    Component {
        id: newPortraitBoard
        NewPortraitBoard {
            board: root.clock.board; bulletsUrl: root.clock.bulletsUrl; staleMessage: root.stale
            showStation: root.clock.showStation; startup: root.clock.startup
        }
    }

    SettingsMenu {
        anchors.fill: parent
        clock: root.clock
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
