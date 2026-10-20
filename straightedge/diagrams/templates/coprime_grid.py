"""Coprime grid: the numbers 1 … n, struck out one prime factor of n at a time.

Euler's φ(n) counts the k in 1 … n that share no factor with n. A number shares
a factor with n exactly when one of n's primes divides it, so the count can be
watched rather than recited: lay 1 … n out in rows, strike the multiples of the
first prime, then the multiples of the next that are still standing, and count
what is left. For n = 100: fifty even numbers, then ten odd multiples of 5,
leaving φ(100) = 100 − 50 − 10 = 40.

image_hint usage::

    {"type": "coprime_grid", "params": {"n": 100, "theme": "dark",
                                        "reveal": [1, 2, 3]}}

``columns`` sets the row length (default: the smallest square that holds n, so
10 for 100). Natural steps, in order: ``strike_<q>`` for each prime factor q of
n, smallest first, then ``survivors`` (the coprime residues and the count). See
``docs/staged-reveal.md`` for ``reveal`` and ``upto``.

The totient and every count in the legend are computed here, and the
inclusion–exclusion total is checked against a direct gcd count. Why not
``lattice_grid``: that template plots lattice points (x, y) against axes and
lights the ones with gcd(x, y) = 1 — a statement about pairs. This one is about
single residues against a fixed n, laid out as a table, so neither its geometry
nor its predicate carries over.
"""
from __future__ import annotations

from math import ceil, gcd, isqrt
from typing import Any, Dict, List

from ...qc import Finding
from ..registry import register
from ..renderer import line, rect, style, svg_document, text, text_width, titled_group
from ..staging import Stager, reveal_findings
from ..themes import DiagramTheme, resolve_theme
from ._modular import THEMES, as_int, phi, prime_factors

MAX_N = 400
MARGIN = 28
TITLE_FONT = 30
LEGEND_FONT = 26
TOTAL_FONT = 32
CELL_MAX = 64
GRID_MAX = 1000
LEGEND_GAP = 48
SWATCH = 30
#: Strike colours, one per prime factor in order. Distinct categorical roles.
STRIKE_ROLES = ("danger", "warning", "secondary", "accent", "primary")


def _columns(n: int, raw: Any) -> int:
    try:
        cols = int(raw)
    except (TypeError, ValueError):
        cols = 0
    if cols < 1:
        cols = isqrt(n) + (0 if isqrt(n) ** 2 == n else 1)
    return max(1, min(cols, n))


def _findings(params: Dict[str, Any]) -> List[Finding]:
    found: List[Finding] = []
    as_int(params, "n", found, low=2, high=MAX_N)
    as_int(params, "columns", found, low=1, high=40, required=False)
    if found:
        return found
    return reveal_findings(params, steps(params))


def steps(params: Dict[str, Any]) -> List[str]:
    """The figure's natural steps for these params, in drawing order."""
    try:
        n = int(params.get("n"))
    except (TypeError, ValueError):
        return []
    if n < 2:
        return []
    return [f"strike_{q}" for q in prime_factors(n)] + ["survivors"]


def _join(words: List[str]) -> str:
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " or " + words[-1]


