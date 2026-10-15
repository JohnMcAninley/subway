"""The settings menu: what it lists and what each key does. No Qt here, so it can be tested without a screen.

Display passes it the keys pressed and draws view() with qml/SettingsMenu.qml.
A mouse does what the keys do: a click on the clock opens it, a click on a row
is Enter there, the wheel moves up and down, and a button stands in for Esc.

It has three pages. "main" lists the settings: Left and Right change the one
selected, at once. Its first row opens "search", which finds a station as its
name is typed (core/stations.py), and a station opens "station", which lists
its platforms' directions to tick. The stops ticked take effect on going back
to the main page, all together, so the clock fetches once rather than at
every tick; and if none are ticked the clock keeps the stops it had.
"""
import dataclasses

from ..core.board import bullet_id
from ..core.gtfs import split_track
from ..core.settings import ROTATIONS, STYLES
from ..core.stations import StationPicker

# The settings on the main page after the stops: (setting, label, what to call each value)
CHOICES = (
    ("style", "Style", {"classic": "Classic", "new": "New", "led": "LED"}),
    ("show_station", "Station name", {False: "Off", True: "On"}),
    ("show_alerts", "Service alerts", {False: "Off", True: "On"}),
    ("rotation", "Last line shows", {"auto": "What the real clocks do", "all": "Every train", "unique": "Each route once"}),
    ("fetch_all_feeds", "Fetch every feed", {False: "Off", True: "On"}),
)
assert tuple(CHOICES[0][2]) == STYLES and set(CHOICES[3][2]) == set(ROTATIONS)

BOROUGHS = {"M": "Manhattan", "Bk": "Brooklyn", "Q": "Queens", "Bx": "The Bronx", "SI": "Staten Island"}

OPEN_KEYS = ("enter", "m", "M")
MAX_RESULTS = 40
MAX_QUERY = 40

TITLES = {"main": "Settings", "search": "Choose a station"}
KEYS = {
    "main": "Up and Down to move, Left and Right to change, Esc to close",
    "search": "Type to search, Up and Down to move, Enter to open a station, Esc to go back",
    "station": "Up and Down to move, Enter to tick or untick, Esc to go back",
}
PROMPT = "Type part of a station's name, or a route"
NO_MATCH = "No station matches"
NO_STOPS = "No stops are ticked. The clock keeps the ones it has until some are."
LOADING = "Loading schedules"


def row(label, value="", detail="", bullets=(), checked=None):
    """A line of the menu. checked is None for a line with no box to tick."""
    return {"label": label, "value": value, "detail": detail, "bullets": [bullet_id(route) for route in bullets],
            "box": checked is not None, "checked": bool(checked)}


