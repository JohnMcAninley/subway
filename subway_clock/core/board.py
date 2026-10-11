"""The screen description: everything a renderer needs to draw the clock, and nothing else.

Renderers draw a Board as-is. All decisions about which trains appear where
are made in the core, so every front end shows the same thing.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Row:
    number: int  # 1-based position in the upcoming train list (or in its group, on a grouped board)
    route: str  # GTFS route_id, e.g. "6X"
    bullet: str  # bullet asset id, e.g. "6d" for the 6 express diamond
    destination: str
    direction: str  # the platform's direction label, e.g. "Uptown & The Bronx"; "" if there isn't one
    headline: str  # how the newer clocks head the train, e.g. "Downtown & Brooklyn"
    detail: str  # what they show under the headline, usually the destination; may be ""
    minutes: int
    arriving: bool


@dataclass(frozen=True)
class Message:
    text: str  # a service alert; routes are in brackets, like "[4]"
    planned: bool  # planned work, as opposed to something happening now like delays
    title: str = ""  # what kind of alert it is, e.g. "Delays" or "Stops Skipped"; "" if the feed doesn't say
    updated_minutes: int | None = None  # how long ago it was last changed; None if the feed doesn't say
    # A route's trains aren't running, or aren't stopping, at the stops: the alert says so and
    # none of the route's trains are on their way.
    no_service: bool = False


@dataclass(frozen=True)
class Group:
    heading: str  # the direction label its trains share; may be ""
    rows: tuple[Row, ...]


@dataclass(frozen=True)
class Route:
    route: str  # GTFS route_id, e.g. "6X"
    bullet: str  # bullet asset id, e.g. "6d"


@dataclass(frozen=True)
class Board:
    style: str
    rows: tuple[Row, ...]  # top to bottom
    stale: bool = False  # live data is out of date, e.g. the network is down
    messages: tuple[Message, ...] = ()  # service alerts to show, most urgent first
    # In styles that show alerts in place of the last line: the text of the one to show there now, or "".
    message: str = ""
    # On a grouped board showing more than one direction: the same rows, split by direction.
    groups: tuple[Group, ...] = ()
    # Where the clock is, for screens that say so, as the sign over a station entrance does:
    # the names of the chosen stops' stations ("14 St-Union Sq"; " / " between them if they
    # differ), the routes scheduled to stop there, and the direction label the stops share
    # ("Downtown & Brooklyn"), or "" when they cover more than one.
    station: str = ""
    direction: str = ""
    routes: tuple[Route, ...] = ()


# Route IDs whose bullet isn't named after the route
SPECIAL_BULLETS = {
    "GS": "S",  # 42 St Shuttle
    "FS": "SF",  # Franklin Av Shuttle
    "H": "SR",  # Rockaway Park Shuttle
    "SI": "SIR",  # Staten Island Railway
}


def bullet_id(route_id):
    """Bullet asset id for a route. Express routes end in X; their diamond bullets end in d."""
    if route_id in SPECIAL_BULLETS:
        return SPECIAL_BULLETS[route_id]
    if route_id.endswith("X"):
        return route_id[:-1] + "d"
    return route_id
