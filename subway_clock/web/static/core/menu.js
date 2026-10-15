// The settings menu: what it lists and what each key does. A port of ui/menu.py, which
// says how it goes; its view() is what the page's menu.js draws, from either.
import { bulletId } from "./board.js"
import { ROTATIONS, STYLES, replace } from "./settings.js"
import { StationPicker } from "./stations.js"

// The settings on the main page after the stops: [setting, label, what to call each value]
export const CHOICES = [
    ["style", "Style", new Map([["classic", "Classic"], ["new", "New"], ["led", "LED"]])],
    ["show_station", "Station name", new Map([[false, "Off"], [true, "On"]])],
    ["show_alerts", "Service alerts", new Map([[false, "Off"], [true, "On"]])],
    ["rotation", "Last line shows", new Map([["auto", "What the real clocks do"], ["all", "Every train"],
                                             ["unique", "Each route once"]])],
    ["fetch_all_feeds", "Fetch every feed", new Map([[false, "Off"], [true, "On"]])],
]
console.assert(String([...CHOICES[0][2].keys()]) === String(STYLES)
               && String([...CHOICES[3][2].keys()].sort()) === String([...ROTATIONS].sort()))

const BOROUGHS = { M: "Manhattan", Bk: "Brooklyn", Q: "Queens", Bx: "The Bronx", SI: "Staten Island" }

const OPEN_KEYS = ["enter", "m", "M"]
const MAX_RESULTS = 40
const MAX_QUERY = 40

const TITLES = { main: "Settings", search: "Choose a station" }
const KEYS = {
    main: "Up and Down to move, Left and Right to change, Esc to close",
    search: "Type to search, Up and Down to move, Enter to open a station, Esc to go back",
    station: "Up and Down to move, Enter to tick or untick, Esc to go back",
}
const PROMPT = "Type part of a station's name, or a route"
const NO_MATCH = "No station matches"
const NO_STOPS = "No stops are ticked. The clock keeps the ones it has until some are."
const LOADING = "Loading schedules"

// A line of the menu. checked is null for a line with no box to tick.
function row(label, value = "", detail = "", bullets = [], checked = null) {
    return { label, value, detail, bullets: bullets.map(bulletId), box: checked !== null, checked: Boolean(checked) }
}

function sameSet(a, b) {
    const set = new Set(a)
    return set.size === new Set(b).size && b.every(item => set.has(item))
}

// Printable: one character that isn't a control character.
function printable(key) {
    return [...key].length === 1 && !/\p{C}/u.test(key)
}

// clock: the Clock whose settings these are. apply(settings): put new ones into effect, and save them.
// complexes is for the StationPicker; undefined is the bundled list.
export class Menu {
    constructor(clock, apply, complexes) {
        this.clock = clock
        this.apply = apply
        this.complexes = complexes
        this.open = false
        this.page = "main"
        this.index = 0  // the selected row of the page
        this.query = ""
        this.picker = null
        this.chosen = []  // on the stops pages: the directional stop IDs ticked, in the order to save them
        this.station = null  // on the station page
        this._found = 0  // the row of the search page to go back to
    }

    // Act on a key: "up", "down", "left", "right", "enter", "escape", "backspace" or a character typed.
    // Returns true if the key was the menu's, which every key is while it is open.
    key(key) {
        if (!this.open) {
            if (!OPEN_KEYS.includes(key))
                return false
            this.open = true
            this.page = "main"
            this.index = 0
            return true
        }
        const count = this._rows().length
        if (key === "up" || key === "down") {
            if (count)
                this.index = (((this.index + (key === "down" ? 1 : -1)) % count) + count) % count
        } else {
            ({ main: this._mainKey, search: this._searchKey, station: this._stationKey })[this.page].call(this, key)
        }
        return true
    }

    // Act on a click: on the row at index, or, while the menu is closed, anywhere on the clock.
    click(index = null) {
        if (!this.open) {
            this.key("enter")
        } else if (index !== null && index >= 0 && index < this._rows().length) {
            this.index = index
            this.key("enter")
        }
    }

    // Go back a page, or from the main page, close: what Esc does.
    back() {
        if (this.open)
            this.key("escape")
    }

    // Move down by rows (up, if negative), stopping at the ends where the keys would wrap.
    scroll(rows) {
        if (this.open)
            this.index = Math.max(0, Math.min(this.index + rows, this._rows().length - 1))
    }

    _mainKey(key) {
        if (key === "escape") {
            this.open = false
        } else if (this.index === 0) {
            if (["enter", "right", " "].includes(key) && this.clock.static.ready) {
                this.picker = new StationPicker(this.clock.static, this.complexes)
                this.chosen = this._expand(this.clock.settings.stops)
                this.page = "search"
                this.index = 0
                this.query = ""
            }
        } else if (["left", "right", "enter", " "].includes(key)) {
            const [setting, , names] = CHOICES[this.index - 1]
            const values = [...names.keys()]
            const step = key === "left" ? -1 : 1
            const value = values[(values.indexOf(this.clock.settings[setting]) + step + values.length) % values.length]
            this.apply(replace(this.clock.settings, { [setting]: value }))
        }
    }

