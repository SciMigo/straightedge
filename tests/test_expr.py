from straightedge.expr import (
    parse_function,
    pretty_expr,
    to_latex_expr,
    to_numpy_expr,
    validate_expression,
)


def test_parses_quadratic_with_caret_and_implicit_multiplication():
    assert parse_function("画 y=x^2-4x+3，标出顶点") == "x ** 2 - 4 * x + 3"


def test_parses_function_notation_and_nested_calls():
    assert parse_function("请画 f(x)=2sin(3x)+1 的图像") == "2 * sin(3 * x) + 1"


def test_stops_at_cjk_characters():
    assert parse_function("已知 y=2x+1 与 x 轴的交点") == "2 * x + 1"


def test_no_formula_returns_none():
    assert parse_function("画一个正弦函数，标出周期和振幅") is None


def test_bare_expression_without_marker_is_not_parsed():
    # No y=/f(x)= marker -> left to keyword routing.
    assert parse_function("画 x^2-4x+3") is None


def test_rejects_attribute_and_call_injection():
    assert parse_function("y=__import__('os').system('echo hi')") is None
    assert parse_function("y=x.__class__") is None


def test_extraction_drops_everything_after_a_semicolon():
    # The injection after ';' is dropped at extraction; only "x" remains.
    assert parse_function("y=x; import os") == "x"


def test_to_numpy_maps_funcs_and_constants():
    assert to_numpy_expr("sin(x) + pi") == "np.sin(x) + np.pi"
    assert to_numpy_expr("e ** x") == "np.e ** x"


def test_to_latex_expr_formats_mathtex_formula():
    assert to_latex_expr("x ** 2 - 4 * x + 3") == "x^{2} - 4x + 3"
    assert to_latex_expr("2 * sin(3 * x) + 1") == r"2\sin\left(3x\right) + 1"


def test_pretty_expr_is_human_readable():
    assert pretty_expr("x ** 2 - 4 * x + 3") == "x^2 - 4x + 3"


def test_validate_expression_allowlist():
    assert validate_expression("x ** 2 + 1")
    assert not validate_expression("os.system('x')")
    assert not validate_expression("[i for i in range(3)]")
