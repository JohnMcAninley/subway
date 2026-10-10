import logging
import time
from dataclasses import dataclass

import requests
from google.protobuf.message import DecodeError

from .board import Board, Row, bullet_id
from .feeds import ALL_FEED_URLS, feed_urls, fetch_feed, get_predictions
from .gtfs import destination

log = logging.getLogger(__name__)

# Arriving trains stay on the board until the feed drops them. This only guards
# against a feed that keeps a train long after it should have left.
OVERDUE_SECONDS = 5 * 60

# The board is marked stale once any feed it needs has failed for this many refreshes.
STALE_REFRESHES = 3


@dataclass(frozen=True)
class FetchResult:
    fetched_at: float
    feeds: dict  # feed URL -> list of Predictions, or None if fetching that feed failed
    scheduled: tuple  # URLs of the feeds for routes scheduled at the stops


class Clock:
    """Upcoming trains for the chosen stops and the rotating second line, independent of any UI.

    The caller drives timing: every settings.refresh_seconds, run fetch() (which
    blocks on the network, so off the UI thread if there is one) and pass its
    result to apply(); every settings.rotation_seconds call rotate(); then draw
    board(). refresh() does fetch and apply in one step.
    """

    def __init__(self, settings, static, fetch_feed=fetch_feed):
        self.settings = settings
        self.static = static
        self.fetch_feed = fetch_feed
        self.predictions = []
        self.rotation_index = 1
        self._feeds = {}  # feed URL -> (predictions, fetched_at) from the last successful fetch
        self._scheduled = []  # feed URLs for routes scheduled at the chosen stops

    def refresh(self, now=None):
        self.apply(self.fetch(now), now)

    def fetch(self, now=None):
        """Download the feeds for the chosen stops. Safe to call from a worker thread."""
        now = time.time() if now is None else now
        try:
            self.static.refresh()
        except (requests.RequestException, OSError) as e:
            log.warning("Checking for new static GTFS failed, using the cached copy: %s", e)

        stops = set(self.settings.stops)
        scheduled = feed_urls(self.static.routes_for(stops))
        feeds = {}
        for url in ALL_FEED_URLS if self.settings.fetch_all_feeds else scheduled:
            try:
                feeds[url] = get_predictions(self.fetch_feed(url), stops)
            except (requests.RequestException, DecodeError) as e:
                log.warning("Fetching %s failed: %s", url, e)
                feeds[url] = None
        return FetchResult(now, feeds, tuple(scheduled))

    def apply(self, result, now=None):
        """Update the upcoming trains from a fetch(). Feeds that failed keep their last good data."""
        now = time.time() if now is None else now
        for url, preds in result.feeds.items():
            if preds is not None:
                self._feeds[url] = (preds, result.fetched_at)
        self._scheduled = list(result.scheduled)

        preds = [p for url in result.feeds if url in self._feeds for p in self._feeds[url][0]]
        earliest = now - OVERDUE_SECONDS
        latest = now + self.settings.max_minutes * 60
        upcoming = sorted([p for p in preds if earliest <= p.time <= latest], key=lambda p: p.time)

        self.predictions = upcoming[:self.settings.max_trains]
        self.rotation_index = 1  # Reset rotation to 2nd train

    def stale(self, now=None):
        """True if any feed for the stops' scheduled routes hasn't been fetched successfully for a while.

        Other feeds (fetched when fetch_all_feeds is on) only matter for
        reroutes, so their failures don't mark the board stale.
        """
        now = time.time() if now is None else now
        limit = STALE_REFRESHES * self.settings.refresh_seconds
        return any(url not in self._feeds or now - self._feeds[url][1] > limit for url in self._scheduled)

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

        return Board(theme=self.settings.theme, rows=tuple(rows), stale=self.stale(now))

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
