# Roadmap

What is left to do, split into packages that can be worked on separately.
`docs/references.md` records how the real clocks look and behave;
`tests/golden/README.md` is the spec for what the core produces.

Last updated 2026-10-11.

## Where things stand

- The core (`subway_clock/core`) turns the MTA's feeds into a `Board`: the
  trains for each line, the rotating last line, service alerts, per-train
  headlines, grouped boards for portrait screens. It has unit tests and
  golden cases captured from live data.
- The Qt/QML front end draws three styles: `classic`, `new` (wide and
  portrait) and `led`.
- Development is on a PC for now. The intended device, a Pi Zero 2 W, can't
  be bought at the moment; see H1.
- Settings are a JSON file; `scripts/find_station.py` finds a station's stop
  IDs by name. There is no settings screen,
  device image or update mechanism yet.

## Working in parallel

The split between the core and the renderers is what makes this possible.

- **The `Board` is the contract.** A package that adds or changes a field in
  `core/board.py`, or changes which trains appear, also updates
  `tests/golden/README.md` and regenerates the golden cases. Only one such
  package should be in flight at a time; they are marked **core** below.
- **Each style's QML is its own territory.** `Classic*.qml`, `New*.qml` and
  `Led*.qml` don't share code beyond `Styles.js` and `Messages.js`, so
  packages marked **classic**, **new** or **led** can run side by side.
- **Shared files to coordinate on:** `Main.qml`, `Styles.js`, `display.py`,
  `settings.py`, `README.md`.
- **Done means:** tests pass, the README and the references or golden spec
  are updated where behaviour changed, and UI changes were checked with
  captures at the `--dev` preset sizes (1920x600, 1920x480, 1280x720,
  608x1080, 360x1080). `scripts/capture.py` draws a golden case to a PNG
  without the live feeds.
- **Seeing QML errors:** Qt only prints QML warnings and `console.log` to
  the terminal with `QT_FORCE_STDERR_LOGGING=1` set.
- **Standing rule:** nothing personal goes to outside services. Requests use
  a plain User-Agent.

## Packages

Sizes are rough: S is an hour or two, M a day, L several days.

### A. Clock behaviour (core)

| ID | Package | Size | Notes |
|---|---|---|---|
| A1 | **Arriving trains: check against a real clock** | S | The feeds have no door or departure signal; the nearest is a train's list of stops no longer including the station. The clock now follows that, refreshing every 10 seconds (the feeds are republished about that often). Measured on 2026-10-11 (47 trains on the 1 to 6, N/Q/R/W and L): the feeds list a train for a median of 39 to 51 seconds after its arrival time, and up to 166. `departed_seconds` can drop trains sooner (30 suits a clock at home). Open: John will take the clock to a station and compare when the real one removes a train and moves line 2 up. The vehicle "stopped at" reports aren't consistent between the numbered and lettered lines, so nothing depends on them. |
| A2 | **Headline override table** | M | A hand-made table for what the borough rule gets wrong or can't know: the F at 75 Av and the 2 at Franklin Av ("Manhattan", not "Manhattan & ..."), short terminal names ("Coney Island", "Whitehall St"), the JFK plane, "via Court Square", and the H train ending at Broad Channel. Needs photos (P1) for the uncertain cases. |
| A3 | **Alerts, second pass** | M | Read the alert type so "no service" alerts can take the whole screen in the `new` style; pass the alert's title ("Delays", "Planned work") and age to the board; stop route-wide alerts for one direction showing on clocks for the other (the direction is only in the text). |
| A4 | **Calibrate `max_minutes`** | S | Compare against real clocks: how far ahead do they list trains? Needs observation (P1). |
| A5 | **Station name on the board** | S | Add the station's name (and the direction label when one direction is shown) to `Board`, for the home views in D. |

### B. Starting up and failing well

