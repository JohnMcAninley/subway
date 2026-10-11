import { bullet, el, list, percent, setBullet, setBullets, setMessage, setText, vars } from "./dom.js"

// The newer clocks: a numbered card per train on a black screen, and the
// portrait screens in station entrances. The sizes are those of
// ui/qml/NewBoard.qml, NewPortraitBoard.qml and what they draw with.

// One line: the number, then a card with the bullet, the headline over its
// detail, and the minutes over "MIN". `numbered` is whether the train's number
// goes to the left of the card, as on the platform clocks.
function newRow(numbered) {
    const number = el("span"), image = bullet(), headline = el("div", "headline"), detail = el("div", "detail")
    const minutes = el("div", "value")
    const content = el("div", "content", image, el("div", "words", headline, detail),
                       el("div", "minutes", minutes, el("div", "label", "MIN")))
    const element = el("div", "new-row" + (numbered ? " numbered" : ""))
    if (numbered)
        element.append(el("div", "number", number))
    element.append(el("div", "card", content))

    // What is drawn (shown) trails the line's train (wanted) while the line rotates.
    let shown = null, wanted = null, rotating = false

    function show(train) {
        shown = train
        element.classList.toggle("arriving", train.arriving)
        setText(number, train.number)
        setBullet(image, train.bullet)
        setText(headline, train.headline)
        setText(detail, train.detail)
        detail.hidden = train.detail === ""
        setText(minutes, train.minutes)
    }

    // The old train dims and its number rolls away upwards; the new one arrives from below.
    async function rotate() {
        rotating = true
        const roll = number.parentElement.clientHeight * 0.6
        const leave = { duration: 220, easing: "cubic-bezier(0.55, 0.085, 0.68, 0.53)", fill: "forwards" }
        const arrive = { duration: 220, easing: "cubic-bezier(0.25, 0.46, 0.45, 0.94)" }
        const going = [content.animate({ opacity: [1, 0.25] }, leave),
                       number.animate({ transform: ["translateY(0)", "translateY(" + -roll + "px)"] }, leave)]
        await Promise.all(going.map(animation => animation.finished))
        show(wanted)
        going.forEach(animation => animation.cancel())
        await Promise.all([content.animate({ opacity: [0.25, 1] }, arrive),
                           number.animate({ transform: ["translateY(" + roll + "px)", "translateY(0)"] }, arrive)]
            .map(animation => animation.finished))
        rotating = false
        if (wanted && wanted !== shown)
            show(wanted)
    }

    // `animated`: show a change of train as the line rotating
    function set(train, animated) {
        const same = shown && train.number === shown.number && train.route === shown.route
            && train.destination === shown.destination
        wanted = train
        if (animated && shown && !same && !rotating)
            rotate()
        else if (!rotating)
            show(train)
    }

    // The line has no train: the next one it gets doesn't rotate in.
    function clear() {
        shown = wanted = null
    }

    return { element, set, clear }
}

// A card like a train's for when there are no trains to show yet: what the
// clock is doing over a lesser line, and how far along it is where the minutes go.
function newNotice(numbered) {
    const title = el("div", "headline"), detail = el("div", "detail"), progress = el("div", "percent")
    const element = el("div", "new-row notice" + (numbered ? " numbered" : ""))
    if (numbered)
        element.append(el("div", "number"))
    element.append(el("div", "card", el("div", "content", el("div", "words", title, detail), progress)))

    function set(startup) {
        element.hidden = startup.state === "ready"
        setText(title, startup.title)
        setText(detail, startup.detail)
        detail.hidden = startup.detail === ""
        setText(progress, percent(startup))
    }

    return { element, set }
}

// The alert that takes over when no trains are coming and it says why: the
// card that otherwise takes the last line, grown to hold a bold title over
// the alert's own words.
function noService() {
    const title = el("div", "title"), text = el("div", "text")
    const panel = el("div", "panel", el("div", "words", title, text))
    const element = el("div", "no-service", el("div", "bar"), panel)

    // alert: one of the board's messages, or nothing to hide the card
    function set(alert, barWidth, titleSize, textSize) {
        element.hidden = !alert
        if (!alert)
            return
        vars(element, { bar: barWidth, "title-size": titleSize, "text-size": textSize })
        const routes = alert.routes.map(route => route.bullet)
        if (title.dataset.routes !== routes.join(" ")) {
            title.dataset.routes = routes.join(" ")
            title.replaceChildren("No ", ...routes.map(asset => bullet(asset, "inline-bullet")), " trains here")
        }
        setMessage(text, alert.text)
        // As many lines as the card has room for under the title
        text.style.setProperty("--max-lines", Math.max(1, Math.floor(
            (panel.clientHeight * 0.92 - title.offsetHeight - textSize * 0.25) / (textSize * 1.25))))
    }

    return { element, set }
}

