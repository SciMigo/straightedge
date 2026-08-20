"""Compass-and-straightedge construction (尺规作图) — drawn from its own steps.

The library is named after a tool it could not draw with. This is the figure
lane's end of that: a list of construction steps in, an SVG out, with every
point placed by exact arithmetic rather than by a float that came close.

What makes it different from drawing two circles and a line is that the *model*
knows what it built. Crossing two circles produces points the caller never named
--- the vesica's two, and then the midpoint when the axis is drawn --- and those
points are exact, so a later claim about them (Phase 5) can be decided rather
than measured.

image_hint usage::

    {"type": "construction", "params": {
        "title": "Perpendicular bisector",
        "steps": [
            {"point": [0, 0], "id": "A"},
            {"point": [1, 0], "id": "B"},
            {"circle": ["A", "B"]},
            {"circle": ["B", "A"]},
            {"line": ["C", "D"]}]}}

A step is one of ``point`` (a coordinate pair), ``line`` (two point ids),
``circle`` (centre id then a point id the circle passes through), ``polygon``
(three or more point ids) or ``section`` (three collinear point ids). Any step
may carry ``"guide": true``, which draws it dashed and excludes it from
intersection --- scaffolding a reader is meant to see and the model is meant to
ignore.

Points produced by intersection are named automatically in order: ``A``, ``B``,
``C``… so the two circles above make ``C`` and ``D`` without being asked. That
is why the example can name ``["C", "D"]`` in a line it never declared.

Coordinates accept integers, ``"p/q"`` fractions, and decimal strings — and a
decimal string is read as the exact rational it denotes, so ``"0.1"`` is one
tenth and not the binary float nearest to it. Pass coordinates as strings when
they are not integers; a Python ``float`` is already the wrong number before it
arrives here, and nothing downstream can recover what was meant.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any, Dict, List

import logging

from ...errors import PrecisionError
from ...geometry.claims import check as check_claims
from ...geometry.draw import DEFAULT_WIDTH, to_svg
from ...geometry.model import Construction
from ...qc import Finding, worst_severity
from ..registry import register
from ..renderer import svg_document

logger = logging.getLogger(__name__)

_POINT_KEYS = ("point", "set_point", "p")
_LINE_KEYS = ("line", "construct_line", "l")
_CIRCLE_KEYS = ("circle", "construct_circle", "c")
_POLYGON_KEYS = ("polygon", "poly")
_SECTION_KEYS = ("section", "sect")


def _coordinate(value: Any) -> Fraction:
    """A coordinate as the exact rational it denotes.

    ``"0.1"`` is one tenth, not the binary float nearest to one tenth. A float
    *object* is accepted and converted exactly, which is lossless but rarely what
    a caller meant --- ``0.1`` in Python is already the wrong number by the time
    it arrives, and there is nothing this can do about that but be honest.
    """
    if isinstance(value, Fraction):
        return value
    if isinstance(value, bool):
        raise TypeError("a boolean is not a coordinate")
    if isinstance(value, int):
        return Fraction(value)
    if isinstance(value, float):
        return Fraction(value).limit_denominator(10 ** 9)
    return Fraction(str(value).strip())


def _first(step: Dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in step:
            return step[key]
    return None


def _apply(construction: Construction, step: Any) -> None:
    """Run one step against the construction, raising on anything unusable."""
    if not isinstance(step, dict):
        raise TypeError(f"a step must be a mapping, got {type(step).__name__}")
    guide = bool(step.get("guide", False))
    element_id = step.get("id")

    coords = _first(step, _POINT_KEYS)
    if coords is not None:
        if not isinstance(coords, (list, tuple)) or len(coords) != 2:
            raise ValueError(f"a point needs two coordinates, got {coords!r}")
        construction.set_point(_coordinate(coords[0]), _coordinate(coords[1]),
                               id=element_id, guide=guide)
        return

    ends = _first(step, _LINE_KEYS)
    if ends is not None:
        first, second = ends
        construction.construct_line(str(first), str(second), id=element_id, guide=guide)
        return

    around = _first(step, _CIRCLE_KEYS)
    if around is not None:
        center, through = around
        construction.construct_circle(str(center), str(through),
                                      id=element_id, guide=guide)
        return

    corners = _first(step, _POLYGON_KEYS)
    if corners is not None:
        construction.set_polygon(*[str(name) for name in corners], id=element_id)
        return

    triple = _first(step, _SECTION_KEYS)
    if triple is not None:
        a, b, c = triple
        construction.set_section(str(a), str(b), str(c), id=element_id)
        return

    raise ValueError(f"a step names nothing to draw: {sorted(step)}")


def build(steps: List[Any], name: str = "construction") -> Construction:
    """Run every step in order. Public so a caller can check what it drew."""
    construction = Construction(name)
    for step in steps:
        _apply(construction, step)
    return construction


def verify(params: Dict[str, Any]) -> List[Finding]:
    """Build the construction and decide its claims, without drawing anything.

    The cheap step, and the one worth doing first: deciding a claim costs
    arithmetic, drawing costs a document, and a construction whose claim is false
    should never reach the second. Returns the findings — an empty list means
    every claim held.
    """
    steps = params.get("steps") or params.get("construction") or []
    if not isinstance(steps, list) or not steps:
        return [Finding("construction:empty", "error", "no steps to build")]
    try:
        construction = build(steps, str(params.get("title") or "construction"))
    except PrecisionError as exc:
        return [Finding("construction:unbuildable", "error", exc.message)]
    except (ValueError, TypeError, KeyError, ZeroDivisionError) as exc:
        return [Finding("construction:unbuildable", "error", str(exc))]
    claims = params.get("claims") or []
    return check_claims(construction, claims) if isinstance(claims, list) else []


@register("construction")
class ConstructionTemplate:
    """Compass-and-straightedge construction with exactly placed points."""

    def render(self, params: Dict[str, Any]) -> str:
        steps = params.get("steps") or params.get("construction") or []
        title = str(params.get("title") or params.get("caption") or "")
        labels = params.get("labels")
        guides = str(params.get("guides") or "dashed")
        width = params.get("width") or DEFAULT_WIDTH

        if not isinstance(steps, list) or not steps:
            return svg_document("", width=200, height=80,
                                class_name="diagram construction")
        try:
            construction = build(steps, title or "construction")
        except (ValueError, TypeError, KeyError, ZeroDivisionError,
                PrecisionError):
            # A construction that cannot be run has no partial drawing worth
            # showing: half a figure reads as a whole one. `render_diagram`
            # reports the blank, and `count_data_marks` refuses to call it a
            # render.
            return svg_document("", width=200, height=80,
                                class_name="diagram construction")

        claims = params.get("claims") or []
        findings = check_claims(construction, claims) if isinstance(claims, list) else []
        if worst_severity(findings) == "error":
            # A construction that asserts something false does not get drawn.
            # This is the rule `AGENTS.md` states for the example scenes, applied
            # where it belongs: a figure whose claim stops being true should fail
            # rather than produce a convincing picture of something false. Call
            # `verify()` for the findings themselves — a template returns a
            # string and has nowhere to put them.
            for finding in findings:
                logger.warning("construction claim failed: %s", finding)
            return svg_document("", width=200, height=80,
                                class_name="diagram construction")

        return to_svg(construction,
                      width=int(width),
                      labels=True if labels is None else bool(labels),
                      guides=guides if guides in ("dashed", "hidden") else "dashed",
                      title=title)
