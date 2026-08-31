from straightedge import list_templates
from straightedge.diagrams import render_diagram
from straightedge.diagrams.registry import refusal_findings
from straightedge.diagrams.templates.graph_algorithm import (
    _coloring, _dijkstra, _kruskal, _matching, compute_steps, frames_from_steps,
)


NODES = [{"id": x} for x in "ABCD"]
STABLE_PROPOSERS = {
    "A": ["4", "3", "1", "2"], "B": ["3", "4", "2", "1"],
    "C": ["1", "2", "4", "3"], "D": ["1", "4", "3", "2"],
}
STABLE_RECEIVERS = {
    "1": ["B", "A", "C", "D"], "2": ["A", "B", "D", "C"],
    "3": ["D", "A", "B", "C"], "4": ["C", "B", "A", "D"],
}


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


def test_new_algorithm_refusals_have_structured_ids_and_labels():
    malformed_cycle = refusal_findings("graph_algorithm", {
        "algorithm": "ear_decomposition", "nodes": [{"id": "A"}],
        "edges": [], "start_cycle": "ABC",
    })[0]
    assert malformed_cycle.check == "graph_algorithm_input"

    articulation = refusal_findings("graph_algorithm", {
        "algorithm": "ear_decomposition", "nodes": [{"id": x} for x in "ABC"],
        "edges": [{"from": "A", "to": "B"}, {"from": "B", "to": "C"}],
    })[0]
    assert articulation.check == "graph_algorithm_connectivity"
    assert articulation.label == "B"

    missing_edge = refusal_findings("graph_algorithm", {
        "algorithm": "ear_decomposition", "nodes": [{"id": x} for x in "ABCD"],
        "edges": [{"from": "A", "to": "B"}, {"from": "B", "to": "C"},
                  {"from": "C", "to": "D"}, {"from": "D", "to": "A"}],
        "start_cycle": ["A", "B", "D", "A"],
    })[0]
    assert missing_edge.check == "graph_algorithm_edges"
    assert missing_edge.label == "B–D"

    bad_code = refusal_findings("graph_algorithm", {
        "algorithm": "prufer_decode", "code": [1, 9],
    })[0]
    assert bad_code.check == "graph_algorithm_code"
    assert bad_code.label == "2, 9"


def test_hamiltonian_expect_array_is_refused_instead_of_raising_type_error():
    finding = refusal_findings("graph_algorithm", {
        "algorithm": "hamiltonian_search", "nodes": [{"id": x} for x in "ABC"],
        "edges": [{"from": "A", "to": "B"}, {"from": "B", "to": "C"},
                  {"from": "C", "to": "A"}],
        "expect": ["A", "B", "C", "A"],
    })[0]
    assert finding.check == "graph_algorithm_input"
    assert "cycle or none" in finding.message


def test_catalog_publishes_the_input_tie_break_default():
    template = {item.id: item for item in list_templates()}["graph_algorithm"]
    tie_break = next(parameter for parameter in template.parameters
                     if parameter["name"] == "tie_break")
    assert tie_break["default"] == "input"


def test_prufer_encode_and_decode_draw_the_course_instance():
    tree = {"nodes": [{"id": str(i)} for i in range(1, 7)],
            "edges": [{"from": a, "to": b} for a, b in
                      [("1", "3"), ("2", "3"), ("3", "4"), ("4", "5"), ("4", "6")]]}
    encoded = render_diagram({"type": "graph_algorithm", "params": {
        **tree, "algorithm": "prufer_encode", "expect": [3, 3, 4, 4], "animate": False}})
    assert "Delete 2" in encoded
    assert compute_steps({**tree, "algorithm": "prufer_encode"})[-1].panel == (
        "code: (3, 3, 4, 4)",)
    decoded = render_diagram({"type": "graph_algorithm", "params": {
        "algorithm": "prufer_decode", "code": [3, 3, 4, 4], "animate": True}})
    assert "Add 5–4" in decoded
    assert "join final leaves" in compute_steps(
        {"algorithm": "prufer_decode", "code": [3, 3, 4, 4]})[-1].caption


def test_prufer_template_refuses_the_first_mismatching_code_position():
    finding = refusal_findings("graph_algorithm", {
        "algorithm": "prufer_encode", "nodes": [{"id": str(i)} for i in range(1, 5)],
        "edges": [{"from": "1", "to": "3"}, {"from": "2", "to": "3"},
                  {"from": "3", "to": "4"}], "expect": [3, 4]})[0]
    assert "position 2" in finding.message and finding.label.startswith("2")


