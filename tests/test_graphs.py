"""The shared graph algorithms compute what they claim, and refuse with a witness.

These are the states both lanes draw from, so each algorithm is checked
against a property a textbook states rather than against a picture: Prim and
Kruskal agree on the tree weight, the max flow equals the min cut it ends on,
König's cover has the matching's size, a negative cycle is named vertex by
vertex.
"""

from __future__ import annotations

import pytest

from straightedge.graphs import (
    GraphError, bellman_ford_steps, bipartition, coerce_graph, degeneracy_ordering_steps,
    dijkstra_steps,
    connectivity_analysis, connectivity_steps, euler_steps, greedy_coloring_steps, konig_cover, kruskal_steps,
    ear_decomposition_steps, edge_coloring_steps, hamiltonian_search_steps,
    havel_hakimi_steps,
    floyd_warshall_steps, matching_steps, max_flow_steps, mycielski_graph, mycielski_steps,
    prim_steps, scc_steps, stable_matching_steps, steps_for,
    prufer_decode_graph, prufer_decode_steps, prufer_encode_steps,
    topological_sort_steps, traversal_steps, tree_center_steps, vertex_cover_steps,
)


def _graph(edges, directed=False, **node_kwargs):
    ids = sorted({v for e in edges for v in e[:2]})
    return coerce_graph({
        "directed": directed,
        "nodes": [{"id": v, **node_kwargs.get(v, {})} for v in ids],
        "edges": [({"from": a, "to": b, "weight": w} if len(e) == 3 else {"from": a, "to": b})
                  for e in edges for a, b, *rest in [e] for w in (rest or [None])],
    })


WEIGHTED = [("A", "B", 4), ("A", "C", 2), ("B", "C", 5), ("B", "D", 10),
            ("C", "E", 3), ("E", "D", 4), ("D", "F", 11)]


# ------------------------------------------------------------- coercion


def test_coercion_names_the_first_thing_it_cannot_read():
    with pytest.raises(GraphError, match="unknown vertex"):
        coerce_graph({"nodes": [{"id": "A"}], "edges": [{"from": "A", "to": "Z"}]})
    with pytest.raises(GraphError, match="loop"):
        coerce_graph({"nodes": [{"id": "A"}], "edges": [{"from": "A", "to": "A"}]})
    with pytest.raises(GraphError, match="repeated"):
        coerce_graph({"nodes": [{"id": "A"}, {"id": "B"}],
                      "edges": [{"from": "A", "to": "B"}, {"from": "B", "to": "A"}]})


def test_neighbors_follow_direction_and_the_declared_order():
    g = _graph([("A", "B"), ("A", "C"), ("C", "A")], directed=True)
    assert g.neighbors("A") == ["B", "C"]
    assert g.neighbors("A", ["C", "B"]) == ["C", "B"]
    assert g.neighbors("B") == []


# ------------------------------------------------------------ traversal


def test_dfs_is_the_recursive_procedure():
    g = _graph([("A", "B"), ("A", "C"), ("B", "C"), ("B", "D")])
    last = traversal_steps(g, "A", "dfs")[-1]
    assert last.extras["visited"] == ["A", "B", "C", "D"]
    assert last.extras["tree_edges"] == [("A", "B"), ("B", "C"), ("B", "D")]


def test_bfs_visits_by_level_and_shows_the_queue():
    g = _graph([("A", "B"), ("A", "C"), ("B", "D"), ("C", "E")])
    steps = traversal_steps(g, "A", "bfs")
    assert steps[1].extras["frontier"] == ["B", "C"]
    assert steps[1].panel[0] == "queue: [B, C]"
    assert steps[-1].extras["visited"] == list("ABCDE")


# ------------------------------------------------------- shortest paths


def test_dijkstra_settles_in_distance_order_with_a_table():
    g = _graph(WEIGHTED)
    steps = dijkstra_steps(g, "A")
    assert [s.label for s in steps[1:]] == ["Settle A", "Settle C", "Settle B",
                                            "Settle E", "Settle D", "Settle F"]
    assert steps[-1].badges == {"A": "0", "B": "4", "C": "2", "D": "9", "E": "5", "F": "20"}
    assert "F: 20" in steps[-1].panel


