"""User settings, stored as JSON so any front end (Qt, web, ESP32) can share the format."""
import dataclasses
import json
from dataclasses import dataclass, field
from pathlib import Path

# The looks of the MTA's platform clocks, each with its own layout:
#   classic: the LCD clocks with a white screen and a time and message strip
#   new: the newer clocks with a card per train, direction labels and terminals
#   led: the LED dot-matrix signs on the numbered lines
STYLES = ("classic", "new", "led")

# Which trains the last line rotates through:
#   all: every train up to max_trains, as the classic and LED clocks do
#   unique: stop once every route among them has been shown, as the newer clocks do,
#       so the next few trains come round more often
#   auto: whichever the real clocks of the chosen style do
ROTATIONS = ("auto", "all", "unique")

# Settings files from before styles called them themes.
OLD_THEMES = {"light": "classic", "dark": "new"}


@dataclass
class Settings:
    # GTFS stop IDs to show trains for. A directional ID ("633S") is one platform
    # direction; a parent ID ("633") is both directions. One stop, a whole
    # station, or several stations are all just a list of stops.
    stops: list[str] = field(default_factory=lambda: ["633S"])
    style: str = "classic"
    # Show up to max_trains trains, and only those within max_minutes.
    # TODO: calibrate both defaults against the real countdown clocks.
    max_trains: int = 5
    max_minutes: int = 30
    rotation: str = "auto"
    # Fetch every realtime feed (about 430 KB per refresh), so trains rerouted
    # onto the chosen stops always appear, even unplanned reroutes. If false,
    # fetch only the feeds for routes scheduled at the stops (including the
    # next week of planned work), which uses less data.
    fetch_all_feeds: bool = True
    # Show the MTA's service alerts for the stops and their routes (another 500 KB every 2 minutes).
    show_alerts: bool = True
    # An arriving train stays on the board until the feed stops listing it at
    # the stop, which is the nearest thing there is to "it has left", or until
    # this long after its arrival time if that comes first. The default only
    # guards against a train stuck in the feed; a clock away from the station
    # might use 30, as a train that arrived 30 seconds ago can't be caught.
    departed_seconds: int = 300
    # The feeds are republished about every 10 seconds.
    refresh_seconds: int = 10
    rotation_seconds: int = 5  # how long each train stays on the second line
    data_dir: str = "data"  # static GTFS cache; relative paths are relative to the settings file

    def __post_init__(self):
        if self.style not in STYLES:
            raise ValueError(f"style must be one of {STYLES}, not {self.style!r}")
        if self.rotation not in ROTATIONS:
            raise ValueError(f"rotation must be one of {ROTATIONS}, not {self.rotation!r}")

    @classmethod
    def load(cls, path):
        """Load settings from path, using defaults for anything missing (or everything, if the file doesn't exist)."""
        path = Path(path)
        if not path.exists():
            return cls()
        with open(path, encoding="utf-8") as f:
            values = json.load(f)
        if "stop_id" in values:  # Before multiple stops were supported
            values.setdefault("stops", [values.pop("stop_id")])
        if "theme" in values:  # Before styles
            values.setdefault("style", OLD_THEMES.get(values.pop("theme"), "classic"))
        known = {field.name for field in dataclasses.fields(cls)}
        return cls(**{k: v for k, v in values.items() if k in known})

    def save(self, path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(dataclasses.asdict(self), f, indent=4)
            f.write("\n")
