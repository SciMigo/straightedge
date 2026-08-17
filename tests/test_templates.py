import ast

import pytest

from straightedge.labels import AUTHORED_LANGUAGE
from straightedge.models import AnimationPlan, Topic
from straightedge.templates import SCENE_CLASS_NAME
from straightedge.templates import scene_code_for as _scene_code_for


def scene_code_for(plan, **kwargs):
    """What a builder *authors*, which is not what a caller is served.

    The shipped default is English — the launch market — but the builders are
    written in Chinese and translated on the way out. Asserting on builder
    content therefore means asking for the authored language explicitly;
    riding the default would silently turn every assertion in this file into a
    test of the translation catalog rather than of the builder.
    """
    kwargs.setdefault("language", AUTHORED_LANGUAGE)
    return _scene_code_for(plan, **kwargs)


def _plan(topic: str) -> AnimationPlan:
    return AnimationPlan(topic=topic, title_zh="", objective_zh="", english_prompt="")


@pytest.mark.parametrize("topic", Topic.ALL)
def test_template_is_valid_python(topic):
    # Guards against typos shipping broken scenes that only fail at render time.
    ast.parse(scene_code_for(_plan(topic)))


@pytest.mark.parametrize("topic", Topic.ALL)
def test_template_defines_scene_class(topic):
    # renderer.render_scene() targets templates.SCENE_CLASS_NAME.
    tree = ast.parse(scene_code_for(_plan(topic)))
    class_names = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    assert SCENE_CLASS_NAME in class_names


def test_unknown_topic_falls_back_to_geometry_scene():
    assert scene_code_for(_plan("nonsense")) == scene_code_for(_plan(Topic.GEOMETRY))


def test_preamble_pins_requested_font():
    code = scene_code_for(_plan(Topic.GEOMETRY), font="My CJK Font")
    assert 'CJK_FONT = "My CJK Font"' in code


def test_scene_body_uses_cjk_text_helper_not_bare_text():
    # Labels must go through _t() so they pick up the pinned font. The only
    # bare Text( call allowed is inside the _t() helper in the preamble.
    code = scene_code_for(_plan(Topic.TRIG))
    body = code.split("class GeneratedScene", 1)[1]
    assert "_t(" in body
    assert "Text(" not in body


def test_function_scene_embeds_parsed_expression_as_numpy():
    plan = AnimationPlan(
        topic=Topic.FUNCTION,
        title_zh="",
        objective_zh="",
        english_prompt="",
        parameters={"expression": "2 * sin(3 * x) + 1"},
    )
    code = scene_code_for(plan)
    ast.parse(code)  # valid python
    assert "return 2 * np.sin(3 * x) + 1" in code


def test_function_scene_title_uses_mathtex_for_formula():
    plan = AnimationPlan(
        topic=Topic.FUNCTION,
        title_zh="",
        objective_zh="",
        english_prompt="",
        parameters={"expression": "x ** 2 - 4 * x + 3"},
    )
    code = scene_code_for(plan)
    assert 'MathTex(r"y = x^{2} - 4x + 3", font_size=34)' in code
    assert "函数 y = x^2 - 4x + 3 的图像" not in code


def test_function_scene_with_unsafe_expression_falls_back_safely():
    plan = AnimationPlan(
        topic=Topic.FUNCTION,
        title_zh="",
        objective_zh="",
        english_prompt="",
        parameters={"expression": "os.system('x')"},
    )
    code = scene_code_for(plan)
    ast.parse(code)
    assert "os.system" not in code
    assert "return x ** 2" in code


def test_solid_overview_scene_uses_make_cube_and_vertex_labels():
    from straightedge.solids3d import Concept3D

    plan = AnimationPlan(
        topic=Topic.THREE_D,
        concept=Concept3D.SOLID_OVERVIEW,
        title_zh="",
        objective_zh="",
        english_prompt="",
        parameters={
            "solid_spec": {
                "kind": "cube",
                "params": {"side": 2.0},
                "name": "ABCD-A1B1C1D1",
            },
        },
    )
    code = scene_code_for(plan)
    ast.parse(code)
    assert 'make_cube(side=2.0, name="ABCD-A1B1C1D1")' in code
    assert "label_vertices(verts)" in code
    assert r"V = a^{3} = 2^{3} = 8" in code
    assert "ABCD-A_{1}B_{1}C_{1}D_{1}" in code


