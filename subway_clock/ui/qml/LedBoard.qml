import QtQuick
import "LedFont.js" as LedFont
import "Styles.js" as Styles

// The LED signs on the numbered lines: a matrix of red, green and amber dots,
// 16 rows to a line. The board is drawn at one pixel per dot, scaled up, and
// covered with a mask that leaves a round hole over each dot. With
// showStation, the top names the station as the sign over an entrance does;
// the real signs don't.
Rectangle {
    id: root

    required property var board
    required property url bulletsUrl
    required property string staleMessage  // these signs have nowhere to show messages
    required property bool showStation
    required property var startup

    readonly property var colors: Styles.colors.led

    // The real 2-line signs are about 192 dots wide, and so is this, with black
    // above and below on a taller screen. As in the other styles, wide screens
    // get 2 lines and taller ones more, like the 4-line signs on mezzanines.
    readonly property int columns: 192
    readonly property int lineDots: 16
    readonly property int pitch: Math.max(1, Math.floor(width / columns))
    readonly property int slots: Math.floor(height / (lineDots * pitch))  // lines the screen has room for

    // The station's routes go beside its name if they fit there, abbreviating it if that
    // is what it takes, or on a line of their own if that still leaves two lines for
    // trains; failing both they are left out.
    // Stations with different names are too much for a sign this narrow: the first stands for them.
    readonly property string station: LedFont.width(board.station) <= columns - 2
        ? board.station : board.station.split(" / ")[0]  // these two only change when their values do,
    readonly property int routeCount: board.routes.length  // so a new board doesn't lay the header out again
    readonly property string besideBullets: LedFont.shortened(station, columns - 2 - 4 - bulletsDots)
    readonly property int stationDots: LedFont.width(stationText)
    readonly property int bulletsDots: routeCount * (LedFont.bulletSize + 1)
    readonly property bool bulletsBeside: bulletsDots > 0 && besideBullets !== ""
    readonly property string stationText: bulletsBeside ? besideBullets : LedFont.fit(station, columns - 2)
    readonly property int headerLines: !(showStation && station) ? 0
        : bulletsDots > 0 && !bulletsBeside && slots >= 4 ? 2 : 1
    readonly property bool bulletsShown: bulletsBeside || headerLines === 2
    // What the header's last line holds before the direction, which goes at its right if there is room
    readonly property int headerDots: headerLines === 2 ? bulletsDots : stationDots + (bulletsBeside ? 4 + bulletsDots : 0)

    readonly property int lines: width > 0 && height > 0
        ? Math.max(1, Math.min(10, Math.round(height / (width / 7.5)), slots - headerLines)) : 2

    color: "black"

    Item {
        // Whole pixels, so the dots stay sharp
        x: Math.floor((root.width - width) / 2)
        y: Math.floor((root.height - height) / 2)
        width: root.columns * root.pitch
        height: (root.lines + root.headerLines) * root.lineDots * root.pitch

        Rectangle {
            id: matrix
            width: root.columns
            height: (root.lines + root.headerLines) * root.lineDots
            color: root.colors.background  // unlit dots are faintly visible
            layer.enabled: true
            layer.smooth: false
            layer.textureSize: Qt.size(width, height)
            transform: Scale { xScale: root.pitch; yScale: root.pitch }

            // The station, its routes and the direction
            LedText {
                visible: root.headerLines > 0
                x: 1
                y: 2
                text: root.stationText
                color: root.colors.text
            }

            Canvas {
                readonly property string content: root.board.routes.map(r => r.bullet).join(" ")

                visible: root.headerLines > 0 && root.bulletsShown
                x: root.bulletsBeside ? 1 + root.stationDots + 4 : 1
                y: (root.headerLines - 1) * root.lineDots
                width: root.bulletsDots
                height: LedFont.bulletSize
                smooth: false
                antialiasing: false

                onContentChanged: requestPaint()

                onPaint: {
                    var ctx = getContext("2d")
                    ctx.clearRect(0, 0, width, height)
                    ctx.fillStyle = root.colors.text
                    root.board.routes.forEach(function (route, i) {
                        LedFont.bulletRuns(route.bullet).forEach(function (run) {
                            ctx.fillRect(i * (LedFont.bulletSize + 1) + run[0], run[1], run[2], 1)
                        })
                    })
                }
            }

            LedText {
                visible: root.headerLines > 0 && 1 + root.headerDots + 6 + width + 1 <= matrix.width
                x: matrix.width - 1 - width
                y: (root.headerLines - 1) * root.lineDots + 2
                text: root.board.direction
                color: root.colors.text
            }

            Repeater {
                model: root.board.rows

                LedRow {
                    required property var modelData
                    required property int index

                    y: (index + root.headerLines) * root.lineDots
                    width: matrix.width
                    height: root.lineDots
                    train: modelData
                    colors: root.colors
                }
            }

            // Before there are trains to show: what the clock is doing on the first line, with
            // how far along it is where the minutes go, and a second line under it
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

                    y: (index + root.headerLines) * root.lineDots
                    width: matrix.width
                    height: root.lineDots

                    LedText {
                        x: 1
                        y: 2
                        text: LedFont.fit(modelData.text, parent.width - 2 - (value.width ? value.width + 3 : 0))
                        color: root.colors.text
                    }

                    LedText {
                        id: value
                        x: parent.width - 1 - width
                        y: 2
                        text: modelData.value
                        color: root.colors.text
                    }
                }
            }
        }

        Image {
            anchors.fill: parent
            visible: root.pitch >= 3  // smaller dots than that are just pixels
            source: root.bulletsUrl + "../led-dot.svg"
            sourceSize: Qt.size(root.pitch, root.pitch)
            fillMode: Image.Tile
            // Tile from the corner, so every hole sits exactly over one dot
            horizontalAlignment: Image.AlignLeft
            verticalAlignment: Image.AlignTop
            smooth: false
        }
    }
}
