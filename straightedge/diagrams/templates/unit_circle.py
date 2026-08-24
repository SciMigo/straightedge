"""Unit circle diagram template.

Visualizes trigonometric concepts on the unit circle including
angles, sin/cos values, and reference triangles.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List

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
    text_width,
)
from ..themes import MATH_THEMES, DiagramTheme, resolve_theme


# Common angles in radians with their labels
COMMON_ANGLES = {
    0: "0",
    30: "π/6",
    45: "π/4",
    60: "π/3",
    90: "π/2",
    120: "2π/3",
    135: "3π/4",
    150: "5π/6",
    180: "π",
    210: "7π/6",
    225: "5π/4",
    240: "4π/3",
    270: "3π/2",
    300: "5π/3",
    315: "7π/4",
    330: "11π/6",
    360: "2π",
}


@register("unit_circle")
class UnitCircleTemplate:
    """Render a unit circle with trigonometric annotations."""

    def render(self, params: Dict[str, Any]) -> str:
        """Render the unit circle as SVG.

        Params:
            angle: Angle in degrees to highlight (default: 45)
            show_triangle: Show reference triangle (default: True)
            show_sin: Highlight sin value (default: True)
            show_cos: Highlight cos value (default: True)
            show_tan: Show tangent line (default: False)
            show_common_angles: Mark common angles (default: False)
            show_coordinates: Show (cos, sin) coordinates (default: True)
            show_arc: Show angle arc (default: True)
            show_labels: Show axis labels (default: True)
            radius_scale: Visual radius multiplier (default: 1)
            width, height: SVG dimensions (default: 400x400)
            title: Optional title
            theme: professional, classroom, dark, high-contrast, or print-friendly
        """
        # Extract parameters
        angle_deg = float(params.get("angle", 45))
        show_triangle = bool(params.get("show_triangle", True))
        show_sin = bool(params.get("show_sin", True))
        show_cos = bool(params.get("show_cos", True))
        show_tan = bool(params.get("show_tan", False))
        show_common_angles = bool(params.get("show_common_angles", False))
        show_coordinates = bool(params.get("show_coordinates", True))
        show_arc = bool(params.get("show_arc", True))
        show_labels = bool(params.get("show_labels", True))
        radius_scale = float(params.get("radius_scale", 1))
        svg_width = int(params.get("width", 400))
        svg_height = int(params.get("height", 400))
        title = params.get("title")
        theme = resolve_theme(params.get("theme", "professional"), MATH_THEMES)
        sin_colour = "#f44336" if theme.name == "professional" else theme.danger
        cos_colour = "#2196F3" if theme.name == "professional" else theme.secondary
        tan_colour = "#9C27B0" if theme.name == "professional" else theme.accent

        # Convert to radians
        angle_rad = math.radians(angle_deg)
        cos_val = math.cos(angle_rad)
        sin_val = math.sin(angle_rad)

        # Calculate dimensions
        center_x = svg_width / 2
        center_y = svg_height / 2
        radius = min(svg_width, svg_height) * 0.35 * radius_scale
        padding = 50

        def to_svg(x: float, y: float) -> tuple[float, float]:
            return center_x + x * radius, center_y - y * radius

        elements: List[str] = []
        elements.append(style(self._styles(theme)))
        if theme.name != "professional":
            elements.append(rect(0, 0, svg_width, svg_height, fill=theme.background,
                                 **{"class": "uc-background"}))

        # Draw axes
        axes_elements = [
            # X-axis
            line(padding, center_y, svg_width - padding, center_y, **{"class": "uc-axis"}),
            # Y-axis
            line(center_x, svg_height - padding, center_x, padding, **{"class": "uc-axis"}),
        ]
        # Axis arrows
        arrow = 8
        axes_elements.extend([
            line(svg_width - padding, center_y, svg_width - padding - arrow, center_y - arrow/2, **{"class": "uc-axis"}),
            line(svg_width - padding, center_y, svg_width - padding - arrow, center_y + arrow/2, **{"class": "uc-axis"}),
            line(center_x, padding, center_x - arrow/2, padding + arrow, **{"class": "uc-axis"}),
            line(center_x, padding, center_x + arrow/2, padding + arrow, **{"class": "uc-axis"}),
        ])
        elements.append(group("\n".join(axes_elements)))

        # Axis labels
        if show_labels:
            # An axis name goes clear of the tick label nearest it, and clear
            # of the common-angle label that sits just past the arrow. `x` was
            # five pixels from its own `1` and `y` was ten from its own, so
            # each name was drawn straight through a tick; lifting `x` only as
            # far as the axis line then put it through the `0` at 1.15r.
            label_elements = [
                text(svg_width - padding + 5, center_y - 20, "x", **{"class": "uc-axis-label"}),
                text(center_x + 14, padding - 2, "y", **{"class": "uc-axis-label"}),
                text(center_x + radius - 3, center_y + 16, "1", **{"class": "uc-label"}),
                text(center_x - radius - 5, center_y + 16, "-1", **{"class": "uc-label"}),
                text(center_x - 16, center_y - radius + 4, "1", **{"class": "uc-label"}),
                text(center_x - 20, center_y + radius + 4, "-1", **{"class": "uc-label"}),
            ]
            elements.append(group("\n".join(label_elements)))

        # Draw unit circle
        elements.append(circle(center_x, center_y, radius, **{"class": "uc-circle"}))

        # Mark common angles
        if show_common_angles:
            angle_elements = []
            for deg, label in COMMON_ANGLES.items():
                if deg == 360:
                    continue
                # Not at the angle being shown. That point already carries its
                # own marker and, with `show_coordinates`, its own readout, so
                # labelling it again put two labels on one ray overlapping by
                # half — at every angle that happens to be a common one. The
                # reader loses both, and one of them is what they asked for.
                # Circular distance, not a bare modulus: `%` is non-negative,
                # so `(45 - 45.2) % 360` is 359.8 and a figure drawn at 45.2°
                # kept the 45° label sitting on the same ray. Wrong by a fifth
                # of a degree, and only on one side.
                if abs((deg - angle_deg + 180) % 360 - 180) < 0.5:
                    continue
                rad = math.radians(deg)
                px, py = to_svg(math.cos(rad), math.sin(rad))
                angle_elements.append(circle(px, py, 3, **{"class": "uc-angle-point"}))
                # Label position (outside circle)
                label_dist = 1.15
                lx, ly = to_svg(math.cos(rad) * label_dist, math.sin(rad) * label_dist)
                angle_elements.append(text(lx, ly, label, **{"class": "uc-angle-label", "text_anchor": "middle"}))
            elements.append(group("\n".join(angle_elements)))

        # Reference triangle
        if show_triangle:
            px, py = to_svg(cos_val, sin_val)
            triangle_elements = [
                # Horizontal leg (cos)
                line(center_x, center_y, center_x + cos_val * radius, center_y, **{"class": "uc-triangle"}),
                # Vertical leg (sin)
                line(center_x + cos_val * radius, center_y, px, py, **{"class": "uc-triangle"}),
                # Hypotenuse (radius)
                line(center_x, center_y, px, py, **{"class": "uc-radius"}),
            ]
            elements.append(group("\n".join(triangle_elements)))

        # Highlight sin (vertical)
        if show_sin and sin_val != 0:
            px, py = to_svg(cos_val, sin_val)
            sin_elements = [
                line(px, center_y, px, py, stroke=sin_colour, stroke_width="3"),
            ]
            # Label
            label_x = px + 10
            label_y = center_y + (py - center_y) / 2
            sin_elements.append(text(label_x, label_y, f"sin={sin_val:.2f}", **{"class": "uc-value-label", "fill": sin_colour}))
            elements.append(group("\n".join(sin_elements)))

        # Highlight cos (horizontal)
        if show_cos and cos_val != 0:
            px, _ = to_svg(cos_val, 0)
            cos_elements = [
                line(center_x, center_y + 3, px, center_y + 3, stroke=cos_colour, stroke_width="3"),
            ]
            # Label
            label_x = center_x + (px - center_x) / 2
            label_y = center_y + 20
            cos_elements.append(text(label_x, label_y, f"cos={cos_val:.2f}", **{"class": "uc-value-label", "fill": cos_colour, "text_anchor": "middle"}))
            elements.append(group("\n".join(cos_elements)))

        # Tangent line (if enabled)
        if show_tan and abs(cos_val) > 0.01:
            tan_val = sin_val / cos_val
            # Tangent line at x=1
            tan_px, _ = to_svg(1, 0)
            _, tan_py = to_svg(0, tan_val)
            tan_elements = [
                # Line from (1,0) to (1, tan)
                line(tan_px, center_y, tan_px, center_y - tan_val * radius, stroke=tan_colour, stroke_width="2"),
                # Line from origin to tangent point
                line(center_x, center_y, tan_px, center_y - tan_val * radius, stroke=tan_colour, stroke_width="1", stroke_dasharray="5,3"),
            ]
            elements.append(group("\n".join(tan_elements)))

        # Angle arc
        if show_arc:
            arc_radius = radius * 0.25
            # SVG arc path
            end_x = center_x + arc_radius * cos_val
            end_y = center_y - arc_radius * sin_val
            large_arc = 1 if angle_deg > 180 else 0
            sweep = 1 if angle_deg > 0 else 0

            arc_path = f"M {center_x + arc_radius} {center_y} A {arc_radius} {arc_radius} 0 {large_arc} 0 {end_x} {end_y}"
            elements.append(path(arc_path, **{"class": "uc-arc"}))

            # Angle label
            label_angle = angle_rad / 2
            label_dist = arc_radius * 1.5
            lx = center_x + label_dist * math.cos(label_angle)
            ly = center_y - label_dist * math.sin(label_angle)
            angle_text = f"{angle_deg}°"
            elements.append(text(lx, ly, angle_text, **{"class": "uc-angle-text", "text_anchor": "middle"}))

        # Point on circle
        px, py = to_svg(cos_val, sin_val)
        elements.append(circle(px, py, 6, **{"class": "uc-point"}))

        # Coordinates label
        if show_coordinates:
            coord_text = f"({cos_val:.2f}, {sin_val:.2f})"
            offset_x = 15 if cos_val >= 0 else -15
            offset_y = -15 if sin_val >= 0 else 15
            anchor = "start" if cos_val >= 0 else "end"
            # Away from the circle is the natural side and, near the edges, off
            # the canvas: at 0° the readout starts at x=355 and is 67px wide on
            # a 400px figure, so a third of it was never painted. Turned back
            # inward when the natural side does not fit — on the wrong side
            # beats not drawn.
            width = text_width(coord_text, 11, safe=True)
            left = px + offset_x - (width if anchor == "end" else 0)
            if left + width > svg_width - 4:
                offset_x, anchor = -15, "end"
            elif left < 4:
                offset_x, anchor = 15, "start"
            if py + offset_y - 11 < 4:
                offset_y = 15
            elif py + offset_y + 4 > svg_height - 4:
                offset_y = -15
            elements.append(text(px + offset_x, py + offset_y, coord_text, **{"class": "uc-coord-label", "text_anchor": anchor}))

        # Title
        if title:
            elements.append(text(svg_width / 2, 25, title, **{"class": "uc-title", "text_anchor": "middle"}))

        return svg_document("\n".join(elements), svg_width, svg_height)

    def _styles(self, theme: DiagramTheme) -> str:
        if theme.name == "professional":
            axis, muted, rule = "#333", "#666", "#999"
            point, point_rule, angle = "#4CAF50", "#2E7D32", "#FF9800"
        else:
            axis, muted, rule = theme.text, theme.muted, theme.rule
            point, point_rule, angle = theme.success, theme.primary, theme.warning
        return f"""
