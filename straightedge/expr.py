"""Parse and validate a single-variable math function from a Chinese request.

The teacher's typed formula is the first place request text flows into code that
Manim later executes, so everything here is built around a strict allowlist:
only numeric literals, the variable ``x``, a fixed set of constants, the basic
arithmetic operators, and a fixed set of math functions are accepted. Anything
else (attribute access, calls to unknown names, comprehensions, ...) is rejected
and the caller falls back to keyword routing.

:func:`evaluate` is the same allowlist pointed at a number instead of at emitted
source. It exists because the SVG templates in :mod:`straightedge.diagrams`
arrived from another repository calling ``eval`` on that expression with
``{"__builtins__": {}}`` as the globals — which is not a sandbox: the standard
subclass walk from any literal reaches ``__import__`` and from there the shell.
That was survivable while the caller was one application passing its own
strings, and stopped being survivable the moment ``render_diagram`` became a
published library's public API. Walking the tree is not much more code than
calling ``eval``, and it cannot be escaped by construction.
"""

from __future__ import annotations

import ast
import math
import re
from typing import Iterable

# Functions allowed in an expression -> their numpy equivalents (emitted into
# the generated scene, where ``from manim import *`` exposes ``np``).
_FUNC_TO_NUMPY = {
    "sin": "np.sin",
    "cos": "np.cos",
    "tan": "np.tan",
    "asin": "np.arcsin",
    "acos": "np.arccos",
    "atan": "np.arctan",
    "sinh": "np.sinh",
    "cosh": "np.cosh",
    "tanh": "np.tanh",
    "exp": "np.exp",
    "log": "np.log",
    "ln": "np.log",
    "sqrt": "np.sqrt",
    "abs": "np.abs",
}
_CONST_TO_NUMPY = {"pi": "np.pi", "e": "np.e", "tau": "np.tau"}
_FUNC_TO_LATEX = {
    "sin": r"\sin",
    "cos": r"\cos",
    "tan": r"\tan",
    "asin": r"\arcsin",
    "acos": r"\arccos",
    "atan": r"\arctan",
    "sinh": r"\sinh",
    "cosh": r"\cosh",
    "tanh": r"\tanh",
    "exp": r"\exp",
    "log": r"\log",
    "ln": r"\ln",
}
_ALLOWED_NAMES = {"x", *_CONST_TO_NUMPY}

#: The same functions as :data:`_FUNC_TO_NUMPY`, as stdlib callables. The video
#: lane emits ``np.*`` source for Manim to run; the figure lane has to produce a
#: float here and now, and must not import numpy — ``straightedge`` declares no
#: dependencies, which is the whole reason a caller can install it for figures
#: alone.
_FUNC_TO_PYTHON = {
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "asin": math.asin, "acos": math.acos, "atan": math.atan,
    "sinh": math.sinh, "cosh": math.cosh, "tanh": math.tanh,
    "exp": math.exp, "log": math.log, "ln": math.log,
    "sqrt": math.sqrt, "abs": abs,
}
_CONST_VALUES = {"pi": math.pi, "e": math.e, "tau": math.tau}

#: Largest exponent :func:`evaluate` will raise to. An allowlist alone does not
#: save you here: ``9**9**9**9`` is four literals and one permitted operator, so
#: it validates, and evaluating it right-associatively asks for nine to the
#: power of 387420489. The caller's ``except Exception`` cannot catch a hang.
_MAX_EXPONENT = 1024


class ExpressionError(ValueError):
    """An expression was rejected, or could not be reduced to a real number."""

_FULLWIDTH = str.maketrans(
    {
        "（": "(", "）": ")", "＝": "=", "＋": "+", "－": "-", "−": "-",
        "×": "*", "∗": "*", "·": "*", "÷": "/", "／": "/", "，": ",",
        "＾": "^", "。": ".", "　": " ",
    }
)
# Stop the captured right-hand side at punctuation or any CJK character, so a
# request like "y=2x+1 与 x 轴" keeps just "2x+1".
_RHS = re.compile(
    r"(?:y|f\s*\(\s*x\s*\)|g\s*\(\s*x\s*\))\s*=\s*([^,;:。；：\n一-鿿]+)",
    re.IGNORECASE,
)


def parse_function(request: str) -> str | None:
    """Return a validated canonical expression in ``x``, or None.

    Example: "画 y=x^2-4x+3，标出顶点" -> "x ** 2 - 4 * x + 3".
    """
    raw = extract_expression(request)
    if raw is None:
        return None
    normalized = normalize_expression(raw)
    if not normalized:
        return None
    try:
        tree = ast.parse(normalized, mode="eval")
    except SyntaxError:
        return None
    if not _is_safe(tree.body):
        return None
    return ast.unparse(tree.body)


