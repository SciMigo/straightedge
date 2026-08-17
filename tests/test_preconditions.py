"""Per-concept plan checks.

The property under test throughout: whenever a builder would *silently* draw
something other than what the plan asks for, `validate` says so first. Each case
therefore asserts both halves — the violation is raised, and the substitution it
warns about is real.
"""

from __future__ import annotations

import pytest

from straightedge.calculus import ConceptCalculus
from straightedge.models import AnimationPlan, Topic
from straightedge.preconditions import Violation, blocking, validate
from straightedge.solids3d import Concept3D
from straightedge.templates import scene_code_for
from straightedge.trig import Concept as ConceptTrig


def _plan(topic, concept, **parameters):
    return AnimationPlan(
        topic=topic, title_zh="标题", objective_zh="目标",
        english_prompt="prompt", concept=concept, parameters=parameters,
    )


def _params(violations):
    return {v.param for v in violations}


# --------------------------------------------------------------- the frame

def test_a_sound_plan_is_silent():
    plan = _plan(Topic.TRIG, ConceptTrig.GRAPH_TRANSFORM,
                 trig_spec={"func": "cos", "A": 2.0, "omega": 3.0, "phi": 0.5, "k": 1.0})
    assert validate(plan) == []


def test_absent_parameters_are_not_a_violation():
    """The builders have defaults; saying nothing is a valid way to ask."""
    assert validate(_plan(Topic.TRIG, ConceptTrig.GRAPH_TRANSFORM)) == []
    assert validate(_plan(Topic.CALCULUS, ConceptCalculus.RIEMANN_INTEGRAL)) == []


def test_an_unregistered_concept_has_nothing_to_say():
    assert validate(_plan(Topic.GEOMETRY, "geometry/unknown", anything=1)) == []


def test_blocking_filters_to_errors():
    vs = [Violation("c", "p", "m", "error"), Violation("c", "p", "m", "warn")]
    assert [v.severity for v in blocking(vs)] == ["error"]


# ------------------------------------------------------------------- trig

class TestTrigSpec:

    def test_unsupported_function_is_reported(self):
        plan = _plan(Topic.TRIG, ConceptTrig.GRAPH_TRANSFORM,
                     trig_spec={"func": "sec", "A": 1.0, "omega": 1.0})
        assert "trig_spec.func" in _params(validate(plan))

    def test_the_substitution_it_warns_about_is_real(self):
        """Guard: if the builder stopped substituting, this check is obsolete."""
        plan = _plan(Topic.TRIG, ConceptTrig.GRAPH_TRANSFORM,
                     trig_spec={"func": "sec", "A": 1.0, "omega": 1.0})
        assert "np.sin" in scene_code_for(plan)

    def test_zero_amplitude_is_reported(self):
        plan = _plan(Topic.TRIG, ConceptTrig.GRAPH_TRANSFORM,
                     trig_spec={"func": "sin", "A": 0.0, "omega": 1.0})
        assert "trig_spec.A" in _params(validate(plan))

    def test_zero_frequency_is_reported(self):
        plan = _plan(Topic.TRIG, ConceptTrig.GRAPH_TRANSFORM,
                     trig_spec={"func": "sin", "A": 1.0, "omega": 0.0})
        assert "trig_spec.omega" in _params(validate(plan))

    def test_several_faults_are_all_reported(self):
        plan = _plan(Topic.TRIG, ConceptTrig.GRAPH_TRANSFORM,
                     trig_spec={"func": "sec", "A": 0.0, "omega": 0.0})
        assert _params(validate(plan)) == {
            "trig_spec.func", "trig_spec.A", "trig_spec.omega"}

    def test_a_non_dict_spec_is_left_to_the_builder(self):
        assert validate(_plan(Topic.TRIG, ConceptTrig.GRAPH_TRANSFORM,
                              trig_spec="sin")) == []


# --------------------------------------------------------------- calculus

