"""Drawing a construction — the first place any of this becomes visible.

Two rules borrowed from the classical tradition, and both are about what a
drawing is *for*. A circle is drawn whole rather than clipped to the arc that
happened to matter, and a line runs to the edge of the frame rather than stopping
at the last point on it. A construction is an argument about relationships, and a
clipped element hides the relationships it is not currently being used for — the
next step is very often the one that needs them.

Rendering is in floats, and that is not a retreat from the exact model. The model
is exact so that *claims* about it can be decided; a viewBox is a question about
pixels, and pixels are floats. What must never happen is the reverse — deciding a
claim from what a float said — and nothing here does that.

    >>> from .model import Construction
    >>> c = Construction()
    >>> a, b = c.set_point(0, 0), c.set_point(1, 0)
    >>> _ = c.construct_circle(a, b); _ = c.construct_circle(b, a)
    >>> to_svg(c).startswith("<svg")
    True
"""

from __future__ import annotations

from typing import Sequence

from ..diagrams.renderer import (
    circle as svg_circle,
    fit_text,
    path,
    style,
    svg_document,
    text,
    text_width,
)
from .model import Circle, Construction, Element, Line, Point, Polygon

__all__ = ["to_svg", "to_svg_steps", "DEFAULT_WIDTH"]

DEFAULT_WIDTH = 640
MIN_HEIGHT = 160
MAX_HEIGHT = 900
PAD_FRACTION = 0.14
POINT_R = 3.4
LABEL_PX = 13.0
TITLE_PX = 16.0
MARGIN = 14.0

# Plain hex, not `var(--ink, …)`. The CSS-custom-property convention two other
# templates use reads well in a browser and is unrenderable anywhere else:
# cairosvg parses `var(` as a hex literal and raises, so those figures produce no
# raster at all rather than the wrong colour. Themability survives without it —
# the class names below are the override surface, and a host stylesheet reaches
# them exactly as it would a custom property.
INK = "#1f2933"
MUTED = "#6b7a8d"
LINE = "#c9d3de"
ACCENT = "#2f7d72"

_CSS = f"""
.gc-line{{stroke:{LINE};stroke-width:1.4;fill:none}}
.gc-circle{{stroke:{ACCENT};stroke-width:1.5;fill:none}}
.gc-guide{{stroke:{MUTED};stroke-width:1.1;fill:none;stroke-dasharray:5 4;opacity:0.75}}
.gc-point{{fill:{INK};stroke:none}}
.gc-given{{fill:{ACCENT};stroke:none}}
.gc-label{{font-size:{LABEL_PX}px;fill:{INK}}}
.gc-title{{font-size:{TITLE_PX}px;font-weight:600;fill:{INK}}}
text{{font-family:'Noto Sans SC',Helvetica,Arial,sans-serif}}
"""


class _Viewport:
    """Construction coordinates in, pixel coordinates out.

    The y axis flips: mathematics counts upward and SVG counts downward, and
    forgetting that draws every construction upside down while every distance in
    it stays correct — which is exactly the kind of wrong a test on lengths does
    not catch.
    """

    __slots__ = ("x0", "y0", "x1", "y1", "scale", "width", "height", "top")

    def __init__(self, bounds: tuple[float, float, float, float], width: int,
                 top: float = 0.0) -> None:
        self.top = top
        x0, y0, x1, y1 = bounds
        span_x = max(x1 - x0, 1e-9)
        span_y = max(y1 - y0, 1e-9)
        pad = PAD_FRACTION * max(span_x, span_y)
        self.x0, self.y0 = x0 - pad, y0 - pad
        self.x1, self.y1 = x1 + pad, y1 + pad
        self.width = width
        self.scale = width / (self.x1 - self.x0)
        raw = (self.y1 - self.y0) * self.scale
        self.height = min(max(raw, MIN_HEIGHT), MAX_HEIGHT)
        if raw > MAX_HEIGHT:                       # very tall: refit to the cap
            self.scale = MAX_HEIGHT / (self.y1 - self.y0)
            self.width = width

    def project(self, x: float, y: float) -> tuple[float, float]:
        """Construction units to pixels, y flipped and the title's band skipped."""
        return ((x - self.x0) * self.scale,
                self.top + self.height - (y - self.y0) * self.scale)

    @property
    def box(self) -> tuple[float, float, float, float]:
        return (self.x0, self.y0, self.x1,
                self.y0 + self.height / self.scale)


