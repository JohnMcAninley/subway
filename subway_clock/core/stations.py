"""Finding stations by name, to choose a clock's stops without knowing GTFS stop IDs.

A Station here is what a rider means by one: a whole complex, such as Union Sq
with its 4/5/6, L and N/Q/R/W platforms, or a station on its own. Each of its
stops is one line's platforms, and each direction of a stop has the ID to put
in the `stops` setting. Where a direction has platforms of its own for some of
its routes, as at Atlantic Av, where the 2 and 3 stop at the sides and the 4
and 5 at an island between, each of them is a direction of its own, with a
track in its ID (see gtfs.split_track).

The search is for a picker that narrows as the user types, not for free text:
every word typed has to start a word of one of the station's names, or be one
of its routes. So "union" finds 14 St-Union Sq, "86 q" the 86 St on the Q, and
"west 4th street" finds W 4 St-Wash Sq. It doesn't correct spelling.
"""
import collections
import json
import re
from dataclasses import dataclass

from .gtfs import STATIONS_PATH, split_track

# The MTA's abbreviations and what a user might type instead. Station names
# use both forms ("Park Place", "Bay Ridge Av", "Avenue U"), so each word
# matches as any form in its group.
ABBREVIATIONS = [
    {"av", "avs", "avenue", "avenues"},
    {"st", "sts", "street", "streets", "saint"},
    {"sq", "square"},
    {"blvd", "boulevard"},
    {"pkwy", "parkway"},
    {"hwy", "highway"},
    {"tpke", "turnpike"},
    {"rd", "road"},
    {"pl", "place"},
    {"ln", "lane"},
    {"pk", "park"},
    {"hts", "heights"},
    {"ctr", "center"},
    {"mt", "mount"},
    {"wash", "washington"},
    {"e", "east"},
    {"w", "west"},
]
WORD_FORMS = {word: group for group in ABBREVIATIONS for word in group}


@dataclass(frozen=True)
class Direction:
    stop_id: str  # the directional stop ID, e.g. "635S", or a platform of it, e.g. "235S:1"
    label: str  # the MTA's name for the direction, e.g. "Downtown & Brooklyn"; "" if unknown
    routes: tuple[str, ...] = ()  # a platform's routes; empty for the stop's


@dataclass(frozen=True)
class Stop:
    stop_id: str  # the parent stop ID, e.g. "635", which as a setting means every direction
    name: str  # e.g. "14 St-Union Sq"
    routes: tuple[str, ...]  # GTFS route IDs scheduled here, e.g. ("4", "5", "6", "6X")
    directions: tuple[Direction, ...]  # the directions trains leave in: one at a terminal, otherwise two


@dataclass(frozen=True)
class Station:
    name: str  # its stops' names, e.g. "14 St-Union Sq" or "Court Sq / Court Sq-23 St"
    borough: str  # "M", "Bk", "Q", "Bx" or "SI"; "" if unknown
    stops: tuple[Stop, ...]

    @property
    def routes(self):
        """Every route at the station, in the order of its stops."""
        return tuple(dict.fromkeys(route for stop in self.stops for route in stop.routes))


def load_complexes(path=STATIONS_PATH):
    """Map each parent stop ID in the bundled station list to its complex ID.

    Stations joined by a free transfer share a complex. This is the MTA's own
    grouping; the transfers in the GTFS also join stations that are a walk
    along the street apart, such as Lexington Av/59 St and Lexington Av/63 St.
    """
    with open(path, encoding="utf-8") as f:
        return {stop: station["complex"] for stop, station in json.load(f).items() if "complex" in station}


def words(text):
    """The words of a name or a query, lower case, without punctuation or ordinal endings ("14th" -> "14")."""
    found = re.findall(r"[a-z0-9]+", text.lower().replace("'", ""))
    return [re.sub(r"^(\d+)(st|nd|rd|th)$", r"\1", word) for word in found]


def name_order(name):
    """A sort key that puts "5 Av" before "14 St"."""
    return [(0, int(word), "") if word.isdigit() else (1, 0, word) for word in words(name)]


class StationPicker:
    """Every station in static (a gtfs.StaticTables), searchable by name.

    complexes maps parent stop IDs to complex IDs, by default the bundled
    list's; a stop it leaves out is a station on its own.
    """

    def __init__(self, static, complexes=None):
        if complexes is None:
            complexes = load_complexes()
        grouped = collections.defaultdict(list)
        for stop_id in sorted(set(static.stop_parents.values())):
            if stop_id in static.stop_names:
                grouped[complexes.get(stop_id, f"stop {stop_id}")].append(self._stop(static, stop_id))

        self.stations = []
        self._by_stop = {}
        self._terms = {}  # Station -> (the forms of its names' words, its routes as typed)
        for stops in grouped.values():
            # The name most of its stops share comes first: "Times Sq-42 St / 42 St-Port Authority Bus Terminal"
            names = collections.Counter(stop.name for stop in stops)
            station = Station(" / ".join(name for name, _ in names.most_common()),
                              static.borough(stops[0].stop_id), tuple(stops))
            self.stations.append(station)
            for stop in stops:
                self._by_stop[stop.stop_id] = station
            name_words = {form for name in names for word in words(name) for form in WORD_FORMS.get(word, {word})}
            # Expresses are found as their locals: the 6X is a 6 to whoever is typing
            routes = {r for route in station.routes for r in (route.lower(), route.lower().removesuffix("x"))}
            self._terms[station] = (name_words, routes)
        self.stations.sort(key=lambda station: name_order(station.name))

    @staticmethod
    def _stop(static, stop_id):
        labels = static.direction_labels.get(stop_id)
        if not labels:
            # Not in the station list, so offer both directions unnamed
            labels = {"N": "", "S": ""}
        directions = tuple(Direction(f"{stop_id}{d}:{platform['track']}", labels[d], tuple(platform["routes"]))
                           if platform else Direction(stop_id + d, labels[d])
                           for d in "NS" if d in labels for platform in static.platforms.get(stop_id + d) or [None])
        return Stop(stop_id, static.stop_names[stop_id], tuple(static.stop_routes.get(stop_id, ())), directions)

    def search(self, query, limit=None):
        """Stations matching every word of query, best first; all of them, by name, if query is empty.

        A word typed in full counts for more than the start of one, so "14"
        lists the 14 St stations ahead of 145 St; busier stations then come
        first.
        """
        query_words = words(query)
        if not query_words:
            return self.stations[:limit]
        matches = []
        for station in self.stations:
            name_words, routes = self._terms[station]
            scores = [self._score(word, name_words, routes) for word in query_words]
            if all(scores):
                matches.append((-sum(scores), -len(station.routes), len(matches), station))
        return [match[-1] for match in sorted(matches)[:limit]]

    @staticmethod
    def _score(word, name_words, routes):
        if word in name_words or word in routes:
            return 2
        return 1 if any(name_word.startswith(word) for name_word in name_words) else 0

    def station_for(self, stop_id):
        """The Station a stop ID (directional or parent, or a platform) belongs to, or None."""
        stop_id, _ = split_track(stop_id)
        return self._by_stop.get(stop_id) or self._by_stop.get(stop_id[:-1])
