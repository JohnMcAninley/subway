// Finding stations by name, to choose a clock's stops without knowing GTFS stop IDs.
// A port of core/stations.py, which says how the search works.
import { STATIONS } from "./gtfs.js"

// The MTA's abbreviations and what a user might type instead. Station names
// use both forms ("Park Place", "Bay Ridge Av", "Avenue U"), so each word
// matches as any form in its group.
const ABBREVIATIONS = [
    ["av", "avs", "avenue", "avenues"],
    ["st", "sts", "street", "streets", "saint"],
    ["sq", "square"],
    ["blvd", "boulevard"],
    ["pkwy", "parkway"],
    ["hwy", "highway"],
    ["tpke", "turnpike"],
    ["rd", "road"],
    ["pl", "place"],
    ["ln", "lane"],
    ["pk", "park"],
    ["hts", "heights"],
    ["ctr", "center"],
    ["mt", "mount"],
    ["wash", "washington"],
    ["e", "east"],
    ["w", "west"],
]
const WORD_FORMS = new Map(ABBREVIATIONS.flatMap(group => group.map(word => [word, group])))

// A direction trains leave a stop in. stop_id: the directional stop ID, e.g. "635S"; label: the
// MTA's name for the direction, e.g. "Downtown & Brooklyn"; "" if unknown.
export function Direction(stop_id, label) {
    return { stop_id, label }
}

// One line's platforms. stop_id: the parent stop ID, e.g. "635", which as a setting means every
// direction; routes: GTFS route IDs scheduled here; directions: one at a terminal, otherwise two.
export function Stop(stop_id, name, routes, directions) {
    return { stop_id, name, routes, directions }
}

// What a rider means by a station: a whole complex, or a station on its own.
// name: its stops' names, e.g. "14 St-Union Sq" or "Court Sq / Court Sq-23 St"
// borough: "M", "Bk", "Q", "Bx" or "SI"; "" if unknown
export function Station(name, borough, stops) {
    // Every route at the station, in the order of its stops.
    const routes = [...new Set(stops.flatMap(stop => stop.routes))]
    return { name, borough, stops, routes }
}

// Map each parent stop ID in the bundled station list to its complex ID. See core/stations.py.
export function loadComplexes(stations = STATIONS) {
    return Object.fromEntries(Object.entries(stations).filter(([, station]) => "complex" in station)
        .map(([stop, station]) => [stop, station.complex]))
}

// The words of a name or a query, lower case, without punctuation or ordinal endings ("14th" -> "14").
export function words(text) {
    const found = text.toLowerCase().replaceAll("'", "").match(/[a-z0-9]+/g) || []
    return found.map(word => word.replace(/^(\d+)(st|nd|rd|th)$/, "$1"))
}

// A comparison that puts "5 Av" before "14 St".
function byName(a, b) {
    const x = words(a), y = words(b)
    for (let i = 0; i < Math.min(x.length, y.length); i++) {
        const digits = /^\d+$/.test(x[i]), otherDigits = /^\d+$/.test(y[i])
        if (digits !== otherDigits)
            return digits ? -1 : 1
        const order = digits ? Number(x[i]) - Number(y[i]) : x[i] < y[i] ? -1 : x[i] > y[i] ? 1 : 0
        if (order)
            return order
    }
    return x.length - y.length
}

// Every station in a gtfs.StaticTables, searchable by name.
//
// complexes maps parent stop IDs to complex IDs, by default the bundled
// list's; a stop it leaves out is a station on its own.
export class StationPicker {
    constructor(tables, complexes = loadComplexes()) {
        const grouped = new Map()
        for (const stopId of [...new Set(Object.values(tables.stop_parents))].sort()) {
            if (Object.hasOwn(tables.stop_names, stopId)) {
                const key = Object.hasOwn(complexes, stopId) ? complexes[stopId] : "stop " + stopId
                if (!grouped.has(key))
                    grouped.set(key, [])
                grouped.get(key).push(StationPicker._stop(tables, stopId))
            }
        }

        this.stations = []
        this._byStop = new Map()
        this._terms = new Map()  // Station -> [the forms of its names' words, its routes as typed]
        for (const stops of grouped.values()) {
            // The name most of its stops share comes first: "Times Sq-42 St / 42 St-Port Authority Bus Terminal"
            const counts = new Map()
            stops.forEach(stop => counts.set(stop.name, (counts.get(stop.name) || 0) + 1))
            const names = [...counts.keys()].sort((a, b) => counts.get(b) - counts.get(a))
            const station = Station(names.join(" / "), tables.borough(stops[0].stop_id), stops)
            this.stations.push(station)
            for (const stop of stops)
                this._byStop.set(stop.stop_id, station)
            const nameWords = new Set(names.flatMap(name => words(name).flatMap(word => WORD_FORMS.get(word) || [word])))
            // Expresses are found as their locals: the 6X is a 6 to whoever is typing
            const routes = new Set(station.routes.flatMap(route => [route.toLowerCase(), route.toLowerCase().replace(/x$/, "")]))
            this._terms.set(station, [nameWords, routes])
        }
        this.stations.sort((a, b) => byName(a.name, b.name))
    }

    static _stop(tables, stopId) {
        let labels = tables.direction_labels[stopId]
        if (!labels || !Object.keys(labels).length) {
            // Not in the station list, so offer both directions unnamed
            labels = { N: "", S: "" }
        }
        const directions = [..."NS"].filter(d => d in labels).map(d => Direction(stopId + d, labels[d]))
        return Stop(stopId, tables.stop_names[stopId], [...(tables.stop_routes[stopId] || [])], directions)
    }

    // Stations matching every word of query, best first; all of them, by name, if query is empty.
    //
    // A word typed in full counts for more than the start of one, so "14"
    // lists the 14 St stations ahead of 145 St; busier stations then come
    // first.
    search(query, limit) {
        const queryWords = words(query)
        if (!queryWords.length)
            return this.stations.slice(0, limit)
        const matches = []
        for (const station of this.stations) {
            const [nameWords, routes] = this._terms.get(station)
            const scores = queryWords.map(word => StationPicker._score(word, nameWords, routes))
            if (scores.every(Boolean))
                matches.push({ score: scores.reduce((a, b) => a + b), station })
        }
        matches.sort((a, b) => b.score - a.score || b.station.routes.length - a.station.routes.length)
        return matches.slice(0, limit).map(match => match.station)
    }

    static _score(word, nameWords, routes) {
        if (nameWords.has(word) || routes.has(word))
            return 2
        return [...nameWords].some(nameWord => nameWord.startsWith(word)) ? 1 : 0
    }

    // The Station a stop ID (directional or parent) belongs to, or null.
    station_for(stopId) {
        return this._byStop.get(stopId) || this._byStop.get(stopId.slice(0, -1)) || null
    }
}