| ID | Package | Size | Notes |
|---|---|---|---|
| B1 | **Loading screen** | done | The window opens at once, and a first run fetches the schedules on the worker thread (`StaticData.prepare`). Meanwhile `clock.startup` in `display.py` tells the QML what to show (it is not part of the `Board`): a title, a lesser line and a percentage, drawn by each style as it draws a train, with the percentage where the minutes go. A start with the schedules already in `data/` shows "Loading train times", with no percentage, for the second or two until the first trains are in (`--loading-trains`); the check for newer schedules, and the indexing if there are some, runs on a thread of its own in `Clock`, so the trains don't wait for it. `scripts/capture.py --loading 42` pictures the first run. The percentage gives the downloads 60% and the indexing 40%, a guess from a PC with a fast connection; adjust once it has run on a Pi. |
| B2 | **Recover from bad downloads** | done | A zip that can't be read is deleted, so it is downloaded again; a zip is extracted beside the old copy and swapped in, with a marker (`.extracted`) saying which zip it came from, so an extraction that was cut short is redone; an unreadable `stop_routes.json` is rebuilt. A first run that can't fetch the schedules shows "No connection" (or "Can't read the schedules" if the trouble isn't the network) and tries again every 15 seconds. `scripts/capture.py --no-connection` pictures it. Not covered: losing the network later, which the stale warning already shows. |
| B3 | **Stale indicator for `led`** | S | The other styles show when data is out of date; the LED style doesn't. |

### C. Style polish (one package per style, can run side by side)

| ID | Package | Size | Notes |
|---|---|---|---|
| C1 | **led: bullets and font** | M | Hand-drawn dot patterns for each route bullet so the route is readable; a true dot-matrix font in place of Roboto Condensed; the signs' own abbreviations for long terminals ("Flatbush Av-Bklyn Col"). Close-up photos would help (P1). |
| C2 | **new: portrait alerts panel** | S | Titles, small bullets with badges, and "Updated 15 mins ago", as on the real screens. After A3. |
| C3 | **new: full-screen alert** | S | The card takes over the whole screen when service isn't running. After A3. |
| C4 | **classic: weather in the strip** | S | The real strip shows the temperature beside the time. Needs a weather source with no key and a location setting; decide whether it is worth it. |

Out of scope: the arrivals strip under street-entrance ad screens, the
paired strip-map screen, track-side arrows and the MTA logo.

### D. Home views

Layouts that make sense on someone's wall rather than in a station. On a
platform the screen doesn't need to say where it is; at home it does.

| ID | Package | Size | Notes |
|---|---|---|---|
| D1 | **Station header** | M | An option, for each existing style, to show the station's name and direction (e.g. "Union Sq – Downtown") in that style's own typography. After A5. The simplest version of a home view, and probably the right first step. |
| D2 | **A home style of its own** | M | To be designed once D1 is in use. Ideas: a station-sign header in the black-band Helvetica style with the route bullets; several stations on one screen, each under its own heading (the grouped board already does this by direction); "leave by" times that allow for the walk to the station. |

Open question for John: which of these matter. D1 is cheap and can go ahead;
D2 wants a sketch or a description first.

### E. Settings without editing JSON

| ID | Package | Size | Notes |
|---|---|---|---|
| E1 | **Station picker (core)** | done | `core/stations.py`: `StationPicker.search` narrows the station list as words are typed (each word starts a word of the name or is a route; abbreviations and ordinals understood; no spelling correction) and returns whole complexes, each stop with its routes and its directions' stop IDs and labels. `station_for` goes from a stop ID back to its station. `scripts/find_station.py` is the same search from the command line. For E2 and the phone page. Whether this is the right behaviour is to be seen in use. |
| E2 | **Keyboard settings overlay** | L | A QML overlay, opened with a key, for style, rotation, stops (using E1), and the toggles. Saves `settings.json` and applies without a restart. |
| E3 | **Apply settings live** | S | Changing the stops or the refresh interval at run time: restart timers, refetch, clear old trains. E2 depends on it. |

### F. The device

Blocked on hardware (H1) except where noted.

| ID | Package | Size | Notes |
|---|---|---|---|
| F1 | **Run on a Pi** | M | Apt PySide6 with eglfs, full screen, check frame rate. The LED style's layer and the classic ticker are the likeliest trouble. |
| F2 | **Image** | L | Pi OS Lite, a systemd service, read-only root, a watchdog. |
| F3 | **Wi-Fi setup and phone settings** | L | Provisioning for a device with no keyboard, then a settings page at `subway.local` (reusing E1). |
| F4 | **Updates** | L | From GitHub Releases, with rollback if the new version fails to start. The update check and version logic can be written and tested on a PC now. |

### G. Making the repo public

The repo on GitHub is already public. The README now starts from "clone and
run" with a picture of each style (`docs/images/`, made with
`scripts/capture.py`), and the history was checked on 2026-10-11: no keys,
addresses, local paths or personal settings in any commit, and every commit
uses the GitHub noreply address. `docs/design.md`, the original notes, is
gone: the README's `stops` setting now describes the kinds of clock it listed.
The code is under the GPL, version 3 (`LICENSE`). It may be loosened to a
permissive licence later; that stays possible as long as outside
contributions are either not taken or come with permission to relicense.

