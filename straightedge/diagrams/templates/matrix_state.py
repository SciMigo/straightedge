"""Matrix/grid state visualization template for CS/data structure diagrams."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

from ..registry import register
from ..renderer import DEFAULT_STYLES, defs, line, polyline, rect, style, svg_document, text


STATE_COLORS = {
    "default": "#f8f9fa",
    "current": "#fff3cd",
    "visited": "#d1ecf1",
    "target": "#d4edda",
    "found": "#d4edda",
    "invalid": "#f8d7da",
    "rejected": "#f8d7da",
    "comparison": "#FF9800",
}


def _parse_coord(value: Any) -> Optional[Tuple[int, int]]:
    if isinstance(value, (list, tuple)) and len(value) == 2:
        row, col = value
        if isinstance(row, int) and isinstance(col, int):
            return row, col
        return None

    if isinstance(value, str) and "," in value:
        row_str, col_str = value.split(",", 1)
        if row_str.strip().lstrip("-").isdigit() and col_str.strip().lstrip("-").isdigit():
            return int(row_str), int(col_str)
    return None


def _normalize_highlights(highlights: Any) -> Dict[Tuple[int, int], str]:
    if not isinstance(highlights, dict):
        return {}
    result: Dict[Tuple[int, int], str] = {}
    for key, state in highlights.items():
        if not isinstance(state, str):
            continue
        coord = _parse_coord(key)
        if coord is None:
            continue
        result[coord] = state
    return result


def _normalize_path(path_points: Any) -> List[Tuple[int, int]]:
    if not isinstance(path_points, list):
        return []
    result: List[Tuple[int, int]] = []
    for item in path_points:
        coord = _parse_coord(item)
        if coord is not None:
            result.append(coord)
    return result


def _normalize_arrows(arrows: Any) -> List[Tuple[Tuple[int, int], Tuple[int, int]]]:
    if not isinstance(arrows, list):
        return []
    result: List[Tuple[Tuple[int, int], Tuple[int, int]]] = []
    for arrow in arrows:
        if not isinstance(arrow, dict):
            continue
        start = _parse_coord(arrow.get("from"))
        end = _parse_coord(arrow.get("to"))
        if start and end:
            result.append((start, end))
    return result


@register("matrix_state")
class MatrixStateTemplate:
    """Render a 2D matrix/grid visualization with highlights and paths."""

    def render(self, params: Dict[str, Any]) -> str:
        values = params.get("values", [])
        if not isinstance(values, list):
            values = []

        rows = len(values)
        cols = max((len(row) for row in values if isinstance(row, list)), default=0)
        cell_width = int(params.get("cell_width", 50))
        cell_height = int(params.get("cell_height", 45))
        row_labels = params.get("row_labels", [])
        col_labels = params.get("col_labels", [])
        caption = params.get("caption")

        if not isinstance(row_labels, list):
            row_labels = []
        if not isinstance(col_labels, list):
            col_labels = []

        highlights = _normalize_highlights(params.get("highlights", {}))
        path_points = _normalize_path(params.get("path", []))
        arrows = _normalize_arrows(params.get("arrows", []))

        padding_x = 20
        padding_y = 20
        row_label_width = 30 if row_labels else 0
        col_label_height = 30 if col_labels else 0

        top_margin = padding_y + col_label_height
        left_margin = padding_x + row_label_width
        bottom_margin = padding_y + (20 if caption else 0)

        svg_width = left_margin + max(1, cols) * cell_width + padding_x
        svg_height = top_margin + max(1, rows) * cell_height + bottom_margin

        elements: List[str] = []
        elements.append(style(DEFAULT_STYLES + self._extra_styles()))
        elements.append(defs(self._arrow_marker()))

        # Draw labels
        if row_labels:
            for r in range(rows):
                label = row_labels[r] if r < len(row_labels) else str(r)
                y = top_margin + r * cell_height + cell_height / 2 + 5
                elements.append(
                    text(
                        left_margin - 10,
                        y,
                        str(label),
                        **{"class": "matrix-label", "text_anchor": "end"},
                    )
                )
        if col_labels:
            for c in range(cols):
                label = col_labels[c] if c < len(col_labels) else str(c)
                x = left_margin + c * cell_width + cell_width / 2
                elements.append(
                    text(
                        x,
                        top_margin - 10,
                        str(label),
                        **{"class": "matrix-label", "text_anchor": "middle"},
                    )
                )

        # Draw cells and values
        for r in range(rows):
            row = values[r]
            if not isinstance(row, list):
                row = []
            for c in range(cols):
                x = left_margin + c * cell_width
                y = top_margin + r * cell_height
                value = row[c] if c < len(row) else ""
                state = highlights.get((r, c), "default")
                if state not in STATE_COLORS:
                    state = "default"
                elements.append(
                    rect(
                        x,
                        y,
                        cell_width,
                        cell_height,
                        **{"class": f"matrix-cell matrix-cell-{state}"},
                    )
                )
                elements.append(
                    text(
                        x + cell_width / 2,
                        y + cell_height / 2 + 5,
                        str(value),
                        **{"class": "matrix-value", "text_anchor": "middle"},
                    )
                )

        # Draw path highlight
        if len(path_points) > 1:
            points = [self._cell_center(point, left_margin, top_margin, cell_width, cell_height) for point in path_points]
            elements.append(
                polyline(
                    points,
                    stroke="#9C27B0",
                    stroke_width="3",
                    fill="none",
                    **{"class": "matrix-path"},
                )
            )

        # Draw arrows
        for start, end in arrows:
            start_x, start_y = self._cell_center(start, left_margin, top_margin, cell_width, cell_height)
            end_x, end_y = self._cell_center(end, left_margin, top_margin, cell_width, cell_height)
            elements.append(
                line(
                    start_x,
                    start_y,
                    end_x,
                    end_y,
                    stroke="#555",
                    stroke_width="2",
                    marker_end="url(#matrix-arrow)",
                    **{"class": "matrix-arrow"},
                )
            )

        if caption:
            elements.append(
                text(
                    svg_width / 2,
                    svg_height - 8,
                    str(caption),
                    **{"class": "matrix-caption", "text_anchor": "middle"},
                )
            )

        return svg_document("\n".join(elements), svg_width, svg_height)

    @staticmethod
    def _cell_center(
        coord: Tuple[int, int],
        left_margin: int,
        top_margin: int,
        cell_width: int,
        cell_height: int,
    ) -> Tuple[float, float]:
        row, col = coord
        x = left_margin + col * cell_width + cell_width / 2
        y = top_margin + row * cell_height + cell_height / 2
        return x, y

    @staticmethod
    def _extra_styles() -> str:
        return """
.matrix-cell { stroke: #343a40; stroke-width: 1.2; fill: #f8f9fa; }
.matrix-cell-current { fill: #fff3cd; }
.matrix-cell-visited { fill: #d1ecf1; }
.matrix-cell-target { fill: #d4edda; }
.matrix-cell-found { fill: #d4edda; }
.matrix-cell-invalid { fill: #f8d7da; }
.matrix-cell-rejected { fill: #f8d7da; }
.matrix-cell-comparison { fill: #FF9800; }
.matrix-value { font-size: 13px; font-family: sans-serif; fill: #212529; }
.matrix-label { font-size: 12px; font-family: sans-serif; fill: #6c757d; }
.matrix-caption { font-size: 13px; font-family: sans-serif; fill: #333; }
.matrix-path { stroke-linecap: round; stroke-linejoin: round; }
.matrix-arrow { stroke-linecap: round; }
"""

    @staticmethod
    def _arrow_marker() -> str:
        return """
<marker id="matrix-arrow" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
  <polygon points="0 0, 10 3.5, 0 7" fill="#555"/>
</marker>
"""
