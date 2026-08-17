"""The examples draw in a style you can change from outside them.

``examples/_layout.py`` is the one place the four dataflow scenes agree on a
look, so it is also the place the look is chosen. Two things need pinning: the
default has to stay ``dataflow`` (anything else silently restyles four published
videos), and a bad name has to fail *before* Manim spends four minutes rendering
in a style nobody asked for.

The scenes themselves are not imported here — they need the ``render`` extra, and
what is under test is the selection, not the drawing.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from straightedge.errors import RequestError
from straightedge.style import DATAFLOW, PAPER, TEXTBOOK

_PATH = Path(__file__).resolve().parent.parent / "examples" / "_layout.py"


def _load(monkeypatch, style: str | None):
    """Import ``_layout`` fresh, with ``STRAIGHTEDGE_STYLE`` set or cleared.

    Fresh every time because ``STYLE`` is resolved at import: a cached module
    would answer the previous test's question.
    """
    if style is None:
        monkeypatch.delenv("STRAIGHTEDGE_STYLE", raising=False)
    else:
        monkeypatch.setenv("STRAIGHTEDGE_STYLE", style)
    sys.modules.pop("_layout", None)
    spec = importlib.util.spec_from_file_location("_layout", _PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_default_is_dataflow(monkeypatch):
    """The published look. Changing this restyles every dataflow video."""
    assert _load(monkeypatch, None).STYLE is DATAFLOW


def test_an_empty_variable_is_not_a_style_name(monkeypatch):
    """``STRAIGHTEDGE_STYLE=`` in a shell profile should mean "unset"."""
    assert _load(monkeypatch, "").STYLE is DATAFLOW


@pytest.mark.parametrize("name,expected", [("paper", PAPER),
                                           ("textbook", TEXTBOOK),
                                           ("dataflow", DATAFLOW)])
def test_a_named_style_is_honoured(monkeypatch, name, expected):
    assert _load(monkeypatch, name).STYLE is expected


def test_an_unknown_style_fails_at_import(monkeypatch):
    """Before the render, not after it — and it names the alternatives."""
    with pytest.raises(RequestError) as caught:
        _load(monkeypatch, "neon")
    assert "paper" in (caught.value.remedy or "")


def test_the_scenes_all_take_their_style_from_here():
    """A scene that hardcoded a theme would not follow the switch.

    Checked as source rather than by importing: these modules need Manim, and
    this assertion is about how they get their style, not about what they draw.
    """
    examples = _PATH.parent
    scenes = sorted(examples.glob("*/scene.py"))
    assert len(scenes) == 4, f"expected four dataflow scenes, found {len(scenes)}"
    for scene in scenes:
        source = scene.read_text(encoding="utf-8")
        assert "from _layout import STYLE as S" in source, (
            f"{scene.parent.name} does not take its style from _layout"
        )
        # The hex literals these scenes used to define by hand now live in one
        # place. A stray one is how the set drifts back apart.
        for stale in ("#0d1117", "#4aa8ff", "#f2b45b", "#4CAF50", "#E5533D",
                      "#5a6885", "#2c5c86", "#1c2534"):
            assert stale not in source, (
                f"{scene.parent.name} still hardcodes {stale}; it belongs to a theme"
            )
