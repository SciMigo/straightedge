"""Every template ships a worked example, and every example is checked.

Types told a caller what shape to send. They still did not say what a working
call looks like — nothing in `parameters` reveals that `solid_spec` is a dict of
{kind, params, name} rather than the string "cube", or that a roadmap given
tracks and items draws an empty frame until it is also handed a top-level
`start_date`. Both of those were found by writing these examples, which is most
of the argument for having them.

An unchecked example is worse than none: it is a wrong answer with the library's
name on it. So each one has to earn its place — a figure example must draw
something different from the same template called bare, an animation example
must plan without blocking violations, a request must actually route to the
template it is filed under, and no example may use a parameter its template
never reads.
"""

import inspect
import json

import pytest

from straightedge.catalog import list_templates
from straightedge.diagrams import DIAGRAM_REGISTRY
from straightedge.examples import EXAMPLES, REQUESTS


def _figures():
    return [t for t in list_templates() if t.lane == "figure"]


def _animations():
    return [t for t in list_templates() if t.lane == "animation"]


# Parameters an example uses that the catalog does not yet list. These are gaps
# in extraction, not bad examples -- each key below is read by its template,
# just from inside a helper that takes `params`, which discovery does not follow
# yet. Written down so the set can shrink without breaking the test, and so a
# newly-added template cannot join it unnoticed.
UNDERREPORTED = {
    "architecture_diagram": {"annotations", "components", "connections"},
    "circle_chord_rational": {"point_label", "triple"},
    "comparison": {"columns"},
    "descent_triangles": {"first", "note", "second"},
    "gantt": {"tasks"},
    "t_account": {"accounts"},
}


class TestEveryTemplateHasOne:

    def test_nothing_is_missing(self):
        for t in list_templates():
            assert t.example, f"{t.id} has no example"

    def test_the_example_names_its_own_template(self):
        """It is meant to be pasted, so the id in it has to be the right one."""
        for t in list_templates():
            key = "type" if t.lane == "figure" else "template"
            assert t.example.get(key) == t.id, f"{t.id}: example says {t.example.get(key)!r}"

    def test_examples_are_json(self):
        json.dumps([t.to_dict() for t in list_templates()], ensure_ascii=False)


class TestFigureExamples:

    def test_each_one_draws_something(self):
        """The check that keeps an example honest. A template called with no
        parameters still returns a frame, so 'it rendered' proves nothing —
        the example has to produce a *different* figure than calling it bare."""
        for t in _figures():
            impl = DIAGRAM_REGISTRY[t.id]
            drawn = impl.render(dict(t.example["params"]))
            assert drawn != impl.render({}), (
                f"{t.id}'s example renders the same as no parameters at all")

    def test_no_example_uses_a_parameter_its_template_never_reads(self):
        """A key the template ignores teaches a caller a habit that does
        nothing — and reads, from the outside, exactly like one that works."""
        for t in _figures():
            source = inspect.getsource(inspect.getmodule(DIAGRAM_REGISTRY[t.id].render))
            for key in t.example["params"]:
                assert f'"{key}"' in source or f"'{key}'" in source, (
                    f"{t.id}'s example passes {key!r}, which appears nowhere in its module")

    def test_undeclared_keys_are_only_the_known_extraction_gaps(self):
        for t in _figures():
            extra = set(t.example["params"]) - set(t.params)
            assert extra <= UNDERREPORTED.get(t.id, set()), (
                f"{t.id}'s example uses {sorted(extra - UNDERREPORTED.get(t.id, set()))}, "
                "which the catalog does not list and which is not a known gap")


class TestAnimationExamples:

    def test_each_one_plans_without_blocking_violations(self):
        """Cheap to check and the thing that matters: `plan` is where a bad
        parameter shape surfaces, long before a render is spent on it."""
        from straightedge.mcp_server import _plan_payload

        for t in _animations():
            result = _plan_payload("", t.id, dict(t.example["params"]))
            assert result.get("ok"), f"{t.id}: {result}"
            assert not result["plan"].get("violations"), (
                f"{t.id} example violates: {result['plan']['violations']}")

    def test_a_request_reaches_the_template_it_is_filed_under(self):
        """Routing is by keyword and Chinese-first. A phrasing that lands on a
        neighbouring template is the worst kind of example: it renders, so
        nothing complains, and it is not what was asked for."""
        from straightedge.mcp_server import _plan_payload

        assert REQUESTS, "no request examples at all"
        for tid, request in REQUESTS.items():
            plan = _plan_payload(request, "", None)["plan"]
            if "/" in tid:
                assert plan.get("concept") == tid, (
                    f"{request!r} routes to {plan.get('concept')!r}, not {tid}")
            else:
                assert str(plan.get("topic")) == tid and not plan.get("concept"), (
                    f"{request!r} routes to topic {plan.get('topic')!r}, not {tid}")

    def test_only_the_id_reachable_templates_lack_a_request(self):
        """`invocation` already says which those are; this keeps the two
        agreeing, so an id-only template cannot quietly appear."""
        for t in _animations():
            if t.invocation == "concept-id":
                assert t.id not in REQUESTS, f"{t.id} is id-only but ships a request"
            else:
                assert t.id in REQUESTS, f"{t.id} is prompt-routed but ships no request"


class TestTheListingStaysAffordable:

    def test_examples_can_be_left_out(self):
        """`list_templates` is the call an agent makes first, and examples are
        about a third of it. A client that only needs the names can say so."""
        from straightedge.catalog import as_dicts
        full = json.dumps(as_dicts(), ensure_ascii=False)
        slim = json.dumps([{k: v for k, v in row.items()
                            if k not in ("example", "example_request")}
                           for row in as_dicts()], ensure_ascii=False)
        assert len(slim) < len(full) * 0.75