### S. Selling a prebuilt clock

Nothing here is needed for the open-source project. It is what stands between
it and a product, as read on 2026-10-11; none of it is legal advice.

| ID | Package | Size | Notes |
|---|---|---|---|
| S1 | **MTA licence for the bullets and the look** | ? | The subway route symbols are registered MTA trademarks, and the product imitates the MTA's signs. Product licences go through the MTA's agent, IMG Licensing (`MTALicensingInquiries@img.com`); the MTA charges a fee and may refuse. The Transit Museum is a division of the MTA and sells licensed products, so it is a possible partner, but the licence itself comes through IMG. |
| S2 | **Relay server for the feeds** | M | The [feed terms](https://www.mta.info/developers/terms-and-conditions) say to download the data and host it on a non-MTA server, and prohibit an app that gives the data to others directly from the MTA's servers. One person's clock fetching for itself is one thing; a product whose every unit polls the MTA every 10 seconds looks like what the clause is aimed at. A sold clock should fetch from a server of ours that fetches from the MTA. That server could also trim the feeds to a device's stops, which would help the Pi and the ESP32. Ask the MTA if in doubt. |
| S3 | **Stale data notice** | S | The terms ask that users be told when the data lags real time by more than a minute. `classic` and `new` show this; `led` doesn't until B3. |
| S4 | **Qt's LGPL on a device** | S | Ship the LGPL text and where to get Qt's source, and leave the buyer able to replace the Qt libraries. Using the Pi OS packages on a card the buyer can reach should do. Goes with F2. |

### Later

- **Web port**, checked against the golden cases as the shared spec.
- **ESP32.**

## Suggested order

1. In parallel: A5 then D1 (home header); C1. (B1, B2 and E1 are done.)
2. A2 and A4 as photos come in. A3, then C2 and C3.
3. E3, then E2.
4. S1 early if the clock is to be sold: the answer decides whether there is a
   product, and it may take a while.
5. F once there is hardware; F4's PC-testable parts can start earlier.

## Waiting on John

| ID | What | Blocks |
|---|---|---|
| H1 | **Hardware.** The Pi Zero 2 W isn't available anywhere. John has an older Pi "Model B or something like that" to dig out. Which model matters a great deal: an original Model B or B+ (single core, 512 MB) is unlikely to run Qt Quick acceptably, while a Pi 2 or 3 Model B should. Also still open: which screen, which sets the shape that gets the most polish. | F |
| P1 | **Photos**, collected over the next couple of weeks of riding: the newer clocks (especially an F at 75 Av and a 2 at Franklin Av), LED signs close up, anything showing an alert, and how far ahead the last train listed is. | A2, A4, C1 |
| D2 | **What a home view should be**, beyond naming the station. | D2 |
| S1 | **Whether to sell it**, and if so, writing to IMG Licensing or the Transit Museum. | S |
