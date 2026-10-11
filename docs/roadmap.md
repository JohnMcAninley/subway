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
- Settings are a JSON file. There is no settings screen, loading screen,
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
  captures at the `--dev` presets (keys 1 to 5).
- **Standing rule:** nothing personal goes to outside services. Requests use
  a plain User-Agent.

## Packages

Sizes are rough: S is an hour or two, M a day, L several days.

### A. Clock behaviour (core)

| ID | Package | Size | Notes |
|---|---|---|---|
| A1 | **Drop trains that have left** | S | Arriving trains stay on the top line too long. Sampling the feeds on 2026-10-11 (4/5/6, 1/2/3, N/Q/R/W, L): a train stays in the feed for a median of 40 to 50 seconds after its arrival time, and up to 2 minutes. We also show "0 min" for the minute before, and refresh every 30 seconds. Plan: drop a train a fixed time after its arrival time, checked every time the board is drawn, and consider a shorter refresh now that one costs about 0.1 s. The vehicle "stopped at" reports aren't consistent between the numbered and lettered lines, so the rule shouldn't depend on them. |
| A2 | **Headline override table** | M | A hand-made table for what the borough rule gets wrong or can't know: the F at 75 Av and the 2 at Franklin Av ("Manhattan", not "Manhattan & ..."), short terminal names ("Coney Island", "Whitehall St"), the JFK plane, "via Court Square", and the H train ending at Broad Channel. Needs photos (P1) for the uncertain cases. |
| A3 | **Alerts, second pass** | M | Read the alert type so "no service" alerts can take the whole screen in the `new` style; pass the alert's title ("Delays", "Planned work") and age to the board; stop route-wide alerts for one direction showing on clocks for the other (the direction is only in the text). |
| A4 | **Calibrate `max_minutes`** | S | Compare against real clocks: how far ahead do they list trains? Needs observation (P1). |
| A5 | **Station name on the board** | S | Add the station's name (and the direction label when one direction is shown) to `Board`, for the home views in D. |

### B. Starting up and failing well

| ID | Package | Size | Notes |
|---|---|---|---|
| B1 | **Loading screen** | S | A first run downloads the schedules, about a minute with nothing on screen. Show progress, in every style. Needs a "loading" state from `display.py`. |
| B2 | **Recover from bad downloads** | S | A zip that fails to extract isn't retried, and a first run with no network just exits. Retry, and show a "no connection" screen instead of quitting. |
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
| E1 | **Station picker (core)** | M | Search stations by name and return stop IDs, with directions and the complex's other platforms. Used by E2 and later by the phone page. Pure Python, no UI. |
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

| ID | Package | Size | Notes |
|---|---|---|---|
| G1 | **Licence and credits** | S | Choose a licence; attribution for the bullets (public domain, Wikimedia Commons) and Roboto (Apache 2.0 or OFL, check the bundled file). John chooses the licence. |
| G2 | **README for a newcomer** | S | Start from "clone and run", with screenshots of each style. |
| G3 | **History check** | S | Look through the git history for anything that shouldn't be published before the first push. |
| G4 | **`docs/design.md`** | S | Still John's original notes. Keep, fold into the README, or drop. John decides. |

### Later

- **Web port**, checked against the golden cases as the shared spec.
- **ESP32.**

## Suggested order

1. A1, since it is a visible fault and small.
2. In parallel: A5 then D1 (home header); B1 and B2; C1; E1.
3. A2 and A4 as photos come in. A3, then C2 and C3.
4. E3, then E2.
5. G1 to G4 whenever the repo is to go public; none depend on the rest.
6. F once there is hardware; F4's PC-testable parts can start earlier.

## Waiting on John

| ID | What | Blocks |
|---|---|---|
| H1 | **Hardware.** The Pi Zero 2 W isn't available anywhere. John has an older Pi "Model B or something like that" to dig out. Which model matters a great deal: an original Model B or B+ (single core, 512 MB) is unlikely to run Qt Quick acceptably, while a Pi 2 or 3 Model B should. Also still open: which screen, which sets the shape that gets the most polish. | F |
| P1 | **Photos**, collected over the next couple of weeks of riding: the newer clocks (especially an F at 75 Av and a 2 at Franklin Av), LED signs close up, anything showing an alert, and how far ahead the last train listed is. | A2, A4, C1 |
| D2 | **What a home view should be**, beyond naming the station. | D2 |
| G1, G4 | **Licence**, and what to do with `docs/design.md`. | G |
