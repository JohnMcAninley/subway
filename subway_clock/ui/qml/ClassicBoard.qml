import QtQuick
import "Styles.js" as Styles

// The classic LCD clock: lines of "1. (bullet) Destination   3 min" over a
// strip with the time and scrolling service alerts. With showStation, a strip
// across the top names the station as the sign over an entrance does; the real
// clocks have nothing like it.
Rectangle {
    id: root

    required property var board
    required property url bulletsUrl
    required property string staleMessage
    required property bool showStation
    required property var startup

    readonly property var colors: Styles.colors.classic

    // As many lines as fit at the real clocks' proportions (2 on their ~3.8:1
    // screens, 4 at 16:9), up to 10 on tall portrait screens.
    readonly property real statusHeight: Math.min(height * 0.12, width * 0.04)
    readonly property int lines: width > 0 && height > 0
        ? Math.max(1, Math.min(10, Math.round((height - statusHeight) / (width / 8)))) : 2
    readonly property real headerHeight: showStation && board.station ? Math.min(height * 0.14, width * 0.07) : 0
    readonly property real rowHeight: (height - headerHeight - statusHeight) / lines
    // Text is sized from the width, so destinations fit, unless the lines are too short for it.
    readonly property real fontSize: Math.min(rowHeight * 0.5, width * 0.057)

    color: colors.background

    Repeater {
        model: root.board.rows

        ClassicRow {
            required property var modelData
            required property int index

            y: root.headerHeight + index * root.rowHeight
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

            y: root.headerHeight + (index + 1) * root.rowHeight - height / 2
            width: root.width
            height: Math.max(1, root.fontSize * 0.02)
            color: root.colors.separator
        }
    }

    // The station, then its routes' bullets, and the direction at the right if there is
    // room, in the strip's colours
    Rectangle {
        id: header
        visible: root.headerHeight > 0
        width: root.width
        height: root.headerHeight
        color: root.colors.statusBackground

        readonly property real margin: root.fontSize * 0.3

        Text {
            id: station
            x: header.margin
            width: Math.min(implicitWidth, header.width - header.margin * 3 - bullets.width
                            - (direction.visible ? direction.width + header.margin : 0))
            anchors.verticalCenter: parent.verticalCenter
            text: root.board.station
            elide: Text.ElideRight
            font.family: "Roboto"
            font.weight: Font.Medium
            font.pixelSize: header.height * 0.62
            color: root.colors.statusText
        }

        Row {
            id: bullets
            anchors.left: station.right
            anchors.leftMargin: header.margin
            anchors.verticalCenter: parent.verticalCenter
            spacing: header.height * 0.08

            Repeater {
                model: root.board.routes

                Image {
                    required property var modelData

                    width: header.height * 0.68
                    height: width
                    sourceSize: Qt.size(width, height)
                    source: root.bulletsUrl + "NYCS-bull-trans-" + modelData.bullet + ".svg"
                }
            }
        }

        // An arriving train's line is black too
        Rectangle {
            anchors.bottom: parent.bottom
            width: parent.width
            height: Math.max(1, root.fontSize * 0.02)
            color: root.colors.separator
        }

        Text {
            id: direction
            visible: station.implicitWidth + bullets.width + width + header.margin * 4 <= header.width
            anchors.right: parent.right
            anchors.rightMargin: root.fontSize * 0.3
            anchors.verticalCenter: parent.verticalCenter
            text: root.board.direction
            font.family: "Roboto"
            font.pixelSize: header.height * 0.5
            color: root.colors.statusText
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

            y: root.headerHeight + index * root.rowHeight
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
