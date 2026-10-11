.pragma library

// Colours for each settings.style, picked from photos of the MTA's platform clocks.
var colors = {
    // The LCD clocks on the lettered lines
    classic: {
        background: "#d4edf7",
        text: "#1b2a4e",
        separator: "#9cb8c6",
        arrivingBackground: "#000000",
        arrivingText: "#ffd200",
        statusBackground: "#000000",
        statusAccent: "#2d6f80",
        statusText: "#ffffff",
    },
    // The newer clocks with a card per train. An arriving train's card is inverted.
    new: {
        background: "#060b17",
        number: "#ffffff",
        card: "#1d3f86",
        text: "#ffffff",
        arrivingCard: "#e8eff8",
        arrivingText: "#10245a",
        messageBackground: "#ffd200",
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
