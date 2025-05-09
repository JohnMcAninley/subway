import csv
import pprint
import collections


def load_stop_names(gtfs_path="gtfs/stops.txt"):
    stop_map = {}

    with open(gtfs_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            stop_id = row['stop_id']
            name = row['stop_name']
            stop_map[stop_id] = name

    return stop_map


def generate_stations(stops):
    """
    TODO this in an insufficient way to group stops into stations. While it
    may end up needing to be done manually, the next attempt should use
    transfers.txt to group stops together.
    """
    stations = collections.defaultdict(list)
    for stop, station in stops.items():
        stations[station].append(stop)

    return stations

"""
def get_trip_to_last_stop_map(gtfs_path="gtfs"):
    trip_stop_times = collections.defaultdict(list)

    # Read stop_times.txt to collect stop sequences
    with open(f"{gtfs_path}/stop_times.txt", newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                trip_id = row['trip_id']
                stop_sequence = int(row['stop_sequence'])
                stop_id = row['stop_id']
                if "_" in trip_id:
                    #trip_id = trip_id.split("_", 2)[2]
                    pass
                trip_stop_times[trip_id].append((stop_sequence, stop_id))
            except:
                print(row['stop_sequence'])

    # Sort stops for each trip and get the last stop
    trip_to_last_stop = {}
    for trip_id, stops in trip_stop_times.items():
        sorted_stops = sorted(stops)
        trip_to_last_stop[trip_id] = sorted_stops[-1][1]  # last stop_id

    return trip_to_last_stop
"""
def load_headsigns(gtfs_path="gtfs/trips.txt", headsigns={}):
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


def all_headsigns():
    trips = load_headsigns()
    trips = load_headsigns("gtfs-supplemented/trips.txt", trips)
    headsigns = set(trips.values())
    headsigns = sorted(headsigns, key=lambda x: len(x), reverse=True)
    for h in headsigns:
        print(h)


if __name__ == "__main__":
    """
    stops = load_stop_names()
    pprint.pprint(stops)
    stations = generate_stations(stops)
    pprint.pprint(stations)
    """
