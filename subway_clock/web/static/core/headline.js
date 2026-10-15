// What the newer clocks say about a train: a headline and a line of detail under it.
// A port of core/headline.py, which says why.

export const BOROUGH_NAMES = { M: "Manhattan", Bk: "Brooklyn", Q: "Queens", Bx: "The Bronx", SI: "Staten Island" }

// [headline, detail] for a train.
//
// label: the platform's direction label, e.g. "Uptown & The Bronx", or ""
// here: the station's borough code, or "" if unknown
// ahead: borough codes of the stops the train has left to visit, in order, ending with its
//     terminal's; empty if they aren't known
// destination: the terminal's name
export function headline(label, here, ahead, destination) {
    if (!here || !ahead.length) {
        // Not enough to go on: the platform's label if it has one
        return label ? [label, destination] : [destination, ""]
    }

    const crossing = [...new Set(ahead.filter(b => b !== here))]  // other boroughs it will enter, in order
    const ends = ahead[ahead.length - 1]
    const base = label.split(" ")[0]
    if (base === "Uptown" || base === "Downtown") {
        // Within Manhattan: the direction, and the borough it goes on to, if any
        return [crossing.length ? base + " & " + BOROUGH_NAMES[crossing[0]] : base, destination]
    }
    if (crossing.includes("M")) {
        // Heading into Manhattan, and perhaps out the other side
        return [ends === "M" ? "Manhattan" : "Manhattan & " + BOROUGH_NAMES[ends], destination]
    }
    // Past Manhattan, or never going there: the terminal is what tells trains apart
    return [destination, BOROUGH_NAMES[ends]]
}
