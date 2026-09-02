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
from straightedge.graph_scene import MAX_STEPS as _GRAPH_MAX_STEPS
from straightedge.graph_scene import MAX_VERTICES as _GRAPH_MAX_VERTICES
from straightedge.graphs import ConceptGraph, GraphError, coerce_graph, steps_for
from straightedge.linalg import (
    MAX_DIM,
    VIEWS,
    ConceptLinAlg,
    coerce_grid,
    coerce_matrix,
    coerce_vectors,
    determinant,
    eigenpairs,
    is_vector_list,
    shape,
    span_dimension,
)
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


# ----------------------------------------------------------- linear algebra

@register(ConceptLinAlg.LINEAR_MAP)
def _linear_map_is_drawable(plan: AnimationPlan) -> list[Violation]:
    """The one concept whose parameters *are* the lesson, so a drop is total.

    Every other builder here is a fixed picture with a few knobs. This one has
    no picture of its own: ``matrix`` decides what the animation shows, and the
    ``show_*`` flags decide which reading it gives. A parameter quietly dropped
    is therefore not a detail rendered slightly differently — it is a different
    lesson, rendered confidently.

    This is also the check :mod:`straightedge.catalog` recovers parameter names
    from, by walking this function for literal ``plan.parameters.get("...")``.
    Hence the repetition of ``plan.parameters`` below rather than a local alias:
    a concept whose entire interface *is* its parameters would otherwise be
    published with none, which is how it read before this check existed.
    """
    concept = plan.concept or ConceptLinAlg.LINEAR_MAP
    out: list[Violation] = []

    raw_matrix = plan.parameters.get("matrix")
    if raw_matrix is not None and not _is_2x2_of_numbers(raw_matrix):
        # An error, not a warning: the scene falls back to the identity, so the
        # video shows *no* transformation while narrating one.
        out.append(Violation(
            concept, "matrix",
            f"expected a 2x2 of numbers, got {raw_matrix!r}; the identity would "
            "be drawn instead, and a map that changes nothing is not the map "
            "that was asked for"))

    # Total by design: ``None`` and a malformed value both give the identity,
    # which is exactly what the scene would draw.
    matrix = coerce_matrix(raw_matrix)

    raw_vectors = plan.parameters.get("vectors")
    if raw_vectors is not None and not is_vector_list(raw_vectors):
        # Not a list of vectors at all. Reported separately from "some entries
        # were dropped", because the two are different mistakes and the counts
        # below cannot describe this one: a string iterates, so it used to
        # produce no violation and render the stock pair, and a bare number
        # raised TypeError from inside the check itself.
        out.append(Violation(
            concept, "vectors",
            f"expected a list of [x, y] pairs, got {raw_vectors!r}; the scene "
            "would draw its own stock pair instead"))
    elif raw_vectors is not None:
        kept = coerce_vectors(raw_vectors)
        dropped = _countable(raw_vectors) - len(kept)
        if dropped > 0:
            out.append(Violation(
                concept, "vectors",
                f"{dropped} of {_countable(raw_vectors)} entries are not plane "
                "vectors and would be dropped; the scene draws the rest, or its "
                "own stock pair if none survive"))
        # ``labels`` is zipped to the surviving vectors by index, so a label
        # past the end is not drawn and nothing says so.
        labels = plan.parameters.get("labels")
        if labels is not None and _countable(labels) > len(kept):
            out.append(Violation(
                concept, "labels",
                f"{_countable(labels)} labels for {len(kept)} drawable vectors; "
                "the extras are not drawn", severity="warn"))

    if plan.parameters.get("show_span"):
        # ``show_span`` was supported, documented and changelogged, and no check
        # read it — so ``list_templates`` published five parameters for a
        # six-parameter concept and the feature was invisible to every caller
        # that trusts the catalog. The check is real as well as load-bearing:
        # the span of nothing but zero vectors is a point, and a lesson that
        # asked to see a subspace is unlikely to have meant that one.
        if span_dimension(coerce_vectors(plan.parameters.get("vectors"))) == 0:
            out.append(Violation(
                concept, "show_span",
                "no non-zero vectors to span, so the subspace drawn is {0}, the "
                "origin alone", severity="warn"))

    # Everything is scaled together to fit the frame, so a violent matrix does
    # not overflow — it shrinks, and past a point the whole drawing is a
    # thumbnail nobody can read. That is the honest place to refuse: the
    # picture would be correct and useless.
    from straightedge.templates import _MIN_PLANE_SCALE, _fit_plane_scale

    drawn = coerce_vectors(plan.parameters.get("vectors")) or [(1.0, 0.0), (0.0, 1.0)]
    fit = _fit_plane_scale(matrix, drawn,
                           want_det=bool(plan.parameters.get("show_determinant")),
                           eig_reach=3.0 if plan.parameters.get("show_eigenvectors") else 0.0)
    if fit < _MIN_PLANE_SCALE:
        out.append(Violation(
            concept, "matrix",
            f"this map is too violent to draw with these vectors: everything "
            f"would be scaled to {fit:.3f} of its size to stay in frame, which "
            "is smaller than the grid can be read at. Use a gentler matrix, or "
            "shorter vectors"))

    if plan.parameters.get("show_eigenvectors") and not eigenpairs(matrix):
        out.append(Violation(
            concept, "show_eigenvectors",
            "this matrix has no real eigenvalues, so it has no invariant "
            "direction to draw — it turns every vector. The scene omits the "
            "step rather than inventing one", severity="warn"))

    if plan.parameters.get("show_determinant") and abs(determinant(matrix)) < 1e-12:
        out.append(Violation(
            concept, "show_determinant",
            "this matrix is singular, so the unit square collapses to a segment "
            "and the area caption reads 0. Drawable, and sometimes the point, "
            "but rarely what a determinant lesson intends", severity="warn"))

    return out


