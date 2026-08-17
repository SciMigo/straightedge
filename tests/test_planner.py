import pytest

from straightedge.models import Topic
from straightedge.planner import build_plan
from straightedge.solids3d import Concept3D


def test_detects_trig_request():
    plan = build_plan("画一个正弦函数，标出周期和振幅")
    assert plan.topic == "trig"
    assert "sine" in plan.english_prompt.lower()


def test_detects_conic_request():
    plan = build_plan("画一个椭圆，显示两个焦点和长轴")
    assert plan.topic == "conic"
    assert "ellipse" in plan.english_prompt.lower()


def test_parabola_focus_directrix_routes_to_specific_concept():
    from straightedge.conics import ConceptConic

    plan = build_plan("展示抛物线的焦点和准线，移动点 P 显示距离相等")
    assert plan.topic == Topic.CONIC
    assert plan.concept == ConceptConic.PARABOLA_FOCUS_DIRECTRIX
    assert "focus-directrix" in plan.english_prompt
    assert "PF = d(P, directrix)" in plan.english_prompt


def test_ellipse_foci_routes_to_specific_concept():
    from straightedge.conics import ConceptConic

    plan = build_plan("画一个椭圆，显示两个焦点，移动点 P，动态展示 PF1 + PF2 保持不变")
    assert plan.topic == Topic.CONIC
    assert plan.concept == ConceptConic.ELLIPSE_FOCI
    assert "PF1 + PF2 = 2a" in plan.english_prompt
    assert "foci definition" in plan.english_prompt


def test_detects_3d_request():
    plan = build_plan("画一个三维球体和平面截面")
    assert plan.topic == "3d"
    assert "ThreeDScene" in plan.english_prompt


def test_defaults_to_geometry():
    plan = build_plan("画一个三角形并标出角")
    assert plan.topic == "geometry"


def test_bare_cone_routes_to_3d_not_conic():
    # 圆锥 alone is a 3D cone solid, not a conic section.
    assert build_plan("画一个圆锥").topic == "3d"


def test_conic_section_routes_to_conic():
    # 圆锥曲线 is the conic-section signal.
    assert build_plan("讲解圆锥曲线中的椭圆").topic == "conic"


def test_no_keyword_defaults_to_geometry():
    assert build_plan("随便讲点东西").topic == "geometry"


def test_explicit_formula_routes_to_function_grapher():
    plan = build_plan("画 y=x^2-4x+3，标出顶点和零点")
    assert plan.topic == Topic.FUNCTION
    assert plan.parameters["expression"] == "x ** 2 - 4 * x + 3"


def test_formula_with_derivative_keyword_routes_to_calculus_tangent():
    from straightedge.calculus import ConceptCalculus

    plan = build_plan("画 y=x^2 的导数，用割线逼近切线并解释斜率")
    assert plan.topic == Topic.CALCULUS
    assert plan.concept == ConceptCalculus.DERIVATIVE_TANGENT
    assert plan.parameters["expression"] == "x ** 2"
    assert "secant line" in plan.english_prompt


def test_formula_with_integral_keyword_routes_to_riemann_integral():
    from straightedge.calculus import ConceptCalculus

    plan = build_plan("画 y=x^2+1 在区间上的积分面积，用黎曼矩形展示")
    assert plan.topic == Topic.CALCULUS
    assert plan.concept == ConceptCalculus.RIEMANN_INTEGRAL
    assert plan.parameters["expression"] == "x ** 2 + 1"
    assert "Riemann rectangles" in plan.english_prompt


def test_ftc_keyword_routes_to_accumulation_concept():
    from straightedge.calculus import ConceptCalculus

    plan = build_plan("用 y=x^2 展示微积分基本定理，变上限面积函数 F(x)")
    assert plan.topic == Topic.CALCULUS
    assert plan.concept == ConceptCalculus.FTC_ACCUMULATION
    assert "F'(x)=f(x)" in plan.english_prompt


