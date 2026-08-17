import ast

import pytest

from straightedge.solids3d import (
    Concept3D,
    SOLID_HELPERS_SRC,
    SolidSpec,
    cube_section_code,
    is_three_views_request,
    parse_section_points,
    parse_solid_spec,
    section_points_latex,
    solid_construction_code,
    solid_title_zh,
    solid_volume_latex,
    three_views_code,
    vertex_name_latex,
)


def test_parses_cube_with_subscripted_vertex_name():
    spec = parse_solid_spec("画正方体 ABCD-A₁B₁C₁D₁ 棱长 2")
    assert spec == SolidSpec(kind="cube", params={"side": 2.0}, name="ABCD-A1B1C1D1")


def test_parses_box_with_lwh():
    spec = parse_solid_spec("画长方体 ABCD-A1B1C1D1，长 3 宽 2 高 4")
    assert spec is not None
    assert spec.kind == "box"
    assert spec.params == {"width": 3.0, "depth": 2.0, "height": 4.0}
    assert spec.name == "ABCD-A1B1C1D1"


def test_parses_box_with_base_and_height():
    spec = parse_solid_spec("长方体 底面 3×2 高 4")
    assert spec is not None
    assert spec.params == {"width": 3.0, "depth": 2.0, "height": 4.0}


def test_cube_defaults_when_dim_missing():
    spec = parse_solid_spec("讲一下正方体的体积公式")
    assert spec == SolidSpec(kind="cube", params={"side": 2.0}, name="ABCD-A1B1C1D1")


def test_returns_none_for_non_solid_request():
    assert parse_solid_spec("画一个球和截面") is None


def test_rejects_out_of_range_dimensions():
    # Defensive: oversized values are clamped to defaults so the scene stays sane.
    spec = parse_solid_spec("正方体 棱长 99999")
    assert spec is not None and spec.params["side"] == 2.0


def test_construction_code_emits_safe_python_literal():
    spec = SolidSpec(kind="cube", params={"side": 2.5}, name="ABCD-A1B1C1D1")
    code = solid_construction_code(spec)
    # Must parse as a single call expression — no smuggled syntax.
    tree = ast.parse(code, mode="eval")
    assert isinstance(tree.body, ast.Call)
    assert code.startswith("make_cube(")


def test_construction_code_sanitizes_bad_vertex_name():
    spec = SolidSpec(kind="cube", params={"side": 2.0}, name='"); import os; #')
    code = solid_construction_code(spec)
    ast.parse(code, mode="eval")
    assert "import" not in code
    assert "ABCD-A1B1C1D1" in code


def test_solid_volume_latex_cube_and_box():
    assert solid_volume_latex(SolidSpec("cube", {"side": 2.0}, "ABCD-A1B1C1D1")) == (
        "V = a^{3} = 2^{3} = 8"
    )
    assert solid_volume_latex(SolidSpec("box", {"width": 3.0, "depth": 2.0, "height": 4.0}, "ABCD-A1B1C1D1")) == (
        r"V = abc = 3 \cdot 2 \cdot 4 = 24"
    )


def test_vertex_name_latex_renders_subscripts():
    assert vertex_name_latex("ABCD-A1B1C1D1") == "ABCD-A_{1}B_{1}C_{1}D_{1}"
    # Bad names fall back to a safe default rather than raising.
    assert vertex_name_latex("not a name") == "ABCD-A_{1}B_{1}C_{1}D_{1}"


def test_solid_title_zh_per_kind():
    assert solid_title_zh(SolidSpec("cube", {"side": 1}, "ABCD-A1B1C1D1")) == "正方体"
    assert solid_title_zh(SolidSpec("box", {"width": 1, "depth": 1, "height": 1}, "ABCD-A1B1C1D1")) == "长方体"


def test_helpers_src_is_valid_python():
    # Embedded into the scene preamble — must at least parse standalone.
    ast.parse(SOLID_HELPERS_SRC)


def test_helpers_src_defines_expected_factory_functions():
    tree = ast.parse(SOLID_HELPERS_SRC)
    names = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert {"make_box", "make_cube", "label_vertices", "_subscriptify"} <= names


def test_concept3d_namespace():
    assert Concept3D.SOLID_OVERVIEW == "3d/solid_overview"
    assert Concept3D.SPHERE_SECTION == "3d/sphere_section"


# --- new solids ---------------------------------------------------------------


def test_parses_regular_prism_with_base_edge_and_height():
    spec = parse_solid_spec("画正四棱柱 ABCD-A₁B₁C₁D₁，底面边长 2，高 3")
    assert spec is not None
    assert spec.kind == "regular_prism"
    assert spec.params["n_sides"] == 4
    assert spec.params["radius"] == pytest.approx(1.0 / __import__("math").sin(__import__("math").pi / 4))
    assert spec.params["height"] == 3.0
    assert spec.name == "ABCD-A1B1C1D1"


def test_parses_hex_prism_n_sides():
    spec = parse_solid_spec("画正六棱柱 底面边长 1 高 2")
    assert spec is not None and spec.kind == "regular_prism"
    assert spec.params["n_sides"] == 6


