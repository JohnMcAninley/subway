"""MTA GTFS-realtime feeds: which feed carries which route, and reading trip updates from them."""
import json
from dataclasses import dataclass
from pathlib import Path

import requests
from google.transit import gtfs_realtime_pb2

with open(Path(__file__).with_name("feeds.json"), encoding="utf-8") as f:
    _FEEDS = json.load(f)

ROUTE_FEEDS = {route: _FEEDS["base"] + suffix for suffix, routes in _FEEDS["feeds"].items() for route in routes}
ALL_FEED_URLS = sorted(set(ROUTE_FEEDS.values()))


def feed_urls(routes):
    """URLs of the feeds carrying any of routes, in a stable order. Unknown routes are ignored."""
    return sorted({ROUTE_FEEDS[route] for route in routes if route in ROUTE_FEEDS})


def fetch_feed(url):
    response = requests.get(url, timeout=10)
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
