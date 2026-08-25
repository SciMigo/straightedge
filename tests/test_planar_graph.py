"""A planar template checks the supplied embedding, not only the abstract graph."""

from straightedge.diagrams import DIAGRAM_REGISTRY, render_diagram
from straightedge.diagrams.registry import refusal_findings


def _node(name, x, y):
    return {"id": name, "label": name, "x": x, "y": y}


def test_template_is_registered():
    assert "planar_graph" in DIAGRAM_REGISTRY


def test_checked_k4_embedding_renders_and_verifies_euler():
    # K4 is planar: put D inside triangle ABC.
    params = {
        "nodes": [_node("A", 0.1, 0.1), _node("B", 0.9, 0.1),
                  _node("C", 0.5, 0.9), _node("D", 0.5, 0.42)],
        "edges": [{"from": a, "to": b} for a, b in
                  [("A", "B"), ("B", "C"), ("C", "A"),
                   ("A", "D"), ("B", "D"), ("C", "D")]],
        "faces": 4,
    }
    svg = render_diagram({"type": "planar_graph", "params": params})
    assert "V=4, E=6, F=4" in svg
    assert svg.count("graph-edge") >= 6


def test_crossing_straight_line_embedding_is_refused():
    params = {
        "nodes": [_node("A", 0, 0), _node("B", 1, 1),
                  _node("C", 0, 1), _node("D", 1, 0)],
        "edges": [{"from": "A", "to": "B"}, {"from": "C", "to": "D"}],
    }
    findings = refusal_findings("planar_graph", params)
    assert findings[0].check == "planar_crossing"
    assert "cross" in findings[0].message


def test_wrong_face_count_is_refused_by_euler_formula():
    params = {
        "nodes": [_node("A", 0, 0), _node("B", 1, 0), _node("C", 0.5, 1)],
        "edges": [{"from": "A", "to": "B"}, {"from": "B", "to": "C"},
                  {"from": "C", "to": "A"}],
        "faces": 1,
    }
    findings = refusal_findings("planar_graph", params)
    assert findings[0].check == "euler_formula"
    assert "V − E + F" in findings[0].message


def test_disconnected_euler_formula_uses_component_count():
    params = {
        "nodes": [_node("A", 0, 0), _node("B", 0.3, 0),
                  _node("C", 0.7, 0), _node("D", 1, 0)],
        "edges": [{"from": "A", "to": "B"}, {"from": "C", "to": "D"}],
        "faces": 1,
    }
    assert not refusal_findings("planar_graph", params)


def test_coordinates_are_required_for_a_claimed_embedding():
    params = {"nodes": [{"id": "A"}, {"id": "B"}],
              "edges": [{"from": "A", "to": "B"}]}
    assert refusal_findings("planar_graph", params)[0].check == "planar_embedding"


def test_loops_and_parallel_edges_are_outside_the_checked_simple_graph_surface():
    nodes = [_node("A", 0, 0), _node("B", 1, 0)]
    loop = {"nodes": nodes, "edges": [{"from": "A", "to": "A"}]}
    parallel = {"nodes": nodes, "edges": [{"from": "A", "to": "B"},
                                            {"from": "B", "to": "A"}]}
    assert refusal_findings("planar_graph", loop)[0].check == "planar_simple_graph"
    assert refusal_findings("planar_graph", parallel)[0].check == "planar_simple_graph"
