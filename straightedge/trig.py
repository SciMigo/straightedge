"""Recognize and describe trigonometric graph transformations.

A teacher request like ``画 y = 2 sin(3x + π/4) + 1`` first becomes a
canonical expression via :mod:`expr`. :func:`parse_trig_spec` then tries to
match that expression against the textbook form ``y = A · f(ω x + φ) + k``
(for ``f ∈ {sin, cos, tan}``). On success the planner routes to the
``Concept.GRAPH_TRANSFORM`` scene, which can label 振幅 / 周期 / 中线 in
addition to plotting the curve.

The expression is already validated by :mod:`expr` before reaching here, so
this module focuses on shape-matching rather than safety.
"""

from __future__ import annotations

import ast
import math
from dataclasses import dataclass
from fractions import Fraction


class Concept:
    """Sub-topic identifiers under ``Topic.TRIG``.

    Mirrors :class:`solids3d.Concept3D` — adding a trig concept means adding
    an entry here, a parser branch, a planner builder, and a scene builder in
    :data:`templates._TRIG_CONCEPT_BUILDERS`.
    """

    GRAPH_TRANSFORM = "trig/graph_transform"
    UNIT_CIRCLE_TO_SINE = "trig/unit_circle_to_sine"


_SUPPORTED_FUNCS = ("sin", "cos", "tan")

_FUNC_ZH = {"sin": "正弦", "cos": "余弦", "tan": "正切"}
_FUNC_LATEX = {"sin": r"\sin", "cos": r"\cos", "tan": r"\tan"}


@dataclass(frozen=True)
class TrigSpec:
    """A parsed trig transformation ``y = A · f(ω x + φ) + k``.

    All four coefficients are stored as floats. The ``func`` field is one of
    ``"sin"``, ``"cos"``, ``"tan"``. Display strings are computed on demand
    by the formatter helpers in this module.
    """

    func: str
    A: float
    omega: float
    phi: float
    k: float


# --- parser -------------------------------------------------------------------


def parse_trig_spec(expression: str | None) -> TrigSpec | None:
    """Match ``A · f(ω x + φ) + k`` (each coefficient optional). Else None.

    The input is the canonical Python form produced by ``expr.parse_function``
    (e.g. ``"2 * sin(3 * x + pi / 4) + 1"``).
    """
    if not expression:
        return None
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError:
        return None
    body, k_val = _peel_offset(tree.body)
    if body is None:
        return None
    body, A_val = _peel_amplitude(body)
    if body is None:
        return None
    if not (
        isinstance(body, ast.Call)
        and isinstance(body.func, ast.Name)
        and body.func.id in _SUPPORTED_FUNCS
        and len(body.args) == 1
        and not body.keywords
    ):
        return None
    arg = body.args[0]
    linear = _linear_in_x(arg)
    if linear is None:
        return None
    omega, phi = linear
    return TrigSpec(func=body.func.id, A=A_val, omega=omega, phi=phi, k=k_val)


def _peel_offset(node: ast.AST) -> tuple[ast.AST | None, float]:
    """Pull off a ``± constant`` at the top. Returns (inner, k_value)."""
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub)):
        left_has_x = _contains_x(node.left)
        right_has_x = _contains_x(node.right)
        if left_has_x and not right_has_x:
            k = _safe_eval(node.right)
            return node.left, (-k if isinstance(node.op, ast.Sub) else k)
        if right_has_x and not left_has_x and isinstance(node.op, ast.Add):
            # k + A f(...)
            return node.right, _safe_eval(node.left)
    if _contains_x(node):
        return node, 0.0
    return None, 0.0


def _peel_amplitude(node: ast.AST) -> tuple[ast.AST | None, float]:
    """Pull off a leading ``±A *`` factor. Returns (inner_call, A_value)."""
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        inner, A = _peel_amplitude(node.operand)
        return inner, -A
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.UAdd):
        return _peel_amplitude(node.operand)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
        left_has_x = _contains_x(node.left)
        right_has_x = _contains_x(node.right)
        if right_has_x and not left_has_x:
            return node.right, _safe_eval(node.left)
        if left_has_x and not right_has_x:
            return node.left, _safe_eval(node.right)
        return None, 0.0
    if isinstance(node, ast.Call):
        return node, 1.0
    return None, 0.0


