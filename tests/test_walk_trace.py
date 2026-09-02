"""graph/walk_trace: author-supplied walks, every move checked against an edge."""

from __future__ import annotations

import pytest

from straightedge.graphs import (ConceptGraph, GraphError, coerce_graph,
                                 steps_for, walk_trace_steps)

# The five-vertex lecture graph walk counting is taught on: two three-step
# walks lead from 1 to 4, and the template exists to show exactly that.
LECTURE_GRAPH = {
    "nodes": [{"id": v} for v in "12345"],
    "edges": [
        {"from": "1", "to": "2"}, {"from": "2", "to": "3"},
        {"from": "3", "to": "4"}, {"from": "4", "to": "5"},
        {"from": "2", "to": "5"},
    ],
}
TWO_WALKS = [["1", "2", "3", "4"], ["1", "2", "5", "4"]]


def test_traces_every_move_and_keeps_finished_walks_visible():
    steps = walk_trace_steps(coerce_graph(LECTURE_GRAPH), TWO_WALKS)
    # 1 intro + (3 moves + 1 completion) per walk.
    assert len(steps) == 1 + 4 + 4
    first_move = steps[1]
    assert first_move.node_states["2"] == "current"
    assert first_move.node_states["1"] == "source"
    assert first_move.edge_states[("1", "2")] == "path"
    # While walk 2 runs, walk 1's edges stay on screen as tree.
    second_walk_move = steps[6]
    assert second_walk_move.edge_states[("3", "4")] == "tree"
    assert second_walk_move.edge_states[("1", "2")] == "path"
    done = steps[-1]
    assert done.edge_states[("2", "5")] == "tree"
    assert all(role == "visited" for role in done.node_states.values())
    assert "walk 2 used 3 move(s)" in done.caption


def test_a_move_across_a_non_edge_is_refused_with_the_pair():
    with pytest.raises(GraphError) as caught:
        walk_trace_steps(coerce_graph(LECTURE_GRAPH), [["1", "3", "4"]])
    assert caught.value.witness == ("1", "3")
    assert "not an edge" in str(caught.value)


def test_direction_is_honoured_on_directed_graphs():
    directed = coerce_graph({
        "nodes": [{"id": "a"}, {"id": "b"}],
        "edges": [{"from": "a", "to": "b"}],
        "directed": True,
    })
    assert len(walk_trace_steps(directed, [["a", "b"]])) == 3
    with pytest.raises(GraphError) as caught:
        walk_trace_steps(directed, [["b", "a"]])
    assert caught.value.witness == ("b", "a")


def test_missing_short_or_unknown_walks_are_refused():
    graph = coerce_graph(LECTURE_GRAPH)
    with pytest.raises(GraphError):
        walk_trace_steps(graph, None)
    with pytest.raises(GraphError):
        walk_trace_steps(graph, [])
    with pytest.raises(GraphError):
        walk_trace_steps(graph, [["1"]])
    with pytest.raises(GraphError) as caught:
        walk_trace_steps(graph, [["1", "9"]])
    assert caught.value.witness == "9"


def test_steps_for_dispatches_and_a_vertex_may_repeat():
    # A walk, unlike a path, may revisit vertices; 1-2-1 is legal.
    steps = steps_for(ConceptGraph.WALK_TRACE,
                      {**LECTURE_GRAPH, "walks": [["1", "2", "1"]]})
    assert steps[-1].caption.startswith("walk 1 used 2 move(s)")


def test_scene_builds_from_a_plan():
    from straightedge.graph_scene import graph_scene
    from straightedge.models import AnimationPlan, Topic

    plan = AnimationPlan(
        topic=Topic.GRAPH, concept=ConceptGraph.WALK_TRACE,
        title_zh="路径追踪", objective_zh="逐边行走", english_prompt="trace",
        parameters={**LECTURE_GRAPH, "walks": TWO_WALKS,
                    "title": "Two three-step walks from 1 to 4"},
    )
    source = graph_scene(plan)
    assert "Two three-step walks from 1 to 4" in source
    assert source.count("_beat(self,") == 1 + 9  # draw + intro + every move/completion


def test_prompt_plan_supplies_stock_walks():
    from straightedge.planner import _graph_plan

    plan = _graph_plan("trace a walk on the graph, edge by edge")
    assert plan.concept == ConceptGraph.WALK_TRACE
    walks = plan.parameters["walks"]
    assert walks and all(len(walk) >= 2 for walk in walks)
    # And the stock walks actually run on the stock graph.
    assert steps_for(ConceptGraph.WALK_TRACE, dict(plan.parameters))
