import pytest

from conftest import NOW, feed
from subway_clock.core.clock import Clock
from subway_clock.core.gtfs import StaticTables
from subway_clock.core.settings import ROTATIONS, STYLES, Settings
from subway_clock.ui.menu import CHOICES, LOADING, NO_MATCH, NO_STOPS, Menu

# (parent stop ID, name, routes, direction labels, complex)
STOPS = [
    ("635", "14 St-Union Sq", ["4", "5", "6", "6X"], {"N": "Uptown & The Bronx", "S": "Downtown & Brooklyn"}, "602"),
    ("L03", "14 St-Union Sq", ["L"], {"N": "8 Av", "S": "Brooklyn"}, "602"),
    ("633", "28 St", ["6", "6X"], {"N": "Uptown & The Bronx", "S": "Downtown & Brooklyn"}, "405"),
    ("A31", "14 St", ["A", "C", "E"], {"N": "Uptown - Queens", "S": "Downtown & Brooklyn"}, "618"),
    ("L01", "8 Av", ["L"], {"S": "Brooklyn"}, "618"),
]
COMPLEXES = {stop: complex_id for stop, *_, complex_id in STOPS}


def make_menu(**settings):
    """A menu, open at its main page, for a clock at 28 St downtown, and the settings it has applied."""
    static = StaticTables(
        stop_names={stop + d: name for stop, name, *_ in STOPS for d in ("", "N", "S")},
        stop_parents={stop + d: stop for stop, *_ in STOPS for d in ("", "N", "S")},
        stop_routes={stop: routes for stop, _, routes, *_ in STOPS},
        headsigns={},
        direction_labels={stop: labels for stop, _, _, labels, _ in STOPS},
        stop_boroughs={stop: "M" for stop, *_ in STOPS})
    clock = Clock(Settings(**{"stops": ["633S"], **settings}), static, fetch_feed=lambda url: feed())
    clock.refresh(now=NOW)
    applied = []

    def apply(new):
        applied.append(new)
        clock.apply_settings(new)

    menu = Menu(clock, apply, COMPLEXES)
    assert menu.key("enter")
    return menu, applied


def press(menu, keys):
    for key in keys.split():
        assert menu.key(" " if key == "space" else key)


def type_in(menu, text):
    for character in text:
        menu.key(character)


def rows(menu, field="label"):
    return [row[field] for row in menu.view()["rows"]]


def test_closed_until_a_key_opens_it():
    menu, _ = make_menu()
    press(menu, "escape")
    assert not menu.view()["open"]
    assert not menu.key("escape") and not menu.key("s") and not menu.key("1") and not menu.key("")
    assert not menu.view()["open"]
    assert menu.key("m")
    assert menu.view()["open"]


def test_every_style_and_rotation_can_be_chosen():
    choices = {setting: names for setting, _, names in CHOICES}
    assert set(choices["style"]) == set(STYLES) and set(choices["rotation"]) == set(ROTATIONS)


def test_main_page_lists_the_settings_as_they_are():
    menu, _ = make_menu(style="new", show_alerts=False)
    view = menu.view()
    assert (view["page"], view["title"], view["index"]) == ("main", "Settings", 0)
    assert list(zip(rows(menu), rows(menu, "value")))[:4] == [
        ("Station", "28 St, Downtown & Brooklyn"), ("Style", "New"), ("Station name", "Off"), ("Service alerts", "Off")]


def test_left_and_right_change_a_setting_at_once():
    menu, applied = make_menu()
    press(menu, "down right")
    assert applied[-1].style == "new" and rows(menu, "value")[1] == "New"
    press(menu, "left left")
    assert applied[-1].style == "led"
    press(menu, "down enter")
    assert applied[-1].show_station is True and applied[-1].style == "led"


def test_up_and_down_wrap():
    menu, _ = make_menu()
    press(menu, "up")
    assert menu.view()["index"] == len(CHOICES)
    press(menu, "down")
    assert menu.view()["index"] == 0


def test_escape_closes_the_menu_without_changing_anything():
    menu, applied = make_menu()
    press(menu, "down escape")
    assert not menu.view()["open"] and not applied
    assert not menu.key("escape")  # which is the window's again, to quit with


def test_station_can_wait_for_the_schedules():
    menu, _ = make_menu()
    menu.clock.static.ready = False
    assert rows(menu, "value")[0] == LOADING
    press(menu, "enter")
    assert menu.view()["page"] == "main"


def test_search_starts_with_the_stations_chosen():
    menu, _ = make_menu(stops=["633S", "L03"])
    press(menu, "enter")
    view = menu.view()
    assert (view["page"], view["query"]) == ("search", "")
    assert [(row["label"], row["detail"], row["value"]) for row in view["rows"]] == [
        ("28 St", "Downtown & Brooklyn", "Manhattan"), ("14 St-Union Sq", "8 Av, Brooklyn", "Manhattan")]


def test_typing_narrows_the_stations():
    menu, _ = make_menu()
    press(menu, "enter")
    type_in(menu, "14 s")
    assert rows(menu) == ["14 St-Union Sq", "14 St / 8 Av"]
    assert menu.view()["rows"][0]["bullets"] == ["4", "5", "6", "L"]  # no diamond beside the 6
    type_in(menu, "q")
    assert rows(menu) == ["14 St-Union Sq"]
    type_in(menu, "x")
    assert rows(menu) == [] and menu.view()["empty"] == NO_MATCH
    press(menu, "backspace backspace backspace backspace")
    assert menu.view()["query"] == "14"


