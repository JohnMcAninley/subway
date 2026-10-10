from google.transit import gtfs_realtime_pb2

from subway_clock.core.clock import Clock
from subway_clock.core.feeds import ROUTE_FEEDS
from subway_clock.core.gtfs import StaticTables
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


def FakeStatic(stop_routes=None, headsigns=None, stop_names=None):
    """StaticTables for parent stops in stop_routes and their N/S platforms."""
    stop_routes = stop_routes or {"633": ["6", "6X"]}
    parents = {stop + direction: stop for stop in stop_routes for direction in ("", "N", "S")}
    return StaticTables(stop_names or {}, parents, stop_routes, headsigns or {})


def make_clock(*trips, static=None, feeds=None, **settings):
    """A Clock refreshed at NOW.

    Each trip is served by its route's feed, unless feeds maps URL -> FeedMessage
    (feeds left out are empty).
    """
    static = static or FakeStatic(headsigns={t[0]: f"Dest {t[0]}" for t in trips})
    fetched = []

    def fetch(feed_url):
        fetched.append(feed_url)
        if feeds is not None:
            return feeds.get(feed_url, feed())
        return feed(*[t for t in trips if url(t[1]) == feed_url])

    clock = Clock(Settings(**settings), static, fetch_feed=fetch)
    clock.refresh(now=NOW)
    clock.fetched = fetched
    return clock


def url(route):
    return ROUTE_FEEDS[route]
