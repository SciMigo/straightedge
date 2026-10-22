"""Arithmetic and lettering shared by the number-theory figures.

Every number these figures print is computed here from the caller's inputs.
None of them accepts a result — a residue, a totient, a running product — from
the caller, because a figure that draws whatever number it is handed is a
convincing picture of an arithmetic slip.
"""
from __future__ import annotations

import re
from html import escape
from math import gcd
from typing import Any, List, Optional, Tuple

from ...qc import Finding
from ..themes import DIAGRAM_THEMES, family

#: Born themed, like ``sequence_diagram``: the professional palette is the
#: shared one, and ``dark`` is the one a dark lecture board wants.
THEMES = family(DIAGRAM_THEMES["professional"], "dark", "high-contrast", "print-friendly")

_SUPERSCRIPT = str.maketrans("0123456789-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻")
_SUBSCRIPT = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")


def sup(value: int) -> str:
    """``117`` → ``¹¹⁷``: exponents as plain text, no typesetting needed."""
    return str(value).translate(_SUPERSCRIPT)


def sub(value: Any) -> str:
    return str(value).translate(_SUBSCRIPT)


def power(base: int, exponent: int) -> str:
    """``3^{64}`` — lettering markup for :func:`mtext`, read as ``3⁶⁴``.

    The exponent 1 is written, since the figures line rungs up by it.
    """
    return f"{base}^{{{exponent}}}"


_SCRIPT = re.compile(r"([\^_])\{([^{}]*)\}")


def plain(value: str) -> str:
    """Lettering markup as plain Unicode: for titles, tooltips and measuring."""
    return _SCRIPT.sub(lambda m: (sup(m.group(2)) if m.group(1) == "^" else sub(m.group(2))), value)


def mtext(x: float, y: float, value: str, **attrs: Any) -> str:
    """An SVG ``<text>`` whose ``^{…}`` / ``_{…}`` runs are raised or lowered tspans.

    Unicode superscript digits come from two different blocks — ¹²³ from
    Latin-1, ⁴…⁹ from Superscripts and Subscripts — and most faces draw them
    at different sizes and heights, so ``3⁶⁴`` reads as a typo on a large
    slide. A shifted, smaller tspan of ordinary digits is uniform in any face.
    """
    attr = " ".join(f'{k.replace("_", "-")}="{escape(str(v))}"' for k, v in attrs.items())
    out: List[str] = []
    last = 0
    for m in _SCRIPT.finditer(value):
        out.append(escape(value[last:m.start()]))
        shift = "super" if m.group(1) == "^" else "sub"
        out.append(f'<tspan baseline-shift="{shift}" font-size="62%">{escape(m.group(2))}</tspan>')
        last = m.end()
    out.append(escape(value[last:]))
    return f'<text x="{x}" y="{y}" {attr}>{"".join(out)}</text>'


def is_prime(n: int) -> bool:
    if n < 2:
        return False
    k = 2
    while k * k <= n:
        if n % k == 0:
            return False
        k += 1
    return True


def prime_factors(n: int) -> List[int]:
    out: List[int] = []
    k, rest = 2, n
    while k * k <= rest:
        if rest % k == 0:
            out.append(k)
            while rest % k == 0:
                rest //= k
        k += 1
    if rest > 1:
        out.append(rest)
    return out


def phi(n: int) -> int:
    return sum(1 for k in range(1, n + 1) if gcd(k, n) == 1)


def as_int(params: dict, name: str, findings: List[Finding], *, low: int,
           high: Optional[int] = None, required: bool = True) -> Optional[int]:
    """An integer parameter in ``[low, high]``, or a finding saying why not.

    Booleans are refused (``True`` is an int in Python and 1 in arithmetic, and
    nobody means it), and so is a float with a fractional part: a figure about
    divisibility must not round its input.
    """
    raw = params.get(name)
    if raw is None:
        if required:
            findings.append(Finding("number_input", "error", f"{name} is required"))
        return None
    value: Optional[int] = None
    if isinstance(raw, bool):
        value = None
    elif isinstance(raw, int):
        value = raw
    elif isinstance(raw, float) and raw.is_integer():
        value = int(raw)
    elif isinstance(raw, str) and raw.strip().lstrip("-").isdigit():
        value = int(raw.strip())
    if value is None:
        findings.append(Finding("number_input", "error", f"{name} = {raw!r} is not an integer",
                                label=str(raw)))
        return None
    if value < low or (high is not None and value > high):
        bound = f"between {low} and {high}" if high is not None else f"at least {low}"
        findings.append(Finding("number_input", "error",
                                f"{name} = {value} must be {bound}", label=str(value)))
        return None
    return value


def ladder(base: int, top: int, modulus: int) -> List[Tuple[int, int, int, int]]:
    """The rungs ``base^(2^k) mod modulus`` for every ``2^k <= top``.

    Each row is ``(exponent, previous_residue, raw_square, residue)``; the first
    rung has no square, so its ``previous_residue`` is the base itself and its
    ``raw_square`` is the base. Every residue is checked against ``pow``.
    """
    rows: List[Tuple[int, int, int, int]] = []
    exponent, residue = 1, base % modulus
    rows.append((1, base, base, residue))
    while exponent * 2 <= top:
        raw = residue * residue
        prev, residue = residue, raw % modulus
        exponent *= 2
        assert residue == pow(base, exponent, modulus)
        rows.append((exponent, prev, raw, residue))
    return rows


def set_powers(n: int) -> List[int]:
    """The powers of two that sum to ``n``, smallest first."""
    return [1 << k for k in range(n.bit_length()) if n >> k & 1]
