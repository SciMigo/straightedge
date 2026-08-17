"""Dynamic programming table visualization template for CS/data structure diagrams."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from ..registry import register
from ..renderer import DEFAULT_STYLES, defs, line, rect, style, svg_document, text


STATE_COLORS = {
    "default": "#f8f9fa",
    "current": "#fff3cd",
    "visited": "#d1ecf1",
    "target": "#d4edda",
    "found": "#d4edda",
    "invalid": "#f8d7da",
    "rejected": "#f8d7da",
    "comparison": "#FF9800",
    "dependency": "#d1ecf1",
}


def _normalize_values(values: Any) -> Tuple[List[List[Any]], int, int]:
    if not isinstance(values, list):
        return [], 0, 0
    matrix: List[List[Any]] = []
    for row in values:
        if isinstance(row, list):
            matrix.append(list(row))
        else:
            matrix.append([row])
    if not matrix:
        return [], 0, 0
    max_cols = max(len(row) for row in matrix)
    padded = [row + [""] * (max_cols - len(row)) for row in matrix]
    return padded, len(padded), max_cols


def _normalize_labels(labels: Any, count: int) -> List[str]:
    if not isinstance(labels, list):
        return [""] * count
    normalized = [str(label) for label in labels[:count]]
    if len(normalized) < count:
        normalized.extend([""] * (count - len(normalized)))
    return normalized


def _parse_cell_key(key: Any) -> Tuple[int, int] | None:
    if isinstance(key, (list, tuple)) and len(key) == 2:
        if isinstance(key[0], int) and isinstance(key[1], int):
            return key[0], key[1]
        return None
    if isinstance(key, str) and "," in key:
        parts = [part.strip() for part in key.split(",", 1)]
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            return int(parts[0]), int(parts[1])
    return None


def _normalize_highlights(
    highlights: Any,
    rows: int,
    cols: int,
) -> Dict[Tuple[int, int], str]:
    if not isinstance(highlights, dict):
        return {}
    result: Dict[Tuple[int, int], str] = {}
    for key, state in highlights.items():
        if not isinstance(state, str):
            continue
        cell = _parse_cell_key(key)
        if cell is None:
            continue
        row, col = cell
        if 0 <= row < rows and 0 <= col < cols:
            result[(row, col)] = state
    return result


@register("dp_table")
class DPTableTemplate:
    """Render a dynamic programming table with labels and dependency arrows."""

    def render(self, params: Dict[str, Any]) -> str:
        values, rows, cols = _normalize_values(params.get("values", []))
        row_labels = _normalize_labels(params.get("row_labels", []), rows)
        col_labels = _normalize_labels(params.get("col_labels", []), cols)
        highlights = _normalize_highlights(params.get("highlights", {}), rows, cols)
        arrows = params.get("arrows", [])
        formula = params.get("formula")
        caption = params.get("caption")

        cell_width = int(params.get("cell_width", 50))
        cell_height = int(params.get("cell_height", 40))

        label_space_x = 30 if any(label for label in row_labels) else 0
        label_space_y = 30 if any(label for label in col_labels) else 0
        formula_space = 26 if formula else 0
        caption_space = 24 if caption else 0

        padding_x = 20
        padding_y = 20

        svg_width = padding_x * 2 + label_space_x + max(1, cols) * cell_width
        svg_height = (
            padding_y * 2
            + label_space_y
            + formula_space
            + max(1, rows) * cell_height
            + caption_space
        )

        table_x = padding_x + label_space_x
        table_y = padding_y + label_space_y + formula_space

        elements: List[str] = []
        elements.append(style(DEFAULT_STYLES + self._extra_styles()))
        elements.append(defs(self._arrow_marker()))

        if formula:
            elements.append(
                text(
                    svg_width / 2,
                    padding_y + 16,
                    str(formula),
                    **{"class": "dp-formula", "text_anchor": "middle"},
                )
            )

        if label_space_y:
            for col_idx, label in enumerate(col_labels):
                if not label:
                    continue
                x = table_x + col_idx * cell_width + cell_width / 2
                elements.append(
                    text(
                        x,
                        table_y - 10,
                        label,
                        **{"class": "dp-col-label", "text_anchor": "middle"},
                    )
                )

        if label_space_x:
            for row_idx, label in enumerate(row_labels):
                if not label:
                    continue
                y = table_y + row_idx * cell_height + cell_height / 2 + 5
                elements.append(
                    text(
                        table_x - 10,
                        y,
                        label,
                        **{"class": "dp-row-label", "text_anchor": "end"},
                    )
                )

        for row_idx in range(rows or 1):
            for col_idx in range(cols or 1):
                x = table_x + col_idx * cell_width
                y = table_y + row_idx * cell_height
                state = highlights.get((row_idx, col_idx), "default")
                elements.append(
                    rect(
                        x,
                        y,
                        cell_width,
                        cell_height,
                        **{"class": f"dp-cell dp-cell-{state}"},
                    )
                )
                if values:
                    value = values[row_idx][col_idx]
                    if value != "":
                        elements.append(
                            text(
                                x + cell_width / 2,
                                y + cell_height / 2 + 5,
                                str(value),
                                **{"class": "dp-value", "text_anchor": "middle"},
                            )
                        )

        if isinstance(arrows, list):
            for arrow in arrows:
                if not isinstance(arrow, dict):
                    continue
                start = arrow.get("from")
                end = arrow.get("to")
                if not (
                    isinstance(start, (list, tuple))
                    and isinstance(end, (list, tuple))
                    and len(start) == 2
                    and len(end) == 2
                ):
                    continue
                if not all(isinstance(idx, int) for idx in (*start, *end)):
                    continue
                start_row, start_col = start
                end_row, end_col = end
                if not (0 <= start_row < rows and 0 <= start_col < cols):
                    continue
                if not (0 <= end_row < rows and 0 <= end_col < cols):
                    continue
                x1 = table_x + start_col * cell_width + cell_width / 2
                y1 = table_y + start_row * cell_height + cell_height / 2
                x2 = table_x + end_col * cell_width + cell_width / 2
                y2 = table_y + end_row * cell_height + cell_height / 2
                elements.append(
                    line(
                        x1,
                        y1,
                        x2,
                        y2,
                        **{
                            "class": "dp-arrow",
                            "marker_end": "url(#dp-arrow)",
                        },
                    )
                )

        if caption:
            elements.append(
                text(
                    svg_width / 2,
                    svg_height - 8,
                    str(caption),
                    **{"class": "dp-caption", "text_anchor": "middle"},
                )
            )

        return svg_document("\n".join(elements), svg_width, svg_height)

    @staticmethod
    def _extra_styles() -> str:
        return """
.dp-cell { stroke: #343a40; stroke-width: 1.2; fill: #f8f9fa; }
.dp-cell-current { fill: #fff3cd; }
.dp-cell-visited { fill: #d1ecf1; }
.dp-cell-target { fill: #d4edda; }
.dp-cell-found { fill: #d4edda; }
.dp-cell-invalid { fill: #f8d7da; }
.dp-cell-rejected { fill: #f8d7da; }
.dp-cell-comparison { fill: #FF9800; }
.dp-cell-dependency { fill: #d1ecf1; }
.dp-value { font-size: 13px; font-family: sans-serif; fill: #212529; }
.dp-row-label, .dp-col-label { font-size: 12px; font-family: sans-serif; fill: #495057; font-weight: 600; }
.dp-formula { font-size: 12px; font-family: sans-serif; fill: #333; }
.dp-caption { font-size: 13px; font-family: sans-serif; fill: #333; }
.dp-arrow { stroke: #6c757d; stroke-width: 1.6; }
"""

    @staticmethod
    def _arrow_marker() -> str:
        return """
<marker id="dp-arrow" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
  <polygon points="0 0, 10 3.5, 0 7" fill="#6c757d"/>
</marker>
"""
