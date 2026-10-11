"""The LED style's dot-matrix font and abbreviations (ui/qml/LedFont.js), run in Qt's JavaScript engine."""
import json
import re
from pathlib import Path

import pytest

QtQml = pytest.importorskip("PySide6.QtQml")
from PySide6.QtCore import QCoreApplication  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "subway_clock" / "ui" / "qml" / "LedFont.js"
GOLDEN = Path(__file__).resolve().parent / "golden"

# The room LedRow.qml leaves for a terminal on a sign 192 dots wide, beside "1." and "00min"
DESTINATION_DOTS = 125


@pytest.fixture(scope="module")
def font():
    app = QCoreApplication.instance() or QCoreApplication([])  # the engine crashes without one
    engine = QtQml.QJSEngine()
    # ".pragma library" is QML's, not JavaScript
    result = engine.evaluate(SOURCE.read_text(encoding="utf-8").replace(".pragma library", ""), SOURCE.name)
    assert not result.isError(), result.toString()

    def call(expression):
        value = engine.evaluate(f"JSON.stringify({expression})")
        assert not value.isError(), value.toString()
        return json.loads(value.toString())

    yield call
    del engine, app


def js(text):
    return json.dumps(text)


def terminal_names():
    names = set()
    for static in GOLDEN.glob("*/static.json"):
        names.update(json.loads(static.read_text(encoding="utf-8"))["stop_names"].values())
    return sorted(names)


def test_glyphs_are_well_formed(font):
    for table, tallest in (("glyphs", 14), ("bulletGlyphs", 9), ("diamondGlyphs", 9)):
        for character, rows in font(table).items():
            assert len(rows) <= tallest, character
            assert any(rows), character
            assert all(set(row) <= {"#", "."} for row in rows), character


def test_every_character_in_a_station_name_has_a_glyph(font):
    glyphs = font("glyphs")
    assert {c for name in terminal_names() for c in name} - {" "} <= set(glyphs)


def test_width_counts_gaps_and_spaces(font):
    assert font("width('')") == 0
    assert font("width('l')") == 2
    assert font("width('ll')") == 2 + 1 + 2
    assert font("width('l l')") == 2 + 1 + 3 + 1 + 2
    assert font("width('A–B')") == font("width('A-B')")  # an en dash is drawn as a hyphen


def test_runs_cover_the_lit_dots(font):
    assert font("runs('.')") == [[0, 9, 2], [0, 10, 2]]
    assert font("runs('i.')")[-2:] == [[3, 9, 2], [3, 10, 2]]
    dots = sum(length for _, _, length in font("runs('H')"))
    assert dots == 11 * 4 + 2 * 2


@pytest.mark.parametrize("bullet", ["1", "2", "3", "4", "5", "6", "7", "A", "B", "C", "D", "E", "F", "G", "J", "L",
                                    "M", "N", "Q", "R", "S", "W", "Z", "6d", "7d", "Fd", "SF", "SR", "SIR"])
def test_bullet_has_its_route_unlit_inside(font, bullet):
    rows = font(f"bulletRows({js(bullet)})")
    assert len(rows) == 15 and all(len(row) == 15 for row in rows)
    plain = font("bulletRows('?d')" if bullet.endswith("d") else "bulletRows('?')")
    cut = [(x, y) for y in range(15) for x in range(15) if plain[y][x] == "#" and rows[y][x] == "."]
    assert len(cut) > 15
    # The route is surrounded by lit dots, or it would break the bullet's outline.
    for x, y in cut:
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            assert plain[ny][nx] == "#", (bullet, x, y)


def test_bullets_are_symmetrical_shapes(font):
    disc, diamond = font("bulletRows('?')"), font("bulletRows('?d')")
    assert [row.count("#") for row in disc] == [5, 9, 11, 13, 13, 15, 15, 15, 15, 15, 13, 13, 11, 9, 5]
    assert [row.count("#") for row in diamond] == [1, 3, 5, 7, 9, 11, 13, 15, 13, 11, 9, 7, 5, 3, 1]


def test_fit_keeps_a_name_that_fits(font):
    assert font(f"fit('Woodlawn', {DESTINATION_DOTS})") == "Woodlawn"
    assert font(f"fit('Crown Hts-Utica Av', {DESTINATION_DOTS})") == "Crown Hts-Utica Av"


def test_fit_uses_the_signs_abbreviation(font):
    assert font(f"fit('Flatbush Av-Brooklyn College', {DESTINATION_DOTS})") == "Flatbush Av-Bklyn Col"


def test_fit_shortens_only_as_much_as_needed(font):
    name = "Brooklyn Bridge-City Hall"
    assert font(f"width({js(name)})") > DESTINATION_DOTS
    assert font(f"fit({js(name)}, {DESTINATION_DOTS})") == "Bklyn Bridge-City Hall"


def test_fit_drops_a_street_type_then_the_last_part(font):
    assert font(f"fit('Far Rockaway-Mott Av', {DESTINATION_DOTS})") == "Far Rockaway-Mott"
    assert font(f"fit('Whitehall St-South Ferry', {DESTINATION_DOTS})") == "Whitehall St"
    assert font(f"fit('47-50 Sts-Rockefeller Ctr', {DESTINATION_DOTS})") == "47-50 Sts"
    assert font(f"fit('Bedford Park Blvd-Lehman College', {DESTINATION_DOTS})") == "Bedford Park Blvd"


def test_fit_cuts_short_as_a_last_resort(font):
    assert font("fit('Woodlawn', 22)") == "Woo"
    assert font("fit('Far Rockaway', 28)") == "Far"  # no dangling space
    assert font("fit('Woodlawn', 0)") == ""


def test_every_station_name_fits_without_cutting_a_word(font):
    """On a sign of the real width, every station in the golden cases' schedules fits as whole words."""
    short_forms = {short for _, short in font("shortenings")}
    for name in terminal_names():
        fitted = font(f"fit({js(name)}, {DESTINATION_DOTS})")
        assert fitted and font(f"width({js(fitted)})") <= DESTINATION_DOTS, name
        words = set(re.split(r"[ /-]", name)) | short_forms
        assert set(re.split(r"[ /-]", fitted)) <= words, (name, fitted)
