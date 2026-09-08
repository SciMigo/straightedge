"""graph/walk_trace: author-supplied walks, every move checked against an edge."""

from __future__ import annotations

import pytest

from straightedge.graphs import (STOCK_WALKS, WALK_TRACE_KEYWORDS, ConceptGraph,
                                 GraphError, coerce_graph, steps_for,
                                 walk_trace_steps)

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


def test_a_reused_edge_is_animated_on_every_move():
    """A -> B -> A crosses one undirected edge twice. Its role is ``path``
    both times, and the scene animates a change of role, so without a flash
    the second move would be invisible on the edge it crosses."""
    from straightedge.graph_scene import graph_scene
    from straightedge.models import AnimationPlan, Topic

    two = {"nodes": [{"id": "A"}, {"id": "B"}], "edges": [{"from": "A", "to": "B"}]}
    steps = walk_trace_steps(coerce_graph(two), [["A", "B", "A"]])
    assert [s.flash for s in steps] == [(), (("A", "B"),), (("A", "B"),), ()]
    plan = AnimationPlan(
        topic=Topic.GRAPH, concept=ConceptGraph.WALK_TRACE,
        title_zh="", objective_zh="", english_prompt="",
        parameters={**two, "walks": [["A", "B", "A"]]})
    beats = [line for line in graph_scene(plan).splitlines() if "_beat(self," in line]
    moves = [b for b in beats if "Indicate(edges[0]" in b]
    assert len(moves) == 2
    # Only the first crossing changes the edge's role; the flash carries both.
    assert sum("edges[0].animate" in b for b in moves) == 1


def test_prompt_plan_supplies_stock_walks():
    from straightedge.planner import _graph_plan

    plan = _graph_plan("trace a walk on the graph, edge by edge")
    assert plan.concept == ConceptGraph.WALK_TRACE
    walks = plan.parameters["walks"]
    assert walks and all(len(walk) >= 2 for walk in walks)
    # And the stock walks actually run on the stock graph.
    assert steps_for(ConceptGraph.WALK_TRACE, dict(plan.parameters))


def test_bare_template_traces_the_stock_walks():
    """plan_from_template("graph/walk_trace") with no parameters must render a
    complete scene, like every other bare animation template."""
    from straightedge.graph_scene import graph_scene
    from straightedge.planner import plan_from_template

    plan = plan_from_template(ConceptGraph.WALK_TRACE)
    assert "walks" not in plan.parameters
    source = graph_scene(plan)
    assert "Nothing to draw" not in source
    assert source.count("_beat(self,") == 1 + 1 + sum(len(w) for w in STOCK_WALKS)


def test_a_callers_own_graph_still_needs_its_walks():
    """The stock default is for the stock graph only: an author's graph with
    no walks is refused, not traced along routes the template made up."""
    with pytest.raises(GraphError):
        steps_for(ConceptGraph.WALK_TRACE, dict(LECTURE_GRAPH))


@pytest.mark.parametrize("word", WALK_TRACE_KEYWORDS)
def test_every_walk_trace_word_reaches_the_concept_through_build_plan(word):
    """Topic detection runs before the graph concept matcher, so a word the
    matcher knows must also be a graph-topic keyword or it never arrives."""
    from straightedge.planner import build_plan

    plan = build_plan(f"please {word} now")
    assert (plan.topic, plan.concept) == ("graph", ConceptGraph.WALK_TRACE)
