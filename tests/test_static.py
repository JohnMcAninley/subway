from pathlib import Path

from subway_clock.core.board import bullet_id
from subway_clock.core.feeds import ROUTE_FEEDS, feed_urls
from subway_clock.core.gtfs import build_stop_routes, load_direction_labels

# route_id column of routes.txt in the MTA subway GTFS
ALL_ROUTES = "A C E B D F FX M G J Z L N Q R W GS FS H 1 2 3 4 5 6 6X 7 7X SI".split()

BULLETS_DIR = Path(__file__).resolve().parent.parent / "subway_clock" / "assets" / "bullets"


def test_every_route_has_a_bullet():
    missing = [route for route in ALL_ROUTES
               if not (BULLETS_DIR / f"NYCS-bull-trans-{bullet_id(route)}.svg").exists()]
    assert missing == []


def test_every_route_has_a_feed():
    assert sorted(ROUTE_FEEDS) == sorted(ALL_ROUTES)


def test_feed_urls_deduplicated_and_unknown_routes_ignored():
    assert feed_urls(["N", "Q", "R", "nope"]) == [ROUTE_FEEDS["N"]]


def test_build_stop_routes_groups_by_parent_across_schedules(tmp_path):
    base, supplemented = tmp_path / "base", tmp_path / "supplemented"
    for gtfs_dir, rows in [(base, [("t1", "6", "633S"), ("t2", "6X", "633N")]),
                           (supplemented, [("t3", "4", "633S"), ("t4", "4", "631S")])]:
        gtfs_dir.mkdir()
        (gtfs_dir / "trips.txt").write_text(
            "route_id,trip_id\n" + "".join(f"{route},{trip}\n" for trip, route, _ in rows))
        (gtfs_dir / "stop_times.txt").write_text(
            "trip_id,stop_id\n" + "".join(f"{trip},{stop}\n" for trip, _, stop in rows))
    parents = {"633S": "633", "633N": "633", "631S": "631"}

    assert build_stop_routes([base, supplemented], parents) == {"633": ["4", "6", "6X"], "631": ["4"]}


def test_bundled_direction_labels():
    labels = load_direction_labels()
    assert labels["633"] == {"N": "Uptown", "S": "Downtown"}
    assert labels["A02"] == {"S": "Downtown"}  # Inwood: "Last Stop" northbound isn't a label
