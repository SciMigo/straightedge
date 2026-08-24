"""Read an emitted SVG back as geometry, and check it the way a scene is checked.

The animation lane has measured its own frames since the beginning: builders
report boxes, ``qc.check`` finds labels sitting on each other or off the edge,
and a finding carries the coordinates of the defect. The figure lane had none of
that. Its only check was ``count_data_marks`` — "did anything get drawn" — so a
figure could place four labels in the same pixels and report success.

Three templates had grown a private version of this in their own test files,
each parsing the SVG and reconstructing text boxes by hand. Thirty-five had
nothing. This is that check, once, over the whole lane — and because it produces
:class:`~straightedge.qc.Box` values it feeds the *existing* checker rather than
a second one, so a figure and a scene report the same findings in the same shape.

    >>> from straightedge.diagrams import render_diagram
    >>> svg = render_diagram({"type": "unit_circle", "params": {"angle": 45}})
    >>> findings = check_figure(svg)
    >>> all(f.box is not None for f in findings)
    True

Every finding carries its ``box``, which is the difference between "this diagram
is wrong" and "this diagram is wrong *here*". That is the answer no diagram
generator returns today, and the only reason it is available is that the figure
lane computes its own geometry instead of asking a browser for it.

The measurement is the shared one — :func:`straightedge.diagrams.renderer.text_width`,
with its safety margin — so a label is judged by the width it may actually
resolve to rather than the width this host happens to render.
"""

from __future__ import annotations

import base64
import math
import re
import xml.etree.ElementTree as ET
from typing import Iterable
from urllib.parse import unquote

from ..qc import _EDGE_TOLERANCE, Box, Finding, check as check_boxes
from .renderer import text_width

__all__ = ["boxes_from_svg", "check_figure", "styles_from_svg", "unfilled_classes"]

_SVG = "{http://www.w3.org/2000/svg}"

#: Fallback when nothing says how big the text is. Most templates set a size
#: somewhere; this keeps an unstyled label from being measured as zero-width,
#: which would hide exactly the collision worth finding.
DEFAULT_FONT_PX = 12.0

_RULE = re.compile(r"([^{}]+)\{([^{}]*)\}")
#: `font: 600 18px 'Noto Sans SC', sans-serif` — a dozen templates use the
#: shorthand, so reading only `font-size` would measure them all at the default.
_SHORTHAND = re.compile(r"(?:(?P<weight>\d{3}|bold)\s+)?(?P<size>[\d.]+)px")
_SIZE = re.compile(r"font-size\s*:\s*([\d.]+)px")
_FILL_NONE = re.compile(r"fill\s*:\s*none")
_WEIGHT = re.compile(r"font-weight\s*:\s*(\d{3}|bold)")
_NUMBER = re.compile(r"-?\d*\.?\d+(?:[eE][-+]?\d+)?")

#: How many coordinate pairs follow each path command, and which of them are
#: points. An arc's first five numbers are radii and flags, not a position —
#: counting them as coordinates put phantom ink at (1, 0) on every figure with
#: a rounded corner.
_PATH_ARGS = {"M": 2, "L": 2, "T": 2, "H": 1, "V": 1,
              "C": 6, "S": 4, "Q": 4, "A": 7, "Z": 0}


def styles_from_svg(svg: str) -> dict[str, tuple[float, bool]]:
    """Class name to ``(font size in px, bold)``, read from the ``<style>`` block.

    Both spellings are handled. ``font-size: 13px`` is the obvious one;
    ``font: 600 18px 'Noto Sans SC', sans-serif`` is the one twelve templates
    actually use, and reading only the longhand would measure every label in
    them at the default size — under-measuring precisely the dense figures where
    collisions live.
    """
    out: dict[str, tuple[float, bool]] = {}
    for block in re.findall(r"<style[^>]*>(.*?)</style>", svg, re.S):
        for selectors, body in _RULE.findall(block):
            size = None
            bold = False
            found = _SIZE.search(body)
            if found:
                size = float(found.group(1))
            weight = _WEIGHT.search(body)
            if weight:
                bold = weight.group(1) in ("bold",) or int(weight.group(1)) >= 600
            if size is None:
                shorthand = _SHORTHAND.search(body)
                if shorthand and "font:" in body:
                    size = float(shorthand.group("size"))
                    raw = shorthand.group("weight")
                    bold = bool(raw) and (raw == "bold" or int(raw) >= 600)
            if size is None:
                continue
            for selector in selectors.split(","):
                name = selector.strip().lstrip(".").split()[-1] if selector.strip() else ""
                for part in name.split("."):
                    if part and not part.startswith(("#", "[")):
                        out[part] = (size, bold)
    return out


