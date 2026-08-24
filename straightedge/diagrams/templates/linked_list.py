"""Linked list visualization template for CS/data structure diagrams."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..registry import register
from ..renderer import DEFAULT_STYLES, defs, line, path, rect, style, svg_document, text, circle
from ..themes import DIAGRAM_THEMES, DiagramTheme, family, readable_on, resolve_theme


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

POINTER_COLORS = ["#2196F3", "#4CAF50", "#FF9800"]
CYCLE = "#9C27B0"

#: The pre-theme palette stated as roles. Four darks that were four different
#: literals — label text, node border, connector ink, back-pointer ink — keep
#: their own roles rather than collapsing into one; the renderer reads the
#: theme unconditionally, so `professional` is the old output by construction.
PROFESSIONAL = DIAGRAM_THEMES["professional"].variant(
    background="", surface=STATE_COLORS["default"],
    warning_soft=STATE_COLORS["current"], secondary_soft=STATE_COLORS["visited"],
    success_soft=STATE_COLORS["target"], danger_soft=STATE_COLORS["invalid"],
    warning=STATE_COLORS["comparison"],
    text="#212529", muted="#6c757d", rule="#343a40", ink="#333", ink_soft="#666",
    secondary=POINTER_COLORS[0], success=POINTER_COLORS[1], accent=CYCLE,
)
THEMES = family(PROFESSIONAL, "classroom", "playful", "dark", "high-contrast")


def _normalize_highlights(highlights: Any) -> Dict[str, str]:
    if not isinstance(highlights, dict):
        return {}
    result: Dict[str, str] = {}
    for key, state in highlights.items():
        if not isinstance(state, str):
            continue
        result[str(key)] = state
    return result


@register("linked_list")
class LinkedListTemplate:
    """Render a themed singly or doubly linked list visualization."""

    themes = THEMES

    def render(self, params: Dict[str, Any]) -> str:
        theme = resolve_theme(params.get("theme", "professional"), THEMES)
        # A comparison node is filled with the saturated warning colour, on
        # which the body ink does not read in every palette (a dark theme's
        # amber under near-white text). Whichever ink reads is used there.
        comparison_ink = readable_on(theme.warning, theme.text, theme.on_primary)
        nodes = params.get("nodes", [])
        if not isinstance(nodes, list):
            nodes = []

        list_type = params.get("type", "singly")
        pointers = params.get("pointers", [])
        highlights = _normalize_highlights(params.get("highlights", {}))
        cycle_to = params.get("cycle_to")
        show_null = bool(params.get("show_null", True))
        caption = params.get("caption")

        node_width = int(params.get("node_width", 70))
        node_height = int(params.get("node_height", 40))
        value_width = int(params.get("value_width", 40))
        pointer_width = node_width - value_width
        node_gap = int(params.get("node_gap", 40))
        padding_x = 20
        padding_top = 30

        valid_nodes: List[Dict[str, Any]] = []
        for node in nodes:
            if not isinstance(node, dict):
                continue
            node_id = node.get("id")
            if node_id is None:
                continue
            valid_nodes.append(node)

        count = len(valid_nodes)
        has_above = isinstance(pointers, list) and len(pointers) > 0
        top_margin = padding_top + (20 if has_above else 0)
        bottom_margin = 30 + (20 if caption else 0)

        extra_tail = node_gap if show_null and count > 0 else 0
        svg_width = padding_x * 2 + max(1, count) * node_width + max(0, count - 1) * node_gap + extra_tail
        svg_height = top_margin + node_height + bottom_margin
        node_y = top_margin

        elements: List[str] = []
        elements.append(style(DEFAULT_STYLES + self._extra_styles(theme)))
        elements.append(defs(self._arrow_markers(theme)))
        if theme.background:
            elements.append(rect(0, 0, svg_width, svg_height, fill=theme.background,
                                 **{"class": "linked-background"}))

        node_positions: Dict[str, float] = {}

        # Draw nodes
        for idx, node in enumerate(valid_nodes):
            node_id = str(node.get("id"))
            value = node.get("value", "")
            x = padding_x + idx * (node_width + node_gap)
            node_positions[node_id] = x
            state = highlights.get(node_id, "default")
            node_class = f"linked-node linked-node-{state}"

            elements.append(rect(x, node_y, node_width, node_height, **{"class": node_class}))
            elements.append(
                line(
                    x + value_width,
                    node_y,
                    x + value_width,
                    node_y + node_height,
                    stroke=theme.rule,
                    stroke_width="1.2",
                )
            )
            value_attrs = {"class": "linked-node-value", "text_anchor": "middle"}
            if state == "comparison" and comparison_ink != theme.text:
                value_attrs["fill"] = comparison_ink
            elements.append(
                text(
                    x + value_width / 2,
                    node_y + node_height / 2 + 5,
                    str(value),
                    **value_attrs,
                )
            )
            elements.append(
                circle(
                    x + value_width + pointer_width / 2,
                    node_y + node_height / 2,
                    4,
                    **{"class": "linked-node-pointer-dot"},
                )
            )

        # Draw arrows between nodes
        for idx in range(count - 1):
            start_x = padding_x + idx * (node_width + node_gap) + node_width
            end_x = padding_x + (idx + 1) * (node_width + node_gap)
            center_y = node_y + node_height / 2
            elements.append(
                line(
                    start_x,
                    center_y,
                    end_x,
                    center_y,
                    stroke=theme.ink,
                    stroke_width="2",
                    marker_end="url(#linked-arrow)",
                    **{"class": "linked-list-arrow"},
                )
            )
            if list_type == "doubly":
                back_y = center_y + 12
                elements.append(
                    line(
                        end_x,
                        back_y,
                        start_x,
                        back_y,
                        stroke=theme.ink_soft,
                        stroke_width="1.8",
                        marker_end="url(#linked-arrow)",
                        **{"class": "linked-list-back-arrow"},
                    )
                )

        # Null marker
        if show_null and count > 0:
            last_x = padding_x + (count - 1) * (node_width + node_gap) + node_width
            null_x = last_x + node_gap - 10
            center_y = node_y + node_height / 2
            elements.append(
                line(
                    last_x,
                    center_y,
                    null_x,
                    center_y,
                    stroke=theme.ink,
                    stroke_width="2",
                    marker_end="url(#linked-arrow)",
                    **{"class": "linked-list-arrow"},
                )
            )
            elements.append(
                text(
                    null_x + 12,
                    center_y + 5,
                    "null",
                    **{"class": "linked-null-label"},
                )
            )

        # Cycle arrow
        if cycle_to is not None and count > 1:
            cycle_id = str(cycle_to)
            if cycle_id in node_positions:
                last_x = padding_x + (count - 1) * (node_width + node_gap) + node_width
                start_y = node_y + node_height / 2
                target_x = node_positions[cycle_id] + node_width / 2
                target_y = node_y - 15
                curve = (
                    f"M {last_x} {start_y} "
                    f"C {last_x + 40} {start_y - 40}, {target_x - 40} {target_y - 20}, {target_x} {target_y}"
                )
                elements.append(
                    path(
                        curve,
                        stroke=theme.accent,
                        stroke_width="2",
                        fill="none",
                        marker_end="url(#linked-arrow)",
                        **{"class": "linked-list-cycle"},
                    )
                )

        # Pointers
        if isinstance(pointers, list):
            for i, pointer in enumerate(pointers):
                if not isinstance(pointer, dict):
                    continue
                node_id = pointer.get("node")
                if node_id is None:
                    continue
                node_key = str(node_id)
                if node_key not in node_positions:
                    continue
                label = str(pointer.get("label", ""))
                palette = (theme.secondary, theme.success, theme.warning)
                color = pointer.get("color", palette[i % len(palette)])
                x = node_positions[node_key] + node_width / 2
                line_start_y = node_y - 20
                line_end_y = node_y
                elements.append(
                    line(
                        x,
                        line_start_y,
                        x,
                        line_end_y,
                        stroke=color,
                        stroke_width="2",
                        marker_end="url(#linked-arrow)",
                        **{"class": "linked-pointer"},
                    )
                )
                if label:
                    elements.append(
                        text(
                            x,
                            line_start_y - 5,
                            label,
                            **{"class": "linked-pointer-label", "text_anchor": "middle", "fill": color},
                        )
                    )

        if caption:
            elements.append(
                text(
                    svg_width / 2,
                    svg_height - 8,
                    str(caption),
                    **{"class": "linked-caption", "text_anchor": "middle"},
                )
            )

        return svg_document("\n".join(elements), svg_width, svg_height)

    @staticmethod
    def _extra_styles(theme: DiagramTheme) -> str:
        return f"""
