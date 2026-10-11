# Golden test cases

Each folder here is a test case built from real MTA data: captured realtime
feeds, the static tables they need, a script of steps, and the boards (screen
descriptions) the clock must produce. Every implementation of the clock core
(Python now; web or ESP32 later) should reproduce `expected.json` exactly from
the other files.

## Files

```
<case>/
  case.json      description, settings, and the steps to run
  static.json    static GTFS tables for this case
  feeds/*.pb     captured GTFS-realtime feeds (protobuf), one per MTA feed
  expected.json  the board at each "board" step
```

### case.json

```json
{
  "description": "...",
  "captured_at": "2026-10-10T20:47:17+00:00",
  "settings": {"stops": ["635S", "R20S", "L03S"]},
  "steps": [
    {"action": "refresh", "now": 1791668837},
    {"action": "board", "now": 1791668837},
    {"action": "rotate", "now": 1791668842},
    {"action": "refresh", "now": 1791669167, "fail": ["gtfs-nqrw"]}
  ]
}
```

`settings` uses the same keys as `settings.json`, with the same defaults for
anything left out. `now` is POSIX seconds. Steps run in order:

- `refresh`: fetch and apply the feeds the settings call for. A feed's data is
  `feeds/<name>.pb`, where the name is the end of its URL (`gtfs`, `gtfs-ace`,
  `gtfs-bdfm`, `gtfs-g`, `gtfs-jz`, `gtfs-l`, `gtfs-nqrw`, `gtfs-si`). Feeds
  listed in `fail` fail to fetch for this step.
- `lines`: set how many lines the board has (`"lines": 4`). Cases start with 2.
- `rotate`: advance the last line.
- `board`: record the board at `now`.

### static.json

Only the entries the case can look up:

- `stop_names`: stop ID (parent or directional) to name
- `stop_parents`: stop ID to parent stop ID
- `stop_routes`: parent stop ID to the sorted routes scheduled there
- `headsigns`: realtime trip ID to scheduled headsign
- `direction_labels`: parent stop ID to its direction labels, e.g.
  `{"N": "Uptown", "S": "Downtown"}`. Either direction may be missing.

### feeds/*.pb

Real feeds trimmed to the trips that stop at the case's stops. Headers and
the MTA's NYCT extension fields are kept as captured.

### expected.json

One entry per `board` step:

```json
{
  "now": 1791668837,
  "style": "classic",
  "rows": [
    {"number": 1, "route": "6", "bullet": "6", "destination": "Brooklyn Bridge-City Hall",
     "direction": "Downtown", "minutes": 0, "arriving": true}
  ],
  "stale": false
}
```

## Rules

What the cases test, for anyone implementing the core:

**Which trains**
- A stop time matches a settings stop if its stop ID equals it, or equals it
  without the final `N`/`S` (so a parent stop matches both directions).
- Its time is the arrival time, or the departure time if there is no arrival
  (usual at a trip's first stop). Stop times with neither are ignored.
- Feeds fetched: all of them if `fetch_all_feeds` (the default), otherwise
  the feeds carrying the routes in `stop_routes` for the stops' parents.
  Feeds are processed in sorted URL order.
- Keep trains with `now - 300 <= time <= now + max_minutes * 60`, sorted by
  time (ties keep feed order, then entity order within a feed). This happens
  on `refresh`, with that step's `now`.
- The board shows the first `max(max_trains, lines)` of those: `max_trains`,
  or more if the screen has more lines than that.

**Rows**
- `minutes` is `floor((time - now) / 60)`, but never below 0. `arriving` is
  `time - now < 60`.
- `destination` is the name of the last stop in the trip's stop time updates
  that has a name in `stop_names`, else the trip's headsign, else `Unknown`.
- `bullet`: `GS` is `S`, `FS` is `SF`, `H` is `SR`, `SI` is `SIR`; otherwise
  routes ending in `X` (express) end in `d` instead (`6X` is `6d`); otherwise
  the route ID.
- `direction` is `direction_labels[parent][d]`, where `d` is the last
  character of the matched stop time's stop ID (`N` or `S`) and `parent` is
  that stop ID without it; or `""` if there is no such label.
- `number` is the train's 1-based position in the kept list.

**The lines**

With `lines` = L and n trains shown:
- Lines 1 to L-1 always show trains 1 to L-1 (as many as there are).
- Line L shows train L, unless there are more than L trains and train L
  isn't arriving, in which case `rotate` advances it through trains L to n
  and back to L. `refresh`, and a `lines` step that changes L, reset it to train L. If train L is
  arriving, line L shows train L and `rotate` does nothing.
- With L = 1, the board shows train 1 only, and `rotate` does nothing.

**Failures and staleness**
- A feed that fails keeps its trains from its last successful fetch.
- The board is `stale` if any feed for the stops' scheduled routes has never
  been fetched, or was last fetched more than `3 * refresh_seconds` before
  `now`.

## Capturing and regenerating

From the repo root:

```sh
python tests/golden_harness.py capture [case ...]   # needs the static GTFS in data/ and a network
python tests/golden_harness.py regenerate           # rewrite every expected.json from the current code
```

Cases are defined in `CASES` in `tests/golden_harness.py`. Captured feeds are
a moment in time, so recapturing changes a case's trains entirely.

Regenerating changes the spec. Do it only for an intended change, and review
the `expected.json` diffs before committing.
