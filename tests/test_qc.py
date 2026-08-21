"""Visual checks, exercised against defects that reached finished videos.

Each case in ``TestRealDefects`` is a reconstruction of something that shipped
and was caught by a human opening a frame. If one of those stops failing here,
the check protecting it has regressed.
"""

from __future__ import annotations

import pytest

from straightedge.qc import (
    DEFAULT_FRAME, Box, Finding, boxes_from_scene, check, frame_from_scene,
    worst_severity,
)

VERTICAL_FRAME = (9.0, 16.0)


def _mark(label, x0, x1, y0, y1):
    return Box(label, x0, x1, y0, y1, kind="mark")


def _text(label, x0, x1, y0, y1):
    return Box(label, x0, x1, y0, y1, kind="text")


def _checks(findings):
    return {f.check for f in findings}


# ------------------------------------------------------------------ basics

def test_a_clean_scene_is_silent():
    boxes = [_mark("axes", -5, 5, -3, 3), _text("title", -2, 2, 3.2, 3.6)]
    assert check(boxes) == []
    assert worst_severity([]) is None


def test_box_geometry():
    b = _mark("b", -1, 1, -2, 2)
    assert (b.width, b.height, b.area) == (2.0, 4.0, 8.0)
    assert b.intersection_area(_mark("c", 0, 3, 0, 3)) == pytest.approx(2.0)
    assert b.intersection_area(_mark("far", 9, 10, 9, 10)) == 0.0


def test_worst_severity_ranks_error_over_warn():
    assert worst_severity([Finding("a", "warn", "m"), Finding("b", "error", "m")]) == "error"
    assert worst_severity([Finding("a", "warn", "m")]) == "warn"


# ------------------------------------------------------- the shipped defects

class TestRealDefects:

    def test_chrome_only_figure_is_empty(self):
        """A coordinate plane drew grid, axes, ticks and title — and no curve.

        The curve spec used a key the template did not read, so it was dropped
        without a word. Kilobytes of chrome, no content.
        """
        findings = check([Box("axes", 0, 0, 0, 0), Box("grid", 0, 0, 0, 0)])
        assert "empty" in _checks(findings)
        assert worst_severity(findings) == "error"

    def test_a_truly_empty_scene_is_empty(self):
        assert "empty" in _checks(check([]))

    def test_curve_leaving_the_plot_vertically(self):
        """Clipped on x but not y, so the arms ran off the top and bottom."""
        boxes = [_mark("curve", -3, 3, -9.0, 9.0)]
        findings = check(boxes)
        assert "out_of_frame" in _checks(findings)

    def test_labels_printed_on_the_same_spot(self):
        """Two curves met at the same endpoint, so both labels anchored there."""
        boxes = [_mark("axes", -5, 5, -3, 3),
                 _text("theta=pi/2", 1.0, 2.6, 0.4, 0.8),
                 _text("theta=3pi/2", 1.1, 2.7, 0.42, 0.82)]
        findings = check(boxes)
        assert "text_overlap" in _checks(findings)
        assert worst_severity(findings) == "error"

    def test_verdict_mark_pushed_past_the_right_edge(self):
        """A tick appended to the right of a legend left the frame."""
        half_w = DEFAULT_FRAME[0] / 2
        boxes = [_mark("axes", -5, 5, -3, 3),
                 _text("checkmark", half_w - 0.2, half_w + 0.9, 1.0, 1.6)]
        findings = check(boxes)
        assert "text_clipped" in _checks(findings)
        assert worst_severity(findings) == "error"

    def test_stroke_drawn_through_a_formula(self):
        """A steep line ran across the text stacked beneath its figure."""
        boxes = [_text("Sigma(k) = ...", -2.0, 2.0, -1.4, -1.0),
                 _mark("line", -1.0, 1.0, -2.0, 2.0)]
        findings = check(boxes)
        assert "text_obscured" in _checks(findings)
        assert worst_severity(findings) == "warn"

    def test_the_vertical_cut_is_judged_against_its_own_frame(self):
        """9:16 overrides frame_width/height; the default would clear anything.

        A box 4 units wide sits inside the landscape frame and outside the tall
        one, so checking a vertical scene against the default passes everything
        that matters.
        """
        boxes = [_mark("axes", -4.4, 4.4, -3, 3), _text("wide", -4.6, 4.6, 3.0, 3.5)]
        assert check(boxes) == []                       # landscape: fine
        findings = check(boxes, frame=VERTICAL_FRAME)   # 9 wide: not fine
        assert "text_clipped" in _checks(findings)


