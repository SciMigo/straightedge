"""The graph-structure figures compute their claims before drawing them."""

from __future__ import annotations

import base64
import re

from straightedge.diagrams import DIAGRAM_REGISTRY, render_diagram
from straightedge.diagrams.templates.graph_algorithm import compute_steps
from straightedge.diagrams.templates.priority_queue import _compute as heap_states


def test_disjoint_set_computes_union_and_path_compression():
    params = {"elements": list("ABCD"), "operations": [
        {"type": "union", "a": "A", "b": "B"},
        {"type": "union", "a": "C", "b": "D"},
        {"type": "union", "a": "B", "b": "C"},
        {"type": "find", "element": "D", "expect": "A"},
    ]}
    svg = render_diagram({"type": "disjoint_set", "params": params})
    assert "<animate" in svg and "find(D)" in svg
    wrong = {**params, "operations": params["operations"][:-1] + [
        {"type": "find", "element": "D", "expect": "D"}]}
    assert DIAGRAM_REGISTRY["disjoint_set"].refusal_findings(wrong)


def test_priority_queue_checks_the_minimum_and_decrease_direction():
    params = {"items": [{"id": "A", "priority": 5}, {"id": "B", "priority": 2}],
              "operations": [{"type": "decrease_key", "id": "A", "priority": 1},
                             {"type": "pop_min", "expect": "A"}]}
    states = heap_states(params)
    assert states[-1]["label"] == "pop_min() → A"
    assert "<animate" in render_diagram({"type": "priority_queue", "params": params})
    bad = {"items": [{"id": "A", "priority": 1}],
           "operations": [{"type": "decrease_key", "id": "A", "priority": 2}]}
    assert DIAGRAM_REGISTRY["priority_queue"].refusal_findings(bad)


def test_block_cut_tree_is_derived_from_the_source_graph():
    params = {"nodes": [{"id": x} for x in "ABCD"], "edges": [
        {"from": "A", "to": "B"}, {"from": "B", "to": "C"},
        {"from": "C", "to": "A"}, {"from": "C", "to": "D"}]}
    svg = render_diagram({"type": "block_cut_tree", "params": params})
    assert "B1" in svg and "{A,B,C}" in svg and "articulation" in svg
    steps = compute_steps({**params, "algorithm": "low_link"})
    assert steps[-1].label == "Block structure"
    assert any("low" in badge for badge in steps[-1].badges.values())


def test_graph_representation_draws_all_four_equivalent_views():
    params = {"nodes": [{"id": x} for x in "ABC"], "edges": [
        {"from": "A", "to": "B"}, {"from": "B", "to": "C"}]}
    svg = render_diagram({"type": "graph_representation", "params": params})
    for label in ("Graph", "Adjacency list", "Adjacency matrix", "Incidence matrix"):
        assert label in svg
    directed = {"directed": True, "nodes": [{"id": "A"}, {"id": "B"}],
                "edges": [{"from": "A", "to": "B", "weight": 2},
                          {"from": "B", "to": "A", "weight": 7}]}
    weighted = render_diagram({"type": "graph_representation", "params": directed})
    children = "".join(base64.b64decode(data).decode("utf-8")
                       for data in re.findall(r"base64,([^\"']+)", weighted))
    assert "B (2)" in children and "A (7)" in children


# ------------------------------------------------ review findings on PR #28


def _path(n: int) -> dict:
    ids = [str(i) for i in range(n)]
    return {"nodes": [{"id": v} for v in ids],
            "edges": [{"from": a, "to": b} for a, b in zip(ids, ids[1:])]}


def test_block_cut_tree_refuses_instead_of_recursing_past_the_stack():
    findings = DIAGRAM_REGISTRY["block_cut_tree"].refusal_findings(_path(1500))
    assert findings and "at most 11 vertices" in findings[0].message


def test_block_cut_tree_grows_with_its_rows_instead_of_overlapping():
    from straightedge.diagrams.legibility import check_figure
    svg = render_diagram({"type": "block_cut_tree", "params": _path(11)})
    assert svg and not [f for f in check_figure(svg) if f.severity == "error"]


def test_priority_queue_can_be_drained_in_the_animated_lane():
    params = {"items": [{"id": "A", "priority": 1}], "operations": [{"type": "pop_min"}]}
    assert not DIAGRAM_REGISTRY["priority_queue"].refusal_findings(params)
    assert "<animate" in render_diagram({"type": "priority_queue", "params": params})


def test_graph_representation_surfaces_the_graph_panels_refusal():
    triangle = {"nodes": [{"id": x} for x in "ABC"], "edges": [
        {"from": "A", "to": "B"}, {"from": "B", "to": "C"}, {"from": "C", "to": "A"}],
        "graph_layout": "bipartite"}
    findings = DIAGRAM_REGISTRY["graph_representation"].refusal_findings(triangle)
    assert findings and "odd cycle" in findings[0].message
    assert render_diagram({"type": "graph_representation", "params": triangle}) == ""


