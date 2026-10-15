// Runs the JavaScript core (subway_clock/web/static/core) on what tests/test_js_core.py
// asks for in /job.json, and posts what it finds back to /result as JSON: the boards
// for each golden case, as tests/golden_harness.py's run_case makes them, and the
// settings menu's and the station search's answers, to compare with Python's.
import { Clock } from "/core/clock.js"
import { parseFeed } from "/core/feeds.js"
import { StaticData, StaticTables } from "/core/gtfs.js"
import { Menu } from "/core/menu.js"
import { Settings } from "/core/settings.js"
import { StationPicker } from "/core/stations.js"

async function json(url) {
    const response = await fetch(url, { cache: "no-store" })
    if (!response.ok)
        throw new Error(url + ": " + response.status)
    return response.json()
}

async function caseFiles(name) {
    const dir = "/tests/golden/" + name + "/"
    return { dir, case: await json(dir + "case.json"), tables: new StaticTables(await json(dir + "static.json")) }
}

// The boards from a case's "board" steps. See run_case in tests/golden_harness.py.
async function runCase(name) {
    const { dir, case: definition, tables } = await caseFiles(name)
    let failing = new Set()

    async function fetchFeed(url) {
        const feed = url.split("%2F").pop()
        if (failing.has(feed))
            throw new Error(feed + " failing in this step")
        const response = await fetch(dir + "feeds/" + feed + ".pb")
        if (!response.ok)
            throw new Error(feed + ": " + response.status)
        return parseFeed(new Uint8Array(await response.arrayBuffer()))
    }

    const clock = new Clock(Settings(definition.settings), tables, fetchFeed)
    const boards = []
    for (const step of definition.steps) {
        if (step.action === "refresh") {
            failing = new Set(step.fail || [])
            await clock.refresh(step.now)
        } else if (step.action === "lines") {
            clock.lines = step.lines
        } else if (step.action === "grouped") {
            clock.grouped = step.grouped
        } else if (step.action === "rotate") {
            clock.rotate(step.now)
        } else if (step.action === "board") {
            boards.push({ now: step.now, ...clock.board(step.now) })
        } else {
            throw new Error("Unknown action " + step.action)
        }
    }
    return boards
}

// The menu's view after each of keys, and the settings at the end.
async function runMenu({ case: name, settings, keys }) {
    const { tables } = await caseFiles(name)
    const clock = new Clock(Settings(settings), tables)
    const menu = new Menu(clock, changed => clock.apply_settings(changed))
    const views = keys.map(function (key) {
        menu.key(key)
        return menu.view()
    })
    return { views, settings: clock.settings }
}

// The names of the stations each query finds, among the stations in tables.
async function runSearch({ tables, queries }) {
    const picker = new StationPicker(new StaticTables(tables))
    return Object.fromEntries(queries.map(query => [query, picker.search(query).map(station => station.name)]))
}

const tables = data => ({ stop_names: data.stop_names, stop_parents: data.stop_parents,
                          stop_routes: data.stop_routes, headsigns: data.headsigns })

// The tables read from a schedules.json, and again as kept in the browser.
async function runPublished() {
    const data = new StaticData("", "/published/schedules.json")
    await data.prepare()
    const kept = new StaticData("", "/published/schedules.json")
    const loaded = await kept.load()
    await kept._update()  // Not changed, so not read again
    return { tables: tables(data), loaded, same: JSON.stringify(tables(kept)) === JSON.stringify(tables(data)) }
}

// The tables read from the schedule zips, as the page reads them when there is no schedules.json to
// be had, and again as kept in the browser.
async function runSchedules() {
    const data = new StaticData("/schedules?url=", "/published/missing.json")
    const stages = new Set()
    await data.prepare(stage => stages.add(stage))
    const kept = new StaticData("/schedules?url=", "/published/missing.json")
    const loaded = await kept.load()
    await kept._update()  // The zips haven't changed, so nothing is read again
    return {
        tables: tables(data), stages: [...stages], loaded,
        same: JSON.stringify(tables(kept)) === JSON.stringify(tables(data)),
    }
}

let result
try {
    const job = await json("/job.json")
    const golden = {}
    for (const name of job.golden)
        golden[name] = await runCase(name)
    const menus = []
    for (const script of job.menus)
        menus.push(await runMenu(script))
    const searches = []
    for (const search of job.searches)
        searches.push(await runSearch(search))
    const published = await runPublished()
    const schedules = job.schedules ? await runSchedules() : null
    result = { golden, menus, searches, published, schedules }
} catch (error) {
    result = { error: String(error && error.stack || error) }
}
await fetch("/result", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(result) })
document.body.textContent = "Done"
