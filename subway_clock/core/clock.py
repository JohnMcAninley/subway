import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import requests
from google.protobuf.message import DecodeError

from .board import Board, Group, Message, Row, bullet_id
from .feeds import ALERTS_URL, ALL_FEED_URLS, feed_urls, fetch_feed, get_alerts, get_predictions
from .gtfs import destination, terminal
from .headline import headline

log = logging.getLogger(__name__)

# The board is marked stale once any feed it needs hasn't been fetched for this long.
STALE_SECONDS = 90

# Alerts change slowly and their feed is large, so it is fetched less often than the trains.
ALERTS_SECONDS = 120
MAX_MESSAGES = 5

# Styles that show alerts in place of the last line, in rotation with its trains.
# Each alert stays for MESSAGE_ROTATIONS rotations, as it takes longer to read than a train.
MESSAGE_LINE_STYLES = ("new",)
MESSAGE_ROTATIONS = 2

# Styles whose real clocks stop the rotation once every route among the trains has been
# shown (settings.rotation "unique"). The others always go through max_trains ("all").
UNIQUE_ROUTE_STYLES = ("new",)


@dataclass(frozen=True)
class FetchResult:
    fetched_at: float
    feeds: dict  # feed URL -> list of Predictions, or None if fetching that feed failed
    scheduled: tuple  # URLs of the feeds for routes scheduled at the stops
    alerts: list | None = None  # Alerts, or None if they weren't fetched this time or fetching failed


