import json

import pytest
import requests
from google.protobuf.message import DecodeError

from conftest import NOW, FakeStatic, feed, make_clock, trip, url
from subway_clock.core.board import bullet_id
from subway_clock.core.clock import Clock
from subway_clock.core.settings import Settings


def six(trip_id, minutes, stop="633S"):
    return trip(trip_id, "6", [(stop, minutes)])


def shown(clock):
    return [row.number for row in clock.board(now=NOW).rows]


def test_upcoming_trains_sorted():
    clock = make_clock(six("b", 9), six("a", 3))
    rows = clock.board(now=NOW).rows
    assert [r.destination for r in rows] == ["Dest a", "Dest b"]
    assert [r.minutes for r in rows] == [3, 9]


def test_arriving_train_stays_until_the_feed_drops_it():
    clock = make_clock(six("late", -2), six("next", 6))
    first = clock.board(now=NOW).rows[0]
    assert (first.destination, first.minutes, first.arriving) == ("Dest late", 0, True)


def test_long_overdue_train_dropped():
    clock = make_clock(six("stuck", -6), six("next", 6))
    assert [r.destination for r in clock.board(now=NOW).rows] == ["Dest next"]


def test_max_minutes():
    clock = make_clock(six("a", 3), six("b", 29), six("c", 31), max_minutes=30)
    assert [r.destination for r in clock.board(now=NOW).rows] == ["Dest a", "Dest b"]


def test_second_arriving_train_is_fixed_on_bottom_line():
    clock = make_clock(six("a", 0), six("b", 0.5), six("c", 5), six("d", 9))
    assert not clock.rotate(now=NOW)
    assert shown(clock) == [1, 2]


def test_second_line_rotates_through_remaining_trains_and_wraps():
    clock = make_clock(*[six(str(i), i * 2 + 2) for i in range(4)])
    assert shown(clock) == [1, 2]
    states = []
    for _ in range(4):
        assert clock.rotate(now=NOW)
        states.append(shown(clock))
    assert states == [[1, 3], [1, 4], [1, 2], [1, 3]]


def test_refresh_resets_rotation():
    clock = make_clock(*[six(str(i), i * 2 + 2) for i in range(4)])
    clock.rotate(now=NOW)
    clock.refresh(now=NOW)
    assert shown(clock) == [1, 2]


@pytest.mark.parametrize("count", [0, 1, 2])
def test_nothing_to_rotate_with_two_or_fewer_trains(count):
    clock = make_clock(*[six(str(i), i + 2) for i in range(count)])
    assert not clock.rotate(now=NOW)
    assert len(clock.board(now=NOW).rows) == count


def test_max_trains_limits_rotation():
    clock = make_clock(*[six(str(i), i + 2) for i in range(10)], max_trains=3)
    clock.rotate(now=NOW)
    clock.rotate(now=NOW)
    assert shown(clock) == [1, 2]


def test_arriving_under_one_minute():
    clock = make_clock(six("a", 0.5), six("b", 1))
    assert [r.arriving for r in clock.board(now=NOW).rows] == [True, False]


def test_unknown_headsign():
    clock = make_clock(six("a", 3), static=FakeStatic())
    assert clock.board(now=NOW).rows[0].destination == "Unknown"


def test_express_bullets():
    assert bullet_id("6X") == "6d"
    assert bullet_id("6") == "6"
    assert bullet_id("FX") == "Fd"
    assert bullet_id("GS") == "S"


# Stops and feeds


def test_only_requested_direction_shown():
    clock = make_clock(six("down", 3, "633S"), six("up", 4, "633N"), stops=["633S"])
    assert [r.destination for r in clock.board(now=NOW).rows] == ["Dest down"]


def test_parent_stop_shows_both_directions():
    clock = make_clock(six("down", 3, "633S"), six("up", 4, "633N"), stops=["633"])
    assert [r.destination for r in clock.board(now=NOW).rows] == ["Dest down", "Dest up"]


def test_stop_ids_match_exactly_not_by_prefix():
    clock = make_clock(six("other", 3, "634S"), six("mine", 4, "633S"), stops=["633S"])
    assert [r.destination for r in clock.board(now=NOW).rows] == ["Dest mine"]


def test_scheduled_feeds_only():
    # Union Sq: 4/5/6 in the main feed, N/Q/R/W in the NQRW feed, L in the L feed
    static = FakeStatic(stop_routes={"635": ["4", "5", "6"], "R20": ["N", "Q", "R", "W"], "L03": ["L"]},
                        headsigns={"q": "Coney Island", "six": "Brooklyn Bridge"})
    feeds = {
        url("6"): feed(trip("six", "6", [("635S", 2)])),
        url("Q"): feed(trip("q", "Q", [("R20S", 5)])),
        url("L"): feed(),
    }
    clock = make_clock(static=static, feeds=feeds, stops=["635S", "R20S"], fetch_all_feeds=False)
    assert sorted(clock.fetched) == sorted([url("6"), url("Q")])
    assert [r.route for r in clock.board(now=NOW).rows] == ["6", "Q"]


# Destinations and times