def test_dijkstra_refuses_a_negative_weight():
    with pytest.raises(GraphError, match="negative weight"):
        dijkstra_steps(_graph([("A", "B", -1)]), "A")


def test_bellman_ford_agrees_with_dijkstra_on_nonnegative_weights():
    g = _graph(WEIGHTED)
    assert bellman_ford_steps(g, "A")[-1].badges == dijkstra_steps(g, "A")[-1].badges


def test_bellman_ford_handles_negative_weights_and_names_a_negative_cycle():
    g = _graph([("A", "B", 4), ("B", "C", -2), ("A", "C", 5)], directed=True)
    assert bellman_ford_steps(g, "A")[-1].badges["C"] == "2"
    cyclic = _graph([("A", "B", 1), ("B", "C", -3), ("C", "B", 1)], directed=True)
    with pytest.raises(GraphError) as info:
        bellman_ford_steps(cyclic, "A")
    assert set(info.value.witness) == {"B", "C"}
    assert "negative cycle" in str(info.value)


# ------------------------------------------------------- spanning trees


def test_kruskal_shows_rejections_and_prim_agrees_on_the_weight():
    g = _graph(WEIGHTED)
    kruskal = kruskal_steps(g)
    rejected = [s.label for s in kruskal if s.label.startswith("Reject")]
    assert rejected == ["Reject B–C", "Reject B–D"]
    assert kruskal[-1].panel == ("forest weight = 24",)
    assert "rejected" in kruskal[-1].edge_states.values()
    prim = prim_steps(g, "A")
    assert prim[-1].panel == ("tree weight = 24",)
    tree = {k for k, role in prim[-1].edge_states.items() if role == "tree"}
    assert tree == {k for k, role in kruskal[-1].edge_states.items() if role == "tree"}


def test_spanning_trees_need_an_undirected_graph():
    with pytest.raises(GraphError, match="undirected"):
        kruskal_steps(_graph([("A", "B", 1)], directed=True))


# ----------------------------------------------------------- Prüfer codes


def test_prufer_code_round_trip_uses_the_course_tree():
    tree = _graph([("1", "3"), ("2", "3"), ("3", "4"), ("4", "5"), ("4", "6")])
    encoded = prufer_encode_steps(tree, [3, 3, 4, 4])
    assert encoded[-1].extras["code"] == ["3", "3", "4", "4"]
    decoded = prufer_decode_graph([3, 3, 4, 4])
    assert {decoded.key(edge.source, edge.target) for edge in decoded.edges} == {
        tree.key(edge.source, edge.target) for edge in tree.edges}
    assert len(prufer_decode_steps([3, 3, 4, 4])) == 6


def test_prufer_refuses_a_non_tree_bad_entry_and_wrong_expectation():
    with pytest.raises(GraphError, match="cycle") as cyclic:
        prufer_encode_steps(_graph([("1", "2"), ("2", "3"), ("3", "1")]))
    assert set(cyclic.value.witness[:-1]) == {"1", "2", "3"}
    with pytest.raises(GraphError, match="outside 1..4") as bad_code:
        prufer_decode_graph([3, 5])
    assert bad_code.value.witness == (2, 5)
    tree = _graph([("1", "3"), ("2", "3"), ("3", "4")])
    with pytest.raises(GraphError, match="position 2") as mismatch:
        prufer_encode_steps(tree, [3, 4])
    assert mismatch.value.witness == (2, "3", "4")


# -------------------------------------------------------- Havel–Hakimi


