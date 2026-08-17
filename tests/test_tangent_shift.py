"""The tangent-shift scene: a curve lifted until it just touches a line.

The scene's claim is that lifting ``curve`` by ``shift`` turns two crossings
into one. That is arithmetic on the generated source's own crossing finder, so
the tests run it rather than grepping for the shapes the scene says it draws.
"""

from __future__ import annotations

import ast
import re

import pytest

from straightedge.calculus import ConceptCalculus
from straightedge.models import AnimationPlan, Topic
from straightedge.templates import scene_code_for


def _plan(**parameters):
    return AnimationPlan(
        topic=Topic.CALCULUS, title_zh="Lift the curve", objective_zh="objective",
        english_prompt="tangent shift", concept=ConceptCalculus.TANGENT_SHIFT,
        parameters=parameters,
    )


def _covered_beats(code):
    """Every beat the scene spends, however it spends it.

    Beats carrying a card are hand-sequenced through ``reveal_over`` rather
    than ``_beat``, so looking only for ``_beat`` calls would report them
    uncovered — and a beat nothing is spent on is a frozen frame, exactly the
    defect this is meant to catch.
    """
    keys = set()
    for node in ast.walk(ast.parse(code)):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
            continue
        name, args = node.func.id, node.args
        at = {"_beat": 1, "_beat_stretch": 1, "reveal_over": 0}.get(name)
        if at is not None and len(args) > at and isinstance(args[at], ast.Constant):
            keys.add(args[at].value)
    return keys


def _steps(code, name="PROBLEM_STEPS"):
    """A card's contents, read back as the literal the scene will see."""
    for node in ast.walk(ast.parse(code)):
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == name):
            return ast.literal_eval(node.value)
    raise AssertionError(f"{name} is not assigned in the generated scene")


def _crossings(code, a, line, curve):
    """Run the generated source's own crossing finder at shift ``a``."""
    ns = {}
    tol = re.search(r"^\s*TOUCH_TOL = (\S+)$", code, re.M)
    assert tol, "TOUCH_TOL is not defined in the generated scene"
    exec(  # the point of the test is that this exact code runs
        "import numpy as np\n"
        f"TOUCH_TOL = {tol.group(1)}\n"
        f"def line_f(x):\n    return {line}\n"
        f"def curve_f(x):\n    return {curve}\n"
        + _extract(code, "safe") + _extract(code, "crossings"),
        ns,
    )
    return ns["crossings"](a)


def _extract(code, name):
    """Pull one nested def out of the generated scene, at module indent."""
    lines = code.splitlines()
    start = next(i for i, l in enumerate(lines) if l.strip().startswith(f"def {name}("))
    indent = len(lines[start]) - len(lines[start].lstrip())
    body = [lines[start]]
    for line in lines[start + 1:]:
        if line.strip() and (len(line) - len(line.lstrip())) <= indent:
            break
        body.append(line)
    return "\n".join(l[indent:] for l in body) + "\n"


ALL_BEATS = {"b01", "b02", "b03", "b04", "b05", "b06", "b07"}


@pytest.mark.parametrize("params", [
    {},
    {"problem": ["f(x)=x"]},
    {"working": ["a=1"]},
    {"problem": ["f(x)=x"], "working": ["a=1"]},
])
def test_source_parses_and_covers_every_beat(params):
    code = scene_code_for(_plan(**params))
    ast.parse(code)
    assert _covered_beats(code) == ALL_BEATS


def test_lifting_collapses_two_crossings_to_one():
    """The whole scene in one assertion: e^x meets x+2 twice, e^x+1 once."""
    code = scene_code_for(_plan(line="x + 2", curve="e ** x", shift=1.0))
    assert len(_crossings(code, 0.0, "x + 2", "np.exp(x)")) == 2
    touch = _crossings(code, 1.0, "x + 2", "np.exp(x)")
    assert len(touch) == 1
    assert touch[0] == pytest.approx(0.0, abs=1e-3)


def test_a_near_miss_is_not_reported_as_a_touch():
    """Lifted past tangency there is no contact, and the scene must say so.

    Without this the tolerance that finds the tangency would also invent one
    for any shift close to it, and the touch point would be placed off the
    line — the failure the sign-change-only finder hid behind a default.
    """
    code = scene_code_for(_plan(line="x + 2", curve="e ** x", shift=1.0))
    assert _crossings(code, 1.05, "x + 2", "np.exp(x)") == []
    assert len(_crossings(code, 0.95, "x + 2", "np.exp(x)")) == 2


def test_cards_survive_latex_backslashes():
    """LaTeX goes through a repr, so it must round-trip, not merely appear."""
    problem = [r"f(x)=\frac{x+2}{e^{x}+a}", r"a=(x+1)e^{x}"]
    working = [r"e^{x}=1\ \Rightarrow\ x=0"]
    code = scene_code_for(_plan(problem=problem, working=working))
    ast.parse(code)
    assert _steps(code) == problem
    assert _steps(code, "WORKING_STEPS") == working


@pytest.mark.parametrize("key,name,limit", [
    ("problem", "PROBLEM_STEPS", 4),
    ("working", "WORKING_STEPS", 5),
])
def test_cards_are_optional_and_bounded(key, name, limit):
    assert _steps(scene_code_for(_plan()), name) == []
    # A bare string is a single line, blanks are dropped, and the card is
    # capped so a runaway list cannot overrun the frame.
    assert _steps(scene_code_for(_plan(**{key: "one"})), name) == ["one"]
    many = [str(i) for i in range(limit + 3)]
    code = scene_code_for(_plan(**{key: many[:1] + ["  "] + many[1:]}))
    assert _steps(code, name) == many[:limit]


def test_bad_parameters_fall_back_instead_of_failing():
    code = scene_code_for(_plan(line="__import__('os')", curve="", shift=-3))
    ast.parse(code)
    assert "SHIFT = 1.0" in code
    assert "__import__" not in code
