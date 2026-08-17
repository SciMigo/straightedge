"""Polar coordinate graph template.

Visualizes polar coordinates and polar function curves like
rose curves, cardioids, spirals, etc.
"""

from __future__ import annotations

import math
from typing import Any, Callable, Dict, List, Tuple

from ...expr import (
    ExpressionError, evaluate, normalize_expression, validate_expression,
)
from ..registry import register
from ..renderer import (
    circle,
    group,
    line,
    path,
    style,
    svg_document,
    text,
)


# Built-in polar functions r(θ)
POLAR_FUNCTIONS: Dict[str, Callable[[float], float]] = {
    "1": lambda t: 1,  # Circle
    "2": lambda t: 2,
    "theta": lambda t: t,  # Archimedean spiral
    "1+cos(theta)": lambda t: 1 + math.cos(t),  # Cardioid
    "1+sin(theta)": lambda t: 1 + math.sin(t),
    "2*cos(theta)": lambda t: 2 * math.cos(t),  # Circle through origin
    "2*sin(theta)": lambda t: 2 * math.sin(t),
    "cos(2*theta)": lambda t: math.cos(2 * t),  # Rose, 4 petals
    "sin(2*theta)": lambda t: math.sin(2 * t),
    "cos(3*theta)": lambda t: math.cos(3 * t),  # Rose, 3 petals
    "sin(3*theta)": lambda t: math.sin(3 * t),
    "cos(4*theta)": lambda t: math.cos(4 * t),  # Rose, 8 petals
    "1-cos(theta)": lambda t: 1 - math.cos(t),  # Reversed cardioid
    "theta/pi": lambda t: t / math.pi,  # Spiral
}


def _is_plottable(expr: str) -> bool:
    """Whether ``expr`` will reduce to numbers, checked once before drawing.

    See ``riemann_sum._is_plottable``: the expression is tried, not just parsed,
    because the allowlist admits arithmetic the evaluator still refuses.
    """
    if expr in POLAR_FUNCTIONS:
        return True
    normalized = normalize_expression(str(expr))
    if not validate_expression(normalized, variables={"t", "theta"}):
        return False
    try:
        evaluate(normalized, t=1.0, theta=1.0)
    except ExpressionError:
        return False
    except Exception:
        pass
    return True


def _eval_polar(expr: str, theta: float) -> float:
    """Evaluate a polar function r(θ).

    Both spellings of the angle are bound, so the caller may write either
    ``sin(2*theta)`` or ``sin(2*t)`` — the old code renamed one to the other
    before evaluating, and callers rely on both.

    NaN, never 0, for anything that does not reduce to a number: r=0 is a point
    at the origin, which draws, so a mistyped curve would come back as a figure
    rather than as nothing.
    """
    if expr in POLAR_FUNCTIONS:
        try:
            return POLAR_FUNCTIONS[expr](theta)
        except Exception:
            return math.nan

    try:
        return evaluate(normalize_expression(expr), t=theta, theta=theta)
    except Exception:
        return math.nan


