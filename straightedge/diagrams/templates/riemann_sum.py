"""Riemann sum diagram template.

Visualizes integration concepts with rectangles approximating area under a curve.
Supports left, right, midpoint, and trapezoidal rules.
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
    rect,
    style,
    svg_document,
    text,
)


# Built-in functions (shared with function_graph)
BUILTIN_FUNCTIONS: Dict[str, Callable[[float], float]] = {
    "x": lambda x: x,
    "x^2": lambda x: x ** 2,
    "x^3": lambda x: x ** 3,
    "sqrt(x)": lambda x: math.sqrt(x) if x >= 0 else 0,
    "sin(x)": lambda x: math.sin(x),
    "cos(x)": lambda x: math.cos(x),
    "e^x": lambda x: math.exp(x),
    "1/(1+x^2)": lambda x: 1 / (1 + x ** 2),
}


def _is_plottable(expr: str) -> bool:
    """Whether ``expr`` will reduce to numbers, checked once before drawing.

    Validation alone is not the question. ``9^9^9^9`` is inside the allowlist —
    four literals and a permitted operator — and is refused only when the
    evaluator meets its exponent bound, so the expression has to be tried, not
    just parsed. A probe that fails on the *domain* proves nothing, though:
    ``sqrt(x)`` and ``ln(x)`` are NaN over half the line and still plot.
    """
    if expr in BUILTIN_FUNCTIONS:
        return True
    normalized = normalize_expression(str(expr))
    if not validate_expression(normalized, variables={"x"}):
        return False
    try:
        evaluate(normalized, x=1.0)
    except ExpressionError:
        return False
    except Exception:
        pass
    return True


def _eval_func(expr: str, x: float) -> float:
    """Evaluate a function expression at x.

    NaN, never 0, for anything that does not reduce to a number. A zero is a
    drawable height: a mistyped expression used to render a complete-looking
    figure of five rectangles that ``is_blank_diagram`` reported as fine, which
    is the one failure this library exists to make impossible.
    """
    if expr in BUILTIN_FUNCTIONS:
        try:
            return BUILTIN_FUNCTIONS[expr](x)
        except Exception:
            return math.nan

    try:
        return evaluate(normalize_expression(expr), x=x)
    except Exception:
        return math.nan


@register("riemann_sum")
class RiemannSumTemplate:
    """Render a Riemann sum visualization."""

    def render(self, params: Dict[str, Any]) -> str:
        """Render the Riemann sum as SVG.

        Params:
            function: Function expression (default: "x^2")
            a, b: Integration bounds (default: 0, 2)
            n: Number of rectangles (default: 5)
            method: "left", "right", "midpoint", "trapezoid" (default: "left")
            show_curve: Show the actual curve (default: True)
            show_rectangles: Show approximating rectangles (default: True)
            show_area_value: Show computed area approximation (default: True)
            fill_color: Rectangle fill color (default: "rgba(33, 150, 243, 0.4)")
            stroke_color: Rectangle stroke color (default: "#2196F3")
            curve_color: Curve color (default: "#333")
            width, height: SVG dimensions (default: 450x300)
            title: Optional title
        """
        # Extract parameters
        func_expr = params.get("function", "x^2")
        if not _is_plottable(func_expr):
            # Nothing to draw. Returning the chrome would be worse than
            # returning nothing: axes and a grid read as a figure, and the
            # rectangles would carry NaN heights that no renderer draws but
            # every element count sees.
            return ""
        a = float(params.get("a", 0))
        b = float(params.get("b", 2))
        n = int(params.get("n", 5))
        method = params.get("method", "left")
        show_curve = bool(params.get("show_curve", True))
        show_rectangles = bool(params.get("show_rectangles", True))
        show_area_value = bool(params.get("show_area_value", False))
        fill_color = params.get("fill_color", "rgba(33, 150, 243, 0.4)")
        stroke_color = params.get("stroke_color", "#2196F3")
        # axis_color: default dark for light backgrounds; pass a light tone for a
        # dark-themed deck. curve_color defaults to follow it so the curve never
        # disappears against the page.
        axis_color = params.get("axis_color", "#333")
        curve_color = params.get("curve_color", "#90caf9" if axis_color != "#333" else "#333")
        svg_width = int(params.get("width", 450))
        svg_height = int(params.get("height", 300))
        title = params.get("title")
        # annotate one rectangle with its width (Δx) and height (f(ξ_i)).
        annotate_index = params.get("annotate_index")
        padding = 50

        # Calculate function values
        dx = (b - a) / n
        samples = 100

        # Sample curve for display
        curve_points: List[Tuple[float, float]] = []
        x_min, x_max = a - 0.5, b + 0.5
        for i in range(samples + 1):
            x = x_min + (x_max - x_min) * i / samples
            y = _eval_func(func_expr, x)
            curve_points.append((x, y))

        # Get y range
        y_values = [p[1] for p in curve_points if math.isfinite(p[1])]
        if y_values:
            y_min = min(0, min(y_values) - 0.5)
            y_max = max(0, max(y_values) + 0.5)
        else:
            y_min, y_max = -1, 5

        # Plot dimensions
        plot_width = svg_width - 2 * padding
        plot_height = svg_height - 2 * padding
        x_range = x_max - x_min
        y_range = y_max - y_min

        def to_svg_x(x: float) -> float:
            return padding + (x - x_min) / x_range * plot_width

        def to_svg_y(y: float) -> float:
            return padding + (y_max - y) / y_range * plot_height

        elements: List[str] = []
        elements.append(style(self._styles()))

        # Grid. `+ 1`, not `+ 2`: the integers inside the plot run up to
        # int(x_max), so overshooting drew one line past the right edge of the
        # data area — off the canvas entirely at 458px on a 450px figure — and
        # one above the top. Invisible, so nothing complained until the frame
        # check stopped skipping axis-aligned strokes for having no area.
        grid_lines = []
        for i in range(int(x_min), int(x_max) + 1):
            px = to_svg_x(i)
            grid_lines.append(line(px, padding, px, svg_height - padding, **{"class": "rs-grid"}))
        for i in range(int(y_min), int(y_max) + 1):
            py = to_svg_y(i)
            grid_lines.append(line(padding, py, svg_width - padding, py, **{"class": "rs-grid"}))
        elements.append(group("\n".join(grid_lines)))

        # Axes — explicit stroke (a CSS class would let .rs-axis's #333 win over
        # the attribute and stay invisible on dark decks).
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

        # Draw rectangles
        total_area = 0
        if show_rectangles:
            rect_elements = []
            for i in range(n):
                x_left = a + i * dx
                x_right = x_left + dx

                # Determine height based on method
                if method == "left":
                    height = _eval_func(func_expr, x_left)
                elif method == "right":
                    height = _eval_func(func_expr, x_right)
                elif method == "midpoint":
                    height = _eval_func(func_expr, (x_left + x_right) / 2)
                else:  # trapezoid - draw as polygon
                    height = (_eval_func(func_expr, x_left) + _eval_func(func_expr, x_right)) / 2

                total_area += height * dx

                # Rectangle coordinates
                rx = to_svg_x(x_left)
                rw = to_svg_x(x_right) - rx
                ry0 = to_svg_y(0)

                if method == "trapezoid":
                    # Draw trapezoid
                    y_left = _eval_func(func_expr, x_left)
                    y_right = _eval_func(func_expr, x_right)
                    trap_path = f"M {rx} {ry0} L {rx} {to_svg_y(y_left)} L {rx + rw} {to_svg_y(y_right)} L {rx + rw} {ry0} Z"
                    rect_elements.append(path(trap_path, fill=fill_color, stroke=stroke_color, stroke_width="1"))
                else:
                    # Draw rectangle
                    ry = to_svg_y(max(height, 0))
                    rh = abs(to_svg_y(0) - to_svg_y(height))

                    if height >= 0:
                        rect_elements.append(rect(rx, ry, rw, rh, fill=fill_color, stroke=stroke_color, stroke_width="1"))
                    else:
                        rect_elements.append(rect(rx, ry0, rw, rh, fill=fill_color, stroke=stroke_color, stroke_width="1"))

                # Show sample point for left/right/midpoint
                sample_x = x_left
                if method in ("left", "right", "midpoint"):
                    if method == "left":
                        sample_x = x_left
                    elif method == "right":
                        sample_x = x_right
                    else:
                        sample_x = (x_left + x_right) / 2
                    sample_y = _eval_func(func_expr, sample_x)
                    rect_elements.append(circle(to_svg_x(sample_x), to_svg_y(sample_y), 4, fill=stroke_color))

                # Annotate one rectangle: width = Δx, height = f(ξ_i).
                if annotate_index is not None and i == int(annotate_index):
                    sy = _eval_func(func_expr, sample_x)
                    # highlight this rectangle
                    rect_elements.append(rect(rx, to_svg_y(max(sy, 0)), rw,
                                              abs(to_svg_y(0) - to_svg_y(sy)),
                                              fill="rgba(255,193,7,0.25)", stroke="#FFC107", stroke_width="2"))
                    # Δx width marker just under the axis
                    yb = to_svg_y(0) + 14
                    rect_elements.append(line(rx, yb, rx + rw, yb, stroke=axis_color, stroke_width="1.2"))
                    rect_elements.append(line(rx, yb - 3, rx, yb + 3, stroke=axis_color, stroke_width="1.2"))
                    rect_elements.append(line(rx + rw, yb - 3, rx + rw, yb + 3, stroke=axis_color, stroke_width="1.2"))
                    rect_elements.append(text(rx + rw / 2, yb + 14, "Δx",
                                              **{"text_anchor": "middle", "fill": axis_color, "font-size": "13", "font-style": "italic"}))
                    # f(ξ_i) height label at the rectangle top
                    rect_elements.append(text(to_svg_x(sample_x) + 6, to_svg_y(sy) - 6, "f(ξᵢ)",
                                              **{"fill": axis_color, "font-size": "13", "font-style": "italic"}))

            elements.append(group("\n".join(rect_elements)))

        # Draw curve
        if show_curve:
            path_parts = []
            for i, (x, y) in enumerate(curve_points):
                px, py = to_svg_x(x), to_svg_y(y)
                if i == 0:
                    path_parts.append(f"M {px} {py}")
                else:
                    path_parts.append(f"L {px} {py}")
            elements.append(path(" ".join(path_parts), stroke=curve_color, stroke_width="2.5", fill="none"))

        # Integration bounds markers — semantic a / b, cleanly formatted
        # (no "a=0.0"), legible against the axis color.
        def _fmt(v: float) -> str:
            return ("%g" % v)
        lbl_a = "a" if a == 0 else f"a={_fmt(a)}"
        lbl_b = f"b={_fmt(b)}"
        bound_elements = [
            line(to_svg_x(a), padding, to_svg_x(a), svg_height - padding, stroke=axis_color, stroke_width="1", stroke_dasharray="5,3"),
            line(to_svg_x(b), padding, to_svg_x(b), svg_height - padding, stroke=axis_color, stroke_width="1", stroke_dasharray="5,3"),
            text(to_svg_x(a), svg_height - padding + 20, lbl_a, **{"text_anchor": "middle", "fill": axis_color, "font-size": "13", "font-style": "italic"}),
            text(to_svg_x(b), svg_height - padding + 20, lbl_b, **{"text_anchor": "middle", "fill": axis_color, "font-size": "13", "font-style": "italic"}),
        ]
        elements.append(group("\n".join(bound_elements)))

        # Area value — raw "Area ≈ 5.3618 (n=6, midpoint)" debug text reads as a
        # chart artifact; off by default now (opt back in with show_area_value).
        if show_area_value:
            area_text = f"Area ≈ {total_area:.4f} (n={n}, {method})"
            elements.append(text(svg_width / 2, svg_height - 10, area_text, **{"class": "rs-area-label", "text_anchor": "middle", "style": f"fill:{axis_color}"}))

        # Title — only when explicitly provided. The old "∫ x^2 dx from 0 to 1"
        # default read as clunky chart text; the slide caption labels the figure.
        if title and title.strip():
            elements.append(text(svg_width / 2, 20, title, **{"class": "rs-title", "text_anchor": "middle", "style": f"fill:{axis_color}"}))

        return svg_document("\n".join(elements), svg_width, svg_height)

    def _styles(self) -> str:
        return """
.rs-grid { stroke: #e8e8e8; stroke-width: 1; }
.rs-axis { stroke: #333; stroke-width: 2; }
.rs-bound-label { font-size: 11px; font-family: sans-serif; fill: #666; }
.rs-area-label { font-size: 12px; font-family: sans-serif; fill: #333; }
.rs-title { font-size: 14px; font-family: sans-serif; fill: #333; font-weight: bold; }
"""