class TestCalculusExpression:

    @pytest.mark.parametrize("concept", [
        ConceptCalculus.DERIVATIVE_TANGENT,
        ConceptCalculus.RIEMANN_INTEGRAL,
        ConceptCalculus.FTC_ACCUMULATION,
    ])
    def test_unparseable_expression_is_reported_for_every_plotting_concept(self, concept):
        plan = _plan(Topic.CALCULUS, concept, expression="x**2 +")
        assert "expression" in _params(validate(plan))

    def test_a_valid_expression_is_silent(self):
        plan = _plan(Topic.CALCULUS, ConceptCalculus.RIEMANN_INTEGRAL,
                     expression="x**2 - 1")
        assert validate(plan) == []

    def test_this_is_the_substitution_most_likely_to_mislead(self):
        """The title and narration keep the requested function; the plot does not.

        A rendered scene looks entirely correct while answering a different
        question — which is why it cannot be left to the geometric checks.
        """
        plan = _plan(Topic.CALCULUS, ConceptCalculus.DERIVATIVE_TANGENT,
                     expression="\\frac{1}{x}")
        assert validate(plan), "an unsupported expression must be reported"
        code = scene_code_for(plan)
        assert "\\frac{1}{x}" not in code, "the builder silently drops it"


class TestTaylorTarget:

    def test_a_target_without_an_expansion_is_reported(self):
        plan = _plan(Topic.CALCULUS, ConceptCalculus.TAYLOR_SERIES, function="exp")
        assert "function" in _params(validate(plan))

    @pytest.mark.parametrize("target", ["sin", "cos"])
    def test_written_targets_are_silent(self, target):
        plan = _plan(Topic.CALCULUS, ConceptCalculus.TAYLOR_SERIES, function=target)
        assert validate(plan) == []


# --------------------------------------------------------------------- 3d

class TestSectionPoints:

    def test_two_points_do_not_define_a_plane(self):
        """The defect class geometric checks cannot reach.

        Two points render a perfectly tidy scene showing the wrong
        construction — nothing is clipped, nothing overlaps, and the cut is not
        the one that was asked for.
        """
        plan = _plan(Topic.THREE_D, Concept3D.CUBE_SECTION, section_points=["A", "B1"])
        assert blocking(validate(plan))

    def test_three_named_vertices_are_silent(self):
        plan = _plan(Topic.THREE_D, Concept3D.CUBE_SECTION,
                     section_points=["D", "A1", "C1"])
        assert validate(plan) == []

    def test_unusable_labels_are_flagged_and_counted_out(self):
        plan = _plan(Topic.THREE_D, Concept3D.CUBE_SECTION,
                     section_points=["D", "A1", "middle of DC"])
        violations = validate(plan)
        assert {v.severity for v in violations} == {"warn", "error"}

    def test_a_string_is_not_a_point_list(self):
        plan = _plan(Topic.THREE_D, Concept3D.CUBE_SECTION, section_points="DA1C1")
        assert blocking(validate(plan))


class TestSolidKind:

    def test_an_unbuildable_solid_is_reported(self):
        plan = _plan(Topic.THREE_D, Concept3D.SOLID_OVERVIEW,
                     solid_spec={"kind": "dodecahedron", "params": {}})
        assert "solid_spec.kind" in _params(validate(plan))

    @pytest.mark.parametrize("kind", ["cube", "cylinder", "cone", "tetrahedron"])
    def test_buildable_solids_are_silent(self, kind):
        plan = _plan(Topic.THREE_D, Concept3D.SOLID_OVERVIEW,
                     solid_spec={"kind": kind, "params": {"side": 2.0}})
        assert validate(plan) == []

    def test_the_check_covers_every_concept_that_builds_a_solid(self):
        """An unknown kind raises during the render rather than substituting."""
        for concept in (Concept3D.SOLID_OVERVIEW, Concept3D.CUBE_SECTION,
                        Concept3D.THREE_VIEWS):
            plan = _plan(Topic.THREE_D, concept,
                         solid_spec={"kind": "torus", "params": {}})
            assert "solid_spec.kind" in _params(validate(plan)), concept
