"""SVG rendering utilities for diagram templates."""

from __future__ import annotations

from html import escape
from typing import Any, Dict, List, Optional


def _attrs_to_str(attrs: Dict[str, Any]) -> str:
    """Convert attribute dict to HTML attribute string."""
    parts = []
    for key, value in attrs.items():
        # Convert underscores to hyphens for CSS-style attributes
        attr_name = key.replace("_", "-")
        parts.append(f'{attr_name}="{escape(str(value))}"')
    return " ".join(parts)


def svg_document(
    content: str,
    width: int = 400,
    height: int = 300,
    viewbox: Optional[str] = None,
    class_name: str = "diagram",
) -> str:
    """Wrap content in an SVG document.

    Args:
        content: Inner SVG elements
        width: SVG width in pixels
        height: SVG height in pixels
        viewbox: Custom viewBox string (defaults to "0 0 width height")
        class_name: CSS class for the SVG element

    Returns:
        Complete SVG document string
    """
    vb = viewbox or f"0 0 {width} {height}"
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="{vb}" class="{class_name}">
{content}
</svg>'''


def circle(cx: float, cy: float, r: float, **attrs: Any) -> str:
    """Create an SVG circle element."""
    attr_str = _attrs_to_str(attrs)
    return f'<circle cx="{cx}" cy="{cy}" r="{r}" {attr_str}/>'


def rect(x: float, y: float, width: float, height: float, **attrs: Any) -> str:
    """Create an SVG rectangle element."""
    attr_str = _attrs_to_str(attrs)
    return f'<rect x="{x}" y="{y}" width="{width}" height="{height}" {attr_str}/>'


def line(x1: float, y1: float, x2: float, y2: float, **attrs: Any) -> str:
    """Create an SVG line element."""
    attr_str = _attrs_to_str(attrs)
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" {attr_str}/>'


def polyline(points: List[tuple[float, float]], **attrs: Any) -> str:
    """Create an SVG polyline element."""
    points_str = " ".join(f"{x},{y}" for x, y in points)
    attr_str = _attrs_to_str(attrs)
    return f'<polyline points="{points_str}" {attr_str}/>'


def path(d: str, **attrs: Any) -> str:
    """Create an SVG path element."""
    attr_str = _attrs_to_str(attrs)
    return f'<path d="{d}" {attr_str}/>'


def text(x: float, y: float, content: str, **attrs: Any) -> str:
    """Create an SVG text element."""
    attr_str = _attrs_to_str(attrs)
    return f'<text x="{x}" y="{y}" {attr_str}>{escape(content)}</text>'


def group(content: str, **attrs: Any) -> str:
    """Create an SVG group element."""
    attr_str = _attrs_to_str(attrs)
    if attr_str:
        return f'<g {attr_str}>{content}</g>'
    return f'<g>{content}</g>'


def defs(content: str) -> str:
    """Create an SVG defs element for reusable definitions."""
    return f'<defs>{content}</defs>'


def use(href: str, x: float = 0, y: float = 0, **attrs: Any) -> str:
    """Create an SVG use element to reference a definition."""
    attr_str = _attrs_to_str(attrs)
    return f'<use href="#{href}" x="{x}" y="{y}" {attr_str}/>'


def style(css: str) -> str:
    """Create an embedded SVG style element."""
    return f'<style>{css}</style>'


# Common style definitions
DEFAULT_STYLES = """
.diagram-point { fill: #666; }
.diagram-point-visible { fill: #4CAF50; }
.diagram-point-hidden { fill: #ccc; }
.diagram-point-origin { fill: #2196F3; }
.diagram-point-highlight { fill: #FF9800; }
.diagram-ray { stroke: #999; stroke-width: 1; stroke-dasharray: 4,2; fill: none; }
.diagram-axis { stroke: #333; stroke-width: 2; fill: none; }
.diagram-grid { stroke: #eee; stroke-width: 1; fill: none; }
.diagram-label { font-size: 12px; font-family: sans-serif; fill: #333; }
.diagram-label-small { font-size: 10px; font-family: sans-serif; fill: #666; }
"""


def wrap_units(s: str, max_units: float, max_lines: int = 2,
               mark_truncation: bool = True) -> List[str]:
    """Greedy wrap counting CJK as full-width (1.0) and Latin as ~half (0.5).

    Breaks at a space when the overflowing line has one, so Latin wraps on word
    boundaries ("thousand" / "joules") instead of mid-word ("thousand j" /
    "oules"). CJK has no spaces, so it keeps the character-greedy behaviour.

    Shared because this bug has now shipped twice — flow_diagram wrapped English
    mid-word, and so did comparison. One wrapper, one fix.

    Content past ``max_lines`` is dropped — there is nowhere to draw it — but the
    last kept line is marked with an ellipsis so the loss is *visible*. It used
    to be silent: an 82-character caption came back as 37 characters that read
    like the whole thing, and nothing downstream could tell that 44 characters
    had gone. Pass ``mark_truncation=False`` for a caller that measures the
    lines itself and would rather have the raw text.
    """
    if not s:
        return []
    lines: List[str] = []
    cur, width = "", 0.0
    for ch in s:
        w = 1.0 if ord(ch) > 0x2E7F else 0.5
        if width + w > max_units and cur:
            head, sep, tail = cur.rpartition(" ")
            if sep and head.strip():
                lines.append(head.rstrip())
                cur = tail + ch
                width = sum(1.0 if ord(c) > 0x2E7F else 0.5 for c in cur)
            else:
                lines.append(cur)
                cur, width = ch, w
        else:
            cur += ch
            width += w
    if cur.strip():
        lines.append(cur.strip())
    if len(lines) <= max_lines:
        return lines
    kept = lines[:max_lines]
    if mark_truncation and kept:
        last = kept[-1].rstrip()
        # Trim to leave room for the mark rather than pushing past `max_units`,
        # which is the budget the caller sized its box from.
        while last and sum(1.0 if ord(c) > 0x2E7F else 0.5
                           for c in last + ELLIPSIS) > max_units:
            last = last[:-1].rstrip()
        kept[-1] = last + ELLIPSIS
    return kept


# ---------------------------------------------------------------------------
# Text measurement
#
# A figure that cannot measure its own text cannot know whether a label fits,
# and every template that guessed grew its own guess: five of them held a
# private width factor, two hard-sliced at a character count, and one measured
# CJK as if it were Latin. The numbers below are the one place to change.
#
# Latin widths are measured, per character, by rasterising each glyph against a
# sentinel and taking the advance.
#
# CJK is 1.0 by definition rather than by measurement — ideographs are drawn on
# a square em. It is deliberately *not* fitted, because fitting it requires a
# host that has the font: where `Noto Sans SC` is absent a rasteriser falls back
# to a Latin face and reports a width belonging to the fallback rather than to
# the font the CSS asks for. Measuring that would bake a substitution artifact
# into the library.
# ---------------------------------------------------------------------------

# Advance widths in em, measured per character rather than averaged. A single
# factor cannot describe a proportional face: "Ken Thompson" and "Chief of
# Staff" are both 12-14 characters and differ by 25% in width, so an averaged
# estimate under-measured the first by 14% and drew its role label on top of its
# name. The tables below were read off a rasteriser and agree with the published
# Helvetica metrics (0.556 digits, 0.278 space, 0.944 W), which is the fallback
# every template's font stack lands on when 'Noto Sans SC' is absent.
_ADV_REG_SPEC = {
    0.19: "'", 0.22: "ijl", 0.26: "|", 0.28: " !,./:;I[\\]ft",
    0.33: "()-`r{}", 0.36: '"', 0.39: "*", 0.47: "^", 0.50: "Jcksvxyz",
    0.56: "#$0123456789?L_abdeghnopqu", 0.58: "+<=>~", 0.61: "FTZ",
    0.67: "&ABEKPSVXY", 0.72: "CDHNRUw", 0.78: "GOQ", 0.83: "Mm",
    0.89: "%", 0.94: "W", 1.02: "@",
}
_ADV_BOLD_SPEC = {
    0.24: "'", 0.28: " ,./I\\ijl|", 0.33: "!()-:;[]`ft", 0.39: "*r{}",
    0.47: '"', 0.50: "z", 0.56: "#$0123456789J_aceksvxy", 0.58: "+<=>^~",
    0.61: "?FLTZbdghnopqu", 0.67: "EPSVXY", 0.72: "&ABCDHKNRU",
    0.78: "GOQw", 0.83: "M", 0.89: "%m", 0.94: "W", 0.98: "@",
}


def _expand(spec: Dict[float, str]) -> Dict[str, float]:
    return {ch: w for w, chars in spec.items() for ch in chars}


_ADV_REG = _expand(_ADV_REG_SPEC)
_ADV_BOLD = _expand(_ADV_BOLD_SPEC)

#: Fallback for a Latin-range character with no measured width of its own.
LATIN_EM = 0.56
LATIN_EM_BOLD = 0.60
CJK_EM = 1.0

#: Codepoints above this are treated as full-width. Covers the CJK blocks, kana,
#: and the full-width forms; below it is Latin, Greek, Cyrillic and punctuation.
_WIDE_ABOVE = 0x2E7F

ELLIPSIS = "\u2026"

#: Headroom for the face actually resolving wider than the one measured. The
#: tables describe Helvetica metrics, which is what `Helvetica,Arial,sans-serif`
#: lands on; every template asks for `'Noto Sans SC'` first, and where that is
#: absent fontconfig substitutes a CJK face whose Latin glyphs measure ~15%
#: wider. A viewer's substitution cannot be known from here, so a fit decision
#: carries the margin: over-measuring costs whitespace, under-measuring puts one
#: label on top of another.
WIDTH_SAFETY = 1.18


def char_em(ch: str, bold: bool = False) -> float:
    """Advance width of one character, in em."""
    if ord(ch) > _WIDE_ABOVE:
        return CJK_EM
    table = _ADV_BOLD if bold else _ADV_REG
    return table.get(ch, LATIN_EM_BOLD if bold else LATIN_EM)


def text_width(value: str, font_px: float, bold: bool = False,
               safe: bool = False) -> float:
    """Approximate rendered advance width of ``value`` in pixels.

    Per-character for Latin and full-width for CJK, so a Chinese caption is not
    measured as though it were English and a name of capitals is not measured as
    though it were lowercase. Pass ``safe=True`` when the answer decides whether
    something *fits* --- it adds :data:`WIDTH_SAFETY` to cover the face
    resolving wider than the one these tables describe. `roadmap` measured a
    nine-character Chinese label at 57px that renders at ~103px, and then drew
    it inside a bar it overflowed — the exact defect that template exists to
    prevent.
    """
    if not value:
        return 0.0
    width = sum(char_em(ch, bold) for ch in value) * font_px
    return width * WIDTH_SAFETY if safe else width


def fit_text(
    value: str,
    max_px: float,
    font_px: float,
    bold: bool = False,
) -> str:
    """Trim ``value`` to ``max_px``, marking the cut with an ellipsis.

    Returns the string unchanged when it already fits. A cut is *visible*:
    a caption trimmed with no mark reads as the whole label, so a reader has no
    way to tell "Dr. Alexan" from someone actually called that. `wbs` sliced at
    `[:10]` and `comparison` at `[:22]`, both silently.
    """
    if not value or max_px <= 0:
        return ""
    if text_width(value, font_px, bold, safe=True) <= max_px:
        return value
    budget = max_px - text_width(ELLIPSIS, font_px, bold, safe=True)
    if budget <= 0:
        return ELLIPSIS
    out, used = "", 0.0
    for ch in value:
        w = char_em(ch, bold) * font_px * WIDTH_SAFETY
        if used + w > budget:
            break
        out += ch
        used += w
    return (out.rstrip() + ELLIPSIS) if out.strip() else ELLIPSIS
