"""One graph computed into four synchronized representations."""

from __future__ import annotations

from typing import Any, Dict, List

from ...graphs import GraphError, coerce_graph
from ...qc import Finding
from ..registry import DIAGRAM_REGISTRY, register


@register("graph_representation")
class GraphRepresentationTemplate:
    """Draw a graph, adjacency list, adjacency matrix, and incidence matrix."""

    checks = ["known endpoints", "simple graph", "matrix/list agreement", "direction convention"]

    def refusal_findings(self, params: Dict[str, Any]) -> List[Finding]:
        try:
            graph = coerce_graph(params)
            if len(graph.ids) > 6 or len(graph.edges) > 8:
                raise GraphError("at most 6 vertices and 8 edges fit all four representations")
        except GraphError as exc:
            return [Finding("graph_representation_refused", "error", str(exc))]
        return []

    def render(self, params: Dict[str, Any]) -> str:
        params.get("nodes", []); params.get("edges", []); params.get("directed", False)
        layout = str(params.get("graph_layout", "circular")); title = params.get("title", "Equivalent graph representations")
        columns = int(params.get("columns", 2))
        if self.refusal_findings(params): return ""
        graph = coerce_graph(params); ids = list(graph.ids); n = len(ids)
        adjacency = [[0 for _ in ids] for _ in ids]
        for edge in graph.edges:
            i, j = ids.index(edge.source), ids.index(edge.target)
            value: Any = edge.weight if edge.weight is not None else 1
            adjacency[i][j] = value
            if not graph.directed: adjacency[j][i] = value
        incidence = [[0 for _ in graph.edges] for _ in ids]
        for j, edge in enumerate(graph.edges):
            incidence[ids.index(edge.source)][j] = -1 if graph.directed else 1
            incidence[ids.index(edge.target)][j] = 1
        adjacency_list = []
        for vertex in ids:
            entries = []
            for neighbor in graph.neighbors(vertex):
                weight = graph.weight(vertex, neighbor)
                edge = next(edge for edge in graph.edges
                            if (edge.source, edge.target) == (vertex, neighbor)
                            or (not graph.directed
                                and (edge.source, edge.target) == (neighbor, vertex)))
                entries.append(f"{neighbor} ({weight:g})" if edge.weight is not None else neighbor)
            adjacency_list.append([", ".join(entries) or "∅"])
        steps: List[Dict[str, Any]] = [
            {"label": "Graph", "visual": {"type": "graph", "params": {
                "nodes": params["nodes"], "edges": params.get("edges", []),
                "directed": graph.directed, "weighted": any(e.weight is not None for e in graph.edges),
                "layout": layout, "caption": "The source structure"}}},
            {"label": "Adjacency list", "visual": {"type": "matrix_state", "params": {
                "values": adjacency_list, "row_labels": ids, "col_labels": ["neighbors"]}}},
            {"label": "Adjacency matrix", "visual": {"type": "matrix_state", "params": {
                "values": adjacency, "row_labels": ids, "col_labels": ids}}},
            {"label": "Incidence matrix", "visual": {"type": "matrix_state", "params": {
                "values": incidence, "row_labels": ids,
                "col_labels": [f"e{i + 1}" for i in range(len(graph.edges))]}}},
        ]
        return DIAGRAM_REGISTRY["algorithm_trace"].render({
            "title": str(title), "steps": steps, "columns": columns, "show_step_numbers": False})
