"""The web front end's server (web/server.py): what it hands the page, without a browser."""
import importlib.util
import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from conftest import NOW, make_clock, trip
from subway_clock.core.gtfs import StaticTables
from subway_clock.core.settings import Settings
from subway_clock.web.server import Service, library, make_server

ROOT = Path(__file__).resolve().parent.parent


def six(trip_id, minutes):
    return trip(trip_id, "6", [("633S", minutes)])


def make_service(*trips, settings_path=None, **settings):
    """A Service for a clock stopped at NOW, fetching nothing and rotating only when told to."""
    clock = make_clock(*(trips or [six(name, 3 * (i + 1)) for i, name in enumerate("abcde")]), **settings)
    board, rotate = clock.board, clock.rotate
    clock.board = lambda _=None: board(NOW)
    clock.rotate = lambda _=None: rotate(NOW)
    return Service(clock, settings_path=settings_path, live=False)


def numbers(service, lines, grouped=False):
    return [row["number"] for row in service.state(lines, grouped)["board"]["rows"]]


def test_state_is_the_board_and_what_goes_with_it():
    service = make_service(show_station=True)
    state = service.state()
    assert [row["destination"] for row in state["board"]["rows"]] == ["Dest a", "Dest b"]
    assert state["board"]["style"] == "classic"
    assert state["startup"]["state"] == "ready"
    assert state["showStation"] is True
    assert state["menu"]["open"] is False
    json.dumps(state)  # All of it can go to the page


def test_the_board_has_the_lines_asked_for():
    service = make_service()
    assert numbers(service, 2) == [1, 2]
    assert numbers(service, 4) == [1, 2, 3, 4]
    assert numbers(service, 0) == [1]  # At least one line
    assert len(numbers(service, 99)) == 5  # Every train, on the most lines a page has


def test_each_shape_of_page_keeps_its_own_place_in_the_rotation():
    service = make_service()
    assert numbers(service, 2) == [1, 2] and numbers(service, 4) == [1, 2, 3, 4]
    service.rotate()
    assert numbers(service, 2) == [1, 3] and numbers(service, 4) == [1, 2, 3, 5]
    service.rotate()
    assert numbers(service, 2) == [1, 4] and numbers(service, 4) == [1, 2, 3, 4]
    # A page of another shape starts at the start, and disturbs neither.
    assert numbers(service, 3) == [1, 2, 3]
    assert numbers(service, 2) == [1, 4] and numbers(service, 4) == [1, 2, 3, 4]


def test_new_settings_restart_the_rotations():
    service = make_service()
    numbers(service, 2)
    service.rotate()
    service.apply_settings(Settings(style="new"))
    state = service.state(2)
    assert state["board"]["style"] == "new" and [row["number"] for row in state["board"]["rows"]] == [1, 2]


def test_keys_and_clicks_go_to_the_menu():
    service = make_service()
    assert service.act({"click": None})
    assert service.state()["menu"]["open"]
    assert service.act({"key": "down"}) and service.act({"key": "right"})
    assert service.clock.settings.style == "new"
    assert service.act({"click": 2})
    assert service.clock.settings.show_station is True
    assert service.act({"scroll": 1})
    assert service.state()["menu"]["index"] == 3
    assert service.act({"back": True})
    assert not service.state()["menu"]["open"]
    for unknown in ({}, {"key": 3}, {"click": "1"}, {"scroll": "down"}, {"back": 1}):
        assert not service.act(unknown)


def test_the_menu_saves_to_the_settings_file(tmp_path):
    path = tmp_path / "settings.json"
    service = make_service(settings_path=path)
    for key in ("enter", "down", "right"):
        service.act({"key": key})
    assert Settings.load(path).style == "new"
    service.reload_settings()  # Its own change, read back, changes nothing
    assert service.clock.settings.style == "new"


def test_the_settings_file_is_read_again_when_it_changes(tmp_path):
    path = tmp_path / "settings.json"
    service = make_service(settings_path=path)
    Settings(style="led", stops=["633N"]).save(path)
    service.reload_settings()
    assert (service.clock.settings.style, service.clock.settings.stops) == ("led", ["633N"])
    path.write_text("{", encoding="utf-8")
    service.reload_settings()  # It can't be read, so the settings stay as they were
    assert service.clock.settings.style == "led"


def test_startup_until_the_first_trains():
    service = make_service()
    service.show_progress("Loading schedules", 0.42)
    assert service.state()["startup"] == {
        "state": "loading", "title": "Loading schedules", "detail": "This can take a minute", "progress": 0.42}
    service.apply_predictions(None)  # The first fetch is back, even if it failed
    assert service.state()["startup"]["state"] == "ready"


def test_library_is_a_script_holding_what_the_qml_library_defines():
    script = library("LedFont")
    assert script.startswith("const LedFont = (function () {")
    assert ".pragma" not in script
    exported = script.rsplit("return {", 1)[1]
    for name in ("height", "width", "runs", "bulletRuns", "fit", "shortened"):
        assert f" {name}," in exported or f" {name} }}" in exported


