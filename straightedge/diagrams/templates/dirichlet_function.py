"""Dirichlet-style function visualization.

Visualizes functions like f(x) = x² if x is rational, 0 if x is irrational.
Since we can't truly plot this, we show an approximation with scattered points.
"""

from __future__ import annotations

import math
import random
from typing import Any, Dict, List

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


@register("dirichlet_function")
class DirichletFunctionTemplate:
    """Render a Dirichlet-style function visualization."""

    def render(self, params: Dict[str, Any]) -> str:
        """Render the Dirichlet function approximation as SVG.

        Params:
            rational_function: Function for rational x (e.g., "x^2")
            irrational_value: Value for irrational x (default: 0)
            x_min, x_max: X-axis range (default: -2, 2)
            y_min, y_max: Y-axis range (default: -0.5, 4)
            num_points: Number of sample points (default: 100)
            zoom_level: Current zoom level 1-5 (affects point density)
            animate_zoom: Zoom animation params {duration_s, zoom_levels}
            highlight_x: X value to highlight with vertical line
            title: Optional title
            width, height: SVG dimensions (default: 400x300)
        """
        # Extract parameters
        rational_func = params.get("rational_function", "x^2")
        irrational_val = float(params.get("irrational_value", 0))
        x_min = float(params.get("x_min", -2))
        x_max = float(params.get("x_max", 2))
        y_min = float(params.get("y_min", -0.5))
        y_max = float(params.get("y_max", 4))
        num_points = int(params.get("num_points", 80))
        zoom_level = int(params.get("zoom_level", 1))
        animate_zoom = params.get("animate_zoom")
        highlight_x = params.get("highlight_x")
        title = params.get("title")
        svg_width = int(params.get("width", 400))
        svg_height = int(params.get("height", 300))
        padding = 40

        # Calculate plot area
        plot_width = svg_width - 2 * padding
        plot_height = svg_height - 2 * padding
        x_range = x_max - x_min
        y_range = y_max - y_min

        def to_svg_x(x: float) -> float:
            return padding + (x - x_min) / x_range * plot_width

        def to_svg_y(y: float) -> float:
            return padding + (y_max - y) / y_range * plot_height

        def eval_rational(x: float) -> float:
            if rational_func == "x^2":
                return x ** 2
            elif rational_func == "x":
                return x
            return x ** 2

        elements: List[str] = []
        elements.append(style(self._styles()))

        # Grid
        grid_lines = []
        grid_step = self._nice_step(x_range)
        x = math.ceil(x_min / grid_step) * grid_step
        while x <= x_max:
            px = to_svg_x(x)
            grid_lines.append(line(px, padding, px, svg_height - padding, **{"class": "dirich-grid"}))
            x += grid_step

        grid_step_y = self._nice_step(y_range)
        y = math.ceil(y_min / grid_step_y) * grid_step_y
        while y <= y_max:
            py = to_svg_y(y)
            grid_lines.append(line(padding, py, svg_width - padding, py, **{"class": "dirich-grid"}))
            y += grid_step_y
        elements.append(group("\n".join(grid_lines)))

        # Axes
        axes_elements = []
        if y_min <= 0 <= y_max:
            y0 = to_svg_y(0)
            axes_elements.append(line(padding, y0, svg_width - padding, y0, **{"class": "dirich-axis"}))
        if x_min <= 0 <= x_max:
            x0 = to_svg_x(0)
            axes_elements.append(line(x0, svg_height - padding, x0, padding, **{"class": "dirich-axis"}))
        elements.append(group("\n".join(axes_elements)))

        # Draw the "ghost" curves for reference
        # Rational curve (parabola) - dashed
        curve_points = []
        for i in range(101):
            x = x_min + (x_max - x_min) * i / 100
            y = eval_rational(x)
            if y_min <= y <= y_max:
                curve_points.append((to_svg_x(x), to_svg_y(y)))
        if curve_points:
            path_d = f"M {curve_points[0][0]} {curve_points[0][1]}"
            for px, py in curve_points[1:]:
                path_d += f" L {px} {py}"
            elements.append(path(path_d, stroke="#E91E63", stroke_width="1",
                                 fill="none", stroke_dasharray="4,4", opacity="0.5"))

        # Irrational line (y = 0 usually) - dashed
        if y_min <= irrational_val <= y_max:
            iy = to_svg_y(irrational_val)
            elements.append(line(padding, iy, svg_width - padding, iy,
                                 stroke="#2196F3", stroke_width="1",
                                 stroke_dasharray="4,4", opacity="0.5"))

        # Generate scattered points - mix of "rational" and "irrational".
        # Seeded, so the figure is reproducible -- but on a generator of its
        # own: `random.seed` would reach into the process-wide stream and
        # silently reset the sequence of whoever called us.
        rng = random.Random(42 + zoom_level)

        points_rational = []
        points_irrational = []

        # Increase density with zoom level
        actual_points = num_points * zoom_level

        for _ in range(actual_points):
            x = rng.uniform(x_min, x_max)

            # Alternate between rational and irrational visualization
            if rng.random() < 0.5:
                # "Rational" point - on the curve
                y = eval_rational(x)
                if y_min <= y <= y_max:
                    points_rational.append((to_svg_x(x), to_svg_y(y)))
            else:
                # "Irrational" point - on y = irrational_val
                if y_min <= irrational_val <= y_max:
                    points_irrational.append((to_svg_x(x), to_svg_y(irrational_val)))

        # Draw points
        for px, py in points_rational:
            elements.append(circle(px, py, 3, fill="#E91E63", opacity="0.8"))
        for px, py in points_irrational:
            elements.append(circle(px, py, 3, fill="#2196F3", opacity="0.8"))

        # Legend
        legend_y = padding - 10
        elements.append(circle(padding + 10, legend_y, 4, fill="#E91E63"))
        elements.append(text(padding + 20, legend_y + 4, "rational x → x²", **{"class": "dirich-legend"}))
        elements.append(circle(padding + 130, legend_y, 4, fill="#2196F3"))
        elements.append(text(padding + 140, legend_y + 4, f"irrational x → {irrational_val}", **{"class": "dirich-legend"}))

        # Highlight x value
        if highlight_x is not None:
            hx = float(highlight_x)
            hx_svg = to_svg_x(hx)
            elements.append(line(hx_svg, padding, hx_svg, svg_height - padding,
                                 stroke="#FF9800", stroke_width="2", stroke_dasharray="5,3"))
            elements.append(text(hx_svg, svg_height - padding + 15, f"x = {hx}",
                                 **{"class": "dirich-highlight", "text_anchor": "middle"}))

            # Show both possible values at this x
            y_rat = eval_rational(hx)
            if y_min <= y_rat <= y_max:
                elements.append(circle(hx_svg, to_svg_y(y_rat), 6,
                                       fill="#E91E63", stroke="#fff", stroke_width="2"))
            if y_min <= irrational_val <= y_max:
                elements.append(circle(hx_svg, to_svg_y(irrational_val), 6,
                                       fill="#2196F3", stroke="#fff", stroke_width="2"))

        # Title
        if title:
            elements.append(text(svg_width / 2, svg_height - 10, title,
                                 **{"class": "dirich-title", "text_anchor": "middle"}))

        # Animation
        animation_styles = ""
        if animate_zoom and isinstance(animate_zoom, dict):
            duration = float(animate_zoom.get("duration_s", 5))
            target_x = float(animate_zoom.get("target_x", 0))
            target_y = float(animate_zoom.get("target_y", 0))
            end_scale = float(animate_zoom.get("end_scale", 4))

            origin_x = to_svg_x(target_x)
            origin_y = to_svg_y(target_y)

            animation_styles = f"""
@keyframes dirichZoom {{
  0% {{ transform: scale(1); }}
  100% {{ transform: scale({end_scale}); }}
}}
.zoom-container {{
  animation: dirichZoom {duration}s ease-in-out forwards;
  transform-origin: {origin_x}px {origin_y}px;
}}
"""
            style_elem = elements[0]
            content_elems = elements[1:]
            elements = [style_elem, '<g class="zoom-container">', *content_elems, '</g>']

        if animation_styles:
            elements[0] = style(self._styles() + animation_styles)

        return svg_document("\n".join(elements), svg_width, svg_height)

    def _nice_step(self, range_val: float) -> float:
        if range_val <= 0:
            return 1
        rough_step = range_val / 5
        magnitude = 10 ** math.floor(math.log10(rough_step))
        residual = rough_step / magnitude
        if residual > 5:
            return 10 * magnitude
        elif residual > 2:
            return 5 * magnitude
        elif residual > 1:
            return 2 * magnitude
        return magnitude

    def _styles(self) -> str:
        return """
.dirich-grid { stroke: #e0e0e0; stroke-width: 1; }
.dirich-axis { stroke: #333; stroke-width: 2; }
.dirich-legend { font-size: 11px; font-family: sans-serif; fill: #666; }
.dirich-title { font-size: 13px; font-family: sans-serif; fill: #333; font-weight: bold; }
.dirich-highlight { font-size: 12px; font-family: sans-serif; fill: #FF9800; font-weight: bold; }
"""
