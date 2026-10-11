"""Save a picture of the clock drawing a golden case, to check a style without the live feeds.

From the repo root:

    python scripts/capture.py tests/golden/union-sq-south out.png
    python scripts/capture.py tests/golden/broad-channel out.png --style new --size 608x1080

The case's feeds are replayed as at its first step, plus --offset seconds, and
the last line is rotated --rotate times before the picture is taken. --loading
and --no-connection picture what a first run shows before it has the schedules,
and --loading-trains what every start shows until the first trains are in.
"""
import argparse
import json
import sys
from pathlib import Path

import requests
from google.transit import gtfs_realtime_pb2
from PySide6.QtCore import QSize, QTimer
from PySide6.QtGui import QGuiApplication

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from subway_clock.core.clock import Clock  # noqa: E402
from subway_clock.core.gtfs import StaticTables  # noqa: E402
from subway_clock.core.settings import STYLES, Settings  # noqa: E402
from subway_clock.ui.display import Display, load_fonts  # noqa: E402


def size(value):
    width, height = value.lower().split("x")
    return QSize(int(width), int(height))


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("case", type=Path, help="a directory under tests/golden")
    parser.add_argument("output", help="the PNG to write")
    parser.add_argument("--style", choices=STYLES, help="draw this style instead of the case's")
    parser.add_argument("--station", action="store_true", help="head the screen with the station (show_station)")
    parser.add_argument("--size", type=size, default=QSize(1920, 480), metavar="WIDTHxHEIGHT")
    parser.add_argument("--offset", type=int, default=10, help="seconds after the case's first step (default 10)")
    parser.add_argument("--rotate", type=int, default=0, help="rotations of the last line first (default 0)")
    parser.add_argument("--keys", default="", metavar="KEYS",
                        help="keys to press first, to picture the settings menu: names or characters with "
                             "spaces between, e.g. 'enter enter u n i o n'")
    startup = parser.add_mutually_exclusive_group()
    startup.add_argument("--loading", type=int, metavar="PERCENT",
                         help="draw a first run's loading screen at this percent, instead of the case's trains")
    startup.add_argument("--no-connection", action="store_true",
                         help="draw the screen for a first run with no network, instead of the case's trains")
    startup.add_argument("--loading-trains", action="store_true",
                         help="draw what a start shows until the first trains are in, instead of the case's trains")
    args = parser.parse_args()

    case = json.loads((args.case / "case.json").read_text(encoding="utf-8"))
    start = case["steps"][0]["now"]
    now = start + args.offset

    def fetch_feed(url):
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString((args.case / "feeds" / f"{url.rsplit('%2F', 1)[1]}.pb").read_bytes())
        return feed

    settings = Settings(**{**case["settings"], **({"style": args.style} if args.style else {}),
                           "show_station": args.station})
    static = StaticTables(**json.loads((args.case / "static.json").read_text(encoding="utf-8")))
    clock = Clock(settings, static, fetch_feed=fetch_feed)
    starting = args.loading is not None or args.no_connection or args.loading_trains
    if not starting:
        clock.refresh(now=start)

    # Freeze the clock at the case's time: no live fetches, and every board as at `now`.
    board, rotate = clock.board, clock.rotate
    clock.board = lambda _=None: board(now)
    clock.rotate = lambda _=None: rotate(now)
    clock.fetch = lambda _=None: None
    clock.apply = lambda result, _=None: None

    app = QGuiApplication(sys.argv[:1])
    load_fonts()
    display = Display(clock)
    display.update_timer.stop()
    display.rotation_timer.stop()
    view = display.view
    view.setPosition(0, 0)
    view.show()

    def rotations():
        for _ in range(args.rotate):
            display.rotate_last_line()
        for key in args.keys.split():
            display.menu_model.key(" " if key == "space" else key)
        display.menuChanged.emit()

    def resize():
        view.resize(args.size)
        # By now the display has made its own start, and won't undo these.
        if args.loading is not None:
            display.show_progress("Downloading schedules", args.loading / 100)
        elif args.no_connection:
            display.finish_preparing(requests.ConnectionError("no network (scripts/capture.py --no-connection)"))
        elif args.loading_trains:
            display.set_startup("loading", "Loading train times", progress=-1)
        display.publish()

    def save():
        view.grabWindow().save(args.output)
        app.quit()

    QTimer.singleShot(300, resize)
    QTimer.singleShot(1500, rotations)
    QTimer.singleShot(3000, save)  # After the rotation animation
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
