"""Cartesian coordinate plane diagram template.

Base template for 2D coordinate systems with axes, grid, and labels.
Used as foundation for function graphs, vector diagrams, etc.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..registry import register
from ..renderer import (
    DEFAULT_STYLES,
    circle,
    group,
    line,
    path,
    style,
    svg_document,
    text,
)
from .function_graph import _safe_eval

logger = logging.getLogger(__name__)

# Distinct default strokes, so a two-curve comparison reads as a comparison.
# Every curve defaulting to the same blue is indistinguishable from a bug.
_CURVE_PALETTE = ("#2196F3", "#E5533D", "#4CAF50", "#9C27B0", "#FF9800")


def _sample_curve(
    func: Callable[[float], List[float]],
    t_min: float,
    t_max: float,
    samples: int = 100,
) -> List[Tuple[float, float]]:
    """Sample a parametric curve, returning list of (x, y) points."""
    points = []
    for i in range(samples + 1):
        t = t_min + (t_max - t_min) * i / samples
        try:
            result = func(t)
            if result and len(result) == 2:
                x, y = result
                if math.isfinite(x) and math.isfinite(y):
                    points.append((x, y))
        except (ValueError, ZeroDivisionError, OverflowError):
            continue
    return points


def _sample_expression(
    expr: str,
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
    samples: int = 200,
) -> List[List[Tuple[float, float]]]:
    """Sample ``y = expr(x)`` into contiguous, in-view segments.

    Returns segments rather than one point list so poles break the stroke:
    joining across the gap in ``tan(x)`` or ``1/x`` draws a near-vertical line
    the viewer reads as part of the curve.
    """
    if x_max <= x_min:
        return []
    # Allow the curve to leave the frame and come back without ending the
    # segment prematurely, but not so far that the clip does nothing.
    margin = (y_max - y_min) * 0.5
    segments: List[List[Tuple[float, float]]] = []
    current: List[Tuple[float, float]] = []
    for i in range(samples + 1):
        x = x_min + (x_max - x_min) * i / samples
        y = _safe_eval(expr, x)
        if not math.isfinite(y) or not (y_min - margin <= y <= y_max + margin):
            if current:
                segments.append(current)
                current = []
            continue
        current.append((x, y))
    if current:
        segments.append(current)
    return [segment for segment in segments if len(segment) >= 2]


@register("coordinate_plane")
class CoordinatePlaneTemplate:
    """Render a Cartesian coordinate plane with configurable axes and grid."""

    def render(self, params: Dict[str, Any]) -> str:
        """Render the coordinate plane as SVG.

        Params:
            x_min, x_max: X-axis range (default: -5, 5)
            y_min, y_max: Y-axis range (default: -5, 5)
            show_grid: Show background grid (default: True)
            show_axes: Show x and y axes (default: True)
            show_labels: Show axis labels (default: True)
            show_ticks: Show tick marks (default: True)
            grid_step: Grid line spacing (default: 1)
            width: SVG width in pixels (default: 400)
            height: SVG height in pixels (default: 400)
            padding: Padding around plot area (default: 40)
            title: Optional title text
            points: List of points to plot [{x, y, label?, style?}]
            vectors: List of vectors [{x, y, color?, label?}]
            curves: List of curves to draw. Each curve is a dict with:
                - type: "parabola_right" (y²=4ax), "parabola_down" (x²=-4ay vertex form),
                        "parabola_up", "line", "vertical_line"
                - For parabola_right: a (focal parameter), or p (where y²=px so a=p/4)
                - For parabola_down/up: a, vertex_x, vertex_y (vertex form)
                - For line: slope, intercept (y = slope*x + intercept) or a, b, c (ax+by+c=0)
                - For vertical_line: x (the x-coordinate)
                - color: stroke color (default: #2196F3)
                - dashed: boolean for dashed line (default: false)
                - label: optional label for the curve
        """
        # Extract parameters
        x_min = float(params.get("x_min", -5))
        x_max = float(params.get("x_max", 5))
        y_min = float(params.get("y_min", -5))
        y_max = float(params.get("y_max", 5))
        show_grid = bool(params.get("show_grid", True))
        show_axes = bool(params.get("show_axes", True))
        show_labels = bool(params.get("show_labels", True))
        show_ticks = bool(params.get("show_ticks", True))
        grid_step = float(params.get("grid_step", 1))
        svg_width = int(params.get("width", 400))
        svg_height = int(params.get("height", 400))
        padding = int(params.get("padding", 40))
        title = params.get("title")
        points = params.get("points", [])
        vectors = params.get("vectors", [])
        curves = params.get("curves", [])

        # Calculate plot area
        plot_width = svg_width - 2 * padding
        plot_height = svg_height - 2 * padding
        x_range = x_max - x_min
        y_range = y_max - y_min

        # Coordinate transforms
        def to_svg_x(x: float) -> float:
            return padding + (x - x_min) / x_range * plot_width

        def to_svg_y(y: float) -> float:
            return padding + (y_max - y) / y_range * plot_height

        elements: List[str] = []
        elements.append(style(DEFAULT_STYLES + self._extra_styles()))

        # Background grid
        if show_grid:
            grid_lines = []
            # Vertical lines
            x = x_min
            while x <= x_max:
                px = to_svg_x(x)
                grid_lines.append(
                    line(px, padding, px, svg_height - padding, **{"class": "coord-grid"})
                )
                x += grid_step
            # Horizontal lines
            y = y_min
            while y <= y_max:
                py = to_svg_y(y)
                grid_lines.append(
                    line(padding, py, svg_width - padding, py, **{"class": "coord-grid"})
                )
                y += grid_step
            elements.append(group("\n".join(grid_lines)))

        # Axes
        if show_axes:
            axes_elements = []
            # X-axis (if in range)
            if y_min <= 0 <= y_max:
                y0 = to_svg_y(0)
                axes_elements.append(
                    line(padding, y0, svg_width - padding, y0, **{"class": "coord-axis"})
                )
                # Arrow
                axes_elements.append(
                    line(svg_width - padding, y0, svg_width - padding - 8, y0 - 4, **{"class": "coord-axis"})
                )
                axes_elements.append(
                    line(svg_width - padding, y0, svg_width - padding - 8, y0 + 4, **{"class": "coord-axis"})
                )
            # Y-axis (if in range)
            if x_min <= 0 <= x_max:
                x0 = to_svg_x(0)
                axes_elements.append(
                    line(x0, svg_height - padding, x0, padding, **{"class": "coord-axis"})
                )
                # Arrow
                axes_elements.append(
                    line(x0, padding, x0 - 4, padding + 8, **{"class": "coord-axis"})
                )
                axes_elements.append(
                    line(x0, padding, x0 + 4, padding + 8, **{"class": "coord-axis"})
                )
            elements.append(group("\n".join(axes_elements)))

        # Tick marks and labels
        if show_ticks or show_labels:
            tick_elements = []
            # X-axis ticks
            x = x_min
            while x <= x_max:
                if x != 0 or not (x_min <= 0 <= x_max):  # Skip origin if axes shown
                    px = to_svg_x(x)
                    y0 = to_svg_y(0) if y_min <= 0 <= y_max else svg_height - padding
                    if show_ticks:
                        tick_elements.append(
                            line(px, y0 - 4, px, y0 + 4, **{"class": "coord-tick"})
                        )
                    if show_labels and x == int(x):
                        tick_elements.append(
                            text(px, y0 + 16, str(int(x)), **{"class": "coord-label", "text_anchor": "middle"})
                        )
                x += grid_step

            # Y-axis ticks
            y = y_min
            while y <= y_max:
                if y != 0 or not (y_min <= 0 <= y_max):
                    py = to_svg_y(y)
                    x0 = to_svg_x(0) if x_min <= 0 <= x_max else padding
                    if show_ticks:
                        tick_elements.append(
                            line(x0 - 4, py, x0 + 4, py, **{"class": "coord-tick"})
                        )
                    if show_labels and y == int(y):
                        tick_elements.append(
                            text(x0 - 8, py + 4, str(int(y)), **{"class": "coord-label", "text_anchor": "end"})
                        )
                y += grid_step

            elements.append(group("\n".join(tick_elements)))

        # Draw curves (parabolas, lines, etc.)
        if curves:
            curve_elements = []
            for curve_index, curve in enumerate(curves):
                if not isinstance(curve, dict):
                    continue
                curve_type = curve.get("type", "")
                color = curve.get("color") or _CURVE_PALETTE[
                    curve_index % len(_CURVE_PALETTE)
                ]
                # ``style: "dashed"`` is the spelling spec authors reach for;
                # the original ``dashed: true`` flag stays supported.
                dashed = bool(curve.get("dashed", False)) or str(
                    curve.get("style", "")
                ).lower() == "dashed"
                stroke_attrs = {
                    "stroke": color,
                    "stroke_width": "2",
                    "fill": "none",
                }
                if dashed:
                    stroke_attrs["stroke_dasharray"] = "6,3"

                curve_points: List[Tuple[float, float]] = []
                curve_segments: List[List[Tuple[float, float]]] = []

                if curve_type == "parabola_right":
                    # y² = 4ax or y² = px (where p = 4a)
                    a = float(curve.get("a", 1))
                    if "p" in curve:
                        a = float(curve["p"]) / 4
                    # Sample from y_min to y_max continuously
                    # x = y² / (4a), so we parameterize by y directly
                    curve_points = _sample_curve(
                        lambda y: [y * y / (4 * a) if a != 0 else 0, y],
                        y_min - 0.5, y_max + 0.5, 120
                    )

                elif curve_type == "parabola_down":
                    # (x - h)² = -4a(y - k), opens downward
                    a = float(curve.get("a", 1))
                    h = float(curve.get("vertex_x", 0))
                    k = float(curve.get("vertex_y", 0))
                    # Parametric: x = h + t, y = k - t²/(4a)
                    t_range = max(abs(x_min - h), abs(x_max - h)) + 1
                    curve_points = _sample_curve(
                        lambda t: [h + t, k - (t * t) / (4 * a) if a != 0 else k],
                        -t_range, t_range, 100
                    )

                elif curve_type == "parabola_up":
                    # (x - h)² = 4a(y - k), opens upward
                    a = float(curve.get("a", 1))
                    h = float(curve.get("vertex_x", 0))
                    k = float(curve.get("vertex_y", 0))
                    t_range = max(abs(x_min - h), abs(x_max - h)) + 1
                    curve_points = _sample_curve(
                        lambda t: [h + t, k + (t * t) / (4 * a) if a != 0 else k],
                        -t_range, t_range, 100
                    )

                elif curve_type == "line":
                    # y = slope * x + intercept, or ax + by + c = 0
                    # For lines, we need to clip to view bounds, not filter
                    if "slope" in curve:
                        slope = float(curve.get("slope", 0))
                        intercept = float(curve.get("intercept", 0))
                        # Clip line to view bounds
                        curve_points = self._clip_line_to_bounds(
                            slope, intercept, x_min, x_max, y_min, y_max
                        )
                    elif "a" in curve and "b" in curve:
                        # ax + by + c = 0 => y = -(ax + c)/b if b != 0
                        a_coef = float(curve.get("a", 0))
                        b_coef = float(curve.get("b", 1))
                        c_coef = float(curve.get("c", 0))
                        if b_coef != 0:
                            slope = -a_coef / b_coef
                            intercept = -c_coef / b_coef
                            curve_points = self._clip_line_to_bounds(
                                slope, intercept, x_min, x_max, y_min, y_max
                            )
                        else:
                            # Vertical line: x = -c/a
                            x_val = -c_coef / a_coef if a_coef != 0 else 0
                            curve_points = [(x_val, y_min), (x_val, y_max)]

                elif curve_type == "vertical_line":
                    x_val = float(curve.get("x", 0))
                    curve_points = [(x_val, y_min), (x_val, y_max)]

                elif curve.get("function") or curve.get("expr"):
                    # A curve given as an expression in x — the shape spec
                    # authors reach for by default, and the one this template
                    # used to drop on the floor, rendering bare axes that read
                    # as a deliberate empty plot rather than a mismatch.
                    expr = str(curve.get("function") or curve.get("expr"))
                    curve_segments = _sample_expression(
                        expr, x_min, x_max, y_min, y_max
                    )
                    if not curve_segments:
                        logger.warning(
                            "coordinate_plane: expression %r yielded no plottable "
                            "points over x in [%s, %s] — curve dropped",
                            expr, x_min, x_max,
                        )

                else:
                    logger.warning(
                        "coordinate_plane: curve %d has no renderable shape "
                        "(type=%r, keys=%s) — curve dropped",
                        curve_index, curve_type or "<untyped>", sorted(curve),
                    )

                # Convert to SVG path
                if curve_points and not curve_segments:
                    # Filter points within view bounds (with some margin)
                    margin = 0.5
                    filtered = [
                        (x, y) for x, y in curve_points
                        if x_min - margin <= x <= x_max + margin
                        and y_min - margin <= y <= y_max + margin
                    ]
                    if filtered:
                        curve_segments = [filtered]

                for segment in curve_segments:
                    path_d = f"M {to_svg_x(segment[0][0])} {to_svg_y(segment[0][1])}"
                    for x, y in segment[1:]:
                        path_d += f" L {to_svg_x(x)} {to_svg_y(y)}"
                    curve_elements.append(path(path_d, **stroke_attrs))

                # Label the curve once. Anchoring at the endpoint collides
                # whenever curves meet there — 2cos(x) and -2cos(x) both end at
                # (pi/2, 0) — and runs off the right edge, so walk a fraction
                # along the longest segment and keep the text inside the frame.
                label = curve.get("label")
                if label and curve_segments:
                    longest = max(curve_segments, key=len)
                    frac = 0.45 + 0.2 * (curve_index % 3)
                    lx, ly = longest[min(int(len(longest) * frac), len(longest) - 1)]
                    tx = to_svg_x(lx)
                    # Clear of the stroke — at -6 the curve strikes through the
                    # text on a steep segment.
                    ty = to_svg_y(ly) - 12
                    if tx > svg_width - padding - 60:
                        tx, anchor = tx - 6, "end"
                    else:
                        tx, anchor = tx + 6, "start"
                    ty = min(max(ty, padding + 10), svg_height - padding - 4)
                    curve_elements.append(
                        text(tx, ty, label,
                             **{"class": "coord-curve-label", "fill": color,
                                "text_anchor": anchor})
                    )

            if curve_elements:
                elements.append(group("\n".join(curve_elements)))

        # Plot points
        if points:
            point_elements = []
            for pt in points:
                if not isinstance(pt, dict):
                    continue
                px = to_svg_x(float(pt.get("x", 0)))
                py = to_svg_y(float(pt.get("y", 0)))
                pt_style = pt.get("style", "default")
                pt_class = f"coord-point coord-point-{pt_style}"
                point_elements.append(circle(px, py, 5, **{"class": pt_class}))
                if pt.get("label"):
                    point_elements.append(
                        text(px + 8, py - 8, pt["label"], **{"class": "coord-point-label"})
                    )
            elements.append(group("\n".join(point_elements)))

        # Draw vectors
        if vectors:
            vector_elements = []
            for vec in vectors:
                if not isinstance(vec, dict):
                    continue
                vx = float(vec.get("x", 0))
                vy = float(vec.get("y", 0))
                origin_x = float(vec.get("origin_x", 0))
                origin_y = float(vec.get("origin_y", 0))
                color = vec.get("color", "#2196F3")

                px1 = to_svg_x(origin_x)
                py1 = to_svg_y(origin_y)
                px2 = to_svg_x(origin_x + vx)
                py2 = to_svg_y(origin_y + vy)

                vector_elements.append(
                    line(px1, py1, px2, py2, stroke=color, stroke_width="2", marker_end="url(#arrowhead)")
                )
            elements.append(group("\n".join(vector_elements)))

        # Title
        if title:
            elements.append(
                text(svg_width / 2, 20, title, **{"class": "coord-title", "text_anchor": "middle"})
            )

        return svg_document("\n".join(elements), svg_width, svg_height)

    def _clip_line_to_bounds(
        self,
        slope: float,
        intercept: float,
        x_min: float,
        x_max: float,
        y_min: float,
        y_max: float,
    ) -> List[Tuple[float, float]]:
        """Clip a line y = slope*x + intercept to the view bounds.

        Returns two points defining the visible segment of the line.
        """
        # Collect all intersection points with the four edges
        candidates: List[Tuple[float, float]] = []

        # Left edge (x = x_min)
        y_at_xmin = slope * x_min + intercept
        if y_min <= y_at_xmin <= y_max:
            candidates.append((x_min, y_at_xmin))

        # Right edge (x = x_max)
        y_at_xmax = slope * x_max + intercept
        if y_min <= y_at_xmax <= y_max:
            candidates.append((x_max, y_at_xmax))

        # Bottom edge (y = y_min)
        if slope != 0:
            x_at_ymin = (y_min - intercept) / slope
            if x_min < x_at_ymin < x_max:  # Strict inequality to avoid corner duplicates
                candidates.append((x_at_ymin, y_min))

        # Top edge (y = y_max)
        if slope != 0:
            x_at_ymax = (y_max - intercept) / slope
            if x_min < x_at_ymax < x_max:  # Strict inequality to avoid corner duplicates
                candidates.append((x_at_ymax, y_max))

        # Handle horizontal line (slope = 0)
        if slope == 0 and y_min <= intercept <= y_max:
            return [(x_min, intercept), (x_max, intercept)]

        # Remove near-duplicates and return two distinct points
        if len(candidates) >= 2:
            # Sort by x to get consistent ordering
            candidates = sorted(candidates, key=lambda p: (round(p[0], 6), round(p[1], 6)))
            # Remove near-duplicates
            unique = [candidates[0]]
            for p in candidates[1:]:
                if abs(p[0] - unique[-1][0]) > 1e-6 or abs(p[1] - unique[-1][1]) > 1e-6:
                    unique.append(p)
            if len(unique) >= 2:
                return [unique[0], unique[-1]]

        return []

    def _extra_styles(self) -> str:
        return """
.coord-grid { stroke: #e0e0e0; stroke-width: 1; }
.coord-axis { stroke: #333; stroke-width: 2; }
.coord-tick { stroke: #333; stroke-width: 1; }
.coord-label { font-size: 11px; font-family: sans-serif; fill: #666; }
.coord-title { font-size: 14px; font-family: sans-serif; fill: #333; font-weight: bold; }
.coord-point { fill: #2196F3; }
.coord-point-default { fill: #2196F3; }
.coord-point-highlight { fill: #FF9800; }
.coord-point-max { fill: #4CAF50; }
.coord-point-min { fill: #f44336; }
.coord-point-inflection { fill: #9C27B0; }
.coord-point-label { font-size: 12px; font-family: sans-serif; fill: #333; }
.coord-curve-label { font-size: 11px; font-family: sans-serif; font-style: italic; }
"""
