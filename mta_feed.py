import requests
from google.transit import gtfs_realtime_pb2


FEED_URL = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs"  # 1 train, etc.


def get_predictions():
    feed = gtfs_realtime_pb2.FeedMessage()

    response = requests.get(FEED_URL)
    feed.ParseFromString(response.content)

    predictions = []

    for entity in feed.entity:
        if entity.HasField('trip_update'):
            trip = entity.trip_update
            for stop_time in trip.stop_time_update:
                stop_id = stop_time.stop_id
                if stop_id.startswith("631"):
                    arrival = stop_time.arrival.time
                    predictions.append({
                        'trip_id': trip.trip.trip_id,
                        'route_id': trip.trip.route_id,
                        'stop_id': stop_id,
                        'arrival_time': arrival
                    })

    return predictions


if __name__ == "__main__":
    preds = get_predictions()
