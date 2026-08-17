"""Measuring a 3D scene as the viewer sees it, not as its coordinates read.

Every check in :mod:`straightedge.qc` judges a flat picture. In a ``ThreeDScene``
the coordinates a mobject reports are not that picture, and the gap is not
subtle: a cube's ``A`` at ``(x, y, 0)`` and ``A₁`` at ``(x, y, h)`` differ only
in z, so measuring x and y alone made their boxes identical and reported a 100%
overlap on labels the camera separates by a quarter of the frame. Across the
builder sweep that produced 80 of 106 warnings and 6 of 13 errors.

Manim is not imported here. The camera contract is small — ``project_points``,
``fixed_in_frame_mobjects``, ``fixed_orientation_mobjects`` — so the fakes below
state exactly what is relied on, and a Manim release that changed any of it
would be caught by the ``smoke`` marker rather than by a mock that quietly kept
agreeing.
"""

from __future__ import annotations

import pytest

from straightedge.qc import boxes_from_scene


class FakeMobject:
    """The subset of a Manim mobject the extractor touches."""

    def __init__(self, label, points, *, kind="mark", fill=0.0, width=None,
                 height=None):
        self.tex_string = label
        self.points = [list(p) for p in points]
        self.fill_opacity = fill
        self.stroke_opacity = 1.0
        self.submobjects = []
        self._kind = kind
        self._width = width
        self._height = height
        # Captured up front so a test can empty ``points`` — as a real mobject
        # with no drawable extent has — while get_left/get_top keep answering,
        # which is what Manim does.
        self._extent = [
            [min(p[i] for p in self.points) for i in range(3)],
            [max(p[i] for p in self.points) for i in range(3)],
        ]

    # Text is matched by class name, so a text fake has to *be* a distinct class.
    @property
    def width(self):
        return (self._width if self._width is not None
                else self._extent[1][0] - self._extent[0][0])

    @property
    def height(self):
        return (self._height if self._height is not None
                else self._extent[1][1] - self._extent[0][1])

    def get_left(self):
        return [self._extent[0][0], 0, 0]

    def get_right(self):
        return [self._extent[1][0], 0, 0]

    def get_bottom(self):
        return [0, self._extent[0][1], 0]

    def get_top(self):
        return [0, self._extent[1][1], 0]

    def get_center(self):
        return _Row([(self._extent[0][i] + self._extent[1][i]) / 2
                     for i in range(3)])

    def get_subpaths(self):
        return [self.points]


class MathTex(FakeMobject):
    """Named to match what ``_is_text`` looks for."""


class _Row(list):
    def reshape(self, *_shape):
        return [list(self)]


class FlatCamera:
    """A 2D camera: no projection at all."""

    frame_width = 14.0
    frame_height = 8.0


class LiftCamera(FlatCamera):
    """Projects by pushing z into y, which is what a tilted camera does.

    Deliberately simple and deliberately *not* identity: the whole point is that
    two points differing only in z must land apart.
    """

    def __init__(self):
        self.fixed_in_frame_mobjects = set()
        self.fixed_orientation_mobjects = {}
        self.rotation_matrix = None
        self.generated = 0

    def generate_rotation_matrix(self):
        self.generated += 1
        return "fresh"

    def project_points(self, points):
        assert self.rotation_matrix == "fresh", (
            "project_points must run against a freshly generated matrix")
        return [[p[0], p[1] + p[2], p[2]] for p in points]


class Scene:
    def __init__(self, camera, *mobjects):
        self.camera = camera
        self.mobjects = list(mobjects)


def _box(boxes, label):
    matching = [b for b in boxes if b.label == label]
    assert len(matching) == 1, f"expected one {label!r}, got {len(matching)}"
    return matching[0]


class TestTheDefectThatMotivatedThis:

    def _cube_labels(self):
        return (MathTex("A", [[1, 1, 0], [1.2, 1.2, 0]]),
                MathTex("A_1", [[1, 1, 2], [1.2, 1.2, 2]]))

    def test_unprojected_they_are_the_same_box(self):
        """The bug, stated as a test: without a camera these coincide."""
        a, a1 = self._cube_labels()
        boxes = boxes_from_scene(Scene(FlatCamera(), a, a1))
        assert _box(boxes, "A").y0 == _box(boxes, "A_1").y0
        assert _box(boxes, "A").intersection_area(_box(boxes, "A_1")) > 0

    def test_projected_the_camera_separates_them(self):
        a, a1 = self._cube_labels()
        boxes = boxes_from_scene(Scene(LiftCamera(), a, a1))
        assert _box(boxes, "A").intersection_area(_box(boxes, "A_1")) == 0


