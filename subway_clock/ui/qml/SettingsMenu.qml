import QtQuick

// The settings menu, drawn over whichever style is showing. What it lists and
// what each key does is decided in Python (ui/menu.py); this draws clock.menu:
//   open, page ("main", "search" or "station"), title, keys (what the keys do)
//   rows: label, value (at the right), detail (lesser, after the label),
//       bullets, box (a box to tick) and checked
//   index: the row selected
//   query, prompt: on the search page, what has been typed, and what to say until something is
//   empty: what to say in place of the rows when there are none
// It keeps to one look of its own, whatever the style, so that it reads the same over all of them.
Item {
    id: root

    required property var menu
    required property url bulletsUrl

    visible: menu.open

    // A row's height. The panel is a title, the rows and the keys, and fits six rows on the
    // widest bar; a taller screen gets more rows, not bigger ones, for the pages that are lists.
    readonly property real unit: Math.min(width * 0.96 / 9, height * 0.94 / 8.6, 72)
    readonly property int most: Math.max(6, Math.min(12, Math.floor(height * 0.94 / unit - 2.6)))
    readonly property int lines: menu.page === "main" ? Math.max(6, Math.min(most, menu.rows.length)) : most
    readonly property bool searching: menu.page === "search"

    // The rows that fit, keeping the selected one in view
    readonly property int shown: lines - (searching ? 1 : 0)
    readonly property int first: Math.max(0, Math.min(menu.index - Math.floor(shown / 2), menu.rows.length - shown))

    readonly property color ink: "#ffffff"
    readonly property color faint: "#a4a4ad"

    Rectangle {
        anchors.fill: parent
        color: "#000000"
        opacity: 0.6
    }

    Rectangle {
        anchors.centerIn: parent
        width: Math.min(parent.width * 0.96, root.unit * 20)
        height: root.unit * (root.lines + 2.6)
        color: "#1c1c21"
        border.color: "#5a5a63"
        border.width: Math.max(1, Math.round(root.unit * 0.03))

        Text {
            id: title
            x: root.unit * 0.5
            width: parent.width - x * 2
            height: root.unit * 1.3
            verticalAlignment: Text.AlignVCenter
            text: root.menu.title
            elide: Text.ElideRight
            font.family: "Roboto"
            font.weight: Font.Bold
            font.pixelSize: root.unit * 0.56
            color: root.ink
        }

        // What has been typed
        Rectangle {
            id: query
            visible: root.searching
            anchors.top: title.bottom
            x: root.unit * 0.3
            width: parent.width - x * 2
            height: visible ? root.unit : 0
            color: "#000000"
            border.color: root.faint
            border.width: Math.max(1, Math.round(root.unit * 0.03))

            Text {
                id: typed
                x: root.unit * 0.3
                width: Math.min(implicitWidth, parent.width - x * 2)
                anchors.verticalCenter: parent.verticalCenter
                text: root.menu.query === "" ? root.menu.prompt : root.menu.query
                elide: root.menu.query === "" ? Text.ElideRight : Text.ElideLeft
                font.family: "Roboto"
                font.pixelSize: root.unit * 0.42
                color: root.menu.query === "" ? root.faint : root.ink
            }

            Rectangle {
                x: root.menu.query === "" ? typed.x : typed.x + typed.width + root.unit * 0.04
                width: Math.max(2, Math.round(root.unit * 0.05))
                height: root.unit * 0.5
                anchors.verticalCenter: parent.verticalCenter
                color: root.ink
                // Over the prompt, which gives way to what is typed
                opacity: root.menu.query === "" ? 0.5 : 1
            }
        }

        Item {
            id: list
            anchors.top: query.bottom
            width: parent.width
            height: root.unit * root.shown
            clip: true

            Text {
                anchors.fill: parent
                anchors.margins: root.unit * 0.5
                visible: root.menu.empty !== ""
                text: root.menu.empty
                wrapMode: Text.WordWrap
                font.family: "Roboto"
                font.pixelSize: root.unit * 0.4
                color: root.faint
            }

            Repeater {
                model: root.menu.rows.slice(root.first, root.first + root.shown)

                Item {
                    id: line

                    required property var modelData
                    required property int index

                    readonly property bool selected: root.first + index === root.menu.index
                    readonly property color ink: selected ? "#000000" : root.ink
                    readonly property color faint: selected ? "#4a4a52" : root.faint

                    y: index * root.unit
                    width: list.width
                    height: root.unit

                    Rectangle {
                        anchors.fill: parent
                        anchors.leftMargin: root.unit * 0.15
                        anchors.rightMargin: root.unit * 0.15
                        anchors.topMargin: root.unit * 0.04
                        anchors.bottomMargin: root.unit * 0.04
                        visible: line.selected
                        color: "#ffffff"
                    }

                    Text {
                        id: value
                        anchors.right: parent.right
                        anchors.rightMargin: root.unit * 0.45
                        anchors.verticalCenter: parent.verticalCenter
                        // A setting's value is what the row is for; a station's borough or a stop's ID is an aside.
                        width: Math.min(implicitWidth, parent.width * (root.menu.page === "main" ? 0.66 : 0.4))
                        text: line.modelData.value
                        elide: Text.ElideRight
                        font.family: "Roboto"
                        font.pixelSize: root.unit * (root.menu.page === "main" ? 0.42 : 0.34)
                        color: root.menu.page === "main" ? line.ink : line.faint
                    }

                    Row {
                        id: left
                        anchors.left: parent.left
                        anchors.leftMargin: root.unit * 0.45
                        anchors.right: value.left
                        anchors.rightMargin: root.unit * 0.3
                        anchors.verticalCenter: parent.verticalCenter
                        height: root.unit
                        spacing: root.unit * 0.2
                        clip: true

                        Rectangle {
                            visible: line.modelData.box
                            anchors.verticalCenter: parent.verticalCenter
                            width: root.unit * 0.46
                            height: width
                            color: "transparent"
                            border.color: line.ink
                            border.width: Math.max(1, Math.round(root.unit * 0.05))

                            Rectangle {
                                anchors.fill: parent
                                anchors.margins: root.unit * 0.12
                                visible: line.modelData.checked
                                color: line.ink
                            }
                        }

                        // A direction's bullets say which platform it is, so they come first;
                        // a station's follow its name.
                        Row {
                            visible: line.modelData.box && line.modelData.bullets.length > 0
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: root.unit * 0.06
                            Repeater {
                                model: line.modelData.box ? line.modelData.bullets : []
                                Image {
                                    required property string modelData
                                    width: root.unit * 0.56
                                    height: width
                                    sourceSize: Qt.size(width, height)
                                    source: root.bulletsUrl + "NYCS-bull-trans-" + modelData + ".svg"
                                }
                            }
                        }

                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            width: Math.min(implicitWidth, left.width - x)
                            text: line.modelData.label
                            elide: Text.ElideRight
                            font.family: "Roboto"
                            font.weight: Font.Medium
                            font.pixelSize: root.unit * 0.44
                            color: line.ink
                        }

                        Row {
                            visible: !line.modelData.box && line.modelData.bullets.length > 0
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: root.unit * 0.06
                            Repeater {
                                model: line.modelData.box ? [] : line.modelData.bullets
                                Image {
                                    required property string modelData
                                    width: root.unit * 0.5
                                    height: width
                                    sourceSize: Qt.size(width, height)
                                    source: root.bulletsUrl + "NYCS-bull-trans-" + modelData + ".svg"
                                }
                            }
                        }

                        Text {
                            visible: text !== ""
                            anchors.verticalCenter: parent.verticalCenter
                            text: line.modelData.detail
                            font.family: "Roboto"
                            font.pixelSize: root.unit * 0.34
                            color: line.faint
                        }
                    }
                }
            }

            // Where the rows shown are among all of them, when they don't all fit
            Rectangle {
                visible: root.menu.rows.length > root.shown
                x: parent.width - width - root.unit * 0.04
                y: parent.height * root.first / Math.max(1, root.menu.rows.length)
                width: Math.max(2, root.unit * 0.07)
                height: parent.height * root.shown / Math.max(1, root.menu.rows.length)
                color: root.faint
            }
        }

        Text {
            anchors.top: list.bottom
            x: root.unit * 0.5
            width: parent.width - x * 2
            height: root.unit * 1.3
            verticalAlignment: Text.AlignVCenter
            text: root.menu.keys
            wrapMode: Text.WordWrap
            maximumLineCount: 2
            elide: Text.ElideRight
            font.family: "Roboto"
            font.pixelSize: root.unit * 0.32
            color: root.faint
        }
    }
}
