"""What the newer clocks say about a train: a headline and a line of detail under it.

They head each train with its direction as announced ("Downtown & Brooklyn")
over its terminal, rather than the terminal alone, which may mean nothing to
riders at the other end of the line. The MTA's own table of these isn't
public, so this works them out from the platform's direction label and the
boroughs the train has left to visit.
"""

BOROUGH_NAMES = {"M": "Manhattan", "Bk": "Brooklyn", "Q": "Queens", "Bx": "The Bronx", "SI": "Staten Island"}


def headline(label, here, ahead, destination):
    """(headline, detail) for a train.

    label: the platform's direction label, e.g. "Uptown & The Bronx", or ""
    here: the station's borough code, or "" if unknown
    ahead: borough codes of the stops the train has left to visit, in order, ending with its
        terminal's; empty if they aren't known
    destination: the terminal's name
    """
    if not here or not ahead:
        # Not enough to go on: the platform's label if it has one
        return (label, destination) if label else (destination, "")

    crossing = list(dict.fromkeys(b for b in ahead if b != here))  # other boroughs it will enter, in order
    ends = ahead[-1]
    base = label.split(" ")[0]
    if base in ("Uptown", "Downtown"):
        # Within Manhattan: the direction, and the borough it goes on to, if any
        return (f"{base} & {BOROUGH_NAMES[crossing[0]]}" if crossing else base, destination)
    if "M" in crossing:
        # Heading into Manhattan, and perhaps out the other side
        return ("Manhattan" if ends == "M" else f"Manhattan & {BOROUGH_NAMES[ends]}", destination)
    # Past Manhattan, or never going there: the terminal is what tells trains apart
    return (destination, BOROUGH_NAMES[ends])
