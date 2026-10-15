import { startPage } from "./page.js"

// The page for the Python core: the server (web/server.py) runs the clock, and
// hands over its state when asked. Keys and clicks are posted to it for the
// settings menu, which is Python's too (ui/menu.py).

startPage(async function (layout, action) {
    const query = "lines=" + layout.lines + "&grouped=" + (layout.grouped ? 1 : 0)
    const response = await fetch(action ? "api/menu?" + query : "api/state?" + query, action
        ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(action) }
        : { cache: "no-store" })
    if (!response.ok)
        throw new Error(response.statusText)
    return await response.json()
})
