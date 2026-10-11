import QtQuick

// One line of the LED sign, drawn one pixel per dot: "1.(bullet)Destination   3min"
Item {
    id: row

    required property var train
    required property var colors

    // An arriving train's whole line changes colour; its bullet keeps the route's.
    readonly property color textColor: train.arriving ? colors.arriving : colors.text
    readonly property bool diamond: train.bullet.length > 1 && train.bullet.endsWith("d")  // express
    readonly property string letter: diamond ? train.bullet.slice(0, -1) : train.route

    component Dots: Text {
        // Without antialiasing every pixel is a dot fully on or off.
        renderType: Text.NativeRendering
        font.family: "Roboto"
        font.styleName: "Condensed Bold"  // the signs' letters are narrow, with strokes two dots wide
        font.pixelSize: 15
        antialiasing: false
        font.hintingPreference: Font.PreferFullHinting
        y: 0
        color: row.textColor
    }

    Dots {
        id: number
        x: 1
        text: row.train.number + "."
    }

    Item {
        id: bullet
        x: number.x + number.width + 1
        y: 2
        width: 13
        height: 13

        Rectangle {
            anchors.centerIn: parent
            width: row.diamond ? 10 : 13
            height: width
            radius: row.diamond ? 0 : width / 2
            rotation: row.diamond ? 45 : 0
            antialiasing: false
            color: row.colors.bullets[row.train.route] || row.colors.text
        }

        Dots {
            anchors.centerIn: parent
            text: row.letter.length === 1 ? row.letter : row.train.bullet.charAt(0)
            font.styleName: "Condensed SemiBold"
            font.pixelSize: 11
            color: row.colors.background
        }
    }

    Dots {
        anchors.left: bullet.right
        anchors.leftMargin: 3
        anchors.right: minutes.left
        anchors.rightMargin: 3
        text: row.train.destination
        elide: Text.ElideRight
    }

    Dots {
        id: minutes
        anchors.right: parent.right
        anchors.rightMargin: 1
        text: row.train.minutes + "min"
    }
}
