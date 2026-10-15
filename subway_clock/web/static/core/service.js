// Runs the clock's timers in the page and hands out what the page draws: web/server.py's
// Service, without the server. See it for why each shape of screen keeps its own place
// in the last line's rotation.
import { Menu } from "./menu.js"

// How long to wait before trying again when the schedules can't be fetched at startup.
const RETRY_SECONDS = 15

// A screen shape that hasn't been asked about for this long is forgotten.
const VIEW_SECONDS = 30
const MAX_LINES = 10

function sameStops(a, b) {
    const set = new Set(a)
    return set.size === new Set(b).size && b.every(stop => set.has(stop))
}

function sleep(seconds) {
    return new Promise(resolve => setTimeout(resolve, seconds * 1000))
}

export class Service {
    // save(settings): keep settings chosen on the menu. With live false nothing is fetched and
    // nothing rotates by itself, for a clock stopped at a moment.
    constructor(clock, { save = null, live = true, complexes } = {}) {
        this.clock = clock
        this.save = save
        this.startup = { state: "ready", title: "", detail: "", progress: 0 }
        this.started = false  // the schedules are in, and the trains are being fetched
        this.views = new Map()  // "lines grouped" -> { index, seen }
        this.menu = new Menu(clock, settings => this.change_settings(settings), complexes)
        this._wake = null  // ends the wait for the next fetch, to fetch now instead
        this._reported = null
        if (live) {
            this._runFetches()
            this._runTimers()
        }
    }

    // What to show while there is no board yet: see Display.startup in ui/display.py.
    set_startup(state, title = "", detail = "", progress = 0) {
        this.startup = { state, title, detail, progress }
    }

    show_progress(stage, fraction) {
        this.set_startup("loading", stage, "This can take a minute", fraction)
    }

    _reportProgress(stage, fraction) {
        // A download reports every few kilobytes; only whole percents are worth showing.
        const report = stage + " " + Math.floor(fraction * 100)
        if (report !== this._reported) {
            this._reported = report
            this.show_progress(stage, Math.floor(fraction * 100) / 100)
        }
    }

    // Fetch the schedules if they aren't kept in the browser yet, trying again for as long as it takes.
    async _prepare() {
        const tables = this.clock.static
        if (!tables.ready)
            await tables.load()
        while (!tables.ready) {
            this.show_progress("Loading schedules", 0)
            try {
                await tables.prepare((stage, fraction) => this._reportProgress(stage, fraction))
            } catch (error) {
                // A browser doesn't tell a page why a request failed, so no network looks like a proxy refusing.
                console.warn("Fetching the schedules failed, trying again in " + RETRY_SECONDS + " seconds:", error)
                if (!tables.proxy && !tables.published)
                    this.set_startup("failed", "No proxy for the schedules", "Add ?proxy= to the address: see the README")
                else
                    this.set_startup("failed", error instanceof TypeError ? "No connection" : "Can't read the schedules",
                                     "Trying again shortly")
                await sleep(RETRY_SECONDS)
            }
        }
    }

    async _runFetches() {
        await this._prepare()
        this.started = true
        this.set_startup("loading", "Loading train times", "", -1)
        for (;;) {
            const woken = new Promise(resolve => this._wake = resolve)
            let result = null
            try {
                result = await this.clock.fetch()
            } catch (error) {
                console.error("Fetching predictions failed:", error)
            }
            this.apply_predictions(result)
            // Settings changed meanwhile were fetched for as they were: go round again at once.
            await Promise.race([woken, sleep(this.clock.settings.refresh_seconds)])
        }
    }

    // Fetch the trains now instead of at the next refresh.
    refetch() {
        if (this._wake)
            this._wake()
    }

    apply_predictions(result) {
        if (result !== null) {
            if (!this.clock.apply(result))
                return  // For stops that have since been replaced; the fetch for the new ones is next.
            this._restartRotations()
        }
        // The first fetch is back. If it failed, the board says so itself (it is stale).
        if (this.startup.state !== "ready")
            this.set_startup("ready")
    }

    _runTimers() {
        let rotated = performance.now()
        setInterval(() => {
            try {
                if (performance.now() - rotated >= this.clock.settings.rotation_seconds * 1000) {
                    rotated = performance.now()
                    this.rotate()
                }
            } catch (error) {
                console.error("The clock's timers failed:", error)
            }
        }, 250)
    }

    _layOut(lines, grouped, index) {
        // A change of lines restarts the clock's rotation, so the view's place in it goes back afterwards.
        this.clock.lines = lines
        this.clock.grouped = grouped
        this.clock.rotation_index = index
    }

    _restartRotations() {
        for (const view of this.views.values())
            view.index = 0
    }

    // Advance every view's last line to its next train or alert.
    rotate() {
        const now = performance.now()
        for (const [shape, view] of this.views) {
            if (now - view.seen >= VIEW_SECONDS * 1000)
                this.views.delete(shape)
        }
        for (const [shape, view] of this.views) {
            const [lines, grouped] = shape.split(" ")
            this._layOut(Number(lines), grouped === "true", view.index)
            this.clock.rotate()
            view.index = this.clock.rotation_index
        }
    }

    // What a page with room for `lines` lines draws.
    state(lines = 2, grouped = false) {
        lines = Math.max(1, Math.min(MAX_LINES, lines))
        const shape = lines + " " + grouped
        if (!this.views.has(shape))
            this.views.set(shape, { index: 0, seen: 0 })
        const view = this.views.get(shape)
        view.seen = performance.now()
        this._layOut(lines, grouped, view.index)
        return {
            board: this.clock.board(),
            startup: this.startup,
            showStation: this.clock.settings.show_station,
            menu: this.menu.view(),
        }
    }

    // Pass on to the settings menu what was done on the page. Returns false if that isn't anything it knows.
    // See web/server.py's Service.act.
    act(action) {
        if (typeof action.key === "string")
            this.menu.key(action.key)
        else if ("click" in action && (action.click === null || Number.isInteger(action.click)))
            this.menu.click(action.click)
        else if (action.back === true)
            this.menu.back()
        else if (Number.isInteger(action.scroll))
            this.menu.scroll(action.scroll)
        else
            return false
        return true
    }

    // Put settings chosen on the menu into effect, and keep them.
    change_settings(settings) {
        if (this.save)
            this.save(settings)
        this.apply_settings(settings)
    }

    // Switch to new settings without a restart.
    apply_settings(settings) {
        const old = this.clock.settings
        const refetch = this.clock.apply_settings(settings)
        this._restartRotations()
        // Until the schedules are in there are no fetches to hurry, and the first is yet to come.
        if (refetch && this.started) {
            if (!sameStops(settings.stops, old.stops))
                this.set_startup("loading", "Loading train times", "", -1)
            this.refetch()
        }
    }
}