def test_destination_is_last_named_stop_of_the_trip():
    # Northbound H trips end at H19, which isn't in stops.txt; Broad Channel is the real destination.
    static = FakeStatic(stop_routes={"H15": ["H"]}, headsigns={"h": "Old headsign"},
                        stop_names={"H15N": "Beach 105 St", "H04N": "Broad Channel"})
    clock = make_clock(trip("h", "H", [("H15N", 2), ("H04N", 9), ("H19N", 12)]), static=static, stops=["H15N"])
    assert clock.board(now=NOW).rows[0].destination == "Broad Channel"


def test_destination_falls_back_to_headsign():
    static = FakeStatic(headsigns={"a": "Brooklyn Bridge-City Hall"})
    clock = make_clock(six("a", 3), static=static)
    assert clock.board(now=NOW).rows[0].destination == "Brooklyn Bridge-City Hall"


def test_departure_only_first_stop_is_shown():
    # Trains starting at a terminal have only a departure time there.
    clock = make_clock(trip("a", "6", [("640N", 4, "departure"), ("639N", 6)]), stops=["640N"],
                       static=FakeStatic(stop_routes={"640": ["6"]}))
    assert [r.minutes for r in clock.board(now=NOW).rows] == [4]


# Settings


def test_settings_defaults_when_file_missing(tmp_path):
    assert Settings.load(tmp_path / "missing.json") == Settings()


def test_settings_round_trip_and_unknown_keys_ignored(tmp_path):
    path = tmp_path / "settings.json"
    Settings(stops=["R20N"], theme="dark").save(path)
    values = json.loads(path.read_text())
    values["future_setting"] = True
    path.write_text(json.dumps(values))
    assert Settings.load(path) == Settings(stops=["R20N"], theme="dark")


def test_settings_single_stop_id_still_loads(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"stop_id": "R20N"}))
    assert Settings.load(path).stops == ["R20N"]


def test_settings_rejects_unknown_theme():
    with pytest.raises(ValueError):
        Settings(theme="neon")


# Network failures


def union_sq_clock(feeds):
    """A clock for Union Sq (6 and Q feeds) whose fetches return or raise from feeds[url]."""
    static = FakeStatic(stop_routes={"635": ["6"], "R20": ["Q"]})
    responses = dict(feeds)

    def fetch(feed_url):
        response = responses.get(feed_url, feed())
        if isinstance(response, Exception):
            raise response
        return response

    clock = Clock(Settings(stops=["635S", "R20S"]), static, fetch_feed=fetch)
    return clock, responses


def test_failed_feed_keeps_its_last_good_data():
    clock, responses = union_sq_clock({url("6"): feed(trip("six", "6", [("635S", 4)])),
                                       url("Q"): feed(trip("q", "Q", [("R20S", 6)]))})
    clock.refresh(now=NOW)
    responses[url("Q")] = requests.ConnectionError("down")
    responses[url("6")] = feed(trip("six2", "6", [("635S", 2)]))
    clock.refresh(now=NOW + 30)
    assert [r.route for r in clock.board(now=NOW + 30).rows] == ["6", "Q"]
    assert clock.predictions[0].trip_id == "six2"


def test_stale_after_three_failed_refreshes():
    clock, responses = union_sq_clock({url("6"): feed(), url("Q"): feed()})
    clock.refresh(now=NOW)
    responses[url("Q")] = requests.Timeout("slow")
    for seconds in (30, 60, 90):
        clock.refresh(now=NOW + seconds)
        assert not clock.board(now=NOW + seconds).stale
    clock.refresh(now=NOW + 120)
    assert clock.board(now=NOW + 120).stale


def test_stale_if_a_feed_never_loaded():
    clock, _ = union_sq_clock({url("6"): feed(), url("Q"): DecodeError("garbage")})
    clock.refresh(now=NOW)
    assert clock.board(now=NOW).stale


def test_static_refresh_failure_still_fetches_live_data():
    clock, _ = union_sq_clock({url("6"): feed(trip("six", "6", [("635S", 4)])), url("Q"): feed()})

    def offline():
        raise requests.ConnectionError("down")

    clock.static.refresh = offline
    clock.refresh(now=NOW)
    assert [r.route for r in clock.board(now=NOW).rows] == ["6"]


def test_all_feeds_show_unscheduled_reroutes():
    # An A train sent along the F line by an incident isn't in any schedule.
    static = FakeStatic(stop_routes={"D20": ["B", "D", "F", "M"]})
    feeds = {url("F"): feed(trip("f", "F", [("D20S", 4)])),
             url("A"): feed(trip("a", "A", [("D20S", 2)]))}
    assert [r.route for r in make_clock(static=static, feeds=feeds, stops=["D20S"]).board(now=NOW).rows] == ["A", "F"]
    scheduled_only = make_clock(static=static, feeds=feeds, stops=["D20S"], fetch_all_feeds=False)
    assert [r.route for r in scheduled_only.board(now=NOW).rows] == ["F"]


def test_unrelated_feed_failure_is_not_stale():
    clock, responses = union_sq_clock({url("SI"): requests.ConnectionError("down")})
    clock.refresh(now=NOW)
    assert not clock.stale(now=NOW)
    responses[url("SI")] = requests.ConnectionError("still down")
    for seconds in (30, 60, 90, 120):
        clock.refresh(now=NOW + seconds)
    assert not clock.stale(now=NOW + 120)
