"""Graph-theory-specific contracts for the general graph template."""

import re

from straightedge.diagrams import render_diagram
from straightedge.diagrams.registry import refusal_findings


def _vertices(*names):
    return [{"id": name, "label": name} for name in names]


def test_bipartite_layout_infers_two_columns_deterministically():
    hint = {
        "type": "graph",
        "params": {
            "nodes": _vertices("u1", "u2", "v1", "v2", "v3"),
            "edges": [
                {"from": "u1", "to": "v1"},
                {"from": "u1", "to": "v2"},
                {"from": "u2", "to": "v2"},
                {"from": "u2", "to": "v3"},
            ],
            "layout": "bipartite",
        },
    }
    svg = render_diagram(hint)
    circles = re.findall(r'<circle cx="([\d.]+)" cy="([\d.]+)"', svg)
    assert len(circles) == 5
    assert len({float(x) for x, _ in circles}) == 2
    assert render_diagram(hint) == svg


def test_explicit_partitions_and_labels_render():
    svg = render_diagram({
        "type": "graph",
        "params": {
            "nodes": _vertices("a", "b", "1", "2"),
            "edges": [{"from": "a", "to": "1"}, {"from": "b", "to": "2"}],
            "layout": "bipartite",
            "partitions": {"left": ["a", "b"], "right": ["1", "2"]},
            "partition_labels": {"left": "U", "right": "V"},
        },
    })
    assert "graph-partition-label" in svg
    assert ">U<" in svg and ">V<" in svg


def test_odd_cycle_is_refused_instead_of_drawn_as_bipartite():
    params = {
        "nodes": _vertices("A", "B", "C"),
        "edges": [
            {"from": "A", "to": "B"},
            {"from": "B", "to": "C"},
            {"from": "C", "to": "A"},
        ],
        "layout": "bipartite",
    }
    findings = refusal_findings("graph", params)
    assert findings
    assert findings[0].check == "bipartition"
    assert "odd cycle" in findings[0].message
    assert render_diagram({"type": "graph", "params": params}) == ""


def test_declared_partition_is_checked_against_edges():
    params = {
        "nodes": _vertices("A", "B", "C"),
        "edges": [{"from": "A", "to": "B"}],
        "layout": "bipartite",
        "partitions": {"left": ["A", "B"], "right": ["C"]},
    }
    findings = refusal_findings("graph", params)
    assert any("within one partition" in finding.message for finding in findings)


def test_unknown_edge_endpoint_is_reported_for_checked_layout():
    params = {
        "nodes": _vertices("A"),
        "edges": [{"from": "A", "to": "missing"}],
        "layout": "bipartite",
    }
    findings = refusal_findings("graph", params)
    assert findings[0].check == "graph_endpoints"
    assert "missing" in findings[0].message


def test_undirected_degree_counts_loop_twice():
    svg = render_diagram({
        "type": "graph",
        "params": {
            "nodes": _vertices("A", "B"),
            "edges": [{"from": "A", "to": "A"}, {"from": "A", "to": "B"}],
            "show_degrees": True,
            "layout": "circular",
        },
    })
    labels = re.findall(r'class="graph-degree-label"[^>]*>([^<]+)<', svg)
    assert sorted(labels) == ["deg 1", "deg 3"]


def test_directed_degree_reports_in_and_out_separately():
    svg = render_diagram({
        "type": "graph",
        "params": {
            "nodes": _vertices("A", "B"),
            "edges": [{"from": "A", "to": "B"}, {"from": "A", "to": "A"}],
            "directed": True,
            "show_degrees": True,
        },
    })
    labels = re.findall(r'class="graph-degree-label"[^>]*>([^<]+)<', svg)
    assert sorted(labels) == ["in 1 · out 0", "in 1 · out 2"]


def test_partition_headings_clear_the_degree_labels():
    from straightedge.diagrams.legibility import check_figure
    svg = render_diagram({"type": "graph", "params": {
        "nodes": [{"id": x} for x in "ABCDEF"],
        "edges": [{"from": a, "to": b} for a, b in
                  [("A", "D"), ("A", "E"), ("B", "E"), ("C", "F"), ("B", "F")]],
        "layout": "bipartite",
        "show_degrees": True,
        "partition_labels": {"left": "L", "right": "R"},
    }})
    assert "deg 2" in svg and ">L<" in svg
    problems = [f for f in check_figure(svg)
                if f.check in {"text_overlap", "text_clipped"}]
    assert problems == []


def test_a_caption_wider_than_the_drawing_is_kept_inside_the_frame():
    from straightedge.diagrams.legibility import check_figure
    svg = render_diagram({"type": "graph", "params": {
        "nodes": [{"id": "s"}, {"id": "t"}],
        "edges": [{"from": "s", "to": "t"}],
        "layout": "hierarchical",
        "caption": "flow value = 4 · cut capacity = 4 · augmenting path: none",
    }})
    assert not [f for f in check_figure(svg) if f.check == "text_clipped"]