# --------------------------------------------------------------- tolerances

def test_two_strokes_crossing_is_a_graph_not_a_defect():
    boxes = [_mark("curve_a", -2, 2, -2, 2), _mark("curve_b", -1, 1, -3, 3)]
    assert check(boxes) == []


def test_touching_text_is_allowed_but_covered_text_is_not():
    base = _text("a", 0, 2, 0, 1)
    grazing = _text("b", 1.98, 4, 0, 1)      # ~1% shared
    covering = _text("c", 0.5, 2.5, 0, 1)    # 75% shared
    assert check([base, grazing]) == []
    assert "text_overlap" in _checks(check([base, covering]))


def test_stroke_width_does_not_trip_the_edge_check():
    half_w = DEFAULT_FRAME[0] / 2
    boxes = [_mark("axis", -half_w - 0.02, half_w + 0.02, -1, 1)]
    assert check(boxes) == []


def test_zero_area_mobjects_are_ignored_once_something_is_drawn():
    boxes = [_mark("real", -1, 1, -1, 1), Box("point", 3, 3, 3, 3)]
    assert check(boxes) == []


# --------------------------------------------------------- the manim adapter

class FakeMobject:
    """Duck-types the slice of Mobject that ``boxes_from_scene`` reads."""

    def __init__(self, x0, x1, y0, y1, *, text=None, children=(), opacity=1.0):
        self._b = (x0, x1, y0, y1)
        self.text = text
        self.submobjects = list(children)
        self.fill_opacity = opacity
        self.stroke_opacity = opacity

    def get_left(self):
        return (self._b[0], 0, 0)

    def get_right(self):
        return (self._b[1], 0, 0)

    def get_bottom(self):
        return (0, self._b[2], 0)

    def get_top(self):
        return (0, self._b[3], 0)


class Text(FakeMobject):
    """Named to match Manim's class, because that is what `_is_text` reads.

    Matching on class name rather than isinstance is what lets `qc` stay free of
    a Manim import — so the test has to exercise the name, not a stand-in.
    """


class FakeScene:
    def __init__(self, mobjects):
        self.mobjects = mobjects


def test_groups_are_walked_to_their_leaves():
    """A VGroup's own box spans its children, hiding one escapee.

    Checking the group would report a comfortable extent while a single label
    sat outside the frame.
    """
    inside = FakeMobject(-1, 1, -1, 1)
    escapee = FakeMobject(20, 22, 0, 1)
    scene = FakeScene([FakeMobject(-1, 22, -1, 1, children=[inside, escapee])])
    boxes = boxes_from_scene(scene)
    assert len(boxes) == 2
    assert any(b.x0 == 20 for b in boxes)


def test_text_is_classified_by_class_name():
    scene = FakeScene([Text(-1, 1, -1, 1, text="hello"), FakeMobject(-2, 2, -2, 2)])
    kinds = {b.label: b.kind for b in boxes_from_scene(scene)}
    assert kinds["hello"] == "text"
    assert kinds["FakeMobject"] == "mark"


def test_invisible_mobjects_are_skipped_by_default():
    scene = FakeScene([FakeMobject(-1, 1, -1, 1, opacity=0.0)])
    assert boxes_from_scene(scene) == []
    assert len(boxes_from_scene(scene, include_invisible=True)) == 1


def test_text_is_atomic_and_not_split_into_glyphs():
    """Manim renders a label as one VMobjectFromSVGPath per glyph.

    Descending into those means no leaf is ever classified as text, which
    silently disables both overlap checks — nothing fails, the scene just stops
    being inspected. A label is also one thing to a reader, so one box is the
    honest measurement.
    """
    glyphs = [FakeMobject(0, 0.4, 0, 1), FakeMobject(0.4, 0.8, 0, 1)]
    scene = FakeScene([Text(0, 0.8, 0, 1, text="hi", children=glyphs)])
    boxes = boxes_from_scene(scene)
    assert len(boxes) == 1
    assert boxes[0].kind == "text"
    assert (boxes[0].x0, boxes[0].x1) == (0, 0.8)


