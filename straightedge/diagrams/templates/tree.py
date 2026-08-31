"""General rooted-tree visualization with arbitrary node arity."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from ...qc import Finding
from ..registry import register
from ..renderer import DEFAULT_STYLES, circle, line, style, svg_document, text, text_width
from .binary_tree import _coerce_size


@dataclass
class _Node:
    value: Any
    key: str
    children: List["_Node"] = field(default_factory=list)
    depth: int = 0
    x: float = 0.0
    y: float = 0.0


def _build(raw: Any, depth: int = 0) -> _Node | None:
    if not isinstance(raw, dict):
        return None
    value = raw.get("value")
    key = str(raw.get("id", value))
    children = raw.get("children", [])
    if not isinstance(children, list):
        children = []
    node = _Node(value, key, depth=depth)
    node.children = [child for item in children if (child := _build(item, depth + 1))]
    return node


def _layout(root: _Node, spacing_x: float, spacing_y: float, padding: float) -> List[_Node]:
    nodes: List[_Node] = []
    leaf_slot = 0

    def place(node: _Node) -> None:
        nonlocal leaf_slot
        for child in node.children:
            place(child)
        if node.children:
            node.x = sum(child.x for child in node.children) / len(node.children)
        else:
            node.x = padding + leaf_slot * spacing_x
            leaf_slot += 1
        node.y = padding + node.depth * spacing_y
        nodes.append(node)

    place(root)
    return nodes


@register("tree")
class TreeTemplate:
    """Render ``{value, children: [...]}`` with parents centred over children."""

    def refusal_findings(self, params: Dict[str, Any]) -> list[Finding]:
        """A malformed root is a shape mistake to report, not a blank figure."""
        if _build(params.get("root")) is None:
            return [Finding("tree_root", "error",
                            "root must be an object with value and optional children")]
        return []

    def render(self, params: Dict[str, Any]) -> str:
        root = _build(params.get("root"))
        if root is None:
            return ""
        spacing_x = _coerce_size(params.get("node_spacing_x", 72), default=72.0, minimum=1.0)
        spacing_y = _coerce_size(params.get("node_spacing_y", 80), default=80.0, minimum=1.0)
        radius = _coerce_size(params.get("node_radius", 18), default=18.0, minimum=1.0)
        padding = max(30.0, radius + 12.0)
        label_size = _coerce_size(params.get("label_size", params.get("font_size", 13)),
                                  default=13.0, minimum=8.0)
        caption_size = _coerce_size(params.get("caption_size", 13), default=13.0, minimum=8.0)
        caption = params.get("caption")
        caption_gap = _coerce_size(params.get("caption_gap", 30),
                                   default=30.0, minimum=0.0) if caption else 0.0
        highlights = params.get("highlights", {})
        highlights = highlights if isinstance(highlights, dict) else {}
        path_values = params.get("path", [])
        path_values = [str(value) for value in path_values] if isinstance(path_values, list) else []
        path_edges = set(zip(path_values, path_values[1:]))

        nodes = _layout(root, spacing_x, spacing_y, padding)
        min_x = min(node.x for node in nodes) - radius
        max_x = max(node.x for node in nodes) + radius
        max_y = max(node.y for node in nodes) + radius
        if caption:
            needed = text_width(str(caption), caption_size, safe=True) + 16
            if needed > max_x - min_x:
                extra = (needed - (max_x - min_x)) / 2
                min_x -= extra
                max_x += extra

        elements = [style(DEFAULT_STYLES + self._styles(label_size, caption_size))]
        for parent in nodes:
            for child in parent.children:
                state = " tree-edge-path" if (
                    (parent.key, child.key) in path_edges
                    or (str(parent.value), str(child.value)) in path_edges
                ) else ""
                elements.append(line(
                    parent.x, parent.y, child.x, child.y,
                    **{"class": f"tree-edge{state}"},
                ))
        for node in nodes:
            state = str(highlights.get(node.key, highlights.get(str(node.value), "default")))
            elements.append(circle(
                node.x, node.y, radius,
                **{"class": f"tree-node tree-node-{state}"},
            ))
            elements.append(text(
                node.x, node.y + label_size * 0.36, str(node.value),
                **{"class": "tree-node-value", "text_anchor": "middle"},
            ))
        if caption:
            elements.append(text(
                (min_x + max_x) / 2, max_y + caption_gap - 8, str(caption),
                **{"class": "tree-caption", "text_anchor": "middle"},
            ))
        margin = 12.0
        width = max_x - min_x + 2 * margin
        height = max_y - (padding - radius) + caption_gap + 2 * margin
        return svg_document(
            "\n".join(elements), round(width), round(height),
            viewbox=f"{min_x - margin:.1f} {padding - radius - margin:.1f} {width:.1f} {height:.1f}",
        )

    @staticmethod
    def _styles(label_size: float, caption_size: float) -> str:
        return f"""
.tree-node {{ stroke: #343a40; stroke-width: 1.5; fill: #f8f9fa; }}
.tree-node-current {{ fill: #fff3cd; }}
.tree-node-frontier {{ fill: #fff3cd; stroke: #B45309; stroke-dasharray: 4 2; }}
.tree-node-visited {{ fill: #d1ecf1; }}
.tree-node-settled {{ fill: #d4edda; stroke: #166534; stroke-width: 3; }}
.tree-node-target, .tree-node-found {{ fill: #d4edda; }}
.tree-node-value {{ font-size: {label_size:g}px; font-family: sans-serif; fill: #212529; }}
.tree-edge {{ stroke: #555; stroke-width: 2; }}
.tree-edge-path {{ stroke: #9C27B0; stroke-width: 3; }}
.tree-caption {{ font-size: {caption_size:g}px; font-family: sans-serif; fill: #333; }}
"""
