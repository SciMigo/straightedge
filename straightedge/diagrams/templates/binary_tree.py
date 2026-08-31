"""Binary tree visualization template for CS/data structure diagrams."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..registry import register
from ..renderer import (DEFAULT_STYLES, circle, defs, line, style, svg_document,
                        text, text_width)


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


@dataclass
class TreeNode:
    value: Any
    color: Optional[str] = None
    left: Optional["TreeNode"] = None
    right: Optional["TreeNode"] = None
    index: Optional[int] = None
    depth: int = 0
    x: float = 0
    y: float = 0


def _coerce_size(value: Any, default: float, minimum: float) -> float:
    """A finite pixel size from an author-supplied value, else ``default``.

    These knobs were ignored for years, so existing callers pass anything
    ("14px"); a value that cannot be read as a finite number falls back
    rather than failing the whole figure, and the floor keeps text legible.
    """
    try:
        size = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(size):
        return default
    return max(size, minimum)


def _normalize_highlights(highlights: Any) -> Dict[str, str]:
    if not isinstance(highlights, dict):
        return {}
    result: Dict[str, str] = {}
    for key, state in highlights.items():
        if not isinstance(state, str):
            continue
        result[str(key)] = state
    return result


def _build_tree_from_dict(data: Any, depth: int = 0) -> Optional[TreeNode]:
    if not isinstance(data, dict):
        return None
    value = data.get("value")
    color = data.get("color")
    node = TreeNode(
        value=value,
        color=str(color).lower() if color is not None else None,
        depth=depth,
    )
    node.left = _build_tree_from_dict(data.get("left"), depth + 1)
    node.right = _build_tree_from_dict(data.get("right"), depth + 1)
    return node


def _build_tree_from_array(values: List[Any]) -> Optional[TreeNode]:
    if not values:
        return None
    start_index = 1 if len(values) > 1 and values[0] is None else 0
    nodes: Dict[int, TreeNode] = {}
    for idx in range(start_index, len(values)):
        value = values[idx]
        if value is None:
            continue
        nodes[idx] = TreeNode(value=value, index=idx)

    for idx, node in nodes.items():
        left_idx = idx * 2
        right_idx = idx * 2 + 1
        node.left = nodes.get(left_idx)
        node.right = nodes.get(right_idx)

    return nodes.get(start_index)


def _assign_positions(root: Optional[TreeNode], spacing_x: int, spacing_y: int, padding: int) -> List[TreeNode]:
    nodes: List[TreeNode] = []
    current_index = 0

    def inorder(node: Optional[TreeNode], depth: int) -> None:
        nonlocal current_index
        if node is None:
            return
        inorder(node.left, depth + 1)
        node.depth = depth
        node.x = padding + current_index * spacing_x
        node.y = padding + depth * spacing_y
        nodes.append(node)
        current_index += 1
        inorder(node.right, depth + 1)

    inorder(root, 0)
    return nodes


@register("binary_tree")
class BinaryTreeTemplate:
    """Render a binary tree/BST/heap visualization."""

    def render(self, params: Dict[str, Any]) -> str:
        highlights = _normalize_highlights(params.get("highlights", {}))
        pointers = params.get("pointers", [])
        annotations = params.get("annotations", [])
        path_values = params.get("path", [])
        caption = params.get("caption")
        label_size = _coerce_size(params.get("label_size", params.get("font_size", 13)),
                                  default=13.0, minimum=8.0)
        caption_size = _coerce_size(params.get("caption_size", 13), default=13.0, minimum=8.0)
        caption_gap = _coerce_size(params.get("caption_gap", 20),
                                   default=20.0, minimum=0.0) if caption else 0.0
        show_null = bool(params.get("show_null", False))
        heap_mode = bool(params.get("heap_mode", False))

        root = None
        if heap_mode or "array" in params:
            array_values = params.get("array", [])
            if isinstance(array_values, list):
                root = _build_tree_from_array(array_values)
        if root is None:
            root = _build_tree_from_dict(params.get("root"))

        spacing_x = int(params.get("node_spacing_x", 70))
        spacing_y = int(params.get("node_spacing_y", 80))
        node_radius = int(params.get("node_radius", 18))
        note_half_width = 0.0
        if isinstance(annotations, list):
            note_half_width = max(
                (text_width(str(note.get("text", "")), 12) / 2
                 for note in annotations if isinstance(note, dict)),
                default=0.0,
            )
        padding = max(30, node_radius + 44 if annotations else 30,
                      int(math.ceil(note_half_width + 4)))

        nodes = _assign_positions(root, spacing_x, spacing_y, padding)

        if not nodes:
            return svg_document("", 200, 120)

        max_x = max(node.x for node in nodes)
        max_y = max(node.y for node in nodes)
        svg_width = max_x + padding + node_radius
        svg_height = max_y + padding + node_radius + caption_gap
        if caption:
            # A one-node tree is 78px wide; "Red-black tree" beneath it is not.
            # Widen the canvas to the caption and keep the tree centred in it.
            caption_width = text_width(str(caption), caption_size, safe=True) + 16.0
            if caption_width > svg_width:
                shift = (caption_width - svg_width) / 2
                for node in nodes:
                    node.x += shift
                svg_width = caption_width

        elements: List[str] = []
        elements.append(style(DEFAULT_STYLES + self._extra_styles(label_size, caption_size)))
        elements.append(defs(self._arrow_marker()))

        node_lookup_by_value: Dict[str, TreeNode] = {str(node.value): node for node in nodes}
        node_lookup_by_index: Dict[str, TreeNode] = {
            str(node.index): node for node in nodes if node.index is not None
        }

        path_edges = set()
        if isinstance(path_values, list):
            for start, end in zip(path_values, path_values[1:]):
                path_edges.add((str(start), str(end)))
                path_edges.add((str(end), str(start)))

        # Draw edges
        for node in nodes:
            for child in (node.left, node.right):
                if child is None:
                    continue
                edge_class = "tree-edge"
                if (str(node.value), str(child.value)) in path_edges:
                    edge_class = "tree-edge tree-edge-path"
                elements.append(
                    line(
                        node.x,
                        node.y,
                        child.x,
                        child.y,
                        stroke="#555",
                        stroke_width="2",
                        **{"class": edge_class},
                    )
                )
                if show_null:
                    continue

        # Draw nodes
        for node in nodes:
            state = "default"
            if heap_mode and node.index is not None:
                state = highlights.get(str(node.index), state)
            state = highlights.get(str(node.value), state)
            node_class = f"tree-node tree-node-{state}"
            if node.color in {"red", "black"}:
                node_class += f" tree-node-color-{node.color}"
            elements.append(circle(node.x, node.y, node_radius, **{"class": node_class}))
            label_class = "tree-node-value"
            if node.color in {"red", "black"}:
                label_class += " tree-node-value-inverse"
            elements.append(
                text(
                    node.x,
                    node.y + 5,
                    str(node.value),
                    **{"class": label_class, "text_anchor": "middle"},
                )
            )

        # Pointers
        if isinstance(pointers, list):
            for pointer in pointers:
                if not isinstance(pointer, dict):
                    continue
                label = str(pointer.get("label", ""))
                color = pointer.get("color", "#2196F3")
                target = None
                if heap_mode and "index" in pointer:
                    target = node_lookup_by_index.get(str(pointer.get("index")))
                if target is None:
                    target = node_lookup_by_value.get(str(pointer.get("value")))
                if target is None:
                    continue
                line_start_y = target.y - node_radius - 18
                elements.append(
                    line(
                        target.x,
                        line_start_y,
                        target.x,
                        target.y - node_radius,
                        stroke=color,
                        stroke_width="2",
                        marker_end="url(#tree-arrow)",
                        **{"class": "tree-pointer"},
                    )
                )
                if label:
                    elements.append(
                        text(
                            target.x,
                            line_start_y - 5,
                            label,
                            **{"class": "tree-pointer-label", "text_anchor": "middle", "fill": color},
                        )
                    )

        # Annotations
        if isinstance(annotations, list):
            for annotation in annotations:
                if not isinstance(annotation, dict):
                    continue
                note = str(annotation.get("text", ""))
                target = node_lookup_by_value.get(str(annotation.get("value")))
                if target is None:
                    continue
                note_y = target.y - node_radius - 30
                elements.append(
                    line(
                        target.x,
                        note_y + 8,
                        target.x,
                        target.y - node_radius,
                        stroke="#666",
                        stroke_width="1",
                        stroke_dasharray="4,2",
                    )
                )
                if note:
                    elements.append(
                        text(
                            target.x,
                            note_y,
                            note,
                            **{"class": "tree-annotation", "text_anchor": "middle"},
                        )
                    )

        if caption:
            elements.append(
                text(
                    svg_width / 2,
                    svg_height - 8,
                    str(caption),
                    **{"class": "tree-caption", "text_anchor": "middle",
                       "font_size": f"{caption_size:g}px"},
                )
            )

        return svg_document("\n".join(elements), int(svg_width), int(svg_height))

    @staticmethod
    def _extra_styles(label_size: float = 13.0, caption_size: float = 13.0) -> str:
        return """
