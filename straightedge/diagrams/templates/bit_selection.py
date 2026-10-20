"""Bit selection: the binary digits of n pick which powers of two — and which rungs — to use.

Fast exponentiation multiplies only the squares that the 1-bits of the exponent
select. This figure makes the selection visible instead of asking a reader to
parse one long equation: the powers of two across the top, the binary digit
under each, the set bits lit, and the chosen powers combining underneath —

    117 = 64 + 32 + 16 + 4 + 1
    3¹¹⁷ = 3⁶⁴ · 3³² · 3¹⁶ · 3⁴ · 3¹

With a ``modulus`` it also writes each chosen rung's residue ``base^(2^k) mod m``
under its bit and multiplies them, smallest first, reducing after every step:
for 3¹¹⁷ mod 19 that is 3 → 15 → 8 → 13 → 18.

image_hint usage::

    {"type": "bit_selection", "params": {
        "n": 117, "base": 3, "modulus": 19, "theme": "dark",
        "reveal": [1, 2, 2, 3, 4, 4, 4, 4]}}

``show_title: false`` drops the title line, for a figure that must stay short.

Natural steps, in order: ``bits``, ``sum``, then ``powers`` with a ``base``, then
``residues`` and one ``multiply_<k>`` per multiplication with a ``modulus``. See
``docs/staged-reveal.md`` for ``reveal`` and ``upto``.

Every number is computed here — the bits, the sum, the residues and the running
product, each checked against ``pow``. ``modulus`` needs a ``base``.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ...qc import Finding
from ..registry import register
from ..renderer import rect, style, svg_document, text, text_width, titled_group
from ..staging import Stager, reveal_findings
from ..themes import DiagramTheme, resolve_theme
from ._modular import THEMES, as_int, ladder, mtext, plain, power, set_powers

MAX_BITS = 12           # n < 4096: twelve columns is what a slide can hold legibly
MARGIN = 28
TITLE_FONT = 30
LABEL_FONT = 26
POW_FONT = 32
BIT_FONT = 44
RUNG_FONT = 30
LINE_FONT = 34
CHAIN_FONT = 30
CELL_MIN = 104
BIT_BOX = 78
ROW_GAP = 18
LINE_GAP = 22
CHAIN_MAX_W = 1400


def _findings(params: Dict[str, Any]) -> List[Finding]:
    found: List[Finding] = []
    as_int(params, "n", found, low=1, high=(1 << MAX_BITS) - 1)
    base = as_int(params, "base", found, low=1, high=10**6, required=False)
    modulus = as_int(params, "modulus", found, low=2, high=10**6, required=False)
    if modulus is not None and base is None and params.get("base") is None:
        found.append(Finding("number_input", "error",
                             "a modulus needs a base: there are no rungs to reduce without one"))
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
    out = ["bits", "sum"]
    if params.get("base") is not None:
        out.append("powers")
        if params.get("modulus") is not None:
            out.append("residues")
            out.extend(f"multiply_{k}" for k in range(1, bin(n).count("1")))
    return out


def _chain_rows(chips: List[str], arrow_w: float) -> List[List[int]]:
    """Wrap the running-product chips onto as few rows as fit ``CHAIN_MAX_W``."""
    rows: List[List[int]] = [[]]
    used = 0.0
    for i, chip in enumerate(chips):
        w = text_width(chip, CHAIN_FONT, safe=True) + (arrow_w if rows[-1] else 0)
        if rows[-1] and used + w > CHAIN_MAX_W:
            rows.append([])
            used = 0.0
            w = text_width(chip, CHAIN_FONT, safe=True)
        rows[-1].append(i)
        used += w
    return rows


@register("bit_selection")
class BitSelectionTemplate:
    """The binary digits of n under the powers of two, and the powers they select."""

    motion = "none"
    themes = THEMES
    checks = ["bits, sum, residues and running product are computed and checked against pow",
              "a modulus is only drawn with a base",
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
        reveal = params.get("reveal") or []
        if _findings(params):
            return ""
        n = int(params.get("n"))
        base: Optional[int] = int(params.get("base")) if params.get("base") is not None else None
        modulus: Optional[int] = (int(params.get("modulus")) if params.get("modulus") is not None
                                  else None)
        upto = int(params.get("upto")) if params.get("upto") is not None else None
        stager = Stager({"reveal": reveal, "upto": upto}, steps(params))
        order = steps(params)

        bits = n.bit_length()
        exps = [1 << k for k in range(bits - 1, -1, -1)]          # high to low, as n is read
        chosen = set(set_powers(n))
        residues: Dict[int, int] = {}
        if base is not None and modulus is not None:
            residues = {e: r for e, _p, _raw, r in ladder(base, n, modulus)}

        if not title:
            if base is None:
                title = f"{n} in binary: each 1 picks a power of two"
            elif modulus is None:
                title = f"The 1-bits of {n} pick the powers of {base} to multiply"
            else:
                title = f"{power(base, n)} mod {modulus}: multiply only the rungs the 1-bits pick"

        labels = ["power of 2", "bit"]
        if base is not None:
            labels.append("rung")
        if modulus is not None:
            labels.append(f"mod {modulus}")
        label_w = max(text_width(s, LABEL_FONT, safe=True) for s in labels) + 24
        cell = max(CELL_MIN, BIT_BOX + 20,
                   *(text_width(str(e), POW_FONT, safe=True) + 20 for e in exps),
                   *((text_width(plain(power(base, e)), RUNG_FONT, bold=True, safe=True) + 20)
                     for e in exps if base is not None),
                   *((text_width(f"≡ {r}", RUNG_FONT, bold=True, safe=True) + 20)
                     for r in residues.values()))
        grid_w = label_w + bits * cell

        picked_high = [e for e in exps if e in chosen]
        sum_line = f"{n} = " + " + ".join(str(e) for e in picked_high)
        lines = [sum_line]
        if base is not None:
            lines.append(f"{power(base, n)} = " + " · ".join(power(base, e) for e in picked_high))
        if modulus is not None:
            lines.append("≡ " + " · ".join(str(residues[e]) for e in picked_high)
                         + f"   (mod {modulus})")

        chips: List[str] = []
        running: List[int] = []
        if modulus is not None:
            low_first = sorted(chosen)
            acc = residues[low_first[0]]
            chips.append(str(acc))
            running.append(acc)
            for e in low_first[1:]:
                raw = acc * residues[e]
                acc = raw % modulus
                chips.append(f"× {residues[e]} = {raw}" + (f" ≡ {acc}" if raw != acc else ""))
                running.append(acc)
            assert acc == pow(base, n, modulus)
        arrow_w = 44
        chain_rows = _chain_rows(chips, arrow_w) if chips else []
        result = f"{power(base, n)} ≡ {running[-1]}   (mod {modulus})" if chips else ""

        if not show_title:
            title = ""
        widths = [grid_w, text_width(plain(title), TITLE_FONT, bold=True, safe=True),
                  *(text_width(plain(s), LINE_FONT, safe=True) for s in lines),
                  text_width(plain(result), LINE_FONT, bold=True, safe=True)]
        for row in chain_rows:
            widths.append(sum(text_width(chips[i], CHAIN_FONT, safe=True) for i in row)
                          + arrow_w * (len(row) - 1))
        width = max(widths) + 2 * MARGIN
        gx = (width - grid_w) / 2 + label_w

        parts: List[str] = [style(self._css(theme)),
                            rect(0, 0, 0, 0, **{"class": "bs-background"})]   # sized below
        if title:
            y = MARGIN + TITLE_FONT
            parts.append(mtext(width / 2, y, title, **{"class": "bs-title", "text-anchor": "middle"}))
            y += 34
        else:
            y = MARGIN - 6

        def col_x(i: int) -> float:
            return gx + i * cell + cell / 2

        # Scaffold: the powers of two, and an empty box for every digit.
        pow_y = y + POW_FONT
        parts.append(text(gx - 16, pow_y, labels[0], **{"class": "bs-label", "text-anchor": "end"}))
        for i, e in enumerate(exps):
            parts.append(text(col_x(i), pow_y, str(e), **{"class": "bs-pow", "text-anchor": "middle"}))
        box_y = pow_y + ROW_GAP
        parts.append(text(gx - 16, box_y + BIT_BOX / 2 + 9, labels[1],
                          **{"class": "bs-label", "text-anchor": "end"}))
        for i in range(bits):
            parts.append(rect(col_x(i) - BIT_BOX / 2, box_y, BIT_BOX, BIT_BOX,
                              rx=theme.radius + 2, **{"class": "bs-box"}))
        y = box_y + BIT_BOX

        # Step: the digits, the set ones lit.
        digits: List[str] = []
        for i, e in enumerate(exps):
            on = e in chosen
            if on:
                digits.append(rect(col_x(i) - BIT_BOX / 2, box_y, BIT_BOX, BIT_BOX,
                                   rx=theme.radius + 2, **{"class": "bs-box-on"}))
            digits.append(text(col_x(i), box_y + BIT_BOX / 2 + 15, "1" if on else "0",
                               **{"class": "bs-bit-on" if on else "bs-bit-off",
                                  "text-anchor": "middle"}))
        parts.append(stager.wrap(order.index("bits"),
                                 titled_group(f"{n} = {format(n, 'b')} in binary", digits)))

        rung_y = res_y = None
        if base is not None:
            rung_y = y + ROW_GAP + RUNG_FONT + 6
            y = rung_y
        if modulus is not None:
            res_y = y + ROW_GAP + RUNG_FONT + 4
            y = res_y
        y += LINE_GAP

        line_y = [y + LINE_FONT + i * (LINE_FONT + LINE_GAP) for i in range(len(lines))]
        y = line_y[-1]
        parts.append(stager.wrap(order.index("sum"), text(width / 2, line_y[0], lines[0],
                                                          **{"class": "bs-line",
                                                             "text-anchor": "middle"})))
        if base is not None:
            rung = [text(gx - 16, rung_y, labels[2], **{"class": "bs-label", "text-anchor": "end"})]
            rung += [mtext(col_x(i), rung_y, power(base, e), **{"class": "bs-rung", "text-anchor": "middle"})
                     for i, e in enumerate(exps) if e in chosen]
            rung.append(mtext(width / 2, line_y[1], lines[1], **{"class": "bs-line", "text-anchor": "middle"}))
            parts.append(stager.wrap(order.index("powers"), titled_group(plain(lines[1]), rung)))
        if modulus is not None:
            res = [text(gx - 16, res_y, labels[3], **{"class": "bs-label", "text-anchor": "end"})]
            res += [text(col_x(i), res_y, f"≡ {residues[e]}", **{"class": "bs-res", "text-anchor": "middle"})
                    for i, e in enumerate(exps) if e in chosen]
            res.append(text(width / 2, line_y[2], lines[2], **{"class": "bs-line", "text-anchor": "middle"}))
            # The chain starts from the smallest selected rung.
            pieces = self._chain(chips, chain_rows, arrow_w, width, y + LINE_GAP)
            res.append(pieces[0])
            if len(chips) == 1:
                res.append(mtext(width / 2, pieces[-1], result,
                                **{"class": "bs-result", "text-anchor": "middle"}))
            parts.append(stager.wrap(order.index("residues"), titled_group(lines[2], res)))
            for k in range(1, len(chips)):
                step = [pieces[k]]
                if k == len(chips) - 1:
                    step.append(mtext(width / 2, pieces[-1], result,
                                     **{"class": "bs-result", "text-anchor": "middle"}))
                parts.append(stager.wrap(order.index(f"multiply_{k}"),
                                         titled_group(f"running product {running[k]}", step)))
            y = pieces[-1]

        height = y + MARGIN + 6
        parts[1] = rect(0, 0, round(width), round(height), **{"class": "bs-background"})
        return svg_document("\n".join(p for p in parts if p), width=round(width),
                            height=round(height), class_name="diagram bit-selection")

    @staticmethod
    def _chain(chips: List[str], rows: List[List[int]], arrow_w: float, width: float,
               top: float) -> List[Any]:
        """One text group per chip (arrow included), then the y the result goes at."""
        out: List[Any] = [""] * len(chips)
        y = top
        for row in rows:
            y += CHAIN_FONT + 14
            row_w = (sum(text_width(chips[i], CHAIN_FONT, safe=True) for i in row)
                     + arrow_w * (len(row) - 1))
            x = (width - row_w) / 2
            for j, i in enumerate(row):
                piece = ""
                if j > 0:
                    piece += text(x + arrow_w / 2, y, "→", **{"class": "bs-arrow",
                                                               "text-anchor": "middle"})
                    x += arrow_w
                cls = "bs-chip-start" if i == 0 else "bs-chip"
                piece += text(x, y, chips[i], **{"class": cls})
                x += text_width(chips[i], CHAIN_FONT, safe=True)
                out[i] = piece
        out.append(y + LINE_FONT + LINE_GAP + 8)
        return out

    @staticmethod
    def _css(theme: DiagramTheme) -> str:
        return (
            f".bs-background{{fill:{theme.background or theme.surface_alt}}}"
            f".bs-title{{font:600 {TITLE_FONT}px sans-serif;fill:{theme.text}}}"
            f".bs-label{{font:{LABEL_FONT}px sans-serif;fill:{theme.muted}}}"
            f".bs-pow{{font:600 {POW_FONT}px sans-serif;fill:{theme.muted}}}"
            f".bs-box{{fill:{theme.surface};stroke:{theme.rule};stroke-width:2}}"
            f".bs-box-on{{fill:{theme.success_soft};stroke:{theme.success};stroke-width:4}}"
            f".bs-bit-on{{font:700 {BIT_FONT}px sans-serif;fill:{theme.success}}}"
            f".bs-bit-off{{font:{BIT_FONT}px sans-serif;fill:{theme.muted}}}"
            f".bs-rung{{font:700 {RUNG_FONT}px sans-serif;fill:{theme.warning}}}"
            f".bs-res{{font:700 {RUNG_FONT}px sans-serif;fill:{theme.text}}}"
            f".bs-line{{font:{LINE_FONT}px sans-serif;fill:{theme.text}}}"
            f".bs-arrow{{font:700 {CHAIN_FONT + 4}px sans-serif;fill:{theme.accent}}}"
            f".bs-chip{{font:{CHAIN_FONT}px sans-serif;fill:{theme.text}}}"
            f".bs-chip-start{{font:700 {CHAIN_FONT}px sans-serif;fill:{theme.text}}}"
            f".bs-result{{font:700 {LINE_FONT}px sans-serif;fill:{theme.success}}}"
        )
