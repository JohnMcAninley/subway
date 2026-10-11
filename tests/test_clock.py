import json

import pytest
import requests
from google.protobuf.message import DecodeError

from conftest import NOW, FakeStatic, alert, alerts_feed, feed, make_clock, trip, url
from subway_clock.core.board import bullet_id
from subway_clock.core.clock import Clock
from subway_clock.core.feeds import ALERTS_URL
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


# More lines, for taller screens


def test_last_line_rotates_and_the_others_are_fixed():
    clock = make_clock(*[six(str(i), i * 2 + 2) for i in range(6)])
    clock.lines = 4
    states = [shown(clock)]
    for _ in range(3):
        assert clock.rotate(now=NOW)
        states.append(shown(clock))
    assert states == [[1, 2, 3, 4], [1, 2, 3, 5], [1, 2, 3, 4], [1, 2, 3, 5]]


def test_arriving_train_is_fixed_on_the_last_line():
    clock = make_clock(six("a", 0), six("b", 0.2), six("c", 0.5), six("d", 5), six("e", 9))
    clock.lines = 3
    assert not clock.rotate(now=NOW)
    assert shown(clock) == [1, 2, 3]


def test_lines_beyond_max_trains_show_more_trains():
    clock = make_clock(*[six(str(i), i + 2) for i in range(10)], max_trains=3)
    clock.lines = 6
    assert not clock.rotate(now=NOW)
    assert shown(clock) == [1, 2, 3, 4, 5, 6]


def test_changing_lines_restarts_rotation():
    clock = make_clock(*[six(str(i), i * 2 + 2) for i in range(5)])
    clock.rotate(now=NOW)
    clock.lines = 3
    assert shown(clock) == [1, 2, 3]


def test_one_line_shows_only_the_next_train():
    clock = make_clock(six("a", 2), six("b", 4), six("c", 6))
    clock.lines = 1
    assert not clock.rotate(now=NOW)
    assert shown(clock) == [1]


def test_direction_labels():
    static = FakeStatic(headsigns={"down": "Dest down", "up": "Dest up"},
                        direction_labels={"633": {"N": "Uptown", "S": "Downtown"}})
    clock = make_clock(six("down", 3, "633S"), six("up", 4, "633N"), stops=["633"], static=static)
    assert [r.direction for r in clock.board(now=NOW).rows] == ["Downtown", "Uptown"]


def test_missing_direction_label_is_empty():
    clock = make_clock(six("a", 3))
    assert clock.board(now=NOW).rows[0].direction == ""


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
    clock = make_clock(static=static, feeds=feeds, stops=["635S", "R20S"], fetch_all_feeds=False, show_alerts=False)
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


# Headlines, as on the newer clocks


def headline_of(route, here, stops, label="", boroughs=None):
    """(headline, detail) for a train at stop `here` with the stops it has left, ending at its terminal."""
    names = {stop: f"{stop} name" for stop in stops}
    static = FakeStatic(stop_routes={stop[:-1]: [route] for stop in [here] + stops}, stop_names=names,
                        direction_labels={here[:-1]: {here[-1]: label}} if label else None, stop_boroughs=boroughs)
    clock = make_clock(trip("t", route, [(here, 3)] + [(stop, 5 + i) for i, stop in enumerate(stops)]),
                       static=static, stops=[here])
    row = clock.board(now=NOW).rows[0]
    return row.headline, row.detail


BOROUGHS = {"M1": "M", "M2": "M", "B1": "Bk", "B2": "Bk", "Q1": "Q", "Q2": "Q", "X1": "Bx"}


def test_headline_within_manhattan_is_the_direction():
    assert headline_of("W", "M1S", ["M2S"], "Downtown & Brooklyn", BOROUGHS) == ("Downtown", "M2S name")


def test_headline_leaving_manhattan_adds_the_next_borough():
    assert headline_of("A", "M1S", ["M2S", "B1S", "Q1S"], "Downtown & Brooklyn", BOROUGHS) == (
        "Downtown & Brooklyn", "Q1S name")
    assert headline_of("4", "M1N", ["X1N"], "Uptown & The Bronx", BOROUGHS) == ("Uptown & The Bronx", "X1N name")


def test_headline_heading_into_manhattan():
    assert headline_of("W", "Q1S", ["Q2S", "M1S"], "Manhattan", BOROUGHS) == ("Manhattan", "M1S name")
    assert headline_of("N", "Q1S", ["M1S", "B1S"], "Manhattan", BOROUGHS) == ("Manhattan & Brooklyn", "B1S name")


def test_headline_elsewhere_is_the_terminal_over_its_borough():
    assert headline_of("C", "B1S", ["B2S"], "Euclid - Lefferts", BOROUGHS) == ("B2S name", "Brooklyn")
    assert headline_of("A", "B1S", ["B2S", "Q1S"], "Euclid - Lefferts", BOROUGHS) == ("Q1S name", "Queens")
    assert headline_of("L", "M1S", ["B1S"], "Brooklyn", BOROUGHS) == ("B1S name", "Brooklyn")