def _line_endpoints(line: Line, view: _Viewport) -> tuple[tuple[float, float],
                                                          tuple[float, float]] | None:
    """Where ``a·x + b·y + c == 0`` leaves the visible box, in construction units."""
    a, b, c = float(line.a), float(line.b), float(line.c)
    x0, y0, x1, y1 = view.box
    span = max(x1 - x0, y1 - y0)
    tol = span * 1e-9
    hits: list[tuple[float, float]] = []
    if abs(b) > 1e-12:
        for x in (x0, x1):
            hits.append((x, -(a * x + c) / b))
    if abs(a) > 1e-12:
        for y in (y0, y1):
            hits.append((-(b * y + c) / a, y))
    inside = [(x, y) for x, y in hits
              if x0 - tol <= x <= x1 + tol and y0 - tol <= y <= y1 + tol]
    unique: list[tuple[float, float]] = []
    for candidate in inside:
        if not any(abs(candidate[0] - kept[0]) < tol and abs(candidate[1] - kept[1]) < tol
                   for kept in unique):
            unique.append(candidate)
    return (unique[0], unique[1]) if len(unique) >= 2 else None


def _label_position(px: float, py: float, label: str, view: _Viewport) -> tuple[float, str]:
    """Offset a label off its point, and keep it on the canvas.

    Uses the shared measurement rather than a guess at the width, so a label near
    the right edge flips to the other side of its point instead of running off.
    """
    width = text_width(label, LABEL_PX, safe=True)
    if px + 8 + width <= view.width - MARGIN:
        return px + 8, "start"
    return px - 8, "end"


def _draw_element(element: Element, view: _Viewport, labels: bool,
                  guides: str) -> list[str]:
    geometry = element.geometry
    if element.guide and guides == "hidden":
        return []
    klass = "gc-guide" if element.guide else None
    out: list[str] = []

    if isinstance(geometry, Point):
        px, py = view.project(*geometry.as_floats())
        given = "intersection" not in element.classes
        out.append(svg_circle(round(px, 2), round(py, 2), POINT_R,
                              **{"class": "gc-given" if given else "gc-point"}))
        if labels:
            lx, anchor = _label_position(px, py, element.id, view)
            out.append(text(round(lx, 2), round(py - 7, 2),
                            fit_text(element.id, view.width, LABEL_PX),
                            text_anchor=anchor, **{"class": "gc-label"}))
        return out

    if isinstance(geometry, Line):
        ends = _line_endpoints(geometry, view)
        if ends is None:
            return []
        (ax, ay), (bx, by) = ends
        sx, sy = view.project(ax, ay)
        ex, ey = view.project(bx, by)
        out.append(path(f"M {sx:.2f} {sy:.2f} L {ex:.2f} {ey:.2f}",
                        **{"class": klass or "gc-line"}))
        return out

    if isinstance(geometry, Circle):
        cx, cy = view.project(*geometry.center.as_floats())
        r = max(float(geometry.radius_sq), 0.0) ** 0.5 * view.scale
        out.append(svg_circle(round(cx, 2), round(cy, 2), round(r, 2),
                              **{"class": klass or "gc-circle"}))
        return out

    if isinstance(geometry, Polygon):
        pts = [view.project(*p.as_floats()) for p in geometry.points]
        d = " ".join(f"{'M' if i == 0 else 'L'} {x:.2f} {y:.2f}"
                     for i, (x, y) in enumerate(pts)) + " Z"
        out.append(path(d, **{"class": klass or "gc-line"}))
        return out

    return []      # Segment and Section carry no ink of their own


def _render(elements: Sequence[Element], bounds: tuple[float, float, float, float],
            width: int, labels: bool, guides: str, title: str) -> str:
    top = MARGIN + TITLE_PX if title else 0.0
    view = _Viewport(bounds, width, top)
    body: list[str] = ["<defs>" + style(_CSS) + "</defs>"]
    if title:
        body.append(text(MARGIN, MARGIN + TITLE_PX - 4,
                         fit_text(title, width - 2 * MARGIN, TITLE_PX, bold=True),
                         **{"class": "gc-title"}))

    # Curves first, points and their labels above them: a point drawn under the
    # circle that produced it is the one thing a reader most needs to see.
    ordered = sorted(elements, key=lambda e: isinstance(e.geometry, Point))
    for element in ordered:
        body.extend(_draw_element(element, view, labels, guides))

    return svg_document("".join(body), width=int(view.width),
                        height=int(view.height + top),
                        class_name="diagram construction")


def to_svg(construction: Construction, *, width: int = DEFAULT_WIDTH,
           labels: bool = True, guides: str = "dashed", title: str = "") -> str:
    """The whole construction, as one SVG."""
    return _render(construction.steps, construction.limits(), width,
                   labels, guides, title)


def to_svg_steps(construction: Construction, *, width: int = DEFAULT_WIDTH,
                 labels: bool = True, guides: str = "dashed",
                 title: str = "") -> list[str]:
    """One SVG per step, each showing everything drawn so far.

    The frame is fixed across the whole sequence — taken from the finished
    construction, not from each prefix — so the drawing grows into a stable
    picture instead of the viewBox lurching on every step. That fixed frame is
    also what lets the sequence become animation beats in the video lane without
    a camera move nobody asked for.
    """
    bounds = construction.limits()
    steps = construction.steps
    return [_render(steps[:i + 1], bounds, width, labels, guides, title)
            for i in range(len(steps))]
