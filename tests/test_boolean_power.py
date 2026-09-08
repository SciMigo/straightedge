"""graph/boolean_power: reachability by repeated Boolean squaring, computed."""

from __future__ import annotations

import pytest

from straightedge.graphs import (ConceptGraph, GraphError, boolean_power_steps,
                                 coerce_graph, steps_for)

# The five-vertex lecture graph: closure needs exactly two squarings.
LECTURE_GRAPH = {
    "nodes": [{"id": v} for v in "12345"],
    "edges": [
        {"from": "1", "to": "2"}, {"from": "2", "to": "3"},
        {"from": "3", "to": "4"}, {"from": "4", "to": "5"},
        {"from": "2", "to": "5"},
    ],
}


def test_flood_reaches_closure_with_computed_counts():
    steps = boolean_power_steps(coerce_graph(LECTURE_GRAPH))
    powers = [s.extras["power"] for s in steps]
    assert powers == [1, 2, 4, 4]
    # R has I plus five undirected edges: 5 + 10 = 15 ones.
    assert len(steps[0].extras["new_ones"]) == 15
    assert len(steps[1].extras["new_ones"]) == 8
    assert len(steps[2].extras["new_ones"]) == 2
    # The final matrix is the all-ones closure: this graph is connected.
    assert all(all(row) for row in steps[-1].extras["matrix"])


def test_new_ones_are_exactly_the_entries_that_changed():
    steps = boolean_power_steps(coerce_graph(LECTURE_GRAPH))
    prev = steps[0].extras["matrix"]
    for step in steps[1:]:
        cur = step.extras["matrix"]
        changed = {(i, j) for i in range(5) for j in range(5)
                   if cur[i][j] and not prev[i][j]}
        assert set(step.extras["new_ones"]) == changed
        prev = cur


def test_direction_is_honoured():
    directed = coerce_graph({
        "nodes": [{"id": v} for v in "abc"],
        "edges": [{"from": "a", "to": "b"}, {"from": "b", "to": "c"}],
        "directed": True,
    })
    final = boolean_power_steps(directed)[-1].extras["matrix"]
    assert final[0][2] == 1  # a reaches c
    assert final[2][0] == 0  # c reaches nothing upstream


def test_disconnected_pairs_stay_zero_at_the_fixed_point():
    two_islands = coerce_graph({
        "nodes": [{"id": v} for v in "abcd"],
        "edges": [{"from": "a", "to": "b"}, {"from": "c", "to": "d"}],
    })
    steps = boolean_power_steps(two_islands)
    final = steps[-1].extras["matrix"]
    assert final[0][2] == 0 and final[1][3] == 0
    assert "Fixed point" in steps[-1].label or "Closure" in steps[-1].label


def test_bad_max_power_is_refused_with_witness():
    graph = coerce_graph(LECTURE_GRAPH)
    with pytest.raises(GraphError) as caught:
        boolean_power_steps(graph, "four")
    assert caught.value.witness == "four"


def test_scene_builds_and_lights_only_computed_entries():
    from straightedge.graph_scene import graph_scene
    from straightedge.models import AnimationPlan, Topic

    plan = AnimationPlan(
        topic=Topic.GRAPH, concept=ConceptGraph.BOOLEAN_POWER,
        title_zh="传递闭包", objective_zh="", english_prompt="closure",
        parameters={**LECTURE_GRAPH, "title": "Reachability floods"},
    )
    source = graph_scene(plan)
    assert "Reachability floods" in source
    # draw + R^2 + R^4 + closure = 4 beats
    assert source.count("_beat(self,") == 4
    # No ghost-label re-targeting: every FadeTransform source is chained.
    assert "FadeTransform(power," in source and "FadeTransform(power1," in source
    # The tex/LaTeX never leaks: values are 0/1 text only.
    assert "bmatrix" not in source


def test_steps_for_dispatches():
    steps = steps_for(ConceptGraph.BOOLEAN_POWER, dict(LECTURE_GRAPH))
    assert steps[0].label == "R = I OR A"


def test_prompt_routes_to_the_concept():
    from straightedge.planner import _graph_plan

    plan = _graph_plan("show the transitive closure by squaring the reachability matrix")
    assert plan.concept == ConceptGraph.BOOLEAN_POWER
