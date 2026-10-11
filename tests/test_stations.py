import pytest

from subway_clock.core.gtfs import StaticTables
from subway_clock.core.stations import Direction, StationPicker, load_complexes

# (parent stop ID, name, routes, direction labels, borough, complex)
STOPS = [
    ("635", "14 St-Union Sq", ["4", "5", "6", "6X"], {"N": "Uptown & The Bronx", "S": "Downtown & Brooklyn"}, "M", "602"),
    ("L03", "14 St-Union Sq", ["L"], {"N": "8 Av", "S": "Brooklyn"}, "M", "602"),
    ("A31", "14 St", ["A", "C", "E"], {"N": "Uptown - Queens", "S": "Downtown & Brooklyn"}, "M", "618"),
    ("L01", "8 Av", ["L"], {"S": "Brooklyn"}, "M", "618"),
    ("R32", "Union St", ["R"], {"N": "Manhattan", "S": "Bay Ridge - 95 St"}, "Bk", "27"),
    ("A12", "145 St", ["A", "C"], {"N": "Uptown & The Bronx", "S": "Downtown & Brooklyn"}, "M", "151"),
    ("A32", "W 4 St-Wash Sq", ["A", "C", "E"], {"N": "Uptown - Queens", "S": "Downtown & Brooklyn"}, "M", "167"),
    ("228", "Park Place", ["2", "3"], {"N": "Uptown & The Bronx", "S": "Downtown & Brooklyn"}, "M", "624"),
    ("F35", "Avenue U", ["F"], {"N": "Manhattan", "S": "Coney Island"}, "Bk", "247"),
    ("Q04", "86 St", ["Q"], {"N": "Uptown", "S": "Downtown & Brooklyn"}, "M", "476"),
    ("626", "86 St", ["4", "5", "6", "6X"], {"N": "Uptown & The Bronx", "S": "Downtown & Brooklyn"}, "M", "397"),
    ("S31", "St George", ["SI"], {"S": "Tottenville"}, "SI", "501"),
]


@pytest.fixture(scope="module")
def picker():
    static = StaticTables(
        stop_names={stop + d: name for stop, name, *_ in STOPS for d in ("", "N", "S")},
        stop_parents={stop + d: stop for stop, *_ in STOPS for d in ("", "N", "S")},
        stop_routes={stop: routes for stop, _, routes, *_ in STOPS},
        headsigns={},
        direction_labels={stop: labels for stop, _, _, labels, *_ in STOPS},
        stop_boroughs={stop: borough for stop, *_, borough, _ in STOPS})
    return StationPicker(static, {stop: complex_id for stop, *_, complex_id in STOPS})


def names(stations):
    return [station.name for station in stations]


def test_a_station_is_its_whole_complex(picker):
    [station] = picker.search("union sq")
    assert (station.name, station.borough) == ("14 St-Union Sq", "M")
    assert [(stop.stop_id, stop.routes) for stop in station.stops] == [("635", ("4", "5", "6", "6X")), ("L03", ("L",))]
    assert station.stops[0].directions == (Direction("635N", "Uptown & The Bronx"),
                                           Direction("635S", "Downtown & Brooklyn"))
    assert station.routes == ("4", "5", "6", "6X", "L")


def test_a_complex_is_named_for_each_of_its_stops(picker):
    assert names(picker.search("8 av")) == ["14 St / 8 Av"]


def test_only_the_directions_trains_leave_in(picker):
    [station] = picker.search("st george")
    assert station.stops[0].directions == (Direction("S31S", "Tottenville"),)


def test_words_match_by_their_start_in_any_order(picker):
    assert names(picker.search("squ uni")) == ["14 St-Union Sq"]
    assert names(picker.search("unoin")) == []  # no spelling correction


def test_whole_words_first_then_busier_stations(picker):
    assert names(picker.search("14")) == ["14 St-Union Sq", "14 St / 8 Av", "145 St"]
    assert names(picker.search("union")) == ["14 St-Union Sq", "Union St"]


def test_abbreviations_and_ordinals(picker):
    assert names(picker.search("West 4th Street")) == ["W 4 St-Wash Sq"]
    assert names(picker.search("washington square")) == ["W 4 St-Wash Sq"]
    assert names(picker.search("park pl")) == ["Park Place"]
    assert names(picker.search("av u")) == ["Avenue U"]
    assert names(picker.search("saint george")) == ["St George"]


def test_a_route_narrows_the_search(picker):
    assert names(picker.search("86")) == ["86 St", "86 St"]
    assert [station.stops[0].stop_id for station in picker.search("86 q")] == ["Q04"]
    assert [station.stops[0].stop_id for station in picker.search("86 6")] == ["626"]


def test_empty_query_lists_every_station_by_name(picker):
    assert names(picker.search("")) == [
        "14 St / 8 Av", "14 St-Union Sq", "86 St", "86 St", "145 St", "Avenue U", "Park Place", "St George",
        "Union St", "W 4 St-Wash Sq"]
    assert len(picker.search("", limit=3)) == 3


def test_station_for_a_stop_id(picker):
    assert picker.station_for("L03S").name == "14 St-Union Sq"
    assert picker.station_for("L01").name == "14 St / 8 Av"
    assert picker.station_for("999S") is None


def test_stops_missing_from_the_station_list_stand_alone_with_both_directions():
    static = StaticTables({"X01": "New St"}, {"X01": "X01", "X01N": "X01", "X01S": "X01"}, {}, {})
    [station] = StationPicker(static).search("new")
    assert (station.borough, station.stops[0].routes) == ("", ())
    assert station.stops[0].directions == (Direction("X01N", ""), Direction("X01S", ""))


def test_bundled_complexes():
    complexes = load_complexes()
    assert complexes["635"] == complexes["L03"] == complexes["R20"]  # Union Sq
    assert complexes["R11"] != complexes["B08"]  # Lexington Av/59 St and /63 St: a walk along the street
