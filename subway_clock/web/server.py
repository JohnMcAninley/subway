"""Web front end: runs the clock's timers and serves its Board to a page that draws it in a browser.

    python -m subway_clock.web [--settings settings.json] [--host 127.0.0.1] [--port 8000]

The page (static/) asks for /api/state about once a second, saying how many
lines fit its screen, and draws what comes back as qml/Main.qml draws
clock.board: the Board, what to show until there is one, and the settings
menu. The keys pressed and the clicks made on the page are posted to /api/menu
for the menu (ui/menu.py), which is the same one the Qt front end has.

Nothing here needs Qt, so it runs on a machine with no screen.

It also serves standalone.html, the page with the JavaScript core in it
(static/core), which needs no server of its own once it is on a static host
(scripts/build_site.py). For trying it here, /proxy passes on the two schedule
zips that a page can't read from the MTA itself, and config.json points the
page at it.
"""
import argparse
import dataclasses
import json
import logging
import re
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

import requests

from ..core.clock import Clock
from ..core.gtfs import SUBWAY_URL, SUPPLEMENTED_URL, StaticData
from ..core.settings import Settings
from ..ui.menu import Menu

PACKAGE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = Path(__file__).resolve().parent / "static"
ASSETS_DIR = PACKAGE_DIR / "assets"
QML_DIR = PACKAGE_DIR / "ui" / "qml"
FEEDS_PATH = PACKAGE_DIR / "core" / "feeds.json"  # for the JavaScript core, as core/feeds.json

# What /proxy will fetch for a page: only the schedules, so that it is no use as anyone's proxy.
PROXIED = (SUBWAY_URL, SUPPLEMENTED_URL)

# The QML's JavaScript libraries that the page uses as they are: see library().
LIBRARIES = ("Styles", "Messages", "LedFont")

TYPES = {
    ".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8",
    ".json": "application/json", ".svg": "image/svg+xml", ".ttf": "font/ttf",
}

# How long to wait before trying again when the schedules can't be fetched at startup.
RETRY_SECONDS = 15

# A screen shape that no page has asked about for this long is forgotten.
VIEW_SECONDS = 30
MAX_LINES = 10

log = logging.getLogger(__name__)


def library(name):
    """One of the QML's JavaScript libraries as a script for a page: a global of its name, holding what it defines."""
    source = (QML_DIR / f"{name}.js").read_text(encoding="utf-8").replace(".pragma library", "")  # QML's, not JavaScript
    names = re.findall(r"^(?:var|function) (\w+)", source, re.MULTILINE)
    return f"const {name} = (function () {{{source}\nreturn {{ {', '.join(names)} }}\n}})()\n"


@dataclasses.dataclass
class View:
    """A screen shape some page is showing: where its last line is in its rotation, and when it was last asked for."""
    index: int = 0
    seen: float = 0.0


