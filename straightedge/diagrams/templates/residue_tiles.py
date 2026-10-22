"""Residue tiles: multiplying 1 … p−1 by a only reorders them mod a prime p.

The permutation at the heart of Fermat's little theorem, drawn with real
numbers. The top row is 1, 2, …, p−1; under each k sits a·k mod p; and a line
from every one of those to its place in a sorted copy shows that the second
row is the first row shuffled — nothing missing, nothing repeated. Multiplying
each row together then gives a^(p−1)·(p−1)! ≡ (p−1)!, so a^(p−1) ≡ 1.

image_hint usage::

    {"type": "residue_tiles", "params": {
        "p": 7, "a": 3, "theme": "dark",
        "reveal": [1, 1, 1, 1, 1, 1, 2, 3]}}

Natural steps, in order: ``tile_1`` … ``tile_<p-1>`` (one multiplied tile each),
``match`` (the sorted row and the lines into it), ``conclude`` (the product
line). See ``docs/staged-reveal.md`` for ``reveal`` and ``upto``.

The figure is refused — drawn blank, with a finding — when ``p`` is not prime or
``p`` divides ``a``. In either case the second row is *not* a permutation, and a
figure that drew one anyway would be teaching the theorem's conclusion without
its hypotheses.
"""
from __future__ import annotations

from typing import Any, Dict, List

from ...qc import Finding
from ..registry import register
from ..renderer import line, rect, style, svg_document, text, text_width, titled_group
from ..staging import Stager, reveal_findings
from ..themes import DiagramTheme, resolve_theme
from ._modular import THEMES, as_int, is_prime, mtext, plain, power

MAX_P = 17              # sixteen tiles: the widest row a slide holds legibly
MARGIN = 28
TITLE_FONT = 30
LABEL_FONT = 26
TILE_FONT = 36
LINE_FONT = 32
TILE = 78
GAP = 16
MATCH_DROP = 150        # vertical room for the lines from the shuffled row to the sorted one


def _findings(params: Dict[str, Any]) -> List[Finding]:
    found: List[Finding] = []
    p = as_int(params, "p", found, low=2, high=MAX_P)
    a = as_int(params, "a", found, low=1, high=10**6)
    if found:
        return found
    if not is_prime(p):
        return [Finding("number_input", "error",
                        f"p = {p} is not prime, so multiplying by a need not permute the "
                        f"residues (and Fermat's theorem does not apply)", label=str(p))]
    if a % p == 0:
        return [Finding("number_input", "error",
                        f"p = {p} divides a = {a}: every a·k is 0 mod p, which is no "
                        f"permutation of 1 … {p - 1}", label=str(a))]
    return reveal_findings(params, steps(params))


def steps(params: Dict[str, Any]) -> List[str]:
    """The figure's natural steps for these params, in drawing order."""
    try:
        p = int(params.get("p"))
    except (TypeError, ValueError):
        return []
    if p < 2:
        return []
    return [f"tile_{k}" for k in range(1, p)] + ["match", "conclude"]


