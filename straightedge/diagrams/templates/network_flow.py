"""Checked capacitated flows, residual graphs, cuts, and augmenting paths."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple

from ...qc import Finding
from ..registry import DIAGRAM_REGISTRY, register


def _number(value: Any) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def _checked(params: Dict[str, Any]) -> Tuple[List[Finding], List[Dict[str, Any]],
                                               List[Dict[str, Any]], float, float | None]:
    raw_nodes, raw_edges = params.get("nodes", []), params.get("edges", [])
    if not isinstance(raw_nodes, list) or not raw_nodes:
        return [Finding("flow_vertices", "error", "nodes must be a non-empty array")], [], [], 0, None
    if not isinstance(raw_edges, list):
        return [Finding("flow_edges", "error", "edges must be an array")], [], [], 0, None
    nodes = [node for node in raw_nodes if isinstance(node, dict) and node.get("id") is not None]
    node_ids = [str(node["id"]) for node in nodes]
    if len(nodes) != len(raw_nodes) or len(node_ids) != len(set(node_ids)):
        return [Finding("flow_vertices", "error", "every node needs a unique id")], [], [], 0, None
    known = set(node_ids)
    source, sink = str(params.get("source", "")), str(params.get("sink", ""))
    if source not in known or sink not in known or source == sink:
        return [Finding(
            "flow_terminals", "error", "source and sink must name distinct vertices"
        )], [], [], 0, None

    edges: List[Dict[str, Any]] = []
    pairs = set()
    balance = {node_id: 0.0 for node_id in node_ids}  # inflow minus outflow
    for edge in raw_edges:
        if not isinstance(edge, dict):
            return [Finding("flow_edges", "error", "every edge must be an object")], [], [], 0, None
        start, end = str(edge.get("from")), str(edge.get("to"))
        capacity, flow = edge.get("capacity"), edge.get("flow", 0)
        if start not in known or end not in known:
            return [Finding(
                "flow_endpoints", "error",
                f"edge {start!r}→{end!r} refers to an unknown vertex",
            )], [], [], 0, None
        if start == end:
            return [Finding("flow_edges", "error", "flow edges cannot be self-loops")], [], [], 0, None
        if (start, end) in pairs:
            return [Finding(
                "flow_edges", "error", f"parallel edge {start!r}→{end!r} is ambiguous"
            )], [], [], 0, None
        pairs.add((start, end))
        if not _number(capacity) or capacity < 0:
            return [Finding(
                "flow_capacity", "error", f"edge {start!r}→{end!r} needs non-negative capacity"
            )], [], [], 0, None
        if not _number(flow) or flow < 0 or flow > capacity:
            return [Finding(
                "flow_bounds", "error",
                f"edge {start!r}→{end!r} has flow {flow!r} outside [0, {capacity!r}]",
            )], [], [], 0, None
        normalized = dict(edge)
        normalized.update({"from": start, "to": end,
                           "capacity": float(capacity), "flow": float(flow)})
        edges.append(normalized)
        balance[start] -= float(flow)
        balance[end] += float(flow)

    for node_id in node_ids:
        if node_id not in {source, sink} and abs(balance[node_id]) > 1e-9:
            return [Finding(
                "flow_conservation", "error",
                f"vertex {node_id!r} has inflow − outflow = {balance[node_id]:g}",
                label=node_id,
            )], [], [], 0, None
    value = -balance[source]
    if abs(balance[sink] - value) > 1e-9:
        return [Finding(
            "flow_conservation", "error", "source outflow does not equal sink inflow"
        )], [], [], 0, None
    claimed = params.get("value")
    if claimed is not None and (not _number(claimed) or abs(float(claimed) - value) > 1e-9):
        return [Finding(
            "flow_value", "error", f"claimed value {claimed!r}, computed {value:g}"
        )], [], [], value, None

    cut_capacity: float | None = None
    cut = params.get("cut")
    if cut is not None:
        if not isinstance(cut, list) or len({str(v) for v in cut}) != len(cut):
            return [Finding("flow_cut", "error", "cut must be an array of unique vertex ids")], [], [], value, None
        source_side = {str(v) for v in cut}
        if not source_side <= known or source not in source_side or sink in source_side:
            return [Finding(
                "flow_cut", "error", "cut must contain source, exclude sink, and name known vertices"
            )], [], [], value, None
        cut_capacity = sum(edge["capacity"] for edge in edges
                           if edge["from"] in source_side and edge["to"] not in source_side)

    path = params.get("augmenting_path")
    if path is not None:
        if (not isinstance(path, list) or len(path) < 2
                or str(path[0]) != source or str(path[-1]) != sink):
            return [Finding(
                "augmenting_path", "error", "augmenting_path must run from source to sink"
            )], [], [], value, cut_capacity
        residual = {(edge["from"], edge["to"]): edge["capacity"] - edge["flow"] for edge in edges}
        for edge in edges:
            residual[(edge["to"], edge["from"])] = residual.get(
                (edge["to"], edge["from"]), 0.0
            ) + edge["flow"]
        for left, right in zip(path, path[1:]):
            pair = (str(left), str(right))
            if residual.get(pair, 0.0) <= 1e-9:
                return [Finding(
                    "augmenting_path", "error",
                    f"residual edge {pair[0]!r}→{pair[1]!r} has no capacity",
                )], [], [], value, cut_capacity

    if bool(params.get("claim_max_flow", False)):
        if cut_capacity is None:
            return [Finding(
                "max_flow_claim", "error", "claim_max_flow requires a cut"
            )], [], [], value, None
        if abs(value - cut_capacity) > 1e-9:
            return [Finding(
                "max_flow_claim", "error",
                f"flow value {value:g} does not equal cut capacity {cut_capacity:g}",
            )], [], [], value, cut_capacity
    return [], nodes, edges, value, cut_capacity


@register("network_flow")
class NetworkFlowTemplate:
    """Render a feasible flow or residual network after checking its claims."""

    checks = ["capacity bounds", "flow conservation", "residual path capacity",
              "max-flow/min-cut certificate"]

    def refusal_findings(self, params: Dict[str, Any]) -> List[Finding]:
        findings, _, _, _, _ = _checked(params)
        return findings

    def render(self, params: Dict[str, Any]) -> str:
        # Kept in render so catalog discovery publishes the checked surface.
        params.get("nodes", [])
        params.get("edges", [])
        params.get("value")
        params.get("claim_max_flow", False)
        source = str(params.get("source", ""))
        sink = str(params.get("sink", ""))
        layout = str(params.get("layout", "hierarchical"))
        show_residual = bool(params.get("show_residual", False))
        caption = params.get("caption")
        width = int(params.get("width", 700))
        height = int(params.get("height", 420))
        node_radius = int(params.get("node_radius", 22))
        path = params.get("augmenting_path", [])
        cut = params.get("cut")
        findings, nodes, edges, value, cut_capacity = _checked(params)
        if findings:
            return ""

        drawn_edges: List[Dict[str, Any]] = []
        if show_residual:
            residual: Dict[Tuple[str, str], float] = {}
            for edge in edges:
                forward = edge["capacity"] - edge["flow"]
                if forward > 1e-9:
                    residual[(edge["from"], edge["to"])] = residual.get(
                        (edge["from"], edge["to"]), 0.0
                    ) + forward
                if edge["flow"] > 1e-9:
                    residual[(edge["to"], edge["from"])] = residual.get(
                        (edge["to"], edge["from"]), 0.0
                    ) + edge["flow"]
            drawn_edges = [{"from": start, "to": end, "weight": f"r={amount:g}"}
                           for (start, end), amount in residual.items()]
        else:
            drawn_edges = [{
                "from": edge["from"], "to": edge["to"],
                "weight": f"{edge['flow']:g}/{edge['capacity']:g}",
            } for edge in edges]

        highlighted = []
        if isinstance(cut, list):
            source_side = {str(v) for v in cut}
            highlighted.extend([[edge["from"], edge["to"]] for edge in edges
                                if edge["from"] in source_side and edge["to"] not in source_side])
        highlighted.extend([[edge["from"], edge["to"]] for edge in edges
                            if edge["flow"] == edge["capacity"] and edge["capacity"] > 0])
        if caption is None:
            caption = f"flow value = {value:g}"
            if cut_capacity is not None:
                caption += f" · cut capacity = {cut_capacity:g}"
        node_highlights = {source: "current", sink: "target"}
        if isinstance(cut, list):
            node_highlights.update({str(node_id): "visited" for node_id in cut
                                    if str(node_id) not in {source, sink}})
        return DIAGRAM_REGISTRY["graph"].render({
            "nodes": nodes,
            "edges": drawn_edges,
            "directed": True,
            "weighted": True,
            "layout": layout,
            "path": path if isinstance(path, list) else [],
            "highlights": {"nodes": node_highlights, "edges": highlighted},
            "caption": caption,
            "width": width,
            "height": height,
            "node_radius": node_radius,
        })
