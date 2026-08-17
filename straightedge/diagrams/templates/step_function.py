"""Step function template for binary search / monotonic predicate visualizations."""

from html import escape
from typing import Any, Dict, List, Optional
from ..registry import register


def _safe(value: Optional[str]) -> Optional[str]:
    """Escape a caller-supplied string for interpolation into raw SVG.

    Alone among the templates this one builds its markup with f-strings rather
    than through :mod:`..renderer`, whose ``text`` escapes for it. Unescaped,
    every label here is an injection point into a document that ends up inside
    an HTML slide — and the everyday half of the same bug is worse odds: a title
    reading ``0 < x`` produced SVG no parser would accept.
    """
    return value if value is None else escape(str(value))


@register("step_function")
class StepFunctionTemplate:
    """Render a step function for visualizing monotonic predicates.

    Perfect for binary search on answer space lectures where we need to show
    the exact transition point (e.g., k=4 for Koko problem).
    """

    def render(self, params: Dict[str, Any]) -> str:
        """Render the step function as SVG.

        Params:
            transition_x: X-value where step occurs (e.g., 4 for k=4)
            x_min, x_max: X-axis range (default: 1, 11)
            y_low, y_high: Y values for low/high states (default: 0, 1)
            left_label: Label for left region (default: "False")
            right_label: Label for right region (default: "True")
            x_label: Label for x-axis (default: "k")
            y_label: Label for y-axis (default: "feasible(k)")
            transition_label: Label at transition point (default: None)
            left_color: Color for left region/markers (default: "#E53935" red)
            right_color: Color for right region/markers (default: "#43A047" green)
            show_markers: Show X/checkmark markers (default: True)
            marker_positions: List of x values for markers (default: auto)
            show_grid: Show background grid (default: True)
            title: Optional title
            width, height: SVG dimensions (default: 400x280)
        """
        # Extract parameters
        transition_x = float(params.get("transition_x", 5))
        x_min = float(params.get("x_min", 1))
        x_max = float(params.get("x_max", 11))
        y_low = float(params.get("y_low", 0))
        y_high = float(params.get("y_high", 1))
        left_label = _safe(params.get("left_label", "False"))
        right_label = _safe(params.get("right_label", "True"))
        x_label = _safe(params.get("x_label", "k"))
        y_label = _safe(params.get("y_label", "feasible(k)"))
        transition_label = _safe(params.get("transition_label"))
        left_color = _safe(params.get("left_color", "#E53935"))
        right_color = _safe(params.get("right_color", "#43A047"))
        show_markers = params.get("show_markers", True)
        marker_positions = params.get("marker_positions")
        show_grid = params.get("show_grid", True)
        title = _safe(params.get("title"))
        svg_width = int(params.get("width", 400))
        svg_height = int(params.get("height", 280))

        padding_left = 50
        padding_right = 30
        padding_top = 40 if title else 25
        padding_bottom = 50

        plot_width = svg_width - padding_left - padding_right
        plot_height = svg_height - padding_top - padding_bottom

        # Coordinate transforms
        def to_svg_x(x: float) -> float:
            return padding_left + (x - x_min) / (x_max - x_min) * plot_width

        def to_svg_y(y: float) -> float:
            y_range = y_high - y_low + 0.4  # Add padding
            y_min_plot = y_low - 0.2
            return padding_top + plot_height - (y - y_min_plot) / y_range * plot_height

        svg_parts = []

        # SVG header
        svg_parts.append(
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {svg_width} {svg_height}" '
            f'width="{svg_width}" height="{svg_height}" style="background: white;">'
        )

        # Styles
        svg_parts.append("""
        <style>
            .axis-line { stroke: #333; stroke-width: 1.5; fill: none; }
            .grid-line { stroke: #ddd; stroke-width: 0.5; }
            .step-line { stroke-width: 2.5; fill: none; }
            .label { font-family: Arial, sans-serif; font-size: 14px; }
            .title { font-family: Arial, sans-serif; font-size: 16px; font-weight: bold; }
            .axis-label { font-family: Arial, sans-serif; font-size: 13px; }
            .tick-label { font-family: Arial, sans-serif; font-size: 11px; }
            .marker-text { font-family: Arial, sans-serif; font-size: 18px; font-weight: bold; }
            .region-label { font-family: Arial, sans-serif; font-size: 13px; font-weight: 600; }
        </style>
        """)

        # Title
        if title:
            svg_parts.append(
                f'<text x="{svg_width/2}" y="18" text-anchor="middle" class="title">{title}</text>'
            )

        # Grid
        if show_grid:
            for i in range(int(x_min), int(x_max) + 1):
                sx = to_svg_x(i)
                svg_parts.append(
                    f'<line x1="{sx}" y1="{padding_top}" x2="{sx}" y2="{padding_top + plot_height}" class="grid-line"/>'
                )
            for y_val in [y_low, (y_low + y_high) / 2, y_high]:
                sy = to_svg_y(y_val)
                svg_parts.append(
                    f'<line x1="{padding_left}" y1="{sy}" x2="{padding_left + plot_width}" y2="{sy}" class="grid-line"/>'
                )

        # Axes
        axis_y = to_svg_y(y_low - 0.15)
        svg_parts.append(
            f'<line x1="{padding_left}" y1="{axis_y}" x2="{padding_left + plot_width + 10}" y2="{axis_y}" class="axis-line" marker-end="url(#arrowhead)"/>'
        )
        svg_parts.append(
            f'<line x1="{padding_left}" y1="{padding_top + plot_height + 5}" x2="{padding_left}" y2="{padding_top - 5}" class="axis-line" marker-end="url(#arrowhead)"/>'
        )

        # Arrow marker definition
        svg_parts.append("""
        <defs>
            <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
                <polygon points="0 0, 10 3.5, 0 7" fill="#333"/>
            </marker>
        </defs>
        """)

        # X-axis ticks and labels
        for i in range(int(x_min), int(x_max) + 1):
            sx = to_svg_x(i)
            svg_parts.append(
                f'<line x1="{sx}" y1="{axis_y - 3}" x2="{sx}" y2="{axis_y + 3}" stroke="#333" stroke-width="1"/>'
            )
            # Highlight transition point
            if i == int(transition_x):
                svg_parts.append(
                    f'<text x="{sx}" y="{axis_y + 18}" text-anchor="middle" class="tick-label" fill="{right_color}" font-weight="bold">{i}</text>'
                )
            else:
                svg_parts.append(
                    f'<text x="{sx}" y="{axis_y + 18}" text-anchor="middle" class="tick-label">{i}</text>'
                )

        # Y-axis labels (0 and 1)
        svg_parts.append(
            f'<text x="{padding_left - 10}" y="{to_svg_y(y_low) + 4}" text-anchor="end" class="tick-label">0</text>'
        )
        svg_parts.append(
            f'<text x="{padding_left - 10}" y="{to_svg_y(y_high) + 4}" text-anchor="end" class="tick-label">1</text>'
        )

        # Axis labels
        svg_parts.append(
            f'<text x="{padding_left + plot_width/2}" y="{svg_height - 8}" text-anchor="middle" class="axis-label">{x_label}</text>'
        )
        svg_parts.append(
            f'<text x="15" y="{padding_top + plot_height/2}" text-anchor="middle" class="axis-label" transform="rotate(-90 15 {padding_top + plot_height/2})">{y_label}</text>'
        )

        # Draw step function
        trans_svg_x = to_svg_x(transition_x)
        y_low_svg = to_svg_y(y_low)
        y_high_svg = to_svg_y(y_high)
        x_min_svg = to_svg_x(x_min)
        x_max_svg = to_svg_x(x_max)

        # Left horizontal segment (False region)
        svg_parts.append(
            f'<line x1="{x_min_svg}" y1="{y_low_svg}" x2="{trans_svg_x}" y2="{y_low_svg}" class="step-line" stroke="{left_color}"/>'
        )
        # Vertical transition
        svg_parts.append(
            f'<line x1="{trans_svg_x}" y1="{y_low_svg}" x2="{trans_svg_x}" y2="{y_high_svg}" class="step-line" stroke="{right_color}"/>'
        )
        # Right horizontal segment (True region)
        svg_parts.append(
            f'<line x1="{trans_svg_x}" y1="{y_high_svg}" x2="{x_max_svg}" y2="{y_high_svg}" class="step-line" stroke="{right_color}"/>'
        )

        # Transition point marker (filled circle at top)
        svg_parts.append(
            f'<circle cx="{trans_svg_x}" cy="{y_high_svg}" r="5" fill="{right_color}"/>'
        )
        # Open circle at bottom of transition (discontinuity)
        svg_parts.append(
            f'<circle cx="{trans_svg_x}" cy="{y_low_svg}" r="5" fill="white" stroke="{left_color}" stroke-width="2"/>'
        )

        # Transition label
        if transition_label:
            svg_parts.append(
                f'<text x="{trans_svg_x}" y="{y_high_svg - 15}" text-anchor="middle" class="label" fill="{right_color}">{transition_label}</text>'
            )

        # Region labels
        left_center_x = (x_min_svg + trans_svg_x) / 2
        right_center_x = (trans_svg_x + x_max_svg) / 2
        label_y = to_svg_y((y_low + y_high) / 2)

        svg_parts.append(
            f'<text x="{left_center_x}" y="{label_y}" text-anchor="middle" class="region-label" fill="{left_color}">{left_label}</text>'
        )
        svg_parts.append(
            f'<text x="{right_center_x}" y="{label_y}" text-anchor="middle" class="region-label" fill="{right_color}">{right_label}</text>'
        )

        # X and checkmark markers
        if show_markers:
            if marker_positions is None:
                # Auto-generate: some X's before transition, some checkmarks after
                x_positions = [i for i in range(int(x_min), int(transition_x)) if i < transition_x][-3:]
                check_positions = [i for i in range(int(transition_x), int(x_max) + 1)][:3]
            else:
                x_positions = [p for p in marker_positions if p < transition_x]
                check_positions = [p for p in marker_positions if p >= transition_x]

            marker_y = to_svg_y(y_low) + 25

            # X markers for false region
            for pos in x_positions:
                sx = to_svg_x(pos)
                svg_parts.append(
                    f'<text x="{sx}" y="{marker_y}" text-anchor="middle" class="marker-text" fill="{left_color}">X</text>'
                )

            # Checkmark markers for true region
            for pos in check_positions:
                sx = to_svg_x(pos)
                svg_parts.append(
                    f'<text x="{sx}" y="{marker_y}" text-anchor="middle" class="marker-text" fill="{right_color}">\u2713</text>'
                )

        svg_parts.append('</svg>')

        return '\n'.join(svg_parts)
