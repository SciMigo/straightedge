"""Checked Mycielski graph construction and coloring trace."""

from __future__ import annotations

import math
from typing import Any, Dict, List

from ...graphs import GraphError, coerce_graph, mycielski_graph, mycielski_steps
from ...qc import Finding
from ..registry import DIAGRAM_REGISTRY, register
from .graph_algorithm import frames_from_steps


def _computed(params: Dict[str, Any]):
    base = coerce_graph(params)
    return mycielski_graph(base), mycielski_steps(base)


def _findings(params: Dict[str, Any]) -> List[Finding]:
    try:
        _computed(params)
    except GraphError as exc:
        witness = exc.witness
        label = ("→".join(str(value) for value in witness)
                 if isinstance(witness, (list, tuple)) else
                 None if witness is None else str(witness))
        return [Finding("mycielski_input", "error", str(exc), label=label)]
    return []


def _params(graph, params: Dict[str, Any]) -> Dict[str, Any]:
    n = (len(graph.ids) - 1) // 2
    nodes = []
    for i in range(n):
        angle = 2 * math.pi * i / n - math.pi / 2
        nodes.append({"id": f"u{i}", "x": 0.5 + 0.22 * math.cos(angle),
                      "y": 0.55 + 0.22 * math.sin(angle)})
        nodes.append({"id": f"v{i}", "x": 0.5 + 0.38 * math.cos(angle),
                      "y": 0.55 + 0.38 * math.sin(angle)})
    nodes.append({"id": "w", "x": 0.5, "y": 0.55})
    return {"algorithm": "greedy_coloring", "nodes": nodes,
            "edges": [{"from": edge.source, "to": edge.target} for edge in graph.edges],
            "graph_layout": "custom", "node_radius": int(params.get("node_radius", 17)),
            "width": int(params.get("width", 600)), "height": int(params.get("height", 380))}


def frames(params: Dict[str, Any]) -> List[Dict[str, Any]]:
    graph, steps = _computed(params)
    return frames_from_steps(_params(graph, params), steps)


@register("mycielski")
class MycielskiTemplate:
    """Construct M(G), prove its size, and expose a checked coloring."""

    motion = "optional"
    checks = ["undirected base graph", "11-vertex output cap",
              "computed chromatic numbers", "triangle-freeness"]

    def refusal_findings(self, params: Dict[str, Any]) -> List[Finding]:
        return _findings(params)

    def render(self, params: Dict[str, Any]) -> str:
        params.get("nodes")
        params.get("edges")
        params.get("animate", False)
        params.get("duration_s", 1.2)
        params.get("loop", True)
        params.get("columns", 3)
        params.get("title")
        params.get("node_radius", 17)
        params.get("width", 600)
        params.get("height", 380)
        # One _computed call per render: each one runs the exact chromatic
        # searches, so recomputing for the frames doubles the expensive part.
        try:
            graph, steps = _computed(params)
        except GraphError:
            return ""
        trace = frames_from_steps(_params(graph, params), steps)
        title = str(params.get("title", "Mycielski construction"))
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
