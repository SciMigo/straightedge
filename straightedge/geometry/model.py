"""The construction itself: points, lines, circles, and what they make together.

A construction is an ordered record of two moves — *draw the line through these
two points* and *draw the circle on this centre through this point* — plus every
point those moves produce by crossing what is already there. Insertion order is
construction order, which is later the animation's beat order, so there is no
second list of steps to keep in agreement with the first.

Every coordinate is an :class:`~straightedge.geometry.exact.Exact`, so two points
are the same point when they are *exactly* the same point. That is what makes
deduplication meaningful: a circle re-drawn on the same centre through the same
point does not grow the model, and the intersections it would have contributed
are already there. Under floats that test is a tolerance, and a tolerance is a
guess.

Only two intersection routines are needed. Line-line is a determinant.
Line-circle drops a perpendicular from the centre and steps along the line by the
half-chord. Circle-circle needs no formula of its own: subtracting the two circle
equations leaves the *radical line*, and intersecting that with either circle
gives the same two points --- which is also why the answer is a line, and why two
circles meet at most twice.

    >>> c = Construction()
    >>> a = c.set_point(0, 0)
    >>> b = c.set_point(1, 0)
    >>> _ = c.construct_circle(a, b)
    >>> _ = c.construct_circle(b, a)
    >>> sorted(c.points)                      # the vesica, and its two new points
    ['A', 'B', 'C', 'D']

``parents`` and ``children`` are kept apart on purpose. A line's parents are the
two points that define it and nothing else; the points it later produces by
intersection are its *children*. Merging the two directions into one list is
what forces a consumer to guess which entries were the defining pair.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Iterable, Iterator, Sequence

from .exact import Exact, Tower

__all__ = [
    "Point",
    "Line",
    "Circle",
    "Segment",
    "Section",
    "Polygon",
    "Element",
    "Construction",
]

Number = int | Fraction | Exact


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Point:
    x: Exact
    y: Exact

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Point):
            return NotImplemented
        return (self.x - other.x).is_zero() and (self.y - other.y).is_zero()

    # Unhashable, for the reason `Exact.__hash__` records: equality here is
    # exact and a rounded-float hash does not agree with it. Nothing hashes a
    # Point, and a hash that silently loses membership is worse than none.
    __hash__ = None       # type: ignore[assignment]

    def as_floats(self) -> tuple[float, float]:
        return float(self.x), float(self.y)

    def __str__(self) -> str:
        return f"({self.x}, {self.y})"


@dataclass(frozen=True)
class Line:
    """``a·x + b·y + c == 0``, carrying the two points that defined it.

    Coefficients are normalised so that the same geometric line always compares
    equal however it was built: scaled to make the first non-zero of ``a``, ``b``
    equal to 1. Without that, the line through *A,B* and the line through *B,A*
    are the same line with negated coefficients, and the model would hold both.
    """

    a: Exact
    b: Exact
    c: Exact

    @classmethod
    def through(cls, p: Point, q: Point) -> "Line":
        a = q.y - p.y
        b = p.x - q.x
        c = q.x * p.y - p.x * q.y
        return cls(*_normalise_line(a, b, c))

    def evaluate(self, point: Point) -> Exact:
        """``a·x + b·y + c`` — zero exactly when the point is on the line."""
        return self.a * point.x + self.b * point.y + self.c

    def contains(self, point: Point) -> bool:
        return self.evaluate(point).is_zero()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Line):
            return NotImplemented
        return ((self.a - other.a).is_zero() and (self.b - other.b).is_zero()
                and (self.c - other.c).is_zero())

    # Unhashable, for the reason `Exact.__hash__` records: equality here is
    # exact and a rounded-float hash does not agree with it. Nothing hashes a
    # Line, and a hash that silently loses membership is worse than none.
    __hash__ = None       # type: ignore[assignment]


def _normalise_line(a: Exact, b: Exact, c: Exact) -> tuple[Exact, Exact, Exact]:
    pivot = a if not a.is_zero() else b
    if pivot.is_zero():
        return a, b, c              # degenerate; the caller rejects it
    return a / pivot, b / pivot, c / pivot


@dataclass(frozen=True)
class Circle:
    """Centre plus **squared** radius.

    Squared because the radius itself is often irrational when the square is
    not, and every predicate that matters --- on the circle, tangency, equal
    radii --- is stated in ``r²``. Taking the root to store it would adjoin a
    generator for a number nothing needs.
    """

    center: Point
    radius_sq: Exact

    @classmethod
    def through(cls, center: Point, point: Point) -> "Circle":
        dx, dy = point.x - center.x, point.y - center.y
        return cls(center, dx * dx + dy * dy)

    def contains(self, point: Point) -> bool:
        dx, dy = point.x - self.center.x, point.y - self.center.y
        return (dx * dx + dy * dy - self.radius_sq).is_zero()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Circle):
            return NotImplemented
        return (self.center == other.center
                and (self.radius_sq - other.radius_sq).is_zero())

    # Unhashable, for the reason `Exact.__hash__` records: equality here is
    # exact and a rounded-float hash does not agree with it. Nothing hashes a
    # Circle, and a hash that silently loses membership is worse than none.
    __hash__ = None       # type: ignore[assignment]


@dataclass(frozen=True)
class Segment:
    """Two points and the span between them. Length is kept squared, as above."""

    start: Point
    end: Point

    @property
    def length_sq(self) -> Exact:
        dx, dy = self.end.x - self.start.x, self.end.y - self.start.y
        return dx * dx + dy * dy


@dataclass(frozen=True)
class Section:
    """Three collinear points --- the object a ratio is asserted about.

    ``/ A B C /`` in the notation. A golden section is a claim *about* one of
    these, which is why it is a first-class element rather than a loose triple.
    """

    points: tuple[Point, Point, Point]

    @property
    def segments(self) -> tuple[Segment, Segment]:
        a, b, c = self.points
        return Segment(a, b), Segment(b, c)


@dataclass(frozen=True)
class Polygon:
    points: tuple[Point, ...]

    @property
    def sides(self) -> tuple[Segment, ...]:
        pts = self.points
        return tuple(Segment(pts[i], pts[(i + 1) % len(pts)])
                     for i in range(len(pts)))


Geometry = Point | Line | Circle | Segment | Section | Polygon


# ---------------------------------------------------------------------------
# Intersections
# ---------------------------------------------------------------------------


def intersect_lines(one: Line, two: Line) -> list[Point]:
    """The single crossing, or nothing when the lines are parallel or identical."""
    det = one.a * two.b - two.a * one.b
    if det.is_zero():
        return []
    x = (one.b * two.c - two.b * one.c) / det
    y = (two.a * one.c - one.a * two.c) / det
    return [Point(x, y)]


def intersect_line_circle(tower: Tower, line: Line, circle: Circle) -> list[Point]:
    """Where a line meets a circle: none, one (tangent), or two.

    Drop a perpendicular from the centre to the line to find the foot, then step
    along the line by the half-chord. The step needs ``√((r² − d²)/(a²+b²))``,
    which is where a construction adjoins new generators --- and why the field is
    a tower of *quadratic* extensions rather than anything larger.
    """
    norm = line.a * line.a + line.b * line.b
    if norm.is_zero():
        return []
    value = line.evaluate(circle.center)
    foot = Point(circle.center.x - line.a * value / norm,
                 circle.center.y - line.b * value / norm)
    # d² = value²/norm, so r² − d² scaled by norm avoids one division.
    discriminant = circle.radius_sq * norm - value * value
    sign = discriminant.sign()
    if sign < 0:
        return []
    if sign == 0:
        return [foot]
    step = tower.sqrt(discriminant / (norm * norm))
    return [Point(foot.x - line.b * step, foot.y + line.a * step),
            Point(foot.x + line.b * step, foot.y - line.a * step)]


def radical_line(one: Circle, two: Circle) -> Line | None:
    """The line through both intersections of two circles, or ``None``.

    Subtracting the circles' equations cancels ``x²`` and ``y²`` and leaves a
    linear one. It is defined whenever the centres differ --- even when the
    circles do not meet, in which case intersecting it with either finds nothing.
    """
    a = (two.center.x - one.center.x) * 2
    b = (two.center.y - one.center.y) * 2
    if a.is_zero() and b.is_zero():
        return None                                   # concentric
    c = ((one.center.x * one.center.x + one.center.y * one.center.y
          - one.radius_sq)
         - (two.center.x * two.center.x + two.center.y * two.center.y
            - two.radius_sq))
    return Line(*_normalise_line(a, b, c))


def intersect_circles(tower: Tower, one: Circle, two: Circle) -> list[Point]:
    line = radical_line(one, two)
    return [] if line is None else intersect_line_circle(tower, line, one)


# ---------------------------------------------------------------------------
# Elements and the construction
# ---------------------------------------------------------------------------


@dataclass
class Element:
    """One named thing in a construction, and where it came from.

    ``parents`` is what *defined* this element and never grows; ``children`` is
    what this element went on to produce. Keeping the two apart is the point ---
    with one bidirectional list, reading the defining pair back off a line means
    guessing which two of its entries came first.
    """

    id: str
    geometry: Geometry
    classes: tuple[str, ...] = ()
    parents: tuple[str, ...] = ()
    children: list[str] = field(default_factory=list)
    guide: bool = False

    @property
    def kind(self) -> str:
        return type(self.geometry).__name__.lower()


def _point_names() -> Iterator[str]:
    """``A``…``Z``, then ``AA``…, so a construction never runs out of labels."""
    from itertools import count, product
    from string import ascii_uppercase

    for width in count(1):
        for letters in product(ascii_uppercase, repeat=width):
            yield "".join(letters)


class Construction:
    """An ordered construction over one exact field.

    One :class:`~straightedge.geometry.exact.Tower` for the whole construction,
    shared by every coordinate in it — values from different constructions are
    elements of different fields and will refuse to combine.
    """

    def __init__(self, name: str = "construction") -> None:
        self.name = name
        self.tower = Tower()
        self._elements: dict[str, Element] = {}
        self._names = _point_names()

    # -- reading ---------------------------------------------------------
    def __len__(self) -> int:
        return len(self._elements)

    def __contains__(self, element_id: object) -> bool:
        return element_id in self._elements

    def __getitem__(self, element_id: str) -> Element:
        return self._elements[element_id]

    def __iter__(self) -> Iterator[Element]:
        """Insertion order, which *is* construction order."""
        return iter(self._elements.values())

    @property
    def steps(self) -> list[Element]:
        return list(self._elements.values())

    def _of_kind(self, kind: type) -> dict[str, Geometry]:
        return {e.id: e.geometry for e in self._elements.values()
                if isinstance(e.geometry, kind)}

    @property
    def points(self) -> dict[str, Point]:
        return self._of_kind(Point)          # type: ignore[return-value]

    @property
    def lines(self) -> dict[str, Line]:
        return self._of_kind(Line)           # type: ignore[return-value]

    @property
    def circles(self) -> dict[str, Circle]:
        return self._of_kind(Circle)         # type: ignore[return-value]

    # -- writing ---------------------------------------------------------
    def _exact(self, value: Number) -> Exact:
        return value if isinstance(value, Exact) else Exact.rational(value)

    def _next_point_name(self) -> str:
        for name in self._names:
            if name not in self._elements:
                return name
        raise RuntimeError("unreachable: the name generator is infinite")

    def _existing(self, geometry: Geometry) -> str | None:
        for element in self._elements.values():
            if type(element.geometry) is type(geometry) and element.geometry == geometry:
                return element.id
        return None

    def _add(self, geometry: Geometry, element_id: str | None,
             classes: Sequence[str], parents: Sequence[str],
             guide: bool) -> str:
        found = self._existing(geometry)
        if found is not None:
            # Re-drawing something already present is a no-op, not a duplicate.
            # Its intersections are in the model already, and adding a second
            # copy would make every one of them a duplicate too.
            return found
        name = element_id or (self._next_point_name() if isinstance(geometry, Point)
                              else self._structural_name(geometry, parents))
        if name in self._elements:
            raise ValueError(f"element id already in use: {name!r}")
        self._elements[name] = Element(name, geometry, tuple(classes),
                                       tuple(parents), [], guide)
        for parent in parents:
            if parent in self._elements:
                self._elements[parent].children.append(name)
        return name

    def _structural_name(self, geometry: Geometry, parents: Sequence[str]) -> str:
        joined = " ".join(parents)
        if isinstance(geometry, Line):
            return f"[ {joined} ]"
        if isinstance(geometry, Circle):
            return f"( {joined} )"
        if isinstance(geometry, Section):
            return f"/ {joined} /"
        if isinstance(geometry, Polygon):
            return f"< {joined} >"
        return f"{type(geometry).__name__} {joined}"

    def set_point(self, x: Number, y: Number, *, id: str | None = None,
                  classes: Sequence[str] = (), parents: Sequence[str] = (),
                  guide: bool = False) -> str:
        """A given point. Returns its id — the existing one if it is already there."""
        return self._add(Point(self._exact(x), self._exact(y)),
                         id, classes, parents, guide)

    def construct_line(self, first: str, second: str, *, id: str | None = None,
                       classes: Sequence[str] = (), guide: bool = False) -> str:
        p, q = self._require_point(first), self._require_point(second)
        if p == q:
            raise ValueError(
                f"a line needs two distinct points; {first} and {second} coincide")
        element_id = self._add(Line.through(p, q), id, classes, (first, second), guide)
        self._intersect_new(element_id)
        return element_id

    def construct_circle(self, center: str, through: str, *, id: str | None = None,
                         classes: Sequence[str] = (), guide: bool = False) -> str:
        c, p = self._require_point(center), self._require_point(through)
        if c == p:
            raise ValueError(
                f"a circle needs a radius; {center} and {through} coincide")
        element_id = self._add(Circle.through(c, p), id, classes, (center, through), guide)
        self._intersect_new(element_id)
        return element_id

    def set_section(self, a: str, b: str, c: str, *, id: str | None = None,
                    classes: Sequence[str] = ()) -> str:
        points = tuple(self._require_point(name) for name in (a, b, c))
        if not _collinear(*points):
            raise ValueError(f"a section needs three collinear points: {a} {b} {c}")
        return self._add(Section(points), id, classes, (a, b, c), False)

    def set_polygon(self, *names: str, id: str | None = None,
                    classes: Sequence[str] = ()) -> str:
        if len(names) < 3:
            raise ValueError("a polygon needs at least three points")
        points = tuple(self._require_point(name) for name in names)
        return self._add(Polygon(points), id, classes, names, False)

    def _require_point(self, name: str) -> Point:
        element = self._elements.get(name)
        if element is None:
            raise KeyError(f"no such element: {name!r}")
        if not isinstance(element.geometry, Point):
            raise TypeError(f"{name!r} is a {element.kind}, not a point")
        return element.geometry

    # -- intersection ----------------------------------------------------
    def _intersect_new(self, element_id: str) -> list[str]:
        """Cross a newly added line or circle with everything already drawn.

        Single-threaded and in insertion order, so the same construction produces
        the same points with the same names every time. A ``guide`` element takes
        part in nothing: it is scaffolding a reader is meant to see and the model
        is meant to ignore.
        """
        element = self._elements[element_id]
        if element.guide:
            return []
        found: list[str] = []
        for other in list(self._elements.values()):
            if other.id == element_id or other.guide:
                continue
            for point in self._crossings(element.geometry, other.geometry):
                found.append(self._add(point, None, ("intersection",),
                                       (element_id, other.id), False))
        return found

    def _crossings(self, one: Geometry, two: Geometry) -> list[Point]:
        if isinstance(one, Line) and isinstance(two, Line):
            return intersect_lines(one, two)
        if isinstance(one, Line) and isinstance(two, Circle):
            return intersect_line_circle(self.tower, one, two)
        if isinstance(one, Circle) and isinstance(two, Line):
            return intersect_line_circle(self.tower, two, one)
        if isinstance(one, Circle) and isinstance(two, Circle):
            return intersect_circles(self.tower, one, two)
        return []

    # -- lineage ---------------------------------------------------------
    def ancestors(self, element_id: str) -> list[str]:
        """Everything ``element_id`` was built from, nearest first.

        Walks ``parents`` only, with a seen-set, so a model that somehow holds a
        cycle returns a finite answer rather than recursing until the stack ends.
        """
        seen: set[str] = set()
        order: list[str] = []
        queue = list(self._elements[element_id].parents)
        while queue:
            current = queue.pop(0)
            if current in seen or current not in self._elements:
                continue
            seen.add(current)
            order.append(current)
            queue.extend(self._elements[current].parents)
        return order

    # -- extent ----------------------------------------------------------
    def limits(self) -> tuple[float, float, float, float]:
        """``(min_x, min_y, max_x, max_y)`` over every point and circle, as floats.

        Floats deliberately. A circle's extent is ``centre ± r``, and ``r`` is
        the square root of a stored ``r²`` — so an *exact* bound would adjoin a
        generator as a side effect of asking how big the drawing is, growing the
        field to answer a question about the viewBox. Measuring must not change
        what is being measured.
        """
        xs: list[float] = []
        ys: list[float] = []
        for element in self._elements.values():
            geometry = element.geometry
            if isinstance(geometry, Point):
                x, y = geometry.as_floats()
                xs.append(x)
                ys.append(y)
            elif isinstance(geometry, Circle):
                cx, cy = geometry.center.as_floats()
                r = max(float(geometry.radius_sq), 0.0) ** 0.5
                xs.extend((cx - r, cx + r))
                ys.extend((cy - r, cy + r))
        if not xs:
            return (0.0, 0.0, 1.0, 1.0)
        return (min(xs), min(ys), max(xs), max(ys))

    def __repr__(self) -> str:
        return (f"Construction({self.name!r}, {len(self._elements)} elements, "
                f"tower depth {self.tower.depth})")


def _collinear(a: Point, b: Point, c: Point) -> bool:
    """Twice the signed area of the triangle is zero."""
    return ((b.x - a.x) * (c.y - a.y) - (c.x - a.x) * (b.y - a.y)).is_zero()
