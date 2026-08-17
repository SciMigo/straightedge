import math

import pytest

from straightedge.trig import (
    Concept,
    TrigSpec,
    amplitude_latex,
    midline_latex,
    parse_trig_spec,
    period_latex,
    period_value,
    trig_func_zh,
    trig_title_latex,
)


def test_concept_namespace():
    assert Concept.GRAPH_TRANSFORM == "trig/graph_transform"


def test_parses_base_sine():
    assert parse_trig_spec("sin(x)") == TrigSpec("sin", 1.0, 1.0, 0.0, 0.0)


def test_parses_full_transformation():
    spec = parse_trig_spec("2 * sin(3 * x + pi / 4) + 1")
    assert spec is not None
    assert spec.func == "sin"
    assert spec.A == 2.0
    assert spec.omega == 3.0
    assert spec.phi == pytest.approx(math.pi / 4)
    assert spec.k == 1.0


@pytest.mark.parametrize(
    "expr,expected",
    [
        ("cos(x)", TrigSpec("cos", 1.0, 1.0, 0.0, 0.0)),
        ("tan(x)", TrigSpec("tan", 1.0, 1.0, 0.0, 0.0)),
        ("-sin(x)", TrigSpec("sin", -1.0, 1.0, 0.0, 0.0)),
        ("sin(-x)", TrigSpec("sin", 1.0, -1.0, 0.0, 0.0)),
        ("sin(x) + 3", TrigSpec("sin", 1.0, 1.0, 0.0, 3.0)),
        ("sin(x) - 2", TrigSpec("sin", 1.0, 1.0, 0.0, -2.0)),
    ],
)
def test_parses_minor_transformations(expr, expected):
    assert parse_trig_spec(expr) == expected


@pytest.mark.parametrize(
    "expr",
    [
        "x ** 2 + 1",       # not trig
        "sin(x) + cos(x)",  # not a single trig term
        "sin(x ** 2)",      # inner not linear in x
        "sin(x) * cos(x)",  # product, not amplitude scale
        "sin(x * x)",       # quadratic inner
        "log(sin(x))",      # outer not trig
    ],
)
def test_rejects_non_transformations(expr):
    assert parse_trig_spec(expr) is None


def test_rejects_empty_or_invalid_input():
    assert parse_trig_spec(None) is None
    assert parse_trig_spec("") is None
    assert parse_trig_spec("not python (((") is None


def test_period_value_sin_cos_and_tan():
    assert period_value(TrigSpec("sin", 1.0, 1.0, 0.0, 0.0)) == pytest.approx(2 * math.pi)
    assert period_value(TrigSpec("sin", 1.0, 2.0, 0.0, 0.0)) == pytest.approx(math.pi)
    assert period_value(TrigSpec("tan", 1.0, 1.0, 0.0, 0.0)) == pytest.approx(math.pi)
    assert period_value(TrigSpec("tan", 1.0, 0.5, 0.0, 0.0)) == pytest.approx(2 * math.pi)


def test_period_latex_renders_pi_multiples_in_lowest_terms():
    assert period_latex(TrigSpec("sin", 1.0, 1.0, 0.0, 0.0)) == r"T = 2\pi"
    # 2π/2 must simplify to π, not stay as a fraction.
    assert period_latex(TrigSpec("sin", 1.0, 2.0, 0.0, 0.0)) == r"T = \pi"
    assert period_latex(TrigSpec("sin", 1.0, 3.0, 0.0, 0.0)) == r"T = \frac{2\pi}{3}"
    # tan(x/2) has period 2π, not π/(1/2).
    assert period_latex(TrigSpec("tan", 1.0, 0.5, 0.0, 0.0)) == r"T = 2\pi"


def test_amplitude_and_midline_latex():
    spec = TrigSpec("sin", 2.0, 1.0, 0.0, 1.0)
    assert amplitude_latex(spec) == "A = 2"
    assert midline_latex(spec) == "y = 1"
    assert amplitude_latex(TrigSpec("sin", -3.0, 1.0, 0.0, 0.0)) == "A = 3"
    assert midline_latex(TrigSpec("sin", 1.0, 1.0, 0.0, -2.5)) == r"y = -\frac{5}{2}"


def test_trig_func_zh():
    assert trig_func_zh(TrigSpec("sin", 1.0, 1.0, 0.0, 0.0)) == "正弦"
    assert trig_func_zh(TrigSpec("cos", 1.0, 1.0, 0.0, 0.0)) == "余弦"
    assert trig_func_zh(TrigSpec("tan", 1.0, 1.0, 0.0, 0.0)) == "正切"


def test_title_latex_omits_unit_coefficients_and_zero_offset():
    # y = sin(x) -- no leading '1', no trailing '+ 0'.
    assert trig_title_latex(TrigSpec("sin", 1.0, 1.0, 0.0, 0.0)) == r"y = \sin\left(x\right)"
    # Leading '-' for A = -1 instead of '-1'.
    assert trig_title_latex(TrigSpec("sin", -1.0, 1.0, 0.0, 0.0)) == r"y = -\sin\left(x\right)"


def test_title_latex_renders_full_form_with_pi_phase():
    spec = TrigSpec("sin", 2.0, 3.0, math.pi / 4, 1.0)
    assert trig_title_latex(spec) == r"y = 2\sin\left(3x + \frac{\pi}{4}\right) + 1"


def test_title_latex_renders_negative_phase_and_offset():
    spec = TrigSpec("cos", 1.0, 2.0, -math.pi / 3, -1.0)
    assert trig_title_latex(spec) == r"y = \cos\left(2x - \frac{\pi}{3}\right) - 1"
