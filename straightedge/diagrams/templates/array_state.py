"""Array state visualization template for CS/data structure diagrams."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

from ..registry import register
from ..renderer import DEFAULT_STYLES, defs, line, path, rect, style, svg_document, text


STATE_COLORS = {
    "default": "#f8f9fa",
    "current": "#fff3cd",
    "visited": "#d1ecf1",
    "target": "#d4edda",
    "found": "#d4edda",
    "invalid": "#f8d7da",
    "rejected": "#f8d7da",
    "comparison": "#FF9800",
    "remaining": "#e9ecef",  # Not-yet-processed elements
}

POINTER_COLORS = ["#2196F3", "#4CAF50", "#FF9800"]


def _expand_highlight_indices(key: Any, count: int) -> Iterable[int]:
    if isinstance(key, int):
        if 0 <= key < count:
            return [key]
        return []

    key_str = str(key)
    if "-" in key_str:
        parts = key_str.split("-", 1)
        if parts[0].strip().isdigit() and parts[1].strip().isdigit():
            start = int(parts[0])
            end = int(parts[1])
            if start > end:
                start, end = end, start
            return [idx for idx in range(start, end + 1) if 0 <= idx < count]
        return []

    if key_str.strip().isdigit():
        idx = int(key_str)
        if 0 <= idx < count:
            return [idx]
    return []


def _normalize_highlights(highlights: Any, count: int) -> Dict[int, str]:
    if not isinstance(highlights, dict):
        return {}
    result: Dict[int, str] = {}
    for key, state in highlights.items():
        if not isinstance(state, str):
            continue
        for idx in _expand_highlight_indices(key, count):
            result[idx] = state
    return result


@register("array_state")
class ArrayStateTemplate:
    """Render a linear array visualization with highlights and pointers."""

    def render(self, params: Dict[str, Any]) -> str:
        values = params.get("values", [])
        if not isinstance(values, list):
            values = []

        count = len(values)
        cell_width = int(params.get("cell_width", 50))
        cell_height = int(params.get("cell_height", 40))
        show_indices = bool(params.get("indices", False))
        show_values = bool(params.get("show_values", True))
        highlights = _normalize_highlights(params.get("highlights", {}), count)
        pointers = params.get("pointers", [])
        annotations = params.get("annotations", [])
        brackets = params.get("brackets", [])
        caption = params.get("caption")

        # Check if any elements need space above or below the array
        has_above = any(
            isinstance(item, dict) and item.get("position", "above") == "above"
            for item in (pointers or [])
        ) or any(
            isinstance(item, dict) and item.get("position", "above") == "above"
            for item in (annotations or [])
        ) or any(
            isinstance(item, dict) and item.get("position", "below") == "above"
            for item in (brackets or [])
        )
        has_below = any(
            isinstance(item, dict) and item.get("position", "above") == "below"
            for item in (pointers or [])
        ) or any(
            isinstance(item, dict) and item.get("position", "above") == "below"
            for item in (annotations or [])
        ) or any(
            isinstance(item, dict) and item.get("position", "below") == "below"
            for item in (brackets or [])
        )

        padding_x = 20
        top_margin = 30 + (30 if has_above else 0)
        bottom_margin = 30 + (20 if show_indices else 0) + (30 if has_below else 0)
        if caption:
            bottom_margin += 20

        svg_width = max(1, count) * cell_width + padding_x * 2
        svg_height = top_margin + cell_height + bottom_margin
        cell_y = top_margin

        elements: List[str] = []
        elements.append(style(DEFAULT_STYLES + self._extra_styles()))
        elements.append(defs(self._arrow_marker()))

        # Draw cells and values
        for idx, value in enumerate(values):
            x = padding_x + idx * cell_width
            state = highlights.get(idx, "default")
            state_class = f"array-cell array-cell-{state}"
            elements.append(
                rect(x, cell_y, cell_width, cell_height, **{"class": state_class})
            )
            if show_values:
                elements.append(
                    text(
                        x + cell_width / 2,
                        cell_y + cell_height / 2 + 5,
                        str(value),
                        **{"class": "array-value", "text_anchor": "middle"},
                    )
                )
            if show_indices:
                elements.append(
                    text(
                        x + cell_width / 2,
                        cell_y + cell_height + 18,
                        str(idx),
                        **{"class": "array-index", "text_anchor": "middle"},
                    )
                )

        # Draw pointers
        if isinstance(pointers, list):
            for i, pointer in enumerate(pointers):
                if not isinstance(pointer, dict):
                    continue
                idx = pointer.get("index")
                if not isinstance(idx, int) or not (0 <= idx < count):
                    continue
                label = str(pointer.get("label", ""))
                position = pointer.get("position", "above")
                color = pointer.get("color", POINTER_COLORS[i % len(POINTER_COLORS)])
                x = padding_x + idx * cell_width + cell_width / 2

                if position == "below":
                    label_y = cell_y + cell_height + (35 if show_indices else 20)
                    line_start_y = label_y - 10
                    line_end_y = cell_y + cell_height
                    elements.append(
                        line(
                            x,
                            line_start_y,
                            x,
                            line_end_y,
                            stroke=color,
                            stroke_width="2",
                            marker_end="url(#array-arrow)",
                        )
                    )
                    if label:
                        elements.append(
                            text(
                                x,
                                label_y + 12,
                                label,
                                **{
                                    "class": "array-pointer-label",
                                    "text_anchor": "middle",
                                    "fill": color,
                                },
                            )
                        )
                else:
                    line_start_y = cell_y - 20
                    line_end_y = cell_y
                    elements.append(
                        line(
                            x,
                            line_start_y,
                            x,
                            line_end_y,
                            stroke=color,
                            stroke_width="2",
                            marker_end="url(#array-arrow)",
                        )
                    )
                    if label:
                        elements.append(
                            text(
                                x,
                                line_start_y - 5,
                                label,
                                **{
                                    "class": "array-pointer-label",
                                    "text_anchor": "middle",
                                    "fill": color,
                                },
                            )
                        )

        # Draw annotations
        if isinstance(annotations, list):
            for annotation in annotations:
                if not isinstance(annotation, dict):
                    continue
                idx = annotation.get("index")
                if not isinstance(idx, int) or not (0 <= idx < count):
                    continue
                note = str(annotation.get("text", ""))
                position = annotation.get("position", "above")
                x = padding_x + idx * cell_width + cell_width / 2
                if position == "below":
                    note_y = cell_y + cell_height + (55 if show_indices else 40)
                    line_start_y = note_y - 12
                    line_end_y = cell_y + cell_height
                else:
                    note_y = cell_y - 45
                    line_start_y = note_y + 6
                    line_end_y = cell_y
                elements.append(
                    line(
                        x,
                        line_start_y,
                        x,
                        line_end_y,
                        stroke="#666",
                        stroke_width="1",
                        stroke_dasharray="4,2",
                    )
                )
                if note:
                    elements.append(
                        text(
                            x,
                            note_y,
                            note,
                            **{"class": "array-annotation", "text_anchor": "middle"},
                        )
                    )

        # Draw brackets
        if isinstance(brackets, list):
            for bracket in brackets:
                if not isinstance(bracket, dict):
                    continue
                start = bracket.get("from")
                end = bracket.get("to")
                if not isinstance(start, int) or not isinstance(end, int):
                    continue
                if start > end:
                    start, end = end, start
                if start < 0 or end >= count:
                    continue
                label = str(bracket.get("label", ""))
                position = bracket.get("position", "below")
                x_start = padding_x + start * cell_width
                x_end = padding_x + (end + 1) * cell_width
                if position == "above":
                    bracket_y = cell_y - 10
                    bracket_height = -10
                    label_y = bracket_y - 8
                else:
                    bracket_y = cell_y + cell_height + (25 if show_indices else 10)
                    bracket_height = 10
                    label_y = bracket_y + 18
                bracket_path = (
                    f"M {x_start} {bracket_y} v {bracket_height} "
                    f"H {x_end} v {-bracket_height}"
                )
                elements.append(
                    path(
                        bracket_path,
                        stroke="#555",
                        stroke_width="2",
                        fill="none",
                    )
                )
                if label:
                    elements.append(
                        text(
                            (x_start + x_end) / 2,
                            label_y,
                            label,
                            **{"class": "array-bracket-label", "text_anchor": "middle"},
                        )
                    )

        if caption:
            elements.append(
                text(
                    svg_width / 2,
                    svg_height - 8,
                    str(caption),
                    **{"class": "array-caption", "text_anchor": "middle"},
                )
            )

        return svg_document("\n".join(elements), svg_width, svg_height)

    @staticmethod
    def _extra_styles() -> str:
        return """
.array-cell { stroke: #343a40; stroke-width: 1.2; fill: #f8f9fa; }
.array-cell-current { fill: #fff3cd; }
.array-cell-visited { fill: #d1ecf1; }
.array-cell-target { fill: #d4edda; }
.array-cell-found { fill: #d4edda; }
.array-cell-invalid { fill: #f8d7da; }
.array-cell-rejected { fill: #f8d7da; }
.array-cell-comparison { fill: #FF9800; }
.array-cell-remaining { fill: #e9ecef; }
.array-value { font-size: 14px; font-family: sans-serif; fill: #212529; }
.array-index { font-size: 12px; font-family: sans-serif; fill: #6c757d; }
.array-pointer-label { font-size: 12px; font-family: sans-serif; font-weight: 600; }
.array-annotation { font-size: 12px; font-family: sans-serif; fill: #444; }
.array-bracket-label { font-size: 12px; font-family: sans-serif; fill: #444; }
.array-caption { font-size: 13px; font-family: sans-serif; fill: #333; }
"""

    @staticmethod
    def _arrow_marker() -> str:
        # Use explicit color for broader renderer compatibility
        return """
<marker id="array-arrow" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
  <polygon points="0 0, 10 3.5, 0 7" fill="#333"/>
</marker>
"""
