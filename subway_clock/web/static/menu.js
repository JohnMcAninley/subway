import { bullet, el, vars } from "./dom.js"

// The settings menu, drawn over whichever style is showing. What it lists and
// what each key does is decided in Python (ui/menu.py); this draws its view,
// which ui/qml/SettingsMenu.qml describes and whose sizes these are. A mouse
// goes back to Python too, through act: a click on a row, the button that does
// what Esc does (as does a click beside the menu), and the wheel.
export function settingsMenu(root, act) {
    let drawn = ""

    root.addEventListener("click", () => act({ back: true }))

    function draw(menu, width, height) {
        root.hidden = !menu.open
        const key = JSON.stringify([menu, width, height])
        if (!menu.open || key === drawn)
            return
        drawn = key

        // A row's height. The panel is a title, the rows and the keys, and fits six rows on the
        // widest bar; a taller screen gets more rows, not bigger ones, for the pages that are lists.
        const unit = Math.min(width * 0.96 / 9, height * 0.94 / 8.6, 72)
        const most = Math.max(6, Math.min(12, Math.floor(height * 0.94 / unit - 2.6)))
        const lines = menu.page === "main" ? Math.max(6, Math.min(most, menu.rows.length)) : most
        const searching = menu.page === "search"
        // The rows that fit, keeping the selected one in view
        const shown = lines - (searching ? 1 : 0)
        const first = Math.max(0, Math.min(menu.index - Math.floor(shown / 2), menu.rows.length - shown))
        vars(root, { m: unit, edge: Math.max(1, Math.round(unit * 0.03)) })

        const list = el("div", "list")
        list.style.height = unit * shown + "px"
        if (menu.empty !== "")
            list.append(el("div", "empty", menu.empty))
        list.append(...menu.rows.slice(first, first + shown).map((row, i) => item(row, first + i, menu.index)))
        // Where the rows shown are among all of them, when they don't all fit
        if (menu.rows.length > shown) {
            const place = el("div", "place")
            place.style.top = first / menu.rows.length * 100 + "%"
            place.style.height = shown / menu.rows.length * 100 + "%"
            list.append(place)
        }

        const back = el("button", "back", menu.back)
        back.addEventListener("click", () => act({ back: true }))
        const panel = el("div", "panel " + menu.page, el("div", "top", el("div", "title", menu.title), back))
        panel.style.height = unit * (lines + 2.6) + "px"
        // Clicks on the panel that hit nothing are not clicks beside it. The wheel moves a row a notch.
        panel.addEventListener("click", event => event.stopPropagation())
        panel.addEventListener("wheel", event => act({ scroll: event.deltaY < 0 ? -1 : 1 }), { passive: true })
        if (searching) {
            // What has been typed, or until something is, what to type
            panel.append(el("div", "query" + (menu.query === "" ? " prompt" : ""),
                            el("span", "typed", menu.query === "" ? menu.prompt : menu.query), el("i", "caret")))
        }
        panel.append(list, el("div", "keys", el("span", "", menu.keys)))
        root.replaceChildren(el("div", "shade"), panel)
    }

    // A row: a box to tick, the label, its bullets, a lesser detail, and the value at the right.
    function item(row, index, selected) {
        const bullets = el("span", "bullets", ...row.bullets.map(asset => bullet(asset)))
        const left = el("div", "left")
        if (row.box)
            left.append(el("span", "box" + (row.checked ? " checked" : "")))
        // A direction's bullets say which platform it is, so they come first; a station's follow its name.
        if (row.box && row.bullets.length)
            left.append(bullets)
        left.append(el("span", "label", row.label))
        if (!row.box && row.bullets.length)
            left.append(bullets)
        if (row.detail !== "")
            left.append(el("span", "detail", row.detail))
        const element = el("div", "item" + (index === selected ? " selected" : ""), left, el("span", "value", row.value))
        element.addEventListener("click", () => act({ click: index }))
        return element
    }

    return { draw }
}

// The name the menu knows a key by: its own for the ones that move about, or the character typed.
export function keyName(event) {
    const names = { ArrowUp: "up", ArrowDown: "down", ArrowLeft: "left", ArrowRight: "right", Enter: "enter",
                    Escape: "escape", Backspace: "backspace" }
    if (event.ctrlKey || event.altKey || event.metaKey)
        return ""
    return names[event.key] || (event.key.length === 1 ? event.key : "")
}