def test_unset_opacity_means_visible_not_transparent():
    """``MathTex.fill_opacity`` is None — the per-glyph children carry the fill.

    Reading None as zero drops every equation from the scene, and dropped boxes
    cannot collide, so the overlap checks pass on a scene they never saw.
    """
    unset = FakeMobject(-1, 1, -1, 1)
    unset.fill_opacity = None
    unset.stroke_opacity = None
    assert len(boxes_from_scene(FakeScene([unset]))) == 1

    transparent = FakeMobject(-1, 1, -1, 1, opacity=0.0)
    assert boxes_from_scene(FakeScene([transparent])) == []


def test_a_mobject_with_no_extent_is_tolerated():
    class Broken(FakeMobject):
        def get_left(self):
            raise AttributeError("no points")

    scene = FakeScene([Broken(0, 0, 0, 0), FakeMobject(-1, 1, -1, 1)])
    assert len(boxes_from_scene(scene)) == 1


# --------------------------------------------------------- against real Manim

@pytest.mark.smoke
def test_real_manim_mobjects_are_measured_and_judged():
    """The fakes above cannot catch a Manim API change; this can.

    Both bugs the adapter shipped with — text decomposing into glyphs, and
    ``fill_opacity`` being None on a container — passed every fake-based test
    and were only found by building real mobjects.
    """
    manim = pytest.importorskip("manim")
    from manim import Axes, MathTex, Scene, Text

    class Probe(Scene):
        def construct(self):  # pragma: no cover - never played
            pass

    axes = Axes(x_range=[0, 3], y_range=[-2, 2], x_length=8, y_length=4)

    clean = Probe()
    clean.add(axes, Text("Clean", font_size=30).to_edge(manim.UP),
              MathTex(r"f(x)", font_size=30).to_edge(manim.DOWN))
    boxes = boxes_from_scene(clean)
    assert sum(1 for b in boxes if b.kind == "text") == 2, "labels must survive as text"
    assert check(boxes) == []

    collided = Probe()
    spot = axes.c2p(1.5, 0)
    collided.add(axes,
                 MathTex(r"\alpha", font_size=30).next_to(spot, manim.UR, buff=0.05),
                 MathTex(r"\beta", font_size=30).next_to(spot, manim.UR, buff=0.05))
    assert "text_overlap" in {f.check for f in check(boxes_from_scene(collided))}

    clipped = Probe()
    clipped.add(axes, MathTex(r"\checkmark", font_size=44).move_to([7.4, 1.0, 0]))
    assert "text_clipped" in {f.check for f in check(boxes_from_scene(clipped))}


# ------------------------------------------------------------- which frame

class FakeCamera:
    def __init__(self, width, height):
        self.frame_width = width
        self.frame_height = height


class FramedScene(FakeScene):
    def __init__(self, mobjects, camera=None):
        super().__init__(mobjects)
        self.camera = camera


def test_the_frame_comes_from_the_camera_not_the_default():
    scene = FramedScene([], FakeCamera(9.0, 16.0))
    assert frame_from_scene(scene) == (9.0, 16.0)


def test_a_scene_without_a_camera_falls_back_to_landscape():
    """So a caller can always hand the result straight to ``check``."""
    assert frame_from_scene(FramedScene([])) == DEFAULT_FRAME
    assert frame_from_scene(FakeScene([])) == DEFAULT_FRAME


def test_a_camera_with_unreadable_dimensions_falls_back():
    assert frame_from_scene(FramedScene([], FakeCamera("wide", None))) == DEFAULT_FRAME


def test_the_default_frame_is_not_restated_by_this_module():
    """QC judges a scene that was composed against ``aspect.FRAME_UNITS``. Two
    copies of the frame that disagreed would pass clipped scenes and fail clean
    ones — worse than not checking at all.
    """
    from straightedge.aspect import LANDSCAPE, FRAME_UNITS

    assert DEFAULT_FRAME == FRAME_UNITS[LANDSCAPE]


def test_a_tall_label_is_clipped_in_a_vertical_frame_but_not_a_landscape_one():
    """The check that only works once the real frame reaches it: y = 7 is
    comfortably inside a 16-unit-tall cut and off the top of an 8-unit one.
    """
    label = Box("caption", -1.0, 1.0, 6.5, 7.0, kind="text")
    assert "text_clipped" in {f.check for f in check([label], frame=DEFAULT_FRAME)}
    assert check([label], frame=(9.0, 16.0)) == []


