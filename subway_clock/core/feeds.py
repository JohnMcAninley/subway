"""MTA GTFS-realtime feeds: which feed carries which route, and reading trip updates and alerts from them."""
import json
from dataclasses import dataclass
from pathlib import Path

import requests
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

    def active(self, now):
        return not self.periods or any(start <= now and (not end or now < end) for start, end in self.periods)

    @property
    def planned(self):
        """Planned work, as opposed to something happening now like delays."""
        return not self.id.startswith("lmm:alert:")


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
        alerts.append(Alert(entity.id, text, tuple((p.start, p.end) for p in alert.active_period), affects))
    return alerts
