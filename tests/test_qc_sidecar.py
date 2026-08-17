"""Carrying a built scene's measurements back out of the render subprocess.

``qc.check`` wants a live Manim scene; ``render_scene`` runs Manim in a
subprocess and hands back an MP4. Nothing in this package could previously do
both, which is why the visual checks had never run against a real render.

The bridge is a sidecar: the scene writes its extents as it finishes, and the
caller checks them once Manim exits. The tests below cover the two halves —
that the emitted tail is valid and wraps the right method, and that reading the
sidecar back degrades rather than explodes.

The live end-to-end path is covered by the ``smoke`` marker, since it needs
Manim and a real render.
"""

from __future__ import annotations

import ast
import json

import pytest

from straightedge.models import AnimationPlan, Topic
from straightedge.qc import Box, check, check_sidecar
from straightedge.templates import SCENE_CLASS_NAME, qc_tail_source, scene_code_for


def _plan() -> AnimationPlan:
    return AnimationPlan(
        topic=Topic.FUNCTION,
        title_zh="标题",
        objective_zh="目标",
        english_prompt="plot y=x**2",
        parameters={"expression": "x ** 2"},
    )


class TestTheEmittedTail:

    def test_it_is_valid_python(self):
        ast.parse(qc_tail_source("/tmp/qc.json"))

    def test_it_wraps_construct_not_tear_down(self):
        """Manim's ``Scene.render`` calls ``remove(*self.mobjects)`` between
        ``construct`` and ``tear_down``, so a tear_down hook would measure an
        empty scene and report every render as ``empty`` — the check failing on
        its own blind spot.
        """
        source = qc_tail_source("/tmp/qc.json")
        assert "cls.construct" in source
        assert "tear_down" not in source

    def test_it_applies_itself_to_the_generated_class(self):
        assert f"_qc_wrap({SCENE_CLASS_NAME})" in qc_tail_source("/tmp/qc.json")

    def test_the_sidecar_path_is_baked_in(self):
        assert repr("/var/run/qc.json") in qc_tail_source("/var/run/qc.json")

    def test_the_import_is_lazy_and_guarded(self):
        """The emitted scene has to render on a host that has Manim and not this
        package — the render container's exact situation. A top-level import
        would turn a missing checker into a failed render.
        """
        source = qc_tail_source("/tmp/qc.json")
        inner = source.split("def _qc_dump")[1]
        assert "try:" in inner.split("from straightedge.qc")[0]
        assert "except Exception:" in inner


class TestSceneAssembly:

    def test_absent_by_default(self):
        """The generated scene otherwise depends on nothing but Manim."""
        assert "_qc_dump" not in scene_code_for(_plan())

    def test_present_when_asked_for(self):
        code = scene_code_for(_plan(), qc_sidecar="/tmp/qc.json")
        assert "_qc_dump" in code

    def test_the_scene_still_parses_with_the_tail(self):
        ast.parse(scene_code_for(_plan(), qc_sidecar="/tmp/qc.json"))

    def test_the_tail_comes_after_the_class(self):
        """It is appended at module scope precisely so it does not depend on how
        a builder's ``construct`` body happens to end.
        """
        code = scene_code_for(_plan(), qc_sidecar="/tmp/qc.json")
        assert code.index(f"class {SCENE_CLASS_NAME}") < code.index("_qc_wrap")


class TestReadingItBack:

    def _write(self, tmp_path, payload):
        path = tmp_path / "qc.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_a_clean_scene_reports_nothing(self, tmp_path):
        path = self._write(tmp_path, {
            "frame": [14.22, 8.0],
            "boxes": [{"label": "curve", "x0": -3, "x1": 3,
                       "y0": -2, "y1": 2, "kind": "mark"}],
        })
        assert check_sidecar(path) == []

    def test_findings_survive_the_round_trip(self, tmp_path):
        """Two labels on the same spot is the defect the sidecar exists to carry
        back; it has to arrive as the same finding a live scene would produce.
        """
        box = {"y0": 0.0, "y1": 0.4, "kind": "text"}
        path = self._write(tmp_path, {
            "frame": [14.22, 8.0],
            "boxes": [
                {"label": "first", "x0": 0.0, "x1": 1.0, **box},
                {"label": "second", "x0": 0.05, "x1": 1.05, **box},
            ],
        })
        findings = check_sidecar(path)
        assert [f.check for f in findings] == ["text_overlap"]
        assert findings[0].severity == "error"

    def test_the_frame_is_read_from_the_scene_not_assumed(self, tmp_path):
        """A 9:16 cut composes into a 9-unit-wide frame. Judging it against the
        landscape default would call a well-placed label clipped.
        """
        box = {"label": "edge", "x0": 5.0, "x1": 6.0, "y0": 0.0, "y1": 0.4,
               "kind": "text"}
        wide = self._write(tmp_path, {"frame": [14.22, 8.0], "boxes": [box]})
        assert check_sidecar(wide) == [], "x=5..6 sits inside a 14.22-wide frame"

        # Same box, 9-unit-wide frame: x spans -4.5..4.5, so it is off the edge.
        narrow = (tmp_path / "narrow.json")
        narrow.write_text(json.dumps({"frame": [9.0, 16.0], "boxes": [box]}),
                          encoding="utf-8")
        clipped = check_sidecar(narrow)
        assert [f.check for f in clipped] == ["text_clipped"]
        assert clipped[0].severity == "error", "unreadable text is not a warning"

    def test_a_missing_sidecar_warns_rather_than_raises(self, tmp_path):
        """A render that produced no measurements is not evidence about the
        video — it is a fact about the checker. Ten minutes of a core are
        already spent by the time this runs.
        """
        findings = check_sidecar(tmp_path / "never-written.json")
        assert [f.severity for f in findings] == ["warn"]
        assert findings[0].check == "sidecar"

    @pytest.mark.parametrize("payload", [
        {"boxes": []},                                  # no frame
        {"frame": [14.22, 8.0]},                        # no boxes
        {"frame": "wide", "boxes": []},                 # frame not a pair
        {"frame": [14.22, 8.0], "boxes": [{"label": "x"}]},   # box missing bounds
    ])
    def test_a_malformed_sidecar_warns_rather_than_raises(self, tmp_path, payload):
        findings = check_sidecar(self._write(tmp_path, payload))
        assert [f.severity for f in findings] == ["warn"]

    def test_unparseable_json_warns(self, tmp_path):
        path = tmp_path / "qc.json"
        path.write_text("{not json", encoding="utf-8")
        assert [f.severity for f in check_sidecar(path)] == ["warn"]

    def test_kind_defaults_to_mark(self, tmp_path):
        """An older render's sidecar predates the field. Defaulting to ``mark``
        loses the text-on-text check for that box rather than crashing on it.
        """
        path = self._write(tmp_path, {
            "frame": [14.22, 8.0],
            "boxes": [{"label": "a", "x0": 0, "x1": 1, "y0": 0, "y1": 1}],
        })
        assert check_sidecar(path) == []