def test_havel_hakimi_reduces_and_realizes_the_course_sequence():
    reduced = havel_hakimi_steps([3, 3, 2, 2, 2])
    assert [step.extras["values"] for step in reduced] == [
        [3, 3, 2, 2, 2], [2, 2, 1, 1], [1, 1, 0], [0, 0]]
    realized = havel_hakimi_steps([3, 3, 2, 2, 2], realize=True)
    final = realized[-1]
    counts = {str(i): 0 for i in range(1, 6)}
    for left, right in final.extras["graph_edges"]:
        counts[left] += 1
        counts[right] += 1
    assert sorted(counts.values(), reverse=True) == [3, 3, 2, 2, 2]


def test_havel_hakimi_refuses_odd_sum_and_negative_reduction_with_witness():
    with pytest.raises(GraphError, match="odd") as odd:
        havel_hakimi_steps([2, 2, 1])
    assert odd.value.witness == (2, 2, 1)
    with pytest.raises(GraphError, match="negative") as negative:
        havel_hakimi_steps([3, 3, 3, 1])
    assert negative.value.witness == (1, -1)


# ------------------------------------------------------------ tree centres


def test_tree_center_strips_the_course_tree_and_computes_eccentricities():
    tree = _graph([("1", "2"), ("2", "3"), ("3", "4"), ("4", "5"),
                   ("5", "6"), ("3", "7"), ("4", "8")])
    steps = tree_center_steps(tree, show_eccentricities=True)
    assert steps[-1].extras == {"centers": ["3", "4"], "radius": 3, "diameter": 5}
    assert steps[-1].node_states["3"] == steps[-1].node_states["4"] == "target"
    assert steps[-2].node_states.get("3") != "target"
    assert steps[-1].badges == {"3": "ε=3", "4": "ε=3"}


def test_tree_center_refuses_a_cycle_with_its_witness():
    with pytest.raises(GraphError, match="cycle") as refused:
        tree_center_steps(_graph([("1", "2"), ("2", "3"), ("3", "1")]))
    assert set(refused.value.witness[:-1]) == {"1", "2", "3"}


# -------------------------------------------------------- ear decomposition


def test_ear_decomposition_matches_the_course_prism():
    prism = _graph([("0", "1"), ("1", "2"), ("2", "0"),
                    ("3", "4"), ("4", "5"), ("5", "3"),
                    ("0", "3"), ("1", "4"), ("2", "5")])
    steps = ear_decomposition_steps(prism, [2, 1, 0, 2])
    assert [step.extras["ears"][-1] for step in steps] == [
        ["2", "1", "0", "2"], ["0", "3", "4", "1"],
        ["2", "5", "4"], ["3", "5"]]
    assert set(steps[-1].edge_states.values()) == {
        "color-1", "color-2", "color-3", "color-4"}


def test_ear_decomposition_refuses_an_articulation_vertex():
    bowtie = _graph([("A", "B"), ("B", "C"), ("C", "A"),
                     ("C", "D"), ("D", "E"), ("E", "C")])
    with pytest.raises(GraphError, match="articulation") as refused:
        ear_decomposition_steps(bowtie)
    assert refused.value.witness == "C"


# ---------------------------------------------------------- stable matching


STABLE_PROPOSERS = {
    "A": ["3", "4", "1", "2"], "B": ["3", "4", "2", "1"],
    "C": ["1", "4", "3", "2"], "D": ["3", "4", "1", "2"],
}
STABLE_RECEIVERS = {
    "1": ["D", "A", "B", "C"], "2": ["B", "D", "C", "A"],
    "3": ["D", "B", "A", "C"], "4": ["B", "A", "D", "C"],
}


def test_gale_shapley_course_outcome_takes_ten_proposals():
    steps = stable_matching_steps(STABLE_PROPOSERS, STABLE_RECEIVERS)
    assert steps[-1].extras["matching"] == {"A": "1", "B": "4", "C": "2", "D": "3"}
    assert steps[-1].extras["proposals"] == 10
    assert len([step for step in steps if "proposes to" in step.label]) == 10


