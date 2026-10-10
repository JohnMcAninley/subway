"""User settings, stored as JSON so any front end (Qt, web, ESP32) can share the format."""
import dataclasses
import json
from dataclasses import dataclass, field
from pathlib import Path

THEMES = ("light", "dark")


@dataclass
class Settings:
    # GTFS stop IDs to show trains for. A directional ID ("633S") is one platform
    # direction; a parent ID ("633") is both directions. One stop, a whole
    # station, or several stations are all just a list of stops.
    stops: list[str] = field(default_factory=lambda: ["633S"])
    theme: str = "light"
    max_trains: int = 5  # upcoming trains to show, including the first
    refresh_seconds: int = 30
    rotation_seconds: int = 5  # how long each train stays on the second line
    data_dir: str = "data"  # static GTFS cache; relative paths are relative to the settings file

    def __post_init__(self):
        if self.theme not in THEMES:
            raise ValueError(f"theme must be one of {THEMES}, not {self.theme!r}")

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
        known = {field.name for field in dataclasses.fields(cls)}
        return cls(**{k: v for k, v in values.items() if k in known})

    def save(self, path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(dataclasses.asdict(self), f, indent=4)
            f.write("\n")
