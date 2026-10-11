import { bullet, el, list, percent, setBullet, setBullets, setText, vars } from "./dom.js"

// The classic LCD clock: lines of "1. (bullet) Destination   3 min" over a
// strip with the time and scrolling service alerts. With showStation, a strip
// across the top names the station. The sizes are ui/qml/ClassicBoard.qml's.
export function classicBoard(root) {
    const station = el("span", "station"), bullets = el("span", "bullets"), direction = el("span", "direction")
    const header = el("div", "header", station, bullets, direction)
    const rows = el("div", "rows")
    const strip = statusStrip()
    root.append(header, rows, strip.element)
    const setRows = list(rows, classicRow)

    const board = { lines: 2, grouped: false, draw }

    function draw(state, width, height, staleMessage) {
        const drawn = state.board, startup = state.startup
        // As many lines as fit at the real clocks' proportions (2 on their ~3.8:1
        // screens, 4 at 16:9), up to 10 on tall portrait screens.
        const statusHeight = Math.min(height * 0.12, width * 0.04)
        board.lines = Math.max(1, Math.min(10, Math.round((height - statusHeight) / (width / 8))))
        const headerHeight = state.showStation && drawn.station ? Math.min(height * 0.14, width * 0.07) : 0
        const rowHeight = (height - headerHeight - statusHeight) / board.lines
        // Text is sized from the width, so destinations fit, unless the lines are too short for it.
        const fontSize = Math.min(rowHeight * 0.5, width * 0.057)
        vars(root, { status: statusHeight, header: headerHeight, row: rowHeight, font: fontSize,
                     rule: Math.max(1, fontSize * 0.02) })

        // Before there are trains to show: what the clock is doing on the first line, with how
        // far along it is where the minutes go, and a second line under it
        const notices = startup.state === "ready" ? [] : [
            { text: startup.title, value: percent(startup) }, { text: startup.detail, value: "" }]
        setRows(Array.from({ length: board.lines }, (_, i) => ({ train: drawn.rows[i], notice: notices[i] })))

        // The station, then its routes' bullets, and the direction at the right if there is room
        header.hidden = headerHeight === 0
        if (!header.hidden) {
            setText(station, drawn.station)
            setBullets(bullets, drawn.routes.map(route => route.bullet))
            setText(direction, drawn.direction)
            direction.hidden = false
            direction.hidden = station.scrollWidth + bullets.offsetWidth + direction.offsetWidth
                + fontSize * 0.3 * 4 > width
        }

        strip.set((drawn.stale ? [staleMessage] : []).concat(drawn.messages.map(message => message.text)),
                  statusHeight)
    }

    return board
}

// One line of the classic clock: a train, or before there are any, what the clock is doing.
function classicRow() {
    const number = el("span", "number"), image = bullet(), destination = el("span", "destination")
    const minutes = el("span", "minutes")
    const train = el("div", "train", number, image, destination, minutes, el("span", "min", "min"))
    const text = el("span", "text"), value = el("span", "value")
    const notice = el("div", "notice", text, value)
    const element = el("div", "row", train, notice)

    function set(item) {
        train.hidden = !item.train
        notice.hidden = !item.notice
        element.classList.toggle("arriving", !!item.train && item.train.arriving)
        if (item.train) {
            setText(number, item.train.number + ".")
            setBullet(image, item.train.bullet)
            setText(destination, item.train.destination)
            setText(minutes, item.train.minutes)
        }
        if (item.notice) {
            setText(text, item.notice.text)
            setText(value, item.notice.value)
        }
    }

    return { element, set }
}

// Bottom strip: the time in a box, then the messages scrolling past.
function statusStrip() {
    const time = el("div", "time"), scrolling = el("div", "scrolling"), ticker = el("div", "ticker", scrolling)
    const element = el("div", "strip", time, ticker)
    let shown = null, running = "", scroll = null

    function tick() {
        const now = new Date()
        setText(time, (now.getHours() % 12 || 12) + ":" + String(now.getMinutes()).padStart(2, "0")
            + (now.getHours() < 12 ? " AM" : " PM"))
    }
    tick()
    const timer = setInterval(() => element.isConnected ? tick() : clearInterval(timer), 1000)

    function set(messages, height) {
        // The board comes again every second; the ticker only starts over when its text or its size changes.
        const text = messages.filter(message => message !== "").join("\n")
        if (text !== shown) {
            shown = text
            // Pieces of text and bullets, with a gap after each message
            scrolling.replaceChildren(...(text ? text.split("\n") : []).flatMap(message => Messages.pieces(message)
                .map(piece => piece.bullet ? bullet(piece.bullet) : el("span", "", piece.text))
                .concat([el("span", "gap")])))
        }
        const from = ticker.clientWidth, length = scrolling.offsetWidth
        const run = [text, from, length, height].join("|")
        if (run === running)
            return
        running = run
        if (scroll)
            scroll.cancel()
        // In from the right and out to the left, at a steady speed whatever the length.
        scroll = text && from > 0 ? scrolling.animate(
            [{ transform: "translateX(" + from + "px)" }, { transform: "translateX(" + -length + "px)" }],
            { duration: Math.max(1, (from + length) / (height * 4) * 1000), iterations: Infinity }) : null
    }

    return { element, set }
}