def test_stable_matching_refuses_bad_preferences_and_names_a_blocking_pair():
    with pytest.raises(GraphError, match="permutation") as preferences:
        stable_matching_steps({**STABLE_PROPOSERS, "A": ["1"]}, STABLE_RECEIVERS)
    assert preferences.value.witness == "A"
    with pytest.raises(GraphError, match="blocking pair") as unstable:
        stable_matching_steps(STABLE_PROPOSERS, STABLE_RECEIVERS,
                              {"A": "4", "B": "3", "C": "1", "D": "2"})
    assert unstable.value.witness == ("D", "3")


# ------------------------------------------------------ Hamiltonian search


def test_hamiltonian_search_finds_an_octahedron_cycle_with_bounded_frames():
    octahedron = _graph([(str(a), str(b)) for a in range(6) for b in range(a + 1, 6)
                         if {a, b} not in ({0, 1}, {2, 3}, {4, 5})])
    steps = hamiltonian_search_steps(octahedron, "0", max_frames=8, expect="cycle")
    assert len(steps) <= 8 and steps[-1].label == "Hamiltonian cycle"
    cycle = steps[-1].extras["cycle"]
    assert cycle[0] == cycle[-1] == "0" and len(set(cycle[:-1])) == 6


def test_hamiltonian_search_exhausts_petersen_and_refuses_false_expectation():
    petersen = _graph([(str(a), str(b)) for a, b in
                       [(0, 1), (1, 2), (2, 3), (3, 4), (4, 0),
                        (0, 5), (1, 6), (2, 7), (3, 8), (4, 9),
                        (5, 7), (7, 9), (9, 6), (6, 8), (8, 5)]])
    steps = hamiltonian_search_steps(petersen, "0", max_frames=10, expect="none")
    assert len(steps) <= 10 and steps[-1].extras["cycle"] is None
    assert steps[-1].extras["explored"] > 10
    with pytest.raises(GraphError, match="exhausted") as refused:
        hamiltonian_search_steps(petersen, "0", expect="cycle")
    assert refused.value.witness[0] == "exhausted"


# --------------------------------------------------------- Floyd–Warshall


def test_floyd_warshall_updates_one_checked_table_per_intermediate():
    graph = _graph([("A", "B", 3), ("A", "D", 7), ("B", "A", 8),
                    ("B", "C", 2), ("C", "A", 5), ("C", "D", 1),
                    ("D", "A", 2)], directed=True)
    steps = floyd_warshall_steps(graph)
    assert len(steps) == 5
    assert steps[-1].extras["values"] == [
        ["0", "3", "5", "6"], ["5", "0", "2", "3"],
        ["3", "6", "0", "1"], ["2", "5", "7", "0"]]
    assert steps[1].extras["k"] == "A"


def test_floyd_warshall_refuses_a_negative_cycle_with_the_cycle_witness():
    graph = _graph([("A", "B", 1), ("B", "C", -3), ("C", "A", 1)], directed=True)
    with pytest.raises(GraphError, match="diagonal entry") as refused:
        floyd_warshall_steps(graph)
    assert set(refused.value.witness) == {"A", "B", "C"}


# ---------------------------------------------------------- Mycielski graph


def test_mycielski_of_c5_is_the_triangle_free_grotzsch_graph():
    cycle = _graph([("0", "1"), ("1", "2"), ("2", "3"), ("3", "4"), ("4", "0")])
    graph = mycielski_graph(cycle)
    assert len(graph.ids) == 11 and len(graph.edges) == 20
    steps = mycielski_steps(cycle)
    assert steps[-1].extras["base_chi"] == 3
    assert steps[-1].extras["result_chi"] == 4
    assert steps[-1].extras["triangle_free"] is True
    assert max(steps[-1].extras["colors"].values()) == 4


def test_mycielski_refuses_a_base_whose_output_exceeds_the_cap():
    base = _graph([(str(i), str((i + 1) % 6)) for i in range(6)])
    with pytest.raises(GraphError, match="13 vertices") as refused:
        mycielski_graph(base)
    assert refused.value.witness == (6, 13)


# ------------------------------------------------------------ edge coloring