// The alert on the last line now, when it is to fill the screen instead
function takeover(drawn) {
    return drawn.takeover ? drawn.messages.find(message => message.text === drawn.message) : undefined
}

// The newer clocks on a wide screen. Service alerts take turns with the trains
// on the last line, and one saying why no trains are coming takes the whole
// screen. With showStation, a line above them names the station.
export function newBoard(root) {
    const station = el("span", "station"), bullets = el("span", "bullets"), direction = el("span", "direction")
    const header = el("div", "header", station, bullets, direction)
    const lines = el("div", "lines")
    const notice = newNotice(true)
    notice.element.classList.add("startup")
    const alertText = el("div", "text")
    const alert = el("div", "alert", el("div", "bar"), el("div", "panel", alertText))
    const filling = noService()
    const staleText = el("span")
    const stale = el("div", "stale", staleText)
    root.append(header, lines, notice.element, alert, filling.element, stale)

    // One part per line, kept as trains come and go, so the last line can animate its rotation
    const setLines = list(lines, function () {
        const row = newRow(true)
        return {
            element: el("div", "slot", row.element),
            set(item) {
                row.element.hidden = !item.train
                if (item.train)
                    row.set(item.train, item.animated)
                else
                    row.clear()
            },
        }
    })

    const board = { lines: 2, grouped: false, draw }

    function draw(state, width, height, staleMessage) {
        const drawn = state.board
        // As many lines as fit at the real clocks' proportions (2 on their ~3.5:1
        // screens, 4 at 16:9), up to 10 on tall portrait screens.
        const count = board.lines = Math.max(1, Math.min(10, Math.round(height / (width / 7))))
        const staleHeight = drawn.stale ? Math.min(height * 0.1, width * 0.035) : 0
        const headerHeight = state.showStation && drawn.station ? Math.min(height * 0.14, width * 0.05) : 0
        const rowHeight = (height - headerHeight - staleHeight) / count
        vars(root, { u: rowHeight, header: headerHeight, stale: staleHeight })
        root.style.setProperty("--lines", count)

        header.hidden = headerHeight === 0
        setText(station, drawn.station)
        setBullets(bullets, drawn.routes.map(route => route.bullet))
        setText(direction, drawn.direction)

        setLines(Array.from({ length: count }, (_, i) => (
            { train: drawn.rows[i], animated: count > 1 && i === count - 1 })))
        notice.set(state.startup)

        // A service alert in place of the last line: two lines at the design's size, or
        // three smaller ones for a long alert
        const fills = takeover(drawn)
        alert.hidden = drawn.message === "" || !!fills
        alert.classList.toggle("lengthy", drawn.message.length > 70)
        setMessage(alertText, drawn.message)

        // No trains are coming, and this alert says why: it has every line. Its title is
        // the headlines' size where there is room.
        const unit = Math.min(rowHeight, (count * rowHeight - rowHeight * 0.08) / 2)
        filling.set(fills, rowHeight * 0.4, unit * 0.4, unit * 0.3)

        stale.hidden = !drawn.stale
        setText(staleText, staleMessage)
    }

    return board
}

// One of the portrait screen's lines: a train's card, or the heading over a direction's trains.
function portraitEntry() {
    const heading = el("div", "heading"), row = newRow(false)
    const element = el("div", "entry", heading, row.element)

    function set(entry) {
        heading.hidden = !!entry.train
        row.element.hidden = !entry.train
        if (entry.train)
            row.set(entry.train, false)
        else
            setText(heading, entry.heading || "")
    }

    return { element, set }
}

