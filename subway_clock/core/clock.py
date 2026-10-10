import time

from .board import Board, Row, bullet_id
from .feeds import get_predictions


class Clock:
    """Upcoming trains for one stop and the rotating second line, independent of any UI.

    The caller drives timing: call refresh() every settings.refresh_seconds and
    rotate() every settings.rotation_seconds, then draw board().
    """

    def __init__(self, settings, static, fetch=get_predictions):
        self.settings = settings
        self.static = static
        self.fetch = fetch
        self.predictions = []
        self.rotation_index = 1

    def refresh(self, now=None):
        now = time.time() if now is None else now
        self.static.refresh()

        preds = self.fetch(self.settings.stop_id)
        upcoming = sorted([p for p in preds if p['arrival_time'] >= now], key=lambda p: p['arrival_time'])

        self.predictions = upcoming[:self.settings.max_trains]
        self.rotation_index = 1  # Reset rotation to 2nd train

    def rotate(self):
        """Advance the second line to the next train. Returns False if there is nothing to rotate."""
        if len(self.predictions) <= 2:
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

        # Second train (cycled)
        if len(self.predictions) > 1:
            rows.append(self._row(self.rotation_index % len(self.predictions), now))

        return Board(theme=self.settings.theme, rows=tuple(rows))

    def _row(self, index, now):
        pred = self.predictions[index]
        minutes = (pred['arrival_time'] - now) / 60.0
        return Row(
            number=index + 1,
            route=pred['route_id'],
            bullet=bullet_id(pred['route_id']),
            destination=self.static.headsigns.get(pred['trip_id'], "Unknown"),
            minutes=int(minutes),
            arriving=minutes < 1,
        )
