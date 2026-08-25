"""Network-flow figures enforce capacities, conservation, and cut claims."""

import re

from straightedge.diagrams import DIAGRAM_REGISTRY, render_diagram
from straightedge.diagrams.registry import refusal_findings


NODES = [{"id": x, "label": x} for x in ("s", "a", "b", "t")]
EDGES = [
    {"from": "s", "to": "a", "capacity": 3, "flow": 2},
    {"from": "s", "to": "b", "capacity": 2, "flow": 2},
    {"from": "a", "to": "b", "capacity": 1, "flow": 0},
    {"from": "a", "to": "t", "capacity": 2, "flow": 2},
    {"from": "b", "to": "t", "capacity": 2, "flow": 2},
]


def _params(**extra):
    return {"nodes": NODES, "edges": EDGES, "source": "s", "sink": "t", **extra}


def test_template_is_registered():
    assert "network_flow" in DIAGRAM_REGISTRY


def test_feasible_flow_renders_flow_over_capacity_labels():
    svg = render_diagram({"type": "network_flow", "params": _params()})
    assert "flow value = 4" in svg
    for label in ("2/3", "2/2", "0/1"):
        assert label in svg


def test_capacity_violation_is_refused():
    edges = [dict(edge) for edge in EDGES]
    edges[0]["flow"] = 4
    findings = refusal_findings("network_flow", _params(edges=edges))
    assert findings[0].check == "flow_bounds"


def test_conservation_violation_is_refused():
    edges = [dict(edge) for edge in EDGES]
    edges[3]["flow"] = 1
    findings = refusal_findings("network_flow", _params(edges=edges))
    assert findings[0].check == "flow_conservation"
    assert "a" in findings[0].message


def test_claimed_flow_value_is_computed_not_trusted():
    findings = refusal_findings("network_flow", _params(value=5))
    assert findings[0].check == "flow_value"
    assert "computed 4" in findings[0].message


def test_max_flow_can_be_certified_by_matching_cut():
    params = _params(cut=["s", "a", "b"], claim_max_flow=True)
    svg = render_diagram({"type": "network_flow", "params": params})
    assert "flow value = 4 · cut capacity = 4" in svg


def test_false_max_flow_claim_is_refused():
    params = _params(cut=["s"], claim_max_flow=True)
    findings = refusal_findings("network_flow", params)
    assert findings[0].check == "max_flow_claim"
    assert "cut capacity 5" in findings[0].message


def test_valid_residual_augmenting_path_is_highlighted():
    # Reverse a unit of existing flow along a→s, then continue s→a is not
    # possible in one simple s-t path here; use a zero-flow network instead.
    edges = [{**edge, "flow": 0} for edge in EDGES]
    params = _params(edges=edges, augmenting_path=["s", "a", "t"], show_residual=True)
    svg = render_diagram({"type": "network_flow", "params": params})
    assert "r=3" in svg and "r=2" in svg
    assert "graph-edge-path" in svg


def test_path_without_residual_capacity_is_refused():
    params = _params(augmenting_path=["s", "b", "t"])
    findings = refusal_findings("network_flow", params)
    assert findings[0].check == "augmenting_path"
    assert "no capacity" in findings[0].message


def test_residual_view_contains_reverse_edges_for_positive_flow():
    svg = render_diagram({"type": "network_flow",
                          "params": _params(show_residual=True)})
    # s→b is saturated, so only its reverse residual edge remains with r=2.
    assert "r=2" in svg
    assert "graph-edge-weight" in svg


def _node_centres(svg):
    return sorted(re.findall(r'<circle[^>]*cx="([\d.]+)"[^>]*cy="([\d.]+)"', svg))


def test_residual_view_keeps_the_flow_networks_vertex_positions():
    from straightedge.diagrams.legibility import check_figure
    flow = render_diagram({"type": "network_flow", "params": _params(cut=["s", "a", "b"])})
    residual = render_diagram({"type": "network_flow",
                               "params": _params(cut=["s", "a", "b"], show_residual=True)})
    # Laid out by the residual arcs alone, the vertices collapsed into a
    # 112-unit-wide column; they must sit where the flow view puts them.
    assert _node_centres(residual) == _node_centres(flow)
    assert not [f for f in check_figure(residual) if f.check == "text_clipped"]
