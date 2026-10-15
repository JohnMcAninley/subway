"""The JavaScript core (web/static/core) against the Python one, in a browser without a window.

tests/web/harness.js runs it on every golden case, and on scripts of keys for
the settings menu and queries for the station search; the Python core does
the same here, and the answers must match. Skipped if no Chrome, Chromium or
Edge is found (see web/browser.py).
"""
import dataclasses
import importlib.util
import json
import subprocess
import tempfile
import threading
from email.utils import formatdate
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from golden_harness import case_dirs, run_case
from subway_clock.core.clock import Clock
from subway_clock.core.gtfs import SUBWAY_URL, SUPPLEMENTED_URL, StaticData, StaticTables
from subway_clock.core.settings import Settings
from subway_clock.core.stations import StationPicker
from subway_clock.ui.menu import Menu
from subway_clock.web.browser import find_browser
from subway_clock.web.server import Handler, make_server

TESTS_DIR = Path(__file__).resolve().parent
ROOT = TESTS_DIR.parent
GOLDEN_DIR = TESTS_DIR / "golden"

# Scripts of keys for the menu: about every way through its three pages, ending with new settings.
MENUS = [
    {"case": "union-sq-south", "settings": {"stops": ["635S", "R20S", "L03S"]},
     "keys": ["enter", "down", "right", "right", "down", "enter", "down", "left", "down", "down", "up", "enter",
              "down", "space", "up", "up", "up", "up", "up", "up", "right", "backspace", "1", "4", " ", "s", "t",
              "down", "enter", "down", "enter", "up", "enter", "escape", "backspace", "backspace", "backspace",
              "backspace", "backspace", "u", "n", "i", "o", "n", "enter", "enter", "down", "enter", "left", "up",
              "escape", "escape", "m"]},
    {"case": "jackson-hts", "settings": {"stops": ["G14", "710"], "style": "new"},
     "keys": ["m", "enter", "7", "enter", "enter", "down", "enter", "escape", "x", "y", "z", "escape", "down",
              "down", "down", "down", "down", "down", "left", "left", "escape"]},
    {"case": "broad-channel", "settings": {"stops": ["H04"]},
     "keys": ["enter", "enter", "enter", "enter", "escape", "b", "r", "o", "a", "d", "enter", "enter", "enter",
              "escape", "escape", "escape", "enter"]},
]

SEARCHES = ["", "14", "union", "14 st", "fourteenth", "86 q", "6", "7", "a", "e", "jackson hts", "roosevelt",
            "west 4th street", "sq", "broad", "Av", "zzz", "h", "1 4", "st'", "times square"]


def menu_run(script):
    """What harness.js's runMenu gives, from the Python menu."""
    case_dir = GOLDEN_DIR / script["case"]
    static = StaticTables(**json.loads((case_dir / "static.json").read_text(encoding="utf-8")))
    clock = Clock(Settings(**script["settings"]), static)
    menu = Menu(clock, clock.apply_settings)
    views = []
    for key in script["keys"]:
        menu.key(" " if key == "space" else key)
        views.append(menu.view())
    settings = dataclasses.asdict(clock.settings)
    del settings["data_dir"]  # Not a setting in a browser
    return {"views": views, "settings": settings}


def search_tables():
    """Tables to search: every golden case's together, and the whole schedule if it is in data/."""
    merged = {"stop_names": {}, "stop_parents": {}, "stop_routes": {}, "headsigns": {}, "direction_labels": {},
              "stop_boroughs": {}}
    for case_dir in case_dirs():
        for name, table in json.loads((case_dir / "static.json").read_text(encoding="utf-8")).items():
            merged[name].update(table)
    tables = [merged]
    try:
        static = StaticData(ROOT / "data")
    except OSError:
        static = None
    if static is not None and static.ready:
        tables.append({"stop_names": static.stop_names, "stop_parents": static.stop_parents,
                       "stop_routes": static.stop_routes, "headsigns": {},
                       "direction_labels": static.direction_labels, "stop_boroughs": static.stop_boroughs})
    return tables


SEARCH_TABLES = search_tables()

spec = importlib.util.spec_from_file_location("build_site", ROOT / "scripts" / "build_site.py")
build_site = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_site)

# What the page reads as schedules.json: every golden case's tables, as scripts/build_site.py publishes them.
PUBLISHED = build_site.schedules(StaticTables(**SEARCH_TABLES[0]))

# The schedule zips in data/, for the page to read as if from the MTA: see HarnessHandler.
ZIPS = {SUBWAY_URL: ROOT / "data" / "gtfs_subway.zip", SUPPLEMENTED_URL: ROOT / "data" / "gtfs_supplemented.zip"}
HAVE_ZIPS = len(SEARCH_TABLES) > 1 and all(path.exists() for path in ZIPS.values())