def _linear_in_x(node: ast.AST) -> tuple[float, float] | None:
    """If ``node`` is a degree-1 polynomial in x, return (omega, phi)."""
    try:
        y0 = _safe_eval(node, x_value=0.0)
        y1 = _safe_eval(node, x_value=1.0)
        y2 = _safe_eval(node, x_value=2.0)
    except (ValueError, ZeroDivisionError):
        return None
    phi = y0
    omega = y1 - y0
    if abs((y2 - phi) - 2 * omega) > 1e-9:
        return None
    if abs(omega) < 1e-12:
        return None  # constant inside — degenerate, treat as not-a-transform
    return omega, phi


def _contains_x(node: ast.AST) -> bool:
    if isinstance(node, ast.Name):
        return node.id == "x"
    if isinstance(node, ast.Constant):
        return False
    return any(_contains_x(child) for child in ast.iter_child_nodes(node))


_SAFE_NAMES = {"pi": math.pi, "e": math.e, "tau": math.tau}
_SAFE_FUNCS = {
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "asin": math.asin, "acos": math.acos, "atan": math.atan,
    "sinh": math.sinh, "cosh": math.cosh, "tanh": math.tanh,
    "exp": math.exp, "log": math.log, "sqrt": math.sqrt, "abs": abs,
}


def _safe_eval(node: ast.AST, x_value: float = 0.0) -> float:
    """Evaluate a validated AST subtree against ``x = x_value``.

    Only the operator/function set already accepted by ``expr._is_safe`` is
    handled — anything else raises ``ValueError``.
    """
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise ValueError(f"unsupported constant: {node.value!r}")
        return float(node.value)
    if isinstance(node, ast.Name):
        if node.id == "x":
            return x_value
        if node.id in _SAFE_NAMES:
            return _SAFE_NAMES[node.id]
        raise ValueError(f"unknown name: {node.id}")
    if isinstance(node, ast.UnaryOp):
        v = _safe_eval(node.operand, x_value)
        if isinstance(node.op, ast.UAdd):
            return v
        if isinstance(node.op, ast.USub):
            return -v
        raise ValueError(f"unsupported unary op: {type(node.op).__name__}")
    if isinstance(node, ast.BinOp):
        l = _safe_eval(node.left, x_value)
        r = _safe_eval(node.right, x_value)
        if isinstance(node.op, ast.Add):
            return l + r
        if isinstance(node.op, ast.Sub):
            return l - r
        if isinstance(node.op, ast.Mult):
            return l * r
        if isinstance(node.op, ast.Div):
            return l / r
        if isinstance(node.op, ast.Pow):
            return l ** r
        if isinstance(node.op, ast.Mod):
            return l % r
        raise ValueError(f"unsupported binary op: {type(node.op).__name__}")
    if isinstance(node, ast.Call):
        if not (isinstance(node.func, ast.Name) and node.func.id in _SAFE_FUNCS):
            raise ValueError("unknown call")
        return float(_SAFE_FUNCS[node.func.id](_safe_eval(node.args[0], x_value)))
    raise ValueError(f"unsupported node: {type(node).__name__}")


# --- formatters ---------------------------------------------------------------


def trig_func_zh(spec: TrigSpec) -> str:
    """Chinese name of the trig function, e.g. 正弦."""
    return _FUNC_ZH[spec.func]


def trig_title_latex(spec: TrigSpec) -> str:
    r"""LaTeX source for the headline formula, e.g. ``y = 2\sin(3x + ...) + 1``."""
    func = _FUNC_LATEX[spec.func]
    inside = _format_inner(spec.omega, spec.phi)
    amp = _format_amplitude(spec.A)
    offset = _format_offset(spec.k)
    return rf"y = {amp}{func}\left({inside}\right){offset}"


def period_latex(spec: TrigSpec) -> str:
    r"""``T = ...π`` in lowest terms, e.g. ``T = \pi`` for ``sin(2x)``."""
    return rf"T = {_format_positive_pi(period_value(spec))}"


def period_value(spec: TrigSpec) -> float:
    """Numeric period for axis ranges and tick spacing."""
    numerator_pi = math.pi if spec.func == "tan" else 2 * math.pi
    return numerator_pi / abs(spec.omega)


def amplitude_latex(spec: TrigSpec) -> str:
    """``A = ...`` label. Tan has no finite amplitude — caller should skip."""
    return rf"A = {_format_positive_float(abs(spec.A))}"


