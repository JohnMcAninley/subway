// Static GTFS: the tables the clock needs, and getting them in a browser. A port of
// core/gtfs.py.
//
// A page can't read the MTA's schedule zips, which don't say that other sites may
// (docs/architecture.md, "What a browser may fetch"). So the tables are read from
// schedules.json beside the page, which scripts/build_site.py makes from the zips,
// or, failing that, the zips are fetched through a CORS proxy: see StaticData. What
// is made from them is kept in the browser, so they are downloaded again only when
// they change.
import { csvFields, csvRows, entries, lines } from "./zip.js"

export const SUBWAY_URL = "https://rrgtfsfeeds.s3.amazonaws.com/gtfs_subway.zip"
export const SUPPLEMENTED_URL = "https://rrgtfsfeeds.s3.amazonaws.com/gtfs_supplemented.zip"

// The bundled station list (assets/stations.json, from scripts/update_stations.py)
export const STATIONS = await (await fetch(new URL("../assets/stations.json", import.meta.url))).json()

// Platforms that share a stop ID with others in the same direction, told apart by the
// track their trains use (assets/platforms.json): see core/gtfs.py.
export const PLATFORMS = await (await fetch(new URL("../assets/platforms.json", import.meta.url))).json()

// schedules.json is built every hour (.github/workflows/pages.yml); older than this, something has stopped.
const STALE_DAYS = 2

// The route and direction in a realtime-style trip ID: "6" and "S" in "061200_6..S04X001"
const TRIP_ROUTE_DIRECTION = /_(\w+?)\.+([NS])/

// The bundled station list as [direction_labels, stop_boroughs]; see StaticTables.
export function loadStations() {
    const labels = {}, boroughs = {}
    for (const [stop, station] of Object.entries(STATIONS)) {
        const directions = {}
        for (const d of "NS") {
            if (d in station)
                directions[d] = station[d]
        }
        if (Object.keys(directions).length)
            labels[stop] = directions
        boroughs[stop] = station.borough
    }
    return [labels, boroughs]
}

// A stop in the stops setting as [stop ID, track]: "235S:1" is the platform of 235S that trains
// on track 1 stop at; a stop with no track ("235S") is every platform it has, and its track "".
export function splitTrack(stop) {
    const colon = stop.indexOf(":")
    return colon < 0 ? [stop, ""] : [stop.slice(0, colon), stop.slice(colon + 1)]
}

// The stop ID where a realtime trip ends for riders: the last of its stops with a name, or null.
export function terminal(stopNames, tripStops) {
    for (let i = tripStops.length - 1; i >= 0; i--) {
        if (Object.hasOwn(stopNames, tripStops[i]))
            return tripStops[i]
    }
    return null
}

// Where a realtime trip is headed: the last of its stops with a name.
//
// Some trips end at unnamed non-revenue stops (northbound H trips end at H19,
// past Broad Channel), so skip those. Fall back to the schedule's headsign,
// which only exists for scheduled trips, not added or rerouted ones.
export function destination(stopNames, headsigns, tripStops, tripId) {
    const last = terminal(stopNames, tripStops)
    return last ? stopNames[last] : Object.hasOwn(headsigns, tripId) ? headsigns[tripId] : "Unknown"
}

// The static GTFS lookups the clock uses, as plain JSON-friendly objects.
//
// stop_names: stop ID (parent or directional) -> station name
// stop_parents: stop ID -> parent stop ID (parents map to themselves)
// stop_routes: parent stop ID -> sorted route IDs scheduled there
// headsigns: realtime-style trip ID -> scheduled headsign
// direction_labels: parent stop ID -> {"N": label, "S": label}, the MTA's names for
//     each platform direction, e.g. {"N": "Uptown", "S": "Downtown"}
// stop_boroughs: parent stop ID -> "M", "Bk", "Q", "Bx" or "SI"
// platforms: directional stop ID -> [{ track, routes }], for the stops with platforms in one
//     direction that are told apart by track (see splitTrack)
//
// The methods taking stop IDs also take a stop with a track, as in the stops setting.
export class StaticTables {
    constructor({ stop_names, stop_parents, stop_routes, headsigns, direction_labels = {}, stop_boroughs = {},
                  platforms = {} }) {
        this.ready = true  // false while the tables are still to be fetched; see StaticData.prepare
        this.set({ stop_names, stop_parents, stop_routes, headsigns, direction_labels, stop_boroughs, platforms })
    }

