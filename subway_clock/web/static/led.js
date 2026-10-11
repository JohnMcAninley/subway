import { el, percent } from "./dom.js"

// The LED signs on the numbered lines: a matrix of dots, 16 rows to a line.
// The board is drawn on a canvas at one pixel per dot, scaled up, and covered
// with a mask that leaves a round hole over each dot. With showStation, the
// top names the station. The layout is ui/qml/LedBoard.qml's and LedRow.qml's.
export function ledBoard(root) {
    const canvas = el("canvas"), mask = el("div", "mask")
    const frame = el("div", "frame", canvas, mask)
    root.append(frame)
    const context = canvas.getContext("2d")
    const colors = Styles.colors.led

    // The real 2-line signs are about 192 dots wide, and so is this, with black
    // above and below on a taller screen.
    const columns = 192, lineDots = 16
    const textY = 2  // the top of a capital; descenders reach the line's last row

    const board = { lines: 2, grouped: false, draw }

    function dots(runs, x, y, color) {
        context.fillStyle = color
        runs.forEach(run => context.fillRect(x + run[0], y + run[1], run[2], 1))
    }

    function text(string, x, y, color) {
        dots(LedFont.runs(string), x, y, color)
    }

    // One line: "1.(bullet)Destination   3min". An arriving train's whole line changes colour, bullet and all.
    function train(row, y) {
        const color = row.arriving ? colors.arriving : colors.text
        const number = row.number + ".", minutes = row.minutes + "min"
        // The bullets line up while the numbers have one digit, and the terminals always do.
        const bulletX = 1 + Math.max(LedFont.width("0."), LedFont.width(number)) + 2
        const destinationX = bulletX + LedFont.bulletSize + 3
        // Room for the terminal beside two digits of minutes, so its name doesn't change as the train nears.
        const destinationWidth = columns - 1 - LedFont.width("00min") - 4 - destinationX
        text(number, bulletX - 2 - LedFont.width(number), y + textY, color)
        dots(LedFont.bulletRuns(row.bullet), bulletX, y, color)
        text(LedFont.fit(row.destination, destinationWidth), destinationX, y + textY, color)
        text(minutes, columns - 1 - LedFont.width(minutes), y + textY, color)
    }

    function draw(state, width, height) {
        const drawn = state.board, startup = state.startup
        const pitch = Math.max(1, Math.floor(width / columns))
        const slots = Math.floor(height / (lineDots * pitch))  // lines the screen has room for

        // The station's routes go beside its name if they fit there, abbreviating it if that
        // is what it takes, or on a line of their own if that still leaves two lines for
        // trains; failing both they are left out.
        // Stations with different names are too much for a sign this narrow: the first stands for them.
        const station = LedFont.width(drawn.station) <= columns - 2 ? drawn.station : drawn.station.split(" / ")[0]
        const bulletsDots = drawn.routes.length * (LedFont.bulletSize + 1)
        const besideBullets = LedFont.shortened(station, columns - 2 - 4 - bulletsDots)
        const bulletsBeside = bulletsDots > 0 && besideBullets !== ""
        const stationText = bulletsBeside ? besideBullets : LedFont.fit(station, columns - 2)
        const stationDots = LedFont.width(stationText)
        const headerLines = !(state.showStation && station) ? 0 : bulletsDots > 0 && !bulletsBeside && slots >= 4 ? 2 : 1
        const bulletsShown = bulletsBeside || headerLines === 2
        // What the header's last line holds before the direction, which goes at its right if there is room
        const headerDots = headerLines === 2 ? bulletsDots : stationDots + (bulletsBeside ? 4 + bulletsDots : 0)

        // As in the other styles, wide screens get 2 lines and taller ones more, like the
        // 4-line signs on mezzanines.
        const lines = board.lines = Math.max(1, Math.min(10, Math.round(height / (width / 7.5)), slots - headerLines))

        // Whole pixels, so the dots stay sharp
        const rows = (lines + headerLines) * lineDots
        frame.style.width = columns * pitch + "px"
        frame.style.height = rows * pitch + "px"
        frame.style.left = Math.floor((width - columns * pitch) / 2) + "px"
        frame.style.top = Math.floor((height - rows * pitch) / 2) + "px"
        mask.hidden = pitch < 3  // smaller dots than that are just pixels
        mask.style.backgroundSize = pitch + "px " + pitch + "px"
        if (canvas.width !== columns || canvas.height !== rows) {
            canvas.width = columns
            canvas.height = rows
        }
        context.fillStyle = colors.background  // unlit dots are faintly visible
        context.fillRect(0, 0, columns, rows)

        // The station, its routes and the direction
        if (headerLines > 0) {
            const lastY = (headerLines - 1) * lineDots
            text(stationText, 1, textY, colors.text)
            if (bulletsShown) {
                drawn.routes.forEach(function (route, i) {
                    dots(LedFont.bulletRuns(route.bullet),
                         (bulletsBeside ? 1 + stationDots + 4 : 1) + i * (LedFont.bulletSize + 1), lastY, colors.text)
                })
            }
            const directionDots = LedFont.width(drawn.direction)
            if (1 + headerDots + 6 + directionDots + 1 <= columns)
                text(drawn.direction, columns - 1 - directionDots, lastY + textY, colors.text)
        }

        drawn.rows.forEach((row, i) => train(row, (i + headerLines) * lineDots))

        // Before there are trains to show: what the clock is doing on the first line, with
        // how far along it is where the minutes go, and a second line under it
        if (startup.state !== "ready") {
            [{ text: startup.title, value: percent(startup) }, { text: startup.detail, value: "" }]
                .slice(0, lines).forEach(function (notice, i) {
                    const y = (i + headerLines) * lineDots + textY, valueDots = LedFont.width(notice.value)
                    text(LedFont.fit(notice.text, columns - 2 - (valueDots ? valueDots + 3 : 0)), 1, y, colors.text)
                    text(notice.value, columns - 1 - valueDots, y, colors.text)
                })
        }
    }

    return board
}
