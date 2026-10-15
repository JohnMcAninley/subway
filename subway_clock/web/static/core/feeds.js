// MTA GTFS-realtime feeds: which feed carries which route, and reading trip updates and
// alerts from them. A port of core/feeds.py, whose feeds.json this reads as it is.
import { read } from "./protobuf.js"

const FEEDS = await (await fetch(new URL("feeds.json", import.meta.url))).json()

export const ROUTE_FEEDS = {}
for (const [suffix, routes] of Object.entries(FEEDS.feeds)) {
    for (const route of routes)
        ROUTE_FEEDS[route] = FEEDS.base + suffix
}
export const ALL_FEED_URLS = [...new Set(Object.values(ROUTE_FEEDS))].sort()
export const ALERTS_URL = FEEDS.alerts  // service alerts for every route, in one feed

// URLs of the feeds carrying any of routes, in a stable order. Unknown routes are ignored.
export function feedUrls(routes) {
    return [...new Set(routes.filter(route => Object.hasOwn(ROUTE_FEEDS, route)).map(route => ROUTE_FEEDS[route]))]
        .sort()
}

// The parts of GTFS-realtime's FeedMessage the clock reads (see protobuf.read).
const TIME = { time: [2, "int"] }
const TRIP_UPDATE = {
    trip: [1, { trip_id: [1, "string"], route_id: [5, "string"] }],
    stop_time_update: [2, [{ arrival: [2, TIME], departure: [3, TIME], stop_id: [4, "string"] }]],
}
// The MTA's extension to GTFS-realtime alerts ("Mercury"): field 1001 of an alert, a message
// whose own fields include these.
const MERCURY = { updated_at: [2, "int"], alert_type: [3, "string"] }
const ALERT = {
    active_period: [1, [{ start: [1, "int"], end: [2, "int"] }]],
    informed_entity: [5, [{ route_id: [2, "string"], stop_id: [5, "string"], direction_id: [6, "int?"] }]],
    header_text: [10, { translation: [1, [{ text: [1, "string"], language: [2, "string"] }]] }],
    mercury: [1001, MERCURY],
}
const FEED = { entity: [2, [{ id: [1, "string"], trip_update: [3, TRIP_UPDATE], alert: [5, ALERT] }]] }

// A feed's bytes as a FeedMessage, of the fields above. Throws if they aren't one.
export function parseFeed(bytes) {
    return read(bytes, FEED)
}

export async function fetchFeed(url) {
    const response = await fetch(url, { cache: "no-store" })
    if (!response.ok)
        throw new Error(url + ": " + response.status + " " + response.statusText)
    return parseFeed(new Uint8Array(await response.arrayBuffer()))
}

// A train arriving at one of the stops. time: POSIX time it arrives at (or, at its first stop,
// departs) stop_id; trip_stops: stop IDs the trip has left to visit, in order.
export function Prediction(trip_id, route_id, stop_id, time, trip_stops) {
    return { trip_id, route_id, stop_id, time, trip_stops }
}

// Upcoming trains in feed at any of stops (a Set).
//
// Stops are directional stop IDs ("633S"), or parent stop IDs ("633") for
// both directions. Realtime stop IDs are always directional.
export function getPredictions(feed, stops) {
    const predictions = []

    for (const entity of feed.entity) {
        if (entity.trip_update !== null) {
            const trip = entity.trip_update
            const tripStops = trip.stop_time_update.map(stopTime => stopTime.stop_id)
            for (const stopTime of trip.stop_time_update) {
                const stopId = stopTime.stop_id
                // A trip's first stop often has only a departure time.
                const arrives = (stopTime.arrival && stopTime.arrival.time) || (stopTime.departure && stopTime.departure.time)
                if (arrives && (stops.has(stopId) || stops.has(stopId.slice(0, -1))))
                    predictions.push(Prediction(trip.trip ? trip.trip.trip_id : "", trip.trip ? trip.trip.route_id : "",
                                                stopId, arrives, tripStops))
            }
        }
    }

    return predictions
}

