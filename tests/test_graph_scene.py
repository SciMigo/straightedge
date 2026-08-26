"""The graph scene draws computed states, one narration beat per step."""

from __future__ import annotations

import ast
import re

from straightedge import plan_from_template, validate
from straightedge.graph_scene import MAX_STEPS, MAX_VERTICES, layout
from straightedge.graphs import ConceptGraph, coerce_graph, steps_for
from straightedge.models import AnimationPlan, Topic
from straightedge.planner import build_plan
from straightedge.templates import scene_code_for


def _beats(code: str) -> list[str]:
    return re.findall(r'_beat(?:_stretch)?\(self, "(b\d+)"', code)


def test_every_concept_and_algorithm_emits_one_beat_per_step_plus_the_drawing():
    for concept, algorithms in (
        (ConceptGraph.TRAVERSAL, ("bfs", "dfs")),
        (ConceptGraph.SHORTEST_PATH, ("dijkstra", "bellman_ford")),
        (ConceptGraph.SPANNING_TREE, ("kruskal", "prim")),
        (ConceptGraph.MAX_FLOW, ("edmonds_karp",)),
        (ConceptGraph.CONNECTIVITY, ("low_link",)),
    ):
        for algorithm in algorithms:
            plan = plan_from_template(concept, {"algorithm": algorithm})
            code = scene_code_for(plan)
            ast.parse(code)
            beats = _beats(code)
            assert beats == ["b%02d" % i for i in range(1, len(beats) + 1)]
            assert len(beats) == 1 + len(steps_for(concept, {"algorithm": algorithm}))
            assert validate(plan) == []


def test_a_request_routes_to_the_graph_topic_and_its_concept():
    plan = build_plan("用 Dijkstra 算法求最短路")
    assert (plan.topic, plan.concept) == (Topic.GRAPH, ConceptGraph.SHORTEST_PATH)
    assert plan.parameters["algorithm"] == "dijkstra"
    assert build_plan("画网络流的最大流和最小割").concept == ConceptGraph.MAX_FLOW
    assert build_plan("用 DFS 遍历这个图").parameters["algorithm"] == "dfs"
    assert build_plan("找出图中的桥和割点").concept == ConceptGraph.CONNECTIVITY
    # A bare graph-theory request is a traversal, not a fallback to geometry.
    assert build_plan("画一个图论的例子").concept == ConceptGraph.TRAVERSAL


def test_a_students_graph_is_drawn_and_its_states_are_the_algorithms():
    params = {"algorithm": "dijkstra", "start": "A",
              "nodes": [{"id": "A"}, {"id": "B"}, {"id": "C"}],
              "edges": [{"from": "A", "to": "B", "weight": 1},
                        {"from": "B", "to": "C", "weight": 1},
                        {"from": "A", "to": "C", "weight": 5}]}
    code = scene_code_for(plan_from_template(ConceptGraph.SHORTEST_PATH, params))
    assert "Settle C (d = 2)" in code          # via B, not the direct edge
    assert "'C: 2'" in code or '"C: 2"' in code


def test_the_precondition_refuses_what_the_algorithm_cannot_do():
    plan = plan_from_template(ConceptGraph.SHORTEST_PATH, {
        "algorithm": "dijkstra", "nodes": [{"id": "A"}, {"id": "B"}],
        "edges": [{"from": "A", "to": "B", "weight": -2}]})
    violations = validate(plan)
    assert violations and "negative weight" in violations[0].message
    # The builder still returns a scene, one that says so.
    assert "Nothing to draw" in scene_code_for(plan)

    big = plan_from_template(ConceptGraph.TRAVERSAL, {
        "nodes": [{"id": str(i)} for i in range(MAX_VERTICES + 1)],
        "edges": [{"from": str(i), "to": str(i + 1)} for i in range(MAX_VERTICES)]})
    messages = [v.message for v in validate(big)]
    assert any("vertices" in m for m in messages)


def test_the_precondition_publishes_the_parameters_it_reads():
    from straightedge import list_templates
    listed = {t.id: t for t in list_templates()}
    for concept in (ConceptGraph.TRAVERSAL, ConceptGraph.MAX_FLOW, ConceptGraph.CONNECTIVITY):
        assert {"nodes", "edges", "algorithm", "start"} <= set(listed[concept].params)
        assert listed[concept].invocation == "prompt"


def test_layout_keeps_every_vertex_left_of_the_panel_and_inside_the_frame():
    graph = coerce_graph({"nodes": [{"id": str(i)} for i in range(MAX_VERTICES)],
                          "edges": [{"from": "0", "to": str(i)} for i in range(1, MAX_VERTICES)]})
    for kind in ("auto", "hierarchical"):
        for x, y in layout(graph, kind).values():
            assert -6.6 <= x <= 2.4 and -2.6 <= y <= 2.6
    placed = coerce_graph({"nodes": [{"id": "A", "x": 0, "y": 0}, {"id": "B", "x": 1, "y": 1}],
                           "edges": [{"from": "A", "to": "B"}]})
    positions = layout(placed, "auto")
    assert positions["A"][0] < positions["B"][0] and positions["A"][1] > positions["B"][1]


def test_max_steps_is_what_the_scene_can_hold():
    plan = AnimationPlan(topic=Topic.GRAPH, title_zh="", objective_zh="", english_prompt="",
                         concept=ConceptGraph.TRAVERSAL,
                         parameters={"nodes": [{"id": str(i)} for i in range(MAX_VERTICES)],
                                     "edges": [{"from": str(i), "to": str(i + 1)}
                                               for i in range(MAX_VERTICES - 1)]})
    assert len(_beats(scene_code_for(plan))) <= MAX_STEPS + 1
