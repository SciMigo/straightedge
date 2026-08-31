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
from ..themes import DIAGRAM_THEMES, DiagramTheme, family, resolve_theme

#: The pre-theme palette stated as roles: transparent paper, Material-style
#: sin/cos/tan and point colours. The renderer reads the theme unconditionally,
#: so `professional` is the old output by construction.
PROFESSIONAL = DIAGRAM_THEMES["professional"].variant(
    background="", text="#333", muted="#666", rule="#999",
    success="#4CAF50", primary="#2E7D32", warning="#FF9800",
    danger="#f44336", secondary="#2196F3", accent="#9C27B0",
)
THEMES = family(PROFESSIONAL, "classroom", "dark", "high-contrast", "print-friendly")


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
    themes = THEMES

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
        theme = resolve_theme(params.get("theme", "professional"), THEMES)
        sin_colour, cos_colour, tan_colour = theme.danger, theme.secondary, theme.accent

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
        if theme.background:
            elements.append(rect(0, 0, svg_width, svg_height, fill=theme.background,
                                 **{"class": "uc-background"}))

        # The extents of every label placed so far, so a later label can dodge
        # them. 0.8em above the baseline and 0.25em below covers ascent and
        # descenders the way the legibility parser estimates them.
        placed_boxes: List[tuple[float, float, float, float]] = []

        def label_box(x: float, y: float, s: str, px: float,
                      anchor: str = "start") -> tuple[float, float, float, float]:
            w = text_width(s, px, safe=True)
            x0 = x - w if anchor == "end" else x - w / 2 if anchor == "middle" else x
            return (x0, x0 + w, y - 0.8 * px, y + 0.25 * px)

        def place(x: float, y: float, s: str, px: float,
                  anchor: str = "start") -> None:
            placed_boxes.append(label_box(x, y, s, px, anchor))

        def collides(box: tuple[float, float, float, float]) -> bool:
            return any(box[0] < b[1] and b[0] < box[1]
                       and box[2] < b[3] and b[2] < box[3]
                       for b in placed_boxes)

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
            # No spot near a circle-axis crossing can be static: the point
            # rides the circle, the readouts ride the point, and the tangent
            # line stands on the crossing itself — so a fixed name or tick is
            # covered at whichever angle brings the moving parts past it (`1`
            # sat exactly where the point passes just after 90°). Each name
            # and tick takes the side of its axis the traffic is not on for
            # this render; the sides are chosen against the readout, point and
            # tangent geometry, and the boxes are recorded so the coordinate
            # readout below dodges them too.
            x_below = sin_val >= 0     # the point is above the x-axis → go below
            y_left = cos_val >= 0      # the point is right of the y-axis → go left
            # The right `1` shares its column with the tangent line whenever
            # the point is on the left half (from where the point itself can
            # never reach this tick), so there it dodges by the tangent's side
            # instead.
            if show_tan and cos_val < -0.01:
                one_below = (sin_val / cos_val) >= 0
            else:
                one_below = x_below
            tick_specs = [
                (center_x + radius - 3,
                 center_y + 18 if one_below else center_y - 10, "1"),
                (center_x - radius - 5,
                 center_y + 18 if x_below else center_y - 10, "-1"),
                # The top and bottom ticks cross the axis away from the point
                # when the point is in their corner.
                (center_x + 8 if (not y_left and sin_val >= 0) else center_x - 16,
                 center_y - radius + 4, "1"),
                (center_x + 8 if (not y_left and sin_val < 0) else center_x - 20,
                 center_y + radius + 4, "-1"),
            ]
            label_elements = []
            for lbl_x, lbl_y, lbl in tick_specs:
                label_elements.append(text(lbl_x, lbl_y, lbl, **{"class": "uc-label"}))
                place(lbl_x, lbl_y, lbl, 11)
            # The names go after the ticks so they can *measure* their way
            # clear of them: on a small canvas the arrow and the circle-axis
            # crossing close ranks, and no fixed offset clears both the tick
            # and the moving parts at every size. Preferred side first, then
            # the other side, then one label-height further out.
            x_steps = (18, -20, 32, -34) if x_below else (-20, 18, -34, 32)
            y_steps = (-20, 14, -34, 28) if y_left else (14, -20, 28, -34)
            for name, cands in (
                ("x", [(svg_width - padding + 5, center_y + s) for s in x_steps]),
                ("y", [(center_x + s, padding - 2) for s in y_steps]),
            ):
                nx, ny = next((c for c in cands
                               if not collides(label_box(c[0], c[1], name, 14))),
                              cands[0])
                label_elements.append(text(nx, ny, name, **{"class": "uc-axis-label"}))
                place(nx, ny, name, 14)
            elements.append(group("\n".join(label_elements)))

        # Draw unit circle
        elements.append(circle(center_x, center_y, radius, **{"class": "uc-circle"}))

        # Mark common angles
        if show_common_angles:
            angle_elements = []
            for deg, label in COMMON_ANGLES.items():
                if deg == 360:
                    continue
                # Not at the angle being shown — when that ray already carries
                # its own text. With `show_coordinates` or `show_arc`, the
                # readout or the arc label sits on the ray, so labelling it
                # again put two labels on top of each other and the reader
                # lost both. With *neither* on, suppressing here deleted the
                # only label the shown angle had: a figure asked to teach π/4
                # marked every common angle except π/4.
                # Circular distance, not a bare modulus: `%` is non-negative,
                # so `(45 - 45.2) % 360` is 359.8 and a figure drawn at 45.2°
                # kept the 45° label sitting on the same ray. Wrong by a fifth
                # of a degree, and only on one side.
                if ((show_coordinates or show_arc)
                        and abs((deg - angle_deg + 180) % 360 - 180) < 0.5):
                    continue
                rad = math.radians(deg)
                px, py = to_svg(math.cos(rad), math.sin(rad))
                angle_elements.append(circle(px, py, 3, **{"class": "uc-angle-point"}))
                # Label position (outside circle)
                label_dist = 1.15
                lx, ly = to_svg(math.cos(rad) * label_dist, math.sin(rad) * label_dist)
                angle_elements.append(text(lx, ly, label, **{"class": "uc-angle-label", "text_anchor": "middle"}))
                place(lx, ly, label, 9, "middle")
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
            # Label — flipped to the inner side of the sin segment when the
            # natural side runs off the canvas, which it did for every shallow
            # angle: at 355° it started at x=349 and lost its last 5px.
            sin_text = f"sin={sin_val:.2f}"
            label_x, sin_anchor = px + 10, "start"
            if label_x + text_width(sin_text, 11, safe=True) > svg_width - 4:
                label_x, sin_anchor = px - 10, "end"
            label_y = center_y + (py - center_y) / 2
            sin_elements.append(text(label_x, label_y, sin_text,
                                     **{"class": "uc-value-label", "fill": sin_colour,
                                        "text_anchor": sin_anchor}))
            place(label_x, label_y, sin_text, 11, sin_anchor)
            elements.append(group("\n".join(sin_elements)))

        # Highlight cos (horizontal)
        if show_cos and cos_val != 0:
            px, _ = to_svg(cos_val, 0)
            cos_elements = [
                line(center_x, center_y + 3, px, center_y + 3, stroke=cos_colour, stroke_width="3"),
            ]
            # Label — one step further from the axis when the spot under the
            # leg is taken, which it is whenever the sin readout sits low on
            # the same side (every shallow angle just past 180°).
            cos_text = f"cos={cos_val:.2f}"
            label_x = center_x + (px - center_x) / 2
            label_y = center_y + 20
            for step in (20, 33, 46):
                if not collides(label_box(label_x, center_y + step, cos_text, 11, "middle")):
                    label_y = center_y + step
                    break
            cos_elements.append(text(label_x, label_y, cos_text, **{"class": "uc-value-label", "fill": cos_colour, "text_anchor": "middle"}))
            place(label_x, label_y, cos_text, 11, "middle")
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
            place(lx, ly, angle_text, 12, "middle")

        # Title — placed (and recorded) before the coordinate readout so a
        # readout near the top edge dodges it rather than landing on it.
        if title:
            elements.append(text(svg_width / 2, 25, title, **{"class": "uc-title", "text_anchor": "middle"}))
            place(svg_width / 2, 25, str(title), 14, "middle")

        # Point on circle
        px, py = to_svg(cos_val, sin_val)
        elements.append(circle(px, py, 6, **{"class": "uc-point"}))

        # Coordinates label
        if show_coordinates:
            coord_text = f"({cos_val:.2f}, {sin_val:.2f})"
            # Away from the circle is the natural corner and, near the edges,
            # off the canvas. But the flipped spot is not automatically free
            # either: at 355° flipping inward landed the readout on `cos=1.00`,
            # and the old if/elif never rechecked (nor could it catch a flip
            # that undershot the opposite margin). So: candidates, nearest
            # first, and the first that fits the canvas *and* clears every
            # label placed so far wins — stepping one label-height further out
            # before giving up.
            h_options = [(15, "start"), (-15, "end")]
            if cos_val < 0:
                h_options.reverse()
            v = -15 if sin_val >= 0 else 15
            chosen = None
            fallback = None
            for offset_y in (v, -v, 2 * v, -2 * v):
                for offset_x, anchor in h_options:
                    box = label_box(px + offset_x, py + offset_y, coord_text, 11, anchor)
                    on_canvas = (box[0] >= 4 and box[1] <= svg_width - 4
                                 and box[2] >= 4 and box[3] <= svg_height - 4)
                    if not on_canvas:
                        continue
                    if fallback is None:
                        fallback = (offset_x, offset_y, anchor)
                    if not collides(box):
                        chosen = (offset_x, offset_y, anchor)
                        break
                if chosen:
                    break
            # Nothing is both on-canvas and clean: take the nearest on-canvas
            # spot — on the wrong side beats not drawn — or the natural corner
            # when even that fails.
            offset_x, offset_y, anchor = (chosen or fallback
                                          or (h_options[0][0], v, h_options[0][1]))
            place(px + offset_x, py + offset_y, coord_text, 11, anchor)
            elements.append(text(px + offset_x, py + offset_y, coord_text, **{"class": "uc-coord-label", "text_anchor": anchor}))

        return svg_document("\n".join(elements), svg_width, svg_height)

    def _styles(self, theme: DiagramTheme) -> str:
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
