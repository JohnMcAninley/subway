"""The screen description: everything a renderer needs to draw the clock, and nothing else.

Renderers draw a Board as-is. All decisions about which trains appear where
are made in the core, so every front end shows the same thing.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Row:
    number: int  # 1-based position in the upcoming train list
    route: str  # GTFS route_id, e.g. "6X"
    bullet: str  # bullet asset id, e.g. "6d" for the 6 express diamond
    destination: str
    minutes: int
    arriving: bool


@dataclass(frozen=True)
class Board:
    theme: str
    rows: tuple[Row, ...]


def bullet_id(route_id):
    """Express routes end in X in the feed; their diamond bullets end in d."""
    return route_id.upper().replace("X", "d")