class Service:
    """Owns the clock's timers, as ui/display.py does for Qt, and hands out what the page draws.

    Pages of different shapes fit different numbers of lines, and the clock
    lays out one board at a time, so each shape (a View) keeps its own place
    in the last line's rotation and the clock is set to it for each board.

    With settings_path, the settings file is read again whenever it changes,
    and the menu saves to it. With live False nothing is fetched and nothing
    rotates by itself, for a clock stopped at a moment (scripts/capture.py).
    """

    def __init__(self, clock, settings_path=None, live=True):
        self.clock = clock
        self.lock = threading.RLock()  # the clock, the views and the menu belong to whoever holds it
        self.startup = {"state": "ready", "title": "", "detail": "", "progress": 0.0}
        self.started = False  # the schedules are in, and the trains are being fetched
        self.views = {}  # (lines, grouped) -> View
        self.menu = Menu(clock, self.change_settings)
        self.refetch = threading.Event()  # set to fetch the trains now instead of at the next refresh
        self.settings_path = None if settings_path is None else Path(settings_path)
        # What the file last said, which is what a change to it is compared with.
        self.file_settings = clock.settings
        self._stamp = self._settings_stamp()
        self._reported = None
        if live:
            threading.Thread(target=self._run_fetches, name="fetches", daemon=True).start()
            threading.Thread(target=self._run_timers, name="timers", daemon=True).start()

    def set_startup(self, state, title="", detail="", progress=0.0):
        """What to show while there is no board yet: see Display.startup in ui/display.py."""
        self.startup = {"state": state, "title": title, "detail": detail, "progress": progress}

    def show_progress(self, stage, fraction):
        self.set_startup("loading", stage, "This can take a minute", fraction)

    def _report_progress(self, stage, fraction):
        # A download reports every few kilobytes; only whole percents are worth showing.
        report = (stage, int(fraction * 100) / 100)
        if report != self._reported:
            self._reported = report
            self.show_progress(*report)

    def _prepare(self):
        """Fetch the schedules if a first run still has to, trying again for as long as it takes."""
        static = self.clock.static
        while not static.ready:
            self.show_progress("Loading schedules", 0)
            try:
                static.prepare(self._report_progress)
            except Exception as e:
                offline = isinstance(e, requests.RequestException)
                log.warning("Fetching the schedules failed, trying again in %s seconds: %r", RETRY_SECONDS, e,
                            exc_info=None if offline else e)
                self.set_startup("failed", "No connection" if offline else "Can't read the schedules",
                                 "Trying again shortly")
                time.sleep(RETRY_SECONDS)

    def _run_fetches(self):
        self._prepare()
        with self.lock:
            self.started = True
            self.set_startup("loading", "Loading train times", progress=-1)
        while True:
            self.refetch.clear()
            try:
                result = self.clock.fetch()
            except Exception:
                log.exception("Fetching predictions failed")
                result = None
            self.apply_predictions(result)
            # Settings changed meanwhile were fetched for as they were: go round again at once.
            self.refetch.wait(self.clock.settings.refresh_seconds)

    def apply_predictions(self, result):
        with self.lock:
            if result is not None:
                if not self.clock.apply(result):
                    return  # For stops that have since been replaced; the fetch for the new ones is next.
                self._restart_rotations()
            # The first fetch is back. If it failed, the board says so itself (it is stale).
            if self.startup["state"] != "ready":
                self.set_startup("ready")

    def _run_timers(self):
        rotated = time.monotonic()
        while True:
            time.sleep(0.25)
            try:
                self.reload_settings()
                if time.monotonic() - rotated >= self.clock.settings.rotation_seconds:
                    rotated = time.monotonic()
                    self.rotate()
            except Exception:
                log.exception("The clock's timers failed")

    def _lay_out(self, lines, grouped, index):
        # A change of lines restarts the clock's rotation, so the view's place in it goes back afterwards.
        self.clock.lines, self.clock.grouped = lines, grouped
        self.clock.rotation_index = index

    def _restart_rotations(self):
        for view in self.views.values():
            view.index = 0

    def rotate(self):
        """Advance every view's last line to its next train or alert."""
        with self.lock:
            now = time.monotonic()
            self.views = {shape: view for shape, view in self.views.items() if now - view.seen < VIEW_SECONDS}
            for (lines, grouped), view in self.views.items():
                self._lay_out(lines, grouped, view.index)
                self.clock.rotate()
                view.index = self.clock.rotation_index

    def state(self, lines=2, grouped=False):
        """What a page with room for `lines` lines draws, as JSON-ready values."""
        lines = max(1, min(MAX_LINES, lines))
        with self.lock:
            view = self.views.setdefault((lines, grouped), View())
            view.seen = time.monotonic()
            self._lay_out(lines, grouped, view.index)
            return {
                "board": dataclasses.asdict(self.clock.board()),
                "startup": self.startup,
                "showStation": self.clock.settings.show_station,
                "menu": self.menu.view(),
            }

    def act(self, action):
        """Pass on to the settings menu what was done on a page. Returns False if that isn't anything it knows.

        action: {"key": a key's name or the character typed}, {"click": the index of
        the row clicked, or None for a click on the clock}, {"back": True} or
        {"scroll": rows to move down by}; see Menu.key, click, back and scroll.
        """
        with self.lock:
            if isinstance(action.get("key"), str):
                self.menu.key(action["key"])
            elif "click" in action and (action["click"] is None or isinstance(action["click"], int)):
                self.menu.click(action["click"])
            elif action.get("back") is True:
                self.menu.back()
            elif isinstance(action.get("scroll"), int):
                self.menu.scroll(action["scroll"])
            else:
                return False
            return True

    def change_settings(self, settings):
        """Put settings chosen on the menu into effect, and save them if there is a file to save to."""
        if self.settings_path is not None:
            try:
                settings.save(self.settings_path)
            except OSError as e:
                log.warning("Can't save %s, so these settings last until the clock is closed: %s",
                            self.settings_path, e)
            else:
                self.file_settings = settings  # so that reading the file back changes nothing
        self.apply_settings(settings)

    def apply_settings(self, settings):
        """Switch to new settings without a restart."""
        with self.lock:
            old = self.clock.settings
            refetch = self.clock.apply_settings(settings)
            self._restart_rotations()
            # Until the schedules are in there are no fetches to hurry, and the first is yet to come.
            if refetch and self.started:
                if set(settings.stops) != set(old.stops):
                    self.set_startup("loading", "Loading train times", progress=-1)
                self.refetch.set()

    def _settings_stamp(self):
        try:
            return self.settings_path.stat().st_mtime_ns
        except (AttributeError, OSError):  # no file to watch, or it isn't there
            return None

    def reload_settings(self):
        """Read the settings file again if it has changed since it was last looked at."""
        stamp = self._settings_stamp()
        if self.settings_path is None or stamp == self._stamp:
            return
        self._stamp = stamp
        old = self.file_settings
        try:
            settings = Settings.load(self.settings_path)
        except (OSError, ValueError, TypeError, AttributeError) as e:
            log.warning("Can't read %s, keeping the settings as they were: %s", self.settings_path, e)
            return
        if settings == old:
            return
        if settings.data_dir != old.data_dir:
            log.warning("A new data_dir takes effect at the next start")
        log.info("Settings changed (%s)", ", ".join(
            field.name for field in dataclasses.fields(settings)
            if getattr(settings, field.name) != getattr(old, field.name)))
        self.file_settings = settings
        self.apply_settings(settings)


