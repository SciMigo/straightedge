"""Checked binary-search, AVL, and red-black trees with insertion animation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from ...qc import Finding
from ..registry import DIAGRAM_REGISTRY, register


@dataclass
class _Node:
    value: Any
    left: "_Node | None" = None
    right: "_Node | None" = None
    color: str = "black"
    height: int = 1


def _height(node: _Node | None) -> int:
    return node.height if node else 0


def _refresh(node: _Node) -> _Node:
    node.height = 1 + max(_height(node.left), _height(node.right))
    return node


def _rotate_left(node: _Node) -> _Node:
    child = node.right
    if child is None:
        return node
    node.right, child.left = child.left, node
    _refresh(node)
    return _refresh(child)


def _rotate_right(node: _Node) -> _Node:
    child = node.left
    if child is None:
        return node
    node.left, child.right = child.right, node
    _refresh(node)
    return _refresh(child)


def _insert_bst(node: _Node | None, value: Any) -> _Node:
    if node is None:
        return _Node(value)
    if value < node.value:
        node.left = _insert_bst(node.left, value)
    elif value > node.value:
        node.right = _insert_bst(node.right, value)
    else:
        raise ValueError(f"duplicate key {value!r}")
    return _refresh(node)


def _insert_avl(node: _Node | None, value: Any) -> _Node:
    if node is None:
        return _Node(value)
    if value < node.value:
        node.left = _insert_avl(node.left, value)
    elif value > node.value:
        node.right = _insert_avl(node.right, value)
    else:
        raise ValueError(f"duplicate key {value!r}")
    _refresh(node)
    balance = _height(node.left) - _height(node.right)
    if balance > 1:
        if value > node.left.value:  # type: ignore[union-attr]
            node.left = _rotate_left(node.left)  # type: ignore[arg-type]
        return _rotate_right(node)
    if balance < -1:
        if value < node.right.value:  # type: ignore[union-attr]
            node.right = _rotate_right(node.right)  # type: ignore[arg-type]
        return _rotate_left(node)
    return node


def _red(node: _Node | None) -> bool:
    return bool(node and node.color == "red")


def _rb_rotate_left(node: _Node) -> _Node:
    child = _rotate_left(node)
    child.color, child.left.color = child.left.color, "red"  # type: ignore[union-attr]
    return child


def _rb_rotate_right(node: _Node) -> _Node:
    child = _rotate_right(node)
    child.color, child.right.color = child.right.color, "red"  # type: ignore[union-attr]
    return child


def _flip_colors(node: _Node) -> None:
    node.color = "red" if node.color == "black" else "black"
    for child in (node.left, node.right):
        if child:
            child.color = "red" if child.color == "black" else "black"


def _insert_red_black(node: _Node | None, value: Any) -> _Node:
    if node is None:
        return _Node(value, color="red")
    if value < node.value:
        node.left = _insert_red_black(node.left, value)
    elif value > node.value:
        node.right = _insert_red_black(node.right, value)
    else:
        raise ValueError(f"duplicate key {value!r}")
    if _red(node.right) and not _red(node.left):
        node = _rb_rotate_left(node)
    if _red(node.left) and _red(node.left.left if node.left else None):
        node = _rb_rotate_right(node)
    if _red(node.left) and _red(node.right):
        _flip_colors(node)
    return _refresh(node)


def _parse(data: Any) -> _Node | None:
    if data is None:
        return None
    if not isinstance(data, dict) or "value" not in data:
        raise ValueError("every tree node must be an object with a value")
    color = str(data.get("color", "black")).lower()
    node = _Node(data["value"], color=color)
    node.left, node.right = _parse(data.get("left")), _parse(data.get("right"))
    return _refresh(node)


def _as_dict(node: _Node | None, *, include_color: bool = True) -> Dict[str, Any] | None:
    if node is None:
        return None
    result: Dict[str, Any] = {"value": node.value}
    if include_color:
        result["color"] = node.color
    if node.left is not None:
        result["left"] = _as_dict(node.left, include_color=include_color)
    if node.right is not None:
        result["right"] = _as_dict(node.right, include_color=include_color)
    return result


def _bst_error(node: _Node | None, low: Any = None, high: Any = None) -> str | None:
    if node is None:
        return None
    try:
        if low is not None and not node.value > low:
            return f"key {node.value!r} is not greater than lower bound {low!r}"
        if high is not None and not node.value < high:
            return f"key {node.value!r} is not less than upper bound {high!r}"
    except TypeError:
        return "tree keys must be mutually comparable"
    return _bst_error(node.left, low, node.value) or _bst_error(node.right, node.value, high)


def _avl_check(node: _Node | None) -> Tuple[int, str | None]:
    if node is None:
        return 0, None
    left_h, error = _avl_check(node.left)
    if error:
        return 0, error
    right_h, error = _avl_check(node.right)
    if error:
        return 0, error
    if abs(left_h - right_h) > 1:
        return 0, f"key {node.value!r} has balance factor {left_h - right_h}"
    return 1 + max(left_h, right_h), None


def _rb_check(node: _Node | None) -> Tuple[int, str | None]:
    if node is None:
        return 1, None
    if node.color not in {"red", "black"}:
        return 0, f"key {node.value!r} has color {node.color!r}, not red or black"
    if node.color == "red" and (_red(node.left) or _red(node.right)):
        return 0, f"red key {node.value!r} has a red child"
    left_bh, error = _rb_check(node.left)
    if error:
        return 0, error
    right_bh, error = _rb_check(node.right)
    if error:
        return 0, error
    if left_bh != right_bh:
        return 0, f"key {node.value!r} has black-heights {left_bh} and {right_bh}"
    return left_bh + (1 if node.color == "black" else 0), None


def _annotations(node: _Node | None) -> List[Dict[str, Any]]:
    if node is None:
        return []
    balance = _height(node.left) - _height(node.right)
    return ([{"value": node.value, "text": f"h={node.height}, bf={balance:+d}"}]
            + _annotations(node.left) + _annotations(node.right))


def _prepare(params: Dict[str, Any]) -> Tuple[List[Finding], _Node | None, List[Dict[str, Any]]]:
    raw_kind = str(params.get("kind", "bst")).strip().lower().replace("-", "_")
    kind = "avl" if raw_kind in {"balanced", "balanced_bst"} else raw_kind
    if kind not in {"bst", "avl", "red_black"}:
        return [Finding(
            "search_tree_kind", "error", "kind must be bst, avl, or red_black"
        )], None, []
    values = params.get("values")
    states: List[Dict[str, Any]] = []
    root: _Node | None = None
    if values is not None:
        if not isinstance(values, list) or not values:
            return [Finding(
                "search_tree_values", "error", "values must be a non-empty array"
            )], None, []
        insert = {"bst": _insert_bst, "avl": _insert_avl, "red_black": _insert_red_black}[kind]
        try:
            for value in values:
                root = insert(root, value)
                if kind == "red_black":
                    root.color = "black"
                states.append(_as_dict(root, include_color=kind == "red_black") or {})
        except (TypeError, ValueError) as exc:
            return [Finding("search_tree_values", "error", str(exc))], None, []
    else:
        try:
            root = _parse(params.get("root"))
        except ValueError as exc:
            return [Finding("search_tree_shape", "error", str(exc))], None, []
        if root is None:
            return [Finding(
                "search_tree_shape", "error", "provide root or insertion values"
            )], None, []

    error = _bst_error(root)
    if error:
        return [Finding("bst_order", "error", error)], root, states
    if kind == "avl":
        _, error = _avl_check(root)
        if error:
            return [Finding("avl_balance", "error", error)], root, states
    if kind == "red_black":
        if root and root.color != "black":
            return [Finding("red_black_root", "error", "the root must be black")], root, states
        _, error = _rb_check(root)
        if error:
            return [Finding("red_black_invariant", "error", error)], root, states
    return [], root, states


#: How each kind is named in a caption; the identifier is not a title.
KIND_NAMES = {"bst": "BST", "avl": "AVL", "red_black": "Red-black"}


@register("search_tree")
class SearchTreeTemplate:
    """Construct or verify BST, AVL, and red-black trees, optionally animated."""

    motion = "optional"
    checks = ["strict BST order", "AVL balance", "red-black invariants"]

    def refusal_findings(self, params: Dict[str, Any]) -> List[Finding]:
        animate = params.get("animate", False)
        if animate and params.get("values") is None:
            return [Finding(
                "search_tree_animation", "error", "animation requires insertion values"
            )]
        duration = params.get("duration_s", 1.2)
        if (not isinstance(duration, (int, float)) or isinstance(duration, bool)
                or not math.isfinite(duration) or duration <= 0):
            return [Finding(
                "search_tree_animation", "error", "duration_s must be a positive number"
            )]
        findings, _, _ = _prepare(params)
        return findings

    def render(self, params: Dict[str, Any]) -> str:
        kind = str(params.get("kind", "bst")).strip().lower().replace("-", "_")
        values = params.get("values")
        animate = bool(params.get("animate", False))
        duration = float(params.get("duration_s", 1.2))
        loop = bool(params.get("loop", False))
        show_balance = bool(params.get("show_balance", kind in {"avl", "balanced"}))
        caption = params.get("caption")
        node_radius = int(params.get("node_radius", 18))
        spacing_x = int(params.get("node_spacing_x", 70))
        spacing_y = int(params.get("node_spacing_y", 80))
        findings, root, states = _prepare(params)
        if findings or root is None:
            return ""

        canonical_kind = "avl" if kind in {"balanced", "balanced_bst"} else kind
        if animate:
            frames = []
            source_values = values if isinstance(values, list) else []
            for index, state in enumerate(states):
                frames.append({
                    "label": f"insert {source_values[index]}",
                    "visual": {"type": "search_tree", "params": {
                        "kind": canonical_kind,
                        "root": state,
                        "show_balance": show_balance,
                        "node_radius": node_radius,
                        "node_spacing_x": spacing_x,
                        "node_spacing_y": spacing_y,
                    }},
                })
            return DIAGRAM_REGISTRY["animated_trace"].render({
                "title": caption or f"{KIND_NAMES[canonical_kind]} insertion",
                "frames": frames,
                "duration_s": duration,
                "loop": loop,
            })

        tree_params: Dict[str, Any] = {
            "root": _as_dict(root, include_color=canonical_kind == "red_black"),
            "node_radius": node_radius,
            "node_spacing_x": spacing_x,
            "node_spacing_y": spacing_y,
            "caption": caption or f"{KIND_NAMES[canonical_kind]} tree",
        }
        if show_balance:
            tree_params["annotations"] = _annotations(root)
        return DIAGRAM_REGISTRY["binary_tree"].render(tree_params)
