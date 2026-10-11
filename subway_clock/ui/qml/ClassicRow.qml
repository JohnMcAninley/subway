import QtQuick

// One line of the classic clock: "1. (bullet) Destination      3 min"
Item {
    id: row

    required property var train
    required property var colors
    required property real fontSize
    required property url bulletsUrl

    readonly property color textColor: train.arriving ? colors.arrivingText : colors.text
    readonly property real margin: fontSize * 0.3

    Rectangle {
        anchors.fill: parent
        color: row.train.arriving ? row.colors.arrivingBackground : "transparent"
    }

    Text {
        id: number
        anchors.left: parent.left
        anchors.leftMargin: row.margin
        anchors.verticalCenter: parent.verticalCenter
        text: row.train.number + "."
        font.family: "Roboto"
        font.pixelSize: row.fontSize
        color: row.textColor
    }

    Image {
        id: bullet
        anchors.left: number.right
        anchors.leftMargin: row.fontSize * 0.04
        // Centre on the capitals, not the line box (Roboto's cap height is 0.71 em)
        anchors.verticalCenter: number.baseline
        anchors.verticalCenterOffset: -row.fontSize * 0.355
        width: row.fontSize * 0.95
        height: width
        sourceSize: Qt.size(width, height)
        source: row.bulletsUrl + "NYCS-bull-trans-" + row.train.bullet + ".svg"
    }

    Text {
        id: destination
        anchors.left: bullet.right
        anchors.leftMargin: row.fontSize * 0.25
        anchors.right: minutes.left
        anchors.rightMargin: row.margin
        anchors.baseline: number.baseline
        text: row.train.destination
        elide: Text.ElideRight
        font.family: "Roboto"
        font.pixelSize: row.fontSize
        color: row.textColor
    }

    Text {
        id: minutes
        anchors.right: minLabel.left
        anchors.rightMargin: row.fontSize * 0.08
        anchors.baseline: number.baseline
        text: row.train.minutes
        font.family: "Roboto"
        font.pixelSize: row.fontSize * 1.05
        color: row.textColor
    }

    Text {
        id: minLabel
        anchors.right: parent.right
        anchors.rightMargin: row.margin
        anchors.baseline: number.baseline
        text: "min"
        font.family: "Roboto"
        font.pixelSize: row.fontSize * 0.55
        color: row.textColor
    }
}