def unfilled_classes(svg: str) -> set[str]:
    """Classes whose rule says ``fill: none`` — outlines rather than surfaces."""
    out: set[str] = set()
    for block in re.findall(r"<style[^>]*>(.*?)</style>", svg, re.S):
        for selectors, body in _RULE.findall(block):
            if not _FILL_NONE.search(body):
                continue
            for selector in selectors.split(","):
                name = selector.strip().lstrip(".").split()[-1] if selector.strip() else ""
                for part in name.split("."):
                    if part and not part.startswith(("#", "[")):
                        out.add(part)
    return out


def _is_outline(node: ET.Element, unfilled: set[str]) -> bool:
    """Is this shape a stroke rather than a surface?

    It matters more than it sounds. A circle drawn with ``fill="none"`` is a
    *ring* of ink, and judging it by its bounding box reports every label inside
    it as obscured — four such warnings on the unit circle, each true of the box
    and false of the drawing. That is the same confusion the scene lane hit with
    a parabola, where one mistake produced 31 of 39 findings and buried the 8
    that were real.
    """
    fill = (node.get("fill") or "").strip().lower()
    if fill:
        return fill == "none"
    return any(name in unfilled for name in (node.get("class") or "").split())


def _outline_of(box: Box, tag: str) -> tuple[tuple[tuple[float, float], ...], ...]:
    """Where an unfilled shape's ink actually is."""
    import math

    if tag in ("circle", "ellipse"):
        cx, cy = (box.x0 + box.x1) / 2, (box.y0 + box.y1) / 2
        rx, ry = box.width / 2, box.height / 2
        steps = 64
        ring = tuple((cx + rx * math.cos(2 * math.pi * i / steps),
                      cy + ry * math.sin(2 * math.pi * i / steps))
                     for i in range(steps + 1))
        return (ring,)
    return (((box.x0, box.y0), (box.x1, box.y0), (box.x1, box.y1),
             (box.x0, box.y1), (box.x0, box.y0)),)


def _font_for(node: ET.Element,
              styles: dict[str, tuple[float, bool]]) -> tuple[float, bool]:
    """The size and weight a label will be drawn at: inline first, then class."""
    size = node.get("font-size")
    if size:
        found = _NUMBER.search(size)
        if found:
            weight = (node.get("font-weight") or "").strip()
            return (float(found.group()),
                    weight == "bold" or (weight.isdigit() and int(weight) >= 600))
    for name in (node.get("class") or "").split():
        if name in styles:
            return styles[name]
    return (DEFAULT_FONT_PX, False)


def _text_box(node: ET.Element,
              styles: dict[str, tuple[float, bool]]) -> Box | None:
    content = "".join(node.itertext()).strip()
    if not content:
        return None
    try:
        x, y = float(node.get("x", "0")), float(node.get("y", "0"))
    except ValueError:
        return None
    size, bold = _font_for(node, styles)
    # The safe width, deliberately: judging a label by the width this host
    # happens to render lets a collision through on every host that resolves the
    # font wider — which is most of them, since the stack asks for a face that is
    # usually absent.
    width = text_width(content, size, bold=bold, safe=True)
    anchor = node.get("text-anchor")
    if anchor == "end":
        x0, x1 = x - width, x
    elif anchor == "middle":
        x0, x1 = x - width / 2, x + width / 2
    else:
        x0, x1 = x, x + width
    # A baseline sits about three quarters down the em box.
    return Box(content, x0, x1, y - size * 0.75, y + size * 0.25, kind="text")


