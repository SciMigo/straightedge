"""Heatmap visualization template.

Renders a 2D grid of continuous values as a color-mapped heatmap.
Used for attention weight matrices, correlation matrices, covariance matrices,
quantization error maps, and other real-valued 2D data.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from ..registry import register
from ..renderer import (
    DEFAULT_STYLES,
    group,
    rect,
    style,
    svg_document,
    text,
)


def _interpolate_color(value: float, scale: str) -> str:
    """Map a value in [0, 1] to an RGB hex color using the given color scale."""
    t = max(0.0, min(1.0, value))

    if scale == "blues":
        # White → Indigo (#6366F1)
        r = int(255 - t * (255 - 99))
        g = int(255 - t * (255 - 102))
        b = int(255 - t * (255 - 241))
    elif scale == "reds":
        # White → Red (#E53935)
        r = int(255 - t * (255 - 229))
        g = int(255 - t * (255 - 57))
        b = int(255 - t * (255 - 53))
    elif scale == "greens":
        # White → Green (#43A047)
        r = int(255 - t * (255 - 67))
        g = int(255 - t * (255 - 160))
        b = int(255 - t * (255 - 71))
    elif scale == "viridis":
        # Simplified viridis: dark purple → teal → yellow
        if t < 0.5:
            s = t * 2  # 0..1 within first half
            r = int(68 + s * (33 - 68))
            g = int(1 + s * (145 - 1))
            b = int(84 + s * (140 - 84))
        else:
            s = (t - 0.5) * 2  # 0..1 within second half
            r = int(33 + s * (253 - 33))
            g = int(145 + s * (231 - 145))
            b = int(140 + s * (37 - 140))
    elif scale == "diverging":
        # Blue → White → Red (for values centered at 0.5)
        if t < 0.5:
            s = t * 2  # 0..1
            r = int(33 + s * (255 - 33))
            g = int(102 + s * (255 - 102))
            b = int(172 + s * (255 - 172))
        else:
            s = (t - 0.5) * 2
            r = int(255 - s * (255 - 214))
            g = int(255 - s * (255 - 39))
            b = int(255 - s * (255 - 40))
    else:
        # Default: white → dark gray
        v = int(255 - t * 200)
        r, g, b = v, v, v

    return f"#{r:02x}{g:02x}{b:02x}"


@register("heatmap")
class HeatmapTemplate:
    """Render a heatmap from a 2D array of values."""

    def render(self, params: Dict[str, Any]) -> str:
        """Render heatmap as SVG.

        Params:
            values: 2D array of numbers (required)
            row_labels: Labels for rows (optional)
            col_labels: Labels for columns (optional)
            color_scale: "blues" (default), "reds", "greens", "viridis", "diverging"
            show_values: Display numeric values in cells (default: True)
            value_format: Format string for values (default: ".2f")
            normalize: Normalize values to [0, 1] (default: True)
            v_min: Manual minimum for color scale (overrides normalize)
            v_max: Manual maximum for color scale (overrides normalize)
            cell_size: Size of each cell in pixels (default: 45)
            caption: Optional caption text
            title: Optional title text
        """
        values = params.get("values", [])
        if not isinstance(values, list) or not values:
            return ""

        rows = len(values)
        cols = max((len(row) for row in values if isinstance(row, list)), default=0)
        if cols == 0:
            return ""

        row_labels = params.get("row_labels", [])
        col_labels = params.get("col_labels", [])
        if not isinstance(row_labels, list):
            row_labels = []
        if not isinstance(col_labels, list):
            col_labels = []

        color_scale = params.get("color_scale", "blues")
        show_values = bool(params.get("show_values", True))
        value_format = params.get("value_format", ".2f")
        normalize = bool(params.get("normalize", True))
        v_min = params.get("v_min")
        v_max = params.get("v_max")
        cell_size = int(params.get("cell_size", 45))
        caption = params.get("caption")
        title = params.get("title")

        # Flatten values and compute range
        flat = []
        for row in values:
            if isinstance(row, list):
                for v in row:
                    if isinstance(v, (int, float)) and math.isfinite(v):
                        flat.append(float(v))

        if not flat:
            return ""

        if v_min is not None:
            data_min = float(v_min)
        else:
            data_min = min(flat) if normalize else 0.0

        if v_max is not None:
            data_max = float(v_max)
        else:
            data_max = max(flat) if normalize else 1.0

        data_range = data_max - data_min if data_max != data_min else 1.0

        # Layout
        padding_top = 25 + (20 if title else 0)
        padding_left = 20
        row_label_width = 0
        col_label_height = 0

        if row_labels:
            # Estimate label width from longest label
            max_label_len = max((len(str(l)) for l in row_labels), default=3)
            row_label_width = max(35, max_label_len * 7 + 10)

        if col_labels:
            col_label_height = 30

        grid_left = padding_left + row_label_width
        grid_top = padding_top + col_label_height

        svg_width = grid_left + cols * cell_size + 20
        svg_height = grid_top + rows * cell_size + 20 + (20 if caption else 0)

        elements: List[str] = []
        elements.append(style(DEFAULT_STYLES + self._styles()))

        # Title
        if title:
            elements.append(
                text(
                    svg_width / 2, 18, title,
                    **{"class": "hm-title", "text_anchor": "middle"},
                )
            )

        # Column labels
        if col_labels:
            for c in range(cols):
                label = col_labels[c] if c < len(col_labels) else ""
                x = grid_left + c * cell_size + cell_size / 2
                y = grid_top - 8
                elements.append(
                    text(x, y, str(label),
                         **{"class": "hm-col-label", "text_anchor": "middle"})
                )

        # Row labels
        if row_labels:
            for r in range(rows):
                label = row_labels[r] if r < len(row_labels) else ""
                x = grid_left - 8
                y = grid_top + r * cell_size + cell_size / 2 + 4
                elements.append(
                    text(x, y, str(label),
                         **{"class": "hm-row-label", "text_anchor": "end"})
                )

        # Cells
        for r in range(rows):
            row = values[r] if r < len(values) and isinstance(values[r], list) else []
            for c in range(cols):
                x = grid_left + c * cell_size
                y = grid_top + r * cell_size
                raw_val = row[c] if c < len(row) else 0
                if not isinstance(raw_val, (int, float)) or not math.isfinite(raw_val):
                    raw_val = 0

                # Normalize to [0, 1]
                norm_val = (float(raw_val) - data_min) / data_range
                fill_color = _interpolate_color(norm_val, color_scale)

                # Use dark text on light backgrounds, white on dark
                text_color = "#333" if norm_val < 0.6 else "#fff"

                elements.append(
                    rect(x, y, cell_size, cell_size,
                         fill=fill_color, stroke="#fff", stroke_width="1")
                )

                if show_values:
                    try:
                        formatted = f"{float(raw_val):{value_format}}"
                    except (ValueError, TypeError):
                        formatted = str(raw_val)
                    elements.append(
                        text(
                            x + cell_size / 2,
                            y + cell_size / 2 + 4,
                            formatted,
                            **{"class": "hm-value", "text_anchor": "middle",
                               "fill": text_color},
                        )
                    )

        # Grid border
        elements.append(
            rect(grid_left, grid_top, cols * cell_size, rows * cell_size,
                 fill="none", stroke="#ccc", stroke_width="1")
        )

        # Caption
        if caption:
            elements.append(
                text(
                    svg_width / 2, svg_height - 5, caption,
                    **{"class": "hm-caption", "text_anchor": "middle"},
                )
            )

        return svg_document("\n".join(elements), svg_width, svg_height)

    @staticmethod
    def _styles() -> str:
        return """
.hm-title { font-size: 14px; font-family: sans-serif; fill: #333; font-weight: bold; }
.hm-row-label { font-size: 11px; font-family: sans-serif; fill: #555; }
.hm-col-label { font-size: 11px; font-family: sans-serif; fill: #555; }
.hm-value { font-size: 10px; font-family: monospace; }
.hm-caption { font-size: 11px; font-family: sans-serif; fill: #666; }
"""
