"""Queue/deque visualization template for CS/data structure diagrams."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

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
    "dequeue": "#fff3cd",
    "enqueue": "#d4edda",
}


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


@register("queue")
class QueueTemplate:
    """Render a queue/deque visualization with operations."""

    def render(self, params: Dict[str, Any]) -> str:
        values = params.get("values", [])
        if not isinstance(values, list):
            values = []

        count = len(values)
        cell_width = int(params.get("cell_width", 60))
        cell_height = int(params.get("cell_height", 45))
        highlights = _normalize_highlights(params.get("highlights", {}), count)
        caption = params.get("caption")
        front_label = str(params.get("front_label", "front"))
        back_label = str(params.get("back_label", "back"))

        operation = params.get("operation", {})
        if not isinstance(operation, dict):
            operation = {}
        operation_type = operation.get("type")
        operation_end = str(operation.get("end", "back"))
        operation_value = operation.get("value")
        show_operation_cell = operation_type == "enqueue" and operation_value is not None

        padding_x = 24
        has_dequeue_label = any(state == "dequeue" for state in highlights.values())
        has_operation_label = show_operation_cell or operation_type == "dequeue"
        top_margin = 40
        bottom_margin = 20 + (20 if has_dequeue_label or has_operation_label else 0)
        if caption:
            bottom_margin += 20

        queue_width = max(1, count) * cell_width
        op_gap = 20
        extra_left = cell_width + op_gap if show_operation_cell and operation_end == "front" else 0
        extra_right = cell_width + op_gap if show_operation_cell and operation_end != "front" else 0
        svg_width = padding_x * 2 + queue_width + extra_left + extra_right
        svg_height = top_margin + cell_height + bottom_margin

        queue_start_x = padding_x + extra_left
        cell_y = top_margin

        elements: List[str] = []
        elements.append(style(DEFAULT_STYLES + self._extra_styles()))
        elements.append(defs(self._arrow_marker()))

        if count == 0:
            elements.append(rect(queue_start_x, cell_y, cell_width, cell_height,
                                 stroke_dasharray="4,3",
                                 **{"class": "queue-cell queue-cell-default"}))
            elements.append(text(queue_start_x + cell_width / 2,
                                 cell_y + cell_height / 2 + 5, "∅",
                                 **{"class": "queue-value", "text_anchor": "middle"}))

        for idx, value in enumerate(values):
            x = queue_start_x + idx * cell_width
            state = highlights.get(idx, "default")
            if state not in STATE_COLORS:
                state = "default"
            state_class = f"queue-cell queue-cell-{state}"
            elements.append(rect(x, cell_y, cell_width, cell_height, **{"class": state_class}))
            elements.append(
                text(
                    x + cell_width / 2,
                    cell_y + cell_height / 2 + 5,
                    str(value),
                    **{"class": "queue-value", "text_anchor": "middle"},
                )
            )

            if state == "dequeue":
                label_y = cell_y + cell_height + 24
                elements.append(
                    line(
                        x + cell_width / 2,
                        cell_y + cell_height,
                        x + cell_width / 2,
                        label_y - 8,
                        stroke="#333",
                        stroke_width="2",
                        marker_end="url(#queue-arrow)",
                    )
                )
                elements.append(
                    text(
                        x + cell_width / 2,
                        label_y + 8,
                        "dequeue",
                        **{"class": "queue-op-label", "text_anchor": "middle"},
                    )
                )

        if count > 0:
            front_x = queue_start_x + cell_width / 2
            back_x = queue_start_x + (count - 1) * cell_width + cell_width / 2
            label_y = cell_y - 18
            for x, label in ((front_x, front_label), (back_x, back_label)):
                elements.append(
                    line(
                        x,
                        label_y + 6,
                        x,
                        cell_y,
                        stroke="#333",
                        stroke_width="2",
                        marker_end="url(#queue-arrow)",
                    )
                )
                elements.append(
                    text(
                        x,
                        label_y,
                        label,
                        **{"class": "queue-end-label", "text_anchor": "middle"},
                    )
                )

        if show_operation_cell:
            if operation_end == "front":
                op_x = padding_x
                arrow_start_x = op_x + cell_width
                arrow_end_x = queue_start_x
            else:
                op_x = queue_start_x + queue_width + op_gap
                arrow_start_x = op_x
                arrow_end_x = queue_start_x + queue_width

            elements.append(rect(op_x, cell_y, cell_width, cell_height, **{"class": "queue-cell queue-cell-enqueue"}))
            elements.append(
                text(
                    op_x + cell_width / 2,
                    cell_y + cell_height / 2 + 5,
                    str(operation_value),
                    **{"class": "queue-value", "text_anchor": "middle"},
                )
            )
            elements.append(
                line(
                    arrow_start_x,
                    cell_y + cell_height / 2,
                    arrow_end_x,
                    cell_y + cell_height / 2,
                    stroke="#333",
                    stroke_width="2",
                    marker_end="url(#queue-arrow)",
                )
            )
            elements.append(
                text(
                    op_x + cell_width / 2,
                    cell_y + cell_height + 24,
                    f"enqueue {operation_value}",
                    **{"class": "queue-op-label", "text_anchor": "middle"},
                )
            )
        elif operation_type == "dequeue" and count > 0:
            end_index = 0 if operation_end == "front" else count - 1
            x = queue_start_x + end_index * cell_width + cell_width / 2
            label_y = cell_y + cell_height + 24
            elements.append(
                line(
                    x,
                    cell_y + cell_height,
                    x,
                    label_y - 8,
                    stroke="#333",
                    stroke_width="2",
                    marker_end="url(#queue-arrow)",
                )
            )
            elements.append(
                text(
                    x,
                    label_y + 8,
                    "dequeue",
                    **{"class": "queue-op-label", "text_anchor": "middle"},
                )
            )

        if caption:
            elements.append(
                text(
                    svg_width / 2,
                    svg_height - 8,
                    str(caption),
                    **{"class": "queue-caption", "text_anchor": "middle"},
                )
            )

        return svg_document("\n".join(elements), svg_width, svg_height)

    @staticmethod
    def _extra_styles() -> str:
        return """
.queue-cell { stroke: #343a40; stroke-width: 1.2; fill: #f8f9fa; }
.queue-cell-current { fill: #fff3cd; }
.queue-cell-visited { fill: #d1ecf1; }
.queue-cell-target { fill: #d4edda; }
.queue-cell-found { fill: #d4edda; }
.queue-cell-invalid { fill: #f8d7da; }
.queue-cell-rejected { fill: #f8d7da; }
.queue-cell-comparison { fill: #FF9800; }
.queue-cell-dequeue { fill: #fff3cd; }
.queue-cell-enqueue { fill: #d4edda; }
.queue-value { font-size: 14px; font-family: sans-serif; fill: #212529; }
.queue-end-label { font-size: 12px; font-family: sans-serif; font-weight: 600; fill: #333; }
.queue-op-label { font-size: 12px; font-family: sans-serif; fill: #444; }
.queue-caption { font-size: 13px; font-family: sans-serif; fill: #333; }
"""

    @staticmethod
    def _arrow_marker() -> str:
        return """
<marker id="queue-arrow" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
  <polygon points="0 0, 10 3.5, 0 7" fill="#333"/>
</marker>
"""
