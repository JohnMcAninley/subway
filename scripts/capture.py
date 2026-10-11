"""Save a picture of the clock drawing a golden case, to check a style without the live feeds.

From the repo root:

    python scripts/capture.py tests/golden/union-sq-south out.png
    python scripts/capture.py tests/golden/broad-channel out.png --style new --size 608x1080

The case's feeds are replayed as at its first step, plus --offset seconds, and
the last line is rotated --rotate times before the picture is taken.
"""
import argparse
import json
import sys
from pathlib import Path

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
    parser.add_argument("--size", type=size, default=QSize(1920, 480), metavar="WIDTHxHEIGHT")
    parser.add_argument("--offset", type=int, default=10, help="seconds after the case's first step (default 10)")
    parser.add_argument("--rotate", type=int, default=0, help="rotations of the last line first (default 0)")
    args = parser.parse_args()

    case = json.loads((args.case / "case.json").read_text(encoding="utf-8"))
    start = case["steps"][0]["now"]
    now = start + args.offset

    def fetch_feed(url):
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString((args.case / "feeds" / f"{url.rsplit('%2F', 1)[1]}.pb").read_bytes())
        return feed

    settings = Settings(**{**case["settings"], **({"style": args.style} if args.style else {})})
    static = StaticTables(**json.loads((args.case / "static.json").read_text(encoding="utf-8")))
    clock = Clock(settings, static, fetch_feed=fetch_feed)
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

    def save():
        view.grabWindow().save(args.output)
        app.quit()

    QTimer.singleShot(300, lambda: (view.resize(args.size), display.publish()))
    QTimer.singleShot(1500, rotations)
    QTimer.singleShot(3000, save)  # After the rotation animation
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