def test_parses_regular_pyramid_with_apex_base_name():
    spec = parse_solid_spec("画正四棱锥 P-ABCD，底面边长 2，高 3")
    assert spec is not None
    assert spec.kind == "regular_pyramid"
    assert spec.params == pytest.approx({"n_sides": 4, "radius": 1.4142135623730951, "height": 3.0})
    assert spec.name == "P-ABCD"


def test_parses_triangular_pyramid_uses_three_base_letters():
    spec = parse_solid_spec("画正三棱锥 P-ABC 底面边长 2 高 3")
    assert spec is not None and spec.kind == "regular_pyramid"
    assert spec.params["n_sides"] == 3
    assert spec.name == "P-ABC"


def test_parses_tetrahedron_with_side_length():
    spec = parse_solid_spec("画一个正四面体 ABCD，棱长 2")
    assert spec == SolidSpec(kind="tetrahedron", params={"side": 2.0}, name="ABCD")


def test_parses_cylinder_with_radius_and_height():
    spec = parse_solid_spec("画一个圆柱，底面半径 1，高 2")
    assert spec == SolidSpec(kind="cylinder", params={"radius": 1.0, "height": 2.0}, name="O-O1")


def test_parses_cone_with_radius_and_height():
    spec = parse_solid_spec("画一个圆锥，底面半径 1，高 2")
    assert spec == SolidSpec(kind="cone", params={"radius": 1.0, "height": 2.0}, name="P-O")


def test_pyramid_with_bad_apex_base_name_falls_back():
    # No vertex name in request -> use the default rather than crash.
    spec = parse_solid_spec("画正四棱锥 底面边长 2 高 3")
    assert spec is not None and spec.name == "P-ABCD"


@pytest.mark.parametrize(
    "kind,params,expected_start",
    [
        ("regular_prism", {"n_sides": 4, "radius": 1.0, "height": 2.0}, "make_regular_prism(n_sides=4, "),
        ("regular_pyramid", {"n_sides": 4, "radius": 1.0, "height": 2.0}, "make_regular_pyramid(n_sides=4, "),
        ("tetrahedron", {"side": 2.0}, "make_tetrahedron(side=2.0, "),
        ("cylinder", {"radius": 1.0, "height": 2.0}, "make_cylinder(radius=1.0, "),
        ("cone", {"radius": 1.0, "height": 2.0}, "make_cone(radius=1.0, "),
    ],
)
def test_construction_code_for_new_solids_is_safe_python(kind, params, expected_start):
    from straightedge.solids3d import _DEFAULT_NAMES  # noqa: PLC2701

    spec = SolidSpec(kind=kind, params=params, name=_DEFAULT_NAMES[kind])
    code = solid_construction_code(spec)
    tree = ast.parse(code, mode="eval")
    assert isinstance(tree.body, ast.Call)
    assert code.startswith(expected_start)


def test_titles_for_new_solids():
    assert solid_title_zh(SolidSpec("regular_prism", {"n_sides": 4, "radius": 1, "height": 2}, "ABCD-A1B1C1D1")) == "正四棱柱"
    assert solid_title_zh(SolidSpec("regular_pyramid", {"n_sides": 3, "radius": 1, "height": 2}, "P-ABC")) == "正三棱锥"
    assert solid_title_zh(SolidSpec("tetrahedron", {"side": 2}, "ABCD")) == "正四面体"
    assert solid_title_zh(SolidSpec("cylinder", {"radius": 1, "height": 2}, "O-O1")) == "圆柱"
    assert solid_title_zh(SolidSpec("cone", {"radius": 1, "height": 2}, "P-O")) == "圆锥"


def test_volume_latex_for_cylinder_and_cone():
    cyl_latex = solid_volume_latex(SolidSpec("cylinder", {"radius": 1.0, "height": 2.0}, "O-O1"))
    assert r"\pi r^{2} h" in cyl_latex
    assert "2\\pi" in cyl_latex
    cone_latex = solid_volume_latex(SolidSpec("cone", {"radius": 1.0, "height": 2.0}, "P-O"))
    assert r"\frac{1}{3} \pi r^{2} h" in cone_latex


def test_helpers_src_contains_all_factory_functions():
    tree = ast.parse(SOLID_HELPERS_SRC)
    names = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert {
        "make_box",
        "make_cube",
        "make_regular_prism",
        "make_regular_pyramid",
        "make_tetrahedron",
        "make_cylinder",
        "make_cone",
        "label_vertices",
    } <= names


def test_safe_n_sides_clamps_out_of_range_values():
    # An out-of-range n_sides on a polyhedron would blow up downstream.
    spec = SolidSpec(kind="regular_prism", params={"n_sides": 99, "radius": 1.0, "height": 2.0}, name="ABCD-A1B1C1D1")
    code = solid_construction_code(spec)
    assert "n_sides=4" in code  # clamped to default