// One of the portrait screen's alerts: the bullets of its routes with a badge on the
// corner of the last, a title and how long ago it was changed, beside its text.
function portraitAlert() {
    const marks = el("span", "bullets"), badge = el("div", "badge", el("i", "", "!"))
    const title = el("div", "title"), updated = el("div", "updated"), text = el("div", "text")
    const element = el("div", "alert", el("div", "rule"), el("div", "columns",
        el("div", "about", el("div", "marks", marks, badge), title, updated), text))

    function set(alert) {
        const routes = alert.routes.slice(0, 4).map(route => route.bullet)
        setBullets(marks, routes)
        marks.hidden = routes.length === 0
        badge.classList.toggle("alone", routes.length === 0)
        setText(title, alert.title)
        setText(updated, alert.updated)
        updated.hidden = alert.updated === ""
        setMessage(text, alert.text)
    }

    return { element, set }
}

// The portrait screens in station entrances and mezzanines: the time, a card
// per train (under a heading per direction when there is more than one), and
// the service alerts at the bottom. When no trains are coming, the alert
// saying why has their place. With showStation, the station's name goes beside
// the time, with its routes' bullets and the direction under it.
export function newPortraitBoard(root) {
    const station = el("div", "station"), time = el("span", "time"), seconds = el("span", "seconds")
    const header = el("div", "header", station, el("div", "now", time, seconds))
    const bullets = el("span", "bullets"), direction = el("span", "direction")
    const entrance = el("div", "entrance", bullets, direction)
    const trains = el("div", "trains")
    const notice = newNotice(false)
    notice.element.classList.add("startup")
    const filling = noService()
    const alerts = el("div", "alerts")
    root.append(header, entrance, el("div", "below", trains, notice.element, filling.element),
                el("div", "alert-panel", el("div", "caption", "Service alerts"), alerts))
    const alertPanel = alerts.parentElement
    const setTrains = list(trains, portraitEntry)
    const setAlerts = list(alerts, portraitAlert)

    function tick() {
        const now = new Date()
        setText(time, now.getHours() + ":" + String(now.getMinutes()).padStart(2, "0"))
        setText(seconds, ":" + String(now.getSeconds()).padStart(2, "0"))
    }
    tick()
    const timer = setInterval(() => header.isConnected ? tick() : clearInterval(timer), 250)

    const board = { lines: 4, grouped: true, draw }

    function draw(state, width, height, staleMessage) {
        const drawn = state.board
        const unit = width / 1080  // the real screens are 1080x1920
        const rowHeight = unit * 165
        const entranceHeight = state.showStation && drawn.routes.length > 0 ? unit * 76 : 0
        const top = unit * 105 + entranceHeight
        // Trains fill about the top half, as on the real screens: 5 lines at 9:16.
        board.lines = Math.max(2, Math.min(8, Math.floor((height * 0.52 - top) / rowHeight)))
        vars(root, { p: unit, u: rowHeight })

        // The station's name shrinks to fit beside the time, down to a point
        station.hidden = !state.showStation
        setText(station, drawn.station)
        station.style.fontSize = ""
        if (!station.hidden && station.scrollWidth > station.clientWidth)
            station.style.fontSize = Math.max(32, 46 * station.clientWidth / station.scrollWidth) * unit + "px"

        // The station's routes, and the direction when the screen shows only one
        entrance.hidden = entranceHeight === 0
        setBullets(bullets, drawn.routes.map(route => route.bullet))
        setText(direction, drawn.direction)

        // The trains, with a heading before those of each direction
        const entries = drawn.groups.length
            ? drawn.groups.flatMap(group => [{ heading: group.heading }].concat(group.rows.map(row => ({ train: row }))))
            : drawn.rows.map(row => ({ train: row }))
        setTrains(entries)
        notice.set(state.startup)

        // The alert that has the trains' place, when none are coming and it says why
        const fills = takeover(drawn)
        filling.set(fills, unit * 40, unit * 58, unit * 42)

        // The other alerts, as many as fit below the trains at about 230 units each. The
        // stale data warning comes first.
        const trainsHeight = entries.reduce((sum, entry) => sum + (entry.train ? rowHeight : unit * 62), 0)
        const room = Math.max(1, Math.floor(
            (height - top - Math.max(trainsHeight, fills ? rowHeight * 2.4 : 0) - unit * 200) / (unit * 230)))
        const shown = (drawn.stale ? [{ title: "Delayed", text: staleMessage, routes: [], updated: "" }] : [])
            .concat(drawn.messages.filter(message => message !== fills).map(message => ({
                title: message.title || (message.planned ? "Planned work" : "Service change"), text: message.text,
                routes: message.routes, updated: Messages.updated(message.updated_minutes) })))
        alertPanel.hidden = shown.length === 0
        setAlerts(shown.slice(0, room))
    }

    return board
}
