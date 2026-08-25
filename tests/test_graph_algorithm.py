from straightedge.diagrams import render_diagram
from straightedge.diagrams.registry import refusal_findings
from straightedge.diagrams.templates.graph_algorithm import _coloring, _dijkstra, _kruskal, _matching


NODES = [{"id": x} for x in "ABCD"]


def test_dijkstra_computes_an_animated_svg_with_distances():
    svg = render_diagram({"type": "graph_algorithm", "params": {
        "algorithm": "dijkstra", "nodes": NODES, "start": "A",
        "edges": [{"from": "A", "to": "B", "weight": 2},
                  {"from": "A", "to": "C", "weight": 5},
                  {"from": "B", "to": "C", "weight": 1},
                  {"from": "C", "to": "D", "weight": 1}],
        "animate": True,
    }})
    assert "<animate " in svg
    assert "Settle D" in svg
    frames = _dijkstra({"algorithm": "dijkstra", "nodes": NODES, "start": "A",
                        "edges": [{"from": "A", "to": "B", "weight": 2},
                                  {"from": "A", "to": "C", "weight": 5},
                                  {"from": "B", "to": "C", "weight": 1},
                                  {"from": "C", "to": "D", "weight": 1}]})
    assert frames[-1]["visual"]["params"]["distance_labels"]["D"] == "4"


def test_dijkstra_refuses_negative_weights():
    findings = refusal_findings("graph_algorithm", {
        "algorithm": "dijkstra", "nodes": NODES[:2], "start": "A",
        "edges": [{"from": "A", "to": "B", "weight": -1}],
    })
    assert any(f.check == "graph_algorithm_weight" for f in findings)


def test_kruskal_computes_a_minimum_spanning_forest_storyboard():
    svg = render_diagram({"type": "graph_algorithm", "params": {
        "algorithm": "kruskal", "nodes": NODES,
        "edges": [{"from": "A", "to": "B", "weight": 7},
                  {"from": "A", "to": "C", "weight": 1},
                  {"from": "B", "to": "C", "weight": 2},
                  {"from": "C", "to": "D", "weight": 3}],
        "animate": False,
    }})
    assert "Accept A–C" in svg
    frames = _kruskal({"algorithm": "kruskal", "nodes": NODES,
                       "edges": [{"from": "A", "to": "B", "weight": 7},
                                 {"from": "A", "to": "C", "weight": 1},
                                 {"from": "B", "to": "C", "weight": 2},
                                 {"from": "C", "to": "D", "weight": 3}]})
    assert "forest weight = 6" in frames[-1]["visual"]["params"]["caption"]
    # The edge that would close a cycle is drawn as rejected, not omitted.
    assert any(f["visual"]["params"]["highlights"]["rejected_edges"] for f in frames)


def test_greedy_coloring_assigns_visible_valid_colors():
    svg = render_diagram({"type": "graph_algorithm", "params": {
        "algorithm": "greedy_coloring", "nodes": NODES[:3],
        "edges": [{"from": "A", "to": "B"}, {"from": "B", "to": "C"},
                  {"from": "C", "to": "A"}],
        "vertex_order": ["A", "B", "C"], "animate": True,
    }})
    last = _coloring({"algorithm": "greedy_coloring", "nodes": NODES[:3],
                      "edges": [{"from": "A", "to": "B"}, {"from": "B", "to": "C"},
                                {"from": "C", "to": "A"}],
                      "vertex_order": ["A", "B", "C"]})[-1]["visual"]["params"]
    assert set(last["highlights"]["nodes"].values()) == {"color-1", "color-2", "color-3"}


def test_matching_computes_augmenting_states():
    svg = render_diagram({"type": "graph_algorithm", "params": {
        "algorithm": "bipartite_matching",
        "nodes": [{"id": x} for x in ("u1", "u2", "v1", "v2")],
        "edges": [{"from": "u1", "to": "v1"}, {"from": "u1", "to": "v2"},
                  {"from": "u2", "to": "v1"}],
        "partitions": {"left": ["u1", "u2"], "right": ["v1", "v2"]},
        "animate": True,
    }})
    frames = _matching({"algorithm": "bipartite_matching",
                        "nodes": [{"id": x} for x in ("u1", "u2", "v1", "v2")],
                        "edges": [{"from": "u1", "to": "v1"}, {"from": "u1", "to": "v2"},
                                  {"from": "u2", "to": "v1"}],
                        "partitions": {"left": ["u1", "u2"], "right": ["v1", "v2"]}})
    assert "matching size = 2" in frames[-1]["visual"]["params"]["caption"]
    assert "Augment from u2" in svg


def test_matching_refuses_an_edge_inside_one_partition():
    findings = refusal_findings("graph_algorithm", {
        "algorithm": "bipartite_matching", "nodes": NODES,
        "edges": [{"from": "A", "to": "B"}],
        "partitions": {"left": ["A", "B"], "right": ["C", "D"]},
    })
    assert any(f.check == "graph_algorithm_bipartite" for f in findings)


def test_every_color_the_greedy_algorithm_can_assign_has_a_style():
    import re
    from straightedge.diagrams.templates.graph import GraphTemplate
    from straightedge.diagrams.templates.graph_algorithm import MAX_VERTICES
    styled = {int(n) for n in re.findall(r"\.graph-node-color-(\d+)", GraphTemplate._extra_styles())}
    # A complete graph on the largest allowed vertex set needs one colour per
    # vertex; K9 used to render its last three vertices in the plain fill.
    ids = [str(index) for index in range(MAX_VERTICES)]
    frames = _coloring({"algorithm": "greedy_coloring", "nodes": [{"id": x} for x in ids],
                        "edges": [{"from": a, "to": b} for a in ids for b in ids if a < b]})
    used = {int(state.split("-")[1])
            for state in frames[-1]["visual"]["params"]["highlights"]["nodes"].values()}
    assert used == set(range(1, MAX_VERTICES + 1))
    assert used <= styled


def test_refusals_carry_the_witness_in_the_right_shape():
    cyclic = {"algorithm": "topological_sort", "directed": True,
              "nodes": [{"id": v} for v in "ABC"],
              "edges": [{"from": a, "to": b} for a, b in [("A", "B"), ("B", "C"), ("C", "A")]]}
    finding = refusal_findings("graph_algorithm", cyclic)[0]
    assert finding.check == "graph_algorithm_cycle" and finding.label == "A → B → C"
    k4 = {"algorithm": "euler", "nodes": [{"id": v} for v in "ABCD"],
          "edges": [{"from": a, "to": b} for a, b in
                    [("A", "B"), ("B", "C"), ("C", "D"), ("D", "A"), ("A", "C"), ("B", "D")]]}
    finding = refusal_findings("graph_algorithm", k4)[0]
    assert finding.check == "graph_algorithm_parity" and finding.label == "A, B, C, D"
    negative = {"algorithm": "bellman_ford", "directed": True, "start": "A",
                "nodes": [{"id": v} for v in "ABC"],
                "edges": [{"from": "A", "to": "B", "weight": 1}, {"from": "B", "to": "C", "weight": -3},
                          {"from": "C", "to": "B", "weight": 1}]}
    finding = refusal_findings("graph_algorithm", negative)[0]
    assert finding.check == "graph_algorithm_negative_cycle" and "→" in finding.label