def test_tree_center_draws_jordans_leaf_stripping_certificate():
    params = {"algorithm": "tree_center", "show_eccentricities": True,
              "nodes": [{"id": str(i)} for i in range(1, 9)],
              "edges": [{"from": a, "to": b} for a, b in
                        [("1", "2"), ("2", "3"), ("3", "4"), ("4", "5"),
                         ("5", "6"), ("3", "7"), ("4", "8")]], "animate": False}
    svg = render_diagram({"type": "graph_algorithm", "params": params})
    assert "Centers" in svg
    steps = compute_steps(params)
    assert steps[-1].panel == ("center: {3, 4}", "radius = 3 · diameter = 5")
    assert all(step.node_states.get("3") != "target" for step in steps[:-1])


def test_tree_center_template_refuses_a_non_tree():
    finding = refusal_findings("graph_algorithm", {
        "algorithm": "tree_center", "nodes": [{"id": x} for x in "ABC"],
        "edges": [{"from": "A", "to": "B"}, {"from": "B", "to": "C"},
                  {"from": "C", "to": "A"}]})[0]
    assert finding.check == "graph_algorithm_cycle"
    assert set(finding.label.split(" → ")) == {"A", "B", "C"}


def test_ear_decomposition_draws_numbered_colored_ears():
    params = {"algorithm": "ear_decomposition", "nodes": [{"id": str(i)} for i in range(6)],
              "edges": [{"from": str(a), "to": str(b)} for a, b in
                        [(0, 1), (1, 2), (2, 0), (3, 4), (4, 5), (5, 3),
                         (0, 3), (1, 4), (2, 5)]],
              "start_cycle": [2, 1, 0, 2], "animate": False}
    svg = render_diagram({"type": "graph_algorithm", "params": params})
    assert all(label in svg for label in ("P0", "P1", "P2", "P3"))
    final = frames_from_steps(params, compute_steps(params))[-1]["visual"]["params"]
    assert set(final["highlights"]["color_edges"]) == {
        "color-1", "color-2", "color-3", "color-4"}


def test_ear_decomposition_template_names_the_cut_vertex():
    finding = refusal_findings("graph_algorithm", {
        "algorithm": "ear_decomposition", "nodes": [{"id": x} for x in "ABCDE"],
        "edges": [{"from": a, "to": b} for a, b in
                  [("A", "B"), ("B", "C"), ("C", "A"),
                   ("C", "D"), ("D", "E"), ("E", "C")]]})[0]
    assert finding.label == "C" and "articulation" in finding.message


def test_stable_matching_draws_ten_proposals_and_the_course_outcome():
    params = {"algorithm": "stable_matching", "proposers": STABLE_PROPOSERS,
              "receivers": STABLE_RECEIVERS, "animate": False}
    svg = render_diagram({"type": "graph_algorithm", "params": params})
    assert "Stable matching" in svg
    final = compute_steps(params)[-1]
    assert final.extras["matching"] == {"A": "1", "B": "4", "C": "2", "D": "3"}
    assert final.panel[1] == "proposals = 10"


def test_stable_matching_template_refuses_with_the_blocking_pair():
    finding = refusal_findings("graph_algorithm", {
        "algorithm": "stable_matching", "proposers": STABLE_PROPOSERS,
        "receivers": STABLE_RECEIVERS,
        "check": {"A": "4", "B": "3", "C": "1", "D": "2"}})[0]
    assert finding.label == "D–3" and "blocking pair" in finding.message


def test_hamiltonian_search_draws_a_bounded_octahedron_trace():
    params = {"algorithm": "hamiltonian_search", "start": "0", "max_frames": 8,
              "expect": "cycle", "nodes": [{"id": str(i)} for i in range(6)],
              "edges": [{"from": str(a), "to": str(b)}
                        for a in range(6) for b in range(a + 1, 6)
                        if {a, b} not in ({0, 1}, {2, 3}, {4, 5})], "animate": True}
    svg = render_diagram({"type": "graph_algorithm", "params": params})
    assert "Hamiltonian cycle" in svg
    assert len(compute_steps(params)) <= 8


def test_hamiltonian_search_refuses_a_false_cycle_expectation():
    finding = refusal_findings("graph_algorithm", {
        "algorithm": "hamiltonian_search", "start": "0", "expect": "cycle",
        "nodes": [{"id": str(i)} for i in range(10)],
        "edges": [{"from": str(a), "to": str(b)} for a, b in
                  [(0, 1), (1, 2), (2, 3), (3, 4), (4, 0),
                   (0, 5), (1, 6), (2, 7), (3, 8), (4, 9),
                   (5, 7), (7, 9), (9, 6), (6, 8), (8, 5)]]})[0]
    assert "exhausted" in finding.message and finding.label.startswith("exhausted")