def test_calculus_keyword_without_formula_uses_default_derivative_scene():
    from straightedge.calculus import ConceptCalculus

    plan = build_plan("解释导数为什么是瞬时变化率")
    assert plan.topic == Topic.CALCULUS
    assert plan.concept == ConceptCalculus.DERIVATIVE_TANGENT
    assert plan.parameters["expression"] == "x ** 2"


def test_taylor_series_request_routes_to_calculus_not_basic_trig():
    from straightedge.calculus import ConceptCalculus

    plan = build_plan("展示 sin(x) 的泰勒展开，逐项加入多项式逼近曲线")
    assert plan.topic == Topic.CALCULUS
    assert plan.concept == ConceptCalculus.TAYLOR_SERIES
    assert "Taylor series of sin(x)" in plan.english_prompt
    assert plan.parameters["function"] == "sin"


def test_taylor_series_request_for_cosine_uses_cosine_variant():
    from straightedge.calculus import ConceptCalculus

    plan = build_plan("展示 cos(x) 的泰勒展开，逐项加入多项式逼近曲线")
    assert plan.topic == Topic.CALCULUS
    assert plan.concept == ConceptCalculus.TAYLOR_SERIES
    assert plan.parameters["function"] == "cos"
    assert "Taylor series of cos(x)" in plan.english_prompt


def test_bare_area_keyword_does_not_route_geometry_to_calculus():
    # 面积 alone is common in plain geometry/3D and must not hijack routing.
    assert build_plan("画一个三角形并求它的面积").topic == Topic.GEOMETRY
    assert build_plan("计算圆的面积").topic == Topic.GEOMETRY


def test_area_with_curve_context_still_routes_to_integral():
    from straightedge.calculus import ConceptCalculus

    plan = build_plan("展示曲线下方的面积")
    assert plan.topic == Topic.CALCULUS
    assert plan.concept == ConceptCalculus.RIEMANN_INTEGRAL


def test_formula_takes_precedence_over_topic_keywords():
    # Containing 正弦 doesn't matter — the formula drives routing. sin(x)
    # is a trig transformation, so it lands on the annotated trig scene
    # rather than the bare-keyword stock scene.
    from straightedge.trig import Concept as ConceptTrig

    plan = build_plan("画正弦函数 y=sin(x)")
    assert plan.topic == Topic.TRIG
    assert plan.concept == ConceptTrig.GRAPH_TRANSFORM


def test_injection_attempt_falls_back_to_keyword_routing():
    # parse_function rejects it, so routing must not crash or run code.
    plan = build_plan("y=__import__('os').system('echo hi')")
    assert plan.topic != Topic.FUNCTION


def test_cube_request_routes_to_solid_overview_concept():
    plan = build_plan("画一个正方体 ABCD-A₁B₁C₁D₁，棱长 2")
    assert plan.topic == Topic.THREE_D
    assert plan.concept == Concept3D.SOLID_OVERVIEW
    spec = plan.parameters["solid_spec"]
    assert spec["kind"] == "cube"
    assert spec["params"] == {"side": 2.0}
    assert spec["name"] == "ABCD-A1B1C1D1"


def test_box_request_routes_to_solid_overview_concept():
    plan = build_plan("画长方体 ABCD-A1B1C1D1，长 3 宽 2 高 4")
    assert plan.concept == Concept3D.SOLID_OVERVIEW
    assert plan.parameters["solid_spec"]["kind"] == "box"


def test_generic_3d_falls_back_to_sphere_section_concept():
    plan = build_plan("画一个三维球体和平面截面")
    assert plan.topic == Topic.THREE_D
    assert plan.concept == Concept3D.SPHERE_SECTION


@pytest.mark.parametrize(
    "request_zh,expected_kind",
    [
        ("画正四棱柱 ABCD-A₁B₁C₁D₁，底面边长 2，高 3", "regular_prism"),
        ("画正三棱锥 P-ABC 底面边长 2 高 3", "regular_pyramid"),
        ("画一个正四面体 ABCD，棱长 2", "tetrahedron"),
        ("画一个圆柱，底面半径 1，高 2", "cylinder"),
        ("画一个圆锥，底面半径 1，高 2", "cone"),
    ],
)
def test_new_solid_kinds_route_to_solid_overview(request_zh, expected_kind):
    plan = build_plan(request_zh)
    assert plan.topic == Topic.THREE_D
    assert plan.concept == Concept3D.SOLID_OVERVIEW
    assert plan.parameters["solid_spec"]["kind"] == expected_kind


