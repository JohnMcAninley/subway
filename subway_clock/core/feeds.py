"""MTA GTFS-realtime feeds: which feed carries which route, and reading trip updates and alerts from them."""
import json
import re
from dataclasses import dataclass
from pathlib import Path

import requests
from google.protobuf import empty_pb2, unknown_fields
from google.transit import gtfs_realtime_pb2

with open(Path(__file__).with_name("feeds.json"), encoding="utf-8") as f:
    _FEEDS = json.load(f)

ROUTE_FEEDS = {route: _FEEDS["base"] + suffix for suffix, routes in _FEEDS["feeds"].items() for route in routes}
ALL_FEED_URLS = sorted(set(ROUTE_FEEDS.values()))
ALERTS_URL = _FEEDS["alerts"]  # service alerts for every route, in one feed


def feed_urls(routes):
    """URLs of the feeds carrying any of routes, in a stable order. Unknown routes are ignored."""
    return sorted({ROUTE_FEEDS[route] for route in routes if route in ROUTE_FEEDS})


# Shared so each refresh reuses the last one's connections; setting them up is most of a fetch.
_session = requests.Session()
_session.mount("https://", requests.adapters.HTTPAdapter(pool_maxsize=len(ALL_FEED_URLS) + 1))


def fetch_feed(url):
    response = _session.get(url, timeout=10)
    response.raise_for_status()
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(response.content)
    return feed


@dataclass(frozen=True)
class Prediction:
    trip_id: str
    route_id: str
    stop_id: str
    time: int  # POSIX time the train arrives at (or, at its first stop, departs) stop_id
    trip_stops: tuple[str, ...]  # stop IDs the trip has left to visit, in order


def get_predictions(feed, stops):
    """Upcoming trains in feed at any of stops.

    Stops are directional stop IDs ("633S"), or parent stop IDs ("633") for
    both directions. Realtime stop IDs are always directional.
    """
    predictions = []

    for entity in feed.entity:
        if entity.HasField('trip_update'):
            trip = entity.trip_update
            trip_stops = tuple(stop_time.stop_id for stop_time in trip.stop_time_update)
            for stop_time in trip.stop_time_update:
                stop_id = stop_time.stop_id
                # A trip's first stop often has only a departure time.
                arrives = stop_time.arrival.time or stop_time.departure.time
                if arrives and (stop_id in stops or stop_id[:-1] in stops):
                    predictions.append(Prediction(trip.trip.trip_id, trip.trip.route_id, stop_id, arrives, trip_stops))

    return predictions


@dataclass(frozen=True)
class Alert:
    id: str
    text: str  # one line; routes are written in brackets, like "[4]"
    periods: tuple[tuple[int, int], ...]  # (start, end) POSIX times it is active; end 0 means no end
    # What it affects: (route_id, parent stop ID, "N" or "S"), each "" if not given
    affects: tuple[tuple[str, str, str], ...]
    kind: str = ""  # the MTA's type for it, e.g. "Delays" or "Planned - Part Suspended"; "" if not given
    updated: int = 0  # POSIX time it was last changed; 0 if not given
    toward: tuple[str, ...] = ()  # where its text says the trains are headed: see headings()

    def active(self, now):
        return not self.periods or any(start <= now and (not end or now < end) for start, end in self.periods)

    @property
    def planned(self):
        """Planned work, as opposed to something happening now like delays."""
        return not self.id.startswith("lmm:alert:")

    @property
    def title(self):
        """A short name for what is going on, e.g. "Delays" or "Part Suspended"; "" if the type isn't given."""
        return self.kind.removeprefix("Planned - ")

    @property
    def no_service(self):
        """True if it is about trains not running, or not stopping, where it applies."""
        return self.title in NO_SERVICE_TITLES


# The alert types that mean a route's trains aren't coming to the stops the alert names.
NO_SERVICE_TITLES = ("Suspended", "Part Suspended", "Stops Skipped", "No Scheduled Service")

# The MTA's extension to GTFS-realtime alerts ("Mercury"): field 1001 of an alert, a message
# whose own fields include these. The bindings don't know it, so it arrives as unknown fields.
MERCURY_ALERT = 1001
MERCURY_UPDATED_AT = 2
MERCURY_ALERT_TYPE = 3

_COMPASS = {"uptown": "N", "northbound": "N", "downtown": "S", "southbound": "S"}
# "Uptown", "southbound" and so on, or a place before "-bound": "Coney Island-bound". Not
# "the Manhattan-bound platform", which says where to board and not which trains.
_HEADING = re.compile(r"\b((?i:uptown|downtown|northbound|southbound))\b(?! (?:platform|track))"
                      r"|((?:[A-Z0-9][\w./']* )*[A-Z0-9][\w./']+)-bound\b(?! (?:platform|track))")


def headings(text):
    """Where an alert's text says its trains are headed, for the many alerts that only say so there.

    "N" for each "uptown" or "northbound" and "S" for each "downtown" or
    "southbound"; and the place for each "Woodlawn-bound", which is "N" or "S"
    depending on the route (and, for "Manhattan-bound", on the stop). The place
    comes with any capitalised words before it, as in "No Jamaica". Empty if
    the text names no direction, or says "both directions".
    """
    if "both directions" in text.lower():
        return ()
    found = (_COMPASS.get(compass.lower(), place) for compass, place in _HEADING.findall(text))
    return tuple(dict.fromkeys(found))


def _unknown(message, number):
    """The values of a message's fields with this number, when they aren't in its definition."""
    return [field.data for field in unknown_fields.UnknownFieldSet(message) if field.field_number == number]


def get_alerts(feed):
    """Every alert in the alerts feed that has English text."""
    alerts = []
    for entity in feed.entity:
        if not entity.HasField("alert"):
            continue
        alert = entity.alert
        text = next((t.text for t in alert.header_text.translation if t.language == "en"), "")
        text = " ".join(text.split())
        if not text:
            continue
        affects = tuple((e.route_id, e.stop_id, ("N", "S")[e.direction_id] if e.HasField("direction_id") else "")
                        for e in alert.informed_entity)
        kind, updated = "", 0
        for data in _unknown(alert, MERCURY_ALERT):
            mercury = empty_pb2.Empty.FromString(data)  # Every field of it is unknown to Empty
            kind = next((value.decode("utf-8") for value in _unknown(mercury, MERCURY_ALERT_TYPE)), "")
            updated = next(iter(_unknown(mercury, MERCURY_UPDATED_AT)), 0)
        alerts.append(Alert(entity.id, text, tuple((p.start, p.end) for p in alert.active_period), affects,
                            kind, updated, headings(text)))
    return alerts