def test_headline_without_boroughs_is_the_platform_label():
    assert headline_of("6", "M1S", ["M2S"], "Downtown") == ("Downtown", "M2S name")
    assert headline_of("6", "M1S", ["M2S"]) == ("M2S name", "")


def test_headline_at_the_last_stop_is_the_platform_label():
    assert headline_of("6", "M1S", [], "Downtown", BOROUGHS) == ("Downtown", "Unknown")


# The newer clocks stop rotating once every route has been shown


def test_new_style_stops_after_the_last_new_route():
    routes = ["W", "N", "R", "W", "R"]
    clock = make_clock(*[trip(str(i), r, [("R20S", i * 3 + 3)]) for i, r in enumerate(routes)],
                       static=FakeStatic(stop_routes={"R20": ["N", "R", "W"]}), stops=["R20S"], style="new")
    states = [shown(clock)]
    for _ in range(3):
        clock.rotate(now=NOW)
        states.append(shown(clock))
    assert states == [[1, 2], [1, 3], [1, 2], [1, 3]]


def test_new_style_with_one_route_still_fills_the_lines():
    clock = make_clock(*[six(str(i), i * 3 + 3) for i in range(5)], style="new")
    assert not clock.rotate(now=NOW)
    assert shown(clock) == [1, 2]


def test_classic_style_rotates_through_max_trains_whatever_the_routes():
    clock = make_clock(*[six(str(i), i * 3 + 3) for i in range(5)])
    states = []
    for _ in range(4):
        clock.rotate(now=NOW)
        states.append(shown(clock))
    assert states == [[1, 3], [1, 4], [1, 5], [1, 2]]


# Grouped boards, for screens with room for a list


def both_ways(*minutes_and_stops, **settings):
    static = FakeStatic(direction_labels={"633": {"N": "Uptown", "S": "Downtown"}})
    trips = [six(f"{stop}{minutes}", minutes, stop) for minutes, stop in minutes_and_stops]
    clock = make_clock(*trips, static=static, stops=["633"], **settings)
    clock.grouped = True
    return clock


def test_grouped_board_splits_the_lines_between_directions():
    clock = both_ways((1, "633S"), (2, "633S"), (3, "633N"), (4, "633S"), (5, "633N"), (6, "633N"), max_trains=2)
    clock.lines = 4
    board = clock.board(now=NOW)
    assert [(g.heading, [(r.number, r.minutes) for r in g.rows]) for g in board.groups] == [
        ("Downtown", [(1, 1), (2, 2)]), ("Uptown", [(1, 3), (2, 5)])]
    assert board.rows == board.groups[0].rows + board.groups[1].rows
    assert not clock.rotate(now=NOW)


def test_grouped_board_gives_spare_lines_to_the_first_direction():
    clock = both_ways((1, "633N"), (2, "633S"), (3, "633N"), (4, "633S"), (5, "633N"), (6, "633S"))
    clock.lines = 5
    assert [(g.heading, len(g.rows)) for g in clock.board(now=NOW).groups] == [("Uptown", 3), ("Downtown", 2)]


def test_grouped_board_with_one_direction_is_a_plain_list():
    clock = both_ways((1, "633S"), (2, "633S"), (3, "633S"), (4, "633S"), max_trains=2)
    clock.lines = 3
    board = clock.board(now=NOW)
    assert board.groups == ()
    assert [r.number for r in board.rows] == [1, 2, 3]


def test_grouped_board_never_replaces_a_line_with_an_alert():
    clock = alert_clock(alert("a", "[6] delays", ("6", "", None)), trips=[six("a", 2), six("b", 4)], style="new")
    clock.grouped = True
    board = clock.board(now=NOW)
    assert (len(board.rows), board.message, texts(board.messages)) == (2, "", ("[6] delays",))
    assert not clock.rotate(now=NOW)


# Alerts


def alert_clock(*alerts, trips=(), **settings):
    settings.setdefault("stops", ["633S"])
    return make_clock(*trips, feeds={ALERTS_URL: alerts_feed(*alerts), url("6"): feed(*trips)}, **settings)


def texts(messages):
    return tuple(m.text for m in messages)


def test_alert_for_a_route_at_the_stop():
    clock = alert_clock(alert("a", "[6] delays", ("6", "", None)), alert("b", "[A] delays", ("A", "", None)))
    assert texts(clock.board(now=NOW).messages) == ("[6] delays",)


