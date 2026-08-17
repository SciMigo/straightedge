"""Function graph diagram template.

Plots 1D functions with optional tangent lines, extrema, and area fills.
Supports common function types and custom expressions.
"""

from __future__ import annotations

import math
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

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


# Built-in function library for common expressions that benefit from
# direct evaluation (special handling for domain restrictions, etc.)
BUILTIN_FUNCTIONS: Dict[str, Callable[[float], float]] = {
    "x": lambda x: x,
    "x^2": lambda x: x ** 2,
    "x^3": lambda x: x ** 3,
    "sqrt(x)": lambda x: math.sqrt(x) if x >= 0 else float('nan'),
    "1/x": lambda x: 1 / x if x != 0 else float('nan'),
    "sin(x)": lambda x: math.sin(x),
    "cos(x)": lambda x: math.cos(x),
    "tan(x)": lambda x: math.tan(x) if abs(math.cos(x)) > 0.01 else float('nan'),
    "e^x": lambda x: math.exp(x),
    "ln(x)": lambda x: math.log(x) if x > 0 else float('nan'),
    "abs(x)": lambda x: abs(x),
    "|x|": lambda x: abs(x),
    "sin(1/x)": lambda x: math.sin(1 / x) if x != 0 else float('nan'),
}


def _add_implicit_multiplication(expr: str) -> str:
    """Insert explicit * for implicit multiplication.

    Handles cases like:
        2x      → 2*x
        3x^2    → 3*x^2
        2sin(x) → 2*sin(x)
        2pi     → 2*pi
        2(x+1)  → 2*(x+1)
        (x+1)(x-1) → (x+1)*(x-1)
        (x+1)x  → (x+1)*x
        x(x+1)  → x*(x+1)  (x is not a function name)
    """
    # Number followed by letter (variable, function, or constant): 2x, 2sin, 2pi
    expr = re.sub(r'(\d)([a-zA-Z])', r'\1*\2', expr)

    # Number followed by opening paren: 2(x+1)
    expr = re.sub(r'(\d)\(', r'\1*(', expr)

    # Closing paren followed by opening paren: (x+1)(x-1)
    expr = re.sub(r'\)\(', r')*(', expr)

    # Closing paren followed by letter: (x+1)x, (x+1)sin(x)
    expr = re.sub(r'\)([a-zA-Z])', r')*\1', expr)

    # Letter/variable followed by opening paren, but only for 'x' (not function names)
    # We need to be careful: sin(x) should stay as sin(x), but x(x+1) should become x*(x+1)
    # Only insert * after single 'x' followed by '('
    expr = re.sub(r'\bx\(', r'x*(', expr)

    return expr


#: Golden ratio, bound as a variable because it is not one of the constants the
#: shared allowlist knows. Callers plot it by name.
_PHI = (1 + math.sqrt(5)) / 2


def _is_plottable(expr: str) -> bool:
    """Whether ``expr`` will reduce to numbers, checked once before drawing.

    See ``riemann_sum._is_plottable``: the expression is tried, not just parsed,
    because the allowlist admits arithmetic the evaluator still refuses.
    """
    if expr in BUILTIN_FUNCTIONS:
        return True
    normalized = _add_implicit_multiplication(normalize_expression(str(expr)))
    if not validate_expression(normalized, variables={"x", "phi"}):
        return False
    try:
        evaluate(normalized, x=1.0, phi=_PHI)
    except ExpressionError:
        return False
    except Exception:
        pass
    return True


