# NYC Subway Countdown Clock

A recreation of the MTA platform countdown clocks, driven by the MTA's live
GTFS-realtime feeds.

It draws three of the MTA's clocks, for any station or group of stations:

| `classic` | `new` |
|---|---|
| ![The classic style: two numbered lines and a time strip](docs/images/classic.png) | ![The new style: a card for each train](docs/images/new.png) |
| **`led`** | **`new`, on a portrait screen** |
| ![The LED style: green dot-matrix text](docs/images/led.png) | <img src="docs/images/new-portrait.png" alt="The new style in portrait: trains above service alerts" width="300"> |

It runs on a PC today. The aim is a small screen driven by a Raspberry Pi; see
the [roadmap](docs/roadmap.md) for what is left.

## Quick start

Requires Python 3.10+ and git.

```sh
git clone https://github.com/JohnMcAninley/subway.git
cd subway
python -m venv venv
# Windows: venv\Scripts\activate    macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
python -m subway_clock --dev
```

The first run downloads the MTA's schedules into `data/` and indexes them,
which takes about a minute with nothing on screen. After that a window opens
showing downtown 6 trains at 28 St. Press S to switch styles, 1-5 to try
screen shapes, and Esc to quit.

To show your own station, make a `settings.json` in the directory you run
from, with the stop IDs from `data/gtfs_subway/stops.txt`:

```json
{
    "stops": ["635S", "R20S", "L03S"],
    "style": "new"
}
```

That is Union Sq, downtown: the 4/5/6, the N/Q/R/W and the L. See
[Settings](#settings) for the rest. No API key or account is needed.

## Run

```sh
python -m subway_clock [--settings settings.json] [--dev | --fullscreen | --size 1920x600 | --width 1920]
```

The schedules in `data/` are refreshed automatically when the MTA publishes a
new version.

By default the window is frameless at the top left of the screen, the screen's
width at a 3.2:1 ratio. `--fullscreen` is for the device. Press Esc to quit.

`--dev` opens a normal, resizable window for working on the display:

- The QML in `subway_clock/ui/qml/` reloads whenever a file there is saved.
- Keys 1-5 resize the window to preview screen shapes: 3.2:1, 4:1, 16:9, 9:16 (like the
  screens in station entrances), and 1:3.
- S switches between the styles.

## Settings

Settings are read from `settings.json` (or the `--settings` path). Any setting
left out uses its default, and the file is optional:

```json
{
    "stops": ["633S"],
    "style": "classic",
    "max_trains": 5,
    "max_minutes": 30,
    "rotation": "auto",
    "fetch_all_feeds": true,
    "show_alerts": true,
    "departed_seconds": 300,
    "refresh_seconds": 10,
    "rotation_seconds": 5,
    "data_dir": "data"
}
```

- `stops`: GTFS stop IDs (listed in `data/gtfs_subway/stops.txt`). What you list decides what kind
  of clock it is:
  - One direction at one stop, like the clock over a side platform: a directional ID,
    `["633S"]`.
  - Both directions, like the clock on an island platform: a parent ID, `["633"]`.
  - A whole station complex: the IDs of each of its platforms, e.g. Union Sq downtown is
    `["635S", "R20S", "L03S"]`.
  - Several stations at once, which no real clock does: the stops nearest a home or office,
    e.g. `["633S", "R18S"]` for downtown trains from either 28 St station.
- `style`: which MTA clock to look like. `classic` is the LCD clocks with a white screen and a
  time strip; `new` is the newer clocks with a card per train, headed by its direction
  (e.g. "Downtown & Brooklyn") over the destination. In portrait it becomes the screens in station
  entrances: the time, trains under a heading for each direction, and service alerts at the bottom.
  `led` is the LED dot-matrix signs on the numbered lines: green text, an amber line for an
  arriving train, and no alerts.
- `max_trains`, `max_minutes`: show up to `max_trains` trains, and only those arriving within
  `max_minutes`. The board fits as many lines as the screen's shape allows (2 on a wide bar, 4 at
  16:9, up to 10 in portrait); the last line rotates through the trains that don't fit. A screen
  with more lines than `max_trains` shows more trains.
