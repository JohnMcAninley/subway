from google.transit import gtfs_realtime_pb2

from subway_clock.core.clock import Clock
from subway_clock.core.feeds import ROUTE_FEEDS
from subway_clock.core.settings import Settings

NOW = 1_000_000.0


def trip(trip_id, route_id, stop_times):
    """A trip update; stop_times is [(stop_id, minutes from NOW), ...].

    Add "departure" to a stop time, as in (stop_id, minutes, "departure"), for a
    stop with only a departure time, like a trip's first stop.
    """
    return (trip_id, route_id, stop_times)


def feed(*trips):
    message = gtfs_realtime_pb2.FeedMessage()
    message.header.gtfs_realtime_version = "1.0"
    message.header.timestamp = int(NOW)
    for trip_id, route_id, stop_times in trips:
        entity = message.entity.add(id=trip_id)
        entity.trip_update.trip.trip_id = trip_id
        entity.trip_update.trip.route_id = route_id
        for stop_id, minutes, *kind in stop_times:
            update = entity.trip_update.stop_time_update.add(stop_id=stop_id)
            event = update.departure if kind == ["departure"] else update.arrival
            event.time = int(NOW + minutes * 60)
    return message


class FakeStatic:
    def __init__(self, stop_routes=None, headsigns=None, stop_names=None):
        self.stop_routes = stop_routes or {"633": ["6", "6X"]}
        self.headsigns = headsigns or {}
        self.stop_names = stop_names or {}

    def refresh(self):
        pass

    def routes_for(self, stops):
        return sorted({route for stop in stops for route in self.stop_routes.get(stop[:3], ())})


def make_clock(*trips, static=None, feeds=None, **settings):
    """A Clock refreshed at NOW. Trips go in every feed unless feeds maps URL -> FeedMessage."""
    static = static or FakeStatic(headsigns={t[0]: f"Dest {t[0]}" for t in trips})
    fetched = []

    def fetch(url):
        fetched.append(url)
        return feeds[url] if feeds is not None else feed(*trips)

    clock = Clock(Settings(**settings), static, fetch_feed=fetch)
    clock.refresh(now=NOW)
    clock.fetched = fetched
    return clock


def url(route):
    return ROUTE_FEEDS[route]
