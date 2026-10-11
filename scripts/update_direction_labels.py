"""Regenerate subway_clock/assets/direction_labels.json from the MTA's subway station list.

The MTA Subway Stations dataset on data.ny.gov gives each station's direction
labels, e.g. "Uptown" and "Downtown", as shown on its platform signs. From the
repo root:

    python scripts/update_direction_labels.py
"""
import csv
import io
import json
from pathlib import Path

import requests

STATIONS_URL = "https://data.ny.gov/api/views/39hk-dx4f/rows.csv?accessType=DOWNLOAD"
OUTPUT = Path(__file__).resolve().parent.parent / "subway_clock" / "assets" / "direction_labels.json"

# "Last Stop" marks the direction trains don't leave in, so it never labels a train.
NOT_LABELS = {"", "Last Stop", "NaN"}


def main():
    response = requests.get(STATIONS_URL, timeout=30)
    response.raise_for_status()
    labels = {}
    for station in csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))):
        directions = {d: station[f"{name} Direction Label"].strip() for d, name in (("N", "North"), ("S", "South"))}
        directions = {d: label for d, label in directions.items() if label not in NOT_LABELS}
        if directions:
            labels[station["GTFS Stop ID"]] = directions
    # One station per line, so updates diff readably
    lines = [f"  {json.dumps(stop)}: {json.dumps(labels[stop], ensure_ascii=False)}" for stop in sorted(labels)]
    OUTPUT.write_text("{\n" + ",\n".join(lines) + "\n}\n", encoding="utf-8", newline="\n")
    print(f"wrote {len(labels)} stations to {OUTPUT}")


if __name__ == "__main__":
    main()
