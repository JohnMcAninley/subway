import { Clock } from "./core/clock.js"
import { StaticData } from "./core/gtfs.js"
import { Service } from "./core/service.js"
import { load, save } from "./core/settings.js"
import { startPage } from "./page.js"

// The page with the clock in it: the JavaScript core (core/) runs here, fetching
// the feeds from the MTA itself, so the page can be plain files on any host.
// Settings are kept in the browser, and can be given in the address too: see
// core/settings.js.
//
// The schedules come from "schedules" in config.json beside the page, the
// address of a schedules.json (scripts/build_site.py), if it has one; if not,
// or that can't be fetched, through a CORS proxy (see core/gtfs.js), whose
// address is the first of: ?proxy= in the page's address, which is then kept
// in the browser and taken out of the address, so that a link passed on
// doesn't carry it; the one kept in the browser; and "proxy" in config.json.
// ?proxy= with nothing after it forgets the one kept.

const PROXY_KEY = "subway-clock.proxy"

// config.json beside the page, or {} if there isn't one.
async function config() {
    try {
        const response = await fetch("config.json", { cache: "no-store" })
        if (response.ok)
            return await response.json()
    } catch (error) {
        // No config.json is nothing configured.
    }
    return {}
}

// The proxy's address: the one given or kept in the browser, or else configured.
function proxy(configured) {
    const params = new URLSearchParams(location.search)
    try {
        if (params.has("proxy")) {
            if (params.get("proxy"))
                localStorage.setItem(PROXY_KEY, params.get("proxy"))
            else
                localStorage.removeItem(PROXY_KEY)
            params.delete("proxy")
            const query = params.toString().replaceAll("%2C", ",")
            history.replaceState(history.state, "", location.pathname + (query ? "?" + query : "") + location.hash)
        }
        const kept = localStorage.getItem(PROXY_KEY)
        if (kept)
            return kept
    } catch (error) {
        console.warn("Can't keep the proxy in the browser:", error)
    }
    return configured || ""
}

const configured = await config()
const tables = new StaticData(proxy(configured.proxy), configured.schedules || "")
const service = new Service(new Clock(load(), tables), { save })
const page = startPage(async (layout, action) => {
    if (action)
        service.act(action)
    return service.state(layout.lines, layout.grouped)
})

// A page out of sight is let run slowly, if at all; back in sight, it catches up at once.
document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "visible") {
        service.refetch()
        page.poll()
    }
})
