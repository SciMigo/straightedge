"""Two right triangles, the second strictly smaller than the first.

The picture a descent proof needs. Fermat's right-triangle theorem argues that a
whole-number right triangle with square area manufactures a *smaller* one with
the same property, so no smallest can exist; Wikipedia's article carries the same
figure for the four-squares-in-arithmetic-progression form. Narration alone makes
a viewer hold two triangles and their three side labels in their head.

Draws each triangle to scale from its actual hypotenuse, so "smaller" is
something the viewer SEES rather than something the labels assert. The right
angle is marked on both, because "right triangle" is a hypothesis of the theorem
and not decoration.

    image_hint = {
        "type": "descent_triangles",
        "params": {
            "first":  {"legs": ["p^2-q^2", "2pq"], "hyp": "p^2+q^2", "area": "pq(p-q)(p+q)"},
            "second": {"legs": ["d-c", "d+c"], "hyp": "2a", "area": "q = b^2"},
            "note": "same property, smaller hypotenuse",
        },
    }

Labels are plain text, not LaTeX: the registry emits standalone SVG that no math
renderer post-processes, so ``p^2`` is written as ``p²`` by the caller or shown
literally. Keep them short — this is a figure, not a derivation.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping

from ..registry import register
from ..renderer import group, path, rect, style, svg_document, text

W, H = 600, 310
# Theme tokens with light-theme fallbacks. Hardcoding #1f2933 here painted the
# side labels near-black on dark_academic's #0b1622 ground -- legible in a unit
# test, invisible on the slide. Inline SVG inherits the page's custom properties,
# so the figure follows whatever theme the deck is wearing.
INK = "var(--ink, #1f2933)"
MUTED = "var(--muted, #6b7a8d)"
DEFAULT_ACCENT = "#c98a1e"


def _triangle(ox: float, oy: float, base: float, height: float, spec: Mapping[str, Any],
              accent: str, caption: str) -> str:
    """One right triangle with the right angle at the bottom-left."""
    legs = list(spec.get("legs") or ["", ""])
    legs += [""] * (2 - len(legs))
    hyp = str(spec.get("hyp") or "")
    area = str(spec.get("area") or "")

    apex_x, apex_y = ox, oy - height
    far_x, far_y = ox + base, oy
    poly = path(
        f"M {ox:.1f} {oy:.1f} L {apex_x:.1f} {apex_y:.1f} L {far_x:.1f} {far_y:.1f} Z",
        fill=accent, fill_opacity="0.13", stroke=accent, stroke_width="2.5",
        stroke_linejoin="round",
    )
    # the right-angle marker: a hypothesis of the theorem, so always drawn
    m = min(13.0, base * 0.16, height * 0.16)
    mark = path(
        f"M {ox:.1f} {oy - m:.1f} L {ox + m:.1f} {oy - m:.1f} L {ox + m:.1f} {oy:.1f}",
        fill="none", stroke=accent, stroke_width="1.8", stroke_opacity="0.8",
    )
    labels = [
        text(ox - 7, oy - height / 2, legs[0], fill=INK, font_size="16",
             text_anchor="end", dominant_baseline="middle"),
        text(ox + base / 2, oy + 21, legs[1], fill=INK, font_size="16",
             text_anchor="middle"),
        text(ox + base * 0.40, oy - height * 0.62, hyp, fill=INK, font_size="16",
             text_anchor="start"),
    ]
    cap = [text(ox + base / 2, oy + 45, caption, fill=accent, font_size="15",
                font_weight="700", text_anchor="middle")]
    if area:
        cap.append(text(ox + base / 2, oy + 66, f"area = {area}", fill=MUTED,
                        font_size="15", text_anchor="middle"))
    return group(poly + mark + "".join(labels) + "".join(cap))


@register("descent_triangles")
class DescentTrianglesTemplate:
    def render(self, params: Dict[str, Any]) -> str:
        return _render(params or {})


def _render(params: Dict[str, Any]) -> str:
    accent = str(params.get("accent") or params.get("color") or DEFAULT_ACCENT)
    first = params.get("first") or {}
    second = params.get("second") or {}
    note = str(params.get("note") or "strictly smaller").strip()

    baseline = H - 96
    # Scale the second triangle down visibly. If the caller gives numeric
    # hypotenuses use their ratio, else fall back to a clear 0.55 so the drawing
    # never accidentally shows two triangles the same size — which would say the
    # opposite of what a descent proof claims.
    ratio = 0.55
    try:
        h1, h2 = float(first.get("size")), float(second.get("size"))
        if h1 > 0 and 0 < h2 < h1:
            ratio = max(0.34, min(0.8, h2 / h1))
    except (TypeError, ValueError):
        pass

    b1, ht1 = 150.0, 118.0
    b2, ht2 = b1 * ratio, ht1 * ratio
    # ox=96 leaves room for the vertical leg label, which is end-anchored and ran
    # off the canvas at ox=46.
    left = _triangle(96, baseline, b1, ht1, first, accent, "the smallest one")
    right = _triangle(400, baseline, b2, ht2, second, accent, "smaller still")

    # The arrow lives in the gutter between the triangles and the note sits well
    # above it: at the same height the note ran straight through the first
    # triangle's hypotenuse label.
    gx0, gx1 = 272.0, 372.0
    ay = baseline - 46
    arrow = (
        path(f"M {gx0:.0f} {ay:.0f} L {gx1:.0f} {ay:.0f}", fill="none",
             stroke=MUTED, stroke_width="2.4", stroke_linecap="round")
        + path(f"M {gx1:.0f} {ay:.0f} l -11 -6 l 0 12 z", fill=MUTED)
        + text((gx0 + gx1) / 2, ay - 16, note, fill=MUTED, font_size="15",
               text_anchor="middle")
    )
    css = style(
        ".diagram text{font-family:var(--sans,'DejaVu Sans',Arial,sans-serif)}"
    )
    return svg_document(css + left + arrow + right, width=W, height=H,
                        viewbox=f"0 0 {W} {H}")
