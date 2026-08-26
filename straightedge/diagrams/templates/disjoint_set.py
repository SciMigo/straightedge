"""Checked union-find traces for Kruskal and dynamic connectivity lessons."""

from __future__ import annotations

from typing import Any, Dict, List

from ...graphs import GraphError
from ...qc import Finding
from ..registry import DIAGRAM_REGISTRY, register


def _compute(params: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw = params.get("elements")
    if not isinstance(raw, list) or not raw:
        raise GraphError("elements must be a non-empty array")
    elements = [str(value) for value in raw]
    if len(elements) != len(set(elements)):
        raise GraphError("elements must be unique")
    if len(elements) > 11:
        raise GraphError("at most 11 elements fit one readable union-find trace")
    operations = params.get("operations", [])
    if not isinstance(operations, list):
        raise GraphError("operations must be an array")
    limit = 23 if bool(params.get("animate", True)) else 11
    if len(operations) > limit:
        raise GraphError(f"at most {limit} operations fit this trace")
    parent = {value: value for value in elements}
    rank = {value: 0 for value in elements}
    states: List[Dict[str, Any]] = []

    def root(value: str, compress: bool = True) -> str:
        trail = []
        while parent[value] != value:
            trail.append(value)
            value = parent[value]
        if compress:
            for item in trail:
                parent[item] = value
        return value

    def snapshot(label: str, current: List[str]) -> None:
        roots = {value: root(value, False) for value in elements}
        states.append({"label": label, "parent": dict(parent), "roots": roots,
                       "rank": dict(rank), "current": list(current)})

    snapshot("Singleton sets", [])
    for index, operation in enumerate(operations):
        if not isinstance(operation, dict):
            raise GraphError(f"operation {index + 1} must be an object")
        kind = str(operation.get("type", "")).strip().lower()
        if kind == "union":
            a, b = str(operation.get("a")), str(operation.get("b"))
            if a not in parent or b not in parent:
                raise GraphError(f"union names an unknown element", witness=(a, b))
            ra, rb = root(a), root(b)
            if ra != rb:
                if rank[ra] < rank[rb]:
                    ra, rb = rb, ra
                parent[rb] = ra
                if rank[ra] == rank[rb]:
                    rank[ra] += 1
            snapshot(f"union({a}, {b})", [a, b, ra])
        elif kind == "find":
            value = str(operation.get("element"))
            if value not in parent:
                raise GraphError(f"find names unknown element {value!r}", witness=value)
            representative = root(value)
            expected = operation.get("expect")
            if expected is not None and str(expected) != representative:
                raise GraphError(f"find({value}) is {representative!r}, not {expected!r}",
                                 witness=representative)
            snapshot(f"find({value}) = {representative}", [value, representative])
        else:
            raise GraphError("operation.type must be union or find")
    return states


def _frames(params: Dict[str, Any], states: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    elements = [str(value) for value in params["elements"]]
    n = max(1, len(elements) - 1)
    frames = []
    for state in states:
        depths = {}
        for value in elements:
            depth, cursor = 0, value
            while state["parent"][cursor] != cursor:
                depth += 1; cursor = state["parent"][cursor]
            depths[value] = depth
        max_depth = max(depths.values(), default=0)
        nodes = [{"id": value, "label": value, "x": 0.08 + 0.84 * i / n,
                  "y": 0.2 + (0.58 * depths[value] / max(max_depth, 1))}
                 for i, value in enumerate(elements)]
        edges = [{"from": value, "to": parent} for value, parent in state["parent"].items()
                 if value != parent]
        highlights = {value: "current" for value in state["current"]}
        highlights.update({value: "found" for value in elements
                           if state["parent"][value] == value})
        groups = len(set(state["roots"].values()))
        graph_params = {"nodes": nodes, "edges": edges, "directed": True,
                        "layout": "custom", "width": int(params.get("width", 680)),
                        "height": int(params.get("height", 360)),
                        "highlights": {"nodes": highlights},
                        "distance_labels": {v: f"rank {state['rank'][v]}" for v in elements
                                            if state["parent"][v] == v},
                        "caption": f"{groups} set(s) · parent pointers point to representatives"}
        frames.append({"label": state["label"], "visual": {"type": "graph", "params": graph_params}})
    return frames


@register("disjoint_set")
class DisjointSetTemplate:
    """Compute union-by-rank and path-compression states."""

    motion = "optional"
    checks = ["unique elements", "known operation operands", "union-by-rank",
              "path compression", "optional find result"]

    def refusal_findings(self, params: Dict[str, Any]) -> List[Finding]:
        try:
            _compute(params)
        except GraphError as exc:
            return [Finding("disjoint_set_refused", "error", str(exc),
                            label=str(exc.witness) if exc.witness is not None else None)]
        return []

    def render(self, params: Dict[str, Any]) -> str:
        elements = params.get("elements", [])
        operations = params.get("operations", [])
        animate = bool(params.get("animate", True))
        duration_s = float(params.get("duration_s", 1.2))
        loop = bool(params.get("loop", False))
        title = params.get("title", "Disjoint-set union")
        columns = int(params.get("columns", 3))
        params.get("width", 680); params.get("height", 360)
        _ = (elements, operations)
        if self.refusal_findings(params): return ""
        frames = _frames(params, _compute(params))
        if animate:
            return DIAGRAM_REGISTRY["animated_trace"].render({
                "title": str(title), "frames": frames, "duration_s": duration_s, "loop": loop})
        return DIAGRAM_REGISTRY["algorithm_trace"].render({
            "title": str(title), "steps": frames, "columns": columns, "show_step_numbers": True})