def test_edge_coloring_computes_k6_and_odd_cycle_chromatic_indices():
    k6 = _graph([(str(a), str(b)) for a in range(6) for b in range(a + 1, 6)])
    assert edge_coloring_steps(k6, expect=5)[-1].extras["chromatic_index"] == 5
    c5 = _graph([(str(i), str((i + 1) % 5)) for i in range(5)])
    assert edge_coloring_steps(c5, expect=3)[-1].extras["chromatic_index"] == 3


def test_edge_coloring_verifies_authored_classes_and_refuses_shared_vertex():
    k4 = _graph([(str(a), str(b)) for a in range(4) for b in range(a + 1, 4)])
    classes = [[["0", "1"], ["2", "3"]],
               [["0", "2"], ["1", "3"]],
               [["0", "3"], ["1", "2"]]]
    assert edge_coloring_steps(k4, classes, expect=3)[-1].extras["chromatic_index"] == 3
    with pytest.raises(GraphError, match="share vertex") as refused:
        edge_coloring_steps(k4, [[["0", "1"], ["0", "2"]]])
    assert refused.value.witness == "0"
    with pytest.raises(GraphError, match="below maximum degree") as too_few:
        edge_coloring_steps(k4, expect=2)
    assert too_few.value.witness == 3


# -------------------------------------------------------------- degeneracy


def test_degeneracy_ordering_colors_petersen_in_twelve_panels():
    petersen = _graph([(str(a), str(b)) for a, b in
                       [(0, 1), (1, 2), (2, 3), (3, 4), (4, 0),
                        (0, 5), (1, 6), (2, 7), (3, 8), (4, 9),
                        (5, 7), (7, 9), (9, 6), (6, 8), (8, 5)]])
    steps = degeneracy_ordering_steps(petersen)
    assert len(steps) == 12 and steps[-1].extras["degeneracy"] == 3
    assert len(steps[-1].extras["classes"]) == 3
    colors = steps[-1].extras["colors"]
    assert all(colors[edge.source] != colors[edge.target] for edge in petersen.edges)
    assert all("color-" not in role for step in steps[:-1]
               for role in step.node_states.values())


# ---------------------------------------------------------- DAGs and SCCs


def test_topological_sort_orders_a_dag_and_names_a_cycle():
    dag = _graph([("A", "B"), ("A", "C"), ("B", "D"), ("C", "D")], directed=True)
    steps = topological_sort_steps(dag)
    assert steps[-1].panel == ("order: A, B, C, D",)
    cyclic = _graph([("A", "B"), ("B", "C"), ("C", "A"), ("C", "D")], directed=True)
    with pytest.raises(GraphError) as info:
        topological_sort_steps(cyclic)
    assert set(info.value.witness) == {"A", "B", "C"}


def test_topological_sort_supports_fifo_and_minimum_tie_breaks():
    dag = coerce_graph({"directed": True, "nodes": [{"id": x} for x in "ABCD"],
                        "edges": [{"from": "A", "to": "D"},
                                  {"from": "B", "to": "C"}]})
    assert topological_sort_steps(dag, "fifo")[-1].panel == ("order: A, B, D, C",)
    assert topological_sort_steps(dag, "min")[-1].panel == ("order: A, B, C, D",)
    with pytest.raises(GraphError, match="tie_break"):
        topological_sort_steps(dag, "random")


def test_scc_finds_the_components():
    g = _graph([("A", "B"), ("B", "C"), ("C", "A"), ("C", "D"), ("D", "E"), ("E", "D")],
               directed=True)
    steps = scc_steps(g)
    components = [set(p.split("= {")[1].rstrip("}").split(", ")) for p in steps[-1].panel]
    assert {frozenset(c) for c in components} == {frozenset("ABC"), frozenset("DE")}


# ----------------------------------------------------------------- flows


