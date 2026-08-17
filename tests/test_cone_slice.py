"""The cone-slice scene: one quadratic, six sections.

Substituting the cutting plane ``z = h + m·x`` into the double cone
``x² + y² = (z·T)²`` leaves ``y² = a·x² + b·x + c``. The sign of ``a`` is the
whole classification, and the degenerate cases are what the same expression
gives at ``h = 0`` — so the tests here check that arithmetic directly rather
than grepping the generated source for shapes it claims to draw.
"""

from __future__ import annotations

import ast

import numpy as np
import pytest

from straightedge.conics import (
    CONE_HALF_ANGLE_TAN, CONE_TAN_MAX, CONE_TAN_MIN, ConceptConic,
)
from straightedge.labels import untranslated
from straightedge.models import AnimationPlan, Topic
from straightedge.preconditions import blocking, validate
from straightedge.templates import scene_code_for


def _plan(**parameters):
    return AnimationPlan(
        topic=Topic.CONIC, title_zh="Where the Conics Come From", objective_zh="目标",
        english_prompt="cone", concept=ConceptConic.CONE_SLICE,
        parameters=parameters,
    )


def _beat_keys(code):
    keys = []
    for node in ast.walk(ast.parse(code)):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id in {"_beat", "_beat_stretch"}
                and len(node.args) >= 2
                and isinstance(node.args[1], ast.Constant)):
            keys.append((node.lineno, node.func.id, node.args[1].value))
    return [(helper, key) for _, helper, key in sorted(keys)]


# ------------------------------------------------------------- the geometry

_SECTION_GLOBALS = {"CONE_T", "CONE_Z", "CONE_R", "PARABOLA_SLOPE"}


def _section_fn(tan=CONE_HALF_ANGLE_TAN):
    """The builder's own ``_section_branches``, executed.

    Deliberately *not* a reimplementation. Hand-copying this arithmetic into the
    test would let every assertion below pass while the scene shipped something
    else — which is the one failure this file exists to catch.
    """
    code = scene_code_for(_plan(half_angle_tan=tan))
    body = [
        node for node in ast.parse(code).body
        if (isinstance(node, ast.FunctionDef) and node.name == "_section_branches")
        or (isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id in _SECTION_GLOBALS
            for t in node.targets))
    ]
    namespace = {"np": np}
    exec(compile(ast.Module(body=body, type_ignores=[]), "<cone>", "exec"), namespace)
    return namespace["_section_branches"]


def _strokes(h, m, tan=CONE_HALF_ANGLE_TAN):
    """Every stroke the scene would draw for this plane."""
    return _section_fn(tan)(h, m)


def _runs(h, m, tan=CONE_HALF_ANGLE_TAN):
    """Connected pieces of the section. Each is drawn as a ±y stroke pair."""
    strokes = _strokes(h, m, tan)
    assert len(strokes) % 2 == 0, "every run is stroked twice, once per sign of y"
    return len(strokes) // 2


class TestClassification:
    """Which curve the plane's tilt produces, from the sign of ``a``."""

    def test_a_horizontal_plane_gives_one_closed_run(self):
        assert _runs(1.0, 0.0) == 1

    def test_a_slight_tilt_still_gives_one_run(self):
        """An ellipse — closed, so a single contiguous span of x."""
        assert _runs(1.0, 0.55) == 1

    def test_the_parabola_tilt_is_derived_from_the_cone(self):
        """Parallel to a slant line means m = 1/T exactly.

        A hardcoded slope stops being the parabola the moment the cone's angle
        changes, and the beat narrated "parallel to a slant line" would then be
        showing an ellipse.
        """
        m = 1.0 / CONE_HALF_ANGLE_TAN
        assert CONE_HALF_ANGLE_TAN ** 2 * m ** 2 - 1.0 == pytest.approx(0.0)

    def test_the_parabola_survives_floating_point(self):
        """``a`` is zero only up to rounding at this tilt.

        An exact ``r >= 0`` test drops the whole section for the frames either
        side of it, so the curve blinks out at the exact moment it is named.
        """
        assert _runs(1.0, 1.0 / CONE_HALF_ANGLE_TAN) >= 1

    def test_a_steep_tilt_splits_into_two_branches(self):
        """The hyperbola, one branch per nappe."""
        assert _runs(1.0, 2.3) == 2

    def test_the_parabola_is_not_drawn_as_a_closed_loop(self):
        """Its two halves are separate strokes.

        Joined into one path they are indistinguishable wherever the section
        closes itself, but where the run instead ends against the cone's rim the
        join lays a chord straight across the opening — and a parabola drawn
        with a lid is a different curve from the one being narrated.
        """
        strokes = _strokes(1.0, 1.0 / CONE_HALF_ANGLE_TAN)
        assert len(strokes) == 2
        upper, lower = strokes
        assert max(p[1] for p in upper) > 0.1, "the +y half"
        assert min(p[1] for p in lower) < -0.1, "the -y half"


