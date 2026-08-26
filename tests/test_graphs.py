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
    GraphError, bellman_ford_steps, bipartition, coerce_graph, dijkstra_steps,
    connectivity_analysis, connectivity_steps, euler_steps, greedy_coloring_steps, konig_cover, kruskal_steps,
    matching_steps, max_flow_steps, prim_steps, scc_steps, steps_for,
    topological_sort_steps, traversal_steps, vertex_cover_steps,
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


# ---------------------------------------------------------- DAGs and SCCs


def test_topological_sort_orders_a_dag_and_names_a_cycle():
    dag = _graph([("A", "B"), ("A", "C"), ("B", "D"), ("C", "D")], directed=True)
    steps = topological_sort_steps(dag)
    assert steps[-1].panel == ("order: A, B, C, D",)
    cyclic = _graph([("A", "B"), ("B", "C"), ("C", "A"), ("C", "D")], directed=True)
    with pytest.raises(GraphError) as info:
        topological_sort_steps(cyclic)
    assert set(info.value.witness) == {"A", "B", "C"}


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