def _path_points(d: str) -> list[tuple[float, float]]:
    """Every position a path command lands on, ignoring radii and flags."""
    points: list[tuple[float, float]] = []
    cursor = (0.0, 0.0)
    for command, chunk in re.findall(r"([MmLlHhVvCcSsQqTtAaZz])([^A-Za-z]*)", d):
        upper = command.upper()
        numbers = [float(n) for n in _NUMBER.findall(chunk)]
        step = _PATH_ARGS.get(upper, 2)
        if step == 0:
            continue
        relative = command.islower()
        for start in range(0, len(numbers) - step + 1, step):
            group = numbers[start:start + step]
            if upper == "H":
                target = (group[0] + (cursor[0] if relative else 0.0), cursor[1])
            elif upper == "V":
                target = (cursor[0], group[0] + (cursor[1] if relative else 0.0))
            else:
                # For A the position is the *last* pair; the first five are two
                # radii, a rotation and two flags.
                dx, dy = group[-2], group[-1]
                target = ((dx + cursor[0], dy + cursor[1]) if relative else (dx, dy))
                if upper in ("C", "S", "Q") and not relative:
                    for i in range(0, step - 2, 2):
                        points.append((group[i], group[i + 1]))
            points.append(target)
            cursor = target
    return points


def _shape_box(node: ET.Element, unfilled: set[str]) -> Box | None:
    tag = node.tag.replace(_SVG, "")
    label = (node.get("class") or tag).split()[0]
    try:
        if tag == "rect":
            x, y = float(node.get("x", "0")), float(node.get("y", "0"))
            w, h = float(node.get("width", "0")), float(node.get("height", "0"))
            box = Box(label, x, x + w, y, y + h)
            return (Box(label, x, x + w, y, y + h,
                        path=_outline_of(box, tag))
                    if _is_outline(node, unfilled) else box)
        if tag in ("circle", "ellipse"):
            cx, cy = float(node.get("cx", "0")), float(node.get("cy", "0"))
            rx = float(node.get("r") or node.get("rx") or 0)
            ry = float(node.get("r") or node.get("ry") or 0)
            box = Box(label, cx - rx, cx + rx, cy - ry, cy + ry)
            return (Box(label, box.x0, box.x1, box.y0, box.y1,
                        path=_outline_of(box, tag))
                    if _is_outline(node, unfilled) else box)
        if tag == "line":
            x1, y1 = float(node.get("x1", "0")), float(node.get("y1", "0"))
            x2, y2 = float(node.get("x2", "0")), float(node.get("y2", "0"))
            return Box(label, min(x1, x2), max(x1, x2), min(y1, y2), max(y1, y2),
                       path=(((x1, y1), (x2, y2)),))
        if tag in ("path", "polyline", "polygon"):
            points = (_path_points(node.get("d", "")) if tag == "path"
                      else _points_attr(node.get("points", "")))
            if not points:
                return None
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            # `path` carries where the ink actually is, so a stroke across a
            # figure is not judged by the whole rectangle it spans — the same
            # distinction the scene lane needed for a parabola.
            box = Box(label, min(xs), max(xs), min(ys), max(ys))
            # A filled path *is* its box; an unfilled one is only its stroke.
            return (Box(label, box.x0, box.x1, box.y0, box.y1,
                        path=(tuple(points),))
                    if _is_outline(node, unfilled) or tag == "polyline" else box)
    except (TypeError, ValueError):
        return None
    return None


def _points_attr(raw: str) -> list[tuple[float, float]]:
    numbers = [float(n) for n in _NUMBER.findall(raw)]
    return list(zip(numbers[::2], numbers[1::2]))



#: Subtrees that describe geometry rather than draw it. A `<marker>` is stamped
#: where an arrow references it, a `<clipPath>` bounds what shows through — none
#: of it is ink at the coordinates it is written at. Counting them made a
#: clip-path rectangle "cover" the text beneath it, which was a finding about
#: nothing.
_DEFINITIONS = ("defs", "clipPath", "marker", "mask", "symbol", "pattern")
_XLINK = "{http://www.w3.org/1999/xlink}"
_DATA_SVG_RE = re.compile(r"data:image/svg\+xml(?:;charset=[^;,]+)?(;base64)?,", re.IGNORECASE)


def _embedded_document(node: ET.Element) -> str | None:
    """The SVG an ``<image>`` carries inline as a ``data:`` URI, or ``None``.

    `algorithm_trace` embeds each child figure this way to keep its CSS and
    ids from colliding with the storyboard's. A browser paints the child's
    labels all the same, so the check has to see them all the same — an image
    it cannot open is left as it was, invisible, rather than guessed at.
    """
    href = node.get("href") or node.get(_XLINK + "href") or ""
    match = _DATA_SVG_RE.match(href)
    if not match:
        return None
    payload = href[match.end():]
    try:
        return (base64.b64decode(payload).decode("utf-8") if match.group(1)
                else unquote(payload))
    except (ValueError, UnicodeDecodeError):
        return None