def search_run(tables):
    picker = StationPicker(StaticTables(**tables))
    return {query: [station.name for station in picker.search(query)] for query in SEARCHES}


class HarnessHandler(Handler):
    """Serves the page's files as the clock's server does, and the tests and the job beside them.

    The page posts what it found to /result.
    """

    def do_POST(self):
        if self.path != "/result":
            self.send_error(404)
            return
        self.server.result = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.send_response(204)
        self.end_headers()
        self.server.done.set()

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/schedules":
            # The zips in data/, as a proxy would pass them on from the MTA
            zip_path = ZIPS.get(parse_qs(urlsplit(self.path).query).get("url", [""])[0])
            if zip_path is None:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Length", str(zip_path.stat().st_size))
            self.send_header("Last-Modified", formatdate(zip_path.stat().st_mtime, usegmt=True))
            self.end_headers()
            try:
                self.wfile.write(zip_path.read_bytes())
            except ConnectionError:
                pass  # The page stopped reading, as it does when it already has this copy
        elif path == "/published/schedules.json":
            self.send_content(json.dumps(PUBLISHED).encode("utf-8"), "application/json")
        elif path == "/job.json":
            self.send_content(json.dumps(self.server.job).encode("utf-8"), "application/json")
        elif path.startswith("/tests/golden/") and path.endswith(".pb"):
            file = (TESTS_DIR / path[len("/tests/"):]).resolve()
            if file.is_relative_to(GOLDEN_DIR) and file.is_file():
                self.send_content(file.read_bytes(), "application/octet-stream")
            else:
                self.send_error(404)
        elif path.startswith("/tests/"):
            self.send_file(TESTS_DIR, path[len("/tests/"):])
        else:
            super().do_GET()


@pytest.fixture(scope="module")
def js():
    """What the harness page found, run once for every test here."""
    browser = find_browser()
    if not browser:
        pytest.skip("no Chrome, Chromium or Edge to run the JavaScript core in")
    server = make_server(service=None, port=0)
    server.RequestHandlerClass = HarnessHandler
    server.job = {
        "golden": [case_dir.name for case_dir in case_dirs()],
        "menus": [{**script, "keys": [" " if key == "space" else key for key in script["keys"]]} for script in MENUS],
        "searches": [{"tables": tables, "queries": SEARCHES} for tables in SEARCH_TABLES],
        "schedules": HAVE_ZIPS,
    }
    server.result = None
    server.done = threading.Event()
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as profile:
            # A profile of its own, or the browser hands the page to one that is already open.
            browsing = subprocess.Popen(
                [browser, "--headless", "--no-first-run", f"--user-data-dir={profile}",
                 f"http://127.0.0.1:{server.server_address[1]}/tests/web/harness.html"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                finished = server.done.wait(timeout=180)
            finally:
                browsing.kill()
                browsing.wait()
    finally:
        server.shutdown()
        server.server_close()
    assert finished, "The harness page didn't post what it found"
    result = server.result
    assert "error" not in result, result.get("error")
    return result


@pytest.mark.parametrize("case_dir", case_dirs(), ids=lambda p: p.name)
def test_golden(js, case_dir):
    expected = json.loads((case_dir / "expected.json").read_text(encoding="utf-8"))
    assert run_case(case_dir) == expected  # The Python core, as test_golden.py checks it
    assert js["golden"][case_dir.name] == expected


@pytest.mark.parametrize("index", range(len(MENUS)))
def test_menu(js, index):
    expected = menu_run(MENUS[index])
    found = js["menus"][index]
    for step, (key, want, got) in enumerate(zip(MENUS[index]["keys"], expected["views"], found["views"])):
        assert got == want, f"after key {step} ({key!r})"
    assert found["settings"] == expected["settings"]


@pytest.mark.parametrize("index", range(len(SEARCH_TABLES)), ids=["golden", "data"][:len(SEARCH_TABLES)])
def test_search(js, index):
    expected = search_run(SEARCH_TABLES[index])
    assert any(expected.values())
    assert js["searches"][index] == expected


def test_published(js):
    found = js["published"]
    assert found["tables"] == {name: PUBLISHED[name] for name in found["tables"]}
    assert found["tables"]["headsigns"] and found["loaded"] and found["same"]


@pytest.mark.skipif(not HAVE_ZIPS, reason="no schedules in data/ to read (run the clock once to fetch them)")
def test_schedules(js):
    static = StaticData(ROOT / "data")
    found = js["schedules"]
    assert found["tables"] == {"stop_names": static.stop_names, "stop_parents": static.stop_parents,
                               "stop_routes": static.stop_routes, "headsigns": static.headsigns}
    assert found["stages"] == ["Downloading schedules", "Reading schedules"]
    assert found["loaded"] and found["same"]