@register("polar_graph")
class PolarGraphTemplate:
    """Render a polar coordinate graph."""

    def render(self, params: Dict[str, Any]) -> str:
        """Render the polar graph as SVG.

        Params:
            function: Polar function r(θ) (default: "1+cos(theta)")
            functions: List of functions [{expr, color, label?}]
            theta_min: Starting angle in radians (default: 0)
            theta_max: Ending angle in radians (default: 2π)
            samples: Number of sample points (default: 200)
            show_grid: Show polar grid circles (default: True)
            show_rays: Show radial grid lines (default: True)
            show_axes: Show x/y axes (default: True)
            r_max: Maximum radius (default: auto)
            point_at: Highlight point at angle θ (optional)
            width, height: SVG dimensions (default: 400x400)
            title: Optional title
        """
        # Extract parameters
        func_expr = params.get("function", "1+cos(theta)")
        if not _is_plottable(func_expr):
            return ""      # see riemann_sum: chrome alone reads as a figure

        functions = params.get("functions", [])
        theta_min = float(params.get("theta_min", 0))
        theta_max = float(params.get("theta_max", 2 * math.pi))
        samples = int(params.get("samples", 200))
        show_grid = bool(params.get("show_grid", True))
        show_rays = bool(params.get("show_rays", True))
        show_axes = bool(params.get("show_axes", True))
        r_max_param = params.get("r_max")
        point_at = params.get("point_at")
        svg_width = int(params.get("width", 400))
        svg_height = int(params.get("height", 400))
        title = params.get("title")

        # Build function list
        if not functions:
            functions = [{"expr": func_expr, "color": "#2196F3"}]

        # Sample all functions
        all_curves: List[List[Tuple[float, float, float]]] = []  # (theta, r, valid)
        r_max = 0

        for func in functions:
            expr = func.get("expr", "1")
            curve_points = []
            for i in range(samples + 1):
                theta = theta_min + (theta_max - theta_min) * i / samples
                r = _eval_polar(expr, theta)
                if math.isfinite(r):
                    curve_points.append((theta, r, True))
                    r_max = max(r_max, abs(r))
                else:
                    curve_points.append((theta, 0, False))
            all_curves.append(curve_points)

        # Use provided r_max or auto
        if r_max_param is not None:
            r_max = float(r_max_param)
        elif r_max == 0:
            r_max = 2

        # Add padding to r_max
        r_max *= 1.1

        # Calculate dimensions
        center_x = svg_width / 2
        center_y = svg_height / 2
        radius = min(svg_width, svg_height) * 0.4
        scale = radius / r_max

        def polar_to_svg(r: float, theta: float) -> Tuple[float, float]:
            x = r * math.cos(theta) * scale
            y = r * math.sin(theta) * scale
            return center_x + x, center_y - y

        elements: List[str] = []
        elements.append(style(self._styles()))

        # Polar grid circles
        if show_grid:
            grid_elements = []
            # Determine nice grid spacing
            grid_step = self._nice_step(r_max)
            r = grid_step
            while r <= r_max:
                grid_elements.append(
                    circle(center_x, center_y, r * scale, **{"class": "polar-grid"})
                )
                # Label
                grid_elements.append(
                    text(center_x + r * scale + 5, center_y - 3, f"{r:.1g}", **{"class": "polar-label"})
                )
                r += grid_step
            elements.append(group("\n".join(grid_elements)))

        # Radial grid lines
        if show_rays:
            ray_elements = []
            for angle_deg in range(0, 360, 30):
                angle_rad = math.radians(angle_deg)
                end_x = center_x + r_max * scale * math.cos(angle_rad)
                end_y = center_y - r_max * scale * math.sin(angle_rad)
                ray_elements.append(
                    line(center_x, center_y, end_x, end_y, **{"class": "polar-ray"})
                )
                # Angle label
                label_dist = r_max * scale + 15
                lx = center_x + label_dist * math.cos(angle_rad)
                ly = center_y - label_dist * math.sin(angle_rad)
                ray_elements.append(
                    text(lx, ly, f"{angle_deg}°", **{"class": "polar-angle-label", "text_anchor": "middle"})
                )
            elements.append(group("\n".join(ray_elements)))

        # Axes
        if show_axes:
            axes_elements = [
                line(center_x - r_max * scale - 10, center_y,
                     center_x + r_max * scale + 10, center_y, **{"class": "polar-axis"}),
                line(center_x, center_y + r_max * scale + 10,
                     center_x, center_y - r_max * scale - 10, **{"class": "polar-axis"}),
            ]
            elements.append(group("\n".join(axes_elements)))

        # Draw curves
        for func, curve_points in zip(functions, all_curves):
            color = func.get("color", "#2196F3")
            label = func.get("label")

            path_parts = []
            in_path = False

            for theta, r, valid in curve_points:
                if valid and r >= 0:  # Only positive r
                    px, py = polar_to_svg(r, theta)
                    if not in_path:
                        path_parts.append(f"M {px} {py}")
                        in_path = True
                    else:
                        path_parts.append(f"L {px} {py}")
                else:
                    in_path = False

            if path_parts:
                elements.append(path(" ".join(path_parts), stroke=color, stroke_width="2", fill="none"))

            # Also handle negative r (reflected)
            neg_path_parts = []
            in_path = False
            for theta, r, valid in curve_points:
                if valid and r < 0:
                    # Negative r means reflect through origin
                    px, py = polar_to_svg(-r, theta + math.pi)
                    if not in_path:
                        neg_path_parts.append(f"M {px} {py}")
                        in_path = True
                    else:
                        neg_path_parts.append(f"L {px} {py}")
                else:
                    in_path = False

            if neg_path_parts:
                elements.append(path(" ".join(neg_path_parts), stroke=color, stroke_width="2", fill="none",
                               stroke_dasharray="4,2"))

        # Highlight point
        if point_at is not None:
            theta = float(point_at)
            r = _eval_polar(functions[0].get("expr", "1"), theta)
            if math.isfinite(r):
                px, py = polar_to_svg(abs(r), theta if r >= 0 else theta + math.pi)
                elements.append(circle(px, py, 6, **{"class": "polar-point"}))
                # Draw radius line
                elements.append(line(center_x, center_y, px, py, stroke="#FF9800", stroke_width="2"))
                # Label
                coord_text = f"(r={r:.2f}, θ={theta:.2f})"
                elements.append(text(px + 10, py - 10, coord_text, **{"class": "polar-coord-label"}))

        # Origin
        elements.append(circle(center_x, center_y, 3, fill="#333"))

        # Title
        if title:
            elements.append(text(svg_width / 2, 20, title, **{"class": "polar-title", "text_anchor": "middle"}))

        return svg_document("\n".join(elements), svg_width, svg_height)

    def _nice_step(self, range_val: float) -> float:
        """Calculate a 'nice' step size."""
        if range_val <= 0:
            return 1
        rough_step = range_val / 4
        magnitude = 10 ** math.floor(math.log10(rough_step))
        residual = rough_step / magnitude

        if residual > 5:
            return 10 * magnitude
        elif residual > 2:
            return 5 * magnitude
        elif residual > 1:
            return 2 * magnitude
        else:
            return magnitude

    def _styles(self) -> str:
        return """
.polar-grid { fill: none; stroke: #e0e0e0; stroke-width: 1; }
.polar-ray { stroke: #e0e0e0; stroke-width: 1; }
.polar-axis { stroke: #999; stroke-width: 1.5; }
.polar-label { font-size: 10px; font-family: sans-serif; fill: #999; }
.polar-angle-label { font-size: 9px; font-family: sans-serif; fill: #999; }
.polar-point { fill: #FF9800; stroke: #E65100; stroke-width: 2; }
.polar-coord-label { font-size: 11px; font-family: sans-serif; fill: #333; }
.polar-title { font-size: 14px; font-family: sans-serif; fill: #333; font-weight: bold; }
"""