@register("residue_tiles")
class ResidueTilesTemplate:
    """1 … p−1, the same tiles times a mod p, and the shuffle that relates them."""

    motion = "none"
    themes = THEMES
    checks = ["p is prime and does not divide a", "the multiplied row is checked to be a permutation",
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
        p, a = int(params.get("p")), int(params.get("a"))
        upto = int(params.get("upto")) if params.get("upto") is not None else None
        stager = Stager({"reveal": reveal, "upto": upto}, steps(params))
        ks = list(range(1, p))
        shuffled = [a * k % p for k in ks]
        assert sorted(shuffled) == ks, "multiplication by a unit must permute the residues"
        assert pow(a, p - 1, p) == 1

        if not title:
            title = f"Multiplying 1 … {p - 1} by {a} only reorders them mod {p}"
        labels = ["k", f"{a}k mod {p}", "sorted"]
        label_w = max(text_width(s, LABEL_FONT, safe=True) for s in labels) + 28
        row_w = len(ks) * TILE + (len(ks) - 1) * GAP
        fact = f"{p - 1}!"
        conclusion = (f"Multiply each row:  {power(a, p - 1)} · {fact} ≡ {fact}  (mod {p}),"
                      f"  so  {power(a, p - 1)} ≡ 1")
        width = max(label_w + row_w, text_width(title, TITLE_FONT, bold=True, safe=True),
                    text_width(plain(conclusion), LINE_FONT, safe=True)) + 2 * MARGIN
        gx = (width - (label_w + row_w)) / 2 + label_w

        def tile_x(i: int) -> float:
            return gx + i * (TILE + GAP)

        y_title = MARGIN + TITLE_FONT
        y1 = y_title + 34
        y2 = y1 + TILE + 30
        y3 = y2 + TILE + MATCH_DROP
        y_end = y3 + TILE + 30 + LINE_FONT
        height = y_end + MARGIN

        parts: List[str] = [style(self._css(theme)),
                            rect(0, 0, round(width), round(height), **{"class": "rt-background"}),
                            text(width / 2, y_title, title, **{"class": "rt-title", "text-anchor": "middle"})]

        def tile(i: int, y: float, value: int, cls: str) -> List[str]:
            return [rect(tile_x(i), y, TILE, TILE, rx=theme.radius + 2, **{"class": cls}),
                    text(tile_x(i) + TILE / 2, y + TILE / 2 + 13, str(value),
                         **{"class": "rt-num", "text-anchor": "middle"})]

        def row_label(y: float, s: str) -> str:
            return text(gx - 18, y + TILE / 2 + 9, s, **{"class": "rt-label", "text-anchor": "end"})

        scaffold = [row_label(y1, labels[0])]
        for i, k in enumerate(ks):
            scaffold += tile(i, y1, k, "rt-tile")
        parts.append(titled_group(f"1 … {p - 1}", scaffold))

        for i, (k, value) in enumerate(zip(ks, shuffled)):
            piece = tile(i, y2, value, "rt-tile-shuffled")
            if i == 0:
                piece.insert(0, row_label(y2, labels[1]))
            parts.append(stager.wrap(i, titled_group(f"{a}·{k} = {a * k} ≡ {value} (mod {p})", piece)))

        match = [row_label(y3, labels[2])]
        for i, value in enumerate(shuffled):
            j = value - 1
            match.append(line(tile_x(i) + TILE / 2, y2 + TILE + 4, tile_x(j) + TILE / 2, y3 - 4,
                              **{"class": "rt-link"}))
        for j, value in enumerate(ks):
            match += tile(j, y3, value, "rt-tile-sorted")
        parts.append(stager.wrap(len(ks), titled_group("the same residues, reordered", match)))

        parts.append(stager.wrap(len(ks) + 1, mtext(width / 2, y_end, conclusion,
                                                   **{"class": "rt-line", "text-anchor": "middle"})))
        return svg_document("\n".join(p_ for p_ in parts if p_), width=round(width), height=round(height),
                            class_name="diagram residue-tiles")

    @staticmethod
    def _css(theme: DiagramTheme) -> str:
        return (
            f".rt-background{{fill:{theme.background or theme.surface_alt}}}"
            f".rt-title{{font:600 {TITLE_FONT}px sans-serif;fill:{theme.text}}}"
            f".rt-label{{font:{LABEL_FONT}px sans-serif;fill:{theme.muted}}}"
            f".rt-tile{{fill:{theme.surface};stroke:{theme.rule};stroke-width:2}}"
            f".rt-tile-shuffled{{fill:{theme.warning_soft};stroke:{theme.warning};stroke-width:3}}"
            f".rt-tile-sorted{{fill:{theme.success_soft};stroke:{theme.success};stroke-width:3}}"
            f".rt-num{{font:700 {TILE_FONT}px sans-serif;fill:{theme.text}}}"
            f".rt-link{{stroke:{theme.accent};stroke-width:2.5;fill:none;opacity:.85}}"
            f".rt-line{{font:{LINE_FONT}px sans-serif;fill:{theme.text}}}"
        )
