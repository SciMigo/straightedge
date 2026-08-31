"""Deterministic checked Turán graph builder."""

from __future__ import annotations

from typing import Any, Dict, List

from ...graphs import GraphError, turan_graph, validate_turan_parameters
from ...qc import Finding
from ..registry import DIAGRAM_REGISTRY, register


MAX_VERTICES = 11


def _computed(params: Dict[str, Any]):
    n, r = validate_turan_parameters(params.get("n"), params.get("r"))
    if n > MAX_VERTICES:
        raise GraphError(f"T({n},{r}) has {n} vertices; "
                         f"at most {MAX_VERTICES} fit", witness=n)
    graph, parts = turan_graph(n, r)
    return graph, parts


def _findings(params: Dict[str, Any]) -> List[Finding]:
    try:
        _computed(params)
    except GraphError as exc:
        witness = exc.witness
        label = (", ".join(str(value) for value in witness)
                 if isinstance(witness, (list, tuple)) else
                 None if witness is None else str(witness))
        return [Finding("turan_input", "error", str(exc), label=label)]
    return []


def graph_params(params: Dict[str, Any]) -> Dict[str, Any]:
    graph, parts = _computed(params)
    width = int(params.get("width", 700))
    height = int(params.get("height", 380))
    padding_x, padding_y = 70, 75
    nodes = []
    for part_index, part in enumerate(parts):
        x = width / 2 if len(parts) == 1 else (
            padding_x + part_index * (width - 2 * padding_x) / (len(parts) - 1))
        for member_index, vertex in enumerate(part):
            y = height / 2 if len(part) == 1 else (
                padding_y + member_index * (height - 2 * padding_y) / (len(part) - 1))
            nodes.append({"id": vertex, "x": x, "y": y})
    sizes = ", ".join(str(len(part)) for part in parts)
    caption = (f"T_{{{len(graph.ids)},{len(parts)}}}: parts {sizes}; "
               f"{len(graph.edges)} edges; no K_{len(parts) + 1}")
    if not bool(params.get("highlight_clique_free", True)):
        caption = f"T_{{{len(graph.ids)},{len(parts)}}}: {len(graph.edges)} edges"
    return {
        "nodes": nodes,
        "edges": [{"from": edge.source, "to": edge.target} for edge in graph.edges],
        "layout": "custom", "width": width, "height": height,
        "node_radius": int(params.get("node_radius", 18)), "caption": caption,
        "highlights": {"nodes": {
            vertex: f"color-{index + 1}" for index, part in enumerate(parts)
            for vertex in part}},
    }


@register("turan")
class TuranTemplate:
    """Build and draw ``T(n,r)`` from its two integer parameters."""

    motion = "none"
    checks = ["positive n", "1 <= r <= n", "balanced parts",
              "complete cross-part edges", "11-vertex figure cap"]

    def refusal_findings(self, params: Dict[str, Any]) -> List[Finding]:
        return _findings(params)

    def render(self, params: Dict[str, Any]) -> str:
        params.get("n")
        params.get("r")
        params.get("highlight_clique_free", True)
        params.get("width", 700)
        params.get("height", 380)
        params.get("node_radius", 18)
        if self.refusal_findings(params):
            return ""
        return DIAGRAM_REGISTRY["graph"].render(graph_params(params))
