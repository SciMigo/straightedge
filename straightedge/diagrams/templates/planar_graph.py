"""Checked straight-line planar embeddings rendered through ``graph``."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple

from ...qc import Finding
from ..registry import DIAGRAM_REGISTRY, register


Point = Tuple[float, float]


def _orientation(a: Point, b: Point, c: Point) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(a: Point, b: Point, p: Point) -> bool:
    eps = 1e-9
    return (min(a[0], b[0]) - eps <= p[0] <= max(a[0], b[0]) + eps
            and min(a[1], b[1]) - eps <= p[1] <= max(a[1], b[1]) + eps
            and abs(_orientation(a, b, p)) <= eps)


def _intersect(a: Point, b: Point, c: Point, d: Point) -> bool:
    eps = 1e-9
    o1, o2, o3, o4 = (_orientation(a, b, c), _orientation(a, b, d),
                      _orientation(c, d, a), _orientation(c, d, b))
    if ((o1 > eps and o2 < -eps) or (o1 < -eps and o2 > eps)) and \
       ((o3 > eps and o4 < -eps) or (o3 < -eps and o4 > eps)):
        return True
    return ((abs(o1) <= eps and _on_segment(a, b, c))
            or (abs(o2) <= eps and _on_segment(a, b, d))
            or (abs(o3) <= eps and _on_segment(c, d, a))
            or (abs(o4) <= eps and _on_segment(c, d, b)))


def _checked(params: Dict[str, Any]) -> Tuple[List[Finding], List[Dict[str, Any]],
                                               List[Dict[str, Any]]]:
    raw_nodes, raw_edges = params.get("nodes", []), params.get("edges", [])
    if not isinstance(raw_nodes, list) or not raw_nodes:
        return [Finding("planar_vertices", "error", "nodes must be a non-empty array")], [], []
    if not isinstance(raw_edges, list):
        return [Finding("planar_edges", "error", "edges must be an array")], [], []
    nodes = [node for node in raw_nodes if isinstance(node, dict)]
    if len(nodes) != len(raw_nodes):
        return [Finding("planar_vertices", "error", "every node must be an object")], [], []
    node_ids = [str(node.get("id")) for node in nodes if node.get("id") is not None]
    if len(node_ids) != len(nodes) or len(node_ids) != len(set(node_ids)):
        return [Finding(
            "planar_vertices", "error", "every node needs a unique id"
        )], [], []
    positions: Dict[str, Point] = {}
    for node in nodes:
        x, y = node.get("x"), node.get("y")
        if (not isinstance(x, (int, float)) or isinstance(x, bool)
                or not isinstance(y, (int, float)) or isinstance(y, bool)
                or not math.isfinite(x) or not math.isfinite(y)):
            return [Finding(
                "planar_embedding", "error",
                f"vertex {node.get('id')!r} needs finite x and y coordinates",
                label=str(node.get("id")),
            )], [], []
        point = (float(x), float(y))
        if point in positions.values():
            return [Finding(
                "planar_embedding", "error", "two vertices occupy the same position"
            )], [], []
        positions[str(node["id"])] = point

    known = set(node_ids)
    edges: List[Dict[str, Any]] = []
    pairs = set()
    for edge in raw_edges:
        if not isinstance(edge, dict):
            return [Finding("planar_edges", "error", "every edge must be an object")], [], []
        source, target = str(edge.get("from")), str(edge.get("to"))
        if source not in known or target not in known:
            return [Finding(
                "planar_endpoints", "error",
                f"edge {source!r}–{target!r} refers to an unknown vertex",
            )], [], []
        if source == target:
            return [Finding(
                "planar_simple_graph", "error", "checked planar embeddings do not accept loops"
            )], [], []
        pair = tuple(sorted((source, target)))
        if pair in pairs:
            return [Finding(
                "planar_simple_graph", "error", f"parallel edge {source!r}–{target!r}"
            )], [], []
        pairs.add(pair)
        edges.append(edge)

    segments = [(str(edge["from"]), str(edge["to"])) for edge in edges]
    for index, (a, b) in enumerate(segments):
        for c, d in segments[index + 1:]:
            if {a, b} & {c, d}:
                continue
            if _intersect(positions[a], positions[b], positions[c], positions[d]):
                return [Finding(
                    "planar_crossing", "error",
                    f"edges {a!r}–{b!r} and {c!r}–{d!r} cross in this embedding",
                    label=f"{a}–{b} × {c}–{d}",
                )], [], []

    faces = params.get("faces")
    if faces is not None:
        if not isinstance(faces, int) or isinstance(faces, bool) or faces < 1:
            return [Finding("euler_formula", "error", "faces must be a positive integer")], [], []
        adjacency = {node_id: [] for node_id in node_ids}
        for source, target in segments:
            adjacency[source].append(target)
            adjacency[target].append(source)
        components, seen = 0, set()
        for root in node_ids:
            if root in seen:
                continue
            components += 1
            stack = [root]
            seen.add(root)
            while stack:
                current = stack.pop()
                for neighbor in adjacency[current]:
                    if neighbor not in seen:
                        seen.add(neighbor)
                        stack.append(neighbor)
        expected = 1 + components
        actual = len(node_ids) - len(edges) + faces
        if actual != expected:
            return [Finding(
                "euler_formula", "error",
                f"V − E + F is {actual}, but an embedding with {components} component(s) needs {expected}",
            )], [], []
    return [], nodes, edges


@register("planar_graph")
class PlanarGraphTemplate:
    """Render a checked straight-line planar embedding and optional Euler claim."""

    checks = ["known endpoints", "simple graph", "straight-line crossings", "Euler identity"]

    def refusal_findings(self, params: Dict[str, Any]) -> List[Finding]:
        findings, _, _ = _checked(params)
        return findings

    def render(self, params: Dict[str, Any]) -> str:
        # Kept in render so catalog discovery publishes the forwarded surface.
        params.get("nodes", [])
        params.get("edges", [])
        faces = params.get("faces")
        show_degrees = bool(params.get("show_degrees", False))
        caption = params.get("caption")
        width = int(params.get("width", 600))
        height = int(params.get("height", 360))
        node_radius = int(params.get("node_radius", 20))
        findings, nodes, edges = _checked(params)
        if findings:
            return ""
        if caption is None and faces is not None:
            total = len(nodes) - len(edges) + faces
            caption = f"V={len(nodes)}, E={len(edges)}, F={faces}: V − E + F = {total}"
        return DIAGRAM_REGISTRY["graph"].render({
            "nodes": nodes,
            "edges": edges,
            "layout": "custom",
            "show_degrees": show_degrees,
            "caption": caption,
            "width": width,
            "height": height,
            "node_radius": node_radius,
        })