def midline_latex(spec: TrigSpec) -> str:
    """``y = k`` label for the horizontal midline (dashed in the scene)."""
    return rf"y = {_format_signed_pi(spec.k)}"


def pi_axis_ticks(
    period: float,
    x_min: float,
    x_max: float,
    n_per_period: int = 2,
) -> list[tuple[float, str]]:
    """Return ``[(x_value, latex_label), ...]`` for a π-aware x-axis.

    Ticks land at multiples of ``period / n_per_period``. Labels render as
    π-fractions when the period is a rational multiple of π (which is true
    for any textbook trig request); otherwise the labels fall back to plain
    decimals so the function stays defined.
    """
    if period <= 0 or x_max <= x_min:
        return []
    period_over_pi = Fraction(period / math.pi).limit_denominator(24)
    is_pi_clean = abs(float(period_over_pi) - period / math.pi) < 1e-9
    if is_pi_clean and period_over_pi != 0:
        step_over_pi = period_over_pi / n_per_period
        step = float(step_over_pi) * math.pi
        k_min = int(math.ceil(x_min / step - 1e-9))
        k_max = int(math.floor(x_max / step + 1e-9))
        out: list[tuple[float, str]] = []
        for k in range(k_min, k_max + 1):
            x_pi_frac = k * step_over_pi
            x_val = float(x_pi_frac) * math.pi
            if x_pi_frac == 0:
                out.append((0.0, "0"))
            else:
                out.append((x_val, _format_signed_pi(x_val)))
        return out
    step = period / n_per_period
    k_min = int(math.ceil(x_min / step - 1e-9))
    k_max = int(math.floor(x_max / step + 1e-9))
    return [(k * step, _format_signed_pi(k * step)) for k in range(k_min, k_max + 1)]


def _format_inner(omega: float, phi: float) -> str:
    """``ωx + φ`` inside the trig call, with nice ω=1 / φ=0 handling."""
    omega_src = _format_omega_coefficient(omega)
    if abs(phi) < 1e-12:
        return f"{omega_src}x"
    sign = "+" if phi > 0 else "-"
    return f"{omega_src}x {sign} {_format_positive_pi(abs(phi))}"


def _format_amplitude(A: float) -> str:
    """Leading amplitude factor as it appears in the title formula."""
    if abs(A - 1) < 1e-12:
        return ""
    if abs(A + 1) < 1e-12:
        return "-"
    return _format_signed_pi(A)


def _format_offset(k: float) -> str:
    """Trailing ``+ k`` (or ``- |k|``) for the title formula, blank when k=0."""
    if abs(k) < 1e-12:
        return ""
    sign = "+" if k > 0 else "-"
    return f" {sign} {_format_positive_pi(abs(k))}"


def _format_omega_coefficient(omega: float) -> str:
    """``ω·`` as it appears before ``x``: '' for 1, '-' for -1, else the value."""
    if abs(omega - 1) < 1e-12:
        return ""
    if abs(omega + 1) < 1e-12:
        return "-"
    return _format_signed_pi(omega)


def _format_signed_pi(value: float) -> str:
    if value < 0:
        return f"-{_format_positive_pi(-value)}"
    return _format_positive_pi(value)


def _format_positive_pi(value: float) -> str:
    """Format a positive float as a π-aware LaTeX literal.

    Recognizes integers, ``n*π``, ``π/n``, ``n*π/m`` for small integers.
    Falls back to ``_format_positive_float`` (which handles plain rationals).
    """
    if value < 1e-12:
        return "0"
    frac = Fraction(value / math.pi).limit_denominator(24)
    if abs(float(frac) - value / math.pi) < 1e-9 and frac.numerator != 0:
        num, den = frac.numerator, frac.denominator
        top = r"\pi" if num == 1 else rf"{num}\pi"
        return top if den == 1 else rf"\frac{{{top}}}{{{den}}}"
    return _format_positive_float(value)


def _format_positive_float(value: float) -> str:
    """Plain rational/integer formatter, no π recognition."""
    if value < 1e-12:
        return "0"
    frac = Fraction(value).limit_denominator(100)
    if abs(float(frac) - value) < 1e-9:
        if frac.denominator == 1:
            return str(frac.numerator)
        return rf"\frac{{{frac.numerator}}}{{{frac.denominator}}}"
    return f"{value:g}"
