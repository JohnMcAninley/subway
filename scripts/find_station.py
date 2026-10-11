"""Look up a station's stop IDs by name, for the `stops` setting.

From the repo root, once the clock has run and downloaded the schedules:

    python scripts/find_station.py union sq
    python scripts/find_station.py 86 q
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from subway_clock.core.gtfs import StaticData  # noqa: E402
from subway_clock.core.settings import Settings  # noqa: E402
from subway_clock.core.stations import StationPicker  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("name", nargs="+", help="words of the station's name, or its routes")
    parser.add_argument("--settings", type=Path, default=Path("settings.json"),
                        help="settings file, to find the schedules (default: settings.json)")
    args = parser.parse_args()

    settings = Settings.load(args.settings)
    picker = StationPicker(StaticData(args.settings.parent / settings.data_dir))
    stations = picker.search(" ".join(args.name))
    if not stations:
        print("No station matches.")
    for station in stations:
        print(f"{station.name} ({station.borough})")
        for stop in station.stops:
            directions = "   ".join(f"{d.stop_id} {d.label}" for d in stop.directions)
            name = f"{stop.name}: " if len(station.stops) > 1 and stop.name != station.name else ""
            print(f"  {stop.stop_id:4} {name}{' '.join(stop.routes)}   {directions}")


if __name__ == "__main__":
    main()
