"""Per-concept checks on a plan, before anything is drawn.

:mod:`straightedge.qc` inspects a built scene and asks whether it *looks* right.
This module asks the earlier question: does the plan describe the animation that
was actually requested? Those are different failures, and geometric checks
cannot see this one — a scene that silently drew the wrong function is
beautifully laid out and completely wrong.

The failure mode being caught is **silent substitution**. The scene builders
repair bad input rather than refusing it, which is the correct behaviour for a
renderer — a video is better than a traceback — but it means a plan can ask for
one thing and get another with nothing logged:

.. code-block:: python

    A = float(spec_dict.get("A", 1.0)) or 1.0      # A=0 quietly becomes 1.0
    if func not in ("sin", "cos", "tan"):
        func = "sin"                                # "sec" quietly becomes sin
    if not validate_expression(raw):
        raw = fallback                              # a typo quietly becomes x**2

Nobody iterating on their own scene is misled for long; they watch the render.
A teacher who typed a prompt has no way to know the video answers a different
question than the one asked. So every substitution a builder would perform
silently is reported here instead.

The checks are also the natural home for genuine impossibilities — a plane that
misses the solid it is meant to cut, a section defined by fewer than three
points. Those cannot be caught generically, which is exactly why they live
beside the concept that understands them.

Findings, never mutations: this module never edits a plan. The caller decides
whether to repair, re-prompt, or fall back.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Sequence

from straightedge.calculus import ConceptCalculus
from straightedge.conics import CONE_TAN_MAX as _CONE_TAN_MAX
from straightedge.conics import CONE_TAN_MIN as _CONE_TAN_MIN
from straightedge.conics import ConceptConic
from straightedge.expr import validate_expression
from straightedge.models import AnimationPlan, Topic
from straightedge.solids3d import Concept3D
from straightedge.trig import Concept as ConceptTrig

#: Trig functions the transform scene can draw. Anything else is redrawn as sin.
_TRIG_FUNCS = ("sin", "cos", "tan")

#: Taylor targets with a written expansion. Anything else is redrawn as sin.
_TAYLOR_TARGETS = ("sin", "cos")

#: Solids ``solids3d`` can build. An unknown kind raises during the render.
_SOLID_KINDS = ("cube", "box", "regular_prism", "regular_pyramid",
                "tetrahedron", "cylinder", "cone")

#: A section needs three points to define a plane, and the builder falls back to
#: a stock triangle below that.
_MIN_SECTION_POINTS = 3


@dataclass(frozen=True)
class Violation:
    """One way the plan will not produce what it appears to ask for."""

    concept: str
    param: str | None
    message: str
    severity: str = "error"     # "error" | "warn"

    def __str__(self) -> str:   # pragma: no cover - trivial
        where = f" ({self.param})" if self.param else ""
        return f"[{self.severity}] {self.concept}{where}: {self.message}"


Check = Callable[[AnimationPlan], list[Violation]]

_CHECKS: dict[str, list[Check]] = {}


def register(*concepts: str) -> Callable[[Check], Check]:
    """Attach a check to one or more concepts.

    Keyed by ``plan.concept`` so a check lives next to the builder that shares
    its assumptions — the reason these cannot be written generically.
    """

    def decorator(func: Check) -> Check:
        for concept in concepts:
            _CHECKS.setdefault(concept, []).append(func)
        return func

    return decorator


def validate(plan: AnimationPlan) -> list[Violation]:
    """Every violation for this plan's concept. Empty means nothing to say."""
    violations: list[Violation] = []
    for check in _CHECKS.get(plan.concept or "", ()):
        violations.extend(check(plan))
    return violations


def blocking(violations: Iterable[Violation]) -> list[Violation]:
    return [v for v in violations if v.severity == "error"]


# --------------------------------------------------------------------- trig

@register(ConceptTrig.GRAPH_TRANSFORM)
def _trig_spec_is_drawable(plan: AnimationPlan) -> list[Violation]:
    spec = plan.parameters.get("trig_spec")
    if not isinstance(spec, dict):
        return []                       # absent is fine: the builder has defaults

    out: list[Violation] = []
    func = spec.get("func", "sin")
    if func not in _TRIG_FUNCS:
        out.append(Violation(
            ConceptTrig.GRAPH_TRANSFORM, "trig_spec.func",
            f"{func!r} is not one of {_TRIG_FUNCS}; the scene would draw sin instead"))

    amplitude = _as_float(spec.get("A", 1.0))
    if amplitude is not None and amplitude == 0:
        out.append(Violation(
            ConceptTrig.GRAPH_TRANSFORM, "trig_spec.A",
            "amplitude 0 is a flat line, and the scene would draw amplitude 1 instead"))

    omega = _as_float(spec.get("omega", 1.0))
    if omega is not None and omega == 0:
        out.append(Violation(
            ConceptTrig.GRAPH_TRANSFORM, "trig_spec.omega",
            "frequency 0 has no period to mark, and the scene would draw omega 1 instead"))

    return out


