"""Tests for the org chart, and the shared text measurement it leans on.

The load-bearing check here is ``test_no_two_labels_overlap``. Every other
assertion in this file would have passed while the template drew a person's role
on top of their name — which is what it did, and what only showed up by
rasterising the SVG and looking at it. A name and a role in the same pixels is
not a smaller version of the right answer; it is unreadable, and it is exactly
the class of defect this project exists to refuse to ship.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

import pytest

from straightedge.diagrams import DIAGRAM_REGISTRY, render_diagram
from straightedge.diagrams.registry import count_data_marks
from straightedge.diagrams.renderer import (
    ELLIPSIS,
    fit_text,
    text_width,
    wrap_units,
)
from straightedge.diagrams.templates.org_chart import (
    CARD_W,
    CARD_W_MAX,
    COL_GAP,
    MARGIN,
    MAX_WIDTH,
    NAME_PX,
    ROLE_PX,
    TITLE_PX,
    column_width,
    columns_per_bank,
)

SVG_NS = "{http://www.w3.org/2000/svg}"

ORG = {
    "title": "SciMigo engineering",
    "root": {
        "name": "Ada Lovelace", "title": "CEO", "children": [
            {"name": "Grace Hopper", "title": "VP Engineering", "children": [
                {"name": "Ken Thompson", "title": "Staff Engineer"},
                {"name": "", "title": "Senior Engineer", "status": "vacant"},
                {"name": "Barbara Liskov", "title": "Principal", "children": [
                    {"name": "Alan Kay", "title": "Engineer"}]}]},
            {"name": "Radia Perlman", "title": "VP Infrastructure", "children": [
                {"name": "Vint Cerf", "title": "Network Lead"},
                {"name": "Sally Floyd", "title": "Staff Engineer",
                 "status": "interim"}]},
            {"name": "Margaret Hamilton", "title": "VP Reliability", "children": [
                {"name": "Jean Bartik", "title": "SRE Lead"}]}]},
    "assistants": [{"name": "Chief of Staff", "assists": "Ada Lovelace"}],
    "dotted": [{"from": "Ken Thompson", "to": "Radia Perlman", "label": "security"}],
}

#: Font size per style class, so a parsed <text> can be measured. Kept beside the
#: template's own constants rather than as literals, so a size change here is a
#: test failure rather than a silently wrong box.
_CLASS_PX = {
    "oc-name": NAME_PX, "oc-name root": NAME_PX,
    "oc-role": ROLE_PX, "oc-role root": ROLE_PX, "oc-role vacant": ROLE_PX,
    "oc-title": TITLE_PX, "oc-legend": 11.0, "oc-dotted-label": 10.5,
}


def _dims(svg: str) -> tuple[int, int]:
    m = re.search(r'width="(\d+)" height="(\d+)"', svg)
    assert m, "missing dimensions"
    return int(m.group(1)), int(m.group(2))


def _org(shape, prefix=""):
    if not shape:
        return []
    return [{"name": f"{prefix}{i + 1} Person Name", "title": "Manager",
             "children": _org(shape[1:], f"{prefix}{i + 1}.")}
            for i in range(shape[0])]


def _text_boxes(svg: str):
    """Every drawn label as ``(content, x0, x1, y0, y1)`` in user units."""
    root = ET.fromstring(svg)
    boxes = []
    for node in root.iter(f"{SVG_NS}text"):
        content = node.text or ""
        if not content.strip():
            continue
        cls = (node.get("class") or "").strip()
        size = _CLASS_PX.get(cls)
        assert size is not None, f"unmeasurable label class {cls!r}"
        bold = cls.startswith("oc-name") or cls == "oc-title"
        # Conservative on purpose. Measuring a label with the same estimate the
        # layout used makes the two agree with each other and disagree with the
        # rasteriser: the first version of this check passed against the very
        # layout bug it was written for, because both sides under-measured "Ken
        # Thompson" by the same 14%. The safe width is the one that spans what
        # the face may actually resolve to.
        w = text_width(content, size, bold=bold, safe=True)
        x, y = float(node.get("x")), float(node.get("y"))
        anchor = node.get("text-anchor")
        if anchor == "end":
            x0, x1 = x - w, x
        elif anchor == "middle":
            x0, x1 = x - w / 2, x + w / 2
        else:
            x0, x1 = x, x + w
        # A baseline sits about three quarters down the em box.
        boxes.append((content, x0, x1, y - size * 0.75, y + size * 0.25))
    return boxes


class TestRegistration:
    def test_registered(self):
        assert "org_chart" in DIAGRAM_REGISTRY

    def test_renders_people_roles_and_conventions(self):
        svg = render_diagram({"type": "org_chart", "params": ORG})
        assert count_data_marks(svg) > 0
        for label in ("Ada Lovelace", "Grace Hopper", "Radia Perlman",
                      "Vacant", "security", "Chief of Staff"):
            assert label in svg
        assert "oc-dotted" in svg          # secondary reporting is drawn
        assert "oc-row interim" in svg     # and so is interim status


class TestTheReasonItExists:
    """wbs packs a tree by subtree width; an org's leaves are people."""

    @pytest.mark.parametrize("shape", [(3, 3), (5, 4, 3), (8, 6, 5), (12, 8, 6)])
    def test_width_is_bounded_however_large_the_org(self, shape):
        svg = render_diagram({"type": "org_chart",
                              "params": {"root": {"name": "CEO", "title": "Chief",
                                                  "children": _org(shape)}}})
        assert _dims(svg)[0] <= MAX_WIDTH

    def test_wbs_is_the_thing_being_avoided(self):
        """The comparison that justifies a second tree template."""
        root = {"name": "CEO", "title": "Chief", "children": _org((6, 5, 4))}
        wide = _dims(render_diagram({"type": "wbs", "params": {"root": root}}))[0]
        ours = _dims(render_diagram({"type": "org_chart", "params": {"root": root}}))[0]
        assert wide > 15000, "wbs no longer explodes; this template's case changed"
        assert ours <= MAX_WIDTH
        assert wide / ours > 10

    def test_depth_adds_height_not_width(self):
        shallow = {"name": "CEO", "title": "C", "children": _org((4, 2))}
        deep = {"name": "CEO", "title": "C", "children": _org((4, 2, 3))}
        sw, sh = _dims(render_diagram({"type": "org_chart", "params": {"root": shallow}}))
        dw, dh = _dims(render_diagram({"type": "org_chart", "params": {"root": deep}}))
        assert dw == sw
        assert dh > sh

    def test_columns_wrap_into_banks_rather_than_overflowing(self):
        assert columns_per_bank(3) == 3
        assert columns_per_bank(50) < 50
        assert columns_per_bank(0) >= 1          # never a zero-column layout