def _safe_eval(expr: str, x: float) -> float:
    """Safely evaluate a mathematical expression at x."""
    # Check for built-in function
    if expr in BUILTIN_FUNCTIONS:
        try:
            return BUILTIN_FUNCTIONS[expr](x)
        except (ValueError, ZeroDivisionError, OverflowError):
            return float('nan')

    # Anything not named above goes through the shared allowlist in
    # straightedge.expr. The character-set check this replaced passed anything
    # alphabetic, so a payload spelled with attribute access and a subscript
    # walked straight into eval; an AST walk cannot be talked around that way.
    # ``ln`` is accepted as a standalone BUILTIN_FUNCTIONS entry ("ln(x)"), so
    # it must also resolve inside compound expressions like "-x*ln(x)" —
    # otherwise those silently evaluate to NaN and the curve renders empty. It
    # is in the shared function table for that reason.
    try:
        safe_expr = _add_implicit_multiplication(expr.replace("^", "**"))
        return evaluate(safe_expr, x=x, phi=_PHI)
    except Exception:
        return float('nan')


@register("function_graph")
class FunctionGraphTemplate:
    """Render a 1D function graph with optional annotations."""

    def render(self, params: Dict[str, Any]) -> str:
        """Render the function graph as SVG.

        Params:
            function: Function expression (e.g., "x^2", "sin(x)")
            functions: List of functions [{expr, color, label?}] for multiple curves
            x_min, x_max: X-axis range (default: -5, 5)
            y_min, y_max: Y-axis range (default: auto or -5, 5)
            samples: Number of sample points (default: 100)
            show_grid: Show background grid (default: True)
            show_axes: Show axes (default: True)
            tangent_at: X-value to draw tangent line (optional)
            tangent_color: Color for tangent line (default: #FF9800)
            show_extrema: Highlight local min/max (default: False)
            fill_area: Fill area under curve [{from, to, color}]
            points: Additional points to mark [{x, y, color?, label?, style?}]
                    style can be "filled" (default), "open" (hollow circle for holes/discontinuities)
            horizontal_band: Horizontal band (ε-band) {y_center, half_width, color?, label?}
            vertical_band: Vertical band (δ-band) {x_center, half_width, color?, label?}
            limit_point: Mark the limit point {x, y, color?, show_dashed_lines?}
            animate_zoom: Zoom animation {target_x, target_y, start_scale, end_scale, duration_s?}
            animate_bands: Animate bands shrinking {start_epsilon, end_epsilon, start_delta, end_delta, duration_s?}
            title: Optional title
            width, height: SVG dimensions (default: 400x300)
            equal_aspect: Force equal scaling for x and y axes (default: True when bands present)
        """
        # Extract parameters
        func_expr = params.get("function", "x^2")
        if not _is_plottable(func_expr):
            return ""      # see riemann_sum: chrome alone reads as a figure

        functions = params.get("functions", [])
        x_min = float(params.get("x_min", -5))
        x_max = float(params.get("x_max", 5))
        y_min_param = params.get("y_min")
        y_max_param = params.get("y_max")
        equal_aspect = params.get("equal_aspect")
        samples = int(params.get("samples", 100))
        show_grid = bool(params.get("show_grid", True))
        show_axes = bool(params.get("show_axes", True))
        tangent_at = params.get("tangent_at")
        tangent_color = params.get("tangent_color", "#FF9800")
        show_extrema = bool(params.get("show_extrema", False))
        fill_areas = params.get("fill_area", [])
        extra_points = params.get("points", [])
        horizontal_band = params.get("horizontal_band")
        vertical_band = params.get("vertical_band")
        limit_point = params.get("limit_point")
        animate_zoom = params.get("animate_zoom")
        animate_bands = params.get("animate_bands")
        title = params.get("title")
        svg_width = int(params.get("width", 400))
        svg_height = int(params.get("height", 300))
        padding = int(params.get("padding", 40))
        # Axis color: default dark for light backgrounds; pass a light tone
        # (e.g. "#cfd8e6") to keep the axis legible on a dark-themed deck.
        axis_color = params.get("axis_color", "#333")

        # Add extra right padding for band labels if bands are present
        right_label_padding = 0
        if horizontal_band or vertical_band:
            right_label_padding = 60  # Extra space for "ε = 0.5" type labels

        # Build function list
        if not functions:
            functions = [{"expr": func_expr, "color": "#2196F3"}]

        # Sample all functions to determine y range
        all_points: List[Tuple[float, float]] = []
        func_curves: List[List[Tuple[float, float]]] = []

        for func in functions:
            expr = func.get("expr", "x")
            curve_points = []

            # Use adaptive sampling for sin(1/x) - sample uniformly in 1/x space
            # to properly capture the rapid oscillations near x=0
            if expr == "sin(1/x)" and x_min > 0:
                # Sample in reciprocal space for better coverage of oscillations
                # Near x=0, oscillations are rapid, so we need more points there
                t_max = 1.0 / x_min  # 1/x at x_min (large, where oscillations are rapid)
                t_min = 1.0 / x_max  # 1/x at x_max (small, slower oscillations)

                for i in range(samples + 1):
                    t = t_min + (t_max - t_min) * i / samples
                    x = 1.0 / t
                    y = _safe_eval(expr, x)
                    if math.isfinite(y):
                        curve_points.append((x, y))
                        all_points.append((x, y))
                # Sort by x for proper path drawing
                curve_points.sort(key=lambda p: p[0])
            else:
                # Standard uniform sampling in x-space
                for i in range(samples + 1):
                    x = x_min + (x_max - x_min) * i / samples
                    y = _safe_eval(expr, x)
                    if math.isfinite(y):
                        curve_points.append((x, y))
                        all_points.append((x, y))
            func_curves.append(curve_points)

        # Auto-determine y range if not specified
        if all_points:
            y_values = [p[1] for p in all_points]
            auto_y_min = min(y_values)
            auto_y_max = max(y_values)
            # Add some padding
            y_padding = (auto_y_max - auto_y_min) * 0.1 or 1
            auto_y_min -= y_padding
            auto_y_max += y_padding
        else:
            auto_y_min, auto_y_max = -5, 5

        y_min = float(y_min_param) if y_min_param is not None else auto_y_min
        y_max = float(y_max_param) if y_max_param is not None else auto_y_max

        # Calculate plot area (account for extra right padding for labels)
        total_svg_width = svg_width + right_label_padding
        plot_width = svg_width - 2 * padding
        plot_height = svg_height - 2 * padding
        x_range = x_max - x_min
        y_range = y_max - y_min

        # Apply equal aspect ratio when bands are present (so ε and δ are visually comparable)
        # Default to True when both horizontal and vertical bands are present
        if equal_aspect is None:
            equal_aspect = (horizontal_band is not None and vertical_band is not None)

        if equal_aspect:
            # Calculate pixels per unit for each axis
            px_per_unit_x = plot_width / x_range
            px_per_unit_y = plot_height / y_range

            # Use the smaller scale (larger range) to ensure everything fits
            if px_per_unit_x > px_per_unit_y:
                # X has more pixels per unit, need to expand x_range
                target_x_range = plot_width / px_per_unit_y
                x_center = (x_min + x_max) / 2
                if limit_point and isinstance(limit_point, dict):
                    x_center = float(limit_point.get("x", x_center))
                x_min = x_center - target_x_range / 2
                x_max = x_center + target_x_range / 2
                x_range = target_x_range
            else:
                # Y has more pixels per unit, need to expand y_range
                target_y_range = plot_height / px_per_unit_x
                y_center = (y_min + y_max) / 2
                if limit_point and isinstance(limit_point, dict):
                    y_center = float(limit_point.get("y", y_center))
                y_min = y_center - target_y_range / 2
                y_max = y_center + target_y_range / 2
                y_range = target_y_range

        def to_svg_x(x: float) -> float:
            return padding + (x - x_min) / x_range * plot_width

        def to_svg_y(y: float) -> float:
            return padding + (y_max - y) / y_range * plot_height

        elements: List[str] = []
        elements.append(style(self._styles()))

        # Grid
        if show_grid:
            grid_lines = []
            grid_step = self._nice_step(x_range)
            x = math.ceil(x_min / grid_step) * grid_step
            while x <= x_max:
                px = to_svg_x(x)
                grid_lines.append(line(px, padding, px, svg_height - padding, **{"class": "func-grid"}))
                x += grid_step

            grid_step_y = self._nice_step(y_range)
            y = math.ceil(y_min / grid_step_y) * grid_step_y
            while y <= y_max:
                py = to_svg_y(y)
                grid_lines.append(line(padding, py, svg_width - padding, py, **{"class": "func-grid"}))
                y += grid_step_y
            elements.append(group("\n".join(grid_lines)))

        # Axes — use an explicit stroke (a CSS class would let .func-axis's #333
        # win over the attribute and stay invisible on dark decks). The x-axis is
        # drawn slightly heavier than the y-axis so "the area sits on it" reads.
        if show_axes:
            axes_elements = []
            if y_min <= 0 <= y_max:
                y0 = to_svg_y(0)
                axes_elements.append(line(padding, y0, svg_width - padding, y0,
                                          stroke=axis_color, stroke_width="2.5"))
            if x_min <= 0 <= x_max:
                x0 = to_svg_x(0)
                axes_elements.append(line(x0, svg_height - padding, x0, padding,
                                          stroke=axis_color, stroke_width="1.5"))
            elements.append(group("\n".join(axes_elements)))

        # Horizontal band (ε-band) - drawn before curves so it's behind
        if horizontal_band and isinstance(horizontal_band, dict):
            y_center = float(horizontal_band.get("y_center", 0))
            half_width = float(horizontal_band.get("half_width", 0.5))
            band_color = horizontal_band.get("color", "rgba(76, 175, 80, 0.25)")
            band_label = horizontal_band.get("label")

            y_top = to_svg_y(y_center + half_width)
            y_bottom = to_svg_y(y_center - half_width)
            band_height = y_bottom - y_top

            elements.append(
                f'<rect x="{padding}" y="{y_top}" width="{plot_width}" height="{band_height}" '
                f'fill="{band_color}" stroke="none" class="epsilon-band"/>'
            )
            # Dashed lines at band edges
            elements.append(line(padding, y_top, svg_width - padding, y_top,
                                 stroke="#4CAF50", stroke_width="1", stroke_dasharray="4,2"))
            elements.append(line(padding, y_bottom, svg_width - padding, y_bottom,
                                 stroke="#4CAF50", stroke_width="1", stroke_dasharray="4,2"))
            # Label
            if band_label:
                elements.append(text(svg_width - padding + 5, (y_top + y_bottom) / 2 + 4,
                                     band_label, **{"class": "band-label", "fill": "#4CAF50"}))
            else:
                # Default ε label
                elements.append(text(svg_width - padding + 5, (y_top + y_bottom) / 2 + 4,
                                     "ε", **{"class": "band-label", "fill": "#4CAF50"}))

        # Vertical band (δ-band) - drawn before curves so it's behind
        if vertical_band and isinstance(vertical_band, dict):
            x_center = float(vertical_band.get("x_center", 0))
            half_width = float(vertical_band.get("half_width", 0.5))
            band_color = vertical_band.get("color", "rgba(33, 150, 243, 0.25)")
            band_label = vertical_band.get("label")

            x_left = to_svg_x(x_center - half_width)
            x_right = to_svg_x(x_center + half_width)
            band_width = x_right - x_left

            elements.append(
                f'<rect x="{x_left}" y="{padding}" width="{band_width}" height="{plot_height}" '
                f'fill="{band_color}" stroke="none" class="delta-band"/>'
            )
            # Dashed lines at band edges
            elements.append(line(x_left, padding, x_left, svg_height - padding,
                                 stroke="#2196F3", stroke_width="1", stroke_dasharray="4,2"))
            elements.append(line(x_right, padding, x_right, svg_height - padding,
                                 stroke="#2196F3", stroke_width="1", stroke_dasharray="4,2"))
            # Label
            if band_label:
                elements.append(text((x_left + x_right) / 2, svg_height - padding + 15,
                                     band_label, **{"class": "band-label", "fill": "#2196F3", "text_anchor": "middle"}))
            else:
                # Default δ label
                elements.append(text((x_left + x_right) / 2, svg_height - padding + 15,
                                     "δ", **{"class": "band-label", "fill": "#2196F3", "text_anchor": "middle"}))

        # Fill areas under curves
        if fill_areas:
            for area in fill_areas:
                if not isinstance(area, dict):
                    continue
                a_from = float(area.get("from", x_min))
                a_to = float(area.get("to", x_max))
                a_color = area.get("color", "rgba(33, 150, 243, 0.3)")
                func_idx = int(area.get("function_index", 0))

                if func_idx < len(func_curves):
                    fill_points = [p for p in func_curves[func_idx] if a_from <= p[0] <= a_to]
                    if fill_points:
                        # Build path for filled area
                        path_d = f"M {to_svg_x(a_from)} {to_svg_y(0)}"
                        for px, py in fill_points:
                            path_d += f" L {to_svg_x(px)} {to_svg_y(py)}"
                        path_d += f" L {to_svg_x(a_to)} {to_svg_y(0)} Z"
                        elements.append(path(path_d, fill=a_color, stroke="none"))

                    # Mark the integration bounds: a vertical drop-line from the
                    # axis up to the curve at each labelled edge, plus a tick label
                    # under the axis. Makes x=a / x=b explicit on the曲边梯形.
                    expr = functions[func_idx].get("expr", "x") if func_idx < len(functions) else "x"
                    y0_px = to_svg_y(0)
                    for bound_x, lbl in ((a_from, area.get("from_label")),
                                         (a_to, area.get("to_label"))):
                        if not lbl:
                            continue
                        by = _safe_eval(expr, bound_x)
                        if not math.isfinite(by):
                            by = 0.0
                        bx_px = to_svg_x(bound_x)
                        elements.append(line(bx_px, y0_px, bx_px, to_svg_y(by),
                                             stroke=axis_color, stroke_width="1.3",
                                             stroke_dasharray="4,3"))
                        elements.append(text(bx_px, y0_px + 18, str(lbl),
                                             **{"fill": axis_color, "font-size": "15",
                                                "font-style": "italic", "text-anchor": "middle"}))

        # Draw function curves
        for i, (func, curve_points) in enumerate(zip(functions, func_curves)):
            if not curve_points:
                continue

            color = func.get("color", "#2196F3")
            label = func.get("label")

            # Build path
            path_parts = []
            in_path = False
            for x, y in curve_points:
                px, py = to_svg_x(x), to_svg_y(y)
                # Clip to view
                if padding <= py <= svg_height - padding:
                    if not in_path:
                        path_parts.append(f"M {px} {py}")
                        in_path = True
                    else:
                        path_parts.append(f"L {px} {py}")
                else:
                    in_path = False

            if path_parts:
                elements.append(path(" ".join(path_parts), stroke=color, stroke_width="2", fill="none"))

            # Label
            if label and curve_points:
                last_point = curve_points[-1]
                lx, ly = to_svg_x(last_point[0]), to_svg_y(last_point[1])
                elements.append(text(lx + 5, ly, label, **{"class": "func-label", "fill": color}))

        # Tangent line
        if tangent_at is not None and functions:
            tx = float(tangent_at)
            expr = functions[0].get("expr", "x")
            ty = _safe_eval(expr, tx)

            if math.isfinite(ty):
                # Numerical derivative
                h = 0.001
                dy = (_safe_eval(expr, tx + h) - _safe_eval(expr, tx - h)) / (2 * h)

                if math.isfinite(dy):
                    # Draw tangent line
                    t_x1, t_x2 = tx - 1, tx + 1
                    t_y1, t_y2 = ty - dy, ty + dy

                    elements.append(line(
                        to_svg_x(t_x1), to_svg_y(t_y1),
                        to_svg_x(t_x2), to_svg_y(t_y2),
                        stroke=tangent_color, stroke_width="2", stroke_dasharray="5,3"
                    ))
                    # Mark tangent point
                    elements.append(circle(to_svg_x(tx), to_svg_y(ty), 5, fill=tangent_color))

        # Extrema detection
        if show_extrema and func_curves:
            extrema_elements = []
            curve = func_curves[0]
            for i in range(1, len(curve) - 1):
                prev_y, curr_y, next_y = curve[i-1][1], curve[i][1], curve[i+1][1]
                x, y = curve[i]

                if curr_y > prev_y and curr_y > next_y:  # Local max
                    extrema_elements.append(circle(to_svg_x(x), to_svg_y(y), 6, **{"class": "func-point-max"}))
                    extrema_elements.append(text(to_svg_x(x), to_svg_y(y) - 10, "max", **{"class": "func-extrema-label"}))
                elif curr_y < prev_y and curr_y < next_y:  # Local min
                    extrema_elements.append(circle(to_svg_x(x), to_svg_y(y), 6, **{"class": "func-point-min"}))
                    extrema_elements.append(text(to_svg_x(x), to_svg_y(y) + 15, "min", **{"class": "func-extrema-label"}))

            elements.append(group("\n".join(extrema_elements)))

        # Extra points
        for pt in extra_points:
            if not isinstance(pt, dict):
                continue
            px = to_svg_x(float(pt.get("x", 0)))
            py = to_svg_y(float(pt.get("y", 0)))
            pt_color = pt.get("color", "#FF9800")
            pt_style = pt.get("style", "filled")

            if pt_style == "open":
                # Open circle (hollow) - for discontinuities/holes
                elements.append(circle(px, py, 6, fill="white", stroke=pt_color, stroke_width="2"))
            else:
                # Filled circle (default)
                elements.append(circle(px, py, 5, fill=pt_color))

            if pt.get("label"):
                elements.append(text(px + 10, py - 5, pt["label"], **{"class": "func-label"}))

        # Limit point - special marker for the limit value
        if limit_point and isinstance(limit_point, dict):
            lp_x = float(limit_point.get("x", 0))
            lp_y = float(limit_point.get("y", 0))
            lp_color = limit_point.get("color", "#E91E63")
            show_dashed = limit_point.get("show_dashed_lines", True)

            lpx = to_svg_x(lp_x)
            lpy = to_svg_y(lp_y)

            if show_dashed:
                # Dashed lines from point to axes
                if y_min <= 0 <= y_max:
                    y_axis = to_svg_y(0)
                    elements.append(line(lpx, lpy, lpx, y_axis,
                                         stroke=lp_color, stroke_width="1", stroke_dasharray="3,3"))
                if x_min <= 0 <= x_max:
                    x_axis = to_svg_x(0)
                    elements.append(line(lpx, lpy, x_axis, lpy,
                                         stroke=lp_color, stroke_width="1", stroke_dasharray="3,3"))

            # The limit point marker
            elements.append(circle(lpx, lpy, 6, fill=lp_color, stroke="#fff", stroke_width="2"))

            # Label
            lp_label = limit_point.get("label", f"({lp_x}, {lp_y})")
            elements.append(text(lpx + 10, lpy - 8, lp_label, **{"class": "func-label", "fill": lp_color}))

        # Title
        if title:
            # Inline style beats the .func-title #333 fill so the title stays
            # legible when axis_color is set for a dark deck.
            elements.append(text(svg_width / 2, 18, title,
                                 **{"class": "func-title", "text_anchor": "middle",
                                    "style": f"fill:{axis_color}"}))

        # Handle animations
        animation_styles = ""

        if animate_zoom and isinstance(animate_zoom, dict):
            # Zoom animation - zooms into a target point
            target_x = float(animate_zoom.get("target_x", (x_min + x_max) / 2))
            target_y = float(animate_zoom.get("target_y", (y_min + y_max) / 2))
            start_scale = float(animate_zoom.get("start_scale", 1))
            end_scale = float(animate_zoom.get("end_scale", 3))
            duration = float(animate_zoom.get("duration_s", 8))  # Default slower: 8s
            delay = float(animate_zoom.get("delay_s", 2))  # Default delay: 2s

            # Calculate transform origin in SVG coordinates
            origin_x = to_svg_x(target_x)
            origin_y = to_svg_y(target_y)

            animation_styles += f"""
@keyframes zoomIn {{
  0% {{ transform: scale({start_scale}); }}
  100% {{ transform: scale({end_scale}); }}
}}
.zoom-container {{
  transform: scale({start_scale});
  transform-origin: {origin_x}px {origin_y}px;
}}
section.present .zoom-container {{
  animation: zoomIn {duration}s ease-in-out {delay}s forwards;
}}
"""
            # Wrap all elements (except style) in zoom container
            style_elem = elements[0]  # The style is always first
            content_elems = elements[1:]
            elements = [style_elem, f'<g class="zoom-container">', *content_elems, '</g>']

        if animate_bands and isinstance(animate_bands, dict):
            # Band shrinking animation
            start_eps = float(animate_bands.get("start_epsilon", 1))
            end_eps = float(animate_bands.get("end_epsilon", 0.1))
            start_delta = float(animate_bands.get("start_delta", 0.5))
            end_delta = float(animate_bands.get("end_delta", 0.05))
            duration = float(animate_bands.get("duration_s", 3))

            # Calculate pixel values for band heights/widths
            eps_start_h = abs(to_svg_y(0) - to_svg_y(start_eps)) * 2
            eps_end_h = abs(to_svg_y(0) - to_svg_y(end_eps)) * 2
            delta_start_w = abs(to_svg_x(start_delta) - to_svg_x(0)) * 2
            delta_end_w = abs(to_svg_x(end_delta) - to_svg_x(0)) * 2

            animation_styles += f"""
@keyframes shrinkEpsilon {{
  0% {{ height: {eps_start_h}px; }}
  100% {{ height: {eps_end_h}px; }}
}}
@keyframes shrinkDelta {{
  0% {{ width: {delta_start_w}px; }}
  100% {{ width: {delta_end_w}px; }}
}}
.epsilon-band {{
  animation: shrinkEpsilon {duration}s ease-in-out forwards;
}}
.delta-band {{
  animation: shrinkDelta {duration}s ease-in-out forwards;
}}
"""

        # Add animation styles if any
        if animation_styles:
            elements[0] = style(self._styles() + animation_styles)

        return svg_document("\n".join(elements), total_svg_width, svg_height)

    def _nice_step(self, range_val: float) -> float:
        """Calculate a 'nice' step size for grid lines."""
        rough_step = range_val / 5
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
.func-grid { stroke: #e0e0e0; stroke-width: 1; }
.func-axis { stroke: #333; stroke-width: 2; }
.func-label { font-size: 12px; font-family: sans-serif; }
.func-title { font-size: 14px; font-family: sans-serif; fill: #333; font-weight: bold; }
.func-point-max { fill: #4CAF50; stroke: #2E7D32; stroke-width: 2; }
.func-point-min { fill: #f44336; stroke: #c62828; stroke-width: 2; }
.func-extrema-label { font-size: 10px; font-family: sans-serif; fill: #666; text-anchor: middle; }
.band-label { font-size: 14px; font-family: sans-serif; font-weight: bold; }
.epsilon-band { opacity: 0.9; }
.delta-band { opacity: 0.9; }
"""