def test_real_manim_reports_the_frame_the_pixels_actually_produce():
    """Verified against Manim CE 0.20.1, and the reason ``frame_from_scene``
    reads the camera rather than ``config``.

    Assigning ``config.frame_height`` does not survive: the camera keeps
    ``frame_width`` and recomputes the height from the output's pixel ratio. So
    a 9:16 scene rendered at landscape pixels reports 9.0 x 5.06 — which is the
    truth about what the viewer sees, and precisely the misconfiguration worth
    catching. The vertical frame only materialises because the renderer passes
    ``-r`` as well as writing the frame into the source.
    """
    pytest.importorskip("manim")
    from manim import Scene, config

    saved = (config.frame_width, config.frame_height,
             config.pixel_width, config.pixel_height)
    try:
        config.frame_width, config.frame_height = 9.0, 16.0
        width, height = frame_from_scene(Scene())
        assert width == pytest.approx(9.0)
        assert height == pytest.approx(5.06, abs=0.05), "pixels still landscape"

        config.pixel_width, config.pixel_height = 480, 854
        width, height = frame_from_scene(Scene())
        assert width == pytest.approx(9.0)
        assert height == pytest.approx(16.0, abs=0.05), "both halves supplied"
    finally:
        (config.frame_width, config.frame_height,
         config.pixel_width, config.pixel_height) = saved


# ------------------------------------------------- one defect, reported once

class TestRepeatedCollisionsCollapse:
    """A filled surface is many mobjects, and a label resting on it hit each.

    ``conic/cone_slice`` reported 34 warnings for what a viewer sees as one
    label sitting on one cone: a cone is dozens of ``ThreeDVMobject`` quads and
    the label overlapped two dozen of them. Every finding was true. Together
    they were noise, and noise is what stops findings being read — the same
    argument that motivated giving strokes their real ink.
    """

    def _facets(self, n, **kw):
        """A surface built from ``n`` abutting quads, as Manim builds one."""
        return [Box(f"ThreeDVMobject", -1 + i * 0.1, -1 + (i + 1) * 0.1,
                    -1, 1, kind="mark", **kw) for i in range(n)]

    def test_many_facets_report_once(self):
        label = _text("alpha", -0.5, 0.5, -0.2, 0.2)
        findings = check(self._facets(20) + [label])
        assert len(findings) == 1
        assert findings[0].check == "text_obscured"

    def test_the_count_survives(self):
        """Collapsing must not become hiding: how many is the useful part."""
        label = _text("alpha", -0.5, 0.5, -0.2, 0.2)
        message = check(self._facets(20) + [label])[0].message
        # Ten of the twenty facets span the label's x range. Asserting the
        # number itself, because a looser check is satisfied by the percentage
        # that appears earlier in the same sentence.
        assert "(10 collisions)" in message

    def test_a_single_collision_reads_as_before(self):
        """No count, no 'up to' — the common case must not get noisier."""
        boxes = [_mark("Line", -0.4, 0.4, -0.1, 0.1),
                 _text("caption", -1, 1, -0.5, 0.5)]
        message = check(boxes)[0].message
        assert "collisions" not in message and "up to" not in message

    def test_coverage_is_measured_against_the_label(self):
        """The number must answer "how buried is the label", not "how big a
        share of one facet is shaded".

        Each facet here is twice the label's area and covers a fifth of it, so
        every *pair* shares 10% of the facet — under the tolerance if it were
        judged pair-wise, and a tenth of the truth. Together they bury the label
        completely, which is the defect a reader needs to see.
        """
        label = _text("alpha", -1.0, 1.0, -0.1, 0.1)
        facets = [Box("Surface", -1.0 + i * 0.4, -1.0 + (i + 1) * 0.4,
                      -1.0, 1.0, kind="mark") for i in range(5)]
        message = check(facets + [label])[0].message
        assert "100% covered" in message, message
        assert "up to" not in message, "a total, not a maximum over pairs"

    def test_overlapping_marks_are_not_counted_twice(self):
        """Coverage is a union, so it can never exceed the label itself."""
        label = _text("alpha", -1.0, 1.0, -1.0, 1.0)
        marks = [_mark("Surface", -1.0, 0.6, -1.0, 1.0),
                 _mark("Surface", -0.6, 1.0, -1.0, 1.0)]      # they share a band
        message = check(marks + [label])[0].message
        assert "100% covered" in message, message

    def test_a_partly_shaded_label_reports_its_real_share(self):
        """Not everything is 100%: a half-covered label must say so."""
        label = _text("alpha", -1.0, 1.0, -1.0, 1.0)
        half = _mark("Surface", -1.0, 0.0, -1.0, 1.0)
        message = check([half, label])[0].message
        assert "50% covered" in message, message

    def test_different_marks_stay_separate(self):
        """Only identical collisions merge — two causes are two findings."""
        label = _text("alpha", -0.5, 0.5, -0.2, 0.2)
        findings = check(self._facets(20) + [
            Box("DashedLine", -0.6, 0.6, -0.3, 0.3, kind="mark"), label])
        assert len(findings) == 2
        assert sum("ThreeDVMobject" in f.message for f in findings) == 1
        assert sum("DashedLine" in f.message for f in findings) == 1

    def test_errors_collapse_too_and_stay_errors(self):
        """Text on text is rarer, but thirty of them would be just as unusable.

        The ticks are spaced apart so they collide only with the caption; abutting
        them would add a second, correct finding about the ticks themselves.
        """
        caption = _text("caption", -3, 3, -0.2, 0.2)
        ticks = [_text("2", -2 + i, -1.9 + i, -0.1, 0.1) for i in range(4)]
        findings = check(ticks + [caption])
        assert len(findings) == 1
        assert findings[0].severity == "error"
        assert worst_severity(findings) == "error"
        assert "(4 collisions)" in findings[0].message

    def test_a_symmetric_overlap_collapses_either_way_round(self):
        """Text on text is symmetric, so scan order must not split the finding.

        Ordered so the caption is scanned before one tick and after the other,
        the same collision is found once as ``(A, B)`` and once as ``(B, A)``.
        Keyed in scan order those are two keys and two error-severity findings
        for one defect — the shape ``3d/cube_section`` reports.
        """
        boxes = [_text("A", -2.0, -1.0, -0.1, 0.1),
                 _text("B", -1.9, -1.1, -0.1, 0.1),
                 _text("B", 1.1, 1.9, -0.1, 0.1),
                 _text("A", 1.0, 2.0, -0.1, 0.1)]
        findings = check(boxes)
        assert len(findings) == 1, [f.message for f in findings]
        assert "(2 collisions)" in findings[0].message

    def test_a_stroke_through_two_labels_is_two_findings(self):
        """Grouping is per subject, so distinct labels are never merged away."""
        line = Box("Line", -2, 2, -0.05, 0.05, kind="mark",
                   path=(((-2.0, 0.0), (2.0, 0.0)),))
        a = _text("first", -1.6, -1.2, -0.2, 0.2)
        b = _text("second", 1.2, 1.6, -0.2, 0.2)
        assert len(check([line, a, b])) == 2