- `departed_seconds`: an arriving train stays at "0 min" until the feed stops listing it at the
  stop (the nearest thing the data has to "it has left"), or until this long after its arrival
  time if that comes first. The default of 300 just guards against a train stuck in the feed.
  Away from the station, 30 makes room for the next train sooner.
- `refresh_seconds`: how often to fetch the feeds. The MTA republishes them about every 10
  seconds.
- `rotation`: which trains the last line rotates through. `all` is every train up to
  `max_trains`, as the classic and LED clocks do. `unique` stops once every route among them has
  been shown, as the newer clocks do, so the next few trains come round more often. `auto` (the
  default) does whichever the real clocks of the chosen `style` do.
- `fetch_all_feeds`: fetch every realtime feed (about 430 KB per refresh) so rerouted trains always
  appear, including unplanned reroutes. Set to `false` to fetch only the feeds for routes
  scheduled at your stops, including the next week of planned work.
- `show_alerts`: show the MTA's service alerts for your stops and their routes. The classic style
  scrolls them along the bottom strip; the new style shows them in turn with the trains on the
  last line.
- `data_dir`: static GTFS cache. Relative paths are relative to the settings file.

## Development

```sh
pip install -r requirements-dev.txt
pytest
```

PySide6 is pinned to 6.8.2.1 to match the version Debian (and so Raspberry Pi
OS) packages.

`scripts/capture.py` draws a golden case to a PNG, in any style and size,
without the live feeds; the pictures above were made with it. Qt only prints
QML warnings to the terminal with `QT_FORCE_STDERR_LOGGING=1` set.

## Layout

- `subway_clock/core/`: data and display logic, with no UI code. `Clock` produces a `Board` (the screen description) that renderers draw as-is.
- `subway_clock/ui/`: the Qt Quick front end. `display.py` runs the clock's timers and passes the
  `Board` to `qml/Main.qml`, which only draws it.
- `subway_clock/assets/`: route bullets, the Roboto font, and the direction labels
  and boroughs (`stations.json`, regenerated by `scripts/update_stations.py`).
- `tests/`: run with `pytest`. `tests/golden/` holds golden cases (captured live feeds and the
  boards they must produce), which double as the spec for other implementations of the core; see
  [tests/golden/README.md](tests/golden/README.md).

## Design

[docs/references.md](docs/references.md) records how the real clocks look and behave, and where
each fact comes from. [tests/golden/README.md](tests/golden/README.md) is the spec for which
trains the board shows and when.

## Data sources

- Realtime: `https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs*` (no API key required)
- Alerts: `https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/camsys%2Fsubway-alerts`
- Static: `https://rrgtfsfeeds.s3.amazonaws.com/gtfs_subway.zip` and `gtfs_supplemented.zip`
- Direction labels: the MTA's station list, `http://web.mta.info/developers/data/nyct/subway/Stations.csv`

The feeds are used under the MTA's
[terms for its data feeds](https://www.mta.info/developers/terms-and-conditions). This project
isn't affiliated with, licensed by or endorsed by the MTA, and the times it shows may not be
accurate, complete or timely.

## Licence

Copyright John McAninley. Licensed under the GNU General Public License, version 3; see
[LICENSE](LICENSE). The bundled bullets and font keep their own terms, below.

## Credits

- Route bullets are the public domain `NYCS-bull-trans-*.svg` files on
  [Wikimedia Commons](https://commons.wikimedia.org/wiki/Category:New_York_City_Subway_bullets),
  by Flamurai and others. The bullets are MTA trademarks.
- [Roboto](https://github.com/googlefonts/roboto-classic) is licensed under the SIL Open Font License
  (`subway_clock/assets/fonts/OFL.txt`).
- The new style follows Adam Fisher-Cox's
  [write-up of its design](https://www.adamfishercox.com/portfolio/mta-platform-screens/).
- The styles are based on photos of the MTA's platform countdown clocks on Wikimedia
  Commons by Ytx21cn, Tdorante10, and others (CC BY-SA 4.0).
