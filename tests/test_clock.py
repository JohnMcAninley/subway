import json

import pytest

from subway_clock.core.board import bullet_id
from subway_clock.core.clock import Clock
from subway_clock.core.settings import Settings

NOW = 1_000_000.0


class FakeStatic:
    def __init__(self, headsigns):
        self.headsigns = headsigns

    def refresh(self):
        pass


def prediction(trip_id, minutes, route_id="6"):
    return {'trip_id': trip_id, 'route_id': route_id, 'stop_id': "633S", 'arrival_time': NOW + minutes * 60}


def make_clock(predictions, **settings):
    static = FakeStatic({p['trip_id']: f"Dest {p['trip_id']}" for p in predictions})
    clock = Clock(Settings(**settings), static, fetch=lambda stop: predictions)
    clock.refresh(now=NOW)
    return clock


def shown(clock):
    return [row.number for row in clock.board(now=NOW).rows]


def test_upcoming_trains_sorted_and_past_trains_dropped():
    clock = make_clock([prediction("b", 9), prediction("past", -2), prediction("a", 3)])
    rows = clock.board(now=NOW).rows
    assert [r.destination for r in rows] == ["Dest a", "Dest b"]
    assert [r.minutes for r in rows] == [3, 9]


def test_second_line_rotates_through_remaining_trains_and_wraps():
    clock = make_clock([prediction(str(i), i * 2 + 2) for i in range(4)])
    assert shown(clock) == [1, 2]
    states = []
    for _ in range(4):
        assert clock.rotate()
        states.append(shown(clock))
    assert states == [[1, 3], [1, 4], [1, 2], [1, 3]]


def test_refresh_resets_rotation():
    clock = make_clock([prediction(str(i), i * 2 + 2) for i in range(4)])
    clock.rotate()
    clock.refresh(now=NOW)
    assert shown(clock) == [1, 2]


@pytest.mark.parametrize("count", [0, 1, 2])
def test_nothing_to_rotate_with_two_or_fewer_trains(count):
    clock = make_clock([prediction(str(i), i + 2) for i in range(count)])
    assert not clock.rotate()
    assert len(clock.board(now=NOW).rows) == count


def test_max_trains_limits_rotation():
    clock = make_clock([prediction(str(i), i + 2) for i in range(10)], max_trains=3)
    clock.rotate()
    clock.rotate()
    assert shown(clock) == [1, 2]


def test_arriving_under_one_minute():
    clock = make_clock([prediction("a", 0.5), prediction("b", 1)])
    assert [r.arriving for r in clock.board(now=NOW).rows] == [True, False]


def test_unknown_headsign():
    clock = make_clock([prediction("a", 3)])
    clock.static.headsigns.clear()
    assert clock.board(now=NOW).rows[0].destination == "Unknown"


def test_express_bullets():
    assert bullet_id("6X") == "6d"
    assert bullet_id("6") == "6"


def test_settings_defaults_when_file_missing(tmp_path):
    assert Settings.load(tmp_path / "missing.json") == Settings()


def test_settings_round_trip_and_unknown_keys_ignored(tmp_path):
    path = tmp_path / "settings.json"
    Settings(stop_id="R20N", theme="dark").save(path)
    values = json.loads(path.read_text())
    values["future_setting"] = True
    path.write_text(json.dumps(values))
    assert Settings.load(path) == Settings(stop_id="R20N", theme="dark")


def test_settings_rejects_unknown_theme():
    with pytest.raises(ValueError):
        Settings(theme="neon")
