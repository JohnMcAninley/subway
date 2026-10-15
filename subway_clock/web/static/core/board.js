// The screen description: everything a renderer needs to draw the clock, and nothing else.
// A port of core/board.py, whose comments say what each field means. The objects are
// plain, with the same names as the Python's fields, so that a Board is the same JSON
// whichever core made it.

export function Row(number, route, bullet, destination, direction, headline, detail, minutes, arriving) {
    return { number, route, bullet, destination, direction, headline, detail, minutes, arriving }
}

export function Route(route, bullet) {
    return { route, bullet }
}

export function Message(text, planned, title = "", updated_minutes = null, no_service = false, routes = []) {
    return { text, planned, title, updated_minutes, no_service, routes }
}

export function Group(heading, rows) {
    return { heading, rows }
}

export function Board({ style, rows, stale = false, messages = [], message = "", takeover = false, groups = [],
                        station = "", direction = "", routes = [] }) {
    return { style, rows, stale, messages, message, takeover, groups, station, direction, routes }
}

// Route IDs whose bullet isn't named after the route
const SPECIAL_BULLETS = {
    GS: "S",  // 42 St Shuttle
    FS: "SF",  // Franklin Av Shuttle
    H: "SR",  // Rockaway Park Shuttle
    SI: "SIR",  // Staten Island Railway
}

// Bullet asset id for a route. Express routes end in X; their diamond bullets end in d.
export function bulletId(routeId) {
    if (Object.hasOwn(SPECIAL_BULLETS, routeId))
        return SPECIAL_BULLETS[routeId]
    if (routeId.endsWith("X"))
        return routeId.slice(0, -1) + "d"
    return routeId
}