class Handler(BaseHTTPRequestHandler):
    """Serves the page, the assets it draws with, and the clock's state."""

    server_version = "subway-clock"

    def do_GET(self):
        url = urlsplit(self.path)
        path = unquote(url.path)
        if path == "/api/state":
            self.send_state(url.query)
        elif path == "/proxy":
            self.send_proxied(parse_qs(url.query).get("url", [""])[0])
        elif path == "/config.json":
            self.send_content(json.dumps({"proxy": "proxy?url="}).encode("utf-8"), TYPES[".json"])
        elif path == "/core/feeds.json":
            self.send_content(FEEDS_PATH.read_bytes(), TYPES[".json"])
        elif path.startswith("/qml/") and path[5:-3] in LIBRARIES and path.endswith(".js"):
            self.send_content(library(path[5:-3]).encode("utf-8"), TYPES[".js"])
        elif path.startswith("/assets/"):
            self.send_file(ASSETS_DIR, path[len("/assets/"):])
        else:
            self.send_file(STATIC_DIR, path[1:] or "index.html")

    def do_POST(self):
        url = urlsplit(self.path)
        # Only JSON, which a page on another site can't post here without asking first.
        if url.path != "/api/menu" or self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            action = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        except ValueError:
            action = None
        if not isinstance(action, dict) or not self.server.service.act(action):
            self.send_error(HTTPStatus.BAD_REQUEST)
            return
        self.send_state(url.query)

    def send_state(self, query):
        values = parse_qs(query)
        try:
            lines = int(values.get("lines", ["2"])[0])
        except ValueError:
            self.send_error(HTTPStatus.BAD_REQUEST)
            return
        state = self.server.service.state(lines, values.get("grouped", ["0"])[0] == "1")
        self.send_content(json.dumps(state).encode("utf-8"), TYPES[".json"])

    def send_proxied(self, url):
        """Pass on one of the schedule zips, with the headers the page reads."""
        if url not in PROXIED:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            log.warning("Fetching %s for a page failed: %s", url, e)
            self.send_error(HTTPStatus.BAD_GATEWAY)
            return
        with response:
            self.send_response(HTTPStatus.OK)
            for header in ("Content-Type", "Content-Length", "Last-Modified"):
                if header in response.headers:
                    self.send_header(header, response.headers[header])
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            try:
                for chunk in response.iter_content(chunk_size=65536):
                    self.wfile.write(chunk)
            except ConnectionError:
                pass  # The page stopped reading, as it does when it already has this copy

    def send_file(self, root, name):
        file = (root / name).resolve()
        if not file.is_relative_to(root) or not file.is_file() or file.suffix not in TYPES:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self.send_content(file.read_bytes(), TYPES[file.suffix])

    def send_content(self, content, content_type):
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format, *args):
        log.debug("%s %s", self.address_string(), format % args)  # A page asks every second


def make_server(service, host="127.0.0.1", port=8000):
    """An HTTP server for a Service, yet to be started with serve_forever(). Port 0 is any free port."""
    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    server.service = service
    return server


def main():
    parser = argparse.ArgumentParser(prog="subway_clock.web", description="NYC subway countdown clock, in a browser")
    parser.add_argument("--settings", type=Path, default=Path("settings.json"),
                        help="settings file (default: settings.json; defaults are used if it doesn't exist)")
    parser.add_argument("--host", default="127.0.0.1",
                        help="address to serve at (default: 127.0.0.1, this computer only; 0.0.0.0 for the "
                             "whole network, where anyone who can open the page can change the settings)")
    parser.add_argument("--port", type=int, default=8000, help="port to serve at (default: 8000)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    settings = Settings.load(args.settings)
    static = StaticData(args.settings.parent / settings.data_dir)
    service = Service(Clock(settings, static), settings_path=args.settings)
    server = make_server(service, args.host, args.port)
    log.info("The clock is at http://%s:%s/ (Ctrl+C to stop)", *server.server_address[:2])
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0
