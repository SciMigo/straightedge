"""Tests for the circle_chord_rational figure.

Every rational point on x^2 + y^2 = 1 is the second intersection of a
rational-slope line through (-1, 0), and clearing denominators there IS Euclid's
formula for Pythagorean triples. The figure has to be drawn from the real slope,
because a schematic that put the point in the wrong place would undercut the
argument it exists to support.
"""

import re
from fractions import Fraction

from straightedge.diagrams import DIAGRAM_REGISTRY, render_diagram


def _svg(**params):
    return render_diagram({"type": "circle_chord_rational", "params": params})


def _circle(svg):
    m = re.search(r'<circle cx="([\d.]+)" cy="([\d.]+)" r="([\d.]+)"[^>]*fill="none"', svg)
    return tuple(float(g) for g in m.groups())


def _dots(svg):
    return [(float(a), float(b)) for a, b, r in
            re.findall(r'<circle cx="([\d.]+)" cy="([\d.]+)" r="([\d.]+)"[^>]*fill="[^n]', svg)]


def test_registered():
    assert "circle_chord_rational" in DIAGRAM_REGISTRY


def test_the_marked_point_is_actually_on_the_circle():
    """Drawn to scale, not schematically: the labelled intersection must satisfy
    the circle equation, or the picture argues against the algebra."""
    for num, den in ((2, 3), (1, 2), (3, 4), (1, 5)):
        svg = _svg(slope=[num, den])
        cx, cy, r = _circle(svg)
        for px, py in _dots(svg):
            d = ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5
            assert abs(d - r) < 1.0, (num, den, d, r)


def test_the_point_matches_the_exact_parametrisation():
    k = Fraction(2, 3)
    want_x = float((1 - k * k) / (1 + k * k))     # 5/13
    want_y = float((2 * k) / (1 + k * k))         # 12/13
    svg = _svg(slope=[2, 3])
    cx, cy, r = _circle(svg)
    dots = _dots(svg)
    # the non-(-1,0) dot, in circle coordinates
    pts = [((px - cx) / r, (cy - py) / r) for px, py in dots]
    p = max(pts, key=lambda t: t[1])
    assert abs(p[0] - want_x) < 0.02, p
    assert abs(p[1] - want_y) < 0.02, p


def test_it_carries_the_equation_and_the_recovered_triple():
    svg = _svg(slope=[2, 3], point_label="P = (5/13, 12/13)", triple="(5, 12, 13)")
    assert "x² + y² = 1" in svg
    assert "P = (5/13, 12/13)" in svg
    assert "(5, 12, 13)" in svg
    assert "slope k = 2/3" in svg


def test_a_degenerate_or_junk_slope_falls_back_instead_of_drawing_nonsense():
    # k = 0 puts the second point back at (-1,0); a huge or unparseable k would
    # push it off canvas. Both must fall back to the documented default.
    for bad in ([0, 1], [-2, 3], [99, 1], "wat", None, [1, 0]):
        svg = _svg(slope=bad)
        assert "slope k = 2/3" in svg, bad


def test_theme_tokens_not_hardcoded_light_ink():
    svg = _svg(slope=[2, 3])
    assert "var(--ink" in svg and "var(--muted" in svg and "var(--line" in svg
    assert 'fill="#1f2933"' not in svg


def test_spec_accent_wins():
    assert "#ff0055" in _svg(slope=[2, 3], accent="#ff0055")