.tree-node { stroke: #343a40; stroke-width: 1.5; fill: #f8f9fa; }
.tree-node-current { fill: #fff3cd; }
.tree-node-visited { fill: #d1ecf1; }
.tree-node-target { fill: #d4edda; }
.tree-node-found { fill: #d4edda; }
.tree-node-invalid { fill: #f8d7da; }
.tree-node-rejected { fill: #f8d7da; }
.tree-node-comparison { fill: #FF9800; }
.tree-node-color-red { fill: #c62828; stroke: #7f1d1d; }
.tree-node-color-black { fill: #20242a; stroke: #050608; }
.tree-node-value { font-family: sans-serif; fill: #212529; }
.tree-node-value-inverse { fill: #fff; font-weight: 600; }
.tree-edge { stroke: #555; }
.tree-edge-path { stroke: #9C27B0; stroke-width: 2.5; }
.tree-pointer-label { font-size: 12px; font-family: sans-serif; font-weight: 600; }
.tree-annotation { font-size: 12px; font-family: sans-serif; fill: #444; }
.tree-caption { font-family: sans-serif; fill: #333; }
""" + f"""
.tree-node-value {{ font-size: {label_size:g}px; }}
.tree-caption {{ font-size: {caption_size:g}px; }}
"""

    @staticmethod
    def _arrow_marker() -> str:
        return """
<marker id="tree-arrow" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
  <polygon points="0 0, 10 3.5, 0 7" fill="#333"/>
</marker>
"""
