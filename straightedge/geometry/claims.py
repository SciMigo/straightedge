"""What a construction asserts about itself — decided, not measured.

This is the reason the rest of the lane exists. A drawing of two circles and a
line is easy; what no diagram tool offers is the drawing *stating* that the line
it drew is the perpendicular bisector, and being refused when it is not.

Every predicate below reduces to ``is_zero`` on an exact value, so a claim is
proved or disproved rather than estimated. ``golden`` is the illustration worth
reading: a section is golden when ``AB/BC == φ``, which looks like it needs
``√5`` — but squaring twice turns it into ``AB⁴ == AC²·BC²``, an identity among
squared lengths with no root in it at all. The predicate is exact *and* costs
the field nothing.

Findings, never mutations. A claim that holds produces nothing; a claim that
fails is an ``error``; a claim that could not be certified because the exact
field hit its cap is a ``warn`` naming the cap. That last case is the one that
matters most: it is never silently a pass.

    >>> from .model import Construction
    >>> c = Construction()
    >>> a, b = c.set_point(0, 0), c.set_point(1, 0)
    >>> _ = c.construct_circle(a, b); _ = c.construct_circle(b, a)
    >>> line = c.construct_line("C", "D")
    >>> check(c, [{"claim": "perpendicular", "of": [line, "[ A B ]"]}])
    [Finding(check='claim:perpendicular', severity='error', ...)]

(The line ``[ A B ]`` has not been drawn in that example, which is itself a
finding — an assertion about something absent is a failed assertion, not a
skipped one.)
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Callable, Sequence

from ..errors import PrecisionError
from ..qc import Finding
from .exact import Exact
from .model import (
    Arc, Circle, Construction, Line, Point, Polygon, Section, Segment)

__all__ = ["Claim", "check", "marks", "Mark", "CLAIMS", "ARITY"]

#: Above this, a float disagreement is taken as proof of *inequality* and the
#: exact path is skipped. The asymmetry is the whole safety argument: this can
#: only ever report a true claim as false — never a false claim as true — so a
#: mis-set threshold costs a spurious error a human will see, not a silent pass.
FLOAT_REJECT = 1e-6


@dataclass(frozen=True)
class Claim:
    kind: str
    of: tuple[Any, ...] = ()
    value: Any = None

    @classmethod
    def parse(cls, raw: Any) -> "Claim":
        if isinstance(raw, Claim):
            return raw
        if not isinstance(raw, dict):
            raise ValueError(f"a claim must be a mapping, got {type(raw).__name__}")
        kind = str(raw.get("claim") or raw.get("kind") or "").strip().lower()
        if not kind:
            raise ValueError(f"a claim must name what it asserts: {sorted(raw)}")
        of = raw.get("of", raw.get("elements", ()))
        if isinstance(of, (str, bytes)) or not isinstance(of, (list, tuple)):
            of = (of,)
        return cls(kind, tuple(of), raw.get("value", raw.get("ratio")))

    def __str__(self) -> str:
        args = ", ".join(_render_arg(a) for a in self.of)
        tail = f" == {self.value}" if self.value is not None else ""
        return f"{self.kind}({args}){tail}"


def _render_arg(arg: Any) -> str:
    if isinstance(arg, (list, tuple)):
        return "[" + " ".join(str(a) for a in arg) + "]"
    return str(arg)


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------


class _Unresolved(Exception):
    """A claim names something the construction does not have."""


def _element(c: Construction, name: Any):
    """The geometry behind an id, with an arc resolved to its circle.

    An arc restricts what is *drawn*, not what is known — so every predicate
    reasons about the whole circle, and `on(P, arc)` asks whether P is on that
    circle rather than on the visible portion. Deciding against the drawn part
    would make a claim depend on a presentation choice, which is the one thing a
    proof must not do.
    """
    key = str(name)
    if key not in c:
        raise _Unresolved(f"no element named {key!r}")
    geometry = c[key].geometry
    return geometry.circle if isinstance(geometry, Arc) else geometry


def _point(c: Construction, name: Any) -> Point:
    geometry = _element(c, name)
    if not isinstance(geometry, Point):
        raise _Unresolved(f"{name!r} is not a point")
    return geometry


def _line(c: Construction, name: Any) -> Line:
    geometry = _element(c, name)
    if not isinstance(geometry, Line):
        raise _Unresolved(f"{name!r} is not a line")
    return geometry


def _circle(c: Construction, name: Any) -> Circle:
    geometry = _element(c, name)
    if not isinstance(geometry, Circle):
        raise _Unresolved(f"{name!r} is not a circle")
    return geometry


def _segment(c: Construction, spec: Any) -> Segment:
    """``["A", "B"]`` or an existing segment-shaped element."""
    if isinstance(spec, (list, tuple)) and len(spec) == 2:
        return Segment(_point(c, spec[0]), _point(c, spec[1]))
    geometry = _element(c, spec)
    if isinstance(geometry, Segment):
        return geometry
    raise _Unresolved(f"{spec!r} is not a segment")


def _section(c: Construction, spec: Any) -> Section:
    if isinstance(spec, (list, tuple)) and len(spec) == 3:
        return Section(tuple(_point(c, name) for name in spec))  # type: ignore[arg-type]
    geometry = _element(c, spec)
    if isinstance(geometry, Section):
        return geometry
    raise _Unresolved(f"{spec!r} is not a section")


def _nondegenerate(section: Section, claim: str) -> None:
    """Refuse a section whose parts have no length.

    Exact arithmetic on a degenerate figure proves undefined statements with
    total confidence: for a section on one repeated point every squared length
    is zero, so ``AB² == r²·BC²`` holds for *every* r and ``AB⁴ == AC²·BC²``
    holds trivially — the collapsed section was reported as being in ratio
    12345 and as golden. A predicate has to own its domain; 0 == 0 is not
    evidence about a ratio that does not exist.
    """
    first, second = section.segments
    whole = Segment(section.points[0], section.points[2])
    for name, segment in (("AB", first), ("BC", second), ("AC", whole)):
        if segment.length_sq.is_zero():
            raise _Unresolved(
                f"{claim} is undefined here: {name} has zero length, so the "
                f"section is three points in one place")


def _rational(value: Any) -> Exact:
    if isinstance(value, Exact):
        return value
    if isinstance(value, (int, Fraction)):
        return Exact.rational(value)
    return Exact.rational(Fraction(str(value).strip()))


# ---------------------------------------------------------------------------
# The decision
# ---------------------------------------------------------------------------


def _is_zero(value: Exact, scale: float = 1.0) -> bool:
    """Exact zero, with a cheap float rejection in front of it.

    The float stage never *confirms*: a value it cannot dismiss goes to the exact
    predicate regardless. So the only error it can introduce is dismissing a true
    zero that floats put far from zero, which reports a holding claim as broken —
    loud, visible, and the safe direction to be wrong in.
    """
    magnitude = abs(float(value))
    if magnitude > FLOAT_REJECT * max(scale, 1.0):
        return False
    return value.is_zero()


def _scale_of(*points: Point) -> float:
    return max((abs(float(p.x)) + abs(float(p.y)) for p in points), default=1.0)


# ---------------------------------------------------------------------------
# Predicates
# ---------------------------------------------------------------------------


def _on(c: Construction, claim: Claim) -> tuple[bool, str]:
    point = _point(c, claim.of[0])
    target = _element(c, claim.of[1])
    if isinstance(target, Line):
        return _is_zero(target.evaluate(point), _scale_of(point)), "on the line"
    if isinstance(target, Circle):
        dx = point.x - target.center.x
        dy = point.y - target.center.y
        residual = dx * dx + dy * dy - target.radius_sq
        return _is_zero(residual, _scale_of(point, target.center)), "on the circle"
    raise _Unresolved(f"{claim.of[1]!r} is not a line or circle")


def _collinear(c: Construction, claim: Claim) -> tuple[bool, str]:
    a, b, d = (_point(c, name) for name in claim.of[:3])
    area2 = (b.x - a.x) * (d.y - a.y) - (d.x - a.x) * (b.y - a.y)
    return _is_zero(area2, _scale_of(a, b, d)), "collinear"


def _parallel(c: Construction, claim: Claim) -> tuple[bool, str]:
    one, two = (_line(c, name) for name in claim.of[:2])
    return _is_zero(one.a * two.b - two.a * one.b), "parallel"


def _perpendicular(c: Construction, claim: Claim) -> tuple[bool, str]:
    one, two = (_line(c, name) for name in claim.of[:2])
    # Directions are (-b, a); their dot product is a₁a₂ + b₁b₂.
    return _is_zero(one.a * two.a + one.b * two.b), "perpendicular"


def _congruent(c: Construction, claim: Claim) -> tuple[bool, str]:
    first = _segment(c, claim.of[0])
    rest = [_segment(c, spec) for spec in claim.of[1:]]
    if not rest:
        raise _Unresolved("congruent needs at least two segments")
    target = first.length_sq
    for segment in rest:
        if not _is_zero(target - segment.length_sq):
            return False, "equal in length"
    return True, "equal in length"


def _midpoint(c: Construction, claim: Claim) -> tuple[bool, str]:
    m, a, b = (_point(c, name) for name in claim.of[:3])
    scale = _scale_of(m, a, b)
    return (_is_zero(m.x * 2 - (a.x + b.x), scale)
            and _is_zero(m.y * 2 - (a.y + b.y), scale)), "the midpoint"


def _equilateral(c: Construction, claim: Claim) -> tuple[bool, str]:
    geometry = _element(c, claim.of[0])
    if not isinstance(geometry, Polygon):
        raise _Unresolved(f"{claim.of[0]!r} is not a polygon")
    sides = geometry.sides
    target = sides[0].length_sq
    for side in sides[1:]:
        if not _is_zero(target - side.length_sq):
            return False, "equilateral"
    return True, "equilateral"


def _tangent(c: Construction, claim: Claim) -> tuple[bool, str]:
    """A circle touching a line, or a circle touching another circle."""
    circle = _circle(c, claim.of[0])
    other = _element(c, claim.of[1])

    if isinstance(other, Circle):
        # Two circles touch when the distance between centres is r₁+r₂
        # (externally) or |r₁−r₂| (internally). Only r² is stored, so square
        # once more to clear both roots at the same time:
        #     d² = r₁² + r₂² ± 2r₁r₂   ⟹   (d² − r₁² − r₂²)² = 4r₁²r₂²
        # which is one identity covering both cases, exact, and needing no √.
        if circle == other:
            # The identity is satisfied by a circle and itself — d² = 0 and
            # r₁ = r₂ make both sides 4r⁴ — but coincident circles meet at every
            # one of their points, which is the opposite of touching at one.
            # A predicate has to own its domain; the algebra alone does not.
            raise _Unresolved(
                "tangency is undefined between a circle and itself: coincident "
                "circles meet everywhere, not at one point")
        dx = other.center.x - circle.center.x
        dy = other.center.y - circle.center.y
        gap = dx * dx + dy * dy - circle.radius_sq - other.radius_sq
        touching = _is_zero(gap * gap - circle.radius_sq * other.radius_sq * 4,
                            _scale_of(circle.center, other.center))
        inside = gap.sign() < 0
        return touching, f"tangent ({'internally' if inside else 'externally'})"

    if not isinstance(other, Line):
        raise _Unresolved(f"{claim.of[1]!r} is not a line or a circle")
    value = other.evaluate(circle.center)
    norm = other.a * other.a + other.b * other.b
    # distance² == r²  ⟺  value² == r²·(a²+b²)
    return _is_zero(value * value - circle.radius_sq * norm), "tangent"


def _concurrent(c: Construction, claim: Claim) -> tuple[bool, str]:
    from .model import intersect_lines
    lines = [_line(c, name) for name in claim.of]
    if len(lines) < 3:
        raise _Unresolved("concurrent needs at least three lines")
    meeting = intersect_lines(lines[0], lines[1])
    if not meeting:
        return False, "concurrent"
    point = meeting[0]
    for line in lines[2:]:
        if not _is_zero(line.evaluate(point), _scale_of(point)):
            return False, "concurrent"
    return True, "concurrent"


def _ratio(c: Construction, claim: Claim) -> tuple[bool, str]:
    """``|AB| / |BC| == r``, decided on squares so no root is taken."""
    section = _section(c, claim.of[0])
    if claim.value is None:
        raise _Unresolved("ratio needs a value")
    wanted = _rational(claim.value)
    # Squaring loses the sign, so a negative target would be satisfied by its
    # own absolute value. A ratio of lengths is positive by construction.
    if wanted.sign() <= 0:
        raise _Unresolved(
            f"a ratio of lengths must be positive, got {claim.value}")
    _nondegenerate(section, "ratio")
    first, second = section.segments
    return (_is_zero(first.length_sq - wanted * wanted * second.length_sq),
            f"in ratio {claim.value}")


def _golden(c: Construction, claim: Claim) -> tuple[bool, str]:
    """``AB/BC == φ`` — squared twice, so ``√5`` never enters the field.

    A section is golden when the whole is to the greater part as the greater is
    to the lesser: ``AC/AB == AB/BC``, i.e. ``AB² == AC·BC``. Squaring that gives
    ``AB⁴ == AC²·BC²``, which is an identity among *squared* lengths — all of
    which the model already holds exactly. Either part may be the greater one.
    """
    section = _section(c, claim.of[0])
    _nondegenerate(section, "golden")
    a, b, d = section.points
    ab = Segment(a, b).length_sq
    bc = Segment(b, d).length_sq
    ac = Segment(a, d).length_sq
    return (_is_zero(ab * ab - ac * bc) or _is_zero(bc * bc - ac * ab)), "golden"


def _harmonic(c: Construction, claim: Claim) -> tuple[bool, str]:
    """Cross ratio ``(A,B;C,D) == −1``.

    Derived rather than borrowed. The condition is
    ``(AC·BD)/(AD·BC) == −1``, so it needs **BD** — a published implementation
    of this used ``CD`` there, which is a different quantity and a different
    predicate. Cleared of denominators: ``AC·BD + AD·BC == 0``.

    The four points must be collinear, and the signed ratios are read off an
    affine parameter along the line, which preserves cross ratio exactly.
    """
    a, b, d, e = (_point(c, name) for name in claim.of[:4])
    # The cross ratio needs four *distinct* points: with any two coincident its
    # numerator and denominator both vanish, and `0 + 0 == 0` reported the
    # degenerate range (A,A;A,A) as harmonic.
    names = [str(n) for n in claim.of[:4]]
    for i, first in enumerate((a, b, d, e)):
        for j, second in enumerate((a, b, d, e)):
            if i < j and first == second:
                raise _Unresolved(
                    f"a harmonic range needs four distinct points; "
                    f"{names[i]} and {names[j]} coincide")
    scale = _scale_of(a, b, d, e)
    dx, dy = b.x - a.x, b.y - a.y
    for other in (d, e):
        area2 = dx * (other.y - a.y) - (other.x - a.x) * dy
        if not _is_zero(area2, scale):
            raise _Unresolved("harmonic needs four collinear points")

    def parameter(p: Point) -> Exact:
        return (p.x - a.x) * dx + (p.y - a.y) * dy

    ta, tb, tc, td = (parameter(p) for p in (a, b, d, e))
    return _is_zero((tc - ta) * (td - tb) + (td - ta) * (tc - tb)), "harmonic"


#: How many arguments each claim needs: ``(minimum, maximum or None)``.
#:
#: Checked before dispatch, because the predicates read ``claim.of`` positionally
#: and an argument that is not there raises out of an unpacking rather than
#: returning a finding — `midpoint` with one name came back as a ValueError
#: through the MCP tool instead of an error a caller could act on. Arity is part
#: of what a claim *is*, so it belongs beside the table that names them.
ARITY: dict[str, tuple[int, int | None]] = {
    "on": (2, 2),
    "collinear": (3, 3),
    "parallel": (2, 2),
    "perpendicular": (2, 2),
    "congruent": (2, None),
    "midpoint": (3, 3),
    "equilateral": (1, 1),
    "tangent": (2, 2),
    "concurrent": (3, None),
    "ratio": (1, 1),
    "golden": (1, 1),
    "harmonic": (4, 4),
}

#: Every claim this version can decide. The table is the documented vocabulary.
CLAIMS: dict[str, Callable[[Construction, Claim], tuple[bool, str]]] = {
    "on": _on,
    "collinear": _collinear,
    "parallel": _parallel,
    "perpendicular": _perpendicular,
    "congruent": _congruent,
    "midpoint": _midpoint,
    "equilateral": _equilateral,
    "tangent": _tangent,
    "concurrent": _concurrent,
    "ratio": _ratio,
    "golden": _golden,
    "harmonic": _harmonic,
}


def _box(c: Construction, claim: Claim) -> tuple[float, float, float, float] | None:
    """Where on the drawing the claim is about, when that can be pinned down."""
    xs: list[float] = []
    ys: list[float] = []

    def collect(name: Any) -> None:
        if isinstance(name, (list, tuple)):
            for inner in name:
                collect(inner)
            return
        element = c[str(name)] if str(name) in c else None
        if element is None:
            return
        geometry = element.geometry
        points: Sequence[Point] = ()
        if isinstance(geometry, Point):
            points = (geometry,)
        elif isinstance(geometry, Circle):
            points = (geometry.center,)
        elif isinstance(geometry, (Section, Polygon)):
            points = geometry.points
        elif isinstance(geometry, Line):
            # A line has no extent of its own — it runs to the frame. The two
            # points that defined it are where a reader should be sent, so a
            # claim about two lines still says *where* rather than only *what*.
            points = tuple(c[parent].geometry for parent in element.parents
                           if parent in c
                           and isinstance(c[parent].geometry, Point))
        for point in points:
            x, y = point.as_floats()
            xs.append(x)
            ys.append(y)

    for arg in claim.of:
        collect(arg)
    if not xs:
        return None
    return (min(xs), max(xs), min(ys), max(ys))


def check(construction: Construction, claims: Sequence[Any]) -> list[Finding]:
    """Decide every claim. Findings for the ones that do not hold.

    A holding claim is silent, which is the same contract :func:`straightedge.qc.check`
    keeps: findings are defects, and an empty list means nothing is wrong.
    """
    findings: list[Finding] = []
    for raw in claims:
        try:
            claim = Claim.parse(raw)
        except ValueError as exc:
            findings.append(Finding("claim:malformed", "error", str(exc)))
            continue

        predicate = CLAIMS.get(claim.kind)
        if predicate is None:
            findings.append(Finding(
                f"claim:{claim.kind}", "error",
                f"unknown claim {claim.kind!r}; known claims are "
                f"{', '.join(sorted(CLAIMS))}", str(claim)))
            continue

        low, high = ARITY[claim.kind]
        if len(claim.of) < low or (high is not None and len(claim.of) > high):
            expected = f"{low}" if high == low else (
                f"{low} or more" if high is None else f"{low} to {high}")
            findings.append(Finding(
                f"claim:{claim.kind}", "error",
                f"takes {expected} argument(s), got {len(claim.of)}",
                str(claim)))
            continue

        try:
            holds, description = predicate(construction, claim)
        except _Unresolved as exc:
            # An assertion about something absent is a failed assertion, not a
            # skipped one: passing it would report a construction as verified
            # against a claim nothing in it was ever checked by.
            findings.append(Finding(f"claim:{claim.kind}", "error",
                                    f"cannot be decided — {exc}", str(claim)))
            continue
        except PrecisionError as exc:
            findings.append(Finding(
                f"claim:{claim.kind}", "warn",
                f"could not be certified: {exc.message}. "
                f"The drawing is unchanged; this claim is neither proved nor "
                f"disproved.", str(claim), _box(construction, claim)))
            continue

        if not holds:
            findings.append(Finding(
                f"claim:{claim.kind}", "error",
                f"the construction does not satisfy this: it is not {description}",
                str(claim), _box(construction, claim)))
    return findings


# ---------------------------------------------------------------------------
# Marks: what a proved claim earns on the drawing
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Mark:
    """One conventional annotation, in construction coordinates.

    A right-angle square, a tick on a segment, a chevron on a parallel. These
    are the marks a geometry figure has always carried, and here they are drawn
    **only for claims that were proved** — so the square at a corner is evidence
    rather than decoration. Every other tool draws them because a human asserted
    them; this one draws them because the arithmetic decided.

    Positions are construction coordinates and directions are *toward* points,
    not vectors: a mark has to be a fixed size on the page whatever the drawing
    is scaled to, so the renderer normalises in screen space. Sizing here would
    make a right angle on a 200-unit figure invisible and one on a unit figure
    enormous.
    """

    kind: str                       # "right_angle" | "tick" | "chevron"
    at: Point                       # where it sits
    toward_a: Point                 # first direction
    toward_b: Point                 # second direction
    count: int = 1                  # tick/chevron multiplicity, to group them
    label: str = ""                 # the claim it came from


def _midpoint(a: Point, b: Point) -> Point:
    return Point((a.x + b.x) / 2, (a.y + b.y) / 2)


def _is_drawn(c: Construction, segment: Segment) -> bool:
    """Is there ink where this segment is?

    A tick sits on a segment, and a segment is not an element — it exists only
    where a drawn line passes through both ends, or where two adjacent corners of
    a drawn polygon are. Claiming `congruent` on four radii that were never drawn
    put four dashes in the middle of empty space, which reads as a rendering
    fault rather than as a proof.

    So a mark needs something to be a mark *on*. The claim still holds and is
    still reported; it simply earns no annotation, because there is nothing on
    the page for the annotation to sit against.
    """
    for element in c:
        geometry = element.geometry
        if isinstance(geometry, Line):
            if geometry.contains(segment.start) and geometry.contains(segment.end):
                return True
        elif isinstance(geometry, Polygon):
            points = geometry.points
            for i, corner in enumerate(points):
                nxt = points[(i + 1) % len(points)]
                if ((corner == segment.start and nxt == segment.end)
                        or (corner == segment.end and nxt == segment.start)):
                    return True
    return False


def _marks_for(c: Construction, claim: Claim, group: int) -> list[Mark]:
    """The marks one *proved* claim earns. Never called for a claim that failed."""
    kind = claim.kind
    tag = str(claim)

    if kind == "perpendicular":
        from .model import intersect_lines
        one, two = (_line(c, name) for name in claim.of[:2])
        meeting = intersect_lines(one, two)
        if not meeting:
            return []                       # perpendicular and parallel at once
        corner = meeting[0]
        # A point along each line, to give the square its two directions.
        along_one = Point(corner.x - one.b, corner.y + one.a)
        along_two = Point(corner.x - two.b, corner.y + two.a)
        return [Mark("right_angle", corner, along_one, along_two, label=tag)]

    if kind == "parallel":
        one, two = (_line(c, name) for name in claim.of[:2])
        out = []
        for line in (one, two):
            # A point on the line, and a second to give its direction.
            base = Point(-line.a * line.c / (line.a * line.a + line.b * line.b),
                         -line.b * line.c / (line.a * line.a + line.b * line.b))
            out.append(Mark("chevron", base,
                            Point(base.x - line.b, base.y + line.a), base,
                            group, tag))
        return out

    if kind in ("congruent", "equilateral", "midpoint"):
        segments = [seg for seg in _segments_of(c, claim) if _is_drawn(c, seg)]
        return [Mark("tick", _midpoint(seg.start, seg.end), seg.start, seg.end,
                     group, tag) for seg in segments]
    return []


def _segments_of(c: Construction, claim: Claim) -> list[Segment]:
    if claim.kind == "congruent":
        return [_segment(c, spec) for spec in claim.of]
    if claim.kind == "midpoint":
        m, a, b = (_point(c, name) for name in claim.of[:3])
        return [Segment(a, m), Segment(m, b)]
    geometry = _element(c, claim.of[0])
    return list(geometry.sides) if isinstance(geometry, Polygon) else []


def marks(construction: Construction, claims: Sequence[Any]) -> list[Mark]:
    """Marks for every claim that holds, and nothing for one that does not.

    A claim that fails already blocks the drawing, and one that could not be
    certified must not be dressed up as proved — an uncertified right angle is
    exactly the confident falsehood the lane refuses. So the check runs first
    and only silence earns a mark.

    Groups are numbered so two independent congruences read apart: one pair gets
    single ticks, the next double, the way they are drawn on paper.
    """
    out: list[Mark] = []
    group = 0
    for raw in claims:
        try:
            claim = Claim.parse(raw)
        except ValueError:
            continue
        if claim.kind not in CLAIMS or check(construction, [claim]):
            continue                        # failed, warned, or unknown
        # Only a claim that *draws* groups consumes a group number. Counting
        # every proved claim let `perpendicular` — which draws a square and no
        # ticks — take group 1, so the first congruence was drawn with two
        # strokes and the reader had to look for a single-tick pair that was
        # never there. The number is a visual grouping, not a claim index.
        try:
            produced = _marks_for(construction, claim, group + 1)
        except (_Unresolved, PrecisionError):
            continue
        if any(m.kind in ("tick", "chevron") for m in produced):
            group += 1
        out.extend(produced)
    return _nudged(out)


def _nudged(found: list[Mark]) -> list[Mark]:
    """Move a tick off a right-angle corner it would be drawn on top of.

    A segment's tick sits at its midpoint, and in the vesica the midpoint of
    `AB` *is* the corner where the bisector crosses it — so the congruence tick
    and the right-angle square landed in the same place. Both are correct and
    together they are unreadable. The tick slides along its own segment, which
    keeps it on the thing it is marking.
    """
    corners = [m.at for m in found if m.kind == "right_angle"]
    if not corners:
        return found
    out: list[Mark] = []
    for mark in found:
        if mark.kind == "tick" and any(mark.at == corner for corner in corners):
            # A quarter of the way toward one end: clear of the corner, still
            # unambiguously on this segment rather than a neighbouring one.
            end = mark.toward_b
            shifted = Point((mark.at.x * 3 + end.x) / 4, (mark.at.y * 3 + end.y) / 4)
            out.append(Mark(mark.kind, shifted, mark.toward_a, mark.toward_b,
                            mark.count, mark.label))
        else:
            out.append(mark)
    return out
