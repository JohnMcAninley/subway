"""Static GTFS: download, unzip, and load the tables the clock needs."""
import collections
import csv
import os
import zipfile
from email.utils import formatdate, parsedate_to_datetime
from pathlib import Path

import requests

SUBWAY_URL = "https://rrgtfsfeeds.s3.amazonaws.com/gtfs_subway.zip"
SUPPLEMENTED_URL = "https://rrgtfsfeeds.s3.amazonaws.com/gtfs_supplemented.zip"


def download_if_newer_zip(url, local_zip_path):
    headers = {}

    if os.path.exists(local_zip_path):
        headers['If-Modified-Since'] = formatdate(os.path.getmtime(local_zip_path), usegmt=True)

    response = requests.get(url, headers=headers, stream=True)

    if response.status_code == 304:
        print("ZIP file is up to date. No download needed.")
        return False
    elif response.status_code == 200:
        with open(local_zip_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        # Update mtime based on Last-Modified header if present
        last_modified = response.headers.get('Last-Modified')
        if last_modified:
            remote_mtime = parsedate_to_datetime(last_modified).timestamp()
            os.utime(local_zip_path, (remote_mtime, remote_mtime))

        print("Downloaded updated ZIP file.")
        return True
    else:
        print(f"Failed to download ZIP. Status code: {response.status_code}")
        return False


def unzip_and_replace(zip_path, extract_to):
    if not zipfile.is_zipfile(zip_path):
        print("Provided file is not a valid ZIP archive.")
        return False

    print(f"Extracting ZIP to: {extract_to}")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)
    return True


def update(url, data_dir, name):
    """Download data_dir/name.zip if the remote copy is newer and extract it to data_dir/name/."""
    zip_path = Path(data_dir) / f"{name}.zip"
    if download_if_newer_zip(url, zip_path):
        return unzip_and_replace(zip_path, Path(data_dir) / name)
    return False


def load_stop_names(gtfs_path):
    stop_map = {}

    with open(gtfs_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            stop_map[row['stop_id']] = row['stop_name']

    return stop_map


def load_headsigns(gtfs_path, headsigns=None):
    """Map realtime-style trip IDs to headsigns, adding to headsigns if given."""
    if headsigns is None:
        headsigns = {}
    with open(gtfs_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            trip_id = row['trip_id']
            trip_headsign = row['trip_headsign']
            # Remove service and schedule from trip_id to match realtime format
            # e.g. AFA24GEN-1038-Sunday-00_000600_1..S03R -> 000600_1..S03R
            trip_id = trip_id.split("_", 1)[1]
            headsigns[trip_id] = trip_headsign

    return headsigns


def build_station_complexes(stops_path, transfers_path):
    # First pass: find parent_station mappings
    stop_to_parent = {}
    parent_to_name = {}
    with open(stops_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            stop_id = row['stop_id']
            parent_station = row['parent_station'] or stop_id
            stop_to_parent[stop_id] = parent_station
            if parent_station == stop_id:
                parent_to_name[parent_station] = row['stop_name']

    # Initialize union-find (disjoint set) for complexes
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    def union(x, y):
        parent[find(x)] = find(y)

    # Union parent stations if they have transfers
    with open(transfers_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            from_stop = stop_to_parent[row['from_stop_id']]
            to_stop = stop_to_parent[row['to_stop_id']]
            union(from_stop, to_stop)

    # Build final complexes
    complexes = collections.defaultdict(list)
    for stop, station in stop_to_parent.items():
        complex_id = find(station)
        complexes[complex_id].append(stop)

    return parent_to_name, complexes


class StaticData:
    """Static GTFS tables kept in data_dir, refreshed from the MTA when they change."""

    def __init__(self, data_dir):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        update(SUBWAY_URL, self.data_dir, "gtfs_subway")
        update(SUPPLEMENTED_URL, self.data_dir, "gtfs_supplemented")

        self.stop_names = load_stop_names(self.data_dir / "gtfs_subway" / "stops.txt")
        self.headsigns = load_headsigns(self.data_dir / "gtfs_subway" / "trips.txt")
        load_headsigns(self.data_dir / "gtfs_supplemented" / "trips.txt", self.headsigns)

    def refresh(self):
        """Pick up new supplemented GTFS (planned service changes) if the MTA has published it."""
        if update(SUPPLEMENTED_URL, self.data_dir, "gtfs_supplemented"):
            load_headsigns(self.data_dir / "gtfs_supplemented" / "trips.txt", self.headsigns)