    set({ stop_names, stop_parents, stop_routes, headsigns, direction_labels, stop_boroughs, platforms = {} }) {
        Object.assign(this, { stop_names, stop_parents, stop_routes, headsigns, direction_labels, stop_boroughs,
                              platforms })
        this._terminals = null  // see terminals(); worked out when first asked for
    }

    // Fixed tables never change.
    async refresh() {
    }

    // The headsigns of route_id's scheduled trips in a direction ("N" or "S"): where they end.
    //
    // A trip ID like "061200_6..S04X001" names its route and direction after
    // the underscore. Express routes ("6X") are scheduled under the local's ID.
    terminals(routeId, direction) {
        if (this._terminals === null) {
            const terminals = new Map()
            for (const [tripId, headsign] of Object.entries(this.headsigns)) {
                const trip = TRIP_ROUTE_DIRECTION.exec(tripId)
                if (trip) {
                    const key = trip[1] + " " + trip[2]
                    if (!terminals.has(key))
                        terminals.set(key, new Set())
                    terminals.get(key).add(headsign)
                }
            }
            this._terminals = terminals
        }
        const route = routeId.endsWith("X") ? routeId.slice(0, -1) : routeId
        return this._terminals.get(route + " " + direction) || new Set()
    }

    // The direction label for a directional stop ID like "633S", or "" if there isn't one.
    direction_label(stopId) {
        stopId = splitTrack(stopId)[0]
        const labels = this.direction_labels[stopId.slice(0, -1)]
        return (labels && labels[stopId.slice(-1)]) || ""
    }

    // The parent of a stop ID, or the stop itself if it has none. (Not of a stop with a track.)
    parent(stopId) {
        return Object.hasOwn(this.stop_parents, stopId) ? this.stop_parents[stopId] : stopId
    }

    // The borough code for a stop ID (directional or parent), or "" if unknown.
    borough(stopId) {
        return this.stop_boroughs[this.parent(splitTrack(stopId)[0])] || ""
    }

    // The platform a stop with a track is ({ track, routes }), or null if it has no track or isn't known.
    platform(stop) {
        const [stopId, track] = splitTrack(stop)
        return (track && (this.platforms[stopId] || []).find(platform => platform.track === track)) || null
    }

    // Sorted route IDs scheduled at any of stops (directional or parent stop IDs, or platforms).
    routes_for(stops) {
        const routes = new Set()
        for (const stop of stops) {
            const platform = this.platform(stop)
            for (const route of platform ? platform.routes : this.stop_routes[this.parent(splitTrack(stop)[0])] || [])
                routes.add(route)
        }
        return [...routes].sort()
    }
}

// What a proxy turns url into: the proxy's address with url's put where it says {url}, or
// on the end. No proxy is url as it is.
export function proxied(proxy, url) {
    if (!proxy)
        return url
    return proxy.includes("{url}") ? proxy.replace("{url}", encodeURIComponent(url)) : proxy + encodeURIComponent(url)
}

// Static GTFS tables kept in the browser, refreshed from the MTA when they change.
//
// The supplemented GTFS adds the next week of planned service changes to the
// regular schedule, so routes rerouted onto a stop are included.
//
// The tables are read from `published`, the address of a schedules.json (see
// scripts/build_site.py), if there is one. If there isn't, or it can't be
// fetched, both zips are fetched through `proxy` (see proxied) and read here.
// What either comes to is kept in IndexedDB with its Last-Modified, and a check
// for a new one stops at the headers when it hasn't changed, as long as a proxy
// passes Last-Modified on.
export class StaticData extends StaticTables {
    static SOURCES = [["gtfs_subway", SUBWAY_URL], ["gtfs_supplemented", SUPPLEMENTED_URL]]
    static CHECK_SECONDS = 60 * 60  // The supplemented GTFS is republished about hourly

    // The share of prepare()'s time that goes on each download, rather than on reading it
    static DOWNLOAD_SHARE = 0.6

    constructor(proxy, published = "") {
        super({ stop_names: {}, stop_parents: {}, stop_routes: {}, headsigns: {} })
        this.proxy = proxy
        this.published = published
        this.ready = false
        this._checkedAt = 0
        this._refreshing = null
        this._kept = null  // what is in IndexedDB: see _update
    }