class TestDegenerateCases:
    """Through the apex, the same expression collapses — no special casing."""

    def test_a_shallow_cut_through_the_apex_is_a_single_point(self):
        """Below two sampled points there is nothing to stroke, which is what
        leaves only the apex dot on screen — the point section.
        """
        assert _strokes(0.0, 0.55) == []

    def test_the_parabola_tilt_through_the_apex_is_one_line(self):
        assert _runs(0.0, 1.0 / CONE_HALF_ANGLE_TAN) == 1

    def test_a_steep_cut_through_the_apex_is_two_crossed_lines(self):
        strokes = _strokes(0.0, 2.3)
        assert len(strokes) == 2, "one x-span, stroked once per sign of y"
        xs = [p[0] for p in strokes[0]]
        assert min(xs) < 0 < max(xs), "the lines cross at the apex"
        # The two strokes are mirror images through y = 0, which is what makes
        # them read as an X rather than as one bent line.
        assert strokes[0][0][1] == pytest.approx(-strokes[1][0][1])


# ---------------------------------------------------------------- the scene

class TestScene:

    def test_the_scene_is_valid_python(self):
        ast.parse(scene_code_for(_plan()))

    def test_every_step_is_on_the_narration_timeline(self):
        keys = [key for _, key in _beat_keys(scene_code_for(_plan()))]
        assert keys == [f"b{i:02d}" for i in range(1, 9)]

    def test_the_four_sweeps_stretch(self):
        """The tilt is the argument, so it must occupy its whole sentence — a
        plain beat would finish the sweep early and hold a frozen frame.
        """
        stretched = [key for helper, key in _beat_keys(scene_code_for(_plan()))
                     if helper == "_beat_stretch"]
        assert stretched == ["b03", "b04", "b05", "b06", "b07"]

    def test_it_renders_in_english_by_default(self):
        code = scene_code_for(_plan())
        assert "Perpendicular to the axis: a circle" in code
        assert untranslated(code) == []

    def test_the_captions_are_authored_not_translated(self):
        """English is the source now, not an output of the label catalog.

        This replaces a test asserting Chinese was "one argument away".
        cone_slice's captions are written in English directly, so asking for
        the authored language no longer produces Chinese -- there is none left
        in the scene to produce. Layout follows: these were tuned against a
        script where a 20-character caption becomes ~66 in English, so `_t`
        was shrinking every translated line into a frame sized for the denser
        one.
        """
        code = scene_code_for(_plan())
        assert "Through the apex: the section shrinks to a point" in code
        rendered = [ln for ln in code.splitlines() if "_t(" in ln]
        assert not any(any("\u4e00" <= c <= "\u9fff" for c in ln) for ln in rendered), (
            "a rendered label still carries Chinese")

    def test_the_half_angle_reaches_the_scene(self):
        assert "CONE_T = 1.5" in scene_code_for(_plan(half_angle_tan=1.5))

    @pytest.mark.parametrize("bad", ["wide", None, 0.0, 100.0])
    def test_an_undrawable_half_angle_falls_back(self, bad):
        """A video beats a traceback — but see the precondition below."""
        code = scene_code_for(_plan(half_angle_tan=bad))
        assert f"CONE_T = {CONE_HALF_ANGLE_TAN!r}" in code


class TestPreconditions:
    """The clamp above is silent. This is what makes it not."""

    def test_a_sound_plan_passes(self):
        assert validate(_plan(half_angle_tan=1.2)) == []

    def test_an_absent_half_angle_is_fine(self):
        assert validate(_plan()) == []

    def test_a_non_numeric_half_angle_is_refused(self):
        violations = validate(_plan(half_angle_tan="wide"))
        assert blocking(violations)
        assert "half_angle_tan" in str(violations[0])

    @pytest.mark.parametrize("bad", [0.0, CONE_TAN_MIN, CONE_TAN_MAX, 50.0])
    def test_an_unreadable_cone_is_refused(self, bad):
        assert blocking(validate(_plan(half_angle_tan=bad)))

    def test_the_check_and_the_builder_agree_on_what_is_drawable(self):
        """A check that passes a value the builder then replaces is worse than
        no check: it reports the render as faithful when it is not.
        """
        for value in (0.2, 0.8, 2.0, 5.0):
            assert not blocking(validate(_plan(half_angle_tan=value)))
            assert f"CONE_T = {float(value)!r}" in scene_code_for(
                _plan(half_angle_tan=value))
