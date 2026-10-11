import QtQuick
import "Styles.js" as Styles

// The LED signs on the numbered lines: a matrix of red, green and amber dots,
// 16 rows to a line. The board is drawn at one pixel per dot, scaled up, and
// covered with a mask that leaves a round hole over each dot.
Rectangle {
    id: root

    required property var board
    required property url bulletsUrl
    required property string staleMessage  // these signs have nowhere to show messages

    readonly property var colors: Styles.colors.led

    // The real 2-line signs are about 192 dots wide. Taller screens get more
    // lines, like the 4-line signs on mezzanines.
    readonly property int columns: 192
    readonly property int lineDots: 16
    readonly property int pitch: Math.max(1, Math.floor(width / columns))
    readonly property int lines: width > 0 && height > 0
        ? Math.max(1, Math.min(10, Math.floor(height / (lineDots * pitch)))) : 2

    color: "black"

    Item {
        anchors.centerIn: parent
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
        }

        Image {
            anchors.fill: parent
            visible: root.pitch >= 3  // smaller dots than that are just pixels
            source: root.bulletsUrl + "../led-dot.svg"
            sourceSize: Qt.size(root.pitch, root.pitch)
            fillMode: Image.Tile
            smooth: false
        }
    }
}