@register("coprime_grid")
class CoprimeGridTemplate:
    """1 … n in a grid; multiples of each prime factor struck; the coprime ones counted."""

    motion = "none"
    themes = THEMES
    checks = ["phi(n) and every struck count are computed, and checked against a gcd count",
              "the reveal plan has one stage per natural step, in order"]

    def refusal_findings(self, params: Dict[str, Any]) -> List[Finding]:
        return _findings(params or {})

    def natural_steps(self, params: Dict[str, Any]) -> List[str]:
        return steps(params or {})

    def render(self, params: Dict[str, Any]) -> str:
        params = params or {}
        theme = resolve_theme(params.get("theme", "professional"), THEMES)
        title = str(params.get("title", "") or "").strip()
        reveal = params.get("reveal") or []
        if _findings(params):
            return ""
        n = int(params.get("n"))
        cols = _columns(n, int(params.get("columns")) if params.get("columns") is not None else 0)
        upto = int(params.get("upto")) if params.get("upto") is not None else None
        stager = Stager({"reveal": reveal, "upto": upto}, steps(params))
        primes = prime_factors(n)

        # Each prime strikes the multiples no earlier prime has struck.
        struck_by: Dict[int, int] = {}
        counts: List[int] = []
        for q in primes:
            fresh = [k for k in range(1, n + 1) if k % q == 0 and k not in struck_by]
            for k in fresh:
                struck_by[k] = q
            counts.append(len(fresh))
        survivors = [k for k in range(1, n + 1) if k not in struck_by]
        total = phi(n)
        assert len(survivors) == total == n - sum(counts)
        assert all(gcd(k, n) == 1 for k in survivors)

        rows = ceil(n / cols)
        cell = min(CELL_MAX, GRID_MAX / cols)
        num_font = max(14.0, round(cell * 0.42, 1))
        grid_w, grid_h = cols * cell, rows * cell

        legend: List[str] = []
        for i, (q, c) in enumerate(zip(primes, counts)):
            earlier = [str(x) for x in primes[:i]]
            name = "even numbers" if q == 2 else f"multiples of {q}"
            if earlier:
                name += f", not of {_join(earlier)}"
            legend.append(f"{name}: {c}")
        legend.append(f"coprime to {n}: {total}")
        total_line = f"φ({n}) = {n}" + "".join(f" − {c}" for c in counts) + f" = {total}"
        legend_w = max(SWATCH + 14 + max(text_width(s, LEGEND_FONT, safe=True) for s in legend),
                       text_width(total_line, TOTAL_FONT, bold=True, safe=True))
        if not title:
            title = f"Which of 1 … {n} share no factor with {n}?"
        body_w = grid_w + LEGEND_GAP + legend_w
        width = max(body_w, text_width(title, TITLE_FONT, bold=True, safe=True)) + 2 * MARGIN
        gx = (width - body_w) / 2
        gy = MARGIN + TITLE_FONT + 30
        lx = gx + grid_w + LEGEND_GAP
        legend_h = len(legend) * (LEGEND_FONT + 30) + TOTAL_FONT + 40
        height = gy + max(grid_h, legend_h) + MARGIN

        parts: List[str] = [style(self._css(theme, num_font)),
                            rect(0, 0, round(width), round(height), **{"class": "cg-background"}),
                            text(width / 2, MARGIN + TITLE_FONT, title,
                                 **{"class": "cg-title", "text-anchor": "middle"})]

        def at(k: int) -> tuple:
            i = k - 1
            return gx + (i % cols) * cell, gy + (i // cols) * cell

        base: List[str] = []
        for k in range(1, n + 1):
            x, y = at(k)
            base.append(rect(round(x, 2), round(y, 2), round(cell, 2), round(cell, 2),
                             **{"class": "cg-cell"}))
            base.append(text(round(x + cell / 2, 2), round(y + cell / 2 + num_font * 0.36, 2), str(k),
                             **{"class": "cg-num", "text-anchor": "middle"}))
        parts.append(titled_group(f"1 … {n}", base))

        def legend_row(i: int, cls: str) -> List[str]:
            y = gy + i * (LEGEND_FONT + 30)
            return [rect(lx, y, SWATCH, SWATCH, rx=4, **{"class": cls}),
                    text(lx + SWATCH + 14, y + SWATCH / 2 + 9, legend[i], **{"class": "cg-legend"})]

        for i, q in enumerate(primes):
            role = f"cg-strike-{i % len(STRIKE_ROLES)}"
            marks: List[str] = []
            for k in range(1, n + 1):
                if struck_by.get(k) != q:
                    continue
                x, y = at(k)
                pad = cell * 0.12
                marks.append(rect(round(x + 2, 2), round(y + 2, 2), round(cell - 4, 2), round(cell - 4, 2),
                                  **{"class": role}))
                marks.append(line(round(x + pad, 2), round(y + cell - pad, 2),
                                  round(x + cell - pad, 2), round(y + pad, 2),
                                  **{"class": role + "-slash"}))
            marks += legend_row(i, role)
            parts.append(stager.wrap(i, titled_group(legend[i], marks)))

        keep: List[str] = []
        for k in survivors:
            x, y = at(k)
            keep.append(rect(round(x + 3, 2), round(y + 3, 2), round(cell - 6, 2), round(cell - 6, 2),
                             rx=4, **{"class": "cg-keep"}))
        keep += legend_row(len(primes), "cg-keep-swatch")
        keep.append(text(lx, gy + len(legend) * (LEGEND_FONT + 30) + TOTAL_FONT + 10, total_line,
                         **{"class": "cg-total"}))
        parts.append(stager.wrap(len(primes), titled_group(total_line, keep)))

        return svg_document("\n".join(p for p in parts if p), width=round(width), height=round(height),
                            class_name="diagram coprime-grid")

    @staticmethod
    def _css(theme: DiagramTheme, num_font: float) -> str:
        strikes = "".join(
            f".cg-strike-{i}{{fill:{getattr(theme, role)};fill-opacity:.42;stroke:none}}"
            f".cg-strike-{i}-slash{{stroke:{getattr(theme, role)};stroke-width:2.5;opacity:.9}}"
            for i, role in enumerate(STRIKE_ROLES))
        return (
            f".cg-background{{fill:{theme.background or theme.surface_alt}}}"
            f".cg-title{{font:600 {TITLE_FONT}px sans-serif;fill:{theme.text}}}"
            f".cg-cell{{fill:{theme.surface};stroke:{theme.background or theme.rule};stroke-width:2}}"
            f".cg-num{{font:600 {num_font}px sans-serif;fill:{theme.text}}}"
            f".cg-keep{{fill:none;stroke:{theme.success};stroke-width:4}}"
            f".cg-keep-swatch{{fill:none;stroke:{theme.success};stroke-width:4}}"
            f".cg-legend{{font:{LEGEND_FONT}px sans-serif;fill:{theme.text}}}"
            f".cg-total{{font:700 {TOTAL_FONT}px sans-serif;fill:{theme.success}}}"
            + strikes
        )