def test_cube_with_section_request_routes_to_cube_section_concept():
    plan = build_plan("画正方体 ABCD-A₁B₁C₁D₁，过 D、A₁、C₁ 三点的截面")
    assert plan.topic == Topic.THREE_D
    assert plan.concept == Concept3D.CUBE_SECTION
    assert plan.parameters["solid_spec"]["kind"] == "cube"
    assert plan.parameters["section_points"] == ["D", "A1", "C1"]


def test_cube_without_section_still_uses_solid_overview():
    # Section routing kicks in only when 截面/平面 phrasing is present.
    plan = build_plan("画正方体 ABCD-A₁B₁C₁D₁，棱长 2")
    assert plan.concept == Concept3D.SOLID_OVERVIEW
    assert "section_points" not in plan.parameters


# --- trig graph transformations ----------------------------------------------


def test_trig_transformation_formula_routes_to_graph_transform():
    from straightedge.trig import Concept as ConceptTrig

    plan = build_plan("画 y = 2 sin(3x + π/4) + 1")
    assert plan.topic == Topic.TRIG
    assert plan.concept == ConceptTrig.GRAPH_TRANSFORM
    spec = plan.parameters["trig_spec"]
    assert spec["func"] == "sin"
    assert spec["A"] == 2.0
    assert spec["omega"] == 3.0
    assert spec["k"] == 1.0


def test_non_trig_formula_still_routes_to_function_grapher():
    # sin(x) + cos(x) is not of the A·f(ωx+φ)+k form — fall through.
    plan = build_plan("画 y = sin(x) + cos(x)")
    assert plan.topic == Topic.FUNCTION


def test_trig_keyword_without_formula_uses_basic_scene():
    # No formula → keyword routing → stock trig scene, no transform concept.
    plan = build_plan("画一个正弦函数，标出周期和振幅")
    assert plan.topic == Topic.TRIG
    assert plan.concept is None


def test_unit_circle_to_sine_routes_to_specific_concept():
    from straightedge.trig import Concept as ConceptTrig

    plan = build_plan("用单位圆动态生成正弦函数图像，右侧画出 y=sin(x) 的轨迹")
    assert plan.topic == Topic.TRIG
    assert plan.concept == ConceptTrig.UNIT_CIRCLE_TO_SINE
    assert "unit circle" in plan.english_prompt.lower()
    assert "Trace" in plan.english_prompt


# --- 三视图 (three views) ----------------------------------------------------


@pytest.mark.parametrize(
    "request_zh,expected_kind",
    [
        ("画正方体 ABCD-A₁B₁C₁D₁，棱长 2 的三视图", "cube"),
        ("画长方体 长 3 宽 2 高 4 的三视图", "box"),
        ("画一个圆柱 底面半径 1 高 2 的三视图", "cylinder"),
        ("画正四棱锥 P-ABCD 底面边长 2 高 3 的三视图", "regular_pyramid"),
    ],
)
def test_three_views_request_routes_to_three_views_concept(request_zh, expected_kind):
    plan = build_plan(request_zh)
    assert plan.topic == Topic.THREE_D
    assert plan.concept == Concept3D.THREE_VIEWS
    assert plan.parameters["solid_spec"]["kind"] == expected_kind


def test_three_views_takes_priority_over_cube_section():
    # If both 三视图 and 截面 phrasing appear, 三视图 is the dominant concept
    # (a section is one view, a 三视图 layout is the full multi-view scene).
    plan = build_plan("画正方体 ABCD-A1B1C1D1 的三视图，并标出 D、A1、C1 的截面")
    assert plan.concept == Concept3D.THREE_VIEWS
