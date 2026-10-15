// Upcoming trains for the chosen stops and the rotating last line, independent of any UI.
// A port of core/clock.py, which is the reference: the golden cases (tests/golden) check
// that both make the same boards.
import { Board, Group, Message, Route, Row, bulletId } from "./board.js"
import { ALERTS_URL, ALL_FEED_URLS, feedUrls, fetchFeed, getAlerts, getPredictions } from "./feeds.js"
import { destination, terminal } from "./gtfs.js"
import { headline } from "./headline.js"

// The board is marked stale once any feed it needs hasn't been fetched for this long.
export const STALE_SECONDS = 90

// Alerts change slowly and their feed is large, so it is fetched less often than the trains.
export const ALERTS_SECONDS = 120
const MAX_MESSAGES = 5

// Styles that show alerts in place of the last line, in rotation with its trains.
// Each alert stays for MESSAGE_ROTATIONS rotations, as it takes longer to read than a train.
const MESSAGE_LINE_STYLES = ["new"]
const MESSAGE_ROTATIONS = 2

// Styles whose real clocks stop the rotation once every route among the trains has been
// shown (settings.rotation "unique"). The others always go through max_trains ("all").
const UNIQUE_ROUTE_STYLES = ["new"]

function time(now) {
    return now === undefined || now === null ? Date.now() / 1000 : now
}

function withoutX(route) {
    return route.endsWith("X") ? route.slice(0, -1) : route
}

function sameStops(a, b) {
    const set = new Set(a)
    return set.size === new Set(b).size && b.every(stop => set.has(stop))
}

// What fetch() brings back for apply().
// feeds: Map of feed URL -> list of Predictions, or null if fetching that feed failed
// scheduled: URLs of the feeds for routes scheduled at the stops
// alerts: Alerts, or null if they weren't fetched this time or fetching failed
// stops: the stops the predictions are for
function FetchResult(fetched_at, feeds, scheduled, alerts, stops) {
    return { fetched_at, feeds, scheduled, alerts, stops }
}

// See core/clock.py's Clock for how it is driven. Here fetch() and refresh() are async.
export class Clock {
    constructor(settings, staticTables, fetch_feed = fetchFeed) {
        this.settings = settings
        this.static = staticTables
        this.fetch_feed = fetch_feed
        this.upcoming = []  // every train within max_minutes at the last fetch, soonest first
        this._lines = 2
        this.grouped = false
        this.rotation_index = 0  // position of the last line in what it rotates through
        this.alerts = []
        this._alerts_at = null  // when the alerts were last fetched successfully
        this._feeds = new Map()  // feed URL -> [predictions, fetched_at] from the last successful fetch
        this._scheduled = []  // feed URLs for routes scheduled at the chosen stops
    }

    async refresh(now) {
        this.apply(await this.fetch(now), now)
    }

    // Replace the settings while running. Returns true if the trains need fetching again now.
    // See core/clock.py.
    apply_settings(settings) {
        const old = this.settings
        this.settings = settings
        this.rotation_index = 0
        if (!sameStops(settings.stops, old.stops)) {
            this.upcoming = []
            this._feeds = new Map()
            this._scheduled = []
            return true
        }
        // More feeds or further ahead needs a fetch; fewer or nearer does too, to drop what
        // no longer belongs. Alerts turned on are fetched with the trains if they are due.
        return settings.fetch_all_feeds !== old.fetch_all_feeds || settings.max_minutes !== old.max_minutes
            || settings.show_alerts && !old.show_alerts
    }

    // Download the feeds for the chosen stops.
    async fetch(now) {
        now = time(now)
        const settings = this.settings  // apply_settings may replace them while this runs
        const stops = new Set(settings.stops)
        const scheduled = feedUrls(this.static.routes_for(stops))
        const urls = settings.fetch_all_feeds ? ALL_FEED_URLS : scheduled
        const due = this._alerts_at === null || now - this._alerts_at >= ALERTS_SECONDS
        const alertsDue = settings.show_alerts && due

        const fetch = async url => {
            try {
                return await this.fetch_feed(url)
            } catch (error) {
                console.warn("Fetching " + url + " failed:", error)
                return null
            }
        }

        // New schedules take effect from a later fetch; the trains don't wait for them.
        this.static.refresh()
        // All at once: one after another, the feeds take several seconds.
        const wanted = alertsDue ? [...urls, ALERTS_URL] : urls
        const fetched = new Map(wanted.map((url, i) => [url, null]))
        await Promise.all(wanted.map(async url => fetched.set(url, await fetch(url))))

        const feeds = new Map(urls.map(url => [url, fetched.get(url) === null ? null : getPredictions(fetched.get(url), stops)]))
        const alerts = fetched.get(ALERTS_URL) ? getAlerts(fetched.get(ALERTS_URL)) : null
        return FetchResult(now, feeds, scheduled, alerts, stops)
    }