class Clock:
    """Upcoming trains for the chosen stops and the rotating last line, independent of any UI.

    The caller drives timing: every settings.refresh_seconds, run fetch() (which
    blocks on the network, so off the UI thread if there is one) and pass its
    result to apply(); every settings.rotation_seconds call rotate(); then draw
    board(). refresh() does fetch and apply in one step.

    The board has `lines` lines, set by the renderer to fit its screen. Lines
    1 to lines-1 show the next trains; the last line rotates through the rest
    (and, in some styles, through the service alerts).

    A renderer with room for a list, like a portrait screen, sets `grouped`
    instead: every line shows a train, split evenly between the directions
    when there is more than one, and nothing rotates.
    """

    def __init__(self, settings, static, fetch_feed=fetch_feed):
        self.settings = settings
        self.static = static
        self.fetch_feed = fetch_feed
        self.upcoming = []  # every train within max_minutes at the last fetch, soonest first
        self._lines = 2
        self.grouped = False
        self.rotation_index = 0  # position of the last line in what it rotates through
        self.alerts = []
        self._alerts_at = None  # when the alerts were last fetched successfully
        self._feeds = {}  # feed URL -> (predictions, fetched_at) from the last successful fetch
        self._scheduled = []  # feed URLs for routes scheduled at the chosen stops

    def refresh(self, now=None):
        self.apply(self.fetch(now), now)

    def fetch(self, now=None):
        """Download the feeds for the chosen stops. Safe to call from a worker thread."""
        now = time.time() if now is None else now
        stops = set(self.settings.stops)
        scheduled = feed_urls(self.static.routes_for(stops))
        urls = list(ALL_FEED_URLS if self.settings.fetch_all_feeds else scheduled)
        due = self._alerts_at is None or now - self._alerts_at >= ALERTS_SECONDS
        alerts_due = self.settings.show_alerts and due

        def fetch(url):
            try:
                return self.fetch_feed(url)
            except (requests.RequestException, DecodeError) as e:
                log.warning("Fetching %s failed: %s", url, e)
                return None

        def refresh_static():
            try:
                self.static.refresh()
            except (requests.RequestException, OSError) as e:
                log.warning("Checking for new static GTFS failed, using the cached copy: %s", e)

        # All at once: one after another, the feeds take several seconds. New
        # static GTFS, checked for meanwhile, takes effect from the next fetch.
        wanted = urls + [ALERTS_URL] * alerts_due
        with ThreadPoolExecutor(max_workers=len(wanted) + 1) as pool:
            pool.submit(refresh_static)
            fetched = dict(zip(wanted, pool.map(fetch, wanted)))

        feeds = {url: None if fetched[url] is None else get_predictions(fetched[url], stops) for url in urls}
        alerts = get_alerts(fetched[ALERTS_URL]) if fetched.get(ALERTS_URL) is not None else None
        return FetchResult(now, feeds, tuple(scheduled), alerts)

    def apply(self, result, now=None):
        """Update the upcoming trains from a fetch(). Feeds that failed keep their last good data."""
        now = time.time() if now is None else now
        for url, preds in result.feeds.items():
            if preds is not None:
                self._feeds[url] = (preds, result.fetched_at)
        self._scheduled = list(result.scheduled)
        if result.alerts is not None:
            self.alerts = result.alerts
            self._alerts_at = result.fetched_at

        preds = [p for url in result.feeds if url in self._feeds for p in self._feeds[url][0]]
        latest = now + self.settings.max_minutes * 60
        self.upcoming = sorted([p for p in preds if p.time <= latest], key=lambda p: p.time)
        self.rotation_index = 0  # Restart rotation

    @property
    def lines(self):
        return self._lines

    @lines.setter
    def lines(self, lines):
        if lines < 1:
            raise ValueError(f"lines must be at least 1, not {lines}")
        if lines != self._lines:
            self._lines = lines
            self.rotation_index = 0

    def _waiting(self, now):
        """The upcoming trains that haven't left yet: see settings.departed_seconds."""
        return [p for p in self.upcoming if p.time >= now - self.settings.departed_seconds]

    def predictions(self, now=None):
        """The trains the board can show: max_trains, or more if there are more lines than that."""
        now = time.time() if now is None else now
        trains = self._waiting(now)[:max(self.settings.max_trains, self.lines)]
        rotation = self.settings.rotation
        if rotation == "unique" or rotation == "auto" and self.settings.style in UNIQUE_ROUTE_STYLES:
            # Stop after the last train that brings a new route, but still fill the lines.
            routes = [p.route_id for p in trains]
            last_new = max((routes.index(route) for route in routes), default=0)
            trains = trains[:max(last_new + 1, self.lines)]
        return trains

    @property
    def _fixed(self):
        """How many lines always show the same train: every line but the rotating last one."""
        return max(1, self.lines - 1)

    def stale(self, now=None):
        """True if any feed for the stops' scheduled routes hasn't been fetched successfully for a while.

        Other feeds (fetched when fetch_all_feeds is on) only matter for
        reroutes, so their failures don't mark the board stale.
        """
        now = time.time() if now is None else now
        return any(url not in self._feeds or now - self._feeds[url][1] > STALE_SECONDS for url in self._scheduled)

    def messages(self, now=None):
        """The active alerts for the stops and their routes: those happening now, then planned work."""
        now = time.time() if now is None else now
        if not self.settings.show_alerts:
            return ()
        on_board = {p.route_id for p in self.predictions(now)}
        relevant = [a for a in self.alerts if a.active(now) and self._affected(a, on_board)]
        by_text = {}  # Alerts are often repeated per route
        for alert in sorted(relevant, key=lambda a: a.planned):
            by_text.setdefault(alert.text, Message(alert.text, alert.planned))
        return tuple(by_text.values())[:MAX_MESSAGES]

    def _affected(self, alert, on_board):
        """True if alert names one of the stops (in a direction shown), or a whole route that serves them.

        on_board: the routes of the trains the board can show, which may include rerouted ones
        """
        parents = self.static.stop_parents
        # (parent stop, direction) pairs shown: one for a directional stop, both for a parent stop
        shown = {(parents.get(stop, stop), d) for stop in self.settings.stops
                 for d in ("NS" if parents.get(stop, stop) == stop else stop[-1])}
        routes = set(self.static.routes_for(self.settings.stops)) | on_board
        for route, stop, direction in alert.affects:
            directions = direction or "NS"
            if stop:
                if any((parents.get(stop, stop), d) in shown for d in directions):
                    return True
            elif route in routes and any(d in directions for _, d in shown):
                return True
        return False

    def _rotation(self, now):
        """What the last line rotates through: ("train", index) and ("message", text) entries."""
        predictions = self.predictions(now)
        count = len(predictions)
        if self.lines < 2:
            return []
        arriving = count > self._fixed and predictions[self._fixed].time - now < 60
        if count > self._fixed and (count <= self.lines or arriving):
            trains = [self._fixed]  # Nothing else to show, or it is arriving and stays put
        else:
            trains = range(self._fixed, count)
        rotation = [("train", i) for i in trains]
        if self.settings.style in MESSAGE_LINE_STYLES and not arriving:
            rotation += [("message", m.text) for m in self.messages(now) for _ in range(MESSAGE_ROTATIONS)]
        return rotation

    def rotate(self, now=None):
        """Advance the last line to its next train or alert. Returns False if there is nothing to rotate."""
        now = time.time() if now is None else now
        rotation = self._rotation(now)
        if self.grouped or len(rotation) < 2:
            return False
        self.rotation_index = (self.rotation_index + 1) % len(rotation)
        return True

    def board(self, now=None):
        now = time.time() if now is None else now
        if self.grouped:
            return self._grouped_board(now)

        # The fixed lines always show the next trains.
        predictions = self.predictions(now)
        indexes = list(range(min(self._fixed, len(predictions))))

        # The last line cycles through the rest.
        message = ""
        rotation = self._rotation(now)
        if rotation:
            kind, value = rotation[self.rotation_index if self.rotation_index < len(rotation) else 0]
            if kind == "train":
                indexes.append(value)
            else:
                message = value

        rows = tuple(self._row(predictions[i], i + 1, now) for i in indexes)
        return Board(style=self.settings.style, rows=rows, stale=self.stale(now),
                     messages=self.messages(now), message=message)

    def _grouped_board(self, now):
        """Every line shows a train; with more than one direction, each gets an equal share of the lines."""
        waiting = self._waiting(now)
        by_direction = {}  # direction label -> its trains, in order of each direction's next train
        for pred in waiting:
            by_direction.setdefault(self.static.direction_label(pred.stop_id), []).append(pred)
        headings = list(by_direction)[:self.lines]

        if len(headings) < 2:
            rows = tuple(self._row(pred, i + 1, now) for i, pred in enumerate(waiting[:self.lines]))
            groups = ()
        else:
            share, extra = divmod(self.lines, len(headings))  # Spare lines go to the first directions
            groups = tuple(
                Group(heading, tuple(self._row(pred, i + 1, now) for i, pred in
                                     enumerate(by_direction[heading][:share + (g < extra)])))
                for g, heading in enumerate(headings))
            rows = tuple(row for group in groups for row in group.rows)
        return Board(style=self.settings.style, rows=rows, stale=self.stale(now),
                     messages=self.messages(now), groups=groups)

    def _row(self, pred, number, now):
        seconds = pred.time - now
        static = self.static
        name = destination(static.stop_names, static.headsigns, pred.trip_stops, pred.trip_id)
        label = static.direction_label(pred.stop_id)

        # Boroughs of the stops after this one, up to where the trip ends for riders
        last = terminal(static.stop_names, pred.trip_stops)
        stops = pred.trip_stops[:pred.trip_stops.index(last) + 1] if last else ()
        ahead = [static.borough(s) for s in stops[stops.index(pred.stop_id) + 1:]] if pred.stop_id in stops else []
        # Without the terminal's borough there is nothing to say; other gaps (unnamed stops) don't matter.
        ahead = [b for b in ahead if b] if ahead and ahead[-1] else []
        head, detail = headline(label, static.borough(pred.stop_id), ahead, name)
        return Row(
            number=number,
            route=pred.route_id,
            bullet=bullet_id(pred.route_id),
            destination=name,
            direction=label,
            headline=head,
            detail=detail,
            minutes=max(0, int(seconds / 60.0)),
            arriving=seconds < 60,
        )