// The alert types that mean a route's trains aren't coming to the stops the alert names.
export const NO_SERVICE_TITLES = ["Suspended", "Part Suspended", "Stops Skipped", "No Scheduled Service"]

export class Alert {
    // text: one line; routes are written in brackets, like "[4]"
    // periods: [start, end] POSIX times it is active; end 0 means no end
    // affects: what it affects, as [route_id, parent stop ID, "N" or "S"], each "" if not given
    // kind: the MTA's type for it, e.g. "Delays" or "Planned - Part Suspended"; "" if not given
    // updated: POSIX time it was last changed; 0 if not given
    // toward: where its text says the trains are headed: see headings()
    constructor(id, text, periods, affects, kind = "", updated = 0, toward = []) {
        Object.assign(this, { id, text, periods, affects, kind, updated, toward })
    }

    active(now) {
        return !this.periods.length || this.periods.some(([start, end]) => start <= now && (!end || now < end))
    }

    // Planned work, as opposed to something happening now like delays.
    get planned() {
        return !this.id.startsWith("lmm:alert:")
    }

    // A short name for what is going on, e.g. "Delays" or "Part Suspended"; "" if the type isn't given.
    get title() {
        return this.kind.startsWith("Planned - ") ? this.kind.slice("Planned - ".length) : this.kind
    }

    // True if it is about trains not running, or not stopping, where it applies.
    get no_service() {
        return NO_SERVICE_TITLES.includes(this.title)
    }
}

const COMPASS = { uptown: "N", northbound: "N", downtown: "S", southbound: "S" }

// A word in either case, letter by letter: Python's (?i:...) for part of a pattern, which not
// every browser has yet.
function anyCase(word) {
    return [...word].map(c => "[" + c.toLowerCase() + c.toUpperCase() + "]").join("")
}

// "Uptown", "southbound" and so on, or a place before "-bound": "Coney Island-bound". Not
// "the Manhattan-bound platform", which says where to board and not which trains.
const HEADING = new RegExp(
    "\\b(" + Object.keys(COMPASS).map(anyCase).join("|") + ")\\b(?! (?:platform|track))"
    + "|((?:[A-Z0-9][\\w./']* )*[A-Z0-9][\\w./']+)-bound\\b(?! (?:platform|track))", "g")

// Where an alert's text says its trains are headed, for the many alerts that only say so there.
//
// "N" for each "uptown" or "northbound" and "S" for each "downtown" or
// "southbound"; and the place for each "Woodlawn-bound", which is "N" or "S"
// depending on the route (and, for "Manhattan-bound", on the stop). The place
// comes with any capitalised words before it, as in "No Jamaica". Empty if
// the text names no direction, or says "both directions".
export function headings(text) {
    if (text.toLowerCase().includes("both directions"))
        return []
    const found = [...text.matchAll(HEADING)].map(([, compass, place]) => compass ? COMPASS[compass.toLowerCase()] : place)
    return [...new Set(found)]
}

// Every alert in the alerts feed that has English text.
export function getAlerts(feed) {
    const alerts = []
    for (const entity of feed.entity) {
        if (entity.alert === null)
            continue
        const alert = entity.alert
        const translations = alert.header_text ? alert.header_text.translation : []
        let text = (translations.find(t => t.language === "en") || { text: "" }).text
        text = text.split(/\s+/).filter(Boolean).join(" ")
        if (!text)
            continue
        const affects = alert.informed_entity.map(e => [e.route_id, e.stop_id, e.direction_id === null ? "" : "NS"[e.direction_id]])
        const kind = alert.mercury ? alert.mercury.alert_type : ""
        const updated = alert.mercury ? alert.mercury.updated_at : 0
        alerts.push(new Alert(entity.id, text, alert.active_period.map(p => [p.start, p.end]), affects, kind, updated,
                              headings(text)))
    }
    return alerts
}
