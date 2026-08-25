"""Checked BFS and DFS storyboards built from the general graph template."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from ...qc import Finding
from ..registry import DIAGRAM_REGISTRY, register


MAX_VISITS = 11  # plus the initial state = algorithm_trace's twelve panels


def _graph_parts(params: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    nodes = params.get("nodes", [])
    edges = params.get("edges", [])
    return (
        nodes if isinstance(nodes, list) else [],
        edges if isinstance(edges, list) else [],
    )


def _adjacency(
    node_ids: List[str],
    edges: List[Dict[str, Any]],
    directed: bool,
    neighbor_order: Any,
) -> Dict[str, List[str]]:
    adjacency: Dict[str, List[str]] = {node_id: [] for node_id in node_ids}
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        source, target = str(edge.get("from")), str(edge.get("to"))
        if source not in adjacency or target not in adjacency:
            continue
        if target not in adjacency[source]:
            adjacency[source].append(target)
        if not directed and source not in adjacency[target]:
            adjacency[target].append(source)

    if isinstance(neighbor_order, list):
        rank = {str(node_id): index for index, node_id in enumerate(neighbor_order)}
        fallback = len(rank)
        input_rank = {node_id: index for index, node_id in enumerate(node_ids)}
        for neighbors in adjacency.values():
            neighbors.sort(key=lambda node_id: (
                rank.get(node_id, fallback), input_rank.get(node_id, len(node_ids))
            ))
    return adjacency


def _traverse(
    node_ids: List[str],
    edges: List[Dict[str, Any]],
    start: str,
    algorithm: str,
    directed: bool,
    neighbor_order: Any,
) -> List[Dict[str, Any]]:
    """Compute snapshots. Vertices are discovered when added to the frontier."""
    adjacency = _adjacency(node_ids, edges, directed, neighbor_order)
    frontier = [start]
    discovered = {start}
    visited: List[str] = []
    tree_edges: List[Tuple[str, str]] = []
    snapshots: List[Dict[str, Any]] = [{
        "current": None, "frontier": list(frontier), "visited": [], "tree_edges": []
    }]

    while frontier:
        current = frontier.pop(0 if algorithm == "bfs" else -1)
        visited.append(current)
        neighbors = adjacency[current]
        candidates = neighbors if algorithm == "bfs" else reversed(neighbors)
        for neighbor in candidates:
            if neighbor in discovered:
                continue
            discovered.add(neighbor)
            tree_edges.append((current, neighbor))
            frontier.append(neighbor)
        snapshots.append({
            "current": current,
            "frontier": list(frontier),
            "visited": list(visited),
            "tree_edges": list(tree_edges),
        })
    return snapshots


def _findings(params: Dict[str, Any]) -> List[Finding]:
    nodes, edges = _graph_parts(params)
    node_ids = [str(node.get("id")) for node in nodes if isinstance(node, dict)]
    findings: List[Finding] = []
    if not isinstance(params.get("nodes", []), list):
        findings.append(Finding(
            "traversal_vertices", "error", "nodes must be an array"
        ))
    if not isinstance(params.get("edges", []), list):
        findings.append(Finding(
            "traversal_edges", "error", "edges must be an array"
        ))
    if any(not isinstance(node, dict) or node.get("id") is None for node in nodes):
        findings.append(Finding(
            "traversal_vertices", "error", "every node must be an object with an id"
        ))
    algorithm = str(params.get("algorithm", "bfs")).strip().lower()
    if algorithm not in {"bfs", "dfs"}:
        findings.append(Finding(
            "traversal_algorithm", "error", "algorithm must be bfs or dfs"
        ))
    if not node_ids:
        findings.append(Finding(
            "traversal_vertices", "error", "nodes must contain at least one vertex"
        ))
        return findings
    if len(node_ids) != len(set(node_ids)):
        findings.append(Finding(
            "traversal_vertices", "error", "vertex ids must be unique"
        ))
    start = str(params.get("start", node_ids[0]))
    if start not in set(node_ids):
        findings.append(Finding(
            "traversal_start", "error", f"start vertex {start!r} does not exist",
            label=start,
        ))
    known = set(node_ids)
    for edge in edges:
        if not isinstance(edge, dict):
            findings.append(Finding(
                "traversal_edges", "error", "every edge must be an object"
            ))
            continue
        if edge.get("from") is None or edge.get("to") is None:
            findings.append(Finding(
                "traversal_edges", "error", "every edge needs from and to endpoints"
            ))
            continue
        source, target = str(edge.get("from")), str(edge.get("to"))
        if source not in known or target not in known:
            findings.append(Finding(
                "traversal_endpoints", "error",
                f"edge {source!r}–{target!r} refers to an unknown vertex",
                label=f"{source}–{target}",
            ))
    order = params.get("neighbor_order")
    if order is not None:
        if not isinstance(order, list):
            findings.append(Finding(
                "traversal_order", "error", "neighbor_order must be an array"
            ))
        else:
            named = [str(node_id) for node_id in order]
            if len(named) != len(set(named)):
                findings.append(Finding(
                    "traversal_order", "error", "neighbor_order must not repeat vertices"
                ))
            unknown = [node_id for node_id in named if node_id not in known]
            if unknown:
                findings.append(Finding(
                    "traversal_order", "error",
                    f"neighbor_order contains unknown vertex {unknown[0]!r}",
                    label=unknown[0],
                ))
    if findings:
        return findings

    snapshots = _traverse(
        node_ids, edges, start, algorithm, bool(params.get("directed", False)), order
    )
    visits = len(snapshots) - 1
    if visits > MAX_VISITS:
        findings.append(Finding(
            "traversal_size", "error",
            f"the reachable component has {visits} vertices; at most {MAX_VISITS} "
            "fit with the initial state in one readable storyboard",
        ))
    return findings


@register("graph_traversal")
class GraphTraversalTemplate:
    """Compute and render a checked BFS or DFS traversal storyboard."""

    def refusal_findings(self, params: Dict[str, Any]) -> List[Finding]:
        return _findings(params)

    def render(self, params: Dict[str, Any]) -> str:
        # Read the complete public surface here so catalog discovery publishes
        # it even though construction is factored into helpers below.
        nodes = params.get("nodes", [])
        edges = params.get("edges", [])
        algorithm = str(params.get("algorithm", "bfs")).strip().lower()
        start_value = params.get("start")
        directed = bool(params.get("directed", False))
        neighbor_order = params.get("neighbor_order")
        graph_layout = str(params.get("graph_layout", "circular"))
        title = params.get("title")
        columns = int(params.get("columns", 3))
        node_radius = int(params.get("node_radius", 20))
        width = int(params.get("width", 600))
        height = int(params.get("height", 360))

        if self.refusal_findings(params):
            return ""
        valid_nodes = nodes if isinstance(nodes, list) else []
        valid_edges = edges if isinstance(edges, list) else []
        node_ids = [str(node.get("id")) for node in valid_nodes if isinstance(node, dict)]
        start = str(start_value) if start_value is not None else node_ids[0]
        snapshots = _traverse(
            node_ids, valid_edges, start, algorithm, directed, neighbor_order
        )

        frontier_name = "queue" if algorithm == "bfs" else "stack"
        steps: List[Dict[str, Any]] = []
        for index, snapshot in enumerate(snapshots):
            highlights = {
                node_id: "visited" for node_id in snapshot["visited"]
            }
            highlights.update({
                node_id: "target" for node_id in snapshot["frontier"]
            })
            current = snapshot["current"]
            if current is not None:
                highlights[current] = "current"
            visit_numbers = {
                node_id: f"#{visit_index + 1}"
                for visit_index, node_id in enumerate(snapshot["visited"])
            }
            frontier = snapshot["frontier"]
            frontier_text = ", ".join(frontier) if frontier else "∅"
            order_text = ", ".join(snapshot["visited"]) or "∅"
            graph_params = {
                "nodes": valid_nodes,
                "edges": valid_edges,
                "directed": directed,
                "layout": graph_layout,
                "node_radius": node_radius,
                "width": width,
                "height": height,
                "highlights": {
                    "nodes": highlights,
                    "edges": [list(edge) for edge in snapshot["tree_edges"]],
                },
                "distance_labels": visit_numbers,
                "caption": f"{frontier_name}: [{frontier_text}] · order: [{order_text}]",
            }
            label = "Initial frontier" if index == 0 else f"Visit {current}"
            steps.append({
                "label": label,
                "visual": {"type": "graph", "params": graph_params},
            })

        trace = DIAGRAM_REGISTRY["algorithm_trace"]
        return trace.render({
            "title": str(title) if title is not None else f"{algorithm.upper()} from {start}",
            "steps": steps,
            "columns": columns,
            "show_step_numbers": True,
        })
