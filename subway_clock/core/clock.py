import time

from .board import Board, Row, bullet_id
from .feeds import feed_urls, fetch_feed, get_predictions
from .gtfs import destination

# Arriving trains stay on the board until the feed drops them. This only guards
# against a feed that keeps a train long after it should have left.
OVERDUE_SECONDS = 5 * 60


class Clock:
    """Upcoming trains for the chosen stops and the rotating second line, independent of any UI.

    The caller drives timing: call refresh() every settings.refresh_seconds and
    rotate() every settings.rotation_seconds, then draw board().
    """

    def __init__(self, settings, static, fetch=fetch_feed):
        self.settings = settings
        self.static = static
        self.fetch = fetch
        self.predictions = []
        self.rotation_index = 1

    def refresh(self, now=None):
        now = time.time() if now is None else now
        self.static.refresh()

        stops = set(self.settings.stops)
        preds = []
        for url in feed_urls(self.static.routes_for(stops)):
            preds.extend(get_predictions(self.fetch(url), stops))
        earliest = now - OVERDUE_SECONDS
        latest = now + self.settings.max_minutes * 60
        upcoming = sorted([p for p in preds if earliest <= p.time <= latest], key=lambda p: p.time)

        self.predictions = upcoming[:self.settings.max_trains]
        self.rotation_index = 1  # Reset rotation to 2nd train

    def rotate(self, now=None):
        """Advance the second line to the next train. Returns False if there is nothing to rotate."""
        now = time.time() if now is None else now
        if len(self.predictions) <= 2 or self._arriving(1, now):
            return False
        self.rotation_index += 1
        if self.rotation_index >= len(self.predictions):
            self.rotation_index = 1
        return True

    def board(self, now=None):
        now = time.time() if now is None else now
        rows = []

        # First train (always static)
        if self.predictions:
            rows.append(self._row(0, now))

        # Second train: cycles through the rest, unless it is also arriving
        if len(self.predictions) > 1:
            index = 1 if self._arriving(1, now) else self.rotation_index % len(self.predictions)
            rows.append(self._row(index, now))

        return Board(theme=self.settings.theme, rows=tuple(rows))

    def _minutes(self, index, now):
        return (self.predictions[index].time - now) / 60.0

    def _arriving(self, index, now):
        return self._minutes(index, now) < 1

    def _row(self, index, now):
        pred = self.predictions[index]
        return Row(
            number=index + 1,
            route=pred.route_id,
            bullet=bullet_id(pred.route_id),
            destination=destination(self.static.stop_names, self.static.headsigns, pred.trip_stops, pred.trip_id),
            minutes=max(0, int(self._minutes(index, now))),
            arriving=self._arriving(index, now),
        )