    // Start from the copy kept in the browser, if there is one. Returns true if there is.
    async load() {
        try {
            this._kept = await keep.get("schedules")
        } catch (error) {
            console.warn("Can't read the schedules kept in the browser:", error)
        }
        const complete = kept => kept.published || StaticData.SOURCES.every(([name]) => kept.sources[name])
        if (!this._kept || !complete(this._kept))
            return false
        this._checkedAt = this._kept.checkedAt
        this._assemble()
        this.ready = true
        return true
    }

    // Download and index the static GTFS, when there was no copy kept to start from.
    //
    // progress, if given, is called with what is going on ("Downloading
    // schedules") and how far along the whole is, 0 to 1. Throws if a download
    // fails; it can be called again.
    async prepare(progress) {
        await this._update(progress)
        this.ready = true
    }

    // Pick up new static GTFS if the MTA has published it, checking at most every CHECK_SECONDS.
    refresh() {
        if (Date.now() / 1000 - this._checkedAt < StaticData.CHECK_SECONDS)
            return this._refreshing || Promise.resolve()
        if (!this._refreshing) {
            this._refreshing = this._update().catch(function (error) {
                console.warn("Checking for new static GTFS failed, using the copy kept:", error)
            }).finally(() => this._refreshing = null)
        }
        return this._refreshing
    }

    // Download the tables if they have changed, and read them in.
    async _update(progress) {
        this._checkedAt = Date.now() / 1000
        if (this.published) {
            try {
                await this._updatePublished(progress)
                return
            } catch (error) {
                if (!this.proxy)
                    throw error
                console.warn("Can't fetch " + this.published + ", so reading the schedule zips instead:", error)
            }
        }
        await this._updateSources(progress)
    }

    // Download schedules.json if it has changed.
    async _updatePublished(progress) {
        const kept = this._kept && this._kept.published
        const file = await this._download(this.published, kept && kept.modified,
                                          stage(progress, "Downloading schedules", 0, 1))
        const published = file === null ? kept
            : { modified: file.modified, tables: JSON.parse(new TextDecoder().decode(file.bytes)) }
        const days = (Date.now() - Date.parse(published.tables.built)) / (24 * 60 * 60 * 1000)
        if (days > STALE_DAYS)
            console.warn(this.published + " was built " + Math.floor(days) + " days ago, and the schedules may have changed since")
        await this._keep({ checkedAt: this._checkedAt, published })
    }

    // Download any schedule zip that has changed, and read it.
    async _updateSources(progress) {
        const kept = this._kept || { sources: {} }
        const sources = { ...kept.sources }
        const share = 1 / StaticData.SOURCES.length
        let stops = kept.stops
        for (const [i, [name, url]] of StaticData.SOURCES.entries()) {
            const split = (i + StaticData.DOWNLOAD_SHARE) * share
            const zip = await this._download(proxied(this.proxy, url), sources[name] && sources[name].modified,
                                             stage(progress, "Downloading schedules", i * share, split))
            if (zip === null)
                continue  // Not changed since it was read
            const files = entries(zip.bytes)
            if (!stops || name === "gtfs_subway")
                stops = await readStops(files["stops.txt"])
            sources[name] = {
                modified: zip.modified,
                ...await readSchedule(files, stops.parents, stage(progress, "Reading schedules", split, (i + 1) * share)),
            }
        }
        await this._keep({ checkedAt: this._checkedAt, stops, sources })
    }

    // Read in what was downloaded, and keep it in the browser.
    async _keep(kept) {
        this._kept = kept
        this._assemble()
        try {
            await keep.set("schedules", this._kept)
        } catch (error) {
            console.warn("Can't keep the schedules in the browser, so they are downloaded again next time:", error)
        }
    }

    // url's bytes and Last-Modified, or null if its Last-Modified is still `modified`.
    async _download(url, modified, progress) {
        const abort = new AbortController()
        const response = await fetch(url, { signal: abort.signal, cache: "no-store" })
        if (!response.ok)
            throw new Error(url + ": " + response.status + " " + response.statusText)
        const lastModified = response.headers.get("Last-Modified")
        if (modified && lastModified === modified) {
            abort.abort()
            return null
        }
        const total = Number(response.headers.get("Content-Length")) || 0
        const chunks = []
        let done = 0
        const reader = response.body.getReader()
        for (;;) {
            const { done: finished, value } = await reader.read()
            if (finished)
                break
            chunks.push(value)
            done += value.length
            if (progress && total)
                progress(Math.min(1, done / total))
        }
        const bytes = new Uint8Array(done)
        let at = 0
        for (const chunk of chunks) {
            bytes.set(chunk, at)
            at += chunk.length
        }
        return { bytes, modified: lastModified }
    }