def _collect_embedded(node: ET.Element, inner: str, matrix, boxes, clip, truncated) -> None:
    """Walk an embedded SVG in the space its ``<image>`` paints it in.

    ``preserveAspectRatio`` decides the scale: ``meet`` (the default) fits the
    whole child inside the image box, ``slice`` fills it, ``none`` stretches.
    The child's own viewBox origin and the alignment offset both fold into one
    affine, so every label lands where a viewer would draw it — smaller, when
    the child is shrunk to fit.
    """
    x, y = _length(node.get("x")), _length(node.get("y"))
    width, height = _length(node.get("width")), _length(node.get("height"))
    min_x, min_y, inner_w, inner_h = _canvas(inner)
    if width <= 0 or height <= 0 or inner_w <= 0 or inner_h <= 0:
        return
    try:
        root = ET.fromstring(inner)
    except ET.ParseError:
        return
    aspect = (node.get("preserveAspectRatio") or "xMidYMid meet").split()
    align = aspect[0]
    if align == "none":
        sx, sy = width / inner_w, height / inner_h
    else:
        fit = max if "slice" in aspect else min
        sx = sy = fit(width / inner_w, height / inner_h)
    spare_x, spare_y = width - inner_w * sx, height - inner_h * sy
    ox = 0.0 if "xMin" in align else spare_x if "xMax" in align else spare_x / 2
    oy = 0.0 if "YMin" in align else spare_y if "YMax" in align else spare_y / 2
    placed = _compose(matrix, (sx, 0.0, 0.0, sy,
                               x + ox - min_x * sx, y + oy - min_y * sy))
    # The image box clips what it paints, exactly as a clip path would.
    corners = [_point(matrix, px, py) for px in (x, x + width) for py in (y, y + height)]
    xs, ys = [c[0] for c in corners], [c[1] for c in corners]
    frame = _intersect(clip, (min(xs), min(ys), max(xs), max(ys)))
    if frame is _EMPTY:
        return
    _collect(root, placed, boxes, styles_from_svg(inner), unfilled_classes(inner),
             _clip_shapes(root), frame, truncated)

_SHAPES = ("rect", "circle", "ellipse", "line", "path", "polyline", "polygon")

#: An affine as SVG writes it: (a, b, c, d, e, f) for [[a c e], [b d f]].
_IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def _compose(outer, inner):
    a, b, c, d, e, f = outer
    a2, b2, c2, d2, e2, f2 = inner
    return (a * a2 + c * b2, b * a2 + d * b2,
            a * c2 + c * d2, b * c2 + d * d2,
            a * e2 + c * f2 + e, b * e2 + d * f2 + f)


def _transform_of(value: str | None):
    """One element's ``transform`` attribute as an affine.

    A rotated label is the case that matters: the step-function y-axis title is
    written horizontally and turned a quarter turn, so measuring it where the
    x/y say it sits reports a long horizontal label hanging off the frame. It is
    a tall narrow one sitting comfortably inside.
    """
    if not value:
        return _IDENTITY
    matrix = _IDENTITY
    for name, raw in re.findall(r"([a-zA-Z]+)\s*\(([^)]*)\)", value):
        n = [float(v) for v in _NUMBER.findall(raw)]
        if name == "translate" and n:
            step = (1.0, 0.0, 0.0, 1.0, n[0], n[1] if len(n) > 1 else 0.0)
        elif name == "scale" and n:
            step = (n[0], 0.0, 0.0, n[1] if len(n) > 1 else n[0], 0.0, 0.0)
        elif name == "rotate" and n:
            rad = math.radians(n[0])
            cos, sin = math.cos(rad), math.sin(rad)
            step = (cos, sin, -sin, cos, 0.0, 0.0)
            if len(n) >= 3:  # rotate about a point, not the origin
                cx, cy = n[1], n[2]
                step = _compose((1.0, 0.0, 0.0, 1.0, cx, cy),
                                _compose(step, (1.0, 0.0, 0.0, 1.0, -cx, -cy)))
        elif name == "matrix" and len(n) >= 6:
            step = tuple(n[:6])
        else:
            # An unsupported transform (skew) would be measured wrongly, and a
            # wrong finding is worse than a missing one.
            return None
        matrix = _compose(matrix, step)
    return matrix


