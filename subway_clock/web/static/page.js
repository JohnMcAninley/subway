import { classicBoard } from "./classic.js"
import { ledBoard } from "./led.js"
import { keyName, settingsMenu } from "./menu.js"
import { newBoard, newPortraitBoard } from "./new.js"

// Draws the clock's Board in its style, as ui/qml/Main.qml does. No train logic
// here: which trains appear on which line is decided by a core, which `source`
// asks for the state from about once a second. There are two: the Python one
// through the server (main.js), and the JavaScript one in the page itself
// (standalone.js). Each style's board works out how many lines fit the screen
// (and whether to group them by direction), and that goes with the request.
// Until there is a board to draw, each style shows the state's startup. Keys
// and clicks go to the core's settings menu.
//
// source(layout, action) gives the state for { lines, grouped }, first passing
// action, if there is one, to the settings menu; it throws if it can't.

const STALE = "Live train times are delayed. Times shown may be out of date."
const POLL_MS = 1000
// With no word from the source for this long, the board on the screen is marked stale.
const LOST_MS = 15000

export function startPage(source) {
    const root = document.getElementById("clock")
    const typing = typingField()
    const menu = settingsMenu(document.getElementById("menu"), act, typing.focus)
    const boards = { classic: classicBoard, led: ledBoard, new: newBoard, "new-portrait": newPortraitBoard }

    let state = null
    let kind = "", board = null
    let asked = ""  // the layout the state was asked for with
    let heard = Date.now()  // when the source last answered
    let sent = 0, answered = 0  // requests are numbered, so an answer overtaken by a later one is dropped
    let acting = Promise.resolve()

    // The styles' colours, for the stylesheet: --classic-background and so on
    for (const [style, colors] of Object.entries(Styles.colors)) {
        for (const [name, color] of Object.entries(colors))
            document.documentElement.style.setProperty("--" + style + "-" + name, color)
    }

    function layout() {
        return board ? { lines: board.lines, grouped: board.grouped } : { lines: 2, grouped: false }
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
        typing.follow(state.menu)
    }

    // What to draw when the source can't be reached: before it has ever answered, a start
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

    // Ask for the state and draw it, first passing `action` on to the settings menu if there is one.
    async function poll(action) {
        const number = ++sent, wanted = layout()
        let next = null
        try {
            next = await source(wanted, action)
        } catch (error) {
            console.warn("Can't reach the clock:", error)
        }
        if (number < answered)
            return
        answered = number
        if (next) {
            state = next
            asked = JSON.stringify(wanted)
            heard = Date.now()
        } else {
            lost()
        }
        render()
        // The state says which style to draw, and the style how many lines to ask for.
        if (next && JSON.stringify(layout()) !== asked)
            poll()
    }

    // Something done to the settings menu: { key }, { click }, { back } or { scroll }, as the server's
    // Service.act takes them. One at a time, so they arrive in the order they were done.
    function act(action) {
        acting = acting.then(() => poll(action))
    }

    typing.onKey = key => act({ key })

    document.addEventListener("keydown", function (event) {
        const key = keyName(event)
        const open = state && state.menu.open
        if (!key || !(open || ["enter", "m", "M"].includes(key)) || typing.takes(event, key))
            return
        event.preventDefault()
        act({ key })
    })

    // A click on the clock opens the menu.
    root.addEventListener("click", () => act({ click: null }))

    new ResizeObserver(function () {
        render()
        if (state && JSON.stringify(layout()) !== asked)
            poll()
    }).observe(root)

    // Text is measured to lay it out, so the font comes first.
    Promise.all(["400", "500", "700"].map(weight => document.fonts.load(weight + " 16px Roboto"))).catch(() => {})
        .then(function () {
            poll()
            setInterval(() => poll(), POLL_MS)
        })

    return { poll }
}

// A text field, out of sight, for typing a station's name on a phone or tablet: the screen
// keyboard only comes up for one. The menu focuses it when the search's line is tapped, and
// what is typed into it goes to the menu as the keys a real keyboard would send.
function typingField() {
    const input = document.createElement("input")
    input.id = "typing"
    input.autocomplete = "off"
    input.autocapitalize = "off"
    input.spellcheck = false
    input.setAttribute("aria-label", "Station name")
    document.body.append(input)
    let typed = ""  // what has been passed on of input's value
    let query = ""  // what the menu has, which may have come from a real keyboard

    const field = {
        onKey: null,

        focus() {
            if (document.activeElement !== input)
                input.value = typed = query
            input.focus({ preventScroll: true })
        },

        // Keep out of the way of anything but the search.
        follow(menu) {
            const searching = menu.open && menu.page === "search"
            query = searching ? menu.query : ""
            if (!searching && document.activeElement === input)
                input.blur()
        },

        // True if a key pressed is the field's to take: what is typed and taken back.
        takes(event, key) {
            return event.target === input && (key.length === 1 || key === "backspace")
        },
    }

    // Screen keyboards change the field rather than sending keys, and a word they suggest can
    // replace several letters at once, so what changed is worked out from the value.
    input.addEventListener("input", function () {
        const value = input.value
        let same = 0
        while (same < typed.length && same < value.length && typed[same] === value[same])
            same++
        for (let i = typed.length; i > same; i--)
            field.onKey("backspace")
        for (const character of value.slice(same))
            field.onKey(character)
        typed = value
    })
    return field
}
