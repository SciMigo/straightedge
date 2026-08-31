"""Checked min-priority-queue traces rendered as binary heaps."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple

from ...graphs import GraphError
from ...qc import Finding
from ..registry import DIAGRAM_REGISTRY, register


def _priority(value: Any) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        raise GraphError("priority must be a finite number")
    return float(value)


def _compute(params: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw = params.get("items", [])
    operations = params.get("operations", [])
    if not isinstance(raw, list) or not isinstance(operations, list):
        raise GraphError("items and operations must be arrays")
    if str(params.get("view", "heap")).strip().lower() not in {"heap", "sorted"}:
        raise GraphError("view must be heap or sorted")
    limit = 23 if params.get("animate", True) else 11
    if len(operations) + 1 > limit:
        raise GraphError(f"at most {limit} heap states fit this trace")
    if len(raw) + sum(1 for op in operations if isinstance(op, dict) and op.get("type") == "insert") > 15:
        raise GraphError("at most 15 heap items fit one readable trace")
    heap: List[Tuple[float, int, str]] = []
    serial = 0
    seen: set[str] = set()
    states: List[Dict[str, Any]] = []

    def sift_up(i: int) -> None:
        while i:
            p = (i - 1) // 2
            if heap[p] <= heap[i]: break
            heap[p], heap[i] = heap[i], heap[p]; i = p

    def sift_down(i: int) -> None:
        while 2 * i + 1 < len(heap):
            child = 2 * i + 1
            if child + 1 < len(heap) and heap[child + 1] < heap[child]: child += 1
            if heap[i] <= heap[child]: break
            heap[i], heap[child] = heap[child], heap[i]; i = child

    def insert(item: Dict[str, Any]) -> str:
        nonlocal serial
        if not isinstance(item, dict) or item.get("id") is None:
            raise GraphError("each item needs id and priority")
        item_id = str(item["id"])
        if item_id in seen: raise GraphError(f"priority-queue id {item_id!r} is repeated")
        priority = _priority(item.get("priority")); seen.add(item_id)
        heap.append((priority, serial, item_id)); serial += 1; sift_up(len(heap) - 1)
        return item_id

    def snapshot(label: str, current: str | None = None) -> None:
        states.append({"label": label, "heap": list(heap), "current": current})

    for item in raw: insert(item)
    snapshot("Build min-heap")
    for index, operation in enumerate(operations):
        if not isinstance(operation, dict): raise GraphError(f"operation {index + 1} must be an object")
        kind = str(operation.get("type", "")).strip().lower()
        if kind == "insert":
            item_id = insert(operation); snapshot(f"insert({item_id})", item_id)
        elif kind == "decrease_key":
            item_id = str(operation.get("id")); new = _priority(operation.get("priority"))
            pos = next((i for i, entry in enumerate(heap) if entry[2] == item_id), None)
            if pos is None: raise GraphError(f"decrease_key names unknown item {item_id!r}")
            if new > heap[pos][0]: raise GraphError("decrease_key cannot increase a priority")
            heap[pos] = (new, heap[pos][1], item_id); sift_up(pos)
            snapshot(f"decrease_key({item_id}, {new:g})", item_id)
        elif kind == "pop_min":
            if not heap: raise GraphError("cannot pop_min from an empty queue")
            minimum = heap[0]
            expected = operation.get("expect")
            if expected is not None and str(expected) != minimum[2]:
                raise GraphError(f"minimum is {minimum[2]!r}, not {expected!r}", witness=minimum[2])
            last = heap.pop()
            if heap: heap[0] = last; sift_down(0)
            seen.remove(minimum[2]); snapshot(f"pop_min() → {minimum[2]}", minimum[2])
        else:
            raise GraphError("operation.type must be insert, decrease_key, or pop_min")
    return states


def _tree(heap: List[Tuple[float, int, str]], index: int = 0) -> Dict[str, Any] | None:
    if index >= len(heap): return None
    priority, _, item_id = heap[index]
    node: Dict[str, Any] = {"value": f"{item_id} · {priority:g}"}
    left, right = _tree(heap, 2 * index + 1), _tree(heap, 2 * index + 2)
    if left is not None: node["left"] = left
    if right is not None: node["right"] = right
    return node


@register("priority_queue")
class PriorityQueueTemplate:
    """Compute insert, decrease-key, and pop-min transitions in a binary heap."""

    motion = "optional"
    checks = ["unique item ids", "finite priorities", "min-heap ordering",
              "decrease-key direction", "optional popped minimum"]

    def refusal_findings(self, params: Dict[str, Any]) -> List[Finding]:
        try: _compute(params)
        except GraphError as exc:
            return [Finding("priority_queue_refused", "error", str(exc),
                            label=str(exc.witness) if exc.witness is not None else None)]
        return []

    def render(self, params: Dict[str, Any]) -> str:
        items, operations = params.get("items", []), params.get("operations", [])
        animate = bool(params.get("animate", True)); duration_s = float(params.get("duration_s", 1.2))
        loop = bool(params.get("loop", False)); title = params.get("title", "Min-priority queue")
        # The heap tree with its true array order stays the documented
        # default; "sorted" is an opt-in view, and its panel says sorted
        # rather than passing a fully sorted array off as the heap's layout.
        columns = int(params.get("columns", 3))
        view = str(params.get("view", "heap")).strip().lower()
        _ = (items, operations)
        try:
            states = _compute(params)
        except GraphError:
            return ""
        frames = []
        for state in states:
            if state["heap"] and view == "heap":
                values = [f"{item_id}:{priority:g}" for priority, _, item_id in state["heap"]]
                visual = {"type": "binary_tree", "params": {
                    "root": _tree(state["heap"]),
                    "caption": "heap array: [" + ", ".join(values) + "]"}}
            elif state["heap"]:
                ordered = sorted(state["heap"])
                values = [f"({priority:g}, {item_id})" for priority, _, item_id in ordered]
                current = state.get("current")
                highlights = {
                    str(index): ("current" if item_id == current else "found")
                    for index, (_, _, item_id) in enumerate(ordered)
                    if index == 0 or item_id == current
                }
                visual = {"type": "array_state", "params": {
                    "values": values, "highlights": highlights,
                    "pointers": [{"index": 0, "label": "min", "position": "above"}]}}
            else:
                # One cell is 90px wide; the caption must fit inside it or
                # the animated lane refuses the frame as clipped.
                visual = {"type": "array_state", "params": {
                    "values": ["∅"], "cell_width": 160, "caption": "heap array: []"}}
            frames.append({"label": state["label"], "visual": visual})
        if animate:
            return DIAGRAM_REGISTRY["animated_trace"].render({"title": str(title), "frames": frames,
                                                               "duration_s": duration_s, "loop": loop})
        return DIAGRAM_REGISTRY["algorithm_trace"].render({"title": str(title), "steps": frames,
                                                            "columns": columns, "show_step_numbers": True})
