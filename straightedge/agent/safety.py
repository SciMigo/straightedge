from __future__ import annotations

import ast
from dataclasses import dataclass

from straightedge.templates import SCENE_CLASS_NAME


@dataclass(frozen=True)
class SafetyResult:
    ok: bool
    errors: list[str]


_BANNED_NAMES = {
    "open", "exec", "eval", "compile", "__import__", "input",
    "breakpoint", "globals", "locals", "vars",
    # getattr/setattr/delattr reach any attribute by a *string*, so without them
    # the dunder-attribute rule below is bypassed by constructing the name —
    # ``getattr(x, "__" + "class__")`` never parses as a dunder attribute. They
    # are the hole that made this an allowlist with a door in it.
    "getattr", "setattr", "delattr",
}
# Keep this exact rather than matching the first dotted segment. ``manim`` and
# ``numpy`` both have submodules that launch processes or access files; the
# generated scene only needs Manim's public namespace, scalar math, and the
# numerical routines in ``numpy.linalg``. ``from manim import *`` also exposes
# NumPy as ``np`` for ordinary array and trigonometry work.
_ALLOWED_IMPORTS = {"manim", "math", "numpy.linalg"}


def check_scene_code(code: str) -> SafetyResult:
    errors: list[str] = []
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return SafetyResult(False, [f"SyntaxError: {exc}"])

    class_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
    if class_names.count(SCENE_CLASS_NAME) != 1:
        errors.append(f"Code must define exactly one {SCENE_CLASS_NAME} class.")

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name not in _ALLOWED_IMPORTS:
                    errors.append(f"Disallowed import: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod not in _ALLOWED_IMPORTS:
                errors.append(f"Disallowed import-from: {mod}")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in _BANNED_NAMES:
                errors.append(f"Disallowed call: {node.func.id}")
            if isinstance(node.func, ast.Attribute) and node.func.attr in _BANNED_NAMES:
                errors.append(f"Disallowed method call: {node.func.attr}")
        elif isinstance(node, ast.Attribute):
            if node.attr.startswith("__"):
                errors.append(f"Disallowed dunder attribute: {node.attr}")
        elif isinstance(node, ast.Name):
            # A bare dunder name reaches the interpreter's internals directly —
            # ``__builtins__`` is the whole allowlist's back door, and
            # ``__class__``/``__globals__`` are the start of the usual escape.
            # The generated scene never needs a ``__…`` name; the same rule as
            # the attribute above, so a literal cannot smuggle one in either.
            if node.id.startswith("__"):
                errors.append(f"Disallowed dunder name: {node.id}")

    return SafetyResult(not errors, errors)
