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
