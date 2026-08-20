"""Tests for the calendar roadmap template, and the gantt bounds it exists beside."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from straightedge.diagrams import DIAGRAM_REGISTRY, render_diagram
from straightedge.diagrams.registry import count_data_marks
from straightedge.diagrams.templates.roadmap import WIDTH, pack_lanes, text_width

PLAN = {
    "title": "Launch roadmap",
    "start_date": "2026-09-01",
    "end_date": "2027-02-28",
    "tracks": [
        {"id": "engine", "label": "Rendering engine"},
        {"id": "service", "label": "Hosted service"},
    ],
    "items": [
        {"id": "t1", "title": "Checked time-plan renderer", "track": "engine",
         "start_date": "2026-09-01", "end_date": "2026-10-15", "status": "active"},
        {"id": "t2", "title": "Artifact API", "track": "service",
         "start_date": "2026-09-01", "end_date": "2026-10-31", "status": "active"},
        {"id": "t3", "title": "Regional overlays", "track": "service",
         "start_date": "2027-01-05", "end_date": "2027-02-15",
         "status": "tentative", "depends_on": ["t2"]},
    ],
    "milestones": [{"title": "Private beta", "date": "2026-11-01"}],
}


def _dims(svg: str) -> tuple[int, int]:
    m = re.search(r'width="(\d+)" height="(\d+)"', svg)
    assert m, "missing dimensions"
    return int(m.group(1)), int(m.group(2))


def test_registered():
    assert "roadmap" in DIAGRAM_REGISTRY


def test_renders_lanes_milestones_and_statuses():
    svg = render_diagram({"type": "roadmap", "params": PLAN})
    assert count_data_marks(svg) > 0
    for label in ("Rendering engine", "Hosted service", "Private beta", "Launch roadmap"):
        assert label in svg
    assert "#2a9d8f" in svg and "#8d79a8" in svg      # active and tentative differ


def test_axis_carries_calendar_dates_not_unit_offsets():
    svg = render_diagram({"type": "roadmap", "params": PLAN})
    assert "Sep 01" in svg and "Feb 28" in svg
    # The gantt failure this template exists to avoid: a 0..180 integer axis.
    assert ">180<" not in svg


def test_width_is_bounded_regardless_of_span():
    short = dict(PLAN, start_date="2026-09-01", end_date="2026-09-30")
    long = dict(PLAN, start_date="2026-09-01", end_date="2031-09-01")
    assert _dims(render_diagram({"type": "roadmap", "params": short}))[0] == WIDTH
    assert _dims(render_diagram({"type": "roadmap", "params": long}))[0] == WIDTH


def test_overlapping_items_never_share_a_row():
    rows = pack_lanes([
        {"start": 1, "end": 10, "title": "a"},
        {"start": 5, "end": 12, "title": "b"},     # overlaps a
        {"start": 13, "end": 20, "title": "c"},    # clears both
    ])
    assert len(rows) == 2
    for row in rows:
        for earlier, later in zip(row, row[1:]):
            assert earlier["end"] < later["start"]


def test_a_crowded_track_grows_taller_not_denser():
    crowded = dict(PLAN, items=PLAN["items"] + [
        {"id": f"x{i}", "title": f"Overlap {i}", "track": "engine",
         "start_date": "2026-09-05", "end_date": "2026-10-01"} for i in range(3)])
    assert _dims(render_diagram({"type": "roadmap", "params": crowded}))[1] > \
           _dims(render_diagram({"type": "roadmap", "params": PLAN}))[1]


def test_dependency_connector_is_drawn():
    svg = render_diagram({"type": "roadmap", "params": PLAN})
    assert "r-dep" in svg


def test_no_caption_is_drawn_outside_the_canvas():
    """A label that overflows the canvas is the legibility failure here: it is
    clipped by the viewBox, so it reads as missing rather than as too long."""
    wide = dict(PLAN, items=PLAN["items"] + [{
        "id": "t9", "title": "A deliberately long item caption that cannot fit",
        "track": "engine", "start_date": "2027-02-20", "end_date": "2027-02-28"}])
    svg = render_diagram({"type": "roadmap", "params": wide})
    root = ET.fromstring(svg)
    for node in root.iter("{http://www.w3.org/2000/svg}text"):
        x, content = float(node.get("x")), (node.text or "")
        span = text_width(content, 12)
        anchor = node.get("text-anchor")
        if anchor == "end":
            left, right = x - span, x
        elif anchor == "middle":
            left, right = x - span / 2, x + span / 2
        else:
            left, right = x, x + span
        assert left >= -1, f"{content!r} starts off-canvas at {left}"
        assert right <= WIDTH + 1, f"{content!r} ends off-canvas at {right}"


def test_unusable_params_render_nothing_rather_than_chrome():
    for bad in ({}, dict(PLAN, tracks=[]), dict(PLAN, start_date="not-a-date"),
                dict(PLAN, start_date="2027-01-01", end_date="2026-01-01")):
        assert count_data_marks(render_diagram({"type": "roadmap", "params": bad})) == 0


def test_gantt_width_stays_bounded_for_many_units():
    """Regression: MIN_UNIT_PX made width grow linearly with the unit count."""
    svg = render_diagram({"type": "gantt", "params": {
        "tasks": [{"name": "long", "start": 0, "duration": 180}]}})
    assert _dims(svg)[0] < 1200


def test_gantt_label_is_trimmed_to_the_gutter_with_an_ellipsis():
    svg = render_diagram({"type": "gantt", "params": {
        "tasks": [{"name": "A very long activity name indeed", "start": 0, "duration": 3}]}})
    assert "…" in svg
