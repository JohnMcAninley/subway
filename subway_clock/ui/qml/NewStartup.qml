import QtQuick

// A card like a train's for when there are no trains to show yet: what the
// clock is doing over a lesser line, as a train's headline is over its detail,
// and how far along it is where the minutes go.
Item {
    id: notice

    required property var startup
    required property var colors
    property bool numbered: true  // leave the space for a train's number, as NewRow does

    readonly property real unit: height  // sizes below are fractions of the line height

    Rectangle {
        x: notice.unit * (notice.numbered ? 0.4 : 0.12)
        width: parent.width - x - (notice.numbered ? 0 : notice.unit * 0.12)
        height: notice.unit * 0.92
        anchors.verticalCenter: parent.verticalCenter
        color: notice.colors.card

        Column {
            anchors.left: parent.left
            anchors.leftMargin: notice.unit * 0.2
            anchors.right: percent.left
            anchors.rightMargin: notice.unit * 0.1
            anchors.verticalCenter: parent.verticalCenter
            spacing: -notice.unit * 0.04

            Text {
                width: parent.width
                text: notice.startup.title
                elide: Text.ElideRight
                font.family: "Roboto"
                font.weight: Font.Bold
                font.pixelSize: notice.unit * 0.4
                color: notice.colors.text
            }

            Text {
                width: parent.width
                visible: text !== ""
                text: notice.startup.detail
                elide: Text.ElideRight
                font.family: "Roboto"
                font.pixelSize: notice.unit * 0.22
                color: notice.colors.text
            }
        }

        Text {
            id: percent
            anchors.right: parent.right
            anchors.rightMargin: notice.unit * 0.2
            anchors.verticalCenter: parent.verticalCenter
            text: notice.startup.state === "loading" && notice.startup.progress >= 0
                ? Math.round(notice.startup.progress * 100) + "%" : ""
            font.family: "Roboto"
            font.weight: Font.Bold
            font.pixelSize: notice.unit * 0.5
            color: notice.colors.text
        }
    }
}
