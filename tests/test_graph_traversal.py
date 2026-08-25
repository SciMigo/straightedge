"""BFS and DFS are computed before their storyboards are drawn."""

import re

from straightedge.diagrams import DIAGRAM_REGISTRY, render_diagram
from straightedge.diagrams.registry import refusal_findings
from straightedge.diagrams.templates.graph_traversal import _traverse


NODES = [{"id": node, "label": node} for node in "ABCDE"]
EDGES = [
    {"from": "A", "to": "B"},
    {"from": "A", "to": "C"},
    {"from": "B", "to": "D"},
    {"from": "C", "to": "E"},
]


def _params(algorithm="bfs"):
    return {
        "nodes": NODES,
        "edges": EDGES,
        "algorithm": algorithm,
        "start": "A",
        "neighbor_order": list("ABCDE"),
        "graph_layout": "hierarchical",
        "columns": 3,
    }


def test_template_is_publicly_registered():
    assert "graph_traversal" in DIAGRAM_REGISTRY


def test_bfs_uses_a_queue_and_visits_by_level():
    snapshots = _traverse(list("ABCDE"), EDGES, "A", "bfs", False, list("ABCDE"))
    assert snapshots[-1]["visited"] == list("ABCDE")
    assert snapshots[1]["frontier"] == ["B", "C"]
    assert snapshots[2]["frontier"] == ["C", "D"]


def test_dfs_uses_a_stack_and_follows_first_neighbor_deeply():
    snapshots = _traverse(list("ABCDE"), EDGES, "A", "dfs", False, list("ABCDE"))
    assert snapshots[-1]["visited"] == ["A", "B", "D", "C", "E"]
    assert snapshots[1]["frontier"] == ["C", "B"]


def test_neighbor_order_makes_the_tie_break_explicit():
    order = ["A", "C", "B", "E", "D"]
    bfs = _traverse(list("ABCDE"), EDGES, "A", "bfs", False, order)
    dfs = _traverse(list("ABCDE"), EDGES, "A", "dfs", False, order)
    assert bfs[-1]["visited"] == ["A", "C", "B", "E", "D"]
    assert dfs[-1]["visited"] == ["A", "C", "E", "B", "D"]


def test_bfs_storyboard_renders_all_states():
    svg = render_diagram({"type": "graph_traversal", "params": _params("bfs")})
    assert "<svg" in svg
    assert "BFS from A" in svg
    # Initial state plus one panel per reachable vertex.
    assert len(re.findall(r'class="at-card"', svg)) == 6


def test_dfs_storyboard_renders():
    svg = render_diagram({"type": "graph_traversal", "params": _params("dfs")})
    assert "<svg" in svg
    assert "DFS from A" in svg


def test_unknown_start_is_refused_with_a_specific_reason():
    params = {**_params(), "start": "Z"}
    findings = refusal_findings("graph_traversal", params)
    assert findings[0].check == "traversal_start"
    assert "Z" in findings[0].message
    assert render_diagram({"type": "graph_traversal", "params": params}) == ""


def test_unknown_endpoint_is_refused():
    params = {**_params(), "edges": EDGES + [{"from": "E", "to": "Z"}]}
    findings = refusal_findings("graph_traversal", params)
    assert any(finding.check == "traversal_endpoints" for finding in findings)


def test_more_than_twelve_panels_is_refused_as_unreadable():
    nodes = [{"id": str(index)} for index in range(12)]
    edges = [{"from": str(index), "to": str(index + 1)} for index in range(11)]
    params = {"nodes": nodes, "edges": edges, "start": "0", "algorithm": "bfs"}
    findings = refusal_findings("graph_traversal", params)
    assert findings[0].check == "traversal_size"
    assert "at most 11" in findings[0].message


def test_directed_traversal_does_not_follow_an_edge_backwards():
    snapshots = _traverse(["A", "B"], [{"from": "A", "to": "B"}],
                          "B", "bfs", True, None)
    assert snapshots[-1]["visited"] == ["B"]
