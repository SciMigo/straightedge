"""Arrows in dp_table and matrix_state stop short of the values they connect.

Drawn centre to centre, a dependency arrow's line and head sat on the number printed in the
target cell (an external review of a knapsack lab: two arrows into T[2][3] covered its 9).
"""

from __future__ import annotations

import math
import re

import pytest

from straightedge.diagrams import render_diagram
from straightedge.diagrams.renderer import cell_arrow_ends


def _lines(svg: str, cls: str) -> list[tuple[float, float, float, float]]:
    out = []
    for tag in re.findall(r"<line [^>]*>", svg):
        if f'class="{cls}"' not in tag:
            continue
        get = lambda k: float(re.search(rf'\b{k}="([-0-9.e]+)"', tag).group(1))
        out.append((get("x1"), get("y1"), get("x2"), get("y2")))
    return out


def test_adjacent_cells_keep_a_visible_arrow():
    # Vertically adjacent 40-px cells: centres 40 apart, the arrow keeps 35% of the span.
    x1, y1, x2, y2 = cell_arrow_ends(0, 0, 0, 40, 25, 20)
    assert (x1, x2) == (0, 0)
    assert y1 == pytest.approx(13) and y2 == pytest.approx(27)


def test_ends_leave_the_middle_of_each_cell_clear():
    # A long diagonal: each end is 55% of the way from its centre to the border it heads for.
    x1, y1, x2, y2 = cell_arrow_ends(0, 0, 200, 80, 25, 20)
    assert x1 == pytest.approx(0.65 * 25) and y1 == pytest.approx(0.65 * 25 * 80 / 200)
    assert 200 - x2 == pytest.approx(0.65 * 25)


def test_same_cell_is_left_alone():
    assert cell_arrow_ends(5, 5, 5, 5, 25, 20) == (5, 5, 5, 5)


@pytest.mark.parametrize("kind, cls, w, h", [("dp_table", "dp-arrow", 50, 40),
                                             ("matrix_state", "matrix-arrow", 50, 45)])
def test_rendered_arrows_do_not_touch_cell_centres(kind, cls, w, h):
    params = {
        "values": [[0, 0, 0, 0], [0, 7, 7, 9], [0, 7, 9, 16]],
        "arrows": [{"from": [1, 3], "to": [2, 3]}, {"from": [1, 0], "to": [2, 3]}],
    }
    svg = render_diagram({"type": kind, "params": params})
    arrows = _lines(svg, cls)
    assert len(arrows) == 2
    for x1, y1, x2, y2 in arrows:
        assert math.hypot(x2 - x1, y2 - y1) >= 0.3 * min(w, h)      # still a visible arrow
    # Both arrows point into the same cell, (2, 3); neither may end on its centre, where the
    # value is printed. Its centre is where the two unshortened arrows would have met.
    (a, b, c, d), (e, f, g, k) = arrows
    ux, uy = (c - a), (d - b)
    vx, vy = (g - e), (k - f)
    # Recover the common target centre as the intersection of the two arrow lines.
    det = ux * (-vy) - uy * (-vx)
    t = ((e - a) * (-vy) - (f - b) * (-vx)) / det
    cx, cy = a + t * ux, b + t * uy
    for (x2, y2) in ((c, d), (g, k)):
        assert math.hypot(x2 - cx, y2 - cy) >= 0.6 * min(w, h) / 2
