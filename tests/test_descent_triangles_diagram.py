"""Tests for the descent_triangles figure.

The picture a descent proof needs: an integer right triangle with square area
manufactures a strictly smaller one with the same property. A narrated lecture
was asking viewers to hold two triangles and six side labels in their head.
"""

import re

from straightedge.diagrams import DIAGRAM_REGISTRY, render_diagram

HINT = {
    "type": "descent_triangles",
    "params": {
        "first": {"legs": ["p²−q²", "2pq"], "hyp": "p²+q²",
                  "area": "pq(p−q)(p+q)", "size": 17},
        "second": {"legs": ["d−c", "d+c"], "hyp": "2a", "area": "q = b²",
                   "size": 4},
        "note": "2a < a⁴+b⁴",
    },
}


def _polys(svg):
    """The two triangle outlines, as lists of (x, y) vertices."""
    out = []
    for d in re.findall(r'<path d="M ([^"]*?) Z"', svg):
        pts = re.findall(r"(-?[\d.]+) (-?[\d.]+)", d)
        if len(pts) == 3:
            out.append([(float(x), float(y)) for x, y in pts])
    return out


def test_registered():
    assert "descent_triangles" in DIAGRAM_REGISTRY


def test_draws_two_right_triangles_and_every_label():
    svg = render_diagram(HINT)
    assert svg and "<svg" in svg
    assert len(_polys(svg)) == 2
    for label in ("p²−q²", "2pq", "p²+q²", "d−c", "d+c", "2a",
                  "pq(p−q)(p+q)", "q = b²"):
        assert label in svg, label
    # the note carries a "<", which the text helper escapes
    assert "2a &lt; a⁴+b⁴" in svg


def test_the_second_triangle_is_actually_drawn_smaller():
    """The whole point of the figure. If both triangles came out the same size it
    would assert the opposite of what a descent proof claims, and the labels
    would be the only thing carrying the argument."""
    a, b = _polys(render_diagram(HINT))

    def area(t):
        (x1, y1), (x2, y2), (x3, y3) = t
        return abs((x2 - x1) * (y3 - y1) - (x3 - x1) * (y2 - y1)) / 2

    big, small = sorted((area(a), area(b)), reverse=True)
    assert small < big * 0.7


def test_equal_sizes_still_draw_a_visibly_smaller_second_triangle():
    # A caller who omits size, or passes a non-shrinking pair, must not get two
    # identical triangles -- the figure would then contradict the theorem.
    for second_size in (17, 99, None, "oops"):
        hint = {"type": "descent_triangles", "params": {
            "first": {"legs": ["a", "b"], "hyp": "c", "size": 17},
            "second": {"legs": ["d", "e"], "hyp": "f", "size": second_size},
        }}
        polys = _polys(render_diagram(hint))
        assert len(polys) == 2
        widths = sorted(max(p[0] for p in t) - min(p[0] for p in t) for t in polys)
        assert widths[0] < widths[1] * 0.85, second_size


def test_labels_use_theme_tokens_not_a_hardcoded_light_ink():
    """Hardcoding #1f2933 painted the side labels near-black on dark_academic's
    #0b1622 ground: legible in a unit test, invisible on the slide."""
    svg = render_diagram(HINT)
    assert "var(--ink" in svg and "var(--muted" in svg
    # the hex may only survive as the var() fallback, never as a bare fill
    assert 'fill="#1f2933"' not in svg
    assert 'fill="#6b7a8d"' not in svg


def test_the_right_angle_is_marked_on_both_triangles():
    # "right triangle" is a hypothesis of the theorem, not decoration.
    svg = render_diagram(HINT)
    # each marker is an open 3-point path (no Z)
    markers = [d for d in re.findall(r'<path d="(M [^"]*?)"', svg)
               if d.count("L") == 2 and "Z" not in d]
    assert len(markers) >= 2


def test_the_spec_accent_wins_so_a_restyled_deck_matches():
    svg = render_diagram({**HINT, "params": {**HINT["params"], "accent": "#ff0055"}})
    assert "#ff0055" in svg


def test_missing_params_do_not_raise():
    for params in ({}, {"first": {}}, {"first": {"legs": []}, "second": {}}):
        svg = render_diagram({"type": "descent_triangles", "params": params})
        assert svg and "<svg" in svg
