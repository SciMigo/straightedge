"""A chord of rational slope through (-1, 0), and where it lands on the circle.

The one picture the Pythagorean-triple parametrisation needs. Every rational
point on x^2 + y^2 = 1 is where some rational-slope line through (-1, 0) meets
the circle a second time, and clearing denominators in that point IS Euclid's
formula. A narrated derivation that only shows algebra asks the viewer to
imagine the circle while following the quadratic.

Draws to scale from a real slope, so the labelled intersection is genuinely
where the line crosses: a schematic that put P in the wrong quadrant would
undercut the argument it exists to support.

    image_hint = {
        "type": "circle_chord_rational",
        "params": {
            "slope": [2, 3],                    # k = n/m, drawn to scale
            "point_label": "P = (5/13, 12/13)",
            "triple": "(5, 12, 13)",
        },
    }

The default slope 2/3 lands on (5/13, 12/13) and so recovers the 5-12-13
triangle, which is the example most viewers already know.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any, Dict

from ..registry import register
from ..renderer import circle, group, line, path, style, svg_document, text

W, H = 460, 400
INK = "var(--ink, #1f2933)"
MUTED = "var(--muted, #6b7a8d)"
LINE = "var(--line, #c9d3de)"
DEFAULT_ACCENT = "#2f6f8f"


def _slope(params: Dict[str, Any]) -> Fraction:
    raw = params.get("slope", [2, 3])
    try:
        if isinstance(raw, (list, tuple)) and len(raw) == 2:
            k = Fraction(int(raw[0]), int(raw[1]))
        else:
            k = Fraction(str(raw))
    except (TypeError, ValueError, ZeroDivisionError):
        k = Fraction(2, 3)
    # A chord through (-1,0) meets the circle again only for |k| < inf; keep the
    # drawing in the upper half and away from the tangent case.
    if not (0 < k < 4):
        k = Fraction(2, 3)
    return k


@register("circle_chord_rational")
class CircleChordRationalTemplate:
    def render(self, params: Dict[str, Any]) -> str:
        return _render(params or {})


def _render(params: Dict[str, Any]) -> str:
    accent = str(params.get("accent") or params.get("color") or DEFAULT_ACCENT)
    k = _slope(params)
    # second intersection, exactly
    px = (1 - k * k) / (1 + k * k)
    py = (2 * k) / (1 + k * k)

    cx, cy, R = W / 2, H / 2 - 10, 132.0
    def sx(v: float) -> float: return cx + float(v) * R
    def sy(v: float) -> float: return cy - float(v) * R

    parts = [
        # axes
        line(cx - R - 26, cy, cx + R + 26, cy, stroke=LINE, stroke_width="1.6"),
        line(cx, cy - R - 26, cx, cy + R + 26, stroke=LINE, stroke_width="1.6"),
        circle(cx, cy, R, fill="none", stroke=accent, stroke_width="2.6",
               stroke_opacity="0.9"),
    ]
    ax, ay = sx(-1), sy(0)
    ppx, ppy = sx(px), sy(py)
    # the chord, extended a little past P so it reads as a line not a segment
    dx, dy = ppx - ax, ppy - ay
    # Extend only slightly past P: at 1.22 the dashes ran through P's own label.
    parts.append(line(ax, ay, ax + dx * 1.07, ay + dy * 1.07,
                      stroke=accent, stroke_width="2.2", stroke_opacity="0.75",
                      stroke_dasharray="6 4"))
    # the two rational points
    parts.append(circle(ax, ay, 5.5, fill=accent))
    parts.append(circle(ppx, ppy, 6.5, fill=accent))
    # below-left of the point, clear of both the axis and the circle
    parts.append(text(ax - 4, ay + 26, "(−1, 0)", fill=MUTED, font_size="15",
                      text_anchor="middle"))
    label = str(params.get("point_label") or "P").strip()
    parts.append(text(ppx + 16, ppy - 16, label, fill=INK, font_size="16",
                      font_weight="700", text_anchor="start"))
    # slope annotation on the chord, placed off the line
    mid_x, mid_y = (ax + ppx) / 2, (ay + ppy) / 2
    parts.append(text(mid_x - 8, mid_y + 22,
                      f"slope k = {k.numerator}/{k.denominator}",
                      fill=accent, font_size="15", font_weight="700",
                      text_anchor="end"))
    # dropped legs: the triple lives in this right triangle
    parts.append(path(f"M {ppx:.1f} {ppy:.1f} L {ppx:.1f} {cy:.1f} L {cx:.1f} {cy:.1f}",
                      fill="none", stroke=MUTED, stroke_width="1.6",
                      stroke_opacity="0.75", stroke_dasharray="4 3"))
    parts.append(text(cx + R + 18, cy + 20, "x", fill=MUTED, font_size="15"))
    parts.append(text(cx - 18, cy - R - 18, "y", fill=MUTED, font_size="15"))
    parts.append(text(cx, cy + R + 44, "x² + y² = 1", fill=INK, font_size="16",
                      text_anchor="middle"))
    triple = str(params.get("triple") or "").strip()
    if triple:
        parts.append(text(cx, cy + R + 68,
                          f"clear denominators → {triple}", fill=accent,
                          font_size="15", font_weight="700", text_anchor="middle"))
    css = style(".diagram text{font-family:var(--sans,'DejaVu Sans',Arial,sans-serif)}")
    return svg_document(css + group("".join(parts)), width=W, height=H,
                        viewbox=f"0 0 {W} {H}")
