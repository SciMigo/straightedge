"""Solid-geometry primitives for 3D scene templates.

A teacher's request like 「正方体 ABCD-A₁B₁C₁D₁ 棱长 2」 is parsed into a
``SolidSpec``. The 3D template then renders that spec by:

  1. embedding ``SOLID_HELPERS_SRC`` into the scene preamble, and
  2. emitting one call to ``make_cube(...)`` / ``make_box(...)``.

The helpers are stored as a source-text constant so tests can ``ast.parse``
them without needing manim installed.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any


class Concept3D:
    """Sub-topic identifiers under ``Topic.THREE_D``.

    Adding a 3D concept means adding an entry here, a parser in
    ``parse_solid_spec`` (or sibling), a planner branch, and a scene builder
    in ``templates._THREE_D_CONCEPT_BUILDERS``.
    """

    SOLID_OVERVIEW = "3d/solid_overview"
    SPHERE_SECTION = "3d/sphere_section"
    CUBE_SECTION = "3d/cube_section"
    THREE_VIEWS = "3d/three_views"


@dataclass(frozen=True)
class SolidSpec:
    """A parsed solid description.

    ``kind`` is one of:
      cube, box, regular_prism, regular_pyramid, tetrahedron, cylinder, cone.
    ``params`` carries kind-specific floats / ints (side, width/depth/height,
    n_sides, radius, ...). ``name`` is the canonical vertex-name spec; its
    format depends on the kind — see ``_NAME_PATTERNS`` / ``_DEFAULT_NAMES``.
    """

    kind: str
    params: dict[str, float]
    name: str


# Unicode subscript digits used in textbook notation (A₁B₁C₁D₁).
_SUB_DIGITS = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")

_DIMS_LWH = re.compile(
    r"长\s*(?:为|是)?\s*([0-9]+(?:\.[0-9]+)?)[\s，,]*"
    r"宽\s*(?:为|是)?\s*([0-9]+(?:\.[0-9]+)?)[\s，,]*"
    r"高\s*(?:为|是)?\s*([0-9]+(?:\.[0-9]+)?)"
)
_DIMS_BASE_H = re.compile(
    r"底面\s*([0-9]+(?:\.[0-9]+)?)\s*[×xX*]\s*([0-9]+(?:\.[0-9]+)?)"
    r"[\s，,]*高\s*(?:为|是)?\s*([0-9]+(?:\.[0-9]+)?)"
)
_DIMS_SIDE = re.compile(r"(?:棱长|边长)\s*(?:为|是)?\s*([0-9]+(?:\.[0-9]+)?)")
_DIMS_BASE_EDGE = re.compile(
    r"底面(?:边长|棱长)\s*(?:为|是)?\s*([0-9]+(?:\.[0-9]+)?)"
)
_DIMS_BASE_RADIUS = re.compile(
    r"(?:底面)?半径\s*(?:为|是)?\s*([0-9]+(?:\.[0-9]+)?)"
)
_DIMS_HEIGHT = re.compile(r"高\s*(?:为|是)?\s*([0-9]+(?:\.[0-9]+)?)")

_VERT_PAIR = re.compile(r"([A-Z]{3,8})\s*[-－]\s*([A-Z][A-Z0-9]+)")
_APEX_BASE = re.compile(r"\b([A-Z])\s*[-－]\s*([A-Z]{3,8})\b")
_TETRA_NAME = re.compile(r"\b([A-Z]{4}|[A-Z]-[A-Z]{3})\b")

# 「过 D、A₁、C₁ 三点(的截面)」 / 「经过 D, A1, C1 的截面」 — the trailing tokens
# anchor the end of the captured point span; non-greedy keeps it minimal.
_SECTION_SPAN = re.compile(
    r"(?:经过|过)([A-Z0-9\s、,，]+?)(?:三点|四点|五点|六点|的截面|的平面|截面|平面)"
)
_SAFE_POINT = re.compile(r"[A-Z]\d?")

_PRISM_HINT = re.compile(r"正?\s*([三四五六七八])\s*棱柱")
_PYRAMID_HINT = re.compile(r"正?\s*([三四五六七八])\s*棱锥")

_CN_NUM = {"三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8}
_CN_NUM_REV = {v: k for k, v in _CN_NUM.items()}

_CUBE_HINTS = ("正方体", "立方体")
_BOX_HINTS = ("长方体",)

# Allowed shape of the canonical vertex-name per kind. The parser and codegen
# validate against this so an unrecognized name falls back to ``_DEFAULT_NAMES``
# rather than being interpolated into the generated scene source.
_NAME_PATTERNS = {
    "cube": re.compile(r"[A-Z]{3,4}-[A-Z0-9]+"),
    "box": re.compile(r"[A-Z]{3,4}-[A-Z0-9]+"),
    "regular_prism": re.compile(r"[A-Z]{3,8}-[A-Z0-9]+"),
    "regular_pyramid": re.compile(r"[A-Z]-[A-Z]{3,8}"),
    "tetrahedron": re.compile(r"[A-Z]{4}|[A-Z]-[A-Z]{3}"),
    "cylinder": re.compile(r"[A-Z][0-9]*-[A-Z][0-9]*"),
    "cone": re.compile(r"[A-Z]-[A-Z][0-9]*"),
}

_DEFAULT_NAMES = {
    "cube": "ABCD-A1B1C1D1",
    "box": "ABCD-A1B1C1D1",
    "regular_prism": "ABCD-A1B1C1D1",
    "regular_pyramid": "P-ABCD",
    "tetrahedron": "ABCD",
    "cylinder": "O-O1",
    "cone": "P-O",
}


def parse_solid_spec(request: str) -> SolidSpec | None:
    """Detect a recognized solid description in a Chinese request.

    Returns None if no recognized solid keyword is present, leaving the caller
    free to fall back to a generic 3D scene. Dispatch order is most-specific
    first (正四面体 before generic 三棱锥; 圆锥曲线 is already routed away by
    the topic-detection layer before reaching here).
    """
    if any(h in request for h in _CUBE_HINTS):
        return _parse_cube(request)
    if any(h in request for h in _BOX_HINTS):
        return _parse_box(request)
    if "正四面体" in request:
        return _parse_tetrahedron(request)
    m = _PYRAMID_HINT.search(request)
    if m:
        return _parse_pyramid(request, n_sides=_CN_NUM[m.group(1)])
    m = _PRISM_HINT.search(request)
    if m:
        return _parse_prism(request, n_sides=_CN_NUM[m.group(1)])
    if "圆柱" in request:
        return _parse_cylinder(request)
    if "圆锥" in request:
        return _parse_cone(request)
    return None


def _parse_cube(request: str) -> SolidSpec:
    name = _validated_name("cube", _parse_vertex_name(request))
    m = _DIMS_SIDE.search(request)
    side = _safe_dim(m.group(1), default=2.0) if m else 2.0
    return SolidSpec(kind="cube", params={"side": side}, name=name)


def _parse_box(request: str) -> SolidSpec:
    name = _validated_name("box", _parse_vertex_name(request))
    m = _DIMS_LWH.search(request) or _DIMS_BASE_H.search(request)
    if m:
        w = _safe_dim(m.group(1), default=3.0)
        d = _safe_dim(m.group(2), default=2.0)
        h = _safe_dim(m.group(3), default=2.0)
    else:
        w, d, h = 3.0, 2.0, 2.0
    return SolidSpec(kind="box", params={"width": w, "depth": d, "height": h}, name=name)


def _parse_prism(request: str, *, n_sides: int) -> SolidSpec:
    candidate = _parse_vertex_name(request)
    if candidate is not None:
        bottom = candidate.split("-", 1)[0]
        if len(bottom) != n_sides:
            candidate = None
    name = _validated_name("regular_prism", candidate)
    radius = _parse_base_radius(request, n_sides)
    height = _parse_height(request)
    return SolidSpec(
        kind="regular_prism",
        params={"n_sides": n_sides, "radius": radius, "height": height},
        name=name,
    )


def _parse_pyramid(request: str, *, n_sides: int) -> SolidSpec:
    candidate = _parse_apex_base_name(request)
    if candidate is not None:
        base = candidate.split("-", 1)[1]
        if len(base) != n_sides:
            candidate = None
    name = _validated_name("regular_pyramid", candidate)
    radius = _parse_base_radius(request, n_sides)
    height = _parse_height(request)
    return SolidSpec(
        kind="regular_pyramid",
        params={"n_sides": n_sides, "radius": radius, "height": height},
        name=name,
    )


def _parse_tetrahedron(request: str) -> SolidSpec:
    name = _validated_name("tetrahedron", _parse_tetra_name(request))
    m = _DIMS_SIDE.search(request)
    side = _safe_dim(m.group(1), default=2.0) if m else 2.0
    return SolidSpec(kind="tetrahedron", params={"side": side}, name=name)


def _parse_cylinder(request: str) -> SolidSpec:
    name = _DEFAULT_NAMES["cylinder"]
    m = _DIMS_BASE_RADIUS.search(request)
    radius = _safe_dim(m.group(1), default=1.0) if m else 1.0
    height = _parse_height(request)
    return SolidSpec(kind="cylinder", params={"radius": radius, "height": height}, name=name)


def _parse_cone(request: str) -> SolidSpec:
    name = _DEFAULT_NAMES["cone"]
    m = _DIMS_BASE_RADIUS.search(request)
    radius = _safe_dim(m.group(1), default=1.0) if m else 1.0
    height = _parse_height(request)
    return SolidSpec(kind="cone", params={"radius": radius, "height": height}, name=name)


def _parse_base_radius(request: str, n_sides: int) -> float:
    """Prefer 底面半径; else convert 底面边长 to circumradius for a regular n-gon."""
    m = _DIMS_BASE_RADIUS.search(request)
    if m:
        return _safe_dim(m.group(1), default=1.0)
    m = _DIMS_BASE_EDGE.search(request)
    if m:
        edge = _safe_dim(m.group(1), default=1.0)
        return edge / (2 * math.sin(math.pi / n_sides))
    return 1.0


def _parse_height(request: str) -> float:
    m = _DIMS_HEIGHT.search(request)
    return _safe_dim(m.group(1), default=2.0) if m else 2.0


def _parse_apex_base_name(request: str) -> str | None:
    """Extract a pyramid name like 'P-ABCD' from the request."""
    normalized = request.translate(_SUB_DIGITS).replace("_", "")
    m = _APEX_BASE.search(normalized)
    return f"{m.group(1)}-{m.group(2)}" if m else None


def _parse_tetra_name(request: str) -> str | None:
    """Extract a tetrahedron name like 'ABCD' or 'A-BCD' from the request."""
    normalized = request.translate(_SUB_DIGITS).replace("_", "")
    # Skip names that look like prism/pyramid pairs.
    if "-" in normalized:
        m = _APEX_BASE.search(normalized)
        if m and len(m.group(2)) == 3:
            return f"{m.group(1)}-{m.group(2)}"
    m = _TETRA_NAME.search(normalized)
    return m.group(1) if m else None


def _validated_name(kind: str, candidate: str | None) -> str:
    if candidate and _is_safe_name_for(kind, candidate):
        return candidate
    return _DEFAULT_NAMES[kind]


def solid_construction_code(spec: SolidSpec) -> str:
    """Return a Python source snippet that constructs ``(solid, verts)``.

    Numeric params and the vertex-name string are validated here so the
    embedded call cannot smuggle arbitrary code into the generated scene.
    """
    name = spec.name if _is_safe_name_for(spec.kind, spec.name) else _DEFAULT_NAMES[spec.kind]
    if spec.kind == "cube":
        side = _safe_dim(spec.params.get("side"), default=2.0)
        return f'make_cube(side={_fmt_float(side)}, name="{name}")'
    if spec.kind == "box":
        w = _safe_dim(spec.params.get("width"), default=3.0)
        d = _safe_dim(spec.params.get("depth"), default=2.0)
        h = _safe_dim(spec.params.get("height"), default=2.0)
        return (
            f"make_box(width={_fmt_float(w)}, depth={_fmt_float(d)}, "
            f'height={_fmt_float(h)}, name="{name}")'
        )
    if spec.kind == "regular_prism":
        n = _safe_n_sides(spec.params.get("n_sides"), default=4)
        r = _safe_dim(spec.params.get("radius"), default=1.0)
        h = _safe_dim(spec.params.get("height"), default=2.0)
        return (
            f"make_regular_prism(n_sides={n}, radius={_fmt_float(r)}, "
            f'height={_fmt_float(h)}, name="{name}")'
        )
    if spec.kind == "regular_pyramid":
        n = _safe_n_sides(spec.params.get("n_sides"), default=4)
        r = _safe_dim(spec.params.get("radius"), default=1.0)
        h = _safe_dim(spec.params.get("height"), default=2.0)
        return (
            f"make_regular_pyramid(n_sides={n}, radius={_fmt_float(r)}, "
            f'height={_fmt_float(h)}, name="{name}")'
        )
    if spec.kind == "tetrahedron":
        side = _safe_dim(spec.params.get("side"), default=2.0)
        return f'make_tetrahedron(side={_fmt_float(side)}, name="{name}")'
    if spec.kind == "cylinder":
        r = _safe_dim(spec.params.get("radius"), default=1.0)
        h = _safe_dim(spec.params.get("height"), default=2.0)
        return (
            f"make_cylinder(radius={_fmt_float(r)}, "
            f'height={_fmt_float(h)}, name="{name}")'
        )
    if spec.kind == "cone":
        r = _safe_dim(spec.params.get("radius"), default=1.0)
        h = _safe_dim(spec.params.get("height"), default=2.0)
        return (
            f"make_cone(radius={_fmt_float(r)}, "
            f'height={_fmt_float(h)}, name="{name}")'
        )
    raise ValueError(f"Unknown solid kind: {spec.kind!r}")


def solid_title_zh(spec: SolidSpec) -> str:
    """Chinese name for the solid, used in the on-screen title."""
    if spec.kind == "cube":
        return "正方体"
    if spec.kind == "box":
        return "长方体"
    if spec.kind == "tetrahedron":
        return "正四面体"
    if spec.kind == "cylinder":
        return "圆柱"
    if spec.kind == "cone":
        return "圆锥"
    if spec.kind in ("regular_prism", "regular_pyramid"):
        n = _safe_n_sides(spec.params.get("n_sides"), default=4)
        suffix = "棱柱" if spec.kind == "regular_prism" else "棱锥"
        return f"正{_CN_NUM_REV.get(n, str(n))}{suffix}"
    raise ValueError(f"Unknown solid kind: {spec.kind!r}")


def solid_volume_latex(spec: SolidSpec) -> str:
    """A symbolic (and where clean, numeric) volume label for MathTex.

    Cube:        ``V = a^{3} = 2^{3} = 8``
    Box:         ``V = abc = 3 \\cdot 2 \\cdot 4 = 24``
    Reg. prism:  ``V = S \\cdot h`` (S is the base area; CJK subscripts
                 don't survive Manim's default LaTeX, so the on-screen Chinese
                 hint lives in the Text narration, not in MathTex).
    Reg. pyrmd:  ``V = \\frac{1}{3} S \\cdot h``
    Tetrahedron: ``V = \\frac{\\sqrt{2}}{12} a^{3}``
    Cylinder:    ``V = \\pi r^{2} h``
    Cone:        ``V = \\frac{1}{3} \\pi r^{2} h``
    """
    if spec.kind == "cube":
        side = float(spec.params.get("side", 2.0))
        return rf"V = a^{{3}} = {_fmt_num(side)}^{{3}} = {_fmt_num(side ** 3)}"
    if spec.kind == "box":
        w = float(spec.params.get("width", 3.0))
        d = float(spec.params.get("depth", 2.0))
        h = float(spec.params.get("height", 2.0))
        return (
            rf"V = abc = {_fmt_num(w)} \cdot {_fmt_num(d)} \cdot {_fmt_num(h)}"
            rf" = {_fmt_num(w * d * h)}"
        )
    if spec.kind == "regular_prism":
        n = _safe_n_sides(spec.params.get("n_sides"), default=4)
        r = float(spec.params.get("radius", 1.0))
        h = float(spec.params.get("height", 2.0))
        s_base = 0.5 * n * r * r * math.sin(2 * math.pi / n)
        return (
            rf"V = S \cdot h = {_fmt_num(s_base)} \cdot {_fmt_num(h)} = "
            rf"{_fmt_num(s_base * h)}"
        )
    if spec.kind == "regular_pyramid":
        n = _safe_n_sides(spec.params.get("n_sides"), default=4)
        r = float(spec.params.get("radius", 1.0))
        h = float(spec.params.get("height", 2.0))
        s_base = 0.5 * n * r * r * math.sin(2 * math.pi / n)
        return (
            rf"V = \frac{{1}}{{3}} S \cdot h = \frac{{1}}{{3}} \cdot "
            rf"{_fmt_num(s_base)} \cdot {_fmt_num(h)} = {_fmt_num(s_base * h / 3)}"
        )
    if spec.kind == "tetrahedron":
        side = float(spec.params.get("side", 2.0))
        return (
            rf"V = \frac{{\sqrt{{2}}}}{{12}} a^{{3}} = "
            rf"\frac{{\sqrt{{2}}}}{{12}} \cdot {_fmt_num(side)}^{{3}}"
        )
    if spec.kind == "cylinder":
        r = float(spec.params.get("radius", 1.0))
        h = float(spec.params.get("height", 2.0))
        return (
            rf"V = \pi r^{{2}} h = \pi \cdot {_fmt_num(r)}^{{2}} \cdot "
            rf"{_fmt_num(h)} = {_fmt_num(r * r * h)}\pi"
        )
    if spec.kind == "cone":
        r = float(spec.params.get("radius", 1.0))
        h = float(spec.params.get("height", 2.0))
        return (
            rf"V = \frac{{1}}{{3}} \pi r^{{2}} h = "
            rf"\frac{{{_fmt_num(r * r * h)}}}{{3}}\pi"
        )
    raise ValueError(f"Unknown solid kind: {spec.kind!r}")


def parse_section_points(request: str) -> list[str] | None:
    """Extract 3+ point names from a 「过 X、Y、Z 三点的截面」-style request.

    Returns None if the request doesn't look like a section query at all,
    or if fewer than 3 valid uppercase point names are present.
    """
    normalized = request.translate(_SUB_DIGITS).replace("_", "")
    if "截" not in normalized and "平面" not in normalized:
        return None
    m = _SECTION_SPAN.search(normalized)
    if not m:
        return None
    points = _SAFE_POINT.findall(m.group(1))
    return points if len(points) >= 3 else None


def cube_section_code(point_names: list[str]) -> str:
    """Emit a safe ``cube_section(verts, [...])`` call.

    Each name is re-validated against ``[A-Z]\\d?`` before being interpolated
    into the generated source. An invalid list falls back to the canonical
    ``[D, A1, C1]`` (a triangle section every textbook recognizes).
    """
    safe = [n for n in point_names if isinstance(n, str) and _SAFE_POINT.fullmatch(n)]
    if len(safe) < 3:
        safe = ["D", "A1", "C1"]
    args = ", ".join(f'"{n}"' for n in safe)
    return f"cube_section(verts, [{args}])"


def is_three_views_request(request: str) -> bool:
    """Whether the teacher asked for 三视图 (standard 正/侧/俯 layout)."""
    return "三视图" in request


def three_views_code(spec: SolidSpec) -> str:
    """Emit a safe ``three_views(kind, {...})`` call.

    Kind and params come from the validated ``SolidSpec``; the runtime helper
    in ``SOLID_HELPERS_SRC`` dispatches on the kind string and returns three
    2D outline mobjects for the textbook layout.
    """
    if spec.kind in ("cube", "tetrahedron"):
        side = _safe_dim(spec.params.get("side"), default=2.0)
        return f'three_views("{spec.kind}", {{"side": {_fmt_float(side)}}})'
    if spec.kind == "box":
        w = _safe_dim(spec.params.get("width"), default=3.0)
        d = _safe_dim(spec.params.get("depth"), default=2.0)
        h = _safe_dim(spec.params.get("height"), default=2.0)
        return (
            f'three_views("box", {{"width": {_fmt_float(w)}, '
            f'"depth": {_fmt_float(d)}, "height": {_fmt_float(h)}}})'
        )
    if spec.kind in ("regular_prism", "regular_pyramid"):
        n = _safe_n_sides(spec.params.get("n_sides"), default=4)
        r = _safe_dim(spec.params.get("radius"), default=1.0)
        h = _safe_dim(spec.params.get("height"), default=2.0)
        return (
            f'three_views("{spec.kind}", {{"n_sides": {n}, '
            f'"radius": {_fmt_float(r)}, "height": {_fmt_float(h)}}})'
        )
    if spec.kind in ("cylinder", "cone"):
        r = _safe_dim(spec.params.get("radius"), default=1.0)
        h = _safe_dim(spec.params.get("height"), default=2.0)
        return (
            f'three_views("{spec.kind}", {{"radius": {_fmt_float(r)}, '
            f'"height": {_fmt_float(h)}}})'
        )
    raise ValueError(f"Unknown solid kind: {spec.kind!r}")


def section_points_latex(point_names: list[str]) -> str:
    """Comma-separated MathTex source for the point list (D, A_{1}, C_{1})."""
    safe = [n for n in point_names if isinstance(n, str) and _SAFE_POINT.fullmatch(n)]
    if len(safe) < 3:
        safe = ["D", "A1", "C1"]
    pieces = []
    for n in safe:
        if len(n) == 2:
            pieces.append(f"{n[0]}_{{{n[1]}}}")
        else:
            pieces.append(n)
    return ", ".join(pieces)


def vertex_name_latex(name: str, kind: str | None = None) -> str:
    """Format a vertex-name spec for MathTex (e.g. 'A1' -> 'A_{1}').

    When ``kind`` is given, an unrecognized name falls back to that kind's
    default; without it, the box/cube default is used.
    """
    if not _is_safe_name_for(kind, name):
        name = _DEFAULT_NAMES.get(kind, "ABCD-A1B1C1D1")
    out: list[str] = []
    for m in re.finditer(r"[A-Z]\d*|-", name):
        token = m.group(0)
        if token == "-":
            out.append("-")
            continue
        letter, digits = token[0], token[1:]
        out.append(f"{letter}_{{{digits}}}" if digits else letter)
    return "".join(out)


def _parse_vertex_name(text: str) -> str | None:
    """Pull 'ABCD-A₁B₁C₁D₁' (with or without subscripts/underscores)."""
    normalized = text.translate(_SUB_DIGITS).replace("_", "")
    m = _VERT_PAIR.search(normalized)
    if not m:
        return None
    bottom, top_raw = m.group(1), m.group(2)
    top = re.findall(r"[A-Z]\d*", top_raw)
    if len(top) != len(bottom):
        return None
    return f"{bottom}-{''.join(top)}"


def _is_safe_name_for(kind: str | None, name: Any) -> bool:
    """Whether ``name`` is a syntactically safe vertex-name spec for ``kind``.

    A None ``kind`` (legacy callers) accepts the cube/box pattern. Unknown
    kinds reject everything so the caller falls back to a default.
    """
    if not isinstance(name, str):
        return False
    pattern = _NAME_PATTERNS.get(kind or "cube")
    return bool(pattern and pattern.fullmatch(name))


def _safe_dim(value: Any, *, default: float) -> float:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return default
    if not (0 < f < 1e3):
        return default
    return f


def _safe_n_sides(value: Any, *, default: int) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return n if 3 <= n <= 12 else default


def _fmt_float(value: float) -> str:
    """A literal that round-trips into the generated Python source."""
    if value == int(value):
        return f"{int(value)}.0"
    return repr(float(value))


def _fmt_num(value: float) -> str:
    """A compact LaTeX-friendly numeric string (1 not 1.0 when integral)."""
    if value == int(value):
        return str(int(value))
    return f"{value:g}"


# Embedded in the generated scene preamble. Tests ``ast.parse`` this string
# directly to catch syntax errors without needing manim installed. Symbols
# referenced (Prism/Polyhedron/VGroup/MathTex/BLUE/WHITE/np) all come from
# ``from manim import *`` in the surrounding preamble.
SOLID_HELPERS_SRC = r'''
def _subscriptify(name):
    import re as _re
    m = _re.fullmatch(r"([A-Za-z])(\d+)", name)
    if m:
        return f"{m.group(1)}_{{{m.group(2)}}}"
    return name


def _split_vertex_name(spec):
    import re as _re
    out = []
    for part in spec.split("-"):
        for m in _re.finditer(r"[A-Z]\d*", part):
            out.append(m.group(0))
    return out


def make_box(width=3.0, depth=2.0, height=2.0, name="ABCD-A1B1C1D1"):
    """Axis-aligned box centered on the origin, with named vertices.

    Returns ``(mobj, verts)`` where ``verts`` maps each name to a 3D position.
    """
    names = _split_vertex_name(name)
    if len(names) != 8:
        names = list("ABCD") + ["A1", "B1", "C1", "D1"]
    a = np.array([-width / 2, -depth / 2, -height / 2])
    b = np.array([+width / 2, -depth / 2, -height / 2])
    c = np.array([+width / 2, +depth / 2, -height / 2])
    d = np.array([-width / 2, +depth / 2, -height / 2])
    up = np.array([0.0, 0.0, height])
    coords = [a, b, c, d, a + up, b + up, c + up, d + up]
    mobj = Prism(dimensions=[width, depth, height])
    mobj.set_fill(BLUE, opacity=0.18)
    mobj.set_stroke(BLUE, width=2)
    return mobj, dict(zip(names, coords))


def make_cube(side=2.0, name="ABCD-A1B1C1D1"):
    return make_box(side, side, side, name)


def make_regular_prism(n_sides=4, radius=1.0, height=2.0, name="ABCD-A1B1C1D1"):
    """Right regular prism: regular n-gon base + parallel top.

    Base centered at z=-height/2, top at z=+height/2; circumradius is ``radius``.
    """
    names = _split_vertex_name(name)
    if len(names) != 2 * n_sides:
        letters = [chr(ord("A") + i) for i in range(n_sides)]
        names = letters + [f"{ch}1" for ch in letters]
    bottom = []
    for i in range(n_sides):
        ang = TAU * i / n_sides
        bottom.append(np.array([radius * np.cos(ang), radius * np.sin(ang), -height / 2]))
    top = [p + np.array([0.0, 0.0, height]) for p in bottom]
    coords = bottom + top
    side_faces = [
        [i, (i + 1) % n_sides, (i + 1) % n_sides + n_sides, i + n_sides]
        for i in range(n_sides)
    ]
    faces = [list(range(n_sides)), list(range(n_sides, 2 * n_sides)), *side_faces]
    mobj = Polyhedron(vertex_coords=coords, faces_list=faces)
    mobj.set_fill(BLUE, opacity=0.18)
    mobj.set_stroke(BLUE, width=2)
    return mobj, dict(zip(names, coords))


def make_regular_pyramid(n_sides=4, radius=1.0, height=2.0, name="P-ABCD"):
    """Right regular pyramid: regular n-gon base + apex above its center."""
    parts = name.split("-")
    if len(parts) == 2 and len(parts[0]) == 1 and len(parts[1]) == n_sides:
        apex_name = parts[0]
        base_names = list(parts[1])
    else:
        apex_name = "P"
        base_names = [chr(ord("A") + i) for i in range(n_sides)]
    base_pts = []
    for i in range(n_sides):
        ang = TAU * i / n_sides
        base_pts.append(np.array([radius * np.cos(ang), radius * np.sin(ang), -height / 2]))
    apex_pt = np.array([0.0, 0.0, height / 2])
    coords = base_pts + [apex_pt]
    apex_idx = n_sides
    side_faces = [[i, (i + 1) % n_sides, apex_idx] for i in range(n_sides)]
    faces = [list(range(n_sides)), *side_faces]
    mobj = Polyhedron(vertex_coords=coords, faces_list=faces)
    mobj.set_fill(BLUE, opacity=0.18)
    mobj.set_stroke(BLUE, width=2)
    verts = dict(zip(base_names, base_pts))
    verts[apex_name] = apex_pt
    return mobj, verts


def make_tetrahedron(side=2.0, name="ABCD"):
    """Regular tetrahedron with all edges of length ``side``.

    Centered so the centroid is at the origin; apex on +Z, base in the
    horizontal plane below.
    """
    flat = name.replace("-", "")
    letters = list(flat) if len(flat) == 4 else list("ABCD")
    apex_name, base_names = letters[0], letters[1:]
    r = side / np.sqrt(3.0)
    h = side * np.sqrt(2.0 / 3.0)
    base_z = -h / 4.0
    apex_pt = np.array([0.0, 0.0, 3.0 * h / 4.0])
    base_pts = []
    for k in range(3):
        ang = PI / 2.0 + TAU * k / 3.0
        base_pts.append(np.array([r * np.cos(ang), r * np.sin(ang), base_z]))
    coords = base_pts + [apex_pt]
    faces = [[0, 1, 2], [0, 1, 3], [1, 2, 3], [2, 0, 3]]
    mobj = Polyhedron(vertex_coords=coords, faces_list=faces)
    mobj.set_fill(BLUE, opacity=0.18)
    mobj.set_stroke(BLUE, width=2)
    verts = dict(zip(base_names, base_pts))
    verts[apex_name] = apex_pt
    return mobj, verts


def make_cylinder(radius=1.0, height=2.0, name="O-O1"):
    """Right circular cylinder centered at the origin with labeled axis ends."""
    parts = name.split("-")
    bottom_name = parts[0] if parts and parts[0] else "O"
    top_name = parts[1] if len(parts) > 1 and parts[1] else "O1"
    mobj = Cylinder(radius=radius, height=height)
    mobj.set_fill(BLUE, opacity=0.18)
    mobj.set_stroke(BLUE, width=2)
    verts = {
        bottom_name: np.array([0.0, 0.0, -height / 2]),
        top_name: np.array([0.0, 0.0, +height / 2]),
    }
    return mobj, verts


def make_cone(radius=1.0, height=2.0, name="P-O"):
    """Right circular cone with apex on +Z, base on -Z (centered)."""
    parts = name.split("-")
    apex_name = parts[0] if parts and parts[0] else "P"
    base_name = parts[1] if len(parts) > 1 and parts[1] else "O"
    # Manim's Cone(direction=+Z) puts apex at z=0 and base at z=-height;
    # shifting by +height/2 centers it (apex at +h/2, base at -h/2).
    mobj = Cone(base_radius=radius, height=height, direction=OUT, show_base=True)
    mobj.shift(OUT * height / 2)
    mobj.set_fill(BLUE, opacity=0.18)
    mobj.set_stroke(BLUE, width=2)
    verts = {
        apex_name: np.array([0.0, 0.0, +height / 2]),
        base_name: np.array([0.0, 0.0, -height / 2]),
    }
    return mobj, verts


def cube_section(verts, point_names, color=YELLOW, opacity=0.45):
    """Polygon where a plane (through >=3 named cube vertices) cuts the cube.

    ``verts`` must be the dict returned by ``make_cube``/``make_box`` (8 entries
    in build order: 4 bottom then 4 top). Returns the Polygon mobject or None
    on degenerate input (collinear plane points, non-cube verts, etc.).
    """
    chosen = [verts[n] for n in point_names if n in verts]
    if len(chosen) < 3:
        return None
    p0 = chosen[0]
    normal = np.cross(chosen[1] - p0, chosen[2] - p0)
    if float(np.linalg.norm(normal)) < 1e-9:
        return None

    pts_list = list(verts.values())
    if len(pts_list) != 8:
        return None
    edge_pairs = [
        (0, 1), (1, 2), (2, 3), (3, 0),
        (4, 5), (5, 6), (6, 7), (7, 4),
        (0, 4), (1, 5), (2, 6), (3, 7),
    ]

    section_pts = []

    def _add(p):
        for q in section_pts:
            if float(np.linalg.norm(p - q)) < 1e-7:
                return
        section_pts.append(p)

    for ai, bi in edge_pairs:
        a, b = pts_list[ai], pts_list[bi]
        da = float(np.dot(a - p0, normal))
        db = float(np.dot(b - p0, normal))
        if abs(da) < 1e-9 and abs(db) < 1e-9:
            continue  # edge lies in the plane; endpoints picked up via neighbors
        if abs(da) < 1e-9:
            _add(a)
        if abs(db) < 1e-9:
            _add(b)
        if abs(da) >= 1e-9 and abs(db) >= 1e-9 and da * db < 0:
            t = da / (da - db)
            _add(a + t * (b - a))

    if len(section_pts) < 3:
        return None

    centroid = sum(section_pts) / len(section_pts)
    n_unit = normal / float(np.linalg.norm(normal))
    ref = section_pts[0] - centroid
    ref_norm = float(np.linalg.norm(ref))
    if ref_norm < 1e-9:
        ref = np.array([1.0, 0.0, 0.0])
        if abs(float(np.dot(ref, n_unit))) > 0.99:
            ref = np.array([0.0, 1.0, 0.0])
        ref = ref - np.dot(ref, n_unit) * n_unit
        ref = ref / float(np.linalg.norm(ref))
    else:
        ref = ref / ref_norm
    cross = np.cross(n_unit, ref)

    def _angle(p):
        d = p - centroid
        return float(np.arctan2(np.dot(d, cross), np.dot(d, ref)))

    ordered = sorted(section_pts, key=_angle)
    return Polygon(*ordered, color=color, fill_opacity=opacity, stroke_width=3)


def label_vertices(verts, font_size=28, offset=0.35, color=WHITE):
    """A VGroup of MathTex vertex labels, each pushed outward from the centroid.

    Scenes typically pass each child through ``add_fixed_orientation_mobjects``
    so the labels billboard toward the camera as it rotates.
    """
    centroid = sum(verts.values()) / len(verts)
    labels = VGroup()
    for n, pos in verts.items():
        direction = pos - centroid
        norm = float(np.linalg.norm(direction))
        unit = direction / norm if norm > 1e-9 else np.array([1.0, 0.0, 0.0])
        label = MathTex(_subscriptify(n), font_size=font_size, color=color)
        label.move_to(pos + unit * offset)
        labels.add(label)
    return labels


def three_views(kind, params, color=BLUE, stroke=3):
    """Return (front, side, top) 2D outline mobjects for textbook 三视图.

    front = 正视图 (view along -y onto xz),  side = 侧视图 (along -x onto yz),
    top   = 俯视图 (along -z onto xy).  Curved solids get circles where
    appropriate; pyramids/cones get a center cross in the top view to show
    where the apex projects.  All returned mobjects live in the xy plane and
    can be freely arranged by the scene.
    """
    if kind == "cube":
        a = float(params.get("side", 2.0))
        return (
            Square(side_length=a, color=color, stroke_width=stroke),
            Square(side_length=a, color=color, stroke_width=stroke),
            Square(side_length=a, color=color, stroke_width=stroke),
        )
    if kind == "box":
        w = float(params.get("width", 3.0))
        d = float(params.get("depth", 2.0))
        h = float(params.get("height", 2.0))
        return (
            Rectangle(width=w, height=h, color=color, stroke_width=stroke),
            Rectangle(width=d, height=h, color=color, stroke_width=stroke),
            Rectangle(width=w, height=d, color=color, stroke_width=stroke),
        )
    if kind == "regular_prism":
        n = int(params.get("n_sides", 4))
        r = float(params.get("radius", 1.0))
        h = float(params.get("height", 2.0))
        base_pts = [
            np.array([r * np.cos(TAU * i / n), r * np.sin(TAU * i / n), 0.0])
            for i in range(n)
        ]
        x_extent = 2.0 * max(abs(p[0]) for p in base_pts)
        return (
            Rectangle(width=x_extent, height=h, color=color, stroke_width=stroke),
            Rectangle(width=x_extent, height=h, color=color, stroke_width=stroke),
            Polygon(*base_pts, color=color, stroke_width=stroke),
        )
    if kind == "regular_pyramid":
        n = int(params.get("n_sides", 4))
        r = float(params.get("radius", 1.0))
        h = float(params.get("height", 2.0))
        base_pts = [
            np.array([r * np.cos(TAU * i / n), r * np.sin(TAU * i / n), 0.0])
            for i in range(n)
        ]
        x_extent = 2.0 * max(abs(p[0]) for p in base_pts)
        # Front/side: isoceles triangle (apex centered above base).
        front = Polygon(
            np.array([-x_extent / 2, -h / 2, 0.0]),
            np.array([+x_extent / 2, -h / 2, 0.0]),
            np.array([0.0, +h / 2, 0.0]),
            color=color, stroke_width=stroke,
        )
        side = front.copy()
        # Top: n-gon outline + lateral edges (dashed) + apex projection dot.
        outline = Polygon(*base_pts, color=color, stroke_width=stroke)
        diags = VGroup(*[
            DashedLine(ORIGIN, p, color=color, stroke_width=2, dash_length=0.08)
            for p in base_pts
        ])
        apex_dot = Dot(ORIGIN, color=color, radius=0.06)
        top = VGroup(outline, diags, apex_dot)
        return front, side, top
    if kind == "tetrahedron":
        side_len = float(params.get("side", 2.0))
        r = side_len / np.sqrt(3.0)
        h = side_len * np.sqrt(2.0 / 3.0)
        apex_z = 3.0 * h / 4.0
        base_z = -h / 4.0
        # Match make_tetrahedron's base layout (one vertex at angle pi/2, etc.).
        base_xy = [
            np.array([r * np.cos(PI / 2 + TAU * k / 3.0),
                      r * np.sin(PI / 2 + TAU * k / 3.0)])
            for k in range(3)
        ]
        x_max = max(abs(p[0]) for p in base_xy)
        y_max = max(p[1] for p in base_xy)
        y_min = min(p[1] for p in base_xy)
        front = Polygon(
            np.array([-x_max, base_z, 0.0]),
            np.array([+x_max, base_z, 0.0]),
            np.array([0.0, apex_z, 0.0]),
            color=color, stroke_width=stroke,
        )
        side = Polygon(
            np.array([y_min, base_z, 0.0]),
            np.array([y_max, base_z, 0.0]),
            np.array([0.0, apex_z, 0.0]),
            color=color, stroke_width=stroke,
        )
        top = Polygon(
            *[np.array([p[0], p[1], 0.0]) for p in base_xy],
            color=color, stroke_width=stroke,
        )
        return front, side, top
    if kind == "cylinder":
        r = float(params.get("radius", 1.0))
        h = float(params.get("height", 2.0))
        return (
            Rectangle(width=2 * r, height=h, color=color, stroke_width=stroke),
            Rectangle(width=2 * r, height=h, color=color, stroke_width=stroke),
            Circle(radius=r, color=color, stroke_width=stroke),
        )
    if kind == "cone":
        r = float(params.get("radius", 1.0))
        h = float(params.get("height", 2.0))
        front = Polygon(
            np.array([-r, -h / 2, 0.0]),
            np.array([+r, -h / 2, 0.0]),
            np.array([0.0, +h / 2, 0.0]),
            color=color, stroke_width=stroke,
        )
        side = front.copy()
        outline = Circle(radius=r, color=color, stroke_width=stroke)
        apex_dot = Dot(ORIGIN, color=color, radius=0.06)
        top = VGroup(outline, apex_dot)
        return front, side, top
    # Unknown kind — return placeholder unit squares so the scene still draws.
    return (
        Square(side_length=1.0, color=color, stroke_width=stroke),
        Square(side_length=1.0, color=color, stroke_width=stroke),
        Square(side_length=1.0, color=color, stroke_width=stroke),
    )
'''.strip()
