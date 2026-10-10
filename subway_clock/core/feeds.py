import json
from pathlib import Path

import requests
from google.transit import gtfs_realtime_pb2


with open(Path(__file__).with_name("urls.json"), "r") as f:
    URL_JSON = json.load(f)

BASE_URL = URL_JSON["base"]
URLS = {line: BASE_URL + suffix for line, suffix in URL_JSON["suffixes"].items()}


def get_predictions(stop):
    feed = gtfs_realtime_pb2.FeedMessage()

    line = stop[0]
    if line == "S": # S is used for SIR
        line = "SIR"
    elif line == "9": # 9 is used for GC Shuttle
        line = "S"
    url = URLS[line]
    response = requests.get(url)
    feed.ParseFromString(response.content)

    predictions = []

    for entity in feed.entity:
        if entity.HasField('trip_update'):
            trip = entity.trip_update
            for stop_time in trip.stop_time_update:
                stop_id = stop_time.stop_id
                if stop_id.startswith(stop):
                    arrival = stop_time.arrival.time
                    predictions.append({
                        'trip_id': trip.trip.trip_id,
                        'route_id': trip.trip.route_id,
                        'stop_id': stop_id,
                        'arrival_time': arrival
                    })

    return predictions
