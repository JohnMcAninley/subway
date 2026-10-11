import QtQuick
import "Messages.js" as Messages

// The alert that takes over when no trains are coming and it says why: the
// card that otherwise takes the last line, grown to hold a bold title over
// the alert's own words.
Item {
    id: card

    required property var alert  // one of the board's messages
    required property var colors
    required property url bulletsUrl
    required property real barWidth
    required property real titleSize
    required property real textSize

    Rectangle {
        width: card.barWidth * 1.25
        height: parent.height
        radius: card.barWidth * 0.15
        color: card.colors.alertBar
    }

    Rectangle {
        id: panel
        x: card.barWidth
        width: parent.width - x
        height: parent.height
        radius: card.barWidth * 0.15
        color: card.colors.alertCard

        Column {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.margins: card.titleSize * 0.45
            anchors.verticalCenter: parent.verticalCenter
            spacing: card.textSize * 0.25

            Text {
                id: title
                width: parent.width
                textFormat: Text.StyledText
                text: "No " + Messages.routeBullets(card.alert.routes, card.bulletsUrl, Math.round(card.titleSize * 0.95))
                    + " trains here"
                wrapMode: Text.WordWrap
                font.family: "Roboto"
                font.weight: Font.Bold
                font.pixelSize: card.titleSize
                color: card.colors.alertText
            }

            Text {
                width: parent.width
                textFormat: Text.StyledText
                text: Messages.styled(card.alert.text, card.bulletsUrl, Math.round(card.textSize * 0.95))
                wrapMode: Text.WordWrap
                elide: Text.ElideRight
                // As many lines as the card has room for under the title
                maximumLineCount: Math.max(1, Math.floor(
                    (panel.height * 0.92 - title.height - parent.spacing) / (card.textSize * 1.25)))
                font.family: "Roboto"
                font.pixelSize: card.textSize
                color: card.colors.alertText
            }
        }
    }
}
