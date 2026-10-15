"""Put together the page with the JavaScript core as plain files, for any static host.

From the repo root:

    python scripts/build_site.py [build/site] [--schedules data] [--proxy https://example.com/?url=]

The folder holds standalone.html as index.html, the page's scripts, styles and
core (subway_clock/web/static), the QML's libraries as the server would hand
them over, the assets, and core/feeds.json. Serve it from anywhere, e.g.
`python -m http.server -d build/site`.

--schedules builds the schedule tables from the MTA's zips, kept in the folder
given (fetched if they have changed), and writes them beside the page as
schedules.json, which the page reads instead of the zips: no proxy, and a
download of under a megabyte rather than 25 (see .github/workflows/pages.yml,
which does this every hour). Without it, the page has only the proxy.

--proxy writes config.json with the CORS proxy the page fetches the schedules
through by default, or if schedules.json can't be had; each browser can still be given another with ?proxy= (see
standalone.js). The folder is public once it is hosted, so a proxy with a key
of yours in it belongs in ?proxy= rather than here.
"""
import argparse
import json
import logging
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from subway_clock.core.gtfs import StaticData  # noqa: E402
from subway_clock.web.server import ASSETS_DIR, FEEDS_PATH, LIBRARIES, STATIC_DIR, library  # noqa: E402

SCHEDULES = "schedules.json"


def schedules(tables, built=None):
    """schedules.json for a core/gtfs.StaticTables: the tables the zips come to, and when they were built.

    The station list's tables aren't in it, as the page has that list already.
    """
    built = built or datetime.now(timezone.utc)
    return {"built": built.isoformat(timespec="seconds"), "stop_names": tables.stop_names,
            "stop_parents": tables.stop_parents, "stop_routes": tables.stop_routes, "headsigns": tables.headsigns}


def build(site, proxy="", tables=None):
    """Write the site to the folder site. tables, if given, are published as schedules.json."""
    site = Path(site)
    shutil.rmtree(site, ignore_errors=True)
    # The server's own page asks it for the board, which a static host has no answer to.
    shutil.copytree(STATIC_DIR, site, ignore=shutil.ignore_patterns("index.html", "main.js"))
    (site / "standalone.html").rename(site / "index.html")
    (site / "qml").mkdir()
    for name in LIBRARIES:
        (site / "qml" / f"{name}.js").write_text(library(name), encoding="utf-8", newline="\n")
    shutil.copytree(ASSETS_DIR, site / "assets")
    shutil.copy(FEEDS_PATH, site / "core" / "feeds.json")
    config = {}
    if tables is not None:
        (site / SCHEDULES).write_text(json.dumps(schedules(tables), separators=(",", ":")), encoding="utf-8")
        config["schedules"] = SCHEDULES
    if proxy:
        config["proxy"] = proxy
    if config:
        (site / "config.json").write_text(json.dumps(config) + "\n", encoding="utf-8", newline="\n")
    # GitHub Pages leaves out files and folders starting with _ unless told not to.
    (site / ".nojekyll").touch()


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("site", nargs="?", type=Path, default=ROOT / "build" / "site",
                        help="the folder to write (default: build/site); anything in it is replaced")
    parser.add_argument("--schedules", type=Path, metavar="DIR",
                        help="build schedules.json from the MTA's schedule zips, kept in DIR")
    parser.add_argument("--proxy", default="", help="the CORS proxy for the schedules: the start of an address that "
                        "the schedule zip's address is added to, or one with {url} where it goes")
    args = parser.parse_args()
    tables = None
    if args.schedules:
        logging.basicConfig(level=logging.INFO, format="%(message)s")
        tables = StaticData(args.schedules)
        if tables.ready:
            tables.refresh()  # The copy kept is checked against the MTA's on the first refresh
        else:
            tables.prepare()
    build(args.site, args.proxy, tables)
    print(f"Built {args.site}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
