"""Phase 4: the construction figure template.

Phase 2 proved the model is right. This proves the drawing is *of* that model —
that every element reaches the SVG, that the frame holds all of it, and that a
construction which cannot be run produces nothing rather than half a figure.

One check here is not about geometry at all. The two templates that already used
`var(--ink, …)` cannot be rasterised: cairosvg reads `var(` as a hex literal and
raises, so those figures produce no PNG rather than the wrong colour. The plan
for this lane said to follow that convention. It is not followed, and
``test_colours_are_literal_so_the_figure_can_be_rasterised`` is why.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from fractions import Fraction

import pytest

from straightedge import catalog
from straightedge.diagrams import DIAGRAM_REGISTRY, render_diagram
from straightedge.diagrams.registry import count_data_marks
from straightedge.diagrams.templates.construction import build
from straightedge.geometry.draw import to_svg, to_svg_steps

SVG_NS = "{http://www.w3.org/2000/svg}"

BISECTOR = {
    "title": "Perpendicular bisector",
    "steps": [
        {"point": [0, 0], "id": "A"},
        {"point": [1, 0], "id": "B"},
        {"circle": ["A", "B"]},
        {"circle": ["B", "A"]},
        {"line": ["C", "D"]},
    ],
}


def _render(params) -> str:
    return render_diagram({"type": "construction", "params": params})


def _dims(svg: str) -> tuple[int, int]:
    match = re.search(r'width="(\d+)" height="(\d+)"', svg)
    assert match, "missing dimensions"
    return int(match.group(1)), int(match.group(2))


class TestRegistration:
    def test_registered(self):
        assert "construction" in DIAGRAM_REGISTRY

    def test_discoverable_with_its_parameters(self):
        [template] = [t for t in catalog.list_templates() if t.id == "construction"]
        assert template.lane == "figure" and template.output == "svg"
        for name in ("steps", "title", "labels", "guides", "width"):
            assert name in template.params


class TestItDrawsTheConstruction:
    def test_renders_marks_rather_than_chrome(self):
        svg = _render(BISECTOR)
        assert svg.startswith("<svg") and count_data_marks(svg) > 0

    def test_every_element_reaches_the_svg(self):
        """Two circles, two lines' worth of paths, and a dot for every point."""
        svg = _render(BISECTOR)
        root = ET.fromstring(svg)
        circles = root.findall(f".//{SVG_NS}circle")
        paths = root.findall(f".//{SVG_NS}path")
        construction = build(BISECTOR["steps"])
        drawn_circles = [c for c in circles
                         if "gc-circle" in (c.get("class") or "")]
        assert len(drawn_circles) == len(construction.circles) == 2
        assert len(paths) >= len(construction.lines) == 1
        dots = [c for c in circles if "gc-circle" not in (c.get("class") or "")]
        assert len(dots) == len(construction.points)

    def test_the_intersections_nobody_named_are_drawn_and_labelled(self):
        """Crossing the two circles makes C and D without being asked."""
        svg = _render(BISECTOR)
        labels = {(node.text or "") for node in ET.fromstring(svg).iter(f"{SVG_NS}text")}
        assert {"A", "B", "C", "D"} <= labels

    def test_drawing_the_axis_finds_the_midpoint(self):
        """Adding AB gives its crossings with both circles and with CD."""
        steps = BISECTOR["steps"] + [{"line": ["A", "B"]}]
        construction = build(steps)
        assert len(construction.points) == 7          # A B C D + E F on the circles + G
        midpoint = construction.points["G"]
        assert (midpoint.x - __import__("fractions").Fraction(1, 2)).is_zero()
        assert midpoint.y.is_zero()

    def test_a_title_is_drawn_and_makes_room_for_itself(self):
        with_title = _render(BISECTOR)
        without = _render({k: v for k, v in BISECTOR.items() if k != "title"})
        assert "Perpendicular bisector" in with_title
        assert _dims(with_title)[1] > _dims(without)[1]

    def test_labels_can_be_turned_off(self):
        """The title is still drawn — it is not a label."""
        svg = _render(dict(BISECTOR, labels=False))
        drawn = [(node.get("class") or "")
                 for node in ET.fromstring(svg).iter(f"{SVG_NS}text")]
        assert "gc-label" not in drawn
        assert drawn == ["gc-title"]


class TestGuides:
    GUIDED = {"steps": [
        {"point": [0, 0], "id": "A"}, {"point": [1, 0], "id": "B"},
        {"circle": ["A", "B"], "guide": True},
    ]}

    @staticmethod
    def _classes(svg: str) -> list[str]:
        """Classes actually used by drawn elements, not by the stylesheet.

        The stylesheet names every class whether or not anything uses it, so a
        substring check on the document answers the wrong question.
        """
        root = ET.fromstring(svg)
        return [(node.get("class") or "") for node in root.iter()
                if node.tag != f"{SVG_NS}style" and node.get("class")]

    def test_a_guide_is_drawn_dashed(self):
        assert "gc-guide" in self._classes(_render(self.GUIDED))

    def test_a_guide_can_be_hidden(self):
        assert "gc-guide" not in self._classes(
            _render(dict(self.GUIDED, guides="hidden")))

    def test_an_unknown_guide_mode_falls_back_rather_than_failing(self):
        svg = _render(dict(self.GUIDED, guides="sideways"))
        assert count_data_marks(svg) > 0