    // Update the upcoming trains from a fetch(). Feeds that failed keep their last good data.
    // Returns false, changing nothing, if the fetch was for stops that have since been replaced.
    apply(result, now) {
        now = time(now)
        if (!sameStops([...result.stops], this.settings.stops))
            return false
        for (const [url, preds] of result.feeds) {
            if (preds !== null)
                this._feeds.set(url, [preds, result.fetched_at])
        }
        this._scheduled = [...result.scheduled]
        if (result.alerts !== null) {
            this.alerts = result.alerts
            this._alerts_at = result.fetched_at
        }

        const preds = [...result.feeds.keys()].filter(url => this._feeds.has(url)).flatMap(url => this._feeds.get(url)[0])
        const latest = now + this.settings.max_minutes * 60
        this.upcoming = preds.filter(p => p.time <= latest).sort((a, b) => a.time - b.time)
        this.rotation_index = 0  // Restart rotation
        return true
    }

    get lines() {
        return this._lines
    }

    set lines(lines) {
        if (lines < 1)
            throw new RangeError("lines must be at least 1, not " + lines)
        if (lines !== this._lines) {
            this._lines = lines
            this.rotation_index = 0
        }
    }

    // The upcoming trains that haven't left yet: see settings.departed_seconds.
    _waiting(now) {
        return this.upcoming.filter(p => p.time >= now - this.settings.departed_seconds)
    }

    // The trains the board can show: max_trains, or more if there are more lines than that.
    predictions(now) {
        now = time(now)
        let trains = this._waiting(now).slice(0, Math.max(this.settings.max_trains, this.lines))
        const rotation = this.settings.rotation
        if (rotation === "unique" || rotation === "auto" && UNIQUE_ROUTE_STYLES.includes(this.settings.style)) {
            // Stop after the last train that brings a new route, but still fill the lines.
            const routes = trains.map(p => p.route_id)
            const lastNew = Math.max(0, ...routes.map(route => routes.indexOf(route)))
            trains = trains.slice(0, Math.max(lastNew + 1, this.lines))
        }
        return trains
    }

    // How many lines always show the same train: every line but the rotating last one.
    get _fixed() {
        return Math.max(1, this.lines - 1)
    }

    // True if any feed for the stops' scheduled routes hasn't been fetched successfully for a while.
    // Other feeds (fetched when fetch_all_feeds is on) only matter for
    // reroutes, so their failures don't mark the board stale.
    stale(now) {
        now = time(now)
        return this._scheduled.some(url => !this._feeds.has(url) || now - this._feeds.get(url)[1] > STALE_SECONDS)
    }

    // The active alerts for the stops and their routes.
    // Those that leave the stops without a route's trains come first, then
    // the others happening now, then planned work.
    messages(now) {
        now = time(now)
        if (!this.settings.show_alerts)
            return []
        const onBoard = new Set(this.predictions(now).map(p => p.route_id))
        const coming = new Set(this._waiting(now).map(p => withoutX(p.route_id)))
        const stale = this.stale(now)  // Then there is no telling which trains are coming
        const messages = []
        for (const alert of this.alerts) {
            const routes = alert.active(now) ? this._affected(alert, onBoard) : []
            if (routes.length) {
                // A suspension often names the stops at its ends too, where trains still run one way.
                const noService = alert.no_service && !stale && !routes.some(route => coming.has(withoutX(route)))
                const updated = alert.updated ? Math.max(0, Math.floor((now - alert.updated) / 60)) : null
                messages.push(Message(alert.text, alert.planned, alert.title, updated, noService,
                                      routes.map(route => Route(route, bulletId(route)))))
            }
        }
        const byText = new Map()  // Alerts are often repeated per route
        const order = m => (m.no_service ? 0 : 2) + (m.planned ? 1 : 0)
        for (const message of messages.sort((a, b) => order(a) - order(b))) {
            if (!byText.has(message.text))
                byText.set(message.text, message)
        }
        return [...byText.values()].slice(0, MAX_MESSAGES)
    }

