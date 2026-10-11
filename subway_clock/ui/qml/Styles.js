.pragma library

// Colours for each settings.style, from the MTA's designs and photos of its platform clocks.
var colors = {
    // The LCD clocks on the lettered lines
    classic: {
        background: "#ffffff",
        text: "#000000",
        separator: "#808080",
        arrivingBackground: "#000000",
        arrivingText: "#ffd200",
        statusBackground: "#000000",
        statusAccent: "#555555",
        statusText: "#ffffff",
    },
    // The newer clocks with a card per train, from the MTA's design. An arriving
    // train's card is inverted, as in photos.
    new: {
        background: "#000000",
        number: "#c8c8cc",
        card: "#2d2d33",
        text: "#ffffff",
        arrivingCard: "#e8eff8",
        arrivingText: "#14161c",
        alertBar: "#fcd116",
        alertCard: "#ffffff",
        alertText: "#000000",
        messageBackground: "#fcd116",
        messageText: "#000000",
    },
    // The LED signs on the numbered lines. Their dots can only be red, green or
    // amber, so each route's bullet is the nearest of those to its colour.
    led: {
        background: "#17170d",
        text: "#a8f000",
        arriving: "#ff9a1f",
        bullets: {
            "1": "#ff2244", "2": "#ff2244", "3": "#ff2244",
            "4": "#a8f000", "5": "#a8f000", "6": "#a8f000", "6X": "#a8f000", "G": "#a8f000",
            "B": "#ff9a1f", "D": "#ff9a1f", "F": "#ff9a1f", "FX": "#ff9a1f", "M": "#ff9a1f",
            "N": "#ff9a1f", "Q": "#ff9a1f", "R": "#ff9a1f", "W": "#ff9a1f", "J": "#ff9a1f", "Z": "#ff9a1f",
        },
    },
}