class TestTheFrameHoldsEverything:
    def test_circles_are_inside_the_viewbox(self):
        svg = _render(BISECTOR)
        width, height = _dims(svg)
        for node in ET.fromstring(svg).iter(f"{SVG_NS}circle"):
            cx, cy, r = (float(node.get("cx")), float(node.get("cy")),
                         float(node.get("r")))
            assert -1 <= cx - r and cx + r <= width + 1
            assert -1 <= cy - r and cy + r <= height + 1

    def test_no_label_is_drawn_off_canvas(self):
        from straightedge.diagrams.renderer import text_width
        svg = _render(BISECTOR)
        width, _ = _dims(svg)
        for node in ET.fromstring(svg).iter(f"{SVG_NS}text"):
            content = node.text or ""
            if not content.strip():
                continue
            size = 16.0 if "gc-title" in (node.get("class") or "") else 13.0
            span = text_width(content, size, safe=True)
            x = float(node.get("x"))
            left, right = ((x - span, x) if node.get("text-anchor") == "end"
                           else (x, x + span))
            assert left >= -1 and right <= width + 1, f"{content!r} leaves the canvas"

    def test_a_lopsided_construction_still_fits(self):
        svg = _render({"steps": [
            {"point": [0, 0], "id": "A"}, {"point": [40, 1], "id": "B"},
            {"circle": ["A", "B"]}]})
        width, height = _dims(svg)
        assert width > 0 and height > 0 and count_data_marks(svg) > 0


class TestRasterisability:
    def test_colours_are_literal_so_the_figure_can_be_rasterised(self):
        """`var(--ink, …)` is unrenderable outside a browser.

        cairosvg parses `var(` as a hex literal and raises, so a figure using
        custom properties produces no raster at all — not merely the wrong
        colour. Class names remain the theming surface.
        """
        svg = _render(BISECTOR)
        assert "var(--" not in svg
        assert "gc-circle" in svg and "gc-point" in svg


class TestExactCoordinates:
    def test_a_decimal_string_is_the_rational_it_denotes(self):
        construction = build([{"point": ["0.1", "0"], "id": "A"},
                              {"point": [1, 0], "id": "B"}])
        from fractions import Fraction
        assert (construction.points["A"].x - Fraction(1, 10)).is_zero()

    def test_a_fraction_string_is_accepted(self):
        construction = build([{"point": ["1/3", "0"], "id": "A"}])
        from fractions import Fraction
        assert (construction.points["A"].x - Fraction(1, 3)).is_zero()


class TestUnusableInputDrawsNothing:
    @pytest.mark.parametrize("params", [
        {},
        {"steps": []},
        {"steps": "not a list"},
        {"steps": [{"point": [0, 0]}, {"line": ["A", "ZZ"]}]},     # unknown id
        {"steps": [{"point": [0, 0]}, {"point": [0, 0]}, {"line": ["A", "A"]}]},
        {"steps": [{"circle": ["A", "B"]}]},                       # no points yet
        {"steps": [{"point": [0, 0, 0]}]},                         # not a pair
        {"steps": [{"nothing": 1}]},
        {"steps": [42]},
        {"steps": [{"point": ["not a number", 0]}]},
    ])
    def test_it_renders_nothing_rather_than_half_a_figure(self, params):
        assert count_data_marks(_render(params)) == 0

    def test_an_unknown_parameter_is_ignored(self):
        svg = _render(dict(BISECTOR, sparkles=True))
        assert count_data_marks(svg) > 0


class TestStepFrames:
    def test_one_frame_per_step(self):
        construction = build(BISECTOR["steps"])
        frames = to_svg_steps(construction)
        assert len(frames) == len(construction.steps)

    def test_each_frame_shows_everything_so_far_and_no_more(self):
        construction = build(BISECTOR["steps"])
        frames = to_svg_steps(construction)
        counts = [count_data_marks(frame) for frame in frames]
        assert counts == sorted(counts), "a later frame drew less than an earlier one"
        assert counts[-1] == count_data_marks(to_svg(construction))

    def test_the_frame_does_not_move_between_steps(self):
        """A fixed viewBox across the sequence, so the drawing grows into a
        stable picture rather than the camera lurching on every step."""
        frames = to_svg_steps(build(BISECTOR["steps"]))
        assert len({_dims(frame) for frame in frames}) == 1


class TestFloatCoordinatesAreNotApproximated:
    """`limit_denominator` was an approximation in the lane that forbids them.

    It turned `0.333333333334` into exactly `1/3`, `1.000000000001` into `1`
    and `1e-12` into `0` — so a claim false of the number supplied could be
    proved, exactly, of a number nobody supplied.
    """

    @pytest.mark.parametrize("value,expected", [
        (0.1, Fraction(1, 10)),
        (0.5, Fraction(1, 2)),
        (-2.25, Fraction(-9, 4)),
        (0.333333333334, Fraction(333333333334, 10 ** 12)),
        (1.000000000001, Fraction(1000000000001, 10 ** 12)),
        (1e-12, Fraction(1, 10 ** 12)),
    ])
    def test_a_float_is_the_decimal_it_prints_as(self, value, expected):
        from straightedge.diagrams.templates.construction import _coordinate
        assert _coordinate(value) == expected

    @pytest.mark.parametrize("value", [0.333333333334, 1.000000000001, 1e-12])
    def test_it_does_not_collapse_onto_a_neighbour(self, value):
        from straightedge.diagrams.templates.construction import _coordinate
        assert _coordinate(value) != Fraction(round(value))
        assert float(_coordinate(value)) == value

    @pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
    def test_a_non_finite_float_is_refused(self, value):
        from straightedge.diagrams.templates.construction import _coordinate
        with pytest.raises(ValueError):
            _coordinate(value)