def test_three_d_default_concept_falls_back_to_sphere_section():
    # No concept set -> existing sphere/plane-section scene, not solid_overview.
    plan = AnimationPlan(
        topic=Topic.THREE_D,
        title_zh="",
        objective_zh="",
        english_prompt="",
    )
    code = scene_code_for(plan)
    scene_body = code.split("class GeneratedScene", 1)[1]
    assert "Sphere(" in scene_body
    assert "make_cube" not in scene_body
    assert "make_box" not in scene_body


def test_preamble_embeds_solid_helpers():
    code = scene_code_for(_plan(Topic.GEOMETRY))
    # Helpers ship in every scene so 3D templates can call them inline.
    for helper in (
        "def make_box(",
        "def make_cube(",
        "def make_regular_prism(",
        "def make_regular_pyramid(",
        "def make_tetrahedron(",
        "def make_cylinder(",
        "def make_cone(",
        "def label_vertices(",
    ):
        assert helper in code


@pytest.mark.parametrize(
    "kind,params,name,expected_fragment",
    [
        (
            "regular_prism",
            {"n_sides": 4, "radius": 1.0, "height": 3.0},
            "ABCD-A1B1C1D1",
            'make_regular_prism(n_sides=4, radius=1.0, height=3.0, name="ABCD-A1B1C1D1")',
        ),
        (
            "regular_pyramid",
            {"n_sides": 3, "radius": 1.0, "height": 2.0},
            "P-ABC",
            'make_regular_pyramid(n_sides=3, radius=1.0, height=2.0, name="P-ABC")',
        ),
        (
            "tetrahedron",
            {"side": 2.0},
            "ABCD",
            'make_tetrahedron(side=2.0, name="ABCD")',
        ),
        (
            "cylinder",
            {"radius": 1.0, "height": 2.0},
            "O-O1",
            'make_cylinder(radius=1.0, height=2.0, name="O-O1")',
        ),
        (
            "cone",
            {"radius": 1.0, "height": 2.0},
            "P-O",
            'make_cone(radius=1.0, height=2.0, name="P-O")',
        ),
    ],
)
def test_solid_overview_scene_emits_expected_call_for_each_kind(
    kind, params, name, expected_fragment
):
    from straightedge.solids3d import Concept3D

    plan = AnimationPlan(
        topic=Topic.THREE_D,
        concept=Concept3D.SOLID_OVERVIEW,
        title_zh="",
        objective_zh="",
        english_prompt="",
        parameters={"solid_spec": {"kind": kind, "params": params, "name": name}},
    )
    code = scene_code_for(plan)
    ast.parse(code)
    scene_body = code.split("class GeneratedScene", 1)[1]
    assert expected_fragment in scene_body
    assert "label_vertices(verts)" in scene_body


def test_cube_section_scene_emits_safe_section_call():
    from straightedge.solids3d import Concept3D

    plan = AnimationPlan(
        topic=Topic.THREE_D,
        concept=Concept3D.CUBE_SECTION,
        title_zh="",
        objective_zh="",
        english_prompt="",
        parameters={
            "solid_spec": {
                "kind": "cube",
                "params": {"side": 2.0},
                "name": "ABCD-A1B1C1D1",
            },
            "section_points": ["D", "A1", "C1"],
        },
    )
    code = scene_code_for(plan)
    ast.parse(code)
    scene_body = code.split("class GeneratedScene", 1)[1]
    assert 'make_cube(side=2.0, name="ABCD-A1B1C1D1")' in scene_body
    assert 'cube_section(verts, ["D", "A1", "C1"])' in scene_body
    # Each section-defining point is highlighted as a Dot3D in the scene.
    assert '["D", "A1", "C1"]' in scene_body
    assert "Dot3D(point=verts[n]" in scene_body
    # MathTex caption uses subscripted point names.
    assert "D, A_{1}, C_{1}" in scene_body


