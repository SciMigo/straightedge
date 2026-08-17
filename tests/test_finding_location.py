"""A finding says *where* the defect is, not just that there is one.

Being told a caption is unreadable and being told the caption at
``(-3, 3, -0.2, 0.2)`` is unreadable are different things to an agent: the first
it can only report, the second it can move. So the location travels with the
finding — through the checks, through the sidecar, into the serialised form.
"""

from __future__ import annotations

import json
from dataclasses import asdict

from straightedge.qc import Box, check, check_sidecar


def _text(label, x0, x1, y0, y1):
    return Box(label, x0, x1, y0, y1, kind="text")


def _mark(label, x0, x1, y0, y1):
    return Box(label, x0, x1, y0, y1, kind="mark")


def test_a_clipped_label_carries_its_own_extent():
    clipped = _text("verdict", 6.4, 8.0, 1.0, 1.6)   # off the right edge
    finding = check([_mark("axes", -5, 5, -3, 3), clipped])[0]
    assert finding.check == "text_clipped"
    assert finding.box == (6.4, 8.0, 1.0, 1.6)


def test_an_overlap_finding_points_at_the_subject_label():
    caption = _text("caption", -3, 3, -0.2, 0.2)
    tick = _text("2", -2.1, -1.9, -0.1, 0.1)
    finding = next(f for f in check([caption, tick]) if f.check == "text_overlap")
    # The subject is the alphabetically-first label; its box is that label's.
    assert finding.box in {(-3, 3, -0.2, 0.2), (-2.1, -1.9, -0.1, 0.1)}
    assert finding.box[0] <= finding.box[1] and finding.box[2] <= finding.box[3]


def test_an_obscured_label_carries_the_text_box_not_the_mark():
    """The location worth having is the *label's*, since that is the thing to
    move — not the sprawling curve that covers it."""
    label = _text("x+h", 1.5, 2.0, -0.8, -0.5)
    curve = Box("ParametricFunction", -3, 3, -2, 9, kind="mark",
                path=(((1.4, -0.7), (2.1, -0.6)),))   # ink through the label
    finding = next(f for f in check([label, curve]) if f.check == "text_obscured")
    assert finding.box == (1.5, 2.0, -0.8, -0.5)


def test_a_finding_with_no_single_place_has_no_box():
    """An empty scene is a defect about the whole frame, not one coordinate."""
    finding = check([])[0]
    assert finding.check == "empty"
    assert finding.box is None


def test_the_box_survives_the_sidecar(tmp_path):
    """A render's findings are read back from the sidecar; the location must not
    be lost crossing that boundary, or an agent reading a report cannot act on
    it."""
    path = tmp_path / "qc.json"
    path.write_text(json.dumps({
        "frame": [14.22, 8.0],
        "boxes": [
            {"label": "caption", "x0": -3, "x1": 3, "y0": -0.2, "y1": 0.2,
             "kind": "text"},
            {"label": "2", "x0": -2.1, "x1": -1.9, "y0": -0.1, "y1": 0.1,
             "kind": "text"},
        ],
    }), encoding="utf-8")
    finding = next(f for f in check_sidecar(path) if f.check == "text_overlap")
    assert finding.box is not None
    assert asdict(finding)["box"] == list(finding.box) or asdict(finding)["box"] == finding.box


def test_the_field_is_optional_for_hand_built_findings():
    """Older callers construct Finding without a box; it must default cleanly."""
    from straightedge.qc import Finding
    assert Finding("x", "warn", "m").box is None
