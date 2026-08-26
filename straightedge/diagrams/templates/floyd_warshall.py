"""Checked Floyd–Warshall dynamic-programming tables."""

from __future__ import annotations

from typing import Any, Dict, List

from ...graphs import GraphError, coerce_graph, floyd_warshall_steps
from ...qc import Finding
from ..registry import DIAGRAM_REGISTRY, register


MAX_VERTICES = 7


def _steps(params: Dict[str, Any]):
    graph = coerce_graph(params)
    if len(graph.ids) > MAX_VERTICES:
        raise GraphError(f"at most {MAX_VERTICES} vertices fit in a readable DP table")
    return floyd_warshall_steps(graph)


def _findings(params: Dict[str, Any]) -> List[Finding]:
    try:
        _steps(params)
    except GraphError as exc:
        witness = exc.witness
        if isinstance(witness, (list, tuple)):
            label = " → ".join(str(value) for value in witness)
        else:
            label = None if witness is None else str(witness)
        check = "floyd_warshall_negative_cycle" if "negative cycle" in str(exc) \
            else "floyd_warshall_input"
        return [Finding(check, "error", str(exc), label=label)]
    return []


def frames(params: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for step in _steps(params):
        highlights = {f"{row},{column}": "current"
                      for row, column in step.extras["changed"]}
        out.append({"label": step.label, "visual": {"type": "dp_table", "params": {
            "values": step.extras["values"],
            "row_labels": step.extras["labels"],
            "col_labels": step.extras["labels"],
            "highlights": highlights,
            "caption": ("direct edges" if step.extras["k"] is None
                        else f"k={step.extras['k']} · {len(step.extras['changed'])} changed"),
        }}})
    return out


@register("floyd_warshall")
class FloydWarshallTemplate:
    """Render one all-pairs distance table per permitted intermediate vertex."""

    motion = "optional"
    checks = ["directed weighted graph", "negative-cycle witness", "table size"]

    def refusal_findings(self, params: Dict[str, Any]) -> List[Finding]:
        return _findings(params)

    def render(self, params: Dict[str, Any]) -> str:
        params.get("nodes")
        params.get("edges")
        params.get("directed", True)
        params.get("animate", False)
        params.get("duration_s", 1.2)
        params.get("loop", True)
        params.get("columns", 3)
        params.get("title")
        if self.refusal_findings(params):
            return ""
        trace = frames(params)
        title = str(params.get("title", "Floyd–Warshall"))
        if bool(params.get("animate", False)):
            return DIAGRAM_REGISTRY["animated_trace"].render({
                "title": title, "frames": trace,
                "duration_s": float(params.get("duration_s", 1.2)),
                "loop": bool(params.get("loop", True)),
            })
        return DIAGRAM_REGISTRY["algorithm_trace"].render({
            "title": title, "steps": trace, "columns": int(params.get("columns", 3)),
            "show_step_numbers": True,
        })
