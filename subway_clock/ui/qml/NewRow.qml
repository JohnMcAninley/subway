import QtQuick

// One line of the newer clocks: the number, then a card with the bullet, the
// direction over the destination, and the minutes over "MIN".
Item {
    id: row

    required property var train
    required property var colors
    required property url bulletsUrl

    readonly property color textColor: train.arriving ? colors.arrivingText : colors.text
    // The direction label is the headline when there is one, as on the real clocks.
    readonly property string headline: train.direction || train.destination
    readonly property string subtitle: train.direction ? train.destination : ""
    readonly property real unit: height  // sizes below are fractions of the line height

    Text {
        anchors.horizontalCenter: parent.left
        anchors.horizontalCenterOffset: row.unit * 0.2
        anchors.verticalCenter: parent.verticalCenter
        text: row.train.number
        font.family: "Roboto"
        font.weight: Font.Bold
        font.pixelSize: row.unit * 0.3
        color: row.colors.number
    }

    Rectangle {
        id: card
        x: row.unit * 0.4
        width: parent.width - x - row.unit * 0.1
        height: row.unit * 0.84
        anchors.verticalCenter: parent.verticalCenter
        radius: row.unit * 0.05
        color: row.train.arriving ? row.colors.arrivingCard : row.colors.card

        Image {
            id: bullet
            anchors.left: parent.left
            anchors.leftMargin: row.unit * 0.12
            anchors.verticalCenter: parent.verticalCenter
            width: row.unit * 0.48
            height: width
            sourceSize: Qt.size(width, height)
            source: row.bulletsUrl + "NYCS-bull-trans-" + row.train.bullet + ".svg"
        }

        Column {
            anchors.left: bullet.right
            anchors.leftMargin: row.unit * 0.14
            anchors.right: minutes.left
            anchors.rightMargin: row.unit * 0.1
            anchors.verticalCenter: parent.verticalCenter

            Text {
                width: parent.width
                text: row.headline
                elide: Text.ElideRight
                font.family: "Roboto"
                font.weight: Font.Bold
                font.pixelSize: row.unit * 0.3
                color: row.textColor
            }

            Text {
                width: parent.width
                visible: text !== ""
                text: row.subtitle
                elide: Text.ElideRight
                font.family: "Roboto"
                font.weight: Font.Medium
                font.pixelSize: row.unit * 0.17
                color: row.textColor
            }
        }

        Column {
            id: minutes
            anchors.right: parent.right
            anchors.rightMargin: row.unit * 0.14
            anchors.verticalCenter: parent.verticalCenter
            spacing: -row.unit * 0.04

            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: row.train.minutes
                font.family: "Roboto"
                font.weight: Font.Bold
                font.pixelSize: row.unit * 0.42
                color: row.textColor
            }

            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "MIN"
                font.family: "Roboto"
                font.weight: Font.Bold
                font.pixelSize: row.unit * 0.1
                color: row.textColor
            }
        }
    }
}
