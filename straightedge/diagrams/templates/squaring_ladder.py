"""Squaring ladder: a, a², a⁴, a⁸, … each reduced mod m before the next square.

The picture behind fast modular exponentiation. Each rung is the square of the
*remainder* below it, never of the full power, so no number on the ladder is
ever bigger than ``(m − 1)²`` — and that is what the arrows show: the residue a
rung ends on is the number the next rung squares.

image_hint usage::

    {"type": "squaring_ladder", "params": {
        "base": 3, "modulus": 19, "n": 117, "select": true,
        "theme": "dark", "reveal": [1, 1, 2, 2, 3, 3, 4, 4]}}

``n`` is the exponent the ladder is climbed for: it has a rung for every power
of two up to ``n`` (3¹ … 3⁶⁴ for 117). ``select: true`` marks the rungs the
binary digits of ``n`` pick out and writes the expansion under the ladder.
``columns`` sets the rungs per row (default: one row up to five rungs, two rows
beyond); ``columns`` at or above the rung count draws a single row, for a wide,
short slot. ``show_title: false`` drops the title line.

Natural steps, in order: one per rung (``rung_1``, ``rung_2``, ``rung_4``, …),
then ``select`` when it is on. See ``docs/staged-reveal.md`` for ``reveal`` and
``upto``.

Every residue is computed here and checked against ``pow``; nothing numerical is
taken from the caller.
"""
from __future__ import annotations

from typing import Any, Dict, List

from ...qc import Finding
from ..registry import register
from ..renderer import defs, line, path, rect, style, svg_document, text, text_width, titled_group
from ..staging import Stager, reveal_findings
from ..themes import DiagramTheme, resolve_theme
from ._modular import THEMES, as_int, ladder, mtext, plain, power, set_powers

MAX_RUNGS = 8           # 2⁷ = 128: past eight cards the ladder is no longer legible
MARGIN = 28
TITLE_FONT = 32
HEAD_FONT = 40
CALC_FONT = 30
RESIDUE_FONT = 54
FOOT_FONT = 32
CARD_MIN_W = 200
CARD_H = 236
CARD_PAD = 24
GAP = 64
ROW_GAP = 70            # between two rows of cards, room for the turn-around arrow
WRAP_AT = 5             # by default, more rungs than this go on two rows

def _findings(params: Dict[str, Any]) -> List[Finding]:
    found: List[Finding] = []
    as_int(params, "base", found, low=1, high=10**6)
    as_int(params, "modulus", found, low=2, high=10**6)
    as_int(params, "n", found, low=1, high=(1 << MAX_RUNGS) - 1)
    as_int(params, "columns", found, low=1, high=64, required=False)
    if found:
        return found
    return reveal_findings(params, steps(params))


def steps(params: Dict[str, Any]) -> List[str]:
    """The figure's natural steps for these params, in drawing order."""
    try:
        n = int(params.get("n"))
    except (TypeError, ValueError):
        return []
    if n < 1:
        return []
    out = [f"rung_{1 << k}" for k in range(n.bit_length())]
    if params.get("select"):
        out.append("select")
    return out


