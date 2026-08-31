"""Deterministic visual checks on a built scene.

The smoke tests already answer *"does it run"* — LaTeX compiles, primitive
signatures match, ``c2p`` gets the right dimensions. They say nothing about
whether the result is worth looking at, and that is a different failure mode
entirely: a scene can render perfectly and still ship a label sitting on top of
another label, or a curve two-thirds outside its axes.

Every check here comes from a defect that reached a finished video and was only
caught by a human opening the frame and looking:

===========================  ==================================================
check                        what it caught
===========================  ==================================================
``empty``                    a figure that drew grid and axes and no data
``out_of_frame``             curves clipped on x but not y, leaving the plot
``text_overlap``             two curve labels printed on the same spot
``text_clipped``             a verdict mark pushed past the right-hand edge
``text_obscured``            a stroke drawn straight through a formula
===========================  ==================================================

That list is the argument for this module existing. An author iterating on their
own video re-renders and squints; an educator who typed a prompt will not, so
whatever the human eye was doing has to happen here instead.

**The core is Manim-free.** :func:`check` operates on plain :class:`Box` values,
so it is unit-testable without Manim and can be lifted out of this repo
unchanged. Only :func:`boxes_from_scene` and :func:`frame_from_scene` know what
a Mobject or a camera is — and both duck-type rather than import. The one
package import below is :mod:`straightedge.aspect`, which is a table of numbers
with no dependencies of its own.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

from straightedge.aspect import LANDSCAPE, FRAME_UNITS

#: Manim CE's default landscape frame. Taken from :mod:`straightedge.aspect`
#: rather than restated, because a scene is composed against that table and
#: judged against this constant: if the two ever disagreed, QC would pass a
#: scene that is clipped and fail one that is fine, which is worse than not
#: checking. A scene that overrides its frame — as the 9:16 cuts do — should be
#: measured with :func:`frame_from_scene` instead.
DEFAULT_FRAME = FRAME_UNITS[LANDSCAPE]

#: Fraction of the smaller text box that two texts may share before it reads as
#: a collision rather than kerning. Deliberately small: the failure being caught
#: is legibility, and text is unreadable long before it is half-covered.
_OVERLAP_TOLERANCE = 0.06

#: How far a mobject may sit outside the frame before it counts as clipped.
#: Strokes are drawn with width, and Manim's own arrowheads sit a hair proud of
#: their nominal extent, so an exact bound produces false positives.
_EDGE_TOLERANCE = 0.05


@dataclass(frozen=True)
class Box:
    """An axis-aligned extent in scene units, plus what kind of thing it is.

    ``kind`` drives severity rather than detection: text over text is a defect,
    text over a stroke is usually a defect, and two strokes crossing is just a
    graph. Nothing here needs to know it came from Manim.

    ``path`` is where the mark's ink actually is, as one or more polylines in
    scene units. It exists because a rectangle is a terrible description of a
    curve: a parabola drawn across a plot has a bounding box covering the whole
    plot, and judging by that box alone reports every label inside the axes as
    obscured by it. Measured on a real render, that one confusion produced 31 of
    39 findings — enough noise to stop anyone reading the other 8, which were
    real.

    Empty means "the box is the ink", which is the truth for text and for filled
    shapes, and the safe assumption for anything we could not read. Box-only
    callers therefore keep exactly the behaviour they had.
    """

    label: str
    x0: float
    x1: float
    y0: float
    y1: float
    kind: str = "mark"          # "text" | "mark"
    path: tuple[tuple[tuple[float, float], ...], ...] = ()

    @property
    def width(self) -> float:
        return max(self.x1 - self.x0, 0.0)

    @property
    def height(self) -> float:
        return max(self.y1 - self.y0, 0.0)

    @property
    def area(self) -> float:
        return self.width * self.height

    def intersection(self, other: "Box") -> tuple[float, float, float, float] | None:
        """The shared rectangle as ``(x0, x1, y0, y1)``, or ``None`` if disjoint."""
        x0, x1 = max(self.x0, other.x0), min(self.x1, other.x1)
        y0, y1 = max(self.y0, other.y0), min(self.y1, other.y1)
        return (x0, x1, y0, y1) if x1 > x0 and y1 > y0 else None

    def intersection_area(self, other: "Box") -> float:
        shared = self.intersection(other)
        return (shared[1] - shared[0]) * (shared[3] - shared[2]) if shared else 0.0


@dataclass(frozen=True)
class Finding:
    """One defect. ``error`` should block delivery; ``warn`` informs.

    ``box`` is where on the frame the defect is — the ``(x0, x1, y0, y1)`` extent,
    in scene units, of the thing the finding is *about* (the clipped label, the
    obscured text). It is what turns "the caption is unreadable" into "the caption
    at these coordinates is unreadable", which is the difference between an agent
    that can move it and one that can only be told it is broken. ``None`` when the
    finding has no single location — an empty scene, an unreadable sidecar.
    """

    check: str
    severity: str               # "error" | "warn"
    message: str
    label: str | None = None
    box: tuple[float, float, float, float] | None = None

    def __str__(self) -> str:   # pragma: no cover - trivial
        where = f" [{self.label}]" if self.label else ""
        return f"[{self.severity}] {self.check}{where}: {self.message}"


def check(
    boxes: Sequence[Box],
    *,
    frame: tuple[float, float] = DEFAULT_FRAME,
    edge_tolerance: float = _EDGE_TOLERANCE,
    overlap_tolerance: float = _OVERLAP_TOLERANCE,
) -> list[Finding]:
    """Every visual defect this module knows how to see.

    Findings, never mutations — the caller decides whether an ``error`` blocks
    delivery or triggers a fallback.
    """
    findings: list[Finding] = []
    findings += _check_empty(boxes)
    findings += _check_frame(boxes, frame, edge_tolerance)
    findings += _check_overlaps(boxes, overlap_tolerance)
    return findings


def _check_empty(boxes: Sequence[Box]) -> list[Finding]:
    """A scene with nothing in it, or nothing with any extent.

    The shipped instance of this drew a full coordinate plane — grid, axes,
    ticks, a title — and no curve, because the curve spec used a key the
    template did not read. Several kilobytes of chrome and no content.
    """
    # Extent, not area: a level or plumb stroke is zero-area however long it
    # is, and a number line or a bare grid of such strokes is a drawn scene.
    # Same reasoning as the frame check below, which stopped skipping on area
    # for exactly this shape of mark.
    drawn = [b for b in boxes if b.width > 1e-9 or b.height > 1e-9]
    if not drawn:
        return [Finding("empty", "error",
                        "nothing with any extent was drawn"
                        f" ({len(boxes)} mobject(s) present)")]
    return []


def _check_frame(
    boxes: Sequence[Box], frame: tuple[float, float], tol: float
) -> list[Finding]:
    half_w, half_h = frame[0] / 2.0, frame[1] / 2.0
    findings: list[Finding] = []
    for box in boxes:
        # A point has nothing to clip; a line does. Skipping on *area* skipped
        # every axis-aligned stroke, because a level line is zero-area however
        # long it is — and axis-aligned is what a guide, an axis, a gridline or
        # a connector usually is. `matrix_transform` drew its eigenvector ray
        # from x=192 to x=477 on a 460-wide canvas and this loop said nothing.
        if box.width <= 1e-9 and box.height <= 1e-9:
            continue
        over = max(
            (-half_w - tol) - box.x0, box.x1 - (half_w + tol),
            (-half_h - tol) - box.y0, box.y1 - (half_h + tol),
        )
        if over <= 0:
            continue
        # A mobject entirely outside is a placement bug; one poking out is a
        # layout bug. Both are errors for text, which becomes unreadable either
        # way; a stroke leaving the frame is often deliberate.
        outside = (box.x1 < -half_w or box.x0 > half_w
                   or box.y1 < -half_h or box.y0 > half_h)
        severity = "error" if (box.kind == "text" or outside) else "warn"
        findings.append(Finding(
            "text_clipped" if box.kind == "text" else "out_of_frame",
            severity,
            f"extends {over:.2f} units beyond the {frame[0]:.2f}x{frame[1]:.2f} frame",
            box.label,
            box=(box.x0, box.x1, box.y0, box.y1),
        ))
    return findings


def _segment_hits_rect(
    p: tuple[float, float],
    q: tuple[float, float],
    box: Box,
) -> bool:
    """Liang-Barsky: does the segment ``p``-``q`` touch ``box`` at all?

    Clipping rather than testing endpoints, because the interesting case is a
    stroke that crosses a label without either end being near it — which is
    exactly what a curve does to an axis tick label.
    """
    dx, dy = q[0] - p[0], q[1] - p[1]
    t0, t1 = 0.0, 1.0
    for num, den in (
        (p[0] - box.x0, -dx),
        (box.x1 - p[0], dx),
        (p[1] - box.y0, -dy),
        (box.y1 - p[1], dy),
    ):
        if den == 0.0:
            if num < 0.0:
                return False        # parallel to this edge and outside it
            continue
        t = num / den
        if den < 0.0:
            if t > t1:
                return False
            t0 = max(t0, t)
        else:
            if t < t0:
                return False
            t1 = min(t1, t)
    return t0 <= t1


def _path_crosses(mark: Box, text: Box) -> bool:
    """Whether the mark's ink actually reaches into the text's box."""
    for polyline in mark.path:
        for start, end in zip(polyline, polyline[1:]):
            if _segment_hits_rect(start, end, text):
                return True
    return False


def _union_area(rects: Iterable[tuple[float, float, float, float]]) -> float:
    """Area covered by axis-aligned rectangles, counting shared parts once.

    The facets of one surface abut rather than overlap, so a plain sum would
    serve the motivating case — but marks that genuinely overlap would then push
    a label past 100% covered, and a percentage that can exceed 100 is not a
    number a reader can act on.
    """
    rects = list(rects)
    xs = sorted({x for rect in rects for x in rect[:2]})
    total = 0.0
    for left, right in zip(xs, xs[1:]):
        width = right - left
        if width <= 0:
            continue
        # Within one x-slab every rectangle spanning it contributes a plain
        # interval, so the 2-D union collapses to merging sorted intervals.
        reach = float("-inf")
        height = 0.0
        for y0, y1 in sorted((r[2], r[3]) for r in rects
                             if r[0] <= left and r[1] >= right):
            height += max(0.0, y1 - max(y0, reach))
            reach = max(reach, y1)
        total += width * height
    return total


@dataclass
class _Occurrence:
    """One kind of collision, however many mobject pairs produced it."""

    check: str
    severity: str
    subject: str                # the label the finding is reported against
    other: str
    crossed: bool               # phrased as a stroke through, not a percentage
    count: int = 0
    #: Extent of the subject label, so the finding can say *where* it is. The
    #: first one seen wins when a label names several physical boxes — the same
    #: string-collapse limit the count already documents.
    subject_box: tuple[float, float, float, float] | None = None
    #: text_overlap only: the worst single pair, as a fraction of the smaller box.
    worst: float = 0.0
    #: text_obscured only: per obscured text box, the shared rectangles covering
    #: it. Keyed by the box because one label can name several mobjects, and each
    #: physical label has its own coverage.
    shaded: dict[Box, list[tuple[float, float, float, float]]] = field(
        default_factory=dict)

    def percentage(self) -> float:
        """How covered the subject is.

        For ``text_obscured`` this is the union of everything shading the label
        divided by the label's own area — *not* the largest per-pair ratio. Those
        ratios are normalised by the smaller box, which for a many-facet surface
        is the facet: twenty facets each covering a tenth of a label each report
        a fifth of *themselves*, so a maximum reads "up to 20% covered" for a
        label that is entirely buried. Summing against the label is the only
        denominator that answers the question a reader is actually asking.
        """
        if self.check != "text_obscured":
            return self.worst
        return max((100.0 * _union_area(rects) / box.area
                    for box, rects in self.shaded.items() if box.area > 0),
                   default=0.0)

    def message(self) -> str:
        # The count is the point of collapsing, so it is never dropped — a
        # reader who wants the old per-pair listing can still see how many
        # there were, which a plain de-duplication would have thrown away. It
        # counts collisions, not locations: ten facets of one cone shading one
        # label is ten collisions in a single place.
        where = "" if self.count < 2 else f" ({self.count} collisions)"
        if self.crossed:
            return f"{self.other!r} is drawn through {self.subject!r}{where}"
        pct = self.percentage()
        if self.check == "text_overlap":
            # Still a maximum over pairs, so it keeps the hedge: the two boxes
            # are both text and neither is the obvious denominator.
            upto = "" if self.count < 2 else "up to "
            return (f"{self.subject!r} and {self.other!r} overlap by "
                    f"{upto}{pct:.0f}%{where}")
        # An exact coverage of one label, so no hedge — unless the label names
        # more than one mobject, when it is the worst of them.
        upto = "" if len(self.shaded) < 2 else "up to "
        return (f"{self.subject!r} is {upto}{pct:.0f}% covered by "
                f"{self.other!r}{where}")


def _check_overlaps(boxes: Sequence[Box], tolerance: float) -> list[Finding]:
    """Text sitting on something it cannot be read against.

    Collisions are collapsed by ``(check, subject, other, crossed)`` before being
    worded — ``crossed`` is in the key because a stroke drawn *through* a label
    is worded as such and has no percentage to merge with a box-overlap finding.
    A filled surface is built from many small mobjects — a cone is dozens of
    ``ThreeDVMobject`` quads — so one label resting on one cone used to report
    once per facet it touched: 34 findings for ``conic/cone_slice``, 43 of the
    74 warnings across the whole builder sweep. Every one was true and they
    described a single defect, which is the shape of noise that stops anyone
    reading findings at all.

    Grouping on the *labels* rather than the mobjects is what makes this work,
    and is also its limit: two genuinely different labels that happen to render
    the same string collapse together. The count keeps that visible instead of
    hiding it, and a caller wanting per-pair detail should read the boxes.
    """
    seen: dict[tuple[str, str, str, bool], _Occurrence] = {}
    # Extent, not area — the same filter as the empty and frame checks. On
    # area, every axis-aligned stroke was dropped before the pairing, so a
    # zero-height rule drawn straight through a label could never be reported.
    real = [b for b in boxes if b.width > 1e-9 or b.height > 1e-9]

    def entry_for(check: str, severity: str, subject: str, other: str,
                  crossed: bool, subject_box: Box) -> _Occurrence:
        key = (check, subject, other, crossed)
        entry = seen.get(key)
        if entry is None:
            entry = seen[key] = _Occurrence(
                check, severity, subject, other, crossed,
                subject_box=(subject_box.x0, subject_box.x1,
                             subject_box.y0, subject_box.y1))
        entry.count += 1
        return entry

    for i, a in enumerate(real):
        for b in real[i + 1:]:
            if a.kind != "text" and b.kind != "text":
                continue        # two strokes crossing is a graph, not a defect
            if a.kind != b.kind:
                text, other = (a, b) if a.kind == "text" else (b, a)
                if other.area <= 1e-9:
                    # A level or plumb stroke: the degenerate box *is* the ink,
                    # so ask the segment test directly. The rectangle pathway
                    # below cannot see it — a zero-area box intersects nothing
                    # and covers 0% of anything.
                    hit = (_path_crosses(other, text) if other.path else
                           _segment_hits_rect((other.x0, other.y0),
                                              (other.x1, other.y1), text))
                    if hit:
                        entry_for("text_obscured", "warn", text.label,
                                  other.label, True, text)
                    continue
            rect = a.intersection(b)
            if rect is None:
                continue
            shared = (rect[1] - rect[0]) * (rect[3] - rect[2])
            smaller = min(a.area, b.area)
            if smaller <= 0 or shared / smaller < tolerance:
                continue
            if a.kind == "text" and b.kind == "text":
                # Two texts colliding is symmetric, so the pair is sorted before
                # it becomes a key. Left in scan order, the same collision found
                # once as (A, B) and once as (B, A) survives as two findings —
                # the error-severity half of the noise this collapsing exists to
                # remove, and the shape 3d/cube_section reports.
                first, second = sorted((a.label, b.label))
                subject_box = a if a.label == first else b
                entry = entry_for("text_overlap", "error", first, second, False,
                                  subject_box)
                entry.worst = max(entry.worst, 100.0 * shared / smaller)
                continue

            text, other = (a, b) if a.kind == "text" else (b, a)
            # Overlapping boxes is the cheap test that says *maybe*. When the
            # mark told us where its ink is, ask that instead: a curve whose
            # bounding box swallows a label has usually not touched it.
            crossed = bool(other.path)
            if crossed and not _path_crosses(other, text):
                continue
            entry = entry_for("text_obscured", "warn", text.label, other.label,
                              crossed, text)
            entry.shaded.setdefault(text, []).append(rect)

    return [Finding(o.check, o.severity, o.message(), o.subject, box=o.subject_box)
            for o in seen.values()]


def check_sidecar(path: Path) -> list[Finding]:
    """Check the measurements a rendered scene left behind.

    The subprocess half of :func:`check`. A scene rendered with a QC sidecar
    (see :func:`~straightedge.templates.qc_tail_source`) writes its extents to
    ``path`` as it finishes; this reads them and applies the same checks a
    caller holding the live scene would.

    A sidecar that is missing or unreadable is reported as a ``warn``, never
    raised. The reasons a render produces no measurements — an older library on
    the render host, a scene written before the tail existed, a crash after the
    MP4 was already muxed — are all deployment facts about the *checker*, and
    none of them is evidence about the video. Turning them into an error would
    throw away finished renders over a check that never ran.
    """
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [Finding("sidecar", "warn",
                        f"no measurements to check: {exc}")]

    try:
        width, height = payload["frame"]
        boxes = [
            Box(label=b["label"], x0=b["x0"], x1=b["x1"],
                y0=b["y0"], y1=b["y1"], kind=b.get("kind", "mark"),
                # Absent in a sidecar written before strokes carried their ink.
                # Empty falls back to box overlap, which is the older, noisier
                # answer rather than a wrong one.
                path=tuple(tuple((float(x), float(y)) for x, y in line)
                           for line in b.get("path", ())))
            for b in payload["boxes"]
        ]
    except (KeyError, TypeError, ValueError) as exc:
        return [Finding("sidecar", "warn",
                        f"measurements are not in the expected shape: {exc!r}")]

    return check(boxes, frame=(float(width), float(height)))


def frame_from_scene(scene) -> tuple[float, float]:
    """The frame this scene is actually composed against, in scene units.

    Read from the scene's **camera**, not from ``config``. Verified against
    Manim CE 0.20.1 and re-verified on 0.21.0: assigning ``config.frame_height``
    does not survive — the camera keeps ``frame_width`` and recomputes the height
    from the output's pixel ratio. A 9:16 scene rendered at landscape pixels
    therefore reports a 9.0 x 5.06 frame, which is the truth about what the
    viewer will see and exactly the misconfiguration worth catching. Reading the
    declared 9.0 x 16.0 instead would call that scene well-composed while most of
    it sits off-screen.

    Worth re-checking on each Manim release rather than trusting this note: if
    the camera ever starts honouring the declared height, the vertical path is
    silently measuring the wrong frame and every 9:16 finding becomes wrong.

    Falls back to :data:`DEFAULT_FRAME` for a scene that exposes no camera, so a
    caller can always pass the result straight to :func:`check`.
    """
    camera = getattr(scene, "camera", None)
    width = getattr(camera, "frame_width", None)
    height = getattr(camera, "frame_height", None)
    if width is None or height is None:
        return DEFAULT_FRAME
    try:
        return float(width), float(height)
    except (TypeError, ValueError):
        return DEFAULT_FRAME


@dataclass(frozen=True)
class _Projection:
    """How a 3D scene turns world coordinates into what the viewer sees.

    Every check here judges a flat picture, and in a ``ThreeDScene`` the
    coordinates a mobject reports are not that picture. A cube's ``A`` at
    ``(x, y, 0)`` and ``A₁`` at ``(x, y, h)`` differ only in z, so measuring x
    and y alone made their boxes identical and reported a 100% overlap on labels
    the camera separates by a quarter of the frame. Across the builder sweep
    that mistake produced 80 of 106 warnings.

    The camera itself tracks the two kinds of mobject that must *not* be
    projected, which is what makes this tractable.
    """

    project: object             # (N, 3) array -> (N, 3) array, in frame units
    fixed_in_frame: object      # already frame coordinates; projecting is wrong
    fixed_orientation: object   # billboards: position projects, size does not


def _projection_for(scene) -> "_Projection | None":
    """``None`` for a 2D scene, where world and screen are the same thing."""
    camera = getattr(scene, "camera", None)
    project_points = getattr(camera, "project_points", None)
    if not callable(project_points):
        return None

    # ``project_points`` reads a cached rotation matrix that the renderer
    # refreshes per frame. Regenerating it once here means a caller measuring
    # outside the render loop gets the camera's real orientation rather than
    # whatever was left over — an identity matrix, in the case that matters,
    # which silently reproduces the unprojected bug this exists to fix.
    matrix = None
    generate = getattr(camera, "generate_rotation_matrix", None)
    if callable(generate):
        try:
            matrix = generate()
        except Exception:
            matrix = None

    def project(points):
        if matrix is None:
            return project_points(points)
        previous = getattr(camera, "rotation_matrix", None)
        camera.rotation_matrix = matrix
        try:
            return project_points(points)
        finally:
            camera.rotation_matrix = previous

    return _Projection(
        project=project,
        fixed_in_frame=getattr(camera, "fixed_in_frame_mobjects", None) or (),
        fixed_orientation=getattr(camera, "fixed_orientation_mobjects", None) or (),
    )


def _is_fixed(mobject, collection) -> bool:
    """Membership, tolerating a mobject that cannot be hashed or compared."""
    try:
        return mobject in collection
    except Exception:
        return False


def _projected_bounds(mobject, projection: "_Projection | None"):
    """``(x0, x1, y0, y1)`` as the viewer sees them, or ``None`` for the raw box.

    ``None`` is the answer whenever projecting would be wrong or impossible, so
    every fallback lands on exactly the behaviour a 2D scene already had.
    """
    if projection is None:
        return None
    if _is_fixed(mobject, projection.fixed_in_frame):
        return None
    try:
        if _is_fixed(mobject, projection.fixed_orientation):
            # Billboards turn to face the camera, so they keep their on-screen
            # size wherever they are; only the anchor point moves. Projecting
            # their glyph outlines instead would squash the label by whatever
            # angle the camera happens to sit at.
            centre = projection.project(mobject.get_center().reshape(1, 3))[0]
            half_w = float(mobject.width) / 2.0
            half_h = float(mobject.height) / 2.0
            return (float(centre[0]) - half_w, float(centre[0]) + half_w,
                    float(centre[1]) - half_h, float(centre[1]) + half_h)

        points = getattr(mobject, "points", None)
        if points is None or len(points) == 0:
            return None
        # Read row by row rather than by column slice: the result is a numpy
        # array from Manim, but nothing here should require that it is.
        flat = projection.project(points)
        xs = [float(row[0]) for row in flat]
        ys = [float(row[1]) for row in flat]
        return (min(xs), max(xs), min(ys), max(ys))
    except Exception:
        return None


def boxes_from_scene(scene, *, include_invisible: bool = False) -> list[Box]:
    """Read the extents of everything currently on a Manim scene.

    The only Manim-aware function here. Kept thin on purpose: the checks are
    the valuable part and they should stay portable.

    Nested groups are walked to their leaves — a ``VGroup``'s own bounding box
    spans its children, so checking the group would hide a single label that
    escaped while its siblings sat comfortably inside.
    """
    projection = _projection_for(scene)
    boxes: list[Box] = []
    for mobject in getattr(scene, "mobjects", []):
        boxes.extend(_boxes_from_mobject(mobject, include_invisible, projection))
    return boxes


def _boxes_from_mobject(
    mobject, include_invisible: bool, projection: "_Projection | None" = None,
) -> Iterable[Box]:
    # Text is atomic. Manim decomposes a Text or MathTex into one
    # ``VMobjectFromSVGPath`` per glyph, so descending first means every label
    # arrives as a pile of anonymous paths — no leaf is ever classified as text,
    # and the two overlap checks silently never fire. A label is also one thing
    # to a reader, so one box is the honest measurement.
    if _is_text(mobject):
        yield from _leaf_box(mobject, include_invisible, projection)
        return

    children = getattr(mobject, "submobjects", None)
    if children:
        for child in children:
            yield from _boxes_from_mobject(child, include_invisible, projection)
        return

    yield from _leaf_box(mobject, include_invisible, projection)


def _leaf_box(
    mobject, include_invisible: bool, projection: "_Projection | None" = None,
) -> Iterable[Box]:
    """One box for one drawable thing."""
    if not include_invisible and _is_invisible(mobject):
        return

    bounds = _projected_bounds(mobject, projection)
    if bounds is None:
        try:
            bounds = (float(mobject.get_left()[0]), float(mobject.get_right()[0]),
                      float(mobject.get_bottom()[1]), float(mobject.get_top()[1]))
        except Exception:   # a mobject with no spatial extent (e.g. a group stub)
            return
    left, right, bottom, top = bounds

    is_text = _is_text(mobject)
    yield Box(
        label=_label_for(mobject),
        x0=left, x1=right, y0=bottom, y1=top,
        kind="text" if is_text else "mark",
        path=() if is_text else _path_of(mobject, projection),
    )


#: Anchors kept per subpath. A stroke is checked by segment intersection, so the
#: polyline only has to follow the curve closely enough that no segment shortcuts
#: past a label — it does not have to reproduce it. Caps what a sidecar carries.
_MAX_ANCHORS_PER_SUBPATH = 128


def _path_of(
    mobject, projection: "_Projection | None" = None,
) -> tuple[tuple[tuple[float, float], ...], ...]:
    """Where this mark's ink is, as polylines — or ``()`` if the box is the ink.

    **Only for stroke-only marks.** A filled shape covers its interior, so its
    outline is the wrong thing to test against and its bounding box is roughly
    right. Reading fill as "no fill" when the attribute is missing would quietly
    downgrade filled shapes to outlines and lose real collisions, so anything
    unreadable falls back to the box.

    Anchors rather than all control points. Manim stores each cubic as four
    points — ``[anchor, handle, handle, anchor]`` — and only the anchors lie on
    the curve; the handles bow away from it and would report ink where none is
    drawn. Measured on a unit circle, sampling every third point picks handles
    reaching 3.5% outside the curve, while the anchors sit exactly on it.

    Subpath boundaries are honoured because a mobject like a pair of axes is one
    mobject and several disconnected strokes. Joining across the gap would draw
    a segment through the middle of the picture that nothing ever rendered.

    Projected for the same reason the box is: in a 3D scene an unprojected
    polyline traces a shape the viewer never sees, and the segment test would
    then be exact about the wrong geometry.
    """
    try:
        fill = getattr(mobject, "fill_opacity", None)
        if fill is None or float(fill) > 0.0:
            return ()
        subpaths = mobject.get_subpaths()
    except Exception:
        return ()

    flatten = None
    if projection is not None and not _is_fixed(mobject, projection.fixed_in_frame):
        flatten = projection.project
    stride = int(getattr(mobject, "n_points_per_curve", 4) or 4)

    polylines: list[tuple[tuple[float, float], ...]] = []
    for subpath in subpaths:
        try:
            size = len(subpath)
            if size < stride:
                continue
            # Start anchor of every cubic, plus the last cubic's end anchor. A
            # subpath is continuous, so each curve's end is the next one's start
            # and taking starts alone would drop only the final point.
            anchors = [subpath[i] for i in range(0, size, stride)]
            anchors.append(subpath[size - 1])
        except (IndexError, TypeError):
            continue
        if len(anchors) > _MAX_ANCHORS_PER_SUBPATH:
            step = len(anchors) // _MAX_ANCHORS_PER_SUBPATH + 1
            anchors = anchors[::step] + [anchors[-1]]
        if flatten is not None:
            try:
                anchors = flatten([[float(p[0]), float(p[1]), float(p[2])]
                                   for p in anchors])
            except Exception:
                return ()   # a half-projected path would be worse than none
        points = tuple((float(p[0]), float(p[1])) for p in anchors)
        if len(points) >= 2:
            polylines.append(points)
    return tuple(polylines)


def _is_text(mobject) -> bool:
    """True for anything the viewer reads rather than looks at.

    Matched by class name rather than ``isinstance`` so the module keeps working
    across Manim versions and does not need the import at all.
    """
    names = {cls.__name__ for cls in type(mobject).__mro__}
    return bool(names & {"Text", "Tex", "MathTex", "MarkupText", "SingleStringMathTex"})


def _is_invisible(mobject) -> bool:
    """Explicitly transparent — not merely silent about its opacity.

    ``None`` means "not set at this level", which is what a container that
    delegates rendering to its children reports: ``MathTex.fill_opacity`` is
    ``None`` because the per-glyph submobjects carry the fill. Reading that as
    zero drops every equation on the scene, and since dropped boxes cannot
    collide, it disables the overlap checks without failing anything.
    """
    fill = getattr(mobject, "fill_opacity", None)
    stroke = getattr(mobject, "stroke_opacity", None)
    if fill is None and stroke is None:
        return False
    return float(fill or 0.0) <= 0.0 and float(stroke or 0.0) <= 0.0


def _label_for(mobject) -> str:
    text = getattr(mobject, "text", None) or getattr(mobject, "tex_string", None)
    if text:
        flat = " ".join(str(text).split())
        return flat[:40]
    return type(mobject).__name__


def worst_severity(findings: Iterable[Finding]) -> str | None:
    """``"error"``, ``"warn"``, or ``None`` when the scene is clean."""
    seen = {f.severity for f in findings}
    for level in ("error", "warn"):
        if level in seen:
            return level
    return None
