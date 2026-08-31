"""One graph computed into four synchronized representations."""

from __future__ import annotations

from typing import Any, Dict, List

from ...graphs import Graph, GraphError, coerce_graph
from ...qc import Finding
from ..registry import DIAGRAM_REGISTRY, register


def _graph_panel(params: Dict[str, Any], graph: Graph) -> Dict[str, Any]:
    """The ``graph`` call for the first panel, shared with the refusal check."""
    panel = {"nodes": params["nodes"], "edges": params.get("edges", []),
            "directed": graph.directed,
            "weighted": any(e.weight is not None for e in graph.edges),
            "layout": str(params.get("graph_layout", "circular")),
            "caption": "The source structure"}
    highlighted = _highlight_edge(params.get("highlight"))
    if highlighted:
        panel["highlights"] = {"edges": [list(highlighted)]}
    return panel


def _highlight_edge(value: Any) -> tuple[str, str] | None:
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return str(value[0]), str(value[1])
    if isinstance(value, dict) and "from" in value and "to" in value:
        return str(value["from"]), str(value["to"])
    return None


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
        highlighted = _highlight_edge(params.get("highlight"))
        if params.get("highlight") is not None and highlighted is None:
            return [Finding(
                "graph_representation_highlight", "error",
                "highlight must identify one edge as [from, to] or {from, to}",
            )]
        if highlighted and not any(
            (edge.source, edge.target) == highlighted
            or (not graph.directed and (edge.target, edge.source) == highlighted)
            for edge in graph.edges
        ):
            return [Finding(
                "graph_representation_highlight", "error",
                f"highlight {highlighted[0]!r}–{highlighted[1]!r} is not an edge",
            )]
        # The first panel forwards graph_layout; a layout the graph template
        # refuses (bipartite on an odd cycle) would otherwise come back as an
        # empty document with the reason lost.
        return DIAGRAM_REGISTRY["graph"].refusal_findings(_graph_panel(params, graph))

    def render(self, params: Dict[str, Any]) -> str:
        params.get("nodes", []); params.get("edges", []); params.get("directed", False)
        params.get("graph_layout", "circular"); title = params.get("title", "Equivalent graph representations")
        columns = int(params.get("columns", 2))
        if self.refusal_findings(params): return ""
        graph = coerce_graph(params); ids = list(graph.ids)
        highlighted = _highlight_edge(params.get("highlight"))
        weighted = any(e.weight is not None for e in graph.edges)
        # A weighted matrix marks absence with a dot: a 0 there would read as
        # a zero-weight edge, which the adjacency list would then contradict.
        absent: Any = "·" if weighted else 0
        adjacency = [[absent for _ in ids] for _ in ids]
        for edge in graph.edges:
            i, j = ids.index(edge.source), ids.index(edge.target)
            value: Any = f"{edge.weight:g}" if edge.weight is not None else 1
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
        adjacency_list_highlights: Dict[str, str] = {}
        adjacency_matrix_highlights: Dict[str, str] = {}
        incidence_highlights: Dict[str, str] = {}
        if highlighted:
            source, target = highlighted
            matches = [
                index for index, edge in enumerate(graph.edges)
                if (edge.source, edge.target) == highlighted
                or (not graph.directed and (edge.target, edge.source) == highlighted)
            ]
            if matches and source in ids and target in ids:
                adjacency_list_highlights[f"{ids.index(source)},0"] = "current"
                adjacency_matrix_highlights[f"{ids.index(source)},{ids.index(target)}"] = "current"
                if not graph.directed:
                    adjacency_list_highlights[f"{ids.index(target)},0"] = "current"
                    adjacency_matrix_highlights[f"{ids.index(target)},{ids.index(source)}"] = "current"
                edge_index = matches[0]
                incidence_highlights[f"{ids.index(source)},{edge_index}"] = "current"
                incidence_highlights[f"{ids.index(target)},{edge_index}"] = "current"
        steps: List[Dict[str, Any]] = [
            {"label": "Graph", "visual": {"type": "graph", "params": _graph_panel(params, graph)}},
            {"label": "Adjacency list", "visual": {"type": "matrix_state", "params": {
                "values": adjacency_list, "row_labels": ids, "col_labels": ["neighbors"],
                "highlights": adjacency_list_highlights}}},
            {"label": "Adjacency matrix", "visual": {"type": "matrix_state", "params": {
                "values": adjacency, "row_labels": ids, "col_labels": ids,
                "highlights": adjacency_matrix_highlights}}},
            {"label": "Incidence matrix", "visual": {"type": "matrix_state", "params": {
                "values": incidence, "row_labels": ids,
                "col_labels": [f"e{i + 1}" for i in range(len(graph.edges))],
                "highlights": incidence_highlights}}},
        ]
        return DIAGRAM_REGISTRY["algorithm_trace"].render({
            "title": str(title), "steps": steps, "columns": columns, "show_step_numbers": False})