# ----------------------------------------------------------------- calculus

@register(ConceptCalculus.DERIVATIVE_TANGENT,
          ConceptCalculus.RIEMANN_INTEGRAL,
          ConceptCalculus.FTC_ACCUMULATION)
def _calculus_expression_parses(plan: AnimationPlan) -> list[Violation]:
    """An unparseable expression is replaced by the concept's stock function.

    This is the substitution most likely to mislead: the video is titled and
    narrated for the function that was asked for, and plots a different one.
    """
    raw = plan.parameters.get("expression")
    if raw in (None, ""):
        return []
    if validate_expression(str(raw)):
        return []
    return [Violation(
        plan.concept or "calculus", "expression",
        f"{raw!r} is not a supported expression; the scene would plot its "
        f"stock function while the narration still describes this one")]


@register(ConceptCalculus.TAYLOR_SERIES)
def _taylor_target_has_an_expansion(plan: AnimationPlan) -> list[Violation]:
    target = plan.parameters.get("function")
    if target in (None, "") or target in _TAYLOR_TARGETS:
        return []
    return [Violation(
        ConceptCalculus.TAYLOR_SERIES, "function",
        f"no written expansion for {target!r}; only {_TAYLOR_TARGETS} are "
        f"available, and the scene would expand sin instead")]


# ----------------------------------------------------------------------- 3d

@register(Concept3D.CUBE_SECTION)
def _section_is_a_plane(plan: AnimationPlan) -> list[Violation]:
    """Three named vertices, or there is no plane to cut with.

    This is the shape of defect that geometric checks cannot reach: two points
    render a perfectly tidy scene showing the wrong construction entirely.
    """
    points = plan.parameters.get("section_points")
    if points is None:
        return []
    if not isinstance(points, Sequence) or isinstance(points, (str, bytes)):
        return [Violation(Concept3D.CUBE_SECTION, "section_points",
                          "expected a list of vertex names")]

    named = [p for p in points if isinstance(p, str) and _is_vertex_name(p)]
    out: list[Violation] = []

    unnamed = [p for p in points if p not in named]
    if unnamed:
        out.append(Violation(
            Concept3D.CUBE_SECTION, "section_points",
            f"{unnamed!r} are not vertex labels (expected forms like 'A' or 'B1')",
            severity="warn"))

    if len(named) < _MIN_SECTION_POINTS:
        out.append(Violation(
            Concept3D.CUBE_SECTION, "section_points",
            f"{len(named)} usable point(s); a section plane needs "
            f"{_MIN_SECTION_POINTS}, and the scene would cut a stock triangle instead"))
    return out


@register(Concept3D.SOLID_OVERVIEW, Concept3D.CUBE_SECTION, Concept3D.THREE_VIEWS)
def _solid_kind_is_buildable(plan: AnimationPlan) -> list[Violation]:
    """An unknown kind raises inside the render rather than substituting."""
    spec = plan.parameters.get("solid_spec")
    if not isinstance(spec, dict):
        return []
    kind = spec.get("kind")
    if kind in (None, "") or kind in _SOLID_KINDS:
        return []
    return [Violation(
        plan.concept or Topic.THREE_D, "solid_spec.kind",
        f"{kind!r} is not a buildable solid; expected one of {_SOLID_KINDS}")]


# ------------------------------------------------------------------- conics

@register(ConceptConic.CONE_SLICE)
def _cone_half_angle_is_drawable(plan: AnimationPlan) -> list[Violation]:
    """The cone's half-angle decides where the parabola falls.

    A silent substitution here is the expensive kind. The builder clamps a bad
    value back to the default and draws a cone of a *different* shape, so the
    beat narrated as "parallel to a slant line" is parallel to nothing and the
    section under that sentence is still an ellipse. The picture is beautiful
    and the words over it are false.
    """
    raw = plan.parameters.get("half_angle_tan")
    if raw is None:
        return []                   # absent is fine: the builder has a default
    value = _as_float(raw)
    if value is None:
        return [Violation(
            plan.concept or ConceptConic.CONE_SLICE, "half_angle_tan",
            f"expected a number, got {raw!r}")]
    if not _CONE_TAN_MIN < value < _CONE_TAN_MAX:
        return [Violation(
            plan.concept or ConceptConic.CONE_SLICE, "half_angle_tan",
            f"{value} is outside ({_CONE_TAN_MIN}, {_CONE_TAN_MAX}); a cone that "
            "flat or that sharp leaves no readable sweep between the circle and "
            "the hyperbola")]
    return []


# -------------------------------------------------------------------- utils

def _as_float(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _is_vertex_name(name: str) -> bool:
    """``A``, ``B1`` — the labelling ``_validated_points`` accepts."""
    return (
        1 <= len(name) <= 2
        and name[0].isascii() and name[0].isupper()
        and (len(name) == 1 or name[1].isdigit())
    )
