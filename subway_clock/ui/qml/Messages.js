.pragma library

// Service alerts name routes in brackets, like "[4]" or "[6X]". These turn
// them into styled text with the route bullets drawn inline.

var bullets = ["1", "2", "3", "4", "5", "6", "7", "A", "B", "C", "D", "E", "F", "G", "J", "L", "M", "N", "Q", "R",
               "S", "W", "Z", "SIR"]
var expressBullets = { "6X": "6d", "7X": "7d", "FX": "Fd" }

// The bullet asset for a marker's name, or "" for markers that are icons we
// don't have, like "[shuttle bus icon]".
function bullet(name) {
    return expressBullets[name] || (bullets.indexOf(name) >= 0 ? name : "")
}

// A message as pieces to lay out in a row: [{text: "Downtown ", bullet: ""}, {text: "", bullet: "4"}, ...]
function pieces(message) {
    var result = []
    message.split(/(\[[^\]]*\])/).forEach(function (part) {
        var marker = /^\[(.*)\]$/.exec(part)
        if (marker && bullet(marker[1]))
            result.push({ text: "", bullet: bullet(marker[1]) })
        else if (!marker && part)
            result.push({ text: part, bullet: "" })
    })
    return result
}

function escape(text) {
    return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
}

// A bullet asset as styled text, `size` pixels across.
function image(asset, bulletsUrl, size) {
    return '<img src="' + bulletsUrl + "NYCS-bull-trans-" + asset + '.svg" width="' + size + '" height="'
        + size + '" align="middle">'
}

// A message as styled text for a wrapping Text, with bullets `size` pixels across.
function styled(message, bulletsUrl, size) {
    return escape(message).replace(/\[([^\]]*)\]/g, function (marker, name) {
        var asset = bullet(name)
        return asset ? image(asset, bulletsUrl, size) : ""
    })
}

// The bullets of a message's routes as styled text.
function routeBullets(routes, bulletsUrl, size) {
    return routes.map(function (route) { return image(route.bullet, bulletsUrl, size) }).join("")
}

// "Updated 15 mins ago" for a message's updated_minutes, as the portrait screens put
// it; "" if the message doesn't say.
function updated(minutes) {
    if (minutes === null || minutes === undefined)
        return ""
    if (minutes < 1)
        return "Updated just now"
    var hours = Math.floor(minutes / 60), days = Math.floor(hours / 24)
    var count = days || hours || minutes, unit = days ? "day" : hours ? "hr" : "min"
    return "Updated " + count + " " + unit + (count === 1 ? "" : "s") + " ago"
}
