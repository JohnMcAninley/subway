# NYC Subway Countdown Clock

A recreation of the MTA platform countdown clocks, driven by the MTA's live
GTFS-realtime feeds.

> Prototype. Currently hardcoded to 28 St (6), southbound (`633S`).

## Setup

Requires Python 3.10+.

```sh
python -m venv venv
# Windows: venv\Scripts\activate    macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
```

Download the static subway GTFS into `gtfs/` (not yet automated):

```sh
curl -L -o gtfs_subway.zip https://rrgtfsfeeds.s3.amazonaws.com/gtfs_subway.zip
unzip gtfs_subway.zip -d gtfs
```

The supplemented GTFS (`gtfs-supplemented/`) is downloaded automatically on
startup and refreshed when the MTA publishes a new version.

## Run

```sh
python subway.py
```

The window is frameless and spans the primary screen's width; close it with
Alt+F4 (Windows/Linux).

## Design

See [docs/design.md](docs/design.md) for display modes, display logic, and themes.

## Data sources

- Realtime: `https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs*` (no API key required)
- Static: `https://rrgtfsfeeds.s3.amazonaws.com/gtfs_subway.zip` and `gtfs_supplemented.zip`
