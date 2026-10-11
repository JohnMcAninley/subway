import { classicBoard } from "./classic.js"
import { ledBoard } from "./led.js"
import { keyName, settingsMenu } from "./menu.js"
import { newBoard, newPortraitBoard } from "./new.js"

// Draws the clock's Board in its style, as ui/qml/Main.qml does. No train logic
// here: which trains appear on which line is decided in Python, and fetched
// from the server (web/server.py) about once a second. Each style's board
// works out how many lines fit the screen (and whether to group them by
// direction), and that goes with the request. Until there is a board to draw,
// each style shows the state's startup. Keys and clicks go to the settings
// menu, which is Python's too (ui/menu.py).

const STALE = "Live train times are delayed. Times shown may be out of date."
const POLL_MS = 1000
// With no word from the server for this long, the board on the screen is marked stale.
const LOST_MS = 15000

const root = document.getElementById("clock")
const menu = settingsMenu(document.getElementById("menu"), act)
const boards = { classic: classicBoard, led: ledBoard, new: newBoard, "new-portrait": newPortraitBoard }

let state = null
let kind = "", board = null
let asked = ""  // the layout the state was asked for with
let heard = Date.now()  // when the server last answered
let sent = 0, answered = 0  // requests are numbered, so an answer overtaken by a later one is dropped
let acting = Promise.resolve()

// The styles' colours, for the stylesheet: --classic-background and so on
for (const [style, colors] of Object.entries(Styles.colors)) {
    for (const [name, color] of Object.entries(colors))
        document.documentElement.style.setProperty("--" + style + "-" + name, color)
}

function layout() {
    return board ? "lines=" + board.lines + "&grouped=" + (board.grouped ? 1 : 0) : "lines=2&grouped=0"
}

function render() {
    const width = root.clientWidth, height = root.clientHeight
    if (!state || !width || !height)
        return
    const style = state.board.style
    const wanted = style === "classic" || style === "led" ? style : height > width * 1.3 ? "new-portrait" : "new"
    if (wanted !== kind) {
        kind = wanted
        root.replaceChildren()
        root.removeAttribute("style")
        root.className = kind
        board = boards[kind](root)
    }
    board.draw(state, width, height, STALE)
    menu.draw(state.menu, width, height)
}

// What to draw when the server can't be reached: before it has ever answered, a start
// that has failed; after, the last board, marked stale once it has been a while.
function lost() {
    if (!state) {
        state = {
            board: { style: "classic", rows: [], stale: false, messages: [], message: "", takeover: false, groups: [],
                     station: "", direction: "", routes: [] },
            startup: { state: "failed", title: "No connection", detail: "Trying again shortly", progress: 0 },
            showStation: false,
            menu: { open: false },
        }
    } else if (Date.now() - heard > LOST_MS && state.startup.state === "ready") {
        state = { ...state, board: { ...state.board, stale: true } }
    }
}

// Fetch the state and draw it, first passing `action` on to the settings menu if there is one.
async function poll(action) {
    const number = ++sent, query = layout()
    let next = null
    try {
        const response = await fetch(action ? "api/menu?" + query : "api/state?" + query, action
            ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(action) }
            : { cache: "no-store" })
        if (!response.ok)
            throw new Error(response.statusText)
        next = await response.json()
    } catch (error) {
        console.warn("Can't reach the clock:", error)
    }
    if (number < answered)
        return
    answered = number
    if (next) {
        state = next
        asked = query
        heard = Date.now()
    } else {
        lost()
    }
    render()
    // The state says which style to draw, and the style how many lines to ask for.
    if (next && layout() !== asked)
        poll()
}

// Something done to the settings menu: { key }, { click }, { back } or { scroll }, as the server's
// Service.act takes them. One at a time, so they arrive in the order they were done.
function act(action) {
    acting = acting.then(() => poll(action))
}

document.addEventListener("keydown", function (event) {
    const key = keyName(event)
    const open = state && state.menu.open
    if (!key || !(open || ["enter", "m", "M"].includes(key)))
        return
    event.preventDefault()
    act({ key })
})

// A click on the clock opens the menu.
root.addEventListener("click", () => act({ click: null }))

new ResizeObserver(function () {
    render()
    if (state && layout() !== asked)
        poll()
}).observe(root)

// Text is measured to lay it out, so the font comes first.
Promise.all(["400", "500", "700"].map(weight => document.fonts.load(weight + " 16px Roboto"))).catch(() => {})
    .then(function () {
        poll()
        setInterval(() => poll(), POLL_MS)
    })
