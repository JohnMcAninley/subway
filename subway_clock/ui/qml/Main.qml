import QtQuick

// Draws a Board from the core (clock.board) in its style. No train logic here:
// which trains appear on which line is decided in Python. Each style's board
// works out how many lines fit the screen, and that goes back to the core.
Item {
    id: root

    required property QtObject clock

    readonly property string stale: "Live train times are delayed. Times shown may be out of date."

    Loader {
        id: style
        anchors.fill: parent
        sourceComponent: root.clock.board.style === "new" ? newBoard : classicBoard
    }

    Component {
        id: classicBoard
        ClassicBoard { board: root.clock.board; bulletsUrl: root.clock.bulletsUrl; staleMessage: root.stale }
    }

    Component {
        id: newBoard
        NewBoard { board: root.clock.board; bulletsUrl: root.clock.bulletsUrl; staleMessage: root.stale }
    }

    Binding {
        target: root.clock
        property: "lines"
        value: style.item ? style.item.lines : 2
        when: style.status === Loader.Ready
    }
}
