import json
import requests

from google.transit import gtfs_realtime_pb2


with open("urls.json", "r") as f:
    URL_JSON = json.load(f)

BASE_URL = URL_JSON["base"]
URLS = {line: BASE_URL + suffix for line, suffix in URL_JSON["suffixes"].items()}


def get_predictions(stop_id):
    feed = gtfs_realtime_pb2.FeedMessage()

    line = stop_id[0]
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
                if stop_id.startswith("R36"):
                    arrival = stop_time.arrival.time
                    predictions.append({
                        'trip_id': trip.trip.trip_id,
                        'route_id': trip.trip.route_id,
                        'stop_id': stop_id,
                        'arrival_time': arrival
                    })

    return predictions


if __name__ == "__main__":
    preds = get_predictions("631")