class TestLegibility:
    def test_no_label_is_drawn_outside_the_canvas(self):
        params = dict(ORG, root=dict(
            ORG["root"], children=ORG["root"]["children"] + [
                {"name": "A person with a deliberately unreasonable name",
                 "title": "And a deliberately unreasonable role as well"}]))
        svg = render_diagram({"type": "org_chart", "params": params})
        width, height = _dims(svg)
        for content, x0, x1, y0, y1 in _text_boxes(svg):
            assert x0 >= -1, f"{content!r} starts off-canvas at {x0}"
            assert x1 <= width + 1, f"{content!r} ends off-canvas at {x1}"
            assert y1 <= height + 1, f"{content!r} runs below the canvas at {y1}"

    def test_no_two_labels_overlap(self):
        """The defect this template actually shipped with, now a check.

        A name and a role were placed by measuring the name and starting the
        role after it. The measurement was ~14% low on a name of wide letters,
        so "Ken Thompson" and "Staff Engine…" were drawn in the same pixels.
        """
        svg = render_diagram({"type": "org_chart", "params": ORG})
        boxes = _text_boxes(svg)
        for i, (ca, ax0, ax1, ay0, ay1) in enumerate(boxes):
            for cb, bx0, bx1, by0, by1 in boxes[i + 1:]:
                overlap_x = min(ax1, bx1) - max(ax0, bx0)
                overlap_y = min(ay1, by1) - max(ay0, by0)
                assert not (overlap_x > 1 and overlap_y > 1), (
                    f"{ca!r} and {cb!r} overlap by "
                    f"{overlap_x:.1f}x{overlap_y:.1f} units")

    def test_a_long_name_is_marked_where_it_is_cut(self):
        svg = render_diagram({"type": "org_chart", "params": {"root": {
            "name": "Dr. Alexandra Whitfield-Montgomery-Fotheringay-Ashby-de-la-Zouch",
            "title": "Chief Executive Officer and Chair of the Supervisory Board",
            "children": [{"name": "Someone With An Extremely Long Name Indeed Who "
                                  "Also Has Several Additional Middle Names",
                          "title": "Principal Engineer, Platform Infrastructure "
                                   "and Developer Experience"}]}}})
        assert ELLIPSIS in svg