def extract_expression(request: str) -> str | None:
    match = _RHS.search(request.translate(_FULLWIDTH))
    if not match:
        return None
    rhs = match.group(1).strip()
    return rhs or None


def normalize_expression(expr: str) -> str:
    expr = expr.translate(_FULLWIDTH)
    for sup, repl in (("²", "**2"), ("³", "**3"), ("⁴", "**4")):
        expr = expr.replace(sup, repl)
    expr = expr.replace("π", "pi").replace("^", "**")
    # Implicit multiplication for the common teacher shorthands. The optional
    # \s* covers both '2x' and '2 sin(...)' (teachers space-separate often).
    expr = re.sub(r"([0-9])\s*([A-Za-z(])", r"\1*\2", expr)  # 2x, 3 sin(, 2 (
    expr = re.sub(r"(\))\s*([0-9A-Za-z(])", r"\1*\2", expr)  # )(  )x  )2
    expr = re.sub(r"\bx\s*(?=\()", "x*", expr)               # x(x+1) -> x*(x+1)
    return expr.strip()


def validate_expression(expr: str, *, variables: Iterable[str] | None = None) -> bool:
    """Whether ``expr`` is inside the allowlist.

    ``variables`` names the free variables the caller will supply, defaulting to
    ``{"x"}``. It is a parameter because the figure lane does not always plot
    against x: a polar template's expression is written in ``t``/``theta``, and a
    validator that only ever accepts ``x`` rejects every legitimate polar curve.
    """
    allowed = set(_CONST_TO_NUMPY)
    allowed |= {"x"} if variables is None else set(variables)
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError:
        return False
    return _is_safe(tree.body, allowed)


def evaluate(expr: str, **variables: float) -> float:
    """Reduce ``expr`` to a float, without ``eval``.

    Raises :class:`ExpressionError` for anything outside the allowlist, and lets
    the ordinary numeric failures — division by zero, ``sqrt`` of a negative,
    overflow — surface as themselves. A caller that would rather draw nothing
    than draw a lie should catch and substitute NaN.
    """
    if not validate_expression(expr, variables=variables):
        raise ExpressionError(f"expression is not in the allowlist: {expr!r}")
    return _eval_node(ast.parse(expr, mode="eval").body, variables)


def _eval_node(node: ast.AST, variables: dict[str, float]) -> float:
    if isinstance(node, ast.Constant):
        return float(node.value)
    if isinstance(node, ast.Name):
        if node.id in variables:
            return float(variables[node.id])
        return _CONST_VALUES[node.id]
    if isinstance(node, ast.UnaryOp):
        value = _eval_node(node.operand, variables)
        return +value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp):
        left = _eval_node(node.left, variables)
        right = _eval_node(node.right, variables)
        if isinstance(node.op, ast.Pow):
            if abs(right) > _MAX_EXPONENT:
                raise ExpressionError(f"exponent {right} exceeds {_MAX_EXPONENT}")
            return float(left ** right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        return math.fmod(left, right)                   # ast.Mod
    # _is_safe has already rejected every other node type, and a Call's func is
    # a bare allowed name with exactly one argument.
    return _FUNC_TO_PYTHON[node.func.id](_eval_node(node.args[0], variables))


def to_numpy_expr(expr: str) -> str:
    """Rewrite allowed funcs/constants to their ``np.*`` form for emission."""
    tree = ast.parse(expr, mode="eval")
    return ast.unparse(_NumpyRewriter().visit(tree.body))


def pretty_expr(expr: str) -> str:
    """A human-friendly form for labels: x ** 2 - 4 * x + 3 -> x^2 - 4x + 3."""
    s = expr.replace("**", "^")
    s = re.sub(r"\s*\^\s*", "^", s)
    s = re.sub(r"\s*\*\s*", "*", s)
    s = re.sub(r"(?<=[0-9)])\*(?=[A-Za-z(])", "", s)
    return s


def to_latex_expr(expr: str) -> str:
    """Format a validated expression for Manim MathTex."""
    tree = ast.parse(expr, mode="eval")
    return _LatexFormatter().format(tree.body)


def _is_safe(node: ast.AST, allowed: set[str] = _ALLOWED_NAMES) -> bool:
    if isinstance(node, ast.Constant):
        return isinstance(node.value, (int, float)) and not isinstance(node.value, bool)
    if isinstance(node, ast.Name):
        return node.id in allowed
    if isinstance(node, ast.BinOp):
        ok_op = isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod))
        return ok_op and _is_safe(node.left, allowed) and _is_safe(node.right, allowed)
    if isinstance(node, ast.UnaryOp):
        return isinstance(node.op, (ast.UAdd, ast.USub)) and _is_safe(node.operand, allowed)
    if isinstance(node, ast.Call):
        return (
            isinstance(node.func, ast.Name)
            and node.func.id in _FUNC_TO_NUMPY
            and not node.keywords
            and len(node.args) == 1
            and _is_safe(node.args[0], allowed)
        )
    return False