def test_alert_for_a_stop_only_in_the_direction_shown():
    alerts = [alert("a", "Uptown [6] skips 28 St", ("6", "633", 0)),
              alert("b", "Downtown [6] skips 28 St", ("6", "633", 1)),
              alert("c", "[6] skips 23 St", ("6", "634", None))]
    assert texts(alert_clock(*alerts).messages(NOW)) == ("Downtown [6] skips 28 St",)
    assert texts(alert_clock(*alerts, stops=["633"]).messages(NOW)) == ("Uptown [6] skips 28 St", "Downtown [6] skips 28 St")


def test_alert_only_while_active():
    clock = alert_clock(alert("a", "Later", ("6", "", None), periods=[(NOW + 600, NOW + 1200)]),
                        alert("b", "Open ended", ("6", "", None), periods=[(NOW - 60, 0)]))
    assert texts(clock.messages(NOW)) == ("Open ended",)
    assert texts(clock.messages(NOW + 900)) == ("Later", "Open ended")
    assert texts(clock.messages(NOW + 1200)) == ("Open ended",)


def test_alerts_happening_now_come_before_planned_work_and_repeats_are_dropped():
    clock = alert_clock(alert("lmm:planned_work:1", "Planned", ("6", "", None)),
                        alert("lmm:alert:2:26", "Delays", ("6", "", None)),
                        alert("lmm:alert:2:29", "Delays", ("6X", "", None)))
    assert [(m.text, m.planned) for m in clock.messages(NOW)] == [("Delays", False), ("Planned", True)]


def test_alert_for_a_rerouted_train_on_the_board():
    clock = alert_clock(alert("a", "[2] runs local", ("2", "", None)), trips=[trip("two", "2", [("633S", 4)])])
    assert texts(clock.messages(NOW)) == ("[2] runs local",)


def test_show_alerts_off():
    clock = alert_clock(alert("a", "[6] delays", ("6", "", None)), show_alerts=False)
    assert ALERTS_URL not in clock.fetched
    assert texts(clock.board(now=NOW).messages) == ()


def test_alerts_fetched_every_two_minutes_and_kept_if_fetching_fails():
    clock = alert_clock(alert("a", "[6] delays", ("6", "", None)))
    clock.refresh(now=NOW + 60)
    assert clock.fetched.count(ALERTS_URL) == 1
    clock.fetch_feed = fail_alerts(clock.fetch_feed)
    clock.refresh(now=NOW + 120)
    assert texts(clock.messages(NOW + 120)) == ("[6] delays",)
    assert not clock.stale(NOW + 120)


def fail_alerts(fetch):
    def fetch_feed(feed_url):
        if feed_url == ALERTS_URL:
            raise requests.ConnectionError("down")
        return fetch(feed_url)
    return fetch_feed


def test_new_style_shows_alerts_in_place_of_the_last_line():
    trips = [six("a", 2), six("b", 4), trip("c", "6X", [("633S", 6)])]
    clock = alert_clock(alert("a", "[6] delays", ("6", "", None)), trips=trips, style="new")
    states = []
    for _ in range(5):
        board = clock.board(now=NOW)
        states.append(([r.number for r in board.rows], board.message))
        assert clock.rotate(now=NOW)
    assert states == [([1, 2], ""), ([1, 3], ""), ([1], "[6] delays"), ([1], "[6] delays"), ([1, 2], "")]


def test_new_style_keeps_an_arriving_train_on_the_last_line():
    trips = [six("a", 0), six("b", 0.5), six("c", 5)]
    clock = alert_clock(alert("a", "[6] delays", ("6", "", None)), trips=trips, style="new")
    assert not clock.rotate(now=NOW)
    assert clock.board(now=NOW).message == ""


def test_classic_style_never_replaces_the_last_line():
    trips = [six(str(i), i * 2 + 2) for i in range(2)]
    clock = alert_clock(alert("a", "[6] delays", ("6", "", None)), trips=trips)
    assert not clock.rotate(now=NOW)
    board = clock.board(now=NOW)
    assert (len(board.rows), board.message, texts(board.messages)) == (2, "", ("[6] delays",))


# Settings


def test_settings_defaults_when_file_missing(tmp_path):
    assert Settings.load(tmp_path / "missing.json") == Settings()


def test_settings_round_trip_and_unknown_keys_ignored(tmp_path):
    path = tmp_path / "settings.json"
    Settings(stops=["R20N"], style="new").save(path)
    values = json.loads(path.read_text())
    values["future_setting"] = True
    path.write_text(json.dumps(values))
    assert Settings.load(path) == Settings(stops=["R20N"], style="new")


def test_settings_single_stop_id_still_loads(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"stop_id": "R20N"}))
    assert Settings.load(path).stops == ["R20N"]


@pytest.mark.parametrize("theme, style", [("light", "classic"), ("dark", "new")])
def test_settings_old_themes_load_as_styles(tmp_path, theme, style):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"theme": theme}))
    assert Settings.load(path).style == style


def test_settings_rejects_unknown_style():
    with pytest.raises(ValueError):
        Settings(style="neon")


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