@register("squaring_ladder")
class SquaringLadderTemplate:
    """A chain of squares, each reduced mod m and fed to the next."""

    motion = "none"
    themes = THEMES
    checks = ["every residue is computed and checked against pow",
              "the reveal plan has one stage per natural step, in order"]

    def refusal_findings(self, params: Dict[str, Any]) -> List[Finding]:
        return _findings(params or {})

    def natural_steps(self, params: Dict[str, Any]) -> List[str]:
        return steps(params or {})

    def render(self, params: Dict[str, Any]) -> str:
        params = params or {}
        theme = resolve_theme(params.get("theme", "professional"), THEMES)
        title = str(params.get("title", "") or "").strip()
        show_title = bool(params.get("show_title", True))
        columns = int(params.get("columns")) if params.get("columns") is not None else 0
        select = bool(params.get("select", False))
        reveal = params.get("reveal") or []
        if _findings(params):
            return ""
        base, modulus, n = int(params.get("base")), int(params.get("modulus")), int(params.get("n"))
        upto = int(params.get("upto")) if params.get("upto") is not None else None
        stager = Stager({"reveal": reveal, "upto": upto}, steps(params))
        rungs = ladder(base, n, modulus)
        chosen = set(set_powers(n)) if select else set()
        if not title:
            title = f"Powers of {base} mod {modulus}: each rung squares the remainder below it"
        if not show_title:
            title = ""

        calcs = []
        for exponent, prev, raw, residue in rungs:
            if exponent == 1:
                calcs.append(f"{base} mod {modulus}" if base >= modulus else f"{base}^{{1}} = {base}")
            else:
                calcs.append(f"{prev}^{{2}} = {raw}")
        card_w = max(CARD_MIN_W,
                     *(text_width(plain(c), CALC_FONT, safe=True) + 2 * CARD_PAD for c in calcs),
                     *(text_width(f"≡ {r[3]}", RESIDUE_FONT, bold=True, safe=True) + 2 * CARD_PAD
                       for r in rungs))
        count = len(rungs)
        if columns:
            per_row = min(columns, count)       # columns >= rungs: one row
        else:
            per_row = count if count <= WRAP_AT else (count + 1) // 2
        rows = (count + per_row - 1) // per_row
        row_w = per_row * card_w + (per_row - 1) * GAP
        foot = ""
        if select:
            picked = [power(base, e) for e in sorted(chosen, reverse=True)]
            foot = f"{n} = {format(n, 'b')}_{{2}}  picks  {',  '.join(picked)}"
        width = max(row_w, text_width(title, TITLE_FONT, bold=True, safe=True),
                    text_width(plain(foot), FOOT_FONT, bold=True, safe=True)) + 2 * MARGIN
        x0 = (width - row_w) / 2
        top = MARGIN + TITLE_FONT + 30 if title else MARGIN + 8
        cards_h = rows * CARD_H + (rows - 1) * ROW_GAP
        height = top + cards_h + (FOOT_FONT + 48 if foot else 0) + MARGIN

        def place(i: int) -> tuple:
            return x0 + (i % per_row) * (card_w + GAP), top + (i // per_row) * (CARD_H + ROW_GAP)

        parts: List[str] = [style(self._css(theme)), defs(self._marker(theme)),
                            rect(0, 0, round(width), round(height), **{"class": "sl-background"})]
        if title:
            parts.append(text(width / 2, MARGIN + TITLE_FONT, title,
                              **{"class": "sl-title", "text-anchor": "middle"}))
        for i, ((exponent, prev, raw, residue), calc) in enumerate(zip(rungs, calcs)):
            x, y = place(i)
            cx = x + card_w / 2
            card = [rect(x, y, card_w, CARD_H, rx=theme.radius + 4, **{"class": "sl-card"}),
                    mtext(cx, y + 54, power(base, exponent),
                          **{"class": "sl-head", "text-anchor": "middle"}),
                    mtext(cx, y + 118, calc, **{"class": "sl-calc", "text-anchor": "middle"}),
                    text(cx, y + 196, f"≡ {residue}", **{"class": "sl-residue", "text-anchor": "middle"})]
            if i > 0:
                # The remainder the last rung ended on is the number this one squares.
                px, py = place(i - 1)
                if py == y:
                    link = line(px + card_w + 6, y + 178, x - 8, y + 108,
                                **{"class": "sl-link", "marker-end": "url(#sl-arrow)"})
                else:
                    turn = py + CARD_H + ROW_GAP / 2
                    link = path(f"M{px + card_w / 2},{py + CARD_H + 4} V{turn} H{cx} V{y - 8}",
                                **{"class": "sl-link", "marker-end": "url(#sl-arrow)"})
                card.insert(0, link)
            name = f"{plain(power(base, exponent))} ≡ {residue} (mod {modulus})"
            parts.append(stager.wrap(i, titled_group(name, card)))

        if select:
            marks: List[str] = []
            for i, (exponent, *_rest) in enumerate(rungs):
                if exponent in chosen:
                    x, y = place(i)
                    marks.append(rect(x - 7, y - 7, card_w + 14, CARD_H + 14, rx=theme.radius + 8,
                                      **{"class": "sl-chosen"}))
            marks.append(mtext(width / 2, top + cards_h + 34 + FOOT_FONT, foot,
                               **{"class": "sl-foot", "text-anchor": "middle"}))
            parts.append(stager.wrap(len(rungs), titled_group(plain(foot), marks)))

        return svg_document("\n".join(p for p in parts if p), width=round(width), height=round(height),
                            class_name="diagram squaring-ladder")

    @staticmethod
    def _marker(theme: DiagramTheme) -> str:
        return ('<marker id="sl-arrow" markerWidth="14" markerHeight="14" refX="11" refY="6" '
                'orient="auto" markerUnits="userSpaceOnUse">'
                f'<path d="M0,0 L12,6 L0,12 Z" fill="{theme.accent}"/></marker>')

    @staticmethod
    def _css(theme: DiagramTheme) -> str:
        return (
            f".sl-background{{fill:{theme.background or theme.surface_alt}}}"
            f".sl-title{{font:600 {TITLE_FONT}px sans-serif;fill:{theme.text}}}"
            f".sl-card{{fill:{theme.surface};stroke:{theme.rule};stroke-width:2}}"
            f".sl-head{{font:700 {HEAD_FONT}px sans-serif;fill:{theme.warning}}}"
            f".sl-calc{{font:{CALC_FONT}px sans-serif;fill:{theme.muted}}}"
            f".sl-residue{{font:700 {RESIDUE_FONT}px sans-serif;fill:{theme.text}}}"
            f".sl-link{{stroke:{theme.accent};stroke-width:3;fill:none}}"
            f".sl-chosen{{fill:none;stroke:{theme.success};stroke-width:5}}"
            f".sl-foot{{font:600 {FOOT_FONT}px sans-serif;fill:{theme.success}}}"
        )