def test_cube_section_scene_sanitizes_unsafe_section_points():
    # Bad point names in the plan must not be interpolated into the source.
    from straightedge.solids3d import Concept3D

    plan = AnimationPlan(
        topic=Topic.THREE_D,
        concept=Concept3D.CUBE_SECTION,
        title_zh="",
        objective_zh="",
        english_prompt="",
        parameters={
            "solid_spec": {
                "kind": "cube",
                "params": {"side": 2.0},
                "name": "ABCD-A1B1C1D1",
            },
            "section_points": ['"); import os; #', "B1", "Z9"],
        },
    )
    code = scene_code_for(plan)
    ast.parse(code)
    scene_body = code.split("class GeneratedScene", 1)[1]
    assert "import os" not in scene_body
    # Falls back to the canonical triangle when the input is unsafe.
    assert 'cube_section(verts, ["D", "A1", "C1"])' in scene_body


def test_trig_transform_scene_renders_title_and_annotations():
    from straightedge.trig import Concept as ConceptTrig

    plan = AnimationPlan(
        topic=Topic.TRIG,
        concept=ConceptTrig.GRAPH_TRANSFORM,
        title_zh="",
        objective_zh="",
        english_prompt="",
        parameters={
            "trig_spec": {
                "func": "sin", "A": 2.0, "omega": 3.0,
                "phi": 0.7853981633974483, "k": 1.0,
            },
        },
    )
    code = scene_code_for(plan)
    ast.parse(code)
    scene_body = code.split("class GeneratedScene", 1)[1]
    # Title formula renders in canonical LaTeX form.
    assert r"y = 2\sin\left(3x + \frac{\pi}{4}\right) + 1" in scene_body
    # Annotations: midline, period, amplitude (sin has finite amplitude).
    assert "y = 1" in scene_body
    assert r"T = \frac{2\pi}{3}" in scene_body
    assert "A = 2" in scene_body
    # The transformation animation: base curve morphs into the target.
    assert "np.sin(x)" in scene_body
    assert "ReplacementTransform(base, target)" in scene_body


def test_trig_transform_scene_omits_amplitude_for_tan():
    # tan has no finite amplitude — the scene must not emit an amp brace.
    from straightedge.trig import Concept as ConceptTrig

    plan = AnimationPlan(
        topic=Topic.TRIG,
        concept=ConceptTrig.GRAPH_TRANSFORM,
        title_zh="",
        objective_zh="",
        english_prompt="",
        parameters={
            "trig_spec": {"func": "tan", "A": 1.0, "omega": 0.5, "phi": 0.0, "k": 0.0},
        },
    )
    code = scene_code_for(plan)
    ast.parse(code)
    scene_body = code.split("class GeneratedScene", 1)[1]
    assert "np.tan(" in scene_body
    assert r"T = 2\pi" in scene_body  # period of tan(x/2)
    # No amplitude brace primitive or play call — only the None fallback.
    assert "Brace(amp_line" not in scene_body
    assert "Create(amp_line)" not in scene_body


def test_unit_circle_to_sine_scene_uses_trace_and_projection():
    from straightedge.trig import Concept as ConceptTrig

    plan = AnimationPlan(
        topic=Topic.TRIG,
        concept=ConceptTrig.UNIT_CIRCLE_TO_SINE,
        title_zh="",
        objective_zh="",
        english_prompt="",
    )
    code = scene_code_for(plan)
    ast.parse(code)
    scene_body = code.split("class GeneratedScene", 1)[1]
    assert "单位圆生成正弦函数" in scene_body
    assert "Circle(radius=radius" in scene_body
    assert "ValueTracker" in scene_body
    assert "TracedPath" in scene_body
    assert "DashedLine" in scene_body
    assert r"y = \sin x" in scene_body
    assert r"T = 2\pi" in scene_body


def test_parabola_focus_directrix_scene_uses_moving_invariant():
    from straightedge.conics import ConceptConic

    plan = AnimationPlan(
        topic=Topic.CONIC,
        concept=ConceptConic.PARABOLA_FOCUS_DIRECTRIX,
        title_zh="",
        objective_zh="",
        english_prompt="",
    )
    code = scene_code_for(plan)
    ast.parse(code)
    scene_body = code.split("class GeneratedScene", 1)[1]
    assert "抛物线的焦点与准线" in scene_body
    assert "plot_parametric_curve" in scene_body
    assert "directrix" in scene_body
    assert "ValueTracker" in scene_body
    assert "RightAngle" in scene_body
    assert "PF = d(P, 准线)" in scene_body


