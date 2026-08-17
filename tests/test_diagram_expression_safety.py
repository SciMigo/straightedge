"""The expression front door, exercised against what it was opened for.

``straightedge.diagrams`` arrived from an application that called ``eval`` on
caller-supplied expressions with ``{"__builtins__": {}}`` as the globals. That
was survivable while the caller was one program passing its own strings, and
stopped being survivable the moment ``render_diagram`` became a published
library's public API. Every case here is a payload that worked through that API
before the allowlist replaced the ``eval``.
"""

from __future__ import annotations

import math
import time

import pytest

from straightedge.diagrams import render_diagram
from straightedge.diagrams.registry import is_blank_diagram
from straightedge.expr import ExpressionError, evaluate, validate_expression

#: The standard escape from ``{"__builtins__": {}}``: walk from any literal to
#: ``object``'s subclasses, find one holding a module reference, and read the
#: real builtins back out of it. Nothing about emptying the globals prevents it.
ESCAPE = (
    "[c for c in (1).__class__.__mro__[1].__subclasses__() "
    "if c.__name__=='catch_warnings'][0]()._module."
    "__builtins__['__import__']('os').system('touch {path}')"
)


class TestNoArbitraryExecution:

    def test_the_subclass_walk_never_reaches_a_shell(self, tmp_path):
        marker = tmp_path / "executed"
        payload = ESCAPE.format(path=marker)
        for kind in ("riemann_sum", "polar_graph", "function_graph"):
            render_diagram({"type": kind, "params": {"function": payload}})
        assert not marker.exists(), "caller-supplied expression executed code"

    def test_the_allowlist_rejects_it_directly(self):
        with pytest.raises(ExpressionError):
            evaluate(ESCAPE.format(path="/tmp/x"), x=1.0)

    @pytest.mark.parametrize("expr", [
        "__import__('os')",
        "(1).__class__",
        "open('/etc/passwd')",
        "[c for c in ().__class__.__mro__]",
        "lambda: 1",
        "x if x else 1",
    ])
    def test_everything_outside_arithmetic_is_rejected(self, expr):
        assert not validate_expression(expr)


class TestNoHang:
    """``render_diagram`` promises a missing figure costs a slide its picture
    and not the deck. An ``except Exception`` cannot keep that promise against
    an expression that never returns."""

    def test_a_power_tower_returns_instead_of_running_forever(self):
        started = time.monotonic()
        svg = render_diagram(
            {"type": "riemann_sum", "params": {"function": "9^9^9^9", "a": 0, "b": 2}}
        )
        assert time.monotonic() - started < 5.0
        assert is_blank_diagram(svg)

    def test_the_allowlist_alone_would_not_have_caught_it(self):
        """Worth pinning: ``**`` is a permitted operator, so validation passes
        and only the exponent bound stops the evaluation."""
        assert validate_expression("9**9**9**9")
        with pytest.raises(ExpressionError):
            evaluate("9**9**9**9", x=1.0)


class TestBrokenExpressionsDrawNothing:
    """A zero is a drawable height. Before this, a mistyped expression rendered
    five rectangles that ``is_blank_diagram`` reported as a healthy figure."""

    @pytest.mark.parametrize("kind,expr", [
        ("riemann_sum", "x^2 +"),
        ("polar_graph", "sin(3*theta) +"),
        ("function_graph", "x^2 +"),
    ])
    def test_a_syntax_error_yields_no_figure(self, kind, expr):
        svg = render_diagram({"type": kind, "params": {"function": expr}})
        assert is_blank_diagram(svg), "a broken expression rendered a figure"

    def test_valid_expressions_still_draw(self):
        for kind, expr in [("riemann_sum", "x^2"), ("polar_graph", "sin(3*theta)"),
                           ("function_graph", "sin(x)")]:
            svg = render_diagram({"type": kind, "params": {"function": expr}})
            assert not is_blank_diagram(svg), f"{kind} stopped drawing {expr}"

    def test_a_non_finite_mark_does_not_count_as_data(self):
        """The guard that protects the other 32 templates, none of which were
        audited: NaN geometry is still a ``<rect>`` to anything counting tags."""
        chrome = '<svg><rect x="1" y="1" width="10" height="nan"/></svg>'
        assert is_blank_diagram(chrome)


class TestEvaluatorAgrees:
    """Replacing ``eval`` must not change any answer."""

    @pytest.mark.parametrize("expr,kwargs,want", [
        ("x**2 - 4*x + 3", {"x": 2.0}, -1.0),
        ("sqrt(x)", {"x": 9.0}, 3.0),
        ("-x + pi", {"x": 1.0}, math.pi - 1),
        ("2*sin(3*t)", {"t": 0.5}, 2 * math.sin(1.5)),
        ("exp(x)/e", {"x": 1.0}, 1.0),
        ("abs(0 - x)", {"x": 3.0}, 3.0),
    ])
    def test_numeric_agreement(self, expr, kwargs, want):
        assert evaluate(expr, **kwargs) == pytest.approx(want)

    def test_the_polar_variable_is_accepted(self):
        """``_ALLOWED_NAMES`` is x-only, which would reject every polar curve."""
        assert validate_expression("2*sin(3*t)", variables={"t"})
        assert not validate_expression("2*sin(3*t)")


class TestNoInjection:
    """These figures are embedded in HTML slides, so an unescaped label is an
    injection point — and the same bug spoils ordinary input first: a title
    reading ``0 < x`` produced SVG no parser would accept."""

    @pytest.mark.parametrize("param", [
        "title", "x_label", "y_label", "left_label", "right_label",
        "transition_label", "left_color", "right_color",
    ])
    def test_markup_in_any_label_is_escaped(self, param):
        svg = render_diagram(
            {"type": "step_function", "params": {param: "<script>alert(1)</script>"}}
        )
        assert "<script>" not in svg

    def test_a_less_than_sign_still_parses(self):
        import xml.dom.minidom as minidom
        svg = render_diagram({"type": "step_function", "params": {"title": "0 < x"}})
        minidom.parseString(svg)          # raises if the escaping is wrong
