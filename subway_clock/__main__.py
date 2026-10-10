import argparse
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from .core.clock import Clock
from .core.gtfs import StaticData
from .core.settings import Settings
from .ui.widgets import SubwayDisplay


def main():
    parser = argparse.ArgumentParser(prog="subway_clock", description="NYC subway countdown clock")
    parser.add_argument("--settings", type=Path, default=Path("settings.json"),
                        help="settings file (default: settings.json; defaults are used if it doesn't exist)")
    parser.add_argument("--width", type=int, help="window width in pixels (default: primary screen width)")
    args = parser.parse_args()

    settings = Settings.load(args.settings)
    static = StaticData(args.settings.parent / settings.data_dir)
    clock = Clock(settings, static)

    app = QApplication(sys.argv[:1])
    width = args.width or app.primaryScreen().size().width()
    display = SubwayDisplay(clock, width)
    display.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