def _point(matrix, x: float, y: float) -> tuple[float, float]:
    a, b, c, d, e, f = matrix
    return (a * x + c * y + e, b * x + d * y + f)


def _mapped(box: Box, matrix) -> Box:
    """``box`` in the coordinates it is actually painted in."""
    if matrix == _IDENTITY:
        return box
    corners = [_point(matrix, x, y)
               for x in (box.x0, box.x1) for y in (box.y0, box.y1)]
    xs = [p[0] for p in corners]
    ys = [p[1] for p in corners]
    return Box(box.label, min(xs), max(xs), min(ys), max(ys), kind=box.kind,
               path=tuple(tuple(_point(matrix, x, y) for x, y in stroke)
                          for stroke in box.path))



def _clip_shapes(root) -> dict:
    """``id`` -> the rectangle a ``<clipPath>`` clips to, or ``None`` if it is
    one this module cannot represent.

    Only a single rectangle is understood, which is every clip the lane draws.
    A clip made of anything else maps to ``None``, and geometry under it is
    omitted rather than measured: reporting a line's full length when the figure
    only ever shows the part inside the panel is a finding about pixels that are
    never drawn.

    A rounded corner (``rx``) is ignored — the few units it would trim cannot
    turn a legible label illegible.
    """
    found = {}
    for node in root.iter():
        if node.tag.replace(_SVG, "") != "clipPath":
            continue
        name = node.get("id")
        if not name:
            continue
        children = [c for c in node if c.tag.replace(_SVG, "") not in ("title", "desc")]
        rect = children[0] if len(children) == 1 else None
        if rect is None or rect.tag.replace(_SVG, "") != "rect":
            found[name] = None
            continue
        try:
            x, y = float(rect.get("x", "0")), float(rect.get("y", "0"))
            w, h = float(rect.get("width", "0")), float(rect.get("height", "0"))
        except ValueError:
            found[name] = None
            continue
        found[name] = (x, y, x + w, y + h)
    return found


_CLIP_REF = re.compile(r"url\(#([^)]+)\)")


def _intersect(a, b):
    if a is None:
        return b
    if b is None:
        return a
    box = (max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3]))
    return box if box[0] < box[2] and box[1] < box[3] else _EMPTY


_EMPTY = (0.0, 0.0, 0.0, 0.0)


def _clip_segment(p, q, clip):
    """Liang-Barsky: the part of segment ``p``-``q`` inside ``clip``, or None."""
    x0, y0 = p
    x1, y1 = q
    dx, dy = x1 - x0, y1 - y0
    t0, t1 = 0.0, 1.0
    for denom, numer in ((-dx, x0 - clip[0]), (dx, clip[2] - x0),
                         (-dy, y0 - clip[1]), (dy, clip[3] - y0)):
        if denom == 0:
            if numer < 0:
                return None
            continue
        t = numer / denom
        if denom < 0:
            if t > t1:
                return None
            t0 = max(t0, t)
        else:
            if t < t0:
                return None
            t1 = min(t1, t)
    if t0 > t1:
        return None
    return ((x0 + t0 * dx, y0 + t0 * dy), (x0 + t1 * dx, y0 + t1 * dy))


def _hidden_by(box: Box, clip) -> float:
    """How far ``box`` reaches past ``clip``, in user units.

    The same measure ``qc`` applies to the frame, because it is the same defect:
    a label the reader cannot finish. Only the *amount* differs in where it is
    measured against.
    """
    if clip is None:
        return 0.0
    return max(clip[0] - box.x0, box.x1 - clip[2],
               clip[1] - box.y0, box.y1 - clip[3])


