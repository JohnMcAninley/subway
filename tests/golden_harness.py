"""Golden test cases: captured live feeds plus the boards the clock should produce from them.

The case format is described in tests/golden/README.md. From the repo root:

    python tests/golden_harness.py capture [case ...]   # capture live feeds (needs data/ and network)
    python tests/golden_harness.py regenerate           # rewrite expected.json from the current code

Regenerating changes the spec, so review the expected.json diffs before committing.
"""
import dataclasses
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from google.transit import gtfs_realtime_pb2

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from subway_clock.core.clock import Clock  # noqa: E402
from subway_clock.core.feeds import ALERTS_URL, ALL_FEED_URLS, fetch_feed  # noqa: E402
from subway_clock.core.gtfs import StaticTables  # noqa: E402
from subway_clock.core.settings import Settings  # noqa: E402

GOLDEN_DIR = Path(__file__).resolve().parent / "golden"


def standard_steps(t):
    """Refresh, rotate the second line a few times, refresh again, then count down without refreshing."""
    steps = [{"action": "refresh", "now": t}, {"action": "board", "now": t}]
    for k in range(1, 5):
        steps += [{"action": "rotate", "now": t + 5 * k}, {"action": "board", "now": t + 5 * k}]
    steps += [{"action": "refresh", "now": t + 60}, {"action": "board", "now": t + 60},
              {"action": "board", "now": t + 240}]
    return steps


def failing_feed_steps(t, feed):
    """Refresh normally, then with feed failing until the board goes stale (after 90 seconds)."""
    return [{"action": "refresh", "now": t + 300}, {"action": "board", "now": t + 300},
            {"action": "refresh", "now": t + 330, "fail": [feed]}, {"action": "board", "now": t + 330},
            {"action": "refresh", "now": t + 420, "fail": [feed]}, {"action": "board", "now": t + 420}]


def more_lines_steps(t):
    """Boards for taller screens: 4 lines with the last rotating; 7, more than max_trains (5); then grouped."""
    steps = [{"action": "lines", "lines": 4}, {"action": "board", "now": t + 60}]
    for k in range(1, 4):
        steps += [{"action": "rotate", "now": t + 60 + 5 * k}, {"action": "board", "now": t + 60 + 5 * k}]
    steps += [{"action": "lines", "lines": 7}, {"action": "board", "now": t + 80},
              {"action": "rotate", "now": t + 85}, {"action": "board", "now": t + 85}]
    # A portrait screen: grouped by direction, with an even and an odd number of lines.
    steps += [{"action": "grouped", "grouped": True}, {"action": "lines", "lines": 4}, {"action": "board", "now": t + 90},
              {"action": "rotate", "now": t + 95}, {"action": "lines", "lines": 5}, {"action": "board", "now": t + 95}]
    return steps


def alerts_steps(t):
    """Refresh, rotate enough to go through the trains and alerts, then refresh with the alerts fetched again."""
    steps = [{"action": "refresh", "now": t}, {"action": "board", "now": t}]
    for k in range(1, 11):
        steps += [{"action": "rotate", "now": t + 5 * k}, {"action": "board", "now": t + 5 * k}]
    steps += [{"action": "refresh", "now": t + 120}, {"action": "board", "now": t + 120}]
    return steps


# Cases captured before alerts existed have no alerts feed.
NO_ALERTS = {"show_alerts": False}

CASES = {
    "union-sq-south": {
        "description": "14 St-Union Sq complex southbound: three feeds (4/5/6, N/Q/R/W, L) and second-line "
                       "rotation, then the N/Q/R/W feed fails until the board goes stale.",
        "settings": {"stops": ["635S", "R20S", "L03S"], **NO_ALERTS},
        "extra_steps": lambda t: failing_feed_steps(t, "gtfs-nqrw"),
    },
    "brooklyn-bridge-north": {
        "description": "Brooklyn Bridge-City Hall northbound: 6 trains starting here have only departure times.",
        "settings": {"stops": ["640N"], **NO_ALERTS},
    },
    "broad-channel": {
        "description": "Broad Channel, both directions: A trains and the Rockaway Park Shuttle (route H, SR "
                       "bullet). Northbound H trips end at H19, an unnamed stop past Broad Channel.",
        "settings": {"stops": ["H04"], **NO_ALERTS},
    },
    "jackson-hts": {
        "description": "Jackson Hts-Roosevelt Av complex, both directions: E/F/M/R and 7 across four feeds, "
                       "then on taller screens with 4 and 7 lines.",
        "settings": {"stops": ["G14", "710"], **NO_ALERTS},
        "extra_steps": more_lines_steps,
    },
    "28-st-new-short": {
        "description": "28 St (6) southbound in the new style, limited to 3 trains within 20 minutes.",
        "settings": {"stops": ["633S"], "style": "new", "max_trains": 3, "max_minutes": 20, **NO_ALERTS},
    },
    "grand-central-alerts": {
        "description": "Grand Central-42 St (4/5/6), both directions, with service alerts in the classic style.",
        "settings": {"stops": ["631"]},
        "steps": alerts_steps,
    },
    "union-sq-south-alerts-new": {
        "description": "14 St-Union Sq complex southbound in the new style, where service alerts take turns "
                       "with trains on the last line.",
        "settings": {"stops": ["635S", "R20S", "L03S"], "style": "new"},
        "steps": alerts_steps,
    },
    "kings-hwy-no-service": {
        "description": "Kings Hwy (B/Q) southbound, captured on a weekend with the Q cut short by planned "
                       "work and no B service: the board is empty.",
        "settings": {"stops": ["D35S"], **NO_ALERTS},
    },
}


def feed_name(url):
    """Short name for a feed URL, e.g. "gtfs-ace"."""
    return url.rsplit("%2F", 1)[1]


