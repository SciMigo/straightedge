"""Stack visualization template for CS/data structure diagrams."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple

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
    "remaining": "#e9ecef",
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


@register("stack")
class StackTemplate:
    """Render a stack visualization with optional highlights and operations."""

    def render(self, params: Dict[str, Any]) -> str:
        values = params.get("values", [])
        if not isinstance(values, list):
            values = []

        count = len(values)
        orientation = params.get("orientation", "vertical")
        cell_width = int(params.get("cell_width", 100))
        cell_height = int(params.get("cell_height", 36))
        top_label = params.get("top_label", "")
        highlights = _normalize_highlights(params.get("highlights", {}), count)
        annotations = params.get("annotations", [])
        operation = params.get("operation", {})
        caption = params.get("caption")

        left_label_space, right_label_space = self._label_margins(top_label, annotations)
        op_space = self._operation_space(operation, cell_height)

        padding_x = 20
        padding_y = 20

        if orientation == "horizontal":
            svg_width = padding_x * 2 + left_label_space + right_label_space + count * cell_width
            svg_height = padding_y * 2 + cell_height + op_space + (20 if caption else 0)
            stack_origin = (padding_x + left_label_space, padding_y + op_space)
            elements, stack_bounds = self._render_horizontal_stack(
                values,
                stack_origin,
                cell_width,
                cell_height,
                highlights,
                top_label,
                annotations,
                operation,
            )
        else:
            svg_width = padding_x * 2 + left_label_space + right_label_space + cell_width
            svg_height = (
                padding_y * 2
                + op_space
                + max(1, count) * cell_height
                + (20 if caption else 0)
            )
            stack_origin = (padding_x + left_label_space, padding_y + op_space)
            elements, stack_bounds = self._render_vertical_stack(
                values,
                stack_origin,
                cell_width,
                cell_height,
                highlights,
                top_label,
                annotations,
                operation,
            )

        if caption:
            elements.append(
                text(
                    svg_width / 2,
                    svg_height - 8,
                    str(caption),
                    **{"class": "stack-caption", "text_anchor": "middle"},
                )
            )

        elements.insert(0, defs(self._arrow_marker()))
        elements.insert(0, style(DEFAULT_STYLES + self._extra_styles()))

        return svg_document("\n".join(elements), svg_width, svg_height)

    @staticmethod
    def _label_margins(top_label: Any, annotations: Any) -> Tuple[int, int]:
        left_space = 20
        right_space = 20
        if top_label:
            left_space = 70
        if isinstance(annotations, list):
            for annotation in annotations:
                if not isinstance(annotation, dict):
                    continue
                position = annotation.get("position", "left")
                if position == "right":
                    right_space = 70
                else:
                    left_space = 70
        return left_space, right_space

    @staticmethod
    def _operation_space(operation: Any, cell_height: int) -> int:
        if not isinstance(operation, dict):
            return 0
        op_type = operation.get("type")
        if op_type in {"push", "pop"}:
            return cell_height + 20
        return 0

    def _render_vertical_stack(
        self,
        values: List[Any],
        origin: Tuple[int, int],
        cell_width: int,
        cell_height: int,
        highlights: Dict[int, str],
        top_label: Any,
        annotations: Any,
        operation: Any,
    ) -> Tuple[List[str], Tuple[float, float, float, float]]:
        elements: List[str] = []
        stack_x, stack_y = origin
        count = len(values)

        for offset, value in enumerate(reversed(values)):
            idx = count - 1 - offset
            y = stack_y + offset * cell_height
            state = highlights.get(idx, "default")
            elements.append(
                rect(
                    stack_x,
                    y,
                    cell_width,
                    cell_height,
                    **{"class": f"stack-cell stack-cell-{state}"},
                )
            )
            elements.append(
                text(
                    stack_x + cell_width / 2,
                    y + cell_height / 2 + 5,
                    str(value),
                    **{"class": "stack-value", "text_anchor": "middle"},
                )
            )

        if top_label and count > 0:
            elements.append(
                text(
                    stack_x - 10,
                    stack_y + cell_height / 2 + 5,
                    str(top_label),
                    **{"class": "stack-top-label", "text_anchor": "end"},
                )
            )

        self._render_annotations(
            elements,
            annotations,
            stack_x,
            stack_y,
            cell_width,
            cell_height,
            count,
            orientation="vertical",
        )

        self._render_operation(
            elements,
            operation,
            stack_x,
            stack_y,
            cell_width,
            cell_height,
            orientation="vertical",
        )

        height = max(1, count) * cell_height
        return elements, (stack_x, stack_y, cell_width, height)

    def _render_horizontal_stack(
        self,
        values: List[Any],
        origin: Tuple[int, int],
        cell_width: int,
        cell_height: int,
        highlights: Dict[int, str],
        top_label: Any,
        annotations: Any,
        operation: Any,
    ) -> Tuple[List[str], Tuple[float, float, float, float]]:
        elements: List[str] = []
        stack_x, stack_y = origin
        count = len(values)

        for offset, value in enumerate(values):
            x = stack_x + offset * cell_width
            state = highlights.get(offset, "default")
            elements.append(
                rect(
                    x,
                    stack_y,
                    cell_width,
                    cell_height,
                    **{"class": f"stack-cell stack-cell-{state}"},
                )
            )
            elements.append(
                text(
                    x + cell_width / 2,
                    stack_y + cell_height / 2 + 5,
                    str(value),
                    **{"class": "stack-value", "text_anchor": "middle"},
                )
            )

        if top_label and count > 0:
            elements.append(
                text(
                    stack_x + count * cell_width + 10,
                    stack_y + cell_height / 2 + 5,
                    str(top_label),
                    **{"class": "stack-top-label", "text_anchor": "start"},
                )
            )

        self._render_annotations(
            elements,
            annotations,
            stack_x,
            stack_y,
            cell_width,
            cell_height,
            count,
            orientation="horizontal",
        )

        self._render_operation(
            elements,
            operation,
            stack_x,
            stack_y,
            cell_width,
            cell_height,
            orientation="horizontal",
        )

        width = max(1, count) * cell_width
        return elements, (stack_x, stack_y, width, cell_height)

    def _render_annotations(
        self,
        elements: List[str],
        annotations: Any,
        stack_x: float,
        stack_y: float,
        cell_width: int,
        cell_height: int,
        count: int,
        orientation: str,
    ) -> None:
        if not isinstance(annotations, list):
            return

        for annotation in annotations:
            if not isinstance(annotation, dict):
                continue
            idx = annotation.get("index")
            if not isinstance(idx, int) or not (0 <= idx < count):
                continue
            label = str(annotation.get("text", ""))
            position = annotation.get("position", "left")
            if orientation == "vertical":
                cell_y = stack_y + (count - 1 - idx) * cell_height
                if position == "right":
                    text_x = stack_x + cell_width + 30
                    line_x = stack_x + cell_width
                    text_anchor = "start"
                else:
                    text_x = stack_x - 30
                    line_x = stack_x
                    text_anchor = "end"
                mid_y = cell_y + cell_height / 2
                elements.append(
                    line(
                        line_x,
                        mid_y,
                        text_x,
                        mid_y,
                        stroke="#666",
                        stroke_width="1",
                        stroke_dasharray="4,2",
                    )
                )
                if label:
                    elements.append(
                        text(
                            text_x,
                            mid_y + 5,
                            label,
                            **{"class": "stack-annotation", "text_anchor": text_anchor},
                        )
                    )
            else:
                cell_x = stack_x + idx * cell_width
                if position == "below":
                    text_y = stack_y + cell_height + 25
                    line_y = stack_y + cell_height
                else:
                    text_y = stack_y - 15
                    line_y = stack_y
                mid_x = cell_x + cell_width / 2
                elements.append(
                    line(
                        mid_x,
                        line_y,
                        mid_x,
                        text_y,
                        stroke="#666",
                        stroke_width="1",
                        stroke_dasharray="4,2",
                    )
                )
                if label:
                    elements.append(
                        text(
                            mid_x,
                            text_y - 2 if position != "below" else text_y + 12,
                            label,
                            **{"class": "stack-annotation", "text_anchor": "middle"},
                        )
                    )

    def _render_operation(
        self,
        elements: List[str],
        operation: Any,
        stack_x: float,
        stack_y: float,
        cell_width: int,
        cell_height: int,
        orientation: str,
    ) -> None:
        if not isinstance(operation, dict):
            return
        op_type = operation.get("type")
        if orientation == "vertical":
            if op_type == "push":
                value = operation.get("value", "")
                op_y = stack_y - cell_height - 10
                elements.append(
                    rect(
                        stack_x,
                        op_y,
                        cell_width,
                        cell_height,
                        **{"class": "stack-cell stack-cell-operation"},
                    )
                )
                elements.append(
                    text(
                        stack_x + cell_width / 2,
                        op_y + cell_height / 2 + 5,
                        str(value),
                        **{"class": "stack-value", "text_anchor": "middle"},
                    )
                )
                elements.append(
                    line(
                        stack_x + cell_width / 2,
                        op_y + cell_height + 5,
                        stack_x + cell_width / 2,
                        stack_y,
                        stroke="#333",
                        stroke_width="2",
                        marker_end="url(#stack-arrow)",
                    )
                )
                elements.append(
                    text(
                        stack_x + cell_width / 2,
                        op_y - 4,
                        f"push({value})",
                        **{"class": "stack-operation", "text_anchor": "middle"},
                    )
                )
            elif op_type == "pop":
                elements.append(
                    line(
                        stack_x + cell_width / 2,
                        stack_y,
                        stack_x + cell_width / 2,
                        stack_y - cell_height - 10,
                        stroke="#333",
                        stroke_width="2",
                        marker_end="url(#stack-arrow)",
                    )
                )
                elements.append(
                    text(
                        stack_x + cell_width / 2,
                        stack_y - cell_height - 18,
                        "pop()",
                        **{"class": "stack-operation", "text_anchor": "middle"},
                    )
                )
        else:
            if op_type == "push":
                value = operation.get("value", "")
                op_x = stack_x + cell_width * (operation.get("index", 0))
                op_y = stack_y - cell_height - 10
                elements.append(
                    rect(
                        op_x,
                        op_y,
                        cell_width,
                        cell_height,
                        **{"class": "stack-cell stack-cell-operation"},
                    )
                )
                elements.append(
                    text(
                        op_x + cell_width / 2,
                        op_y + cell_height / 2 + 5,
                        str(value),
                        **{"class": "stack-value", "text_anchor": "middle"},
                    )
                )
                elements.append(
                    line(
                        op_x + cell_width / 2,
                        op_y + cell_height + 5,
                        op_x + cell_width / 2,
                        stack_y,
                        stroke="#333",
                        stroke_width="2",
                        marker_end="url(#stack-arrow)",
                    )
                )
                elements.append(
                    text(
                        op_x + cell_width / 2,
                        op_y - 4,
                        f"push({value})",
                        **{"class": "stack-operation", "text_anchor": "middle"},
                    )
                )
            elif op_type == "pop":
                op_x = stack_x + cell_width * (max(0, operation.get("index", 0)))
                elements.append(
                    line(
                        op_x + cell_width / 2,
                        stack_y,
                        op_x + cell_width / 2,
                        stack_y - cell_height - 10,
                        stroke="#333",
                        stroke_width="2",
                        marker_end="url(#stack-arrow)",
                    )
                )
                elements.append(
                    text(
                        op_x + cell_width / 2,
                        stack_y - cell_height - 18,
                        "pop()",
                        **{"class": "stack-operation", "text_anchor": "middle"},
                    )
                )

    @staticmethod
    def _extra_styles() -> str:
        return """
.stack-cell { stroke: #343a40; stroke-width: 1.2; fill: #f8f9fa; }
.stack-cell-current { fill: #fff3cd; }
.stack-cell-visited { fill: #d1ecf1; }
.stack-cell-target { fill: #d4edda; }
.stack-cell-found { fill: #d4edda; }
.stack-cell-invalid { fill: #f8d7da; }
.stack-cell-rejected { fill: #f8d7da; }
.stack-cell-comparison { fill: #FF9800; }
.stack-cell-remaining { fill: #e9ecef; }
.stack-cell-operation { fill: #f1f3f5; stroke-dasharray: 4,2; }
.stack-value { font-size: 14px; font-family: sans-serif; fill: #212529; }
.stack-top-label { font-size: 12px; font-family: sans-serif; fill: #333; font-weight: 600; }
.stack-annotation { font-size: 12px; font-family: sans-serif; fill: #444; }
.stack-operation { font-size: 12px; font-family: sans-serif; fill: #333; }
.stack-caption { font-size: 13px; font-family: sans-serif; fill: #333; }
"""

    @staticmethod
    def _arrow_marker() -> str:
        return """
<marker id="stack-arrow" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
  <polygon points="0 0, 10 3.5, 0 7" fill="#333"/>
</marker>
"""