def test_edge_coloring_draws_k6_round_robin_classes():
    params = {"algorithm": "edge_coloring", "expect": 5,
              "nodes": [{"id": str(i)} for i in range(6)],
              "edges": [{"from": str(a), "to": str(b)}
                        for a in range(6) for b in range(a + 1, 6)], "animate": False}
    svg = render_diagram({"type": "graph_algorithm", "params": params})
    assert "Color class 5" in svg
    final = frames_from_steps(params, compute_steps(params))[-1]["visual"]["params"]
    assert set(final["highlights"]["color_edges"]) == {
        "color-1", "color-2", "color-3", "color-4", "color-5"}


def test_edge_coloring_refuses_adjacent_edges_in_one_authored_class():
    finding = refusal_findings("graph_algorithm", {
        "algorithm": "edge_coloring", "nodes": [{"id": x} for x in "ABC"],
        "edges": [{"from": "A", "to": "B"}, {"from": "A", "to": "C"}],
        "classes": [[["A", "B"], ["A", "C"]]]})[0]
    assert finding.label == "A" and "share vertex" in finding.message


def test_degeneracy_ordering_draws_petersen_deletions_then_coloring():
    params = {"algorithm": "degeneracy_ordering",
              "nodes": [{"id": str(i)} for i in range(10)],
              "edges": [{"from": str(a), "to": str(b)} for a, b in
                        [(0, 1), (1, 2), (2, 3), (3, 4), (4, 0),
                         (0, 5), (1, 6), (2, 7), (3, 8), (4, 9),
                         (5, 7), (7, 9), (9, 6), (6, 8), (8, 5)]],
              "animate": False}
    svg = render_diagram({"type": "graph_algorithm", "params": params})
    assert "Reverse greedy coloring" in svg
    steps = compute_steps(params)
    assert steps[-1].extras["degeneracy"] == 3
    assert len(steps[-1].extras["classes"]) == 3


def test_degeneracy_ordering_obeys_the_graph_trace_vertex_cap():
    finding = refusal_findings("graph_algorithm", {
        "algorithm": "degeneracy_ordering", "nodes": [{"id": str(i)} for i in range(12)],
        "edges": []})[0]
    assert finding.check == "graph_algorithm_size" and "11 vertices" in finding.message


def test_topological_sort_routes_fifo_and_min_tie_breaks():
    params = {"algorithm": "topological_sort", "directed": True,
              "nodes": [{"id": x} for x in "ABCD"],
              "edges": [{"from": "A", "to": "D"}, {"from": "B", "to": "C"}]}
    assert compute_steps({**params, "tie_break": "fifo"})[-1].panel == (
        "order: A, B, D, C",)
    assert compute_steps({**params, "tie_break": "min"})[-1].panel == (
        "order: A, B, C, D",)
    finding = refusal_findings("graph_algorithm", {**params, "tie_break": "random"})[0]
    assert "tie_break must be input, min, or fifo" in finding.message


def test_topological_sort_matches_both_course_d8_orders():
    params = {"algorithm": "topological_sort", "directed": True,
              "nodes": [{"id": x} for x in "ABCDEFGH"],
              "edges": [{"from": a, "to": b} for a, b in
                        [("A", "C"), ("B", "C"), ("B", "D"), ("C", "E"),
                         ("D", "E"), ("D", "F"), ("E", "G"), ("F", "G"),
                         ("H", "F")]]}
    assert compute_steps({**params, "tie_break": "min"})[-1].panel == (
        "order: A, B, C, D, E, H, F, G",)
    assert compute_steps({**params, "tie_break": "fifo"})[-1].panel == (
        "order: A, B, H, C, D, E, F, G",)


def test_scc_storyboard_names_kosaraju_and_draws_the_condensation():
    params = {"algorithm": "scc", "directed": True,
              "nodes": [{"id": x} for x in "ABCDEFGH"],
              "edges": [{"from": a, "to": b} for a, b in
                        [("A", "B"), ("B", "C"), ("C", "A"), ("B", "D"),
                         ("D", "E"), ("E", "F"), ("F", "D"), ("G", "F"),
                         ("G", "H"), ("H", "G")]], "animate": False}
    svg = render_diagram({"type": "graph_algorithm", "params": params})
    assert "Kosaraju: finish order" in svg and "Condensation DAG" in svg
    final = frames_from_steps(params, compute_steps(params))[-1]["visual"]["params"]
    assert final["layout"] == "hierarchical" and final["directed"] is True
    assert len(final["nodes"]) == 3 and len(final["edges"]) == 2


