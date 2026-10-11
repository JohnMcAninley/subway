"""Regenerate subway_clock/assets/stations.json from the MTA's subway station list.

The MTA's developer station list gives each station's borough and its
direction labels, e.g. "Uptown & The Bronx" and "Downtown & Brooklyn", as
shown on its platform signs. (The MTA Subway Stations dataset on data.ny.gov
has the same stations with plainer labels, like "Uptown".) From the repo root:

    python scripts/update_stations.py
"""
import csv
import io
import json
from pathlib import Path

import requests

STATIONS_URL = "http://web.mta.info/developers/data/nyct/subway/Stations.csv"
OUTPUT = Path(__file__).resolve().parent.parent / "subway_clock" / "assets" / "stations.json"

# "Last Stop" marks the direction trains don't leave in, so it never labels a train.
NOT_LABELS = {"", "Last Stop", "NaN"}


def main():
    response = requests.get(STATIONS_URL, timeout=30)
    response.raise_for_status()
    stations = {}
    for station in csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))):
        directions = {d: station[f"{name} Direction Label"].strip() for d, name in (("N", "North"), ("S", "South"))}
        directions = {d: label for d, label in directions.items() if label not in NOT_LABELS}
        # Boroughs are M, Bk, Q, Bx and SI
        stations[station["GTFS Stop ID"]] = {"borough": station["Borough"].strip(), **directions}
    # One station per line, so updates diff readably
    lines = [f"  {json.dumps(stop)}: {json.dumps(stations[stop], ensure_ascii=False)}" for stop in sorted(stations)]
    OUTPUT.write_text("{\n" + ",\n".join(lines) + "\n}\n", encoding="utf-8", newline="\n")
    print(f"wrote {len(stations)} stations to {OUTPUT}")


if __name__ == "__main__":
    main()