def test_graph_representation_keeps_a_zero_weight_edge_visible_in_the_matrix():
    params = {"nodes": [{"id": x} for x in "ABC"], "edges": [
        {"from": "A", "to": "B", "weight": 0}, {"from": "B", "to": "C", "weight": 2.0}]}
    svg = render_diagram({"type": "graph_representation", "params": params})
    children = "".join(base64.b64decode(data).decode("utf-8")
                       for data in re.findall(r"base64,([^\"']+)", svg))
    assert ">·<" in children and ">0<" in children  # absent vs weight 0
    assert ">2<" in children  # the matrix formats the weight with :g


def test_graph_representation_highlights_one_edge_in_every_view():
    params = {"nodes": [{"id": x} for x in "ABC"], "edges": [
        {"from": "A", "to": "B"}, {"from": "B", "to": "C"}],
        "highlight": ["A", "B"]}
    svg = render_diagram({"type": "graph_representation", "params": params})
    children = "".join(base64.b64decode(data).decode("utf-8")
                       for data in re.findall(r"base64,([^\"']+)", svg))
    assert "graph-edge graph-edge-highlight" in children
    assert children.count("matrix-cell matrix-cell-current") >= 5


def test_nary_tree_supports_paths_highlights_and_label_size():
    svg = render_diagram({"type": "tree", "params": {
        "root": {"value": "r", "children": [
            {"value": "a"}, {"value": "b"}, {"value": "c"}]},
        "path": ["r", "b"], "highlights": {"b": "current"},
        "label_size": 17,
    }})
    assert svg.count('class="tree-node ') == 4
    assert "tree-edge tree-edge-path" in svg
    assert "tree-node tree-node-current" in svg
    assert "font-size: 17px" in svg


def test_low_link_storyboard_draws_the_bridge_unlike_a_tree_edge():
    params = {"nodes": [{"id": x} for x in "ABCD"], "edges": [
        {"from": "A", "to": "B"}, {"from": "B", "to": "C"},
        {"from": "C", "to": "A"}, {"from": "C", "to": "D"}],
        "algorithm": "low_link", "animate": False}
    svg = render_diagram({"type": "graph_algorithm", "params": params})
    children = "".join(base64.b64decode(data).decode("utf-8")
                       for data in re.findall(r"base64,([^\"']+)", svg))
    assert "graph-edge graph-edge-cut" in children
    assert "graph-edge graph-edge-highlight" in children


# ------------------------------------------------ review findings on PR #31


def _decoded_children(svg: str) -> str:
    return "".join(base64.b64decode(data).decode("utf-8")
                   for data in re.findall(r"base64,([^\"']+)", svg))


def test_priority_queue_defaults_to_the_documented_heap_tree():
    """A new `view` param defaulted to "sorted", silently regenerating every
    published figure as a sorted array instead of the heap tree, with the
    caption's labels changed and a sorted array misrepresenting heap order."""
    params = {"items": [{"id": "A", "priority": 5}, {"id": "B", "priority": 2}],
              "operations": [], "animate": False}
    children = _decoded_children(render_diagram({"type": "priority_queue",
                                                 "params": params}))
    assert children.count("<circle") == 2
    assert "heap array: [B:2, A:5]" in children
    sorted_view = _decoded_children(render_diagram({
        "type": "priority_queue", "params": {**params, "view": "sorted"}}))
    assert "<circle" not in sorted_view and "(2, B)" in sorted_view
    findings = DIAGRAM_REGISTRY["priority_queue"].refusal_findings(
        {**params, "view": "array"})
    assert findings and "view must be heap or sorted" in findings[0].message


def test_binary_tree_survives_a_font_size_it_cannot_read():
    """font_size was ignored for years, then fed through bare float(): a
    '14px' that rendered fine crashed to an empty figure with the reason
    swallowed by the registry's blanket except."""
    svg = render_diagram({"type": "binary_tree", "params": {
        "root": {"value": 1, "left": {"value": 2}}, "font_size": "14px"}})
    assert svg.count("<circle") == 2 and "font-size: 13px" in svg
    floored = render_diagram({"type": "binary_tree", "params": {
        "root": {"value": 1}, "font_size": 6}})
    assert "font-size: 8px" in floored


# ---------------------------------------------- follow-up review findings


def test_tree_reports_a_malformed_root_instead_of_drawing_nothing():
    findings = DIAGRAM_REGISTRY["tree"].refusal_findings({"root": "not-a-node"})
    assert findings and "root must be an object" in findings[0].message
    assert render_diagram({"type": "tree", "params": {"root": "not-a-node"}}) == ""


def test_tree_tolerates_size_values_it_cannot_read():
    svg = render_diagram({"type": "tree", "params": {
        "root": {"value": 1, "children": [{"value": 2}]}, "font_size": "14px",
        "node_radius": "big"}})
    assert svg.count("<circle") == 2 and "font-size: 13px" in svg