@pytest.fixture
def served():
    """A function fetching a path from a running server, as (status, content type, body)."""
    server = make_server(make_service(), port=0)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    def fetch(path, data=None, content_type="application/json"):
        request = urllib.request.Request(f"http://127.0.0.1:{server.server_address[1]}{path}", data=data,
                                         headers={"Content-Type": content_type} if data is not None else {})
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status, response.headers["Content-Type"], response.read()
        except urllib.error.HTTPError as e:
            return e.code, e.headers["Content-Type"], b""

    yield fetch
    server.shutdown()
    server.server_close()


def test_serves_the_page_and_what_it_draws_with(served):
    status, content_type, body = served("/")
    assert status == 200 and content_type.startswith("text/html") and b'src="main.js"' in body
    for path, expected in (("/main.js", "text/javascript"), ("/clock.css", "text/css"),
                           ("/qml/Styles.js", "text/javascript"), ("/assets/fonts/Roboto.ttf", "font/ttf"),
                           ("/assets/bullets/NYCS-bull-trans-6d.svg", "image/svg+xml"),
                           ("/assets/led-dot.svg", "image/svg+xml")):
        status, content_type, body = served(path)
        assert (status, content_type.split(";")[0]) == (200, expected) and body, path


@pytest.mark.parametrize("path", [
    "/nothing.js", "/server.py", "/../server.py", "/assets/../web/server.py", "/assets/..%2F..%2FREADME.md",
    "/qml/Main.js", "/qml/Main.qml", "/api/state?lines=two",
])
def test_serves_nothing_else(served, path):
    assert served(path)[0] in (400, 404)


def test_serves_the_state_for_the_lines_asked_for(served):
    status, content_type, body = served("/api/state?lines=3&grouped=0")
    assert status == 200 and content_type == "application/json"
    assert [row["number"] for row in json.loads(body)["board"]["rows"]] == [1, 2, 3]


def test_the_menu_is_posted_to_as_json_and_answers_with_the_state(served):
    status, _, body = served("/api/menu?lines=2", json.dumps({"key": "enter"}).encode())
    assert status == 200 and json.loads(body)["menu"]["open"] is True
    # A form on another site's page can post text, but not JSON without asking first.
    assert served("/api/menu", json.dumps({"key": "escape"}).encode(), "text/plain")[0] == 404
    assert served("/api/menu", b"{}")[0] == 400
    assert served("/api/menu", b"not json")[0] == 400
    assert json.loads(served("/api/state")[2])["menu"]["open"] is True


def test_build_site_makes_the_standalone_page_as_plain_files(tmp_path):
    spec = importlib.util.spec_from_file_location("build_site", ROOT / "scripts" / "build_site.py")
    build_site = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build_site)

    site = tmp_path / "site"
    build_site.build(site, proxy="https://proxy.example/?url=")
    assert b'src="standalone.js"' in (site / "index.html").read_bytes()
    assert not (site / "main.js").exists() and not (site / "standalone.html").exists()
    for path in ("page.js", "core/clock.js", "core/feeds.json", "qml/Styles.js", "assets/stations.json",
                 "assets/fonts/Roboto.ttf", "assets/bullets/NYCS-bull-trans-6d.svg"):
        assert (site / path).is_file(), path
    assert ".pragma" not in (site / "qml" / "LedFont.js").read_text(encoding="utf-8")
    assert json.loads((site / "config.json").read_text(encoding="utf-8")) == {"proxy": "https://proxy.example/?url="}
    assert not (site / "schedules.json").exists()

    tables = StaticTables({"635": "14 St-Union Sq", "635S": "14 St-Union Sq"}, {"635": "635", "635S": "635"},
                          {"635": ["4", "5", "6"]}, {"000600_6..S03R": "Brooklyn Bridge-City Hall"})
    build_site.build(site, tables=tables)
    published = json.loads((site / "schedules.json").read_text(encoding="utf-8"))
    assert published.pop("built")
    assert published == {"stop_names": tables.stop_names, "stop_parents": tables.stop_parents,
                         "stop_routes": tables.stop_routes, "headsigns": tables.headsigns}
    assert json.loads((site / "config.json").read_text(encoding="utf-8")) == {"schedules": "schedules.json"}


def test_serves_the_standalone_page_and_its_proxy_config(served):
    status, _, body = served("/standalone.html")
    assert status == 200 and b'src="standalone.js"' in body
    assert json.loads(served("/config.json")[2]) == {"proxy": "proxy?url="}
    status, content_type, body = served("/core/feeds.json")
    assert status == 200 and "alerts" in json.loads(body)
    assert served("/core/clock.js")[0] == 200
    # It passes on the schedules and nothing else.
    assert served("/proxy?url=https%3A%2F%2Fexample.com%2F")[0] == 404