.uc-axis {{ stroke: {axis}; stroke-width: 2; }}
.uc-axis-label {{ font-size: 14px; font-family: sans-serif; fill: {axis}; font-style: italic; }}
.uc-circle {{ fill: none; stroke: {muted}; stroke-width: 2; }}
.uc-radius {{ stroke: {axis}; stroke-width: 2; }}
.uc-triangle {{ stroke: {rule}; stroke-width: 1; stroke-dasharray: 4,2; }}
.uc-point {{ fill: {point}; stroke: {point_rule}; stroke-width: 2; }}
.uc-arc {{ fill: none; stroke: {angle}; stroke-width: 2; }}
.uc-angle-text {{ font-size: 12px; font-family: sans-serif; fill: {angle}; }}
.uc-label {{ font-size: 11px; font-family: sans-serif; fill: {muted}; }}
.uc-value-label {{ font-size: 11px; font-family: sans-serif; font-weight: bold; }}
.uc-coord-label {{ font-size: 11px; font-family: sans-serif; fill: {axis}; }}
.uc-angle-point {{ fill: {rule}; }}
.uc-angle-label {{ font-size: 9px; font-family: sans-serif; fill: {muted}; }}
.uc-title {{ font-size: 14px; font-family: sans-serif; fill: {axis}; font-weight: bold; }}
"""
