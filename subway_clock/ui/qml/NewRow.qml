import QtQuick

// One line of the newer clocks: the number, then a card with the bullet, the
// headline over its detail, and the minutes over "MIN". Proportions follow
// the MTA's 1920x480 design, where a line is 240 high.
Item {
    id: row

    required property var train
    required property var colors
    required property url bulletsUrl
    property bool numbered: true  // the train's number to the left of the card, as on the platform clocks
    property bool animated: false  // show a change of train as the line rotating

    // What is drawn. It trails `train` during the rotation animation.
    property var shown: train
    readonly property color textColor: shown.arriving ? colors.arrivingText : colors.text
    readonly property real unit: height  // sizes below are fractions of the line height

    onTrainChanged: {
        const same = train.number === shown.number && train.route === shown.route
            && train.destination === shown.destination
        if (animated && !same)
            rotation.restart()
        else if (!rotation.running)
            shown = train
    }

    // The old train dims and its number rolls away upwards; the new one arrives from below.
    SequentialAnimation {
        id: rotation

        ParallelAnimation {
            NumberAnimation { target: content; property: "opacity"; to: 0.25; duration: 220; easing.type: Easing.InQuad }
            NumberAnimation { target: number; property: "offset"; to: -1; duration: 220; easing.type: Easing.InQuad }
        }
        ScriptAction { script: { row.shown = row.train; number.offset = 1 } }
        ParallelAnimation {
            NumberAnimation { target: content; property: "opacity"; to: 1; duration: 220; easing.type: Easing.OutQuad }
            NumberAnimation { target: number; property: "offset"; to: 0; duration: 220; easing.type: Easing.OutQuad }
        }
    }

    Item {
        visible: row.numbered
        width: row.unit * 0.4
        height: parent.height
        clip: true

        Text {
            id: number

            property real offset: 0  // -1 is a line up, 1 a line down

            anchors.horizontalCenter: parent.horizontalCenter
            y: (parent.height - height) / 2 + offset * parent.height * 0.6
            text: row.shown.number
            font.family: "Roboto"
            font.weight: Font.Bold
            font.pixelSize: row.unit * 0.36
            color: row.colors.number
        }
    }

    Rectangle {
        id: card
        x: row.unit * (row.numbered ? 0.4 : 0.12)
        width: parent.width - x - (row.numbered ? 0 : row.unit * 0.12)
        height: row.unit * 0.92
        anchors.verticalCenter: parent.verticalCenter
        color: row.shown.arriving ? row.colors.arrivingCard : row.colors.card

        Item {
            id: content
            anchors.fill: parent

            Image {
                id: bullet
                anchors.left: parent.left
                anchors.leftMargin: row.unit * 0.125
                anchors.verticalCenter: parent.verticalCenter
                width: row.unit * 0.66
                height: width
                sourceSize: Qt.size(width, height)
                source: row.bulletsUrl + "NYCS-bull-trans-" + row.shown.bullet + ".svg"
            }

            Column {
                anchors.left: bullet.right
                anchors.leftMargin: row.unit * 0.1
                anchors.right: minutes.left
                anchors.rightMargin: row.unit * 0.1
                anchors.verticalCenter: parent.verticalCenter
                spacing: -row.unit * 0.04

                Text {
                    width: parent.width
                    text: row.shown.headline
                    elide: Text.ElideRight
                    font.family: "Roboto"
                    font.weight: Font.Bold
                    font.pixelSize: row.unit * 0.4
                    color: row.textColor
                }

                Text {
                    width: parent.width
                    visible: text !== ""
                    text: row.shown.detail
                    elide: Text.ElideRight
                    font.family: "Roboto"
                    font.pixelSize: row.unit * 0.22
                    color: row.textColor
                }
            }

            // The minutes and "MIN" share a fixed centre line, whether one digit or two.
            Item {
                id: minutes
                anchors.right: parent.right
                anchors.rightMargin: row.unit * 0.08
                width: row.unit * 0.8
                height: parent.height

                Column {
                    anchors.centerIn: parent
                    spacing: -row.unit * 0.07

                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: row.shown.minutes
                        font.family: "Roboto"
                        font.weight: Font.Bold
                        font.pixelSize: row.unit * 0.6
                        color: row.textColor
                    }

                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: "MIN"
                        font.family: "Roboto"
                        font.weight: Font.Bold
                        font.letterSpacing: row.unit * 0.012
                        font.pixelSize: row.unit * 0.11
                        color: row.textColor
                        opacity: 0.75
                    }
                }
            }
        }
    }
}
