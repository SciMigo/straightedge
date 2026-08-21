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
        """Extraction never invents: every name it lists is a literal key in
        the source.

        Searched in the defining *module*, not the template class: a template
        may keep ``render`` as a one-line delegation to a module-level helper
        and do all of its reading there, and extraction follows that hop.
        """
        import inspect
        from straightedge.diagrams import DIAGRAM_REGISTRY

        for t in list_templates():
            if t.lane != "figure":
                continue
            src = inspect.getsource(inspect.getmodule(DIAGRAM_REGISTRY[t.id].render))
            for name in t.params:
                assert repr(name) in src or f'"{name}"' in src, (
                    f"{t.id} lists {name!r}, which appears nowhere in its module")


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


# --------------------------------------------------------- inference: idioms
#
# Module-level so `inspect.getmodule` can find them the way it finds a real
# template. `_TYPING_*` are read by TestInference below.

_TYPING_WIDTH = 640
_TYPING_ACCENT = "#c33"


def _typing_or_idiom(params):
    _ = params.get("steps") or []
    _ = params.get("gap") or 12
    _ = params.get("label") or "untitled"


def _typing_chained(params):
    _ = params.get("steps") or params.get("construction") or []


def _typing_coerced(params):
    _ = float(params.get("angle") or _TYPING_WIDTH)
    _ = bool(params.get("dotted"))
    _ = int(params.get("rows", len(params.get("data") or [])))


def _typing_named(params):
    _ = params.get("width") or _TYPING_WIDTH
    _ = params.get("accent") or _TYPING_ACCENT


def _typing_delegate(params):
    return _typing_or_idiom(params or {})


def _typing_side(settings):
    """Called with the params dict under a different name."""
    _ = settings.get("accent") or "#333"


def _typing_outline(params):
    """`render` as an outline: the reads live in the helpers it calls."""
    _ = _typing_side(params)
    _ = _typing_or_idiom(params)
    _ = params.get("caption") or ""


class TestInference:
    """What the catalog can read off a template's own code.

    Each idiom below is half of how the lane actually reads parameters; a
    reader that knows only `params.get(x, default)` publishes a name with no
    type beside it, and a caller with no type in front of them guesses.
    """

    def _params(self, func):
        from straightedge.catalog import _dict_get_parameters
        return {p["name"]: p for p in _dict_get_parameters(func, receiver="params")}

    def test_or_states_the_default_as_plainly_as_a_comma(self):
        got = self._params(_typing_or_idiom)
        assert got["steps"]["type"] == "array"
        assert got["gap"] == {"name": "gap", "type": "number", "default": 12}
        assert got["label"] == {"name": "label", "type": "string", "default": "untitled"}

    def test_a_chain_shares_one_fallback(self):
        got = self._params(_typing_chained)
        assert got["steps"]["type"] == "array"
        assert got["construction"]["type"] == "array"

    def test_a_coercion_names_the_type(self):
        got = self._params(_typing_coerced)
        assert got["angle"]["type"] == "number"
        assert got["dotted"]["type"] == "boolean"

    def test_a_coercion_speaks_only_for_what_it_wraps(self):
        """`int(params.get("rows", len(params.get("data") or [])))` says `rows`
        is a number and says nothing at all about `data`."""
        got = self._params(_typing_coerced)
        assert got["rows"]["type"] == "number"
        assert got["data"].get("type") != "number"

    def test_a_named_default_resolves_to_its_value(self):
        got = self._params(_typing_named)
        assert got["width"] == {"name": "width", "type": "number", "default": 640}
        assert got["accent"] == {"name": "accent", "type": "string", "default": "#c33"}

    def test_a_one_line_delegation_is_followed(self):
        """Otherwise the template reports no parameters at all — worse than
        reporting them untyped, because it reads as taking no input."""
        assert self._params(_typing_delegate).keys() == self._params(_typing_or_idiom).keys()

    def test_helpers_that_take_the_params_dict_are_read_too(self):
        """`render` is often an outline calling `_tasks_from_params(params)`.
        Reading only `render` dropped whole parameters -- `gantt` never listed
        `tasks`, the only parameter it really has."""
        got = self._params(_typing_outline)
        assert {"caption", "accent", "steps", "gap", "label"} <= got.keys()
        assert got["accent"]["type"] == "string", "the helper renamed it; follow by position"

    def test_a_helper_is_followed_by_position_not_by_name(self):
        got = self._params(_typing_side)
        assert "accent" not in got, "receiver is `settings` here, not `params`"

    def test_the_lane_really_gained_those(self):
        by_id = {t.id: t for t in list_templates()}
        assert "tasks" in by_id["gantt"].params
        assert "accounts" in by_id["t_account"].params
        assert "components" in by_id["architecture_diagram"].params
        assert "columns" in by_id["comparison"].params

    def test_no_figure_template_reports_zero_parameters(self):
        from straightedge.diagrams import DIAGRAM_REGISTRY
        for t in list_templates():
            if t.lane != "figure":
                continue
            source = __import__("inspect").getsource(
                __import__("inspect").getmodule(DIAGRAM_REGISTRY[t.id].render))
            if "params.get(" in source or "params[" in source:
                assert t.params, f"{t.id} reads params but publishes none"

    def test_a_published_default_is_what_omitting_it_does(self):
        """The check that keeps inference honest: if a published default were
        guessed rather than read, passing it would not reproduce the figure
        that leaving it out produces."""
        import copy
        from straightedge.diagrams import DIAGRAM_REGISTRY

        checked = 0
        for t in list_templates():
            if t.lane != "figure":
                continue
            impl = DIAGRAM_REGISTRY[t.id]
            for p in t.parameters:
                if "default" not in p:
                    continue
                bare = impl.render({})
                given = impl.render({p["name"]: copy.deepcopy(p["default"])})
                assert bare == given, (
                    f"{t.id}: passing the published default for {p['name']!r} "
                    f"({p['default']!r}) does not match omitting it")
                checked += 1
        assert checked > 270, f"only {checked} defaults checked; extraction regressed"

    def test_most_parameters_carry_a_type(self):
        """A floor, not a target. Reading only `params.get(x, default)` typed
        219 of 334; adding the `or`, coercion, named-constant, delegation and
        helper-scope idioms took it to 290 of 365. Dropping back under this line means an
        idiom stopped being read, which is invisible from the outside: the
        catalog still lists the name, just with nothing beside it."""
        figures = [t for t in list_templates() if t.lane == "figure"]
        total = sum(len(t.params) for t in figures)
        typed = sum(1 for t in figures for p in t.parameters if p.get("type"))
        assert typed / total > 0.78, f"only {typed}/{total} parameters typed"