class TestInputShapes:
    def test_flat_export_folds_into_a_tree(self):
        svg = render_diagram({"type": "org_chart", "params": {"people": [
            {"id": "1", "name": "Ada", "title": "CEO"},
            {"id": "2", "name": "Grace", "title": "VP", "reports_to": "1"},
            {"id": "3", "name": "Ken", "title": "Eng", "reports_to": "2"}]}})
        for who in ("Ada", "Grace", "Ken"):
            assert who in svg

    def test_a_cycle_in_the_export_does_not_hang(self):
        svg = render_diagram({"type": "org_chart", "params": {"people": [
            {"id": "a", "name": "Alice", "title": "X", "reports_to": "b"},
            {"id": "b", "name": "Bob", "title": "Y", "reports_to": "a"}]}})
        assert "Alice" in svg and "Bob" in svg

    def test_an_unknown_manager_keeps_the_person(self):
        """Better drawn in the wrong place than missing from the chart."""
        svg = render_diagram({"type": "org_chart", "params": {"people": [
            {"id": "1", "name": "Ada", "title": "CEO"},
            {"id": "9", "name": "Orphan", "title": "Eng", "reports_to": "nobody"}]}})
        assert "Orphan" in svg

    def test_a_vacancy_with_no_name_is_still_a_role(self):
        svg = render_diagram({"type": "org_chart", "params": {"root": {
            "name": "Ada", "title": "CEO",
            "children": [{"title": "Head of Design", "status": "open"}]}}})
        assert "Vacant" in svg and "Head of Design" in svg

    def test_unusable_params_render_nothing_rather_than_chrome(self):
        for bad in ({}, {"root": None}, {"people": []}, {"people": "nope"},
                    {"root": {"name": "", "title": ""}}):
            assert count_data_marks(
                render_diagram({"type": "org_chart", "params": bad})) == 0


class TestSharedMeasurement:
    """Regressions for the bugs the shared kernel was extracted to fix."""

    def test_cjk_is_measured_full_width(self):
        latin = text_width("abcd", 12)
        cjk = text_width("渲染引擎", 12)
        assert cjk > latin * 1.6, "CJK measured as though it were Latin"

    def test_width_depends_on_which_letters_not_just_how_many(self):
        """A flat per-character factor under-measured 'Ken Thompson' by 14%."""
        assert text_width("WWWW", 12) > text_width("llll", 12) * 2

    def test_bold_measures_wider_than_regular(self):
        assert text_width("Engineering", 12, bold=True) > text_width("Engineering", 12)

    def test_safe_width_is_conservative(self):
        assert text_width("Ken Thompson", 13.5, bold=True, safe=True) > \
               text_width("Ken Thompson", 13.5, bold=True)

    def test_fit_text_marks_the_cut(self):
        out = fit_text("A caption far too long for the space given", 60, 12)
        assert out.endswith(ELLIPSIS)
        assert text_width(out, 12) <= 60

    def test_fit_text_leaves_a_fitting_string_alone(self):
        assert fit_text("Short", 200, 12) == "Short"

    def test_wrap_units_marks_dropped_content(self):
        """It used to drop 44 of 82 characters and read like the whole thing."""
        s = ("A deliberately long caption that will certainly need more than "
             "two lines to render")
        assert wrap_units(s, 12, max_lines=2)[-1].endswith(ELLIPSIS)
        assert not wrap_units(s, 12, max_lines=2, mark_truncation=False)[-1] \
            .endswith(ELLIPSIS)

    def test_wrap_units_leaves_fitting_text_unmarked(self):
        assert wrap_units("Short label", 12, max_lines=2) == ["Short label"]


class TestNeighbouringTemplatesNoLongerCutSilently:
    def test_wbs_marks_a_trimmed_name(self):
        """`[:10]` rendered a real name as 'Dr. Alexan', which reads as a name."""
        svg = render_diagram({"type": "wbs", "params": {"root": {
            "name": "Dr. Alexandra Whitfield", "children": [{"name": "Sub"}]}}})
        assert "Dr. Alexan" not in svg or ELLIPSIS in svg
        assert ELLIPSIS in svg

    def test_comparison_marks_a_trimmed_description(self):
        svg = render_diagram({"type": "comparison", "params": {"columns": [
            {"label": "A", "desc": "A description far longer than the column "
                                   "it is drawn in can possibly hold",
             "points": ["one"]},
            {"label": "B", "desc": "short", "points": ["two"]}]}})
        assert ELLIPSIS in svg

    def test_roadmap_measures_cjk_captions_full_width(self):
        """It measured a nine-glyph Chinese caption at 57px; it renders ~103px,
        so the caption went inside a bar it overflowed."""
        from straightedge.diagrams.templates.roadmap import text_width as rm_width
        assert rm_width("渲染引擎与托管服务", 11.5) > 90