    // The routes alert is about here, in its own order: empty if it isn't about the stops at all.
    // See core/clock.py.
    _affected(alert, onBoard) {
        const parents = this.static
        // (parent stop, direction) pairs shown: one for a directional stop, both for a parent stop
        const shown = new Set()
        for (const stop of this.settings.stops) {
            const parent = parents.parent(stop)
            for (const d of parent === stop ? "NS" : stop.slice(-1))
                shown.add(parent + " " + d)
        }
        const pairs = [...shown].map(pair => pair.split(" "))
        const routes = new Set([...this.static.routes_for(this.settings.stops), ...onBoard])
        const affected = new Set()
        for (const [route, stop, direction] of alert.affects) {
            if (stop) {
                if ([...(direction || "NS")].some(d => shown.has(parents.parent(stop) + " " + d)))
                    affected.add(route)
            } else if (routes.has(route) && pairs.some(([parent, d]) =>
                (direction ? direction === d : this._headed(alert, route, parent).has(d)))) {
                affected.add(route)
            }
        }
        return [...affected]
    }

    // The directions at a parent stop, "N" and "S", of the trains a route-wide alert is about.
    // See core/clock.py.
    _headed(alert, route, parent) {
        const directions = new Set()
        for (const heading of alert.toward) {
            const found = heading === "N" || heading === "S" ? new Set([heading]) : this._toward(heading, route, parent)
            if (!found.size)
                return new Set(["N", "S"])
            found.forEach(d => directions.add(d))
        }
        return directions.size ? directions : new Set(["N", "S"])
    }

    // The directions in which route's trains at a parent stop are headed for place; empty if unknown.
    // See core/clock.py.
    _toward(place, route, parent) {
        const labels = this.static.direction_labels[parent] || {}
        const words = place.split(/\s+/).filter(Boolean)
        for (let start = 0; start < words.length; start++) {  // "No Jamaica" is tried whole, then as "Jamaica"
            const name = new RegExp("(?<!\\w)" + escape(words.slice(start).join(" ")) + "(?!\\w)", "i")
            const found = new Set([..."NS"].filter(d => name.test(labels[d] || "")
                || [...this.static.terminals(route, d)].some(end => name.test(end))))
            if (found.size)
                return found
        }
        return new Set()
    }

    // What the last line rotates through: ["train", index] and ["message", text] entries.
    _rotation(now) {
        const predictions = this.predictions(now)
        const count = predictions.length
        const takeover = this._takeover(now)
        if (takeover.length)
            return takeover.flatMap(m => Array(MESSAGE_ROTATIONS).fill(["message", m.text]))
        if (this.lines < 2)
            return []
        const fixed = this._fixed
        const arriving = count > fixed && predictions[fixed].time - now < 60
        let trains
        if (count > fixed && (count <= this.lines || arriving))
            trains = [fixed]  // Nothing else to show, or it is arriving and stays put
        else
            trains = Array.from({ length: Math.max(0, count - fixed) }, (_, i) => fixed + i)
        const rotation = trains.map(i => ["train", i])
        if (MESSAGE_LINE_STYLES.includes(this.settings.style) && !arriving)
            rotation.push(...this.messages(now).flatMap(m => Array(MESSAGE_ROTATIONS).fill(["message", m.text])))
        return rotation
    }

    // The alerts to fill the screen with, in the styles that put alerts on the last line.
    // They are the ones that say why no trains are coming, when none are.
    _takeover(now) {
        if (!MESSAGE_LINE_STYLES.includes(this.settings.style) || this._waiting(now).length)
            return []
        return this.messages(now).filter(m => m.no_service)
    }

    // Advance the last line to its next train or alert. Returns false if there is nothing to rotate.
    rotate(now) {
        now = time(now)
        const rotation = this._rotation(now)
        if (this.grouped || rotation.length < 2)
            return false
        this.rotation_index = (this.rotation_index + 1) % rotation.length
        return true
    }

