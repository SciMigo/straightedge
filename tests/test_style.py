"""The style layer's job is to change nothing until it is asked to.

Two properties matter here and they pull in opposite directions. A theme has to
be *swappable*, or the module is pointless; and :data:`DATAFLOW` has to be
*exactly* what the three dataflow examples drew by hand before they were ported,
or the port silently restyled three published videos. The first half of this
file pins the second property, hex by hex, against the literals recovered from
the pre-port scenes.
"""

from __future__ import annotations

import re

import pytest

from straightedge.errors import RequestError
from straightedge.style import (
    DATAFLOW, PAPER, TEXTBOOK, THEME_NAMES, THEMES, Opacities, Sizes, Style,
    Widths, theme,
)

HEX = re.compile(r"^#[0-9a-fA-F]{6}$")

#: The colours the dataflow examples defined by hand, before the style layer
#: existed. Recovered from git history (e4b674e and earlier) and frozen here:
#: this table *is* the promise that porting them changed no pixel.
PRE_PORT_DATAFLOW = {
    "ink": "#0d1117",
    "flow": "#4aa8ff",     # ACT / FWD / OWNED
    "hold": "#f2b45b",     # WEIGHT / BWD / MOVING
    "done": "#4CAF50",     # PSUM / GOOD / DONE
    "warn": "#E5533D",     # HOT / MEM / COST
    "dim": "#5a6885",      # DIM, in all three
    "deep": "#2c5c86",     # PARTIAL, in ring_allreduce
    "inert": "#1c2534",    # IDLE, in pipeline_schedules
}

COLOUR_TOKENS = (
    "ink", "well", "inert", "rule", "fg", "muted", "dim", "on_fill",
    "flow", "hold", "deep", "done", "warn", "aux", "warm",
)


