# Roadmap

What is left to do, split into packages that can be worked on separately.
Finished packages are taken out; what they built is described in the README,
`docs/references.md` (how the real clocks look and behave) and
`tests/golden/README.md` (the spec for what the core produces). IDs aren't
reused, so a gap in the numbering is a finished package.

Last updated 2026-10-11.

## Where things stand

- The core (`subway_clock/core`) turns the MTA's feeds into a `Board`: the
  trains for each line, the rotating last line, service alerts, per-train
  headlines, grouped boards for portrait screens, and the station's name. It
  has unit tests and golden cases captured from live data.
- The Qt/QML front end draws three styles: `classic`, `new` (wide and
  portrait) and `led`, each with a loading screen and an optional station
  header.
- Development is on a PC for now. The intended device, a Pi Zero 2 W, can't
  be bought at the moment; see H1.
- Settings are a JSON file, read again whenever it is saved, so changes take
  effect without a restart; `scripts/find_station.py` finds a station's stop
  IDs by name. There is no settings screen, device image or update mechanism
  yet.

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
  are updated where behaviour changed, UI changes were checked with captures
  at the `--dev` preset sizes (1920x600, 1920x480, 1280x720, 608x1080,
  360x1080), and the package is taken out of this file. `scripts/capture.py`
  draws a golden case to a PNG without the live feeds.
- **Seeing QML errors:** Qt only prints QML warnings and `console.log` to
  the terminal with `QT_FORCE_STDERR_LOGGING=1` set.
- **Standing rules:** nothing personal goes to outside services or into the
  repo, and requests use a plain User-Agent. The code is under the GPL,
  version 3; it may be loosened to a permissive licence later, which stays
  possible as long as outside contributions are either not taken or come
  with permission to relicense.

## Packages

Sizes are rough: S is an hour or two, M a day, L several days.

### A. Clock behaviour (core)

| ID | Package | Size | Notes |
|---|---|---|---|
| A1 | **Arriving trains: check against a real clock** | S | The clock drops a train when the feeds stop listing it at the stop; see "When a train has left" in `docs/references.md` for what was measured. Open: compare with a real clock at a station (H2), and change the rule or the default `departed_seconds` if they disagree. |
| A2 | **Headline override table** | M | A hand-made table for what the borough rule gets wrong or can't know: the F at 75 Av and the 2 at Franklin Av ("Manhattan", not "Manhattan & ..."), short terminal names ("Coney Island", "Whitehall St"), the JFK plane, "via Court Square", and the H train ending at Broad Channel. Needs photos (P1) for the uncertain cases. |
| A4 | **Calibrate `max_minutes`** | S | Compare against real clocks: how far ahead do they list trains? Needs observation (P1). |

### B. Starting up and failing well

| ID | Package | Size | Notes |
|---|---|---|---|
| B3 | **Stale indicator for `led`** | S | The other styles show when data is out of date; the LED style doesn't. |

### C. Style polish (one package per style, can run side by side)

| ID | Package | Size | Notes |
|---|---|---|---|
| C1 | **led: check the font and bullets against photos** | S | `LedFont.js` was drawn from measurements, without a close-up. Once photos come in (P1): the letter shapes, the size of the bullets (the 6 and the Q are hard to read on a small screen), the express diamond, and what the signs show for long terminals other than "Flatbush Av-Bklyn Col" (e.g. Van Cortlandt Park-242 St, which we show as "Van Cortlandt Park"). |
| C2 | **new: portrait alerts panel** | S | Titles, small bullets with badges, and "Updated 15 mins ago", as on the real screens. The board's messages already carry `title` and `updated_minutes`; nothing draws them yet. |
| C3 | **new: full-screen alert** | S | The card takes over the whole screen when service isn't running: a message with `no_service` set, which nothing draws yet. |
| C4 | **classic: weather in the strip** | S | The real strip shows the temperature beside the time. Needs a weather source with no key and a location setting; decide whether it is worth it. |

Out of scope: the arrivals strip under street-entrance ad screens, the
paired strip-map screen, track-side arrows and the MTA logo.

### D. Home views

Layouts that make sense on someone's wall rather than in a station. The
first step, the `show_station` header, is in.

| ID | Package | Size | Notes |
|---|---|---|---|
| D2 | **A home style of its own** | M | Wants a sketch or a description from John first (H3). Ideas: a station-sign header in the black-band Helvetica style with the route bullets; several stations on one screen, each under its own heading (the grouped board already does this by direction); "leave by" times that allow for the walk to the station. |

### E. Settings without editing JSON

| ID | Package | Size | Notes |
|---|---|---|---|
| E2 | **Keyboard settings overlay** | L | A QML overlay, opened with a key, for style, rotation, stops, and the toggles. Saves `settings.json` and applies without a restart. The pieces are there: `StationPicker.search` in `core/stations.py` narrows the station list as words are typed, and `Display.apply_settings` puts new settings into effect (all but `data_dir`). Whether the picker's matching is right is to be seen in use here. |

### F. The device

Blocked on hardware (H1) except where noted.

| ID | Package | Size | Notes |
|---|---|---|---|
| F1 | **Run on a Pi** | M | Apt PySide6 with eglfs, full screen, check frame rate. The LED style's layer and the classic ticker are the likeliest trouble. Also adjust the loading screen's percentage (`DOWNLOADS_SHARE` in `core/gtfs.py`), which gives the downloads 60% and the indexing 40%: a guess from a PC with a fast connection. |
| F2 | **Image** | L | Pi OS Lite, a systemd service, read-only root, a watchdog. |
| F3 | **Wi-Fi setup and phone settings** | L | Provisioning for a device with no keyboard, then a settings page at `subway.local` (reusing `core/stations.py`). |
| F4 | **Updates** | L | From GitHub Releases, with rollback if the new version fails to start. The update check and version logic can be written and tested on a PC now. |

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

1. C2, C3 and B3: small, and nothing blocks them.
2. E2.
3. A1, A2, A4 and C1 as photos and station visits come in.
4. S1 early if the clock is to be sold: the answer decides whether there is a
   product, and it may take a while.
5. F once there is hardware; F4's PC-testable parts can start earlier.

## Waiting on John

| ID | What | Blocks |
|---|---|---|
| H1 | **Hardware.** The Pi Zero 2 W isn't available anywhere. John has an older Pi "Model B or something like that" to dig out. Which model matters a great deal: an original Model B or B+ (single core, 512 MB) is unlikely to run Qt Quick acceptably, while a Pi 2 or 3 Model B should. Also still open: which screen, which sets the shape that gets the most polish. | F |
| H2 | **A station visit with the clock running**, to compare when the real clock removes an arriving train and moves line 2 up. | A1 |
| H3 | **What a home view should be**, beyond naming the station. | D2 |
| H4 | **The header's direction at Union Sq downtown.** It is left empty, because the L's platform is labelled "Brooklyn" and the others "Downtown & Brooklyn". Should it pick one instead (the commonest, or the first stop's)? | |
| P1 | **Photos**, collected over the next couple of weeks of riding: the newer clocks (especially an F at 75 Av and a 2 at Franklin Av), LED signs close up (a line near enough to count the dots, a bullet, an express diamond if one turns up, and long terminals such as Van Cortlandt Park-242 St and Brooklyn Bridge-City Hall), anything showing an alert, and how far ahead the last train listed is. | A2, A4, C1 |
| S1 | **Whether to sell it**, and if so, writing to IMG Licensing or the Transit Museum. | S |