    board(now) {
        now = time(now)
        if (this.grouped)
            return this._grouped_board(now)

        // The fixed lines always show the next trains.
        const predictions = this.predictions(now)
        const indexes = Array.from({ length: Math.min(this._fixed, predictions.length) }, (_, i) => i)

        // The last line cycles through the rest.
        let message = ""
        const rotation = this._rotation(now)
        if (rotation.length) {
            const [kind, value] = rotation[this.rotation_index < rotation.length ? this.rotation_index : 0]
            if (kind === "train")
                indexes.push(value)
            else
                message = value
        }

        const rows = indexes.map(i => this._row(predictions[i], i + 1, now))
        return Board({ style: this.settings.style, rows, stale: this.stale(now), messages: this.messages(now),
                       message, takeover: this._takeover(now).length > 0, ...this._station() })
    }

    // Every line shows a train; with more than one direction, each gets an equal share of the lines.
    _grouped_board(now) {
        const waiting = this._waiting(now)
        const byDirection = new Map()  // direction label -> its trains, in order of each direction's next train
        for (const pred of waiting) {
            const label = this.static.direction_label(pred.stop_id)
            if (!byDirection.has(label))
                byDirection.set(label, [])
            byDirection.get(label).push(pred)
        }
        const headings = [...byDirection.keys()].slice(0, this.lines)

        let rows, groups
        if (headings.length < 2) {
            rows = waiting.slice(0, this.lines).map((pred, i) => this._row(pred, i + 1, now))
            groups = []
        } else {
            // Spare lines go to the first directions
            const share = Math.floor(this.lines / headings.length), extra = this.lines % headings.length
            groups = headings.map((heading, g) => Group(heading, byDirection.get(heading).slice(0, share + (g < extra ? 1 : 0))
                .map((pred, i) => this._row(pred, i + 1, now))))
            rows = groups.flatMap(group => group.rows)
        }
        const takeover = this._takeover(now)  // Nothing rotates, so the first of them
        return Board({ style: this.settings.style, rows, stale: this.stale(now), messages: this.messages(now),
                       message: takeover.length ? takeover[0].text : "", takeover: takeover.length > 0, groups,
                       ...this._station() })
    }

    // The Board's station, direction and routes: where the chosen stops are and what stops there.
    _station() {
        const tables = this.static
        const stops = this.settings.stops
        const names = new Set(stops.filter(stop => Object.hasOwn(tables.stop_names, stop)).map(stop => tables.stop_names[stop]))
        // A parent stop is both directions, so there is no one label for it.
        const directional = stops.every(stop => tables.parent(stop) !== stop)
        const labels = directional ? new Set(stops.map(stop => tables.direction_label(stop))) : new Set()
        // Stop by stop, as the bullets on an entrance's sign are grouped by line
        const routes = new Set(stops.flatMap(stop => tables.routes_for([stop])))
        return {
            station: [...names].join(" / "), direction: labels.size === 1 ? [...labels][0] : "",
            routes: [...routes].map(route => Route(route, bulletId(route))),
        }
    }

    _row(pred, number, now) {
        const seconds = pred.time - now
        const tables = this.static
        const name = destination(tables.stop_names, tables.headsigns, pred.trip_stops, pred.trip_id)
        const label = tables.direction_label(pred.stop_id)

        // Boroughs of the stops after this one, up to where the trip ends for riders
        const last = terminal(tables.stop_names, pred.trip_stops)
        const stops = last ? pred.trip_stops.slice(0, pred.trip_stops.indexOf(last) + 1) : []
        let ahead = stops.includes(pred.stop_id)
            ? stops.slice(stops.indexOf(pred.stop_id) + 1).map(s => tables.borough(s)) : []
        // Without the terminal's borough there is nothing to say; other gaps (unnamed stops) don't matter.
        ahead = ahead.length && ahead[ahead.length - 1] ? ahead.filter(Boolean) : []
        const [head, detail] = headline(label, tables.borough(pred.stop_id), ahead, name)
        return Row(number, pred.route_id, bulletId(pred.route_id), name, label, head, detail,
                   Math.max(0, Math.trunc(seconds / 60)), seconds < 60)
    }
}

function escape(text) {
    return text.replace(/[.*+?^${}()|[\]\\\/-]/g, "\\$&")
}