def run_case(case_dir):
    """Run a case's steps and return the boards from its "board" steps, as JSON-ready dicts."""
    case_dir = Path(case_dir)
    case = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    static = StaticTables(**json.loads((case_dir / "static.json").read_text(encoding="utf-8")))
    failing = set()

    def fetch(url):
        name = feed_name(url)
        if name in failing:
            raise requests.ConnectionError(f"{name} failing in this step")
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString((case_dir / "feeds" / f"{name}.pb").read_bytes())
        return feed

    clock = Clock(Settings(**case["settings"]), static, fetch_feed=fetch)
    boards = []
    for step in case["steps"]:
        if step["action"] == "refresh":
            failing = set(step.get("fail", []))
            clock.refresh(now=step["now"])
        elif step["action"] == "lines":
            clock.lines = step["lines"]
        elif step["action"] == "grouped":
            clock.grouped = step["grouped"]
        elif step["action"] == "rotate":
            clock.rotate(now=step["now"])
        elif step["action"] == "board":
            boards.append({"now": step["now"], **dataclasses.asdict(clock.board(now=step["now"]))})
        else:
            raise ValueError(f"Unknown action {step['action']!r}")
    return json.loads(json.dumps(boards))  # As stored: tuples become lists


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def regenerate(case_dir):
    write_json(Path(case_dir) / "expected.json", run_case(case_dir))


def capture(names):
    from subway_clock.core.gtfs import StaticData

    static = StaticData(ROOT / "data")
    captured_at = int(time.time())
    feeds = {url: fetch_feed(url) for url in ALL_FEED_URLS}
    alerts = fetch_feed(ALERTS_URL)

    for name in names:
        definition = CASES[name]
        settings = Settings(**definition["settings"])
        stops = set(settings.stops)
        case_dir = GOLDEN_DIR / name
        (case_dir / "feeds").mkdir(parents=True, exist_ok=True)

        # Keep only trips that stop at the case's stops, so the files stay small.
        trip_stops = set()
        trip_ids = set()
        for url, feed in feeds.items():
            trimmed = gtfs_realtime_pb2.FeedMessage()
            trimmed.header.CopyFrom(feed.header)
            for entity in feed.entity:
                stop_ids = [u.stop_id for u in entity.trip_update.stop_time_update]
                if any(s in stops or s[:-1] in stops for s in stop_ids):
                    trimmed.entity.add().CopyFrom(entity)
                    trip_stops.update(stop_ids)
                    trip_ids.add(entity.trip_update.trip.trip_id)
            (case_dir / "feeds" / f"{feed_name(url)}.pb").write_bytes(trimmed.SerializeToString())

        if settings.show_alerts:
            # Keep alerts for the case's stops, or for whole routes scheduled or running there.
            case_parents = {static.stop_parents.get(s, s) for s in stops}
            routes = set(static.routes_for(stops))
            for url in feeds:
                trimmed = gtfs_realtime_pb2.FeedMessage()
                trimmed.ParseFromString((case_dir / "feeds" / f"{feed_name(url)}.pb").read_bytes())
                routes.update(e.trip_update.trip.route_id for e in trimmed.entity)
            trimmed = gtfs_realtime_pb2.FeedMessage()
            trimmed.header.CopyFrom(alerts.header)
            for entity in alerts.entity:
                if any(e.stop_id in case_parents or (not e.stop_id and e.route_id in routes)
                       for e in entity.alert.informed_entity):
                    trimmed.entity.add().CopyFrom(entity)
            (case_dir / "feeds" / "subway-alerts.pb").write_bytes(trimmed.SerializeToString())

        # Only the static tables the case can look up.
        parents = {s: static.stop_parents[s] for s in stops | trip_stops if s in static.stop_parents}
        write_json(case_dir / "static.json", {
            "stop_names": {s: static.stop_names[s] for s in sorted(trip_stops) if s in static.stop_names},
            "stop_parents": dict(sorted(parents.items())),
            "stop_routes": {p: static.stop_routes[p] for p in sorted({static.stop_parents.get(s, s) for s in stops})
                            if p in static.stop_routes},
            "headsigns": {t: static.headsigns[t] for t in sorted(trip_ids) if t in static.headsigns},
            "direction_labels": direction_labels(static, stops),
            "stop_boroughs": stop_boroughs(static, stops | trip_stops),
        })

        steps = definition.get("steps", standard_steps)(captured_at)
        steps += definition.get("extra_steps", lambda t: [])(captured_at)
        write_json(case_dir / "case.json", {
            "description": definition["description"],
            "captured_at": datetime.fromtimestamp(captured_at, timezone.utc).isoformat(),
            "settings": definition["settings"],
            "steps": steps,
        })
        regenerate(case_dir)
        print(f"captured {name}: {len(trip_ids)} trips")


def direction_labels(static, stops):
    """The static direction labels for a case's stops' parents."""
    parents = sorted({static.stop_parents.get(s, s) for s in stops})
    return {p: static.direction_labels[p] for p in parents if p in static.direction_labels}


def stop_boroughs(static, stops):
    """The boroughs of the parents of stops."""
    parents = sorted({static.stop_parents.get(s, s) for s in stops})
    return {p: static.stop_boroughs[p] for p in parents if p in static.stop_boroughs}


def case_dirs():
    return sorted(p for p in GOLDEN_DIR.iterdir() if (p / "case.json").exists())


if __name__ == "__main__":
    command, *args = sys.argv[1:] or ["help"]
    if command == "capture":
        capture(args or list(CASES))
    elif command == "regenerate":
        for case_dir in case_dirs():
            regenerate(case_dir)
            print(f"regenerated {case_dir.name}")
    else:
        print(__doc__)
