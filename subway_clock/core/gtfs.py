"""Static GTFS: download, unzip, and load the tables the clock needs."""
import collections
import csv
import json
import logging
import os
import time
import zipfile
from email.utils import formatdate, parsedate_to_datetime
from pathlib import Path

import requests

SUBWAY_URL = "https://rrgtfsfeeds.s3.amazonaws.com/gtfs_subway.zip"
SUPPLEMENTED_URL = "https://rrgtfsfeeds.s3.amazonaws.com/gtfs_supplemented.zip"

# Generated from the MTA's station list by scripts/update_stations.py
STATIONS_PATH = Path(__file__).resolve().parent.parent / "assets" / "stations.json"

log = logging.getLogger(__name__)


def download_if_newer_zip(url, local_zip_path):
    headers = {}

    if os.path.exists(local_zip_path):
        headers['If-Modified-Since'] = formatdate(os.path.getmtime(local_zip_path), usegmt=True)

    response = requests.get(url, headers=headers, stream=True, timeout=30)

    if response.status_code == 304:
        log.debug("%s is up to date", url)
        return False
    elif response.status_code == 200:
        # Download beside the old copy and swap it in once complete, so an
        # interrupted download can't leave a truncated zip that looks current.
        part_path = f"{local_zip_path}.part"
        with open(part_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        # Update mtime based on Last-Modified header if present
        last_modified = response.headers.get('Last-Modified')
        if last_modified:
            remote_mtime = parsedate_to_datetime(last_modified).timestamp()
            os.utime(part_path, (remote_mtime, remote_mtime))
        os.replace(part_path, local_zip_path)

        log.info("Downloaded %s", url)
        return True
    else:
        log.warning("Downloading %s failed with status %s", url, response.status_code)
        return False


def unzip_and_replace(zip_path, extract_to):
    if not zipfile.is_zipfile(zip_path):
        log.warning("%s is not a valid ZIP archive", zip_path)
        return False

    log.info("Extracting %s to %s", zip_path, extract_to)
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)
    return True


def update(url, data_dir, name):
    """Download data_dir/name.zip if the remote copy is newer and extract it to data_dir/name/."""
    zip_path = Path(data_dir) / f"{name}.zip"
    if download_if_newer_zip(url, zip_path):
        return unzip_and_replace(zip_path, Path(data_dir) / name)
    return False


