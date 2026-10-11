import QtQuick
import "Messages.js" as Messages
import "Styles.js" as Styles

// The portrait screens in station entrances and mezzanines: the time, a card
// per train (under a heading per direction when there is more than one), and
// the service alerts at the bottom.
Rectangle {
    id: root

    required property var board
    required property url bulletsUrl
    required property string staleMessage

    readonly property var colors: Styles.colors.new
    readonly property real unit: width / 1080  // the real screens are 1080x1920

    // Trains fill about the top half, as on the real screens: 5 lines at 9:16.
    readonly property bool grouped: true
    readonly property real rowHeight: unit * 165
    readonly property int lines: width > 0 && height > 0
        ? Math.max(2, Math.min(8, Math.floor((height * 0.52 - header.height) / rowHeight))) : 4

    // The trains, with a heading before those of each direction
    readonly property var entries: board.groups.length
        ? board.groups.reduce((all, g) => all.concat([{ heading: g.heading }], g.rows.map(r => ({ train: r }))), [])
        : board.rows.map(r => ({ train: r }))

    // Alerts as title and text. The stale data warning comes first.
    readonly property var alerts: (board.stale ? [{ title: "Delayed", text: staleMessage }] : []).concat(
        board.messages.map(m => ({ title: m.planned ? "Planned work" : "Happening now", text: m.text })))

    color: colors.background

    Item {
        id: header
        width: parent.width
        height: root.unit * 105

        Row {
            anchors.right: parent.right
            anchors.rightMargin: root.unit * 28
            anchors.verticalCenter: parent.verticalCenter

            Text {
                id: time
                font.family: "Roboto"
                font.weight: Font.Bold
                font.pixelSize: root.unit * 46
                color: root.colors.text
            }

            Text {
                id: seconds
                anchors.baseline: time.baseline
                font.family: "Roboto"
                font.pixelSize: root.unit * 46
                color: root.colors.text
                opacity: 0.75
            }
        }

        Timer {
            interval: 250; running: true; repeat: true; triggeredOnStart: true
            onTriggered: {
                const now = new Date()
                time.text = Qt.formatTime(now, "h:mm")
                seconds.text = Qt.formatTime(now, ":ss")
            }
        }
    }

    Column {
        id: trains
        anchors.top: header.bottom
        width: parent.width

        Repeater {
            model: root.entries

            Item {
                id: entry

                required property var modelData

                width: trains.width
                height: modelData.train ? root.rowHeight : root.unit * 62

                Text {
                    visible: !entry.modelData.train
                    x: root.unit * 28
                    anchors.bottom: parent.bottom
                    anchors.bottomMargin: root.unit * 4
                    text: entry.modelData.heading || ""
                    font.family: "Roboto"
                    font.weight: Font.Bold
                    font.pixelSize: root.unit * 36
                    color: root.colors.text
                }

                Loader {
                    active: !!entry.modelData.train
                    anchors.fill: parent
                    sourceComponent: NewRow {
                        train: entry.modelData.train
                        colors: root.colors
                        bulletsUrl: root.bulletsUrl
                        numbered: false
                    }
                }
            }
        }
    }

    // Service alerts, from the bottom up to where the trains end
    Column {
        id: alertPanel
        visible: root.alerts.length > 0
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: root.unit * 55
        anchors.bottomMargin: root.unit * 40
        spacing: root.unit * 26

        Text {
            text: "Service alerts"
            font.family: "Roboto"
            font.weight: Font.Bold
            font.pixelSize: root.unit * 46
            color: root.colors.text
        }

        Repeater {
            // As many as fit below the trains, at about 230 units each
            model: root.alerts.slice(0, Math.max(1, Math.floor(
                (root.height - header.height - trains.height - root.unit * 200) / (root.unit * 230))))

            Column {
                id: alert

                required property var modelData

                width: alertPanel.width
                spacing: root.unit * 22

                Rectangle { width: parent.width; height: Math.max(1, root.unit * 3); color: root.colors.text; opacity: 0.5 }

                Row {
                    width: parent.width
                    spacing: root.unit * 30

                    Text {
                        width: parent.width * 0.3
                        text: alert.modelData.title
                        wrapMode: Text.WordWrap
                        font.family: "Roboto"
                        font.weight: Font.Bold
                        font.pixelSize: root.unit * 34
                        color: root.colors.text
                    }

                    Text {
                        width: parent.width * 0.7 - parent.spacing
                        textFormat: Text.StyledText
                        text: Messages.styled(alert.modelData.text, root.bulletsUrl, Math.round(root.unit * 36))
                        wrapMode: Text.WordWrap
                        elide: Text.ElideRight
                        maximumLineCount: 4
                        font.family: "Roboto"
                        font.pixelSize: root.unit * 34
                        color: root.colors.text
                    }
                }
            }
        }
    }
}
