import argparse
import logging
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication

from .core.clock import Clock
from .core.gtfs import StaticData
from .core.settings import Settings
from .ui.display import Display, load_fonts


def size(value):
    width, height = value.lower().split("x")
    return int(width), int(height)


def main():
    parser = argparse.ArgumentParser(prog="subway_clock", description="NYC subway countdown clock")
    parser.add_argument("--settings", type=Path, default=Path("settings.json"),
                        help="settings file (default: settings.json; defaults are used if it doesn't exist)")
    window = parser.add_mutually_exclusive_group()
    window.add_argument("--fullscreen", action="store_true", help="fill the screen (for the device)")
    window.add_argument("--size", type=size, metavar="WIDTHxHEIGHT",
                        help="window size (default: the primary screen's width at 3.2:1)")
    window.add_argument("--width", type=int, help="window width in pixels, at 3.2:1")
    parser.add_argument("--dev", action="store_true",
                        help="resizable window, live QML reload, keys 1-4 for screen shapes and T for theme")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    settings = Settings.load(args.settings)
    static = StaticData(args.settings.parent / settings.data_dir)
    clock = Clock(settings, static)

    app = QGuiApplication(sys.argv[:1])
    load_fonts()
    display = Display(clock, dev=args.dev)
    view = display.view

    if args.fullscreen:
        view.showFullScreen()
        return app.exec()

    if args.size:
        width, height = args.size
    else:
        width = args.width or app.primaryScreen().size().width()
        height = int(width / 3.2)
    view.resize(width, height)
    if not args.dev:
        view.setFlags(view.flags() | Qt.FramelessWindowHint)
        view.setPosition(0, 0)
    view.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
