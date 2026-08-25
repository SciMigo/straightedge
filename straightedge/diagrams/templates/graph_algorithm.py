"""Checked graph-algorithm storyboards and dependency-free animated SVGs."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple

from ...qc import Finding
from ..registry import DIAGRAM_REGISTRY, register

MAX_VERTICES = 11
ALGORITHMS = {"dijkstra", "kruskal", "greedy_coloring", "bipartite_matching"}


def _parts(params: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    nodes, edges = params.get("nodes", []), params.get("edges", [])
    return (nodes if isinstance(nodes, list) else [], edges if isinstance(edges, list) else [])


def _number(value: Any) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def _findings(params: Dict[str, Any]) -> List[Finding]:
    nodes, edges = _parts(params)
    findings: List[Finding] = []
    algorithm = str(params.get("algorithm", "dijkstra")).strip().lower()
    if algorithm not in ALGORITHMS:
        findings.append(Finding("graph_algorithm", "error",
                                "algorithm must be dijkstra, kruskal, greedy_coloring, "
                                "or bipartite_matching"))
    if not isinstance(params.get("nodes", []), list) or not nodes:
        findings.append(Finding("graph_algorithm_nodes", "error", "nodes must be a non-empty array"))
        return findings
    if not isinstance(params.get("edges", []), list):
        findings.append(Finding("graph_algorithm_edges", "error", "edges must be an array"))
    ids = [str(n.get("id")) for n in nodes if isinstance(n, dict) and n.get("id") is not None]
    if len(ids) != len(nodes):
        findings.append(Finding("graph_algorithm_nodes", "error", "every node must be an object with an id"))
    if len(ids) != len(set(ids)):
        findings.append(Finding("graph_algorithm_nodes", "error", "vertex ids must be unique"))
    if len(ids) > MAX_VERTICES:
        findings.append(Finding("graph_algorithm_size", "error",
                                f"at most {MAX_VERTICES} vertices fit in one readable trace"))
    known, seen = set(ids), set()
    directed = bool(params.get("directed", False))
    for edge in edges:
        if not isinstance(edge, dict) or edge.get("from") is None or edge.get("to") is None:
            findings.append(Finding("graph_algorithm_edges", "error", "every edge needs from and to endpoints"))
            continue
        u, v = str(edge["from"]), str(edge["to"])
        if u not in known or v not in known:
            findings.append(Finding("graph_algorithm_endpoints", "error",
                                    f"edge {u!r}–{v!r} names an unknown vertex"))
        if u == v:
            findings.append(Finding("graph_algorithm_loop", "error", "algorithm traces require loop-free graphs"))
        key = (u, v) if directed else tuple(sorted((u, v)))
        if key in seen:
            findings.append(Finding("graph_algorithm_parallel", "error",
                                    "parallel edges are ambiguous in an algorithm trace"))
        seen.add(key)
    if findings:
        return findings
    if algorithm in {"dijkstra", "kruskal"}:
        for edge in edges:
            if not _number(edge.get("weight")):
                findings.append(Finding("graph_algorithm_weight", "error",
                                        "every weighted edge needs a finite numeric weight"))
            elif algorithm == "dijkstra" and edge["weight"] < 0:
                findings.append(Finding("graph_algorithm_weight", "error",
                                        "Dijkstra requires nonnegative edge weights"))
    if algorithm == "dijkstra" and str(params.get("start", ids[0])) not in known:
        findings.append(Finding("graph_algorithm_start", "error", "start must name a vertex"))
    if algorithm == "kruskal" and directed:
        findings.append(Finding("graph_algorithm_direction", "error", "Kruskal requires an undirected graph"))
    if algorithm == "greedy_coloring":
        order = params.get("vertex_order")
        if order is not None and (not isinstance(order, list)
                                  or len({str(x) for x in order}) != len(order)
                                  or any(str(x) not in known for x in order)):
            findings.append(Finding("graph_algorithm_order", "error",
                                    "vertex_order must be a unique list of known vertices"))
    if algorithm == "bipartite_matching":
        partitions = params.get("partitions")
        if not isinstance(partitions, dict):
            findings.append(Finding("graph_algorithm_partitions", "error",
                                    "bipartite_matching needs partitions.left and partitions.right"))
        else:
            left, right = partitions.get("left"), partitions.get("right")
            if not isinstance(left, list) or not isinstance(right, list):
                findings.append(Finding("graph_algorithm_partitions", "error",
                                        "partitions.left and partitions.right must be arrays"))
            else:
                left_ids, right_ids = [str(x) for x in left], [str(x) for x in right]
                left_set = set(left_ids)
                if (len(left_ids) + len(right_ids) != len(known)
                        or left_set & set(right_ids) or left_set | set(right_ids) != known):
                    findings.append(Finding("graph_algorithm_partitions", "error",
                                            "partitions must contain every vertex exactly once"))
                for edge in edges:
                    u, v = str(edge["from"]), str(edge["to"])
                    if (u in left_set) == (v in left_set):
                        findings.append(Finding("graph_algorithm_bipartite", "error",
                                                f"edge {u!r}–{v!r} does not cross the partition"))
    return findings


def _base(params: Dict[str, Any]) -> Dict[str, Any]:
    nodes, edges = _parts(params)
    algorithm = str(params.get("algorithm", "dijkstra")).strip().lower()
    return {"nodes": nodes, "edges": edges, "directed": bool(params.get("directed", False)),
            "weighted": algorithm in {"dijkstra", "kruskal"},
            "layout": str(params.get("graph_layout", "circular")),
            "node_radius": int(params.get("node_radius", 20)),
            "width": int(params.get("width", 600)), "height": int(params.get("height", 360))}


def _dijkstra(params: Dict[str, Any]) -> List[Dict[str, Any]]:
    nodes, edges = _parts(params); ids = [str(n["id"]) for n in nodes]
    directed, start = bool(params.get("directed", False)), str(params.get("start", ids[0]))
    adj: Dict[str, List[Tuple[str, float]]] = {x: [] for x in ids}
    for edge in edges:
        u, v, w = str(edge["from"]), str(edge["to"]), float(edge["weight"])
        adj[u].append((v, w))
        if not directed: adj[v].append((u, w))
    dist = {x: math.inf for x in ids}; dist[start] = 0.0
    previous: Dict[str, str] = {}; settled: List[str] = []
    states = [(None, dict(dist), dict(previous), list(settled))]
    while True:
        choices = [x for x in ids if x not in settled and math.isfinite(dist[x])]
        if not choices: break
        current = min(choices, key=lambda x: (dist[x], ids.index(x))); settled.append(current)
        for neighbor, weight in adj[current]:
            if dist[current] + weight < dist[neighbor]:
                dist[neighbor], previous[neighbor] = dist[current] + weight, current
        states.append((current, dict(dist), dict(previous), list(settled)))
    out, base = [], _base(params)
    for current, distances, previous_state, done in states:
        labels = {x: ("∞" if not math.isfinite(d) else f"{d:g}") for x, d in distances.items()}
        highlights = {x: "visited" for x in done}
        if current is not None: highlights[current] = "current"
        gp = {**base, "distance_labels": labels,
              "highlights": {"nodes": highlights,
                             "edges": [[u, v] for v, u in previous_state.items()]},
              "caption": ("Initialize tentative distances" if current is None
                          else f"Settle {current}; relax adjacent edges")}
        out.append({"label": "Initialize" if current is None else f"Settle {current}",
                    "visual": {"type": "graph", "params": gp}})
    return out


def _kruskal(params: Dict[str, Any]) -> List[Dict[str, Any]]:
    nodes, edges = _parts(params); ids = [str(n["id"]) for n in nodes]; parent = {x: x for x in ids}
    def root(x: str) -> str:
        while parent[x] != x: parent[x] = parent[parent[x]]; x = parent[x]
        return x
    chosen: List[List[str]] = []; states = [("Start with no edges", [], 0.0)]; total = 0.0
    for index, edge in sorted(enumerate(edges), key=lambda pair: (float(pair[1]["weight"]), pair[0])):
        _ = index
        u, v = str(edge["from"]), str(edge["to"]); ru, rv = root(u), root(v)
        if ru == rv: continue
        parent[ru] = rv; chosen.append([u, v]); total += float(edge["weight"])
        states.append((f"Accept {u}–{v}", list(chosen), total))
    out, base = [], _base(params)
    for label, selected, weight in states:
        gp = {**base, "highlights": {"edges": selected}, "caption": f"forest weight = {weight:g}"}
        out.append({"label": label, "visual": {"type": "graph", "params": gp}})
    return out


def _coloring(params: Dict[str, Any]) -> List[Dict[str, Any]]:
    nodes, edges = _parts(params); ids = [str(n["id"]) for n in nodes]
    supplied = params.get("vertex_order"); order = [str(x) for x in supplied] if isinstance(supplied, list) else []
    order += [x for x in ids if x not in order]
    adj = {x: set() for x in ids}
    for edge in edges:
        u, v = str(edge["from"]), str(edge["to"]); adj[u].add(v); adj[v].add(u)
    colors: Dict[str, int] = {}; states = [(None, {})]
    for vertex in order:
        used = {colors[n] for n in adj[vertex] if n in colors}
        colors[vertex] = next(c for c in range(1, len(ids) + 1) if c not in used)
        states.append((vertex, dict(colors)))
    out, base = [], _base(params)
    for current, assigned in states:
        gp = {**base, "highlights": {"nodes": {x: f"color-{c}" for x, c in assigned.items()}},
              "caption": ("No vertices colored" if current is None else
                          f"Assign {current} the smallest available color: {assigned[current]}")}
        out.append({"label": "Initialize" if current is None else f"Color {current}",
                    "visual": {"type": "graph", "params": gp}})
    return out


def _matching(params: Dict[str, Any]) -> List[Dict[str, Any]]:
    nodes, edges = _parts(params); partitions = params["partitions"]
    left = [str(x) for x in partitions["left"]]; adj = {x: [] for x in left}
    for edge in edges:
        u, v = str(edge["from"]), str(edge["to"])
        if u in adj: adj[u].append(v)
        else: adj[v].append(u)
    match_r: Dict[str, str] = {}; states = [(None, {})]
    def augment(u: str, seen: set[str]) -> bool:
        for v in adj[u]:
            if v in seen: continue
            seen.add(v)
            if v not in match_r or augment(match_r[v], seen): match_r[v] = u; return True
        return False
    for u in left:
        if augment(u, set()): states.append((u, dict(match_r)))
    base = {**_base(params), "layout": "bipartite", "partitions": partitions}
    out = []
    for current, matching in states:
        selected = [[u, v] for v, u in matching.items()]
        gp = {**base, "highlights": {"edges": selected}, "caption": f"matching size = {len(selected)}"}
        out.append({"label": "Empty matching" if current is None else f"Augment from {current}",
                    "visual": {"type": "graph", "params": gp}})
    return out


@register("graph_algorithm")
class GraphAlgorithmTemplate:
    """Compute shortest-path, spanning-tree, colouring, or matching states."""
    motion = "optional"
    checks = ["valid vertices and endpoints", "algorithm-specific assumptions",
              "nonnegative Dijkstra weights", "bipartition integrity",
              "computed intermediate states"]

    def refusal_findings(self, params: Dict[str, Any]) -> List[Finding]:
        return _findings(params)

    def render(self, params: Dict[str, Any]) -> str:
        algorithm = str(params.get("algorithm", "dijkstra")).strip().lower()
        nodes, edges, start = params.get("nodes", []), params.get("edges", []), params.get("start")
        directed, partitions = bool(params.get("directed", False)), params.get("partitions")
        vertex_order, graph_layout = params.get("vertex_order"), str(params.get("graph_layout", "circular"))
        animate, duration_s = bool(params.get("animate", True)), float(params.get("duration_s", 1.2))
        loop, title, columns = bool(params.get("loop", True)), params.get("title"), int(params.get("columns", 3))
        node_radius, width, height = int(params.get("node_radius", 20)), int(params.get("width", 600)), int(params.get("height", 360))
        _ = (nodes, edges, start, directed, partitions, vertex_order, graph_layout, node_radius, width, height)
        if self.refusal_findings(params): return ""
        frames = {"dijkstra": _dijkstra, "kruskal": _kruskal,
                  "greedy_coloring": _coloring, "bipartite_matching": _matching}[algorithm](params)
        heading = str(title) if title is not None else algorithm.replace("_", " ").title()
        if animate:
            return DIAGRAM_REGISTRY["animated_trace"].render({"title": heading, "frames": frames,
                                                               "duration_s": duration_s, "loop": loop})
        return DIAGRAM_REGISTRY["algorithm_trace"].render({"title": heading, "steps": frames,
                                                            "columns": columns, "show_step_numbers": True})