def test_ellipse_foci_scene_uses_moving_distance_sum():
    from straightedge.conics import ConceptConic

    plan = AnimationPlan(
        topic=Topic.CONIC,
        concept=ConceptConic.ELLIPSE_FOCI,
        title_zh="",
        objective_zh="",
        english_prompt="",
    )
    code = scene_code_for(plan)
    ast.parse(code)
    scene_body = code.split("class GeneratedScene", 1)[1]
    assert "椭圆的焦点距离和" in scene_body
    assert "ValueTracker" in scene_body
    assert "always_redraw" in scene_body
    assert "PF_1 + PF_2 = 2a" in scene_body
    assert "rate_func=linear" in scene_body


def test_conic_without_specific_concept_uses_static_ellipse_fallback():
    plan = AnimationPlan(
        topic=Topic.CONIC,
        title_zh="",
        objective_zh="",
        english_prompt="",
    )
    code = scene_code_for(plan)
    scene_body = code.split("class GeneratedScene", 1)[1]
    assert "椭圆的焦点与长轴" in scene_body
    assert "ValueTracker" not in scene_body


def test_three_views_scene_emits_layout_for_cube():
    from straightedge.solids3d import Concept3D

    plan = AnimationPlan(
        topic=Topic.THREE_D,
        concept=Concept3D.THREE_VIEWS,
        title_zh="",
        objective_zh="",
        english_prompt="",
        parameters={
            "solid_spec": {
                "kind": "cube",
                "params": {"side": 2.0},
                "name": "ABCD-A1B1C1D1",
            },
        },
    )
    code = scene_code_for(plan)
    ast.parse(code)
    scene_body = code.split("class GeneratedScene", 1)[1]
    # Calls the runtime helper with the safe kind/params payload.
    assert 'three_views("cube", {"side": 2.0})' in scene_body
    # Chinese view labels are present (rendered via _t for CJK font support).
    for label in ("正视图", "侧视图", "俯视图"):
        assert label in scene_body
    # Alignment guides for the textbook 长对正 / 高平齐 conventions.
    assert "长对正" in scene_body
    assert "高平齐" in scene_body
    assert "DashedLine(" in scene_body


def test_three_views_scene_uses_kind_specific_helper_call():
    # Pyramid emits the regular_pyramid params payload, not the cube one.
    from straightedge.solids3d import Concept3D

    plan = AnimationPlan(
        topic=Topic.THREE_D,
        concept=Concept3D.THREE_VIEWS,
        title_zh="",
        objective_zh="",
        english_prompt="",
        parameters={
            "solid_spec": {
                "kind": "regular_pyramid",
                "params": {"n_sides": 4, "radius": 1.0, "height": 2.0},
                "name": "P-ABCD",
            },
        },
    )
    code = scene_code_for(plan)
    ast.parse(code)
    scene_body = code.split("class GeneratedScene", 1)[1]
    assert 'three_views("regular_pyramid"' in scene_body
    assert '"n_sides": 4' in scene_body
    # Title uses the pyramid name + Chinese kind label.
    assert "正四棱锥" in scene_body
    assert "P-ABCD" in scene_body


def test_derivative_tangent_scene_uses_secant_and_tangent():
    from straightedge.calculus import ConceptCalculus

    plan = AnimationPlan(
        topic=Topic.CALCULUS,
        concept=ConceptCalculus.DERIVATIVE_TANGENT,
        title_zh="",
        objective_zh="",
        english_prompt="",
        parameters={"expression": "x ** 2"},
    )
    code = scene_code_for(plan)
    ast.parse(code)
    scene_body = code.split("class GeneratedScene", 1)[1]
    assert "导数" in scene_body
    assert "ValueTracker" in scene_body
    assert "slope_at" in scene_body
    assert r"\frac{dy}{dx}=f'(x)" in scene_body
    assert "ReplacementTransform(secant.copy(), tangent)" in scene_body


def test_taylor_series_scene_builds_polynomial_sequence():
    from straightedge.calculus import ConceptCalculus

    plan = AnimationPlan(
        topic=Topic.CALCULUS,
        concept=ConceptCalculus.TAYLOR_SERIES,
        title_zh="",
        objective_zh="",
        english_prompt="",
    )
    code = scene_code_for(plan)
    ast.parse(code)
    scene_body = code.split("class GeneratedScene", 1)[1]
    assert "sin(x) 的泰勒展开" in scene_body
    assert r"P_1(x)=x" in scene_body
    assert r"P_3(x)=x-\frac{x^3}{3!}" in scene_body
    assert r"P_5(x)=x-\frac{x^3}{3!}+\frac{x^5}{5!}" in scene_body
    assert r"P_7(x)=x-\frac{x^3}{3!}+\frac{x^5}{5!}-\frac{x^7}{7!}" in scene_body
    assert "ReplacementTransform(current_curve, approx_curves[i])" in scene_body


