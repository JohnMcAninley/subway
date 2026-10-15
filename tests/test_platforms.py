"""Platforms told apart by track, where one stop ID has several in a direction, as at Atlantic Av."""
from conftest import NOW, alert, alerts_feed, feed, trip, url
from subway_clock.core.clock import Clock
from subway_clock.core.feeds import ALERTS_URL, get_predictions
from subway_clock.core.gtfs import StaticTables, load_platforms, split_track
from subway_clock.core.settings import Settings
from subway_clock.core.stations import Direction, StationPicker
from subway_clock.ui.menu import Menu

# Atlantic Av: the 2 and 3 at the side platforms, on tracks 1 (south) and 4 (north); the
# 4 and 5 at the island between, on tracks 2 and 3.
PLATFORMS = {
    "235N": [{"track": "4", "routes": ["2", "3"]}, {"track": "3", "routes": ["4", "5"]}],
    "235S": [{"track": "1", "routes": ["2", "3"]}, {"track": "2", "routes": ["4", "5"]}],
}


def atlantic():
    return StaticTables(
        stop_names={stop: "Atlantic Av-Barclays Ctr" for stop in ("235", "235N", "235S")},
        stop_parents={"235": "235", "235N": "235", "235S": "235"},
        stop_routes={"235": ["2", "3", "4", "5"]},
        headsigns={},
        direction_labels={"235": {"N": "Manhattan", "S": "Flatbush - New Lots"}},
        stop_boroughs={"235": "Bk"},
        platforms=PLATFORMS)


TRIPS = feed(
    trip("two", "2", [("235S", 1, "track 1")]),
    trip("four", "4", [("235S", 2, "track 2")]),
    trip("three", "3", [("235S", 3)]),  # No track given
    trip("five", "5", [("235S", 4, "scheduled 1", "track 2")]),  # Moved to the express track
    trip("north", "2", [("235N", 5, "track 4")]),
)


def trip_ids(stops):
    return [prediction.trip_id for prediction in get_predictions(TRIPS, stops)]


def make_clock(stops, alerts=()):
    feeds = {url("2"): TRIPS, ALERTS_URL: alerts_feed(*alerts)}
    clock = Clock(Settings(stops=stops), atlantic(), fetch_feed=lambda u: feeds.get(u, feed()))
    clock.refresh(now=NOW)
    return clock


def test_a_stop_with_a_track_is_one_platform():
    assert split_track("235S:1") == ("235S", "1")
    assert split_track("235S") == ("235S", "")


def test_a_platform_has_the_trains_on_its_track_and_those_with_none_given():
    assert trip_ids(["235S:1"]) == ["two", "three"]
    assert trip_ids(["235S:2"]) == ["four", "three", "five"]  # The track it is on, not the one scheduled
    assert trip_ids(["235S"]) == ["two", "four", "three", "five"]
    assert trip_ids(["235"]) == ["two", "four", "three", "five", "north"]
    assert trip_ids(["235S:1", "235N:4"]) == ["two", "three", "north"]


def test_a_platform_has_its_own_routes_and_the_stops_label_and_name():
    static = atlantic()
    assert static.routes_for(["235S:1"]) == ["2", "3"]
    assert static.routes_for(["235S:1", "235N:3"]) == ["2", "3", "4", "5"]
    assert static.routes_for(["235S:9"]) == ["2", "3", "4", "5"]  # A track it doesn't know is the whole stop
    assert static.direction_label("235S:1") == "Flatbush - New Lots"
    assert static.borough("235S:1") == "Bk"

    board = make_clock(["235S:1"]).board(now=NOW)
    assert [row.route for row in board.rows] == ["2", "3"]
    assert (board.station, board.direction) == ("Atlantic Av-Barclays Ctr", "Flatbush - New Lots")
    assert [route.route for route in board.routes] == ["2", "3"]


def test_alerts_at_the_stop_are_for_the_platforms_routes():
    alerts = [alert("a", "[4] skips Atlantic Av", ("4", "235", 1)),
              alert("b", "[2] skips Atlantic Av", ("2", "235", 1)),
              alert("c", "Station closed", ("", "235", None))]
    assert [m.text for m in make_clock(["235S:1"], alerts).messages(NOW)] == ["[2] skips Atlantic Av"]
    assert len(make_clock(["235S"], alerts).messages(NOW)) == 3


def test_the_picker_offers_each_platform_with_its_routes():
    stop, = StationPicker(atlantic(), {}).stations[0].stops
    assert stop.directions == (Direction("235N:4", "Manhattan", ("2", "3")), Direction("235N:3", "Manhattan", ("4", "5")),
                               Direction("235S:1", "Flatbush - New Lots", ("2", "3")),
                               Direction("235S:2", "Flatbush - New Lots", ("4", "5")))
    assert StationPicker(atlantic(), {}).station_for("235S:1").name == "Atlantic Av-Barclays Ctr"


def menu_for(stops):
    clock = Clock(Settings(stops=stops), atlantic(), fetch_feed=lambda u: feed())
    applied = []
    menu = Menu(clock, applied.append, {})
    for key in ["enter", "enter", "enter"]:  # Open, choose a station, open the one ticked
        menu.key(key)
    return menu, applied


def test_the_menu_ticks_platforms():
    menu, applied = menu_for(["235S:1"])
    view = menu.view()
    assert [(row["label"], row["value"], row["bullets"], row["checked"]) for row in view["rows"]] == [
        ("Manhattan", "235N:4", ["2", "3"], False), ("Manhattan", "235N:3", ["4", "5"], False),
        ("Flatbush - New Lots", "235S:1", ["2", "3"], True), ("Flatbush - New Lots", "235S:2", ["4", "5"], False)]
    for key in ["up", "enter", "escape", "escape"]:  # From the ticked row, up to 235N:3 and tick it
        menu.key(key)
    assert applied[-1].stops == ["235S:1", "235N:3"]


def test_the_menu_ticks_every_platform_of_a_direction_without_a_track():
    menu, applied = menu_for(["235S"])
    assert [row["checked"] for row in menu.view()["rows"]] == [False, False, True, True]
    for key in ["up", "up"]:  # From the first ticked row to the first
        menu.key(key)
    for key in ["enter", "down", "enter", "escape", "escape"]:  # Tick both northbound: the whole station
        menu.key(key)
    assert applied[-1].stops == ["235"]


def test_bundled_platforms():
    platforms = load_platforms()
    assert platforms["235S"] == PLATFORMS["235S"] and platforms["235N"] == PLATFORMS["235N"]
    for stop_id, listed in platforms.items():
        assert stop_id[-1] in "NS" and len(listed) > 1
        assert all(platform["track"] and platform["routes"] for platform in listed)
