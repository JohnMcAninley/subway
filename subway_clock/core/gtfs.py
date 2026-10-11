"""Static GTFS: download, unzip, and load the tables the clock needs."""
import collections
import csv
import io
import json
import logging
import os
import re
import shutil
import time
import zipfile
import zlib
from email.utils import formatdate, parsedate_to_datetime
from pathlib import Path

import requests

SUBWAY_URL = "https://rrgtfsfeeds.s3.amazonaws.com/gtfs_subway.zip"
SUPPLEMENTED_URL = "https://rrgtfsfeeds.s3.amazonaws.com/gtfs_supplemented.zip"

# Generated from the MTA's station list by scripts/update_stations.py
STATIONS_PATH = Path(__file__).resolve().parent.parent / "assets" / "stations.json"

# Written into an extracted directory once it is complete: the mtime of the zip it came from.
EXTRACTED_MARKER = ".extracted"

# The route and direction in a realtime-style trip ID: "6" and "S" in "061200_6..S04X001"
TRIP_ROUTE_DIRECTION = re.compile(r"_(\w+?)\.+([NS])")

log = logging.getLogger(__name__)


def download_if_newer_zip(url, local_zip_path, progress=None):
    """Download url if it is newer than the local copy. progress, if given, is called with 0 to 1."""
    headers = {}

    if os.path.exists(local_zip_path):
        headers['If-Modified-Since'] = formatdate(os.path.getmtime(local_zip_path), usegmt=True)

    response = requests.get(url, headers=headers, stream=True, timeout=30)

    if response.status_code == 304:
        log.debug("%s is up to date", url)
        return False
    response.raise_for_status()

    # Download beside the old copy and swap it in once complete, so an
    # interrupted download can't leave a truncated zip that looks current.
    part_path = f"{local_zip_path}.part"
    total = int(response.headers.get('Content-Length', 0))
    done = 0
    with open(part_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
            done += len(chunk)
            if progress and total:
                progress(min(1, done / total))

    # Update mtime based on Last-Modified header if present
    last_modified = response.headers.get('Last-Modified')
    if last_modified:
        remote_mtime = parsedate_to_datetime(last_modified).timestamp()
        os.utime(part_path, (remote_mtime, remote_mtime))
    os.replace(part_path, local_zip_path)

    log.info("Downloaded %s", url)
    return True


def unzip_and_replace(zip_path, extract_to, progress=None):
    """Replace extract_to with the zip's contents. progress, if given, is called with 0 to 1.

    A zip that can't be read is deleted, so the next update downloads it again.
    """
    extract_to = Path(extract_to)
    # Extract beside the old copy and swap it in once complete, as for the download.
    part_path = extract_to.with_name(f"{extract_to.name}.part")
    shutil.rmtree(part_path, ignore_errors=True)

    log.info("Extracting %s to %s", zip_path, extract_to)
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            members = zip_ref.infolist()
            total = sum(member.file_size for member in members)
            done = 0
            for member in members:
                zip_ref.extract(member, part_path)
                done += member.file_size
                if progress and total:
                    progress(done / total)
    except (zipfile.BadZipFile, zlib.error, EOFError) as e:
        log.warning("%s is not a valid ZIP archive (%s), so it will be downloaded again", zip_path, e)
        shutil.rmtree(part_path, ignore_errors=True)
        os.remove(zip_path)
        return False

    (part_path / EXTRACTED_MARKER).write_text(repr(os.path.getmtime(zip_path)))
    shutil.rmtree(extract_to, ignore_errors=True)
    os.replace(part_path, extract_to)
    return True


def extracted(zip_path, extract_to):
    """True if extract_to holds everything in zip_path as it is now."""
    try:
        return float((Path(extract_to) / EXTRACTED_MARKER).read_text()) == os.path.getmtime(zip_path)
    except (OSError, ValueError):
        return False


def update(url, data_dir, name, downloading=None, extracting=None):
    """Download data_dir/name.zip if the remote copy is newer and extract it to data_dir/name/.

    downloading and extracting, if given, are each called with 0 to 1 as that part goes.
    """
    zip_path = Path(data_dir) / f"{name}.zip"
    extract_to = Path(data_dir) / name
    downloaded = download_if_newer_zip(url, zip_path, downloading)
    # Also extract a zip from an earlier run that never finished extracting.
    if downloaded or zip_path.exists() and not extracted(zip_path, extract_to):
        return unzip_and_replace(zip_path, extract_to, extracting)
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


def build_stop_routes(gtfs_dirs, parents, progress=None):
    """Map each parent stop ID to the sorted route IDs scheduled to stop there in any of gtfs_dirs.

    progress, if given, is called with 0 to 1.
    """
    stop_routes = collections.defaultdict(set)
    total = sum(os.path.getsize(Path(gtfs_dir) / "stop_times.txt") for gtfs_dir in gtfs_dirs)
    done = 0
    for gtfs_dir in gtfs_dirs:
        with open(Path(gtfs_dir) / "trips.txt", newline='', encoding='utf-8') as f:
            trip_routes = {row['trip_id']: row['route_id'] for row in csv.DictReader(f)}
        # Opened as bytes underneath, which can say how far through the file the rows are.
        with open(Path(gtfs_dir) / "stop_times.txt", 'rb') as raw:
            # By column number: a dict for each of millions of rows takes twice as long.
            rows = csv.reader(io.TextIOWrapper(raw, newline='', encoding='utf-8'))
            header = next(rows)
            trip_column, stop_column = header.index('trip_id'), header.index('stop_id')
            for count, row in enumerate(rows):
                stop_id = row[stop_column]
                stop_routes[parents.get(stop_id, stop_id)].add(trip_routes[row[trip_column]])
                if progress and count % 20000 == 0:
                    progress((done + raw.tell()) / total)
            done += raw.tell()
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

    ready = True  # False while the tables are still to be fetched; see StaticData.prepare

    def __init__(self, stop_names, stop_parents, stop_routes, headsigns, direction_labels=None,
                 stop_boroughs=None):
        self.stop_names = stop_names
        self.stop_parents = stop_parents
        self.stop_routes = stop_routes
        self.headsigns = headsigns
        self.direction_labels = direction_labels or {}
        self.stop_boroughs = stop_boroughs or {}
        self._terminals = None  # see terminals(); worked out when first asked for

    def refresh(self):
        """Fixed tables never change."""

    def terminals(self, route_id, direction):
        """The headsigns of route_id's scheduled trips in a direction ("N" or "S"): where they end.

        A trip ID like "061200_6..S04X001" names its route and direction after
        the underscore. Express routes ("6X") are scheduled under the local's ID.
        """
        if self._terminals is None:
            terminals = collections.defaultdict(set)
            for trip_id, headsign in self.headsigns.items():
                trip = TRIP_ROUTE_DIRECTION.search(trip_id)
                if trip:
                    terminals[trip.groups()].add(headsign)
            self._terminals = terminals
        return self._terminals.get((route_id.removesuffix("X"), direction), ())

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

    # What a cached copy that is missing, incomplete or damaged fails to load with.
    LOAD_ERRORS = (OSError, LookupError, ValueError)

    # The share of prepare()'s time that goes on the downloads, and on each download rather than
    # extracting it. Indexing the stop routes takes the rest.
    DOWNLOADS_SHARE = 0.6
    DOWNLOAD_SHARE = 0.8

    def __init__(self, data_dir):
        super().__init__({}, {}, {}, {})
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._checked_at = 0
        try:
            # Start from the cached copy if it is all there; the first refresh() checks for a newer one.
            self._load(build=False)
        except self.LOAD_ERRORS:
            # A first run, most likely. It is up to the caller to call prepare().
            self.ready = False

    def prepare(self, progress=None):
        """Download and index the static GTFS, when there was no usable cached copy to start from.

        This takes about a minute. progress, if given, is called with what is
        going on ("Downloading schedules") and how far along the whole is, 0 to
        1. Raises requests.RequestException if a download fails, or one of
        LOAD_ERRORS if what there is still can't be loaded; either way it can be
        called again.
        """
        log.info("No usable static GTFS in %s, downloading it", self.data_dir)
        try:
            self._update_sources(progress)
        except requests.RequestException as e:
            # No network, but an earlier download may only have been waiting to be indexed.
            try:
                self._load(progress)
            except self.LOAD_ERRORS:
                raise e from None
        else:
            self._load(progress)
        self.ready = True

    def refresh(self):
        """Pick up new static GTFS if the MTA has published it, checking at most every CHECK_SECONDS."""
        if time.time() - self._checked_at < self.CHECK_SECONDS:
            return
        if self._update_sources():
            self._load()

    def _update_sources(self, progress=None):
        """Download any static GTFS that has changed. Returns True if anything did."""
        self._checked_at = time.time()
        share = self.DOWNLOADS_SHARE / len(self.SOURCES)
        updated = []
        for i, (name, url) in enumerate(self.SOURCES):
            split = (i + self.DOWNLOAD_SHARE) * share
            updated.append(update(url, self.data_dir, name,
                                  _stage(progress, "Downloading schedules", i * share, split),
                                  _stage(progress, "Unpacking schedules", split, (i + 1) * share)))
        return any(updated)

    def _load(self, progress=None, build=True):
        """Load the tables from data_dir. With build false, fail rather than spend seconds indexing."""
        # Build into locals and assign at the end, so readers never see half-loaded tables.
        stop_names, stop_parents = load_stops(self.data_dir / "gtfs_subway" / "stops.txt")
        headsigns = {}
        for name, _ in self.SOURCES:
            load_headsigns(self.data_dir / name / "trips.txt", headsigns)
        stop_routes = self._cached_stop_routes(stop_parents, build,
                                               _stage(progress, "Reading schedules", self.DOWNLOADS_SHARE, 1))
        super().__init__(stop_names, stop_parents, stop_routes, headsigns, *load_stations())

    def _cached_stop_routes(self, stop_parents, build, progress):
        """build_stop_routes takes seconds (millions of stop_times rows), so cache it until the GTFS changes."""
        cache_path = self.data_dir / "stop_routes.json"
        sources = {name: os.path.getmtime(self.data_dir / f"{name}.zip") for name, _ in self.SOURCES}
        try:
            with open(cache_path, encoding="utf-8") as f:
                cache = json.load(f)
            if cache["sources"] == sources:
                return cache["stop_routes"]
        except self.LOAD_ERRORS:
            pass  # No cache yet, or not one that can be read: build it again
        if not build:
            raise LookupError(f"{cache_path} isn't up to date")

        log.info("Building stop routes from GTFS schedules")
        stop_routes = build_stop_routes([self.data_dir / name for name, _ in self.SOURCES], stop_parents, progress)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump({"sources": sources, "stop_routes": stop_routes}, f)
        return stop_routes


def _stage(progress, name, start, end):
    """A 0-to-1 progress callback for one stage of a whole: it reports name and start to end to progress."""
    if progress is None:
        return None
    return lambda fraction: progress(name, start + (end - start) * fraction)
