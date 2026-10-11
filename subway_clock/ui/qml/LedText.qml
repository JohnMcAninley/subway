import QtQuick
import "LedFont.js" as LedFont

// A text in the LED signs' lettering, drawn one pixel per dot and as wide as it needs
Canvas {
    id: label

    property string text: ""
    property color color

    width: LedFont.width(text)
    height: LedFont.height
    smooth: false
    antialiasing: false

    onTextChanged: requestPaint()
    onColorChanged: requestPaint()

    onPaint: {
        var ctx = getContext("2d")
        ctx.clearRect(0, 0, width, height)
        ctx.fillStyle = color
        var runs = LedFont.runs(text)
        for (var i = 0; i < runs.length; i++)
            ctx.fillRect(runs[i][0], runs[i][1], runs[i][2], 1)
    }
}