    _searchKey(key) {
        const stations = this._stations()
        if (key === "escape") {
            const stops = this._collapse()
            if (this.chosen.length && !sameSet(this.chosen, this._expand(this.clock.settings.stops)))
                this.apply(replace(this.clock.settings, { stops }))
            this.page = "main"
            this.index = 0
        } else if (key === "enter") {
            if (stations.length) {
                this.station = stations[this.index]
                this._found = this.index
                // Start at a direction that is ticked, as unticking it is the likeliest thing to want.
                const ticked = this._directions().findIndex(([, d]) => this.chosen.includes(d.stop_id))
                this.page = "station"
                this.index = Math.max(0, ticked)
            }
        } else if (key === "backspace") {
            this.query = [...this.query].slice(0, -1).join("")
            this.index = 0
        } else if (printable(key) && [...this.query].length < MAX_QUERY) {
            this.query += key
            this.index = 0
        }
    }

    _stationKey(key) {
        if (["escape", "left", "backspace"].includes(key)) {
            // A station found with nothing typed is listed because it had stops ticked, and may not be now.
            this.page = "search"
            this.index = Math.min(this._found, Math.max(0, this._stations().length - 1))
        } else if (key === "enter" || key === " ") {
            const stopId = this._directions()[this.index][1].stop_id
            if (this.chosen.includes(stopId))
                this.chosen.splice(this.chosen.indexOf(stopId), 1)
            else
                this.chosen.push(stopId)
        }
    }

    // The picker's Stop for a parent stop ID (parent) or for a direction's, or null if it doesn't have it.
    _stop(stopId, parent) {
        const station = this.picker.station_for(stopId)
        const wanted = parent ? stopId : stopId.slice(0, -1)
        return station ? station.stops.find(stop => stop.stop_id === wanted) || null : null
    }

    // The stops setting as directional IDs: a parent stop becomes each of its directions.
    _expand(stops) {
        const expanded = []
        for (const stopId of stops) {
            const stop = this._stop(stopId, true)
            expanded.push(...(stop ? stop.directions.map(direction => direction.stop_id) : [stopId]))
        }
        return [...new Set(expanded)]
    }

    // The stops ticked as a stops setting: a stop with every direction ticked becomes its parent stop.
    _collapse() {
        const stops = []
        for (const stopId of this.chosen) {
            const stop = this._stop(stopId, false)
            const whole = stop && stop.directions.length > 1 && stop.directions.every(d => this.chosen.includes(d.stop_id))
            stops.push(whole ? stop.stop_id : stopId)
        }
        return [...new Set(stops)]
    }

    // The search page's stations: those found, or with nothing typed, those with stops ticked.
    _stations() {
        if (this.query.trim())
            return this.picker.search(this.query, MAX_RESULTS)
        return [...new Set(this.chosen.map(stopId => this.picker.station_for(stopId)).filter(Boolean))]
    }

    // The station page's lines: [stop, direction] for each direction of each of the station's stops.
    _directions() {
        return this.station.stops.flatMap(stop => stop.directions.map(direction => [stop, direction]))
    }

    _rows() {
        if (this.page === "main") {
            const settings = this.clock.settings
            return [row("Station", this._where()),
                    ...CHOICES.map(([setting, label, names]) => row(label, names.get(settings[setting])))]
        }
        if (this.page === "search")
            return this._stations().map(station => this._stationRow(station))
        const several = new Set(this.station.stops.map(stop => stop.name)).size > 1
        return this._directions().map(([stop, direction]) => row(
            direction.label || direction.stop_id, direction.stop_id, several ? stop.name : "", stop.routes,
            this.chosen.includes(direction.stop_id)))
    }

    _where() {
        if (!this.clock.static.ready)
            return LOADING
        const board = this.clock.board()
        return [board.station, board.direction].filter(Boolean).join(", ") || this.clock.settings.stops.join(", ")
    }

    _stationRow(station) {
        // Its directions that are ticked, each said once: "Downtown & Brooklyn" for all three platforms at Union Sq
        const ticked = new Set(station.stops.flatMap(stop => stop.directions)
            .filter(direction => this.chosen.includes(direction.stop_id))
            .map(direction => direction.label || direction.stop_id))
        // The express is the same line to whoever is choosing: no diamond beside the circle
        const routes = station.routes.filter(route => !(route.endsWith("X") && station.routes.includes(route.slice(0, -1))))
        return row(station.name, BOROUGHS[station.borough] || "", [...ticked].join(", "), routes)
    }

    // What to draw: see web/static/menu.js.
    view() {
        const rows = this.open ? this._rows() : []
        const searching = this.open && this.page === "search"
        let empty = ""
        if (searching && !rows.length)
            empty = this.query.trim() ? NO_MATCH : NO_STOPS
        return {
            open: this.open,
            page: this.page,
            title: this.page === "station" ? this.station.name : TITLES[this.page],
            query: this.query,
            prompt: PROMPT,
            empty,
            rows,
            index: this.index,
            keys: KEYS[this.page],
            back: this.page === "main" ? "Close" : "Back",
        }
    }
}