def test_max_flow_ends_on_a_cut_of_equal_capacity():
    g = coerce_graph({"directed": True, "nodes": [{"id": v} for v in "sabt"],
                      "edges": [{"from": "s", "to": "a", "capacity": 3},
                                {"from": "s", "to": "b", "capacity": 2},
                                {"from": "a", "to": "b", "capacity": 1},
                                {"from": "a", "to": "t", "capacity": 2},
                                {"from": "b", "to": "t", "capacity": 3}]})
    steps = max_flow_steps(g, "s", "t")
    assert steps[-1].label == "Min cut"
    assert steps[-1].panel == ("flow value = 5", "cut capacity = 5")
    # Two cuts have capacity 5; the certificate is the one the residual graph
    # reaches from s — here just {s}, whose two out-edges are saturated.
    assert {k for k, role in steps[-1].edge_states.items() if role == "cut"} == {("s", "a"), ("s", "b")}
    assert steps[-1].edge_labels[("s", "a")] == "3/3"


def test_max_flow_can_cancel_flow_along_a_reverse_edge():
    # The classic case: the first path uses a→b, the second must undo it.
    g = coerce_graph({"directed": True, "nodes": [{"id": v} for v in "sabt"],
                      "edges": [{"from": "s", "to": "a", "capacity": 1},
                                {"from": "s", "to": "b", "capacity": 1},
                                {"from": "a", "to": "b", "capacity": 1},
                                {"from": "a", "to": "t", "capacity": 1},
                                {"from": "b", "to": "t", "capacity": 1}]})
    assert max_flow_steps(g, "s", "t")[-1].panel[0] == "flow value = 2"


def test_flows_refuse_a_source_that_is_the_sink_or_an_uncapacitated_edge():
    g = _graph([("A", "B")], directed=True)
    with pytest.raises(GraphError, match="differ"):
        max_flow_steps(g, "A", "A")
    with pytest.raises(GraphError, match="capacity"):
        max_flow_steps(g, "A", "B")


# --------------------------------------------------- colouring, matching


def test_bipartition_returns_the_odd_cycle_when_there_is_one():
    colours, cycle = bipartition(_graph([("A", "B"), ("B", "C"), ("C", "D"), ("D", "A")]))
    assert cycle == [] and colours["A"] != colours["B"]
    _, cycle = bipartition(_graph([("A", "B"), ("B", "C"), ("C", "A")]))
    assert len(cycle) == 3 and set(cycle) == {"A", "B", "C"}


def test_greedy_coloring_uses_the_supplied_order():
    g = _graph([("A", "B"), ("B", "C"), ("C", "A"), ("C", "D")])
    last = greedy_coloring_steps(g, ["D", "C", "B", "A"])[-1]
    assert last.node_states["D"] == "color-1" and last.node_states["C"] == "color-2"
    assert last.panel == ("colours used: 3",)


def test_konig_cover_has_the_size_of_the_maximum_matching():
    g = _graph([("u1", "v1"), ("u1", "v2"), ("u2", "v1"), ("u3", "v2"), ("u3", "v3")])
    steps, match_r = matching_steps(g, ["u1", "u2", "u3"])
    assert len(match_r) == 3
    cover = konig_cover(g, ["u1", "u2", "u3"], match_r)
    assert len(cover) == 3
    for edge in g.edges:
        assert edge.source in cover or edge.target in cover
    assert vertex_cover_steps(g, ["u1", "u2", "u3"])[-1].label == "Vertex cover"


# ------------------------------------------------------------------ Euler


def test_euler_circuit_uses_every_edge_once_and_refuses_odd_degrees():
    square = _graph([("A", "B"), ("B", "C"), ("C", "D"), ("D", "A"), ("A", "C"), ("B", "D")])
    with pytest.raises(GraphError) as info:      # K4: every vertex has degree 3
        euler_steps(square)
    assert info.value.witness == ["A", "B", "C", "D"]
    bowtie = _graph([("A", "B"), ("B", "C"), ("C", "A"), ("C", "D"), ("D", "E"), ("E", "C")])
    steps = euler_steps(bowtie)
    assert len(steps) == 1 + 6
    assert steps[-1].panel[0].startswith("circuit: ")
    trail = _graph([("A", "B"), ("B", "C")])
    assert euler_steps(trail)[-1].panel[0] == "trail: A → B → C"


