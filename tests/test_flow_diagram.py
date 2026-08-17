"""Tests for the flow_diagram process/block-diagram template."""
from __future__ import annotations

import straightedge.diagrams.templates  # noqa: F401  (triggers @register)
from straightedge.diagrams.registry import DIAGRAM_REGISTRY, render_diagram
from straightedge.diagrams.templates.flow_diagram import _wrap


def test_flow_diagram_registered():
    assert "flow_diagram" in DIAGRAM_REGISTRY


def test_renders_boxes_arrows_and_labels():
    svg = render_diagram({"type": "flow_diagram", "params": {
        "title": "会计核算流程",
        "steps": [
            {"label": "填制凭证", "desc": "审核原始凭证"},
            {"label": "登记账簿"},
            {"label": "编制报表"},
        ]}})
    assert svg.startswith("<svg")
    assert "填制凭证" in svg and "编制报表" in svg
    assert "会计核算流程" in svg          # title
    assert "flow-arrow" in svg            # arrow marker defined
    assert svg.count("<rect") >= 3        # one box (plus accent bar) per step


def test_accepts_bare_string_steps_and_aliases():
    svg = render_diagram({"type": "flow_diagram", "params": {
        "steps": ["资金投入", {"name": "资金循环"}, {"text": "资金退出"}]}})
    assert "资金投入" in svg and "资金循环" in svg and "资金退出" in svg


def test_snake_wraps_many_steps_into_rows():
    """Beyond MAX_COLS the layout wraps to a new row: width is capped at the
    4-column width, and the extra row makes it taller."""
    import re

    def _hw(n):
        svg = render_diagram({"type": "flow_diagram",
                              "params": {"steps": [f"步骤{i}" for i in range(n)]}})
        m = re.search(r'width="(\d+)" height="(\d+)"', svg)
        return int(m.group(1)), int(m.group(2))

    w4, h4 = _hw(4)   # exactly one full row (the cap)
    w6, h6 = _hw(6)   # wraps to a second row
    assert w6 == w4   # width capped by MAX_COLS, not 6 boxes wide
    assert h6 > h4    # the wrapped row adds height


def test_vertical_orientation_stacks():
    svg = render_diagram({"type": "flow_diagram", "params": {
        "orientation": "vertical",
        "steps": ["甲", "乙", "丙", "丁", "戊"]}})
    import re
    w, h = re.search(r'width="(\d+)" height="(\d+)"', svg).groups()
    assert int(h) > int(w)  # taller than wide when stacked


def test_empty_steps_is_safe():
    svg = render_diagram({"type": "flow_diagram", "params": {"steps": []}})
    assert svg.startswith("<svg")  # no crash, minimal doc


class TestWordAwareWrap:
    """Latin labels must wrap on word boundaries; CJK stays character-greedy.

    Regression: `_wrap` counted ASCII as half-width and broke purely on the
    character budget, so English diagram labels came out mid-word
    ("Molecules collid" / "e") on every generated English deck.
    """

    def test_latin_label_breaks_at_space(self):
        assert _wrap("Molecules collide", 8, 2) == ["Molecules", "collide"]

    def test_latin_description_breaks_at_space(self):
        assert _wrap("billions of times a second", 12, 3) == [
            "billions of times a",
            "second",
        ]

    def test_short_enough_text_stays_on_one_line(self):
        assert _wrap("Magnetron", 8, 2) == ["Magnetron"]

    def test_cjk_keeps_character_greedy_wrapping(self):
        # No spaces to break on — behaviour must be unchanged.
        assert _wrap("填制凭证审核原始凭证", 8, 2) == ["填制凭证审核原始", "凭证"]

    def test_unbreakable_long_word_still_hard_breaks(self):
        assert _wrap("Supercalifragilistic", 8, 2) == ["Supercalifragili", "stic"]

    def test_max_lines_is_respected(self):
        assert len(_wrap("one two three four five six seven", 6, 2)) == 2


class TestTitleFitsCanvas:
    """A long title must widen the canvas instead of overflowing the viewBox.

    Regression: a vertical flow is only one box wide (214px), so an ordinary
    title ("How the heat actually happens") ran past the SVG edge and rendered
    visibly cut off — "w the heat actually happ" — in a published short.
    """

    def _view_width(self, svg: str) -> float:
        import re

        return float(re.search(r'viewBox="([^"]+)"', svg).group(1).split()[2])

    def _hint(self, title: str, orientation: str | None = None):
        params = {
            "title": title,
            "steps": [{"label": "One"}, {"label": "Two"}, {"label": "Three"}],
        }
        if orientation:
            params["orientation"] = orientation
        return {"type": "flow_diagram", "params": params}

    def test_vertical_canvas_widens_for_long_title(self):
        from straightedge.diagrams.templates.flow_diagram import MARGIN, TITLE_FONT_PX, _text_width

        title = "How the heat actually happens"
        svg = render_diagram(self._hint(title, "vertical"))
        assert self._view_width(svg) >= _text_width(title, TITLE_FONT_PX) + 2 * MARGIN

    def test_short_title_does_not_shrink_the_grid(self):
        # Grid still sets the width when the title is narrower than the boxes.
        narrow = self._view_width(render_diagram(self._hint("Flow", "vertical")))
        assert narrow == 214  # MARGIN*2 + BOX_W

    def test_horizontal_layout_unchanged_by_ordinary_title(self):
        svg = render_diagram(self._hint("How the heat actually happens"))
        # 3 boxes across already exceed the title width.
        assert self._view_width(svg) == 24 * 2 + 3 * 166 + 2 * 46

    def test_cjk_title_counts_as_full_width(self):
        from straightedge.diagrams.templates.flow_diagram import TITLE_FONT_PX, _text_width

        assert _text_width("会计核算流程", TITLE_FONT_PX) == 6 * TITLE_FONT_PX

    def test_empty_title_has_zero_width(self):
        from straightedge.diagrams.templates.flow_diagram import _text_width

        assert _text_width("", 19) == 0.0