def load_stops(gtfs_path):
    """Return (stop_id -> name, stop_id -> parent stop_id). Parent stops are their own parent."""
    names = {}
    parents = {}

    with open(gtfs_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            names[row['stop_id']] = row['stop_name']
            parents[row['stop_id']] = row['parent_station'] or row['stop_id']

    return names, parents


def build_stop_routes(gtfs_dirs, parents):
    """Map each parent stop ID to the sorted route IDs scheduled to stop there in any of gtfs_dirs."""
    stop_routes = collections.defaultdict(set)
    for gtfs_dir in gtfs_dirs:
        with open(Path(gtfs_dir) / "trips.txt", newline='', encoding='utf-8') as f:
            trip_routes = {row['trip_id']: row['route_id'] for row in csv.DictReader(f)}
        with open(Path(gtfs_dir) / "stop_times.txt", newline='', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                stop_id = row['stop_id']
                stop_routes[parents.get(stop_id, stop_id)].add(trip_routes[row['trip_id']])
    return {stop: sorted(routes) for stop, routes in stop_routes.items()}


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


def load_stations(path=STATIONS_PATH):
    """The bundled station list as (direction_labels, stop_boroughs); see StaticTables."""
    with open(path, encoding="utf-8") as f:
        stations = json.load(f)
    labels = {stop: {d: station[d] for d in "NS" if d in station} for stop, station in stations.items()}
    boroughs = {stop: station["borough"] for stop, station in stations.items()}
    return {stop: directions for stop, directions in labels.items() if directions}, boroughs


def terminal(stop_names, trip_stops):
    """The stop ID where a realtime trip ends for riders: the last of its stops with a name, or None."""
    return next((stop_id for stop_id in reversed(trip_stops) if stop_id in stop_names), None)


def destination(stop_names, headsigns, trip_stops, trip_id):
    """Where a realtime trip is headed: the last of its stops with a name.

    Some trips end at unnamed non-revenue stops (northbound H trips end at H19,
    past Broad Channel), so skip those. Fall back to the schedule's headsign,
    which only exists for scheduled trips, not added or rerouted ones.
    """
    last = terminal(stop_names, trip_stops)
    return stop_names[last] if last else headsigns.get(trip_id, "Unknown")


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


class StaticTables:
    """The static GTFS lookups the clock uses, as plain JSON-friendly dicts.

    stop_names: stop ID (parent or directional) -> station name
    stop_parents: stop ID -> parent stop ID (parents map to themselves)
    stop_routes: parent stop ID -> sorted route IDs scheduled there
    headsigns: realtime-style trip ID -> scheduled headsign
    direction_labels: parent stop ID -> {"N": label, "S": label}, the MTA's names for
        each platform direction, e.g. {"N": "Uptown", "S": "Downtown"}
    stop_boroughs: parent stop ID -> "M", "Bk", "Q", "Bx" or "SI"
    """

    def __init__(self, stop_names, stop_parents, stop_routes, headsigns, direction_labels=None,
                 stop_boroughs=None):
        self.stop_names = stop_names
        self.stop_parents = stop_parents
        self.stop_routes = stop_routes
        self.headsigns = headsigns
        self.direction_labels = direction_labels or {}
        self.stop_boroughs = stop_boroughs or {}

    def refresh(self):
        """Fixed tables never change."""

    def direction_label(self, stop_id):
        """The direction label for a directional stop ID like "633S", or "" if there isn't one."""
        return self.direction_labels.get(stop_id[:-1], {}).get(stop_id[-1:], "")

    def borough(self, stop_id):
        """The borough code for a stop ID (directional or parent), or "" if unknown."""
        return self.stop_boroughs.get(self.stop_parents.get(stop_id, stop_id), "")

    def routes_for(self, stops):
        """Sorted route IDs scheduled at any of stops (directional or parent stop IDs)."""
        routes = set()
        for stop in stops:
            routes.update(self.stop_routes.get(self.stop_parents.get(stop, stop), ()))
        return sorted(routes)


class StaticData(StaticTables):
    """Static GTFS tables kept in data_dir, refreshed from the MTA when they change.

    The supplemented GTFS adds the next week of planned service changes to the
    regular schedule, so routes rerouted onto a stop are included.
    """

    SOURCES = (("gtfs_subway", SUBWAY_URL), ("gtfs_supplemented", SUPPLEMENTED_URL))
    CHECK_SECONDS = 60 * 60  # The supplemented GTFS is republished about hourly

    def __init__(self, data_dir):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._checked_at = 0
        try:
            # Start from the cached copy if there is one; the first refresh() checks for a newer one.
            self._load()
        except (OSError, KeyError, ValueError):
            log.info("No usable static GTFS in %s, downloading it", self.data_dir)
            self._update_sources()
            self._load()

    def refresh(self):
        """Pick up new static GTFS if the MTA has published it, checking at most every CHECK_SECONDS."""
        if time.time() - self._checked_at < self.CHECK_SECONDS:
            return
        if self._update_sources():
            self._load()

    def _update_sources(self):
        """Download any static GTFS that has changed. Returns True if anything did."""
        self._checked_at = time.time()
        updated = [update(url, self.data_dir, name) for name, url in self.SOURCES]
        return any(updated)

    def _load(self):
        # Build into locals and assign at the end, so readers never see half-loaded tables.
        stop_names, stop_parents = load_stops(self.data_dir / "gtfs_subway" / "stops.txt")
        headsigns = {}
        for name, _ in self.SOURCES:
            load_headsigns(self.data_dir / name / "trips.txt", headsigns)
        stop_routes = self._cached_stop_routes(stop_parents)
        super().__init__(stop_names, stop_parents, stop_routes, headsigns, *load_stations())

    def _cached_stop_routes(self, stop_parents):
        """build_stop_routes takes seconds (millions of stop_times rows), so cache it until the GTFS changes."""
        cache_path = self.data_dir / "stop_routes.json"
        sources = {name: os.path.getmtime(self.data_dir / f"{name}.zip") for name, _ in self.SOURCES}
        if cache_path.exists():
            with open(cache_path, encoding="utf-8") as f:
                cache = json.load(f)
            if cache["sources"] == sources:
                return cache["stop_routes"]

        log.info("Building stop routes from GTFS schedules")
        stop_routes = build_stop_routes([self.data_dir / name for name, _ in self.SOURCES], stop_parents)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump({"sources": sources, "stop_routes": stop_routes}, f)
        return stop_routes
