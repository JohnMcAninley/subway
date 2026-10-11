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
}