def test_pyramid_name_too_few_base_letters_rejected():
    # 正四棱锥 expects 4 base letters; a 3-letter base in the request must
    # not be silently accepted (it would mis-shape the polyhedron).
    spec = parse_solid_spec("画正四棱锥 P-ABC 底面边长 2 高 3")
    assert spec is not None and spec.name == "P-ABCD"  # default kicked in


# --- cube section -------------------------------------------------------------


def test_concept3d_cube_section_namespace():
    assert Concept3D.CUBE_SECTION == "3d/cube_section"


@pytest.mark.parametrize(
    "request_zh",
    [
        "正方体 ABCD-A₁B₁C₁D₁，过 D、A₁、C₁ 三点的截面",
        "正方体 ABCD-A1B1C1D1，过 D, A1, C1 的截面",
        "经过 D A1 C1 的截面",
        "正方体过 D、A₁、C₁ 截面",
    ],
)
def test_parse_section_points_extracts_three_points(request_zh):
    assert parse_section_points(request_zh) == ["D", "A1", "C1"]


def test_parse_section_points_extracts_four_points():
    assert parse_section_points("过 B、D、D₁、B₁ 四点的截面") == ["B", "D", "D1", "B1"]


def test_parse_section_points_returns_none_for_non_section_request():
    # Same vertex names but no 截面/平面 anchor — must not match.
    assert parse_section_points("画正方体 ABCD-A1B1C1D1，棱长 2") is None


def test_parse_section_points_returns_none_for_fewer_than_three():
    # Two points cannot determine a plane → caller should fall back.
    assert parse_section_points("过 D、A₁ 两点的截面") is None


def test_cube_section_code_emits_safe_call():
    code = cube_section_code(["D", "A1", "C1"])
    tree = ast.parse(code, mode="eval")
    assert isinstance(tree.body, ast.Call)
    assert code == 'cube_section(verts, ["D", "A1", "C1"])'


def test_cube_section_code_sanitizes_unsafe_names():
    # Names that don't match [A-Z]\d? must be dropped; fewer than 3 valid
    # names then triggers the canonical D/A1/C1 fallback.
    code = cube_section_code(['"); import os; #', "X", "A1"])
    ast.parse(code, mode="eval")
    assert "import" not in code
    assert code == 'cube_section(verts, ["D", "A1", "C1"])'


def test_section_points_latex_subscripts():
    assert section_points_latex(["D", "A1", "C1"]) == "D, A_{1}, C_{1}"


def test_section_points_latex_falls_back_on_bad_input():
    assert section_points_latex([]) == "D, A_{1}, C_{1}"


def test_helpers_src_includes_cube_section():
    tree = ast.parse(SOLID_HELPERS_SRC)
    names = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert "cube_section" in names


# --- three views (三视图) ----------------------------------------------------


def test_concept3d_three_views_namespace():
    assert Concept3D.THREE_VIEWS == "3d/three_views"


@pytest.mark.parametrize(
    "request_zh,expected",
    [
        ("画正方体的三视图", True),
        ("画长方体 ABCD-A1B1C1D1 长3宽2高4 的三视图", True),
        ("画一个圆柱底面半径1高2的三视图", True),
        # No 三视图 keyword → False.
        ("画正方体 ABCD-A1B1C1D1", False),
        ("画一个圆柱", False),
    ],
)
def test_is_three_views_request(request_zh, expected):
    assert is_three_views_request(request_zh) is expected


@pytest.mark.parametrize(
    "kind,params,expected_start",
    [
        ("cube",            {"side": 2.0},                                   'three_views("cube", '),
        ("box",             {"width": 3.0, "depth": 2.0, "height": 4.0},     'three_views("box", '),
        ("regular_prism",   {"n_sides": 4, "radius": 1.0, "height": 2.0},    'three_views("regular_prism", '),
        ("regular_pyramid", {"n_sides": 4, "radius": 1.0, "height": 2.0},    'three_views("regular_pyramid", '),
        ("tetrahedron",     {"side": 2.0},                                   'three_views("tetrahedron", '),
        ("cylinder",        {"radius": 1.0, "height": 2.0},                  'three_views("cylinder", '),
        ("cone",            {"radius": 1.0, "height": 2.0},                  'three_views("cone", '),
    ],
)
def test_three_views_code_is_safe_python_call(kind, params, expected_start):
    from straightedge.solids3d import _DEFAULT_NAMES  # noqa: PLC2701

    spec = SolidSpec(kind=kind, params=params, name=_DEFAULT_NAMES[kind])
    code = three_views_code(spec)
    tree = ast.parse(code, mode="eval")
    assert isinstance(tree.body, ast.Call)
    assert code.startswith(expected_start)


def test_three_views_code_clamps_unsafe_dimensions():
    # Out-of-range side gets clamped to default (same defense as construction code).
    spec = SolidSpec(kind="cube", params={"side": 99999}, name="ABCD-A1B1C1D1")
    code = three_views_code(spec)
    assert '"side": 2.0' in code


def test_helpers_src_includes_three_views():
    tree = ast.parse(SOLID_HELPERS_SRC)
    names = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert "three_views" in names
