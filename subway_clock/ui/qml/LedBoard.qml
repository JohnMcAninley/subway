import QtQuick
import "LedFont.js" as LedFont
import "Styles.js" as Styles

// The LED signs on the numbered lines: a matrix of red, green and amber dots,
// 16 rows to a line. The board is drawn at one pixel per dot, scaled up, and
// covered with a mask that leaves a round hole over each dot.
Rectangle {
    id: root

    required property var board
    required property url bulletsUrl
    required property string staleMessage  // these signs have nowhere to show messages
    required property var startup

    readonly property var colors: Styles.colors.led

    // The real 2-line signs are about 192 dots wide, and so is this, with black
    // above and below on a taller screen. As in the other styles, wide screens
    // get 2 lines and taller ones more, like the 4-line signs on mezzanines.
    readonly property int columns: 192
    readonly property int lineDots: 16
    readonly property int pitch: Math.max(1, Math.floor(width / columns))
    readonly property int lines: width > 0 && height > 0
        ? Math.max(1, Math.min(10, Math.round(height / (width / 7.5)), Math.floor(height / (lineDots * pitch)))) : 2

    color: "black"

    Item {
        // Whole pixels, so the dots stay sharp
        x: Math.floor((root.width - width) / 2)
        y: Math.floor((root.height - height) / 2)
        width: root.columns * root.pitch
        height: root.lines * root.lineDots * root.pitch

        Rectangle {
            id: matrix
            width: root.columns
            height: root.lines * root.lineDots
            color: root.colors.background  // unlit dots are faintly visible
            layer.enabled: true
            layer.smooth: false
            layer.textureSize: Qt.size(width, height)
            transform: Scale { xScale: root.pitch; yScale: root.pitch }

            Repeater {
                model: root.board.rows

                LedRow {
                    required property var modelData
                    required property int index

                    y: index * root.lineDots
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

                    y: index * root.lineDots
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