# ----------------------------------------------------------- connectivity


def test_low_link_finds_bridges_articulations_and_biconnected_blocks():
    graph = _graph([("A", "B"), ("B", "C"), ("C", "A"), ("C", "D"),
                    ("D", "E"), ("E", "F"), ("F", "D")])
    found = connectivity_analysis(graph)
    assert found.bridges == (("C", "D"),)
    assert set(found.articulations) == {"C", "D"}
    assert {frozenset(block) for block in found.blocks} == {
        frozenset("ABC"), frozenset("CD"), frozenset("DEF")}
    assert found.low["C"] == found.discovery["A"]
    assert found.low["F"] == found.discovery["D"]


def test_low_link_handles_a_forest_and_refuses_direction():
    forest = coerce_graph({"nodes": [{"id": x} for x in "ABCD"],
                           "edges": [{"from": "A", "to": "B"},
                                     {"from": "B", "to": "C"}]})
    found = connectivity_analysis(forest)
    assert set(found.bridges) == {("A", "B"), ("B", "C")}
    assert found.articulations == ("B",)
    assert frozenset({"D"}) in {frozenset(block) for block in found.blocks}
    with pytest.raises(GraphError, match="undirected"):
        connectivity_analysis(_graph([("A", "B")], directed=True))


def test_connectivity_trace_draws_the_computed_certificate():
    graph = _graph([("A", "B"), ("B", "C"), ("C", "A"), ("C", "D")])
    final = connectivity_steps(graph)[-1]
    assert final.node_states["C"] == "articulation"
    assert final.edge_states[("C", "D")] == "cut"
    assert "bridges: C–D" in final.panel
    assert any(line.startswith("blocks:") for line in final.panel)


# ------------------------------------------------------------ the topic


def test_steps_for_runs_the_stock_graph_when_none_is_supplied():
    steps = steps_for("graph/shortest_path", {"algorithm": "dijkstra"})
    assert steps[0].label == "Initialize" and len(steps) == 7
    with pytest.raises(GraphError, match="runs"):
        steps_for("graph/shortest_path", {"algorithm": "kruskal"})
    assert steps_for("graph/connectivity", {"algorithm": "low_link"})[-1].label == "Block structure"


def test_connectivity_trace_reveals_an_articulation_only_once_it_is_proved():
    # U is a cut vertex because of V2; finishing V1 (low < d[U]) proves nothing.
    graph = _graph([("R", "U"), ("U", "V1"), ("V1", "R"), ("U", "V2")])
    by_label = {step.label: step for step in connectivity_steps(graph)}
    assert by_label["Finish V1"].node_states.get("U") != "articulation"
    assert by_label["Finish V1"].panel[1] == "articulations: —"
    assert by_label["Finish V2"].node_states["U"] == "articulation"
    # The root needs a second DFS child; the first child's subtree is not a proof.
    root = _graph([("A", "B"), ("B", "C"), ("C", "A"), ("A", "D")])
    labels = {step.label: step.panel[1] for step in connectivity_steps(root)}
    assert labels["Finish B"] == "articulations: —"
    assert labels["Finish D"] == "articulations: A"


def test_connectivity_trace_lists_bridges_in_proof_order_not_hash_order():
    graph = _graph([("A", "B"), ("B", "C"), ("C", "D"), ("D", "E"), ("E", "F")])
    panels = [step.panel[0] for step in connectivity_steps(graph)]
    assert panels[-2] == "bridges: E–F, D–E, C–D, B–C, A–B"


def test_connectivity_honours_start_and_refuses_a_stranger():
    graph = _graph([("A", "B"), ("B", "C"), ("C", "A"), ("C", "D")])
    assert connectivity_analysis(graph, start="D").discovery["D"] == 1
    assert connectivity_steps(graph, start="D")[1].label != connectivity_steps(graph)[1].label
    with pytest.raises(GraphError, match="start 'Z' is not a vertex"):
        steps_for("graph/connectivity", {"nodes": [{"id": "A"}], "edges": [], "start": "Z"})