class TestWhatMustNotBeProjected:

    def test_a_title_fixed_in_frame_keeps_its_own_coordinates(self):
        """``add_fixed_in_frame_mobjects`` puts a mobject in frame coordinates
        already. Projecting it a second time moves a title that never moved.
        """
        camera = LiftCamera()
        title = MathTex("title", [[-1, 3, 5], [1, 3.4, 5]])
        camera.fixed_in_frame_mobjects.add(title)
        box = _box(boxes_from_scene(Scene(camera, title)), "title")
        assert (box.y0, box.y1) == (3.0, 3.4), "z must not have been folded in"

    def test_a_billboard_moves_but_does_not_change_size(self):
        """``add_fixed_orientation_mobjects`` labels turn to face the camera, so
        they keep their on-screen size wherever they sit. Projecting their glyph
        outlines instead would squash them by the camera angle.
        """
        camera = LiftCamera()
        label = MathTex("v", [[0, 0, 4], [0.5, 0.25, 4]], width=0.5, height=0.25)
        camera.fixed_orientation_mobjects[label] = None
        box = _box(boxes_from_scene(Scene(camera, label)), "v")
        assert box.width == pytest.approx(0.5)
        assert box.height == pytest.approx(0.25)
        # Centre projected: y centre 0.125 plus z 4.
        assert box.y0 == pytest.approx(4.125 - 0.125)


class TestFallbacks:
    """Every failure lands on the behaviour a 2D scene already had."""

    def test_a_scene_with_no_camera_is_measured_flat(self):
        mob = MathTex("m", [[0, 0, 9], [1, 1, 9]])
        scene = Scene(None, mob)
        assert _box(boxes_from_scene(scene), "m").y1 == 1

    def test_a_camera_without_projection_is_measured_flat(self):
        mob = MathTex("m", [[0, 0, 9], [1, 1, 9]])
        assert _box(boxes_from_scene(Scene(FlatCamera(), mob)), "m").y1 == 1

    def test_a_mobject_with_no_points_falls_back_to_its_box(self):
        mob = MathTex("m", [[0, 0, 0], [1, 1, 0]])
        mob.points = []
        assert _box(boxes_from_scene(Scene(LiftCamera(), mob)), "m").y1 == 1

    def test_a_camera_that_raises_does_not_take_the_check_down(self):
        class Broken(LiftCamera):
            def project_points(self, points):
                raise RuntimeError("no")

        mob = MathTex("m", [[0, 0, 9], [1, 1, 9]])
        assert _box(boxes_from_scene(Scene(Broken(), mob)), "m").y1 == 1


class TestTheRotationMatrixIsRefreshed:
    """``project_points`` reads a cached matrix the renderer refreshes per frame.

    A caller measuring outside the render loop would otherwise get whatever was
    left over — an identity matrix, in the case that matters, silently
    reproducing the unprojected bug.
    """

    def test_it_is_generated_once_and_restored_after(self):
        camera = LiftCamera()
        camera.rotation_matrix = "stale"
        mobs = [MathTex(str(i), [[0, 0, i], [1, 1, i]]) for i in range(4)]
        boxes_from_scene(Scene(camera, *mobs))
        assert camera.generated == 1, "regenerating per mobject is wasted work"
        assert camera.rotation_matrix == "stale", "the camera must be left as found"


class TestStrokePathsAreProjectedToo:

    def test_a_curve_carries_projected_ink(self):
        """An unprojected polyline traces a shape the viewer never sees, and the
        segment test would then be exact about the wrong geometry.
        """
        curve = FakeMobject("Curve", [[0, 0, 0], [1, 0, 1], [2, 0, 2],
                                      [3, 0, 3], [4, 0, 4]])
        box = _box(boxes_from_scene(Scene(LiftCamera(), curve)), "Curve")
        assert box.path, "a stroke-only mark should carry its ink"
        ys = [p[1] for line in box.path for p in line]
        assert max(ys) > 0, "z must have been folded into the projected y"
