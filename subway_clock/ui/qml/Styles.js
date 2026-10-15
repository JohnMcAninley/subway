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
    // The LED signs on the numbered lines. Everything is green, bullets included,
    // whatever the route's colour; an arriving train's line turns amber, all but the bullet.
    led: {
        background: "#17170d",
        text: "#a8f000",
        arriving: "#ff9a1f",
    },
}
