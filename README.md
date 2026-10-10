# NYC Subway Countdown Clock

A recreation of the MTA platform countdown clocks, driven by the MTA's live
GTFS-realtime feeds.

> Prototype. Currently hardcoded to 28 St (6), southbound (`633S`).

## Setup

Requires Python 3.10+.

```sh
python -m venv venv
# Windows: venv\Scripts\activate    macOS/Linux: source venv/bin/activate
pip install -r requirements-dev.txt
```

PySide6 is pinned to 6.8.2.1 to match the version Debian (and so Raspberry Pi
OS) packages.

## Run

```sh
python -m subway_clock [--settings settings.json] [--width 1280]
```

On first run the static GTFS is downloaded into `data/` and indexed, which takes
about a minute.
It is refreshed automatically when the MTA publishes a new version.

The window is frameless and, by default, spans the primary screen's width.
Press Esc to close it.

## Settings

Settings are read from `settings.json` (or the `--settings` path). Any setting
left out uses its default, and the file is optional:

```json
{
    "stops": ["633S"],
    "theme": "light",
    "max_trains": 5,
    "max_minutes": 30,
    "fetch_all_feeds": true,
    "refresh_seconds": 30,
    "rotation_seconds": 5,
    "data_dir": "data"
}
```

- `stops`: GTFS stop IDs (listed in `data/gtfs_subway/stops.txt`). A directional ID like `633S` is one
  direction; a parent ID like `633` is both. List several for a whole station complex or nearby
  stations, e.g. Union Sq southbound is `["635S", "R20S", "L03S"]`.
- `theme`: `light` or `dark`.
- `max_trains`, `max_minutes`: show up to `max_trains` trains, and only those arriving within
  `max_minutes`. The second line rotates through trains 2 onward.
- `fetch_all_feeds`: fetch every realtime feed (about 430 KB per refresh) so rerouted trains always
  appear, including unplanned reroutes. Set to `false` to fetch only the feeds for routes
  scheduled at your stops, including the next week of planned work.
- `data_dir`: static GTFS cache. Relative paths are relative to the settings file.

## Layout

- `subway_clock/core/`: data and display logic, with no UI code. `Clock` produces a `Board` (the screen description) that renderers draw as-is.
- `subway_clock/ui/`: renderers. Currently a Qt widgets UI.
- `subway_clock/assets/`: route bullets.
- `tests/`: run with `pytest`. `tests/golden/` holds golden cases (captured live feeds and the
  boards they must produce), which double as the spec for other implementations of the core; see
  [tests/golden/README.md](tests/golden/README.md).

## Design

See [docs/design.md](docs/design.md) for display modes, display logic, and themes.

## Data sources

- Realtime: `https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs*` (no API key required)
- Static: `https://rrgtfsfeeds.s3.amazonaws.com/gtfs_subway.zip` and `gtfs_supplemented.zip`
