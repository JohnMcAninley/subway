import json

import pytest

from conftest import NOW, FakeStatic, feed, make_clock, trip, url
from subway_clock.core.board import bullet_id
from subway_clock.core.settings import Settings


def six(trip_id, minutes, stop="633S"):
    return trip(trip_id, "6", [(stop, minutes)])


def shown(clock):
    return [row.number for row in clock.board(now=NOW).rows]


def test_upcoming_trains_sorted_and_past_trains_dropped():
    clock = make_clock(six("b", 9), six("past", -2), six("a", 3))
    rows = clock.board(now=NOW).rows
    assert [r.destination for r in rows] == ["Dest a", "Dest b"]
    assert [r.minutes for r in rows] == [3, 9]


def test_second_line_rotates_through_remaining_trains_and_wraps():
    clock = make_clock(*[six(str(i), i * 2 + 2) for i in range(4)])
    assert shown(clock) == [1, 2]
    states = []
    for _ in range(4):
        assert clock.rotate()
        states.append(shown(clock))
    assert states == [[1, 3], [1, 4], [1, 2], [1, 3]]


def test_refresh_resets_rotation():
    clock = make_clock(*[six(str(i), i * 2 + 2) for i in range(4)])
    clock.rotate()
    clock.refresh(now=NOW)
    assert shown(clock) == [1, 2]


@pytest.mark.parametrize("count", [0, 1, 2])
def test_nothing_to_rotate_with_two_or_fewer_trains(count):
    clock = make_clock(*[six(str(i), i + 2) for i in range(count)])
    assert not clock.rotate()
    assert len(clock.board(now=NOW).rows) == count


def test_max_trains_limits_rotation():
    clock = make_clock(*[six(str(i), i + 2) for i in range(10)], max_trains=3)
    clock.rotate()
    clock.rotate()
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


def test_fetches_every_feed_serving_the_stop():
    # Union Sq: 4/5/6 in the main feed, N/Q/R/W in the NQRW feed, L in the L feed
    static = FakeStatic(stop_routes={"635": ["4", "5", "6"], "R20": ["N", "Q", "R", "W"], "L03": ["L"]},
                        headsigns={"q": "Coney Island", "six": "Brooklyn Bridge"})
    feeds = {
        url("6"): feed(trip("six", "6", [("635S", 2)])),
        url("Q"): feed(trip("q", "Q", [("R20S", 5)])),
        url("L"): feed(),
    }
    clock = make_clock(static=static, feeds=feeds, stops=["635S", "R20S"])
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