class TestColumnsFillTheCanvas:
    """Reported from a real re-org: five labels trimmed with 498px unused.

    The columns were pinned to a constant instead of to the space they had, so
    the layout trimmed names while a third of the page stayed blank. Trimming is
    correct only when there is nothing left to trim into.
    """

    def test_a_few_columns_use_the_width_available(self):
        svg = render_diagram({"type": "org_chart", "params": ORG})
        width, _ = _dims(svg)
        root = ET.fromstring(svg)
        edges = []
        for node in root.iter(f"{SVG_NS}rect"):
            if node.get("class") == "grid-paper":
                continue
            x = float(node.get("x"))
            edges += [x, x + float(node.get("width"))]
        assert max(edges) >= width - MARGIN - 1, (
            f"content stops at {max(edges):.0f} of {width}, leaving "
            f"{width - max(edges):.0f}px unused while labels are trimmed")

    def test_nothing_is_trimmed_when_there_is_room_for_it(self):
        svg = render_diagram({"type": "org_chart", "params": ORG})
        trimmed = [node.text for node in ET.fromstring(svg).iter(f"{SVG_NS}text")
                   if node.text and ELLIPSIS in node.text]
        assert trimmed == [], f"trimmed with room to spare: {trimmed}"

    def test_a_column_never_exceeds_the_readable_maximum(self):
        """One unit must not become a single page-wide card."""
        assert column_width(1) == CARD_W_MAX
        assert CARD_W <= column_width(3) <= CARD_W_MAX

    def test_many_columns_fall_back_to_the_minimum(self):
        assert column_width(20) == CARD_W

    def test_widths_fit_for_every_count_a_bank_can_hold(self):
        """The floor and the cap are one invariant, not two settings.

        `column_width` never goes below `CARD_W`, so a large enough column count
        would overflow the canvas — `columns_per_bank` is what stops that count
        ever being asked for. The two constants have to agree, and this is where
        they are checked against each other rather than tuned apart.
        """
        widest = columns_per_bank(99)
        for columns in range(1, widest + 1):
            span = columns * column_width(columns) + (columns - 1) * COL_GAP
            assert span <= MAX_WIDTH - 2 * MARGIN + 1, (
                f"{columns} columns span {span:.0f} of "
                f"{MAX_WIDTH - 2 * MARGIN} usable")


class TestTheDottedLineLandsWhereItPoints:
    """Also reported: 'security' rendered beside the CEO, labelling nothing."""

    @staticmethod
    def _curve(svg):
        for node in ET.fromstring(svg).iter(f"{SVG_NS}path"):
            if (node.get("class") or "") == "oc-dotted":
                found = re.match(
                    r"M ([\d.-]+) ([\d.-]+) Q ([\d.-]+) ([\d.-]+) "
                    r"([\d.-]+) ([\d.-]+)", node.get("d") or "")
                if found:
                    return [float(v) for v in found.groups()]
        return None

    @staticmethod
    def _label_y(svg):
        for node in ET.fromstring(svg).iter(f"{SVG_NS}text"):
            if (node.get("class") or "") == "oc-dotted-label":
                return float(node.get("y"))
        return None

    def test_the_label_sits_on_the_curve_it_names(self):
        svg = render_diagram({"type": "org_chart", "params": ORG})
        x0, y0, cx, cy, x1, y1 = self._curve(svg)
        apex = (y0 + 2 * cy + y1) / 4          # a quadratic at t = 1/2
        label = self._label_y(svg)
        assert abs(label - apex) <= 12, (
            f"label at y={label} but the curve peaks at y={apex}")

    def test_the_curve_clears_both_boxes_it_joins(self):
        """Ending at a box's centre draws the line through its own name."""
        svg = render_diagram({"type": "org_chart", "params": ORG})
        x0, y0, cx, cy, x1, y1 = self._curve(svg)
        boxes = []
        for node in ET.fromstring(svg).iter(f"{SVG_NS}rect"):
            if node.get("class") == "grid-paper":
                continue
            boxes.append((float(node.get("x")), float(node.get("y")),
                          float(node.get("width")), float(node.get("height"))))
        for x, y in ((x0, y0), (x1, y1)):
            for bx, by, bw, bh in boxes:
                inside = (bx + 1 < x < bx + bw - 1) and (by + 1 < y < by + bh - 1)
                assert not inside, f"endpoint ({x}, {y}) is inside a card"