def test_taylor_series_scene_supports_cosine_variant():
    from straightedge.calculus import ConceptCalculus

    plan = AnimationPlan(
        topic=Topic.CALCULUS,
        concept=ConceptCalculus.TAYLOR_SERIES,
        title_zh="",
        objective_zh="",
        english_prompt="",
        parameters={"function": "cos"},
    )
    code = scene_code_for(plan)
    ast.parse(code)
    scene_body = code.split("class GeneratedScene", 1)[1]
    assert "cos(x) 的泰勒展开" in scene_body
    assert "np.cos(x)" in scene_body
    assert r"P_0(x)=1" in scene_body
    assert r"P_2(x)=1-\frac{x^2}{2!}" in scene_body
    assert r"P_6(x)=1-\frac{x^2}{2!}+\frac{x^4}{4!}-\frac{x^6}{6!}" in scene_body
    # The sine-only formulas must not leak into the cosine scene.
    assert r"P_1(x)=x" not in scene_body


def test_riemann_integral_scene_uses_refined_rectangles():
    from straightedge.calculus import ConceptCalculus

    plan = AnimationPlan(
        topic=Topic.CALCULUS,
        concept=ConceptCalculus.RIEMANN_INTEGRAL,
        title_zh="",
        objective_zh="",
        english_prompt="",
        parameters={"expression": "x ** 2 + 1"},
    )
    code = scene_code_for(plan)
    ast.parse(code)
    scene_body = code.split("class GeneratedScene", 1)[1]
    assert "定积分" in scene_body
    assert "def rectangles(n):" in scene_body
    assert "rectangles(6)" in scene_body
    assert "rectangles(24)" in scene_body
    assert r"\int_a^b f(x)\,dx" in scene_body


def test_ftc_accumulation_scene_traces_area_function():
    from straightedge.calculus import ConceptCalculus

    plan = AnimationPlan(
        topic=Topic.CALCULUS,
        concept=ConceptCalculus.FTC_ACCUMULATION,
        title_zh="",
        objective_zh="",
        english_prompt="",
        parameters={"expression": "x ** 2"},
    )
    code = scene_code_for(plan)
    ast.parse(code)
    scene_body = code.split("class GeneratedScene", 1)[1]
    assert "微积分基本定理" in scene_body
    assert "get_area" in scene_body
    assert "TracedPath" in scene_body
    # F(x) is precomputed once and looked up by interpolation rather than
    # re-integrated on every always_redraw frame.
    assert "np.interp(x, accum_grid, accum_table)" in scene_body
    assert "np.cumsum" in scene_body
    assert r"F'(x)=f(x)" in scene_body


def test_trig_basic_scene_still_used_when_no_concept():
    # Bare 正弦函数 keyword request (no formula) keeps the stock scene.
    plan = AnimationPlan(
        topic=Topic.TRIG,
        title_zh="",
        objective_zh="",
        english_prompt="",
    )
    code = scene_code_for(plan)
    scene_body = code.split("class GeneratedScene", 1)[1]
    assert "正弦函数的周期与振幅" in scene_body
    assert "ReplacementTransform" not in scene_body


def test_pyramid_scene_title_uses_apex_base_name_not_cube_default():
    # Regression: vertex_name_latex must be told the kind, otherwise a
    # pyramid name like 'P-ABCD' fails the cube/box pattern and gets replaced
    # by the wrong default in the title.
    from straightedge.solids3d import Concept3D

    plan = AnimationPlan(
        topic=Topic.THREE_D,
        concept=Concept3D.SOLID_OVERVIEW,
        title_zh="",
        objective_zh="",
        english_prompt="",
        parameters={
            "solid_spec": {
                "kind": "regular_pyramid",
                "params": {"n_sides": 4, "radius": 1.0, "height": 2.0},
                "name": "P-ABCD",
            },
        },
    )
    code = scene_code_for(plan)
    assert "P-ABCD" in code
    assert "ABCD-A_{1}B_{1}C_{1}D_{1}" not in code.split("class GeneratedScene", 1)[1]