    // Put the tables together from what each source came to.
    _assemble() {
        const [labels, boroughs] = loadStations()
        if (this._kept.published) {
            const { stop_names, stop_parents, stop_routes, headsigns } = this._kept.published.tables
            this.set({ stop_names, stop_parents, stop_routes, headsigns, direction_labels: labels, stop_boroughs: boroughs,
                       platforms: PLATFORMS })
            return
        }
        const { stops, sources } = this._kept
        const headsigns = {}
        const stopRoutes = new Map()
        for (const [name] of StaticData.SOURCES) {
            Object.assign(headsigns, sources[name].headsigns)
            for (const [stop, routes] of Object.entries(sources[name].stop_routes)) {
                if (!stopRoutes.has(stop))
                    stopRoutes.set(stop, new Set())
                routes.forEach(route => stopRoutes.get(stop).add(route))
            }
        }
        this.set({
            stop_names: stops.names, stop_parents: stops.parents, headsigns,
            stop_routes: Object.fromEntries([...stopRoutes].map(([stop, routes]) => [stop, [...routes].sort()])),
            direction_labels: labels, stop_boroughs: boroughs, platforms: PLATFORMS,
        })
    }
}

// A 0-to-1 progress callback for one stage of a whole: it reports name and start to end to progress.
function stage(progress, name, start, end) {
    return progress ? fraction => progress(name, start + (end - start) * fraction) : null
}

// { names: stop_id -> name, parents: stop_id -> parent stop_id } from stops.txt. Parent stops are their own parent.
async function readStops(file) {
    const names = {}, parents = {}
    for (const row of await csvRows(file.stream())) {
        names[row.stop_id] = row.stop_name
        parents[row.stop_id] = row.parent_station || row.stop_id
    }
    return { names, parents }
}

// What a schedule zip's files come to: { headsigns, stop_routes } (see StaticTables), the
// routes as lists. progress, if given, is called with 0 to 1.
async function readSchedule(files, parents, progress) {
    const headsigns = {}
    const tripRoutes = new Map()
    for (const row of await csvRows(files["trips.txt"].stream())) {
        tripRoutes.set(row.trip_id, row.route_id)
        // Remove service and schedule from trip_id to match realtime format
        // e.g. AFA24GEN-1038-Sunday-00_000600_1..S03R -> 000600_1..S03R
        const underscore = row.trip_id.indexOf("_")
        if (underscore >= 0)
            headsigns[row.trip_id.slice(underscore + 1)] = row.trip_headsign
    }

    // Millions of rows, so by column number and a chunk at a time.
    const stopRoutes = new Map()
    const file = files["stop_times.txt"]
    let header = null, tripColumn, stopColumn, done = 0
    for await (const batch of lines(file.stream())) {
        for (const line of batch) {
            done += line.length + 1
            if (line === "")
                continue
            const row = csvFields(line)
            if (header === null) {
                header = row
                tripColumn = header.indexOf("trip_id")
                stopColumn = header.indexOf("stop_id")
                continue
            }
            const stopId = row[stopColumn]
            const parent = Object.hasOwn(parents, stopId) ? parents[stopId] : stopId
            let routes = stopRoutes.get(parent)
            if (!routes)
                stopRoutes.set(parent, routes = new Set())
            const route = tripRoutes.get(row[tripColumn])
            if (route !== undefined)
                routes.add(route)
        }
        if (progress && file.size)
            progress(Math.min(1, done / file.size))
    }
    return { headsigns, stop_routes: Object.fromEntries([...stopRoutes].map(([stop, routes]) => [stop, [...routes]])) }
}

// Values kept in the browser's IndexedDB, by key.
const keep = {
    open() {
        return new Promise(function (resolve, reject) {
            const request = indexedDB.open("subway-clock", 1)
            request.onupgradeneeded = () => request.result.createObjectStore("kept")
            request.onsuccess = () => resolve(request.result)
            request.onerror = () => reject(request.error)
        })
    },

    async run(mode, act) {
        const db = await keep.open()
        try {
            return await new Promise(function (resolve, reject) {
                const request = act(db.transaction("kept", mode).objectStore("kept"))
                request.onsuccess = () => resolve(request.result)
                request.onerror = () => reject(request.error)
            })
        } finally {
            db.close()
        }
    },

    get: key => keep.run("readonly", store => store.get(key)),
    set: (key, value) => keep.run("readwrite", store => store.put(value, key)),
}
