"""Enumerating what the library can draw, across both lanes.

The catalog exists because nothing else could answer *what can this produce* — the
animation builders were private dicts and the figure templates had a registry but
no listing. These tests hold the properties an agent relies on when it reads the
catalog instead of the source: that everything is listed, that "reachable from a
prompt" is true when claimed, and that the two concepts no prompt reaches are
labelled rather than hidden.
"""

from __future__ import annotations

import json

import pytest

from straightedge import list_templates
from straightedge.catalog import (
    CANONICAL_PROMPTS, TOPIC_PROMPTS, Template, as_dicts,
)
from straightedge.planner import build_plan


def _by_id():
    return {t.id: t for t in list_templates()}


def test_both_lanes_are_present():
    lanes = {t.lane for t in list_templates()}
    assert lanes == {"animation", "figure"}


def test_every_figure_template_is_listed():
    from straightedge.diagrams import DIAGRAM_REGISTRY

    figures = {t.id for t in list_templates() if t.lane == "figure"}
    assert figures == set(DIAGRAM_REGISTRY)


def test_the_output_format_matches_the_lane():
    for t in list_templates():
        assert t.output == ("mp4" if t.lane == "animation" else "svg")


def test_it_serialises_to_json():
    """An agent reads this over a wire; a dataclass that will not dump is useless."""
    dumped = json.dumps(as_dicts())
    assert json.loads(dumped)[0].keys() >= {"id", "lane", "output", "invocation"}


class TestReachability:
    """The claim `invocation` makes is checked against the planner, not asserted.

    This is the part most easily wrong and least easily noticed: a routing change
    can strand a concept, and a hand-maintained "reachable" flag would keep
    saying otherwise. Computing it here means the catalog and the planner cannot
    disagree.
    """

    @pytest.mark.parametrize("concept,prompt", sorted(CANONICAL_PROMPTS.items()))
    def test_a_prompt_marked_reachable_actually_routes_there(self, concept, prompt):
        assert build_plan(prompt).concept == concept
        assert _by_id()[concept].invocation == "prompt"

    @pytest.mark.parametrize("topic,prompt", sorted(TOPIC_PROMPTS.items()))
    def test_a_topic_listed_generic_actually_renders_generic(self, topic, prompt):
        listed = _by_id().get(topic)
        if listed is None:            # topic always specialises; not a generic entry
            assert build_plan(prompt).concept is not None
        else:
            plan = build_plan(prompt)
            assert plan.topic == topic and plan.concept is None

    def test_the_orphans_are_labelled_not_hidden(self):
        """cone_slice and tangent_shift ship, render, and no phrasing reaches them.

        They are the reason this catalog exists: found once by a manual sweep,
        they must now be discoverable as text-unreachable rather than absent.
        """
        catalog = _by_id()
        for orphan in ("conic/cone_slice", "calculus/tangent_shift"):
            assert catalog[orphan].invocation == "concept-id"

    def test_no_canonical_prompt_reaches_an_orphan(self):
        reached = {build_plan(p).concept for p in CANONICAL_PROMPTS.values()}
        assert "conic/cone_slice" not in reached
        assert "calculus/tangent_shift" not in reached


class TestCompleteness:
    def test_topics_without_concepts_are_still_listed(self):
        """geometry and function have no concept ids; the topic layer is the only
        place they appear, so dropping it would drop them from the catalog."""
        catalog = _by_id()
        assert catalog["geometry"].lane == "animation"
        assert catalog["function"].lane == "animation"

    def test_every_precondition_concept_is_in_the_catalog(self):
        """A concept the library validates but does not list would be invisible
        to a caller and impossible to invoke knowingly."""
        from straightedge import preconditions

        listed = set(_by_id())
        assert set(preconditions._CHECKS) <= listed


class TestParameters:
    def test_figure_params_are_the_keys_the_template_reads(self):
        """Spot-check against a template whose params are known by hand."""
        params = _by_id()["riemann_sum"].params
        assert {"function", "a", "b", "n"} <= set(params)

    def test_animation_params_come_from_the_precondition(self):
        assert _by_id()["calculus/derivative_tangent"].params == ["expression"]

    def test_a_listed_parameter_is_always_real(self):
        """Extraction under-reports (it reads one level deep) but never invents:
        every name it lists is a literal key in the source."""
        import inspect
        from straightedge.diagrams import DIAGRAM_REGISTRY

        for t in list_templates():
            if t.lane != "figure":
                continue
            src = inspect.getsource(type(DIAGRAM_REGISTRY[t.id]))
            for name in t.params:
                assert repr(name) in src or f'"{name}"' in src


def test_the_shape_is_stable():
    """The fields an agent parses. A rename here breaks every consumer silently."""
    t = list_templates()[0]
    assert isinstance(t, Template)
    assert set(vars(t)) == {"id", "lane", "output", "invocation", "params",
                            "parameters", "summary"}


def test_a_collection_default_keeps_its_contents():
    """Publishing `[]` for a matrix whose default is [[1, 0], [0, 1]] is a wrong
    answer where no answer was available."""
    matrix = [p for p in _parameters("matrix_transform") if p["name"] == "matrix"][0]
    assert matrix == {"name": "matrix", "type": "array", "default": [[1, 0], [0, 1]]}


def test_an_unrepresentable_default_is_omitted_not_flattened():
    for template in list_templates():
        for parameter in template.parameters:
            if "default" in parameter:
                assert parameter["default"] is not None
                if parameter["type"] == "array":
                    assert isinstance(parameter["default"], list)


def _parameters(template_id: str) -> list[dict]:
    return [t for t in list_templates() if t.id == template_id][0].parameters
