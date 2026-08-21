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

import re
import xml.etree.ElementTree as ET
from typing import Iterable

from ..qc import Box, Finding, check as check_boxes
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


def boxes_from_svg(svg: str) -> list[Box]:
    """Every drawn element of an emitted figure, as boxes the checker understands."""
    if not svg or not svg.strip().startswith("<svg"):
        return []
    try:
        root = ET.fromstring(svg)
    except ET.ParseError:
        return []
    boxes: list[Box] = []
    styles = styles_from_svg(svg)
    unfilled = unfilled_classes(svg)
    for node in root.iter():
        tag = node.tag.replace(_SVG, "")
        if tag == "text":
            box = _text_box(node, styles)
        elif tag in ("rect", "circle", "ellipse", "line", "path", "polyline",
                     "polygon"):
            box = _shape_box(node, unfilled)
        else:
            continue
        if box is not None:
            boxes.append(box)
    return boxes


def _canvas(svg: str) -> tuple[float, float]:
    found = re.search(r'width="([\d.]+)"\s+height="([\d.]+)"', svg)
    return (float(found.group(1)), float(found.group(2))) if found else (0.0, 0.0)


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
    width, height = _canvas(svg)
    if width <= 0 or height <= 0:
        return []
    boxes = [b for b in boxes_from_svg(svg)
             if not any(hint in b.label for hint in _BACKGROUND)]
    if not boxes:
        return []
    half_w, half_h = width / 2, height / 2
    centred = [
        Box(b.label, b.x0 - half_w, b.x1 - half_w, b.y0 - half_h, b.y1 - half_h,
            kind=b.kind,
            path=tuple(tuple((x - half_w, y - half_h) for x, y in stroke)
                       for stroke in b.path))
        for b in boxes
    ]
    kwargs = {} if tolerance is None else {"overlap_tolerance": tolerance}
    return check_boxes(centred, frame=(width, height), **kwargs)