class _NumpyRewriter(ast.NodeTransformer):
    def visit_Call(self, node: ast.Call) -> ast.AST:
        self.generic_visit(node)
        if isinstance(node.func, ast.Name) and node.func.id in _FUNC_TO_NUMPY:
            node.func = ast.parse(_FUNC_TO_NUMPY[node.func.id], mode="eval").body
        return node

    def visit_Name(self, node: ast.Name) -> ast.AST:
        if node.id in _CONST_TO_NUMPY:
            return ast.parse(_CONST_TO_NUMPY[node.id], mode="eval").body
        return node


class _LatexFormatter:
    _PREC_SUM = 10
    _PREC_PRODUCT = 20
    _PREC_POWER = 30
    _PREC_UNARY = 40
    _PREC_ATOM = 50

    def format(self, node: ast.AST, parent_prec: int = 0) -> str:
        text, prec = self._format(node)
        if prec < parent_prec:
            return rf"\left({text}\right)"
        return text

    def _format(self, node: ast.AST) -> tuple[str, int]:
        if isinstance(node, ast.Constant):
            return self._format_number(node.value), self._PREC_ATOM
        if isinstance(node, ast.Name):
            return self._format_name(node.id), self._PREC_ATOM
        if isinstance(node, ast.UnaryOp):
            operand = self.format(node.operand, self._PREC_UNARY)
            if isinstance(node.op, ast.USub):
                return f"-{operand}", self._PREC_UNARY
            return operand, self._PREC_UNARY
        if isinstance(node, ast.BinOp):
            return self._format_binop(node)
        if isinstance(node, ast.Call):
            return self._format_call(node), self._PREC_ATOM
        raise ValueError(f"Unsupported expression node: {type(node).__name__}")

    def _format_binop(self, node: ast.BinOp) -> tuple[str, int]:
        if isinstance(node.op, ast.Add):
            return (
                f"{self.format(node.left, self._PREC_SUM)} + "
                f"{self.format(node.right, self._PREC_SUM)}",
                self._PREC_SUM,
            )
        if isinstance(node.op, ast.Sub):
            return (
                f"{self.format(node.left, self._PREC_SUM)} - "
                f"{self.format(node.right, self._PREC_PRODUCT)}",
                self._PREC_SUM,
            )
        if isinstance(node.op, ast.Mult):
            left = self.format(node.left, self._PREC_PRODUCT)
            right = self.format(node.right, self._PREC_PRODUCT)
            return f"{left}{right}", self._PREC_PRODUCT
        if isinstance(node.op, ast.Div):
            left = self.format(node.left)
            right = self.format(node.right)
            return rf"\frac{{{left}}}{{{right}}}", self._PREC_PRODUCT
        if isinstance(node.op, ast.Pow):
            left = self.format(node.left, self._PREC_POWER)
            right = self.format(node.right)
            return rf"{left}^{{{right}}}", self._PREC_POWER
        if isinstance(node.op, ast.Mod):
            left = self.format(node.left, self._PREC_PRODUCT)
            right = self.format(node.right, self._PREC_PRODUCT)
            return rf"{left}\bmod {right}", self._PREC_PRODUCT
        raise ValueError(f"Unsupported operator: {type(node.op).__name__}")

    def _format_call(self, node: ast.Call) -> str:
        assert isinstance(node.func, ast.Name)
        name = node.func.id
        arg = self.format(node.args[0])
        if name == "sqrt":
            return rf"\sqrt{{{arg}}}"
        if name == "abs":
            return rf"\left|{arg}\right|"
        latex_name = _FUNC_TO_LATEX[name]
        return rf"{latex_name}\left({arg}\right)"

    def _format_name(self, name: str) -> str:
        if name == "pi":
            return r"\pi"
        if name == "tau":
            return r"\tau"
        return name

    def _format_number(self, value: object) -> str:
        if isinstance(value, int):
            return str(value)
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value)