class TestAxisAlignedStrokesAreChecked:
    """A level line is zero-area however long it is.

    `_check_frame` skipped on area, so it skipped every axis-aligned stroke --
    and axis-aligned is what a guide, an axis, a gridline or a connector
    usually is. `matrix_transform` drew its eigenvector ray from x=192 to
    x=477 on a 460-wide canvas and the frame check said nothing about it; the
    grid in `riemann_sum` put a line 8px off the right edge of the figure for
    the same reason. Both were invisible to the one check that exists to catch
    exactly that.
    """

    def test_a_horizontal_line_leaving_the_frame_is_reported(self):
        box = Box("guide", 2.0, 12.0, 0.0, 0.0)          # zero height, far right
        found = check([box, Box("body", -1.0, 1.0, -1.0, 1.0)], frame=(14.0, 8.0))
        assert [f for f in found if f.check == "out_of_frame"], "level line went unseen"

    def test_a_vertical_line_leaving_the_frame_is_reported(self):
        box = Box("axis", 0.0, 0.0, 2.0, 9.0)            # zero width, off the top
        found = check([box, Box("body", -1.0, 1.0, -1.0, 1.0)], frame=(14.0, 8.0))
        assert [f for f in found if f.check == "out_of_frame"]

    def test_a_line_inside_the_frame_is_not_reported(self):
        box = Box("guide", -3.0, 3.0, 0.0, 0.0)
        found = check([box, Box("body", -1.0, 1.0, -1.0, 1.0)], frame=(14.0, 8.0))
        assert not [f for f in found if f.check == "out_of_frame"]

    def test_a_point_is_still_skipped(self):
        """Nothing to clip, and no extent to report an overhang of. The area
        guard was right about points and wrong about lines."""
        box = Box("dot", 20.0, 20.0, 20.0, 20.0)
        found = check([box, Box("body", -1.0, 1.0, -1.0, 1.0)], frame=(14.0, 8.0))
        assert not [f for f in found if f.check == "out_of_frame"]