def test_failed_bipartite_matching_finishes_on_the_hall_violator():
    params = {"algorithm": "bipartite_matching",
              "nodes": [{"id": x} for x in list("abcde") + list("12345")],
              "edges": [{"from": a, "to": b} for a, b in
                        [("a", "1"), ("a", "2"), ("b", "1"), ("b", "2"),
                         ("c", "1"), ("c", "2"), ("c", "3"), ("d", "3"),
                         ("e", "3"), ("e", "4"), ("e", "5")]],
              "partitions": {"X": list("abcde"), "Y": list("12345")},
              "animate": False}
    svg = render_diagram({"type": "graph_algorithm", "params": params})
    assert "Hall violator" in svg
    steps = compute_steps(params)
    assert steps[-1].extras["S"] == list("abcd")
    assert steps[-1].extras["neighbors"] == ["1", "2", "3"]
    assert all("Hall" not in step.label for step in steps[:-1])


def test_scc_condensation_yields_to_a_full_storyboard():
    """The condensation DAG is a summary panel. Appending it to a trace that
    already filled the 12-panel storyboard turned a previously renderable
    figure into a refusal; unrequested, it yields instead. Asking for it
    explicitly keeps the refusal, and the animated lane has room for it."""
    params = {"algorithm": "scc", "directed": True, "animate": False,
              "nodes": [{"id": x} for x in "ABCDEFGHIJK"],
              "edges": [{"from": "A", "to": "B"}]}
    assert refusal_findings("graph_algorithm", params) == []
    steps = compute_steps(params)
    assert len(steps) == 12 and steps[-1].label == "Component 11"
    explicit = refusal_findings("graph_algorithm", {**params, "condensation": True})
    assert explicit and "13 steps" in explicit[0].message
    animated = compute_steps({**params, "animate": True})
    assert animated[-1].label == "Condensation DAG"


def test_scc_condensation_false_drops_the_summary_panel():
    params = {"algorithm": "scc", "directed": True, "condensation": False,
              "nodes": [{"id": x} for x in "ABC"],
              "edges": [{"from": "A", "to": "B"}]}
    assert all(step.label != "Condensation DAG" for step in compute_steps(params))


def test_half_named_partitions_are_refused_not_guessed():
    """With only one of left/right named, dict order decided the sides — so an
    array literally named "right" beside any other key became the proposing
    *left* side, flipping S and N(S) in every Hall panel."""
    params = {"algorithm": "bipartite_matching",
              "nodes": [{"id": x} for x in ("r1", "r2", "s1", "s2")],
              "edges": [{"from": "r1", "to": "s1"}, {"from": "r2", "to": "s2"}],
              "partitions": {"right": ["r1", "r2"], "students": ["s1", "s2"]}}
    finding = refusal_findings("graph_algorithm", params)[0]
    assert "must name both" in finding.message
    renamed = {**params, "partitions": {"proposers": ["r1", "r2"],
                                        "students": ["s1", "s2"]}}
    assert refusal_findings("graph_algorithm", renamed) == []


def test_the_graph_template_refuses_half_named_partitions_too():
    finding = [f for f in refusal_findings("graph", {
        "layout": "bipartite",
        "nodes": [{"id": x} for x in ("r1", "r2", "s1", "s2")],
        "edges": [{"from": "r1", "to": "s1"}, {"from": "r2", "to": "s2"}],
        "partitions": {"right": ["r1", "r2"], "students": ["s1", "s2"]},
    }) if f.check == "bipartition"][0]
    assert "must name both" in finding.message


# ------------------------------------------------ review findings on PR #31


def test_hamiltonian_search_storyboard_default_fits_the_panel_budget():
    """max_frames defaulted to 20 in both lanes, so the storyboard lane
    refused its own default parameters on the course octahedron; the default
    is now sized to the lane's budget."""
    params = {"algorithm": "hamiltonian_search", "start": "0", "animate": False,
              "nodes": [{"id": str(i)} for i in range(6)],
              "edges": [{"from": str(a), "to": str(b)}
                        for a in range(6) for b in range(a + 1, 6)
                        if {a, b} not in ({0, 1}, {2, 3}, {4, 5})]}
    assert not refusal_findings("graph_algorithm", params)
    svg = render_diagram({"type": "graph_algorithm", "params": params})
    assert svg and "Hamiltonian cycle" in svg


def test_render_computes_the_steps_once(monkeypatch):
    """refusal_findings computed the steps and _frames recomputed them,
    doubling every exponential search per successful render."""
    import straightedge.diagrams.templates.graph_algorithm as module
    calls = []
    original = module.compute_steps
    monkeypatch.setattr(module, "compute_steps",
                        lambda params: calls.append(1) or original(params))
    params = {"algorithm": "hamiltonian_search", "start": "0",
              "nodes": [{"id": str(i)} for i in range(6)],
              "edges": [{"from": str(a), "to": str(b)}
                        for a in range(6) for b in range(a + 1, 6)
                        if {a, b} not in ({0, 1}, {2, 3}, {4, 5})]}
    assert render_diagram({"type": "graph_algorithm", "params": params})
    assert len(calls) == 1