@register(ConceptLinAlg.MATMUL_VIEWS)
def _matrix_product_exists(plan: AnimationPlan) -> list[Violation]:
    """A product needs two matrices that conform, and a reading that exists.

    Stricter than the single-map checks above, and it has to be. ``linear_map``
    can fall back to the identity and still draw something the caller recognises
    as their request minus a detail. There is no such fallback for a product:
    substituting a matrix animates *different arithmetic*, narrated as if it
    were the arithmetic that was asked for, with every intermediate value on
    screen agreeing with the substitution.
    """
    concept = plan.concept or ConceptLinAlg.MATMUL_VIEWS
    out: list[Violation] = []

    a = coerce_grid(plan.parameters.get("a"))
    b = coerce_grid(plan.parameters.get("b"))
    for name, raw, grid in (("a", plan.parameters.get("a"), a),
                            ("b", plan.parameters.get("b"), b)):
        if raw is not None and grid is None:
            out.append(Violation(
                concept, name,
                f"expected a rectangular grid of numbers, got {raw!r}; the scene "
                "would animate its own stock matrices instead, and every value "
                "on screen would agree with them"))

    if a is not None and b is not None and shape(a)[1] != shape(b)[0]:
        out.append(Violation(
            concept, "b",
            f"shapes {shape(a)} and {shape(b)} do not conform: A has "
            f"{shape(a)[1]} columns and B has {shape(b)[0]} rows, so AB does "
            "not exist and there is nothing to animate"))

    for name, grid in (("a", a), ("b", b)):
        if grid is not None and max(shape(grid)) > MAX_DIM:
            out.append(Violation(
                concept, name,
                f"{shape(grid)[0]}x{shape(grid)[1]} exceeds {MAX_DIM}x{MAX_DIM}; "
                "the grids shrink to fit, and past this size the bottom row runs "
                "into the running caption — measured, not assumed: qc reports a "
                "clean 4x4 and ten text_overlap errors at 5x5"))

    view = plan.parameters.get("view")
    if view is not None and str(view).lower() not in VIEWS:
        out.append(Violation(
            concept, "view",
            f"{view!r} is not one of {VIEWS}; the entry reading would be drawn, "
            "which is a different lesson from the one requested", severity="warn"))

    return out

def _is_2x2_of_numbers(raw: object) -> bool:
    """Whether ``coerce_matrix`` will keep this, rather than substitute.

    Asked structurally instead of by comparing the result to the identity: a
    caller who passes the identity *on purpose* must not be told their matrix
    was rejected.
    """
    try:
        rows = [list(row) for row in raw]        # type: ignore[call-overload]
    except TypeError:
        return False
    if len(rows) != 2 or any(len(row) != 2 for row in rows):
        return False
    try:
        [float(x) for row in rows for x in row]
    except (TypeError, ValueError):
        return False
    return True


def _countable(value: object) -> int:
    """``len`` where there is one. A string is not a list of vectors."""
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        return 0
    return len(value)


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


# ------------------------------------------------------------------ graphs

@register(ConceptGraph.TRAVERSAL, ConceptGraph.SHORTEST_PATH,
          ConceptGraph.SPANNING_TREE, ConceptGraph.MAX_FLOW,
          ConceptGraph.CONNECTIVITY, ConceptGraph.WALK_TRACE)
def _graph_states_are_computable(plan: AnimationPlan) -> list[Violation]:
    """The algorithm must run on the supplied graph, and fit in one video.

    Runs the same :func:`steps_for` the scene builder draws from, so what is
    refused here is exactly what would not have been drawn. Anything the
    algorithm cannot honestly do — a negative weight under Dijkstra, a source
    equal to the sink, an edge to a vertex that does not exist — is an error
    carrying the witness in its message.

    The parameter reads below are literal so the catalog can publish them.
    """
    concept = plan.concept or ConceptGraph.TRAVERSAL
    params = {
        "nodes": plan.parameters.get("nodes"),
        "edges": plan.parameters.get("edges"),
        "directed": plan.parameters.get("directed"),
        "algorithm": plan.parameters.get("algorithm"),
        "start": plan.parameters.get("start"),
        "source": plan.parameters.get("source"),
        "sink": plan.parameters.get("sink"),
        "neighbor_order": plan.parameters.get("neighbor_order"),
        "layout": plan.parameters.get("layout"),
        "title": plan.parameters.get("title"),
        "walks": plan.parameters.get("walks"),
    }
    params = {key: value for key, value in params.items() if value is not None}
    out: list[Violation] = []
    try:
        steps = steps_for(concept, params)
    except GraphError as exc:
        return [Violation(concept, None, f"{exc}; nothing would be drawn")]
    if params.get("nodes") is not None:
        vertices = len(coerce_graph(params).ids)
        if vertices > _GRAPH_MAX_VERTICES:
            out.append(Violation(
                concept, "nodes",
                f"{vertices} vertices; at most {_GRAPH_MAX_VERTICES} stay legible "
                "beside the state panel in one frame"))
    if len(steps) > _GRAPH_MAX_STEPS:
        out.append(Violation(
            concept, "nodes",
            f"the algorithm takes {len(steps)} steps; at most {_GRAPH_MAX_STEPS} fit "
            "one narrated video, and the scene would stop early"))
    return out
