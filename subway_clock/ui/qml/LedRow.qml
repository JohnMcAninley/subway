import QtQuick
import "LedFont.js" as LedFont

// One line of the LED sign, drawn one pixel per dot: "1.(bullet)Destination   3min"
Canvas {
    id: row

    required property var train
    required property var colors

    // An arriving train's whole line changes colour, bullet and all.
    readonly property color textColor: train.arriving ? colors.arriving : colors.text

    readonly property int textY: 2  // the top of a capital; descenders reach the line's last row
    readonly property string number: train.number + "."
    readonly property string minutes: train.minutes + "min"
    // The bullets line up while the numbers have one digit, and the terminals always do.
    readonly property int bulletX: 1 + Math.max(LedFont.width("0."), LedFont.width(number)) + 2
    readonly property int destinationX: bulletX + LedFont.bulletSize + 3
    // Room for the terminal beside two digits of minutes, so its name doesn't change as the train nears.
    readonly property int destinationWidth: width - 1 - LedFont.width("00min") - 4 - destinationX
    readonly property string destination: LedFont.fit(train.destination, destinationWidth)

    // Everything the line shows; the board is republished more often than that changes.
    readonly property string content: [number, train.bullet, destination, minutes, textColor].join("|")
    onContentChanged: requestPaint()

    smooth: false
    antialiasing: false

    onPaint: {
        var ctx = getContext("2d")
        ctx.clearRect(0, 0, width, height)

        function draw(runs, x, y, color) {
            ctx.fillStyle = color
            for (var i = 0; i < runs.length; i++)
                ctx.fillRect(x + runs[i][0], y + runs[i][1], runs[i][2], 1)
        }

        draw(LedFont.runs(number), bulletX - 2 - LedFont.width(number), textY, textColor)
        draw(LedFont.bulletRuns(train.bullet), bulletX, 0, textColor)
        draw(LedFont.runs(destination), destinationX, textY, textColor)
        draw(LedFont.runs(minutes), width - 1 - LedFont.width(minutes), textY, textColor)
    }
}