class Menu:
    """clock: the Clock whose settings these are. apply(settings): put new ones into effect, and save them.

    complexes is for the StationPicker; None is the bundled list.
    """

    def __init__(self, clock, apply, complexes=None):
        self.clock = clock
        self.apply = apply
        self.complexes = complexes
        self.open = False
        self.page = "main"
        self.index = 0  # the selected row of the page
        self.query = ""
        self.picker = None
        self.chosen = []  # on the stops pages: the directional stop IDs ticked, in the order to save them
        self.station = None  # on the station page
        self._found = 0  # the row of the search page to go back to

    def key(self, key):
        """Act on a key: "up", "down", "left", "right", "enter", "escape", "backspace" or a character typed.

        Returns True if the key was the menu's, which every key is while it is open.
        """
        if not self.open:
            if key not in OPEN_KEYS:
                return False
            self.open, self.page, self.index = True, "main", 0
            return True
        count = len(self._rows())
        if key in ("up", "down"):
            if count:
                self.index = (self.index + (1 if key == "down" else -1)) % count
        else:
            {"main": self._main_key, "search": self._search_key, "station": self._station_key}[self.page](key)
        return True

    def click(self, index=None):
        """Act on a click: on the row at index, or, while the menu is closed, anywhere on the clock."""
        if not self.open:
            self.key("enter")
        elif index is not None and 0 <= index < len(self._rows()):
            self.index = index
            self.key("enter")

    def back(self):
        """Go back a page, or from the main page, close: what Esc does."""
        if self.open:
            self.key("escape")

    def scroll(self, rows):
        """Move down by rows (up, if negative), stopping at the ends where the keys would wrap."""
        if self.open:
            self.index = max(0, min(self.index + rows, len(self._rows()) - 1))

    def _main_key(self, key):
        if key == "escape":
            self.open = False
        elif self.index == 0:
            if key in ("enter", "right", " ") and self.clock.static.ready:
                self.picker = StationPicker(self.clock.static, self.complexes)
                self.chosen = self._expand(self.clock.settings.stops)
                self.page, self.index, self.query = "search", 0, ""
        elif key in ("left", "right", "enter", " "):
            setting, _, names = CHOICES[self.index - 1]
            values = list(names)
            step = -1 if key == "left" else 1
            value = values[(values.index(getattr(self.clock.settings, setting)) + step) % len(values)]
            self.apply(dataclasses.replace(self.clock.settings, **{setting: value}))

    def _search_key(self, key):
        stations = self._stations()
        if key == "escape":
            stops = self._collapse()
            if self.chosen and set(self.chosen) != set(self._expand(self.clock.settings.stops)):
                self.apply(dataclasses.replace(self.clock.settings, stops=stops))
            self.page, self.index = "main", 0
        elif key == "enter":
            if stations:
                self.station, self._found = stations[self.index], self.index
                # Start at a direction that is ticked, as unticking it is the likeliest thing to want.
                ticked = [i for i, (_, d) in enumerate(self._directions()) if d.stop_id in self.chosen]
                self.page, self.index = "station", ticked[0] if ticked else 0
        elif key == "backspace":
            self.query, self.index = self.query[:-1], 0
        elif len(key) == 1 and key.isprintable() and len(self.query) < MAX_QUERY:
            self.query, self.index = self.query + key, 0

    def _station_key(self, key):
        if key in ("escape", "left", "backspace"):
            # A station found with nothing typed is listed because it had stops ticked, and may not be now.
            self.page, self.index = "search", min(self._found, max(0, len(self._stations()) - 1))
        elif key in ("enter", " "):
            stop_id = self._directions()[self.index][1].stop_id
            if stop_id in self.chosen:
                self.chosen.remove(stop_id)
            else:
                self.chosen.append(stop_id)

    def _stop(self, stop_id, parent):
        """The picker's Stop for a parent stop ID (parent) or for a direction's, or None if it doesn't have it."""
        station = self.picker.station_for(stop_id)
        wanted = stop_id if parent else split_track(stop_id)[0][:-1]
        return next((stop for stop in station.stops if stop.stop_id == wanted), None) if station else None

    def _expand(self, stops):
        """The stops setting as directional IDs: a parent stop becomes each of its directions.

        So does a direction with platforms of its own become each of them.
        """
        expanded = []
        for stop_id in stops:
            stop = self._stop(stop_id, parent=True)
            if stop:
                expanded += [direction.stop_id for direction in stop.directions]
                continue
            stop = self._stop(stop_id, parent=False)
            platforms = [d.stop_id for d in stop.directions
                         if d.stop_id != stop_id and split_track(d.stop_id)[0] == stop_id] if stop else []
            expanded += platforms or [stop_id]
        return list(dict.fromkeys(expanded))

    def _collapse(self):
        """The stops ticked as a stops setting: a stop with every direction ticked becomes its parent stop."""
        stops = []
        for stop_id in self.chosen:
            stop = self._stop(stop_id, parent=False)
            whole = stop and len(stop.directions) > 1 and all(d.stop_id in self.chosen for d in stop.directions)
            stops.append(stop.stop_id if whole else stop_id)
        return list(dict.fromkeys(stops))

    def _stations(self):
        """The search page's stations: those found, or with nothing typed, those with stops ticked."""
        if self.query.strip():
            return self.picker.search(self.query, MAX_RESULTS)
        return list(dict.fromkeys(filter(None, map(self.picker.station_for, self.chosen))))

    def _directions(self):
        """The station page's lines: (stop, direction) for each direction of each of the station's stops."""
        return [(stop, direction) for stop in self.station.stops for direction in stop.directions]

    def _rows(self):
        if self.page == "main":
            settings = self.clock.settings
            return [row("Station", self._where())] + [
                row(label, names[getattr(settings, setting)]) for setting, label, names in CHOICES]
        if self.page == "search":
            return [self._station_row(station) for station in self._stations()]
        several = len({stop.name for stop in self.station.stops}) > 1
        return [row(direction.label or direction.stop_id, direction.stop_id, stop.name if several else "",
                    direction.routes or stop.routes, direction.stop_id in self.chosen)
                for stop, direction in self._directions()]

    def _where(self):
        if not self.clock.static.ready:
            return LOADING
        board = self.clock.board()
        return ", ".join(filter(None, (board.station, board.direction))) or ", ".join(self.clock.settings.stops)

    def _station_row(self, station):
        # Its directions that are ticked, each said once: "Downtown & Brooklyn" for all three platforms at Union Sq
        ticked = dict.fromkeys(direction.label or direction.stop_id for stop in station.stops
                               for direction in stop.directions if direction.stop_id in self.chosen)
        # The express is the same line to whoever is choosing: no diamond beside the circle
        routes = [route for route in station.routes if not (route.endswith("X") and route[:-1] in station.routes)]
        return row(station.name, BOROUGHS.get(station.borough, ""), ", ".join(ticked), routes)

    def view(self):
        """What to draw: see qml/SettingsMenu.qml."""
        rows = self._rows() if self.open else []
        searching = self.open and self.page == "search"
        empty = ""
        if searching and not rows:
            empty = NO_MATCH if self.query.strip() else NO_STOPS
        return {
            "open": self.open,
            "page": self.page,
            "title": self.station.name if self.page == "station" else TITLES[self.page],
            "query": self.query,
            "prompt": PROMPT,
            "empty": empty,
            "rows": rows,
            "index": self.index,
            "keys": KEYS[self.page],
            "back": "Close" if self.page == "main" else "Back",
        }