def _luminance(hex_colour: str) -> float:
    """Rough perceptual lightness in [0, 1]. Enough to tell light from dark."""
    r, g, b = (int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


# --- the identity guarantee -------------------------------------------------


@pytest.mark.parametrize("token,expected", sorted(PRE_PORT_DATAFLOW.items()))
def test_dataflow_matches_the_hand_written_palette(token, expected):
    """The ported scenes must render identically, which means exact hexes."""
    assert getattr(DATAFLOW, token) == expected, (
        f"DATAFLOW.{token} drifted from the value the examples shipped with; "
        f"changing it restyles the published dataflow videos"
    )


def test_textbook_matches_manims_defaults():
    """TEXTBOOK is pinned to Manim's constants, so templates.py can adopt it.

    Skipped without the render extra: the whole point of keeping
    :mod:`straightedge.style` Manim-free is that the package imports without it.
    """
    colour = pytest.importorskip("manim.utils.color")
    for token, constant in (("well", "BLACK"), ("rule", "GREY_D"),
                            ("fg", "WHITE"), ("muted", "GREY_B"),
                            ("dim", "GREY"), ("on_fill", "BLACK"),
                            ("flow", "BLUE"), ("hold", "YELLOW"),
                            ("done", "GREEN"), ("warn", "RED"),
                            ("aux", "GREEN_B"), ("warm", "ORANGE")):
        manim_hex = getattr(colour, constant).to_hex()
        assert getattr(TEXTBOOK, token).upper() == manim_hex.upper(), (
            f"TEXTBOOK.{token} should be Manim's {constant}"
        )


def test_style_module_does_not_import_manim():
    """The core stays importable without the render extra."""
    import straightedge.style as mod
    source = open(mod.__file__, encoding="utf-8").read()
    assert "import manim" not in source
    assert "from manim" not in source


# --- every theme is complete and usable -------------------------------------


@pytest.mark.parametrize("style", sorted(THEMES.values(), key=lambda s: s.name))
def test_every_colour_token_is_a_hex_string(style):
    for token in COLOUR_TOKENS:
        value = getattr(style, token)
        assert HEX.match(value), f"{style.name}.{token} is not a hex colour: {value!r}"


@pytest.mark.parametrize("style", sorted(THEMES.values(), key=lambda s: s.name))
def test_text_reads_against_its_background(style):
    """Primary text and the background must not be near-identical.

    A cheap check, but it is the failure a new theme actually makes: pick a
    light ``ink`` and forget that ``fg`` is still white.
    """
    assert abs(_luminance(style.fg) - _luminance(style.ink)) > 0.4, (
        f"{style.name}: fg on ink is unreadable"
    )


@pytest.mark.parametrize("style", sorted(THEMES.values(), key=lambda s: s.name))
def test_the_four_accents_are_distinct(style):
    """A legend with two identical swatches explains nothing."""
    assert len(set(style.accents)) == 4, f"{style.name} has duplicate accents"


@pytest.mark.parametrize("style", sorted(THEMES.values(), key=lambda s: s.name))
def test_on_fill_reads_against_every_accent(style):
    """Text on a filled accent has to survive all four accents, not just one."""
    for accent in style.accents:
        assert abs(_luminance(style.on_fill) - _luminance(accent)) > 0.2, (
            f"{style.name}: on_fill is invisible on {accent}"
        )


def test_paper_is_light_and_the_others_are_dark():
    assert _luminance(PAPER.ink) > 0.8
    assert _luminance(DATAFLOW.ink) < 0.2
    assert _luminance(TEXTBOOK.ink) < 0.2


def test_paper_moves_its_opacities():
    """A light theme that reuses dark fills is the mistake this token exists for."""
    assert PAPER.opacity != Opacities(), "PAPER should not use the dark defaults"
    assert PAPER.opacity.solid < DATAFLOW.opacity.solid


# --- the scale --------------------------------------------------------------


def test_the_type_scale_descends():
    sizes = Sizes()
    ordered = [sizes.title, sizes.display, sizes.heading, sizes.subtitle,
               sizes.body, sizes.label, sizes.small, sizes.tiny]
    assert ordered == sorted(ordered, reverse=True), "the scale must be ordered"
    assert len(set(ordered)) == len(ordered), "a scale with a repeat has a spare step"


def test_the_stroke_scale_ascends():
    w = Widths()
    ordered = [w.hairline, w.rule, w.mark, w.accent, w.chip]
    assert ordered == sorted(ordered)
    assert len(set(ordered)) == len(ordered)


def test_opacities_ascend():
    o = Opacities()
    assert 0 < o.tint < o.panel < o.solid <= 1.0


# --- the API ----------------------------------------------------------------


def test_theme_lookup_by_name():
    assert theme("dataflow") is DATAFLOW
    assert theme("paper") is PAPER


def test_unknown_theme_names_the_alternatives():
    """An agent that cannot read --help gets the options in the error."""
    with pytest.raises(RequestError) as caught:
        theme("neon")
    error = caught.value
    assert error.code == "no_request"
    assert error.remedy and "dataflow" in error.remedy
    assert error.details["available"] == list(THEME_NAMES)


def test_theme_names_are_sorted_and_complete():
    assert THEME_NAMES == tuple(sorted(THEMES))
    assert set(THEME_NAMES) == {"dataflow", "paper", "textbook"}


def test_variant_copies_rather_than_mutating():
    hot = DATAFLOW.variant(name="dataflow-hot", flow=DATAFLOW.warn)
    assert hot.flow == DATAFLOW.warn
    assert hot.name == "dataflow-hot"
    assert DATAFLOW.flow == "#4aa8ff", "the shared theme was mutated"
    assert hot.size is DATAFLOW.size, "untouched groups should be shared, not copied"


def test_a_style_cannot_be_edited_in_place():
    """Two scenes hold the same theme; one must not be able to restyle the other."""
    with pytest.raises(Exception):
        DATAFLOW.flow = "#ffffff"          # type: ignore[misc]


def test_style_is_exported_from_the_package():
    import straightedge

    assert straightedge.theme("dataflow") is straightedge.DATAFLOW
    for name in ("Style", "theme", "THEMES", "THEME_NAMES",
                 "DATAFLOW", "TEXTBOOK", "PAPER"):
        assert name in straightedge.__all__, f"{name} missing from __all__"


def test_a_theme_can_be_built_from_scratch():
    """The dataclass is the surface; nothing about it is dataflow-specific."""
    mono = Style(
        name="mono", ink="#000000", well="#000000", inert="#222222",
        rule="#444444", fg="#ffffff", muted="#bbbbbb", dim="#888888",
        on_fill="#000000", flow="#ffffff", hold="#cccccc", deep="#666666",
        done="#eeeeee", warn="#999999", aux="#dddddd", warm="#aaaaaa",
    )
    assert mono.size == Sizes()
    assert mono.accents == ("#ffffff", "#cccccc", "#eeeeee", "#999999")