.linked-node {{ stroke: {theme.rule}; stroke-width: 1.2; fill: {theme.surface}; }}
.linked-node-current {{ fill: {theme.warning_soft}; }}
.linked-node-visited {{ fill: {theme.secondary_soft}; }}
.linked-node-target {{ fill: {theme.success_soft}; }}
.linked-node-found {{ fill: {theme.success_soft}; }}
.linked-node-invalid {{ fill: {theme.danger_soft}; }}
.linked-node-rejected {{ fill: {theme.danger_soft}; }}
.linked-node-comparison {{ fill: {theme.warning}; }}
.linked-node-value {{ font-size: 14px; font-family: sans-serif; fill: {theme.text}; }}
.linked-node-pointer-dot {{ fill: {theme.text}; }}
.linked-pointer-label {{ font-size: 12px; font-family: sans-serif; font-weight: 600; }}
.linked-null-label {{ font-size: 12px; font-family: sans-serif; fill: {theme.muted}; }}
.linked-caption {{ font-size: 13px; font-family: sans-serif; fill: {theme.ink}; }}
"""

    @staticmethod
    def _arrow_markers(theme: DiagramTheme) -> str:
        return f"""
<marker id="linked-arrow" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
  <polygon points="0 0, 10 3.5, 0 7" fill="{theme.ink}"/>
</marker>
"""