def _clipped(box: Box, clip) -> Box | None:
    """``box`` reduced to the part the figure actually shows.

    Callers must ask :func:`_hidden_by` *before* this for text: reducing a label
    to its visible fragment is right for deciding what it overlaps, and wrong as
    the whole story. A label running from x=40 to x=120 under a clip ending at
    50 becomes an unremarkable ten-unit box sitting well inside the frame, and
    nothing downstream can tell it from a label that is simply short — which
    would quietly turn the one check this module exists for into a pass.
    """
    if clip is None:
        return box
    x0, x1 = max(box.x0, clip[0]), min(box.x1, clip[2])
    y0, y1 = max(box.y0, clip[1]), min(box.y1, clip[3])
    if x0 > x1 or y0 > y1:
        return None
    strokes = []
    for stroke in box.path:
        kept: list[tuple[float, float]] = []
        for start, end in zip(stroke, stroke[1:]):
            piece = _clip_segment(start, end, clip)
            if piece is None:
                continue
            if kept and kept[-1] == piece[0]:
                kept.append(piece[1])
            else:
                kept.extend(piece)
        if len(stroke) == 1 and clip[0] <= stroke[0][0] <= clip[2] \
                and clip[1] <= stroke[0][1] <= clip[3]:
            kept = list(stroke)
        if kept:
            strokes.append(tuple(kept))
    if box.path and not strokes:
        return None
    return Box(box.label, x0, x1, y0, y1, kind=box.kind, path=tuple(strokes))


def _collect(node, matrix, boxes, styles, unfilled, clips, clip, truncated) -> None:
    for child in node:
        tag = child.tag.replace(_SVG, "")
        if tag in _DEFINITIONS:
            continue
        here = _transform_of(child.get("transform"))
        if here is None:  # unsupported transform: omit rather than misplace
            continue
        here = _compose(matrix, here)

        # The clip is resolved in the user space of the element referencing it,
        # which is the space its own transform establishes — so map it with the
        # composed matrix, not the inherited one.
        active = clip
        reference = _CLIP_REF.search(child.get("clip-path") or "")
        if reference:
            shape = clips.get(reference.group(1), None)
            if shape is None:
                continue  # a clip this module cannot represent: draw nothing
            corners = [_point(here, x, y)
                       for x in (shape[0], shape[2]) for y in (shape[1], shape[3])]
            xs = [c[0] for c in corners]
            ys = [c[1] for c in corners]
            active = _intersect(active, (min(xs), min(ys), max(xs), max(ys)))
        if active is _EMPTY:
            continue
        if tag == "image":
            inner = _embedded_document(child)
            if inner is not None:
                _collect_embedded(child, inner, here, boxes, active, truncated)
            continue

        box = (_text_box(child, styles) if tag == "text"
               else _shape_box(child, unfilled) if tag in _SHAPES else None)
        if box is not None:
            placed = _mapped(box, here)
            if placed.kind == "text":
                over = _hidden_by(placed, active)
                if over > _EDGE_TOLERANCE:
                    truncated.append((placed, over))
            visible = _clipped(placed, active)
            if visible is not None:
                boxes.append(visible)
        _collect(child, here, boxes, styles, unfilled, clips, active, truncated)


def boxes_from_svg(svg: str) -> list[Box]:
    """Every drawn element of an emitted figure, as boxes the checker understands."""
    return _geometry(svg)[0]


def _geometry(svg: str) -> tuple[list[Box], list[tuple[Box, float]]]:
    """Every drawn element, and every text box a clip path cut short.

    The truncations travel beside the boxes rather than inside them because a
    clipped label is two different things at once: a small box for deciding what
    it overlaps, and a full-length one for saying how much of it the reader
    never sees.
    """
    if not svg or not svg.strip().startswith("<svg"):
        return [], []
    try:
        root = ET.fromstring(svg)
    except ET.ParseError:
        return [], []
    boxes: list[Box] = []
    truncated: list[tuple[Box, float]] = []
    _collect(root, _IDENTITY, boxes, styles_from_svg(svg), unfilled_classes(svg),
             _clip_shapes(root), None, truncated)
    return boxes, truncated


