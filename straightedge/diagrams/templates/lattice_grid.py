"""Lattice grid diagram template.

Visualizes 2D integer lattice points, commonly used for:
- Visible lattice points (gcd(a,b) = 1)
- Primitive vectors
- Blocked/hidden points demonstration
"""

from __future__ import annotations

from math import gcd
from typing import Any, Dict, List

from ..registry import register
from ..renderer import (
    DEFAULT_STYLES,
    circle,
    group,
    line,
    style,
    svg_document,
    text,
)


@register("lattice_grid")
class LatticeGridTemplate:
    """Render a 2D integer lattice with visible/hidden points."""

    def render(self, params: Dict[str, Any]) -> str:
        """Render the lattice grid as SVG.

        Params:
            width: Grid width (default: 8)
            height: Grid height (default: 8)
            highlight: Which points to highlight:
                - "visible": points with gcd(x,y)=1 (default)
                - "primitive": same as visible
                - "all": all points
                - "none": no highlighting
            show_rays: Draw rays from origin through visible points (default: False)
            show_origin: Highlight the origin point (default: True)
            show_axes: Draw x and y axes (default: True)
            show_grid: Draw background grid lines (default: False)
            labels: Show coordinate labels (default: False)
            point_radius: Radius of point circles (default: 4)
            cell_size: Size of each grid cell in pixels (default: 30)
            padding: Padding around the grid (default: 30)
            highlighted_points: List of [x,y] points to specially highlight
        """
        # Extract parameters with defaults
        grid_width = int(params.get("width", 8))
        grid_height = int(params.get("height", 8))
        highlight = params.get("highlight", "visible")
        show_rays = bool(params.get("show_rays", False))
        show_origin = bool(params.get("show_origin", True))
        show_axes = bool(params.get("show_axes", True))
        show_grid = bool(params.get("show_grid", False))
        show_labels = bool(params.get("labels", False))
        point_radius = float(params.get("point_radius", 4))
        cell_size = int(params.get("cell_size", 30))
        padding = int(params.get("padding", 30))
        highlighted_points = params.get("highlighted_points", [])

        # Calculate SVG dimensions
        svg_width = grid_width * cell_size + 2 * padding
        svg_height = grid_height * cell_size + 2 * padding

        # Helper to convert grid coords to SVG coords
        def to_svg(x: int, y: int) -> tuple[float, float]:
            px = padding + x * cell_size
            py = svg_height - padding - y * cell_size
            return px, py

        elements: List[str] = []

        # Add styles
        elements.append(style(DEFAULT_STYLES))

        # Draw background grid
        if show_grid:
            grid_lines = []
            for x in range(grid_width + 1):
                px, _ = to_svg(x, 0)
                _, py_top = to_svg(0, grid_height)
                _, py_bottom = to_svg(0, 0)
                grid_lines.append(
                    line(px, py_top, px, py_bottom, **{"class": "diagram-grid"})
                )
            for y in range(grid_height + 1):
                _, py = to_svg(0, y)
                px_left, _ = to_svg(0, 0)
                px_right, _ = to_svg(grid_width, 0)
                grid_lines.append(
                    line(px_left, py, px_right, py, **{"class": "diagram-grid"})
                )
            elements.append(group("\n".join(grid_lines)))

        # Draw axes
        if show_axes:
            origin = to_svg(0, 0)
            x_end = to_svg(grid_width, 0)
            y_end = to_svg(0, grid_height)

            axes_elements = [
                # X-axis
                line(origin[0], origin[1], x_end[0], x_end[1], **{"class": "diagram-axis"}),
                # Y-axis
                line(origin[0], origin[1], y_end[0], y_end[1], **{"class": "diagram-axis"}),
            ]

            # Arrowheads
            arrow_size = 8
            # X-axis arrow
            axes_elements.append(
                line(
                    x_end[0], x_end[1],
                    x_end[0] - arrow_size, x_end[1] - arrow_size / 2,
                    **{"class": "diagram-axis"}
                )
            )
            axes_elements.append(
                line(
                    x_end[0], x_end[1],
                    x_end[0] - arrow_size, x_end[1] + arrow_size / 2,
                    **{"class": "diagram-axis"}
                )
            )
            # Y-axis arrow
            axes_elements.append(
                line(
                    y_end[0], y_end[1],
                    y_end[0] - arrow_size / 2, y_end[1] + arrow_size,
                    **{"class": "diagram-axis"}
                )
            )
            axes_elements.append(
                line(
                    y_end[0], y_end[1],
                    y_end[0] + arrow_size / 2, y_end[1] + arrow_size,
                    **{"class": "diagram-axis"}
                )
            )

            elements.append(group("\n".join(axes_elements)))

        # Draw rays from origin (if enabled)
        if show_rays:
            ray_elements = []
            for x in range(1, grid_width + 1):
                for y in range(1, grid_height + 1):
                    if gcd(x, y) == 1:  # primitive direction
                        # Extend ray to edge of grid
                        scale_x = grid_width / x if x > 0 else float('inf')
                        scale_y = grid_height / y if y > 0 else float('inf')
                        scale = min(scale_x, scale_y)

                        end_x = x * scale
                        end_y = y * scale

                        origin_svg = to_svg(0, 0)
                        end_svg = to_svg(int(end_x), int(end_y))

                        ray_elements.append(
                            line(
                                origin_svg[0], origin_svg[1],
                                end_svg[0], end_svg[1],
                                **{"class": "diagram-ray"}
                            )
                        )
            elements.append(group("\n".join(ray_elements)))

        # Convert highlighted_points to set for fast lookup
        highlight_set = set()
        for pt in highlighted_points:
            if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                highlight_set.add((int(pt[0]), int(pt[1])))

        # Draw points
        point_elements = []
        for x in range(0, grid_width + 1):
            for y in range(0, grid_height + 1):
                px, py = to_svg(x, y)

                # Determine point class based on position and highlight mode
                if (x, y) in highlight_set:
                    point_class = "diagram-point-highlight"
                elif x == 0 and y == 0:
                    point_class = "diagram-point-origin" if show_origin else "diagram-point-hidden"
                elif x == 0 or y == 0:
                    # Points on axes (not origin)
                    point_class = "diagram-point-hidden"
                elif highlight in ("visible", "primitive"):
                    if gcd(x, y) == 1:
                        point_class = "diagram-point-visible"
                    else:
                        point_class = "diagram-point-hidden"
                elif highlight == "all":
                    point_class = "diagram-point-visible"
                else:
                    point_class = "diagram-point-hidden"

                point_elements.append(
                    circle(px, py, point_radius, **{"class": point_class})
                )

        elements.append(group("\n".join(point_elements)))

        # Draw labels
        if show_labels:
            label_elements = []
            # X-axis labels
            for x in range(0, grid_width + 1, max(1, grid_width // 5)):
                px, py = to_svg(x, 0)
                label_elements.append(
                    text(px, py + 15, str(x), **{
                        "class": "diagram-label-small",
                        "text_anchor": "middle"
                    })
                )
            # Y-axis labels
            for y in range(0, grid_height + 1, max(1, grid_height // 5)):
                px, py = to_svg(0, y)
                label_elements.append(
                    text(px - 10, py + 4, str(y), **{
                        "class": "diagram-label-small",
                        "text_anchor": "end"
                    })
                )
            elements.append(group("\n".join(label_elements)))

        return svg_document("\n".join(elements), svg_width, svg_height)
