"""Reaching a named template directly, in any language, with no LLM.

The keyword router in ``build_plan`` is Chinese-first, so the obvious English
prompt for the README's hero animations does not reach them. ``plan_from_template``
and the ``--template`` flag do — every shipped animation, by name. These pin that
the ids from ``list_templates`` route back, that a bad id is refused with a
remedy, and that the request path is untouched.
"""

from __future__ import annotations

import json

import pytest

from straightedge import build_plan, cli, list_templates, plan_from_template
from straightedge.errors import StraightedgeError


class TestPlanFromTemplate:
    def test_the_hero_animations_are_reachable_by_name(self):
        """derivative-tangent and ellipse-foci are in the README gallery and
        cannot be reached by the obvious English prompt — only by name."""
        for concept in ("calculus/derivative_tangent", "conic/ellipse_foci"):
            plan = plan_from_template(concept)
            assert plan.concept == concept
            assert plan.match == "concept"

    def test_every_animation_id_from_the_catalogue_routes_back(self):
        """list_templates says what exists; each of those ids must build a plan.

        This is the contract the two are meant to honour together — enumerate,
        then take one back."""
        for t in list_templates():
            if t.lane != "animation":
                continue
            plan = plan_from_template(t.id)
            assert plan.topic == t.id.split("/")[0]

    def test_parameters_pass_through(self):
        plan = plan_from_template("calculus/derivative_tangent",
                                  {"expression": "x**3"})
        assert plan.parameters == {"expression": "x**3"}

    def test_a_figure_template_is_refused(self):
        """riemann_sum is a figure (render_diagram), not an animation — naming it
        here should be refused, not silently mis-rendered."""
        with pytest.raises(StraightedgeError) as exc:
            plan_from_template("riemann_sum")
        assert "list-templates" in (exc.value.remedy or "")

    def test_an_unknown_id_is_refused(self):
        with pytest.raises(StraightedgeError):
            plan_from_template("calculus/does_not_exist")


class TestTheFlag:
    def _plan(self, capsys, argv):
        assert cli.main(argv) == 0
        return json.loads(capsys.readouterr().out)["plan"]

    def test_template_reaches_a_concept_in_english(self, capsys):
        plan = self._plan(capsys, ["plan", "--template",
                                   "calculus/derivative_tangent", "--json"])
        assert plan["concept"] == "calculus/derivative_tangent"

    def test_params_are_parsed(self, capsys):
        plan = self._plan(capsys, ["plan", "--template",
                                   "calculus/derivative_tangent",
                                   "--params", '{"expression": "x**3"}', "--json"])
        assert plan["parameters"] == {"expression": "x**3"}

    def test_scaffold_writes_the_named_template(self, capsys, tmp_path):
        code = cli.main(["scaffold", "--template", "conic/ellipse_foci",
                         "--json", "--output-dir", str(tmp_path)])
        assert code == 0
        assert (tmp_path / "scene.py").exists()

    def test_a_bad_template_is_a_typed_error(self, capsys):
        code = cli.main(["plan", "--template", "nope", "--json"])
        obj = json.loads(capsys.readouterr().out)
        assert code == 1 and obj["ok"] is False
        assert obj["error"]["remedy"]

    def test_malformed_params_is_a_typed_error(self, capsys):
        code = cli.main(["plan", "--template", "conic/ellipse_foci",
                         "--params", "{not json", "--json"])
        obj = json.loads(capsys.readouterr().out)
        assert code == 1 and obj["error"]["code"] == "bad_input_file"

    def test_template_is_rejected_for_the_agent_commands(self, capsys):
        code = cli.main(["agent-plan", "--template", "conic/ellipse_foci", "--json"])
        obj = json.loads(capsys.readouterr().out)
        assert code == 1 and obj["ok"] is False

    def test_the_request_path_still_works(self, capsys):
        plan = self._plan(capsys, ["plan", "画一个椭圆", "--json"])
        assert plan["topic"] == "conic"
