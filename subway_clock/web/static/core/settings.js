// User settings: the same names and defaults as core/settings.py, which says what each one
// is for. In a browser they are kept in localStorage, and can also come from the page's
// address, so that a link such as ?stops=635S,R20S&style=new is a whole clock.

// The looks of the MTA's platform clocks: see core/settings.py.
export const STYLES = ["classic", "new", "led"]

// Which trains the last line rotates through: see core/settings.py.
export const ROTATIONS = ["auto", "all", "unique"]

export const DEFAULTS = Object.freeze({
    stops: Object.freeze(["633S"]),
    style: "classic",
    max_trains: 5,
    max_minutes: 30,
    rotation: "auto",
    fetch_all_feeds: true,
    show_alerts: true,
    show_station: false,
    departed_seconds: 300,
    refresh_seconds: 10,
    rotation_seconds: 5,
})

// Settings from values, with the defaults for any left out. Throws on a style or rotation it doesn't know.
export function Settings(values = {}) {
    const settings = { ...DEFAULTS, stops: [...DEFAULTS.stops] }
    for (const name of Object.keys(DEFAULTS)) {
        if (Object.hasOwn(values, name))
            settings[name] = name === "stops" ? [...values.stops] : values[name]
    }
    if (!STYLES.includes(settings.style))
        throw new RangeError("style must be one of " + STYLES.join(", ") + ", not " + settings.style)
    if (!ROTATIONS.includes(settings.rotation))
        throw new RangeError("rotation must be one of " + ROTATIONS.join(", ") + ", not " + settings.rotation)
    return Object.freeze(settings)
}

// settings with some of them changed: Python's dataclasses.replace.
export function replace(settings, changes) {
    return Settings({ ...settings, ...changes })
}

export function equal(a, b) {
    return JSON.stringify(Object.keys(DEFAULTS).map(name => a[name]))
        === JSON.stringify(Object.keys(DEFAULTS).map(name => b[name]))
}

const KEY = "subway-clock.settings"
const TRUE = ["1", "true", "on", "yes"], FALSE = ["0", "false", "off", "no"]

// A setting as written in an address, or undefined if it can't be read as one.
function parse(name, text) {
    const kind = typeof DEFAULTS[name]
    if (name === "stops")
        return text.split(",").map(stop => stop.trim()).filter(Boolean)
    if (kind === "boolean")
        return TRUE.includes(text.toLowerCase()) ? true : FALSE.includes(text.toLowerCase()) ? false : undefined
    if (kind === "number")
        return /^\d+$/.test(text) ? Number(text) : undefined
    return text
}

// The settings kept in the browser, with any in `search` (a page's address's) over them.
export function load(search = location.search) {
    let values = {}
    try {
        values = JSON.parse(localStorage.getItem(KEY)) || {}
    } catch (error) {
        console.warn("Can't read the settings kept in the browser:", error)
    }
    const params = new URLSearchParams(search)
    for (const name of Object.keys(DEFAULTS)) {
        const value = params.has(name) ? parse(name, params.get(name)) : undefined
        if (value !== undefined && !(name === "stops" && !value.length))
            values[name] = value
    }
    try {
        return Settings(values)
    } catch (error) {
        console.warn("Using the default settings, as these can't be used:", values, error)
        return Settings()
    }
}

// Keep settings in the browser, and put them in the page's address, so that it is a link to this clock.
export function save(settings) {
    try {
        localStorage.setItem(KEY, JSON.stringify(settings))
    } catch (error) {
        console.warn("Can't keep the settings in the browser, so they last until the page is closed:", error)
    }
    const params = new URLSearchParams(location.search)
    for (const [name, value] of Object.entries(settings)) {
        if (JSON.stringify(value) === JSON.stringify(DEFAULTS[name]))
            params.delete(name)
        else
            params.set(name, name === "stops" ? value.join(",") : String(value))
    }
    const query = params.toString().replaceAll("%2C", ",")
    history.replaceState(history.state, "", location.pathname + (query ? "?" + query : "") + location.hash)
}