def test_letters_that_open_or_quit_elsewhere_are_typed_in_a_search():
    menu, _ = make_menu()
    press(menu, "enter")
    type_in(menu, "ms1")
    assert menu.view()["query"] == "ms1"


def test_station_page_starts_at_a_ticked_direction():
    menu, _ = make_menu()
    press(menu, "enter enter")
    view = menu.view()
    assert (view["title"], view["index"], rows(menu, "checked")) == ("28 St", 1, [False, True])


def test_station_page_lists_each_platform_direction():
    menu, _ = make_menu()
    press(menu, "enter")
    type_in(menu, "8 av")
    press(menu, "enter")
    view = menu.view()
    assert (view["page"], view["title"]) == ("station", "14 St / 8 Av")
    assert [(row["label"], row["detail"], row["value"], row["bullets"], row["checked"]) for row in view["rows"]] == [
        ("Uptown - Queens", "14 St", "A31N", ["A", "C", "E"], False),
        ("Downtown & Brooklyn", "14 St", "A31S", ["A", "C", "E"], False),
        ("Brooklyn", "8 Av", "L01S", ["L"], False)]


def choose(menu, query, keys):
    """From the main page: find a station, press keys on its page, and go back to the main page."""
    press(menu, "enter")
    type_in(menu, query)
    press(menu, "enter " + keys + " escape escape")


def test_ticked_stops_take_effect_together_on_going_back():
    menu, applied = make_menu()
    press(menu, "enter")
    type_in(menu, "union")
    press(menu, "enter down space down down enter")
    assert not applied
    press(menu, "escape")
    assert menu.view()["page"] == "search" and not applied
    press(menu, "escape")
    assert menu.view()["page"] == "main"
    assert [s.stops for s in applied] == [["633S", "635S", "L03S"]]
    assert rows(menu, "value")[0] == "28 St / 14 St-Union Sq"


def test_unticking_removes_a_stop():
    menu, applied = make_menu(stops=["633S", "635S"])
    press(menu, "enter enter enter escape escape")  # 28 St is listed first: untick its only stop
    assert [s.stops for s in applied] == [["635S"]]


def test_both_directions_are_saved_as_the_parent_stop():
    menu, applied = make_menu()
    choose(menu, "28", "up enter")
    assert applied[-1].stops == ["633"]


def test_a_parent_stop_is_both_directions_ticked():
    menu, applied = make_menu(stops=["633"])
    press(menu, "enter enter")
    assert rows(menu, "checked") == [True, True]
    press(menu, "enter escape escape")
    assert applied[-1].stops == ["633S"]


def test_a_terminal_keeps_its_one_direction():
    menu, applied = make_menu()
    choose(menu, "8 av", "down down enter")
    assert applied[-1].stops == ["633S", "L01S"]


def test_no_stops_ticked_leaves_the_clock_as_it_was():
    menu, applied = make_menu()
    press(menu, "enter enter enter escape")
    assert menu.view()["empty"] == NO_STOPS
    press(menu, "escape")
    assert not applied and menu.clock.settings.stops == ["633S"]


def test_the_same_stops_are_not_applied_again():
    menu, applied = make_menu(stops=["635N", "635S"])
    press(menu, "enter enter enter enter escape escape")  # untick and tick again
    assert not applied


def test_a_stop_the_schedules_lack_is_kept():
    menu, applied = make_menu(stops=["X99S"])
    choose(menu, "28", "down enter")
    assert applied[-1].stops == ["X99S", "633S"]


@pytest.mark.parametrize("keys", ["escape", "left", "backspace"])
def test_going_back_from_a_station_returns_to_it_in_the_list(keys):
    menu, _ = make_menu()
    press(menu, "enter")
    type_in(menu, "14")
    press(menu, "down enter " + keys)
    view = menu.view()
    assert (view["page"], view["query"], view["index"]) == ("search", "14", 1)


# With a mouse


def test_a_click_on_the_clock_opens_the_menu():
    menu, _ = make_menu()
    press(menu, "escape")
    menu.back()  # Nothing to go back from
    menu.scroll(1)
    assert not menu.view()["open"]
    menu.click()
    view = menu.view()
    assert (view["open"], view["page"], view["index"], view["back"]) == (True, "main", 0, "Close")


def test_a_click_on_a_setting_changes_it():
    menu, applied = make_menu()
    menu.click(1)
    assert applied[-1].style == "new" and menu.view()["index"] == 1
    menu.click(2)
    assert applied[-1].show_station is True


def test_clicks_choose_a_station_and_tick_its_directions():
    menu, applied = make_menu()
    menu.click(0)
    assert (menu.view()["page"], menu.view()["back"]) == ("search", "Back")
    type_in(menu, "union")
    menu.click(0)
    assert menu.view()["title"] == "14 St-Union Sq"
    menu.click(1)
    menu.click(3)
    assert rows(menu, "checked") == [False, True, False, True]
    menu.back()
    menu.back()
    assert menu.view()["page"] == "main" and applied[-1].stops == ["633S", "635S", "L03S"]
    menu.back()
    assert not menu.view()["open"]


def test_a_click_past_the_rows_does_nothing():
    menu, applied = make_menu()
    menu.click(len(CHOICES) + 1)
    menu.click(-1)
    assert not applied and menu.view()["index"] == 0


def test_the_wheel_stops_at_the_ends():
    menu, _ = make_menu()
    menu.scroll(-1)
    assert menu.view()["index"] == 0
    menu.scroll(2)
    assert menu.view()["index"] == 2
    menu.scroll(99)
    assert menu.view()["index"] == len(CHOICES)