def _canvas(svg: str) -> tuple[float, float, float, float]:
    """The drawable frame as (min_x, min_y, width, height), in user units.

    Read off the root element, not scanned for out of the document text. The
    ``viewBox`` wins where there is one, because it is the coordinate system the
    content is written in — and it need not start at the origin. `graph` emits
    ``viewBox="53.2 94.0 521.6 152.0"``: measuring its labels against a frame
    running from 0 reported five of them past the right edge while every one
    sits comfortably inside. The width and height attributes are the *display*
    size and can differ from both.

    Searching the raw string for the first ``width=...  height=...`` pair used
    to be enough only because ``<svg>`` is written first. On a document whose
    root carries no size, it matched the first rectangle it found instead — a
    ``<clipPath>``'s, in the case that turned this up — and measured the whole
    figure against a frame taken from something that is not even drawn.
    """
    try:
        root = ET.fromstring(svg)
    except ET.ParseError:
        return (0.0, 0.0, 0.0, 0.0)

    box = (root.get("viewBox") or "").replace(",", " ").split()
    if len(box) == 4:
        try:
            min_x, min_y, width, height = (float(v) for v in box)
        except ValueError:
            pass
        else:
            if width > 0 and height > 0:
                return (min_x, min_y, width, height)

    width, height = _length(root.get("width")), _length(root.get("height"))
    if width > 0 and height > 0:
        return (0.0, 0.0, width, height)
    return (0.0, 0.0, 0.0, 0.0)


def figure_frame(svg: str) -> tuple[float, float, float, float]:
    """The drawable frame of an emitted figure as (min_x, min_y, width, height).

    What a template that places other figures needs to know about each of
    them: how large the child is in its own units, so it can be given a card
    it fits rather than one it is shrunk into.
    """
    return _canvas(svg)


def _length(value: str | None) -> float:
    """A length attribute as a number, ignoring any unit written after it."""
    if not value:
        return 0.0
    found = re.match(r"\s*(-?[\d.]+(?:[eE][-+]?\d+)?)", value)
    return float(found.group(1)) if found else 0.0


#: A full-bleed background is not a mark, and every template draws one. Judged as
#: ink it covers the whole canvas, so every label would be reported as sitting on
#: something — the check would find one defect per label and be useless.
_BACKGROUND = ("grid-paper", "background", "backdrop")


def check_figure(svg: str, *, tolerance: float | None = None) -> list[Finding]:
    """Legibility findings for an emitted figure, each carrying its coordinates.

    Runs the *same* :func:`straightedge.qc.check` the animation lane uses, so a
    figure and a scene report identically: text on text is an ``error``, text on
    a stroke is a ``warn``, anything past the edge is placed by severity, and
    each finding names the box it is about.

    The boxes are shifted so the canvas is centred before the check, because
    ``qc`` works in a frame about the origin and SVG counts from the top left.
    Everything else — the collapsing, the severities, the wording — is the
    checker's, unchanged.
    """
    min_x, min_y, width, height = _canvas(svg)
    if width <= 0 or height <= 0:
        return []
    drawn, truncated = _geometry(svg)
    boxes = [b for b in drawn
             if not any(hint in b.label for hint in _BACKGROUND)]
    # Centre on the middle of the *viewBox*, not on half its size: an origin
    # away from zero shifts every box by exactly that offset otherwise.
    half_w, half_h = min_x + width / 2, min_y + height / 2

    # Built before the nothing-was-drawn return, and independent of it. A label
    # lying *entirely* outside its clip is the worst case this check has —
    # every glyph missing — and it is also the one that leaves no visible box
    # behind, so hanging these findings off the box list dropped exactly the
    # figures that needed them most.
    clipped_away = [
        Finding("text_clipped", "error",
                f"extends {over:.2f} units beyond the clip path it is drawn in,"
                " so most of it may never be painted",
                box.label,
                box=(box.x0 - half_w, box.x1 - half_w,
                     box.y0 - half_h, box.y1 - half_h))
        for box, over in truncated
        if not any(hint in box.label for hint in _BACKGROUND)
    ]
    if not boxes:
        return clipped_away
    centred = [
        Box(b.label, b.x0 - half_w, b.x1 - half_w, b.y0 - half_h, b.y1 - half_h,
            kind=b.kind,
            path=tuple(tuple((x - half_w, y - half_h) for x, y in stroke)
                       for stroke in b.path))
        for b in boxes
    ]
    kwargs = {} if tolerance is None else {"overlap_tolerance": tolerance}
    # A label cut off by a clip path is cut off exactly as a label past the edge
    # of the frame is, and the reader loses it the same way — so it is reported
    # under the same name, at the same severity, with the boundary it ran past
    # being the only difference. Measured on the full label rather than on the
    # fragment left behind, and located there too, because the fragment is not
    # where the missing glyphs were meant to be.
    return check_boxes(centred, frame=(width, height), **kwargs) + clipped_away