class TestStrokesCarryTheirInk:
    """A curve's bounding box is a terrible description of a curve.

    The parabola in ``calculus/derivative_tangent`` spans the whole plot, so
    judging by boxes alone reported every axis tick label inside the axes as
    obscured by it: 31 of 39 findings on the first real render, none of them
    true. The mark now says where its ink is, and the check asks that instead.
    """

    #: A parabola across the plot, sampled. Its bounding box covers everything
    #: from x=-3..3, y=0..9, but the ink only follows the curve.
    PARABOLA = Box(
        label="ParametricFunction", x0=-3.0, x1=3.0, y0=0.0, y1=9.0,
        path=(tuple((x / 10.0, (x / 10.0) ** 2) for x in range(-30, 31)),),
    )

    def test_a_label_inside_the_curves_box_is_not_obscured_by_it(self):
        """The tick '2' sits at (2, -0.3) — inside the parabola's box, nowhere
        near the parabola.
        """
        tick = Box(label="2", x0=1.9, x1=2.1, y0=-0.4, y1=-0.1, kind="text")
        findings = check([self.PARABOLA, tick])
        assert [f.check for f in findings if f.check == "text_obscured"] == []

    def test_a_label_the_curve_really_runs_through_is_still_caught(self):
        """At x=2 the parabola is at y=4, so a label there is genuinely covered.

        The fix must not buy its silence by disabling the check.
        """
        label = Box(label="on the curve", x0=1.8, x1=2.2, y0=3.8, y1=4.2,
                    kind="text")
        findings = check([self.PARABOLA, label])
        assert "text_obscured" in [f.check for f in findings]

    def test_a_stroke_crossing_between_samples_is_caught(self):
        """Neither endpoint is near the label; the segment crosses it anyway.

        Testing endpoints instead of clipping the segment would miss this, and
        it is the common shape: a long tangent line drawn across a caption.
        """
        line = Box(label="Line", x0=-4.0, x1=4.0, y0=-1.0, y1=1.0,
                   path=(((-4.0, -1.0), (4.0, 1.0)),))
        label = Box(label="caption", x0=-0.2, x1=0.2, y0=-0.15, y1=0.15,
                    kind="text")
        assert "text_obscured" in [f.check for f in check([line, label])]

    def test_a_mark_with_no_path_keeps_the_box_answer(self):
        """Filled shapes and anything unreadable fall back to box overlap, so a
        caller constructing boxes by hand behaves exactly as before.
        """
        blob = Box(label="Dot", x0=-1.0, x1=1.0, y0=-1.0, y1=1.0)
        label = Box(label="under it", x0=-0.5, x1=0.5, y0=-0.2, y1=0.2,
                    kind="text")
        assert "text_obscured" in [f.check for f in check([blob, label])]

    def test_the_path_survives_the_sidecar(self, tmp_path):
        """Serialized as nested lists; it has to come back as usable geometry."""
        path = tmp_path / "qc.json"
        path.write_text(json.dumps({
            "frame": [14.22, 8.0],
            "boxes": [
                {"label": "ParametricFunction", "x0": -3.0, "x1": 3.0,
                 "y0": 0.0, "y1": 9.0, "kind": "mark",
                 "path": [[[x / 10.0, (x / 10.0) ** 2] for x in range(-30, 31)]]},
                {"label": "2", "x0": 1.9, "x1": 2.1, "y0": -0.4, "y1": -0.1,
                 "kind": "text"},
            ],
        }), encoding="utf-8")
        assert [f for f in check_sidecar(path) if f.check == "text_obscured"] == []


def test_box_round_trips_through_the_sidecar_shape():
    """The emitted dump writes exactly these keys; drift here is silent.

    A field added to ``Box`` and not to the dump is invisible: the sidecar keeps
    parsing, the new field silently defaults, and the check it was added for
    stops working on rendered scenes while still passing in unit tests.
    """
    box = Box(label="l", x0=0.0, x1=1.0, y0=2.0, y1=3.0, kind="text")
    fields = set(vars(box))
    assert fields == {"label", "x0", "x1", "y0", "y1", "kind", "path"}

    emitted = qc_tail_source("/tmp/qc.json")
    for field in fields:
        assert f'"{field}"' in emitted, f"the dump does not write {field!r}"
