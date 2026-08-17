"""Tests for the accounting/business diagram templates (t_account / cycle /
comparison) added for the courseware graphics upgrade."""
from __future__ import annotations

import xml.dom.minidom as minidom

import straightedge.diagrams.templates  # noqa: F401  (registers templates)
from straightedge.diagrams.registry import DIAGRAM_REGISTRY, render_diagram


def _wellformed(svg: str) -> None:
    assert svg.strip().startswith("<svg")
    minidom.parseString(svg)  # raises on malformed XML


def test_all_registered():
    for name in ("t_account", "cycle_diagram", "comparison", "timeline"):
        assert name in DIAGRAM_REGISTRY


# -- timeline --------------------------------------------------------------

def test_timeline_renders_events_dates_labels():
    svg = render_diagram({"type": "timeline", "params": {
        "title": "会计发展简史",
        "events": [
            {"date": "远古", "label": "结绳记事", "desc": "简单计数"},
            {"date": "1494", "label": "复式记账", "desc": "帕乔利"},
            {"date": "当代", "label": "会计信息化", "desc": "智能财务"}]}})
    _wellformed(svg)
    for s in ("结绳记事", "复式记账", "会计信息化", "1494", "远古"):
        assert s in svg


def test_timeline_needs_two_events():
    svg = render_diagram({"type": "timeline",
                          "params": {"events": [{"label": "只有一个"}]}})
    _wellformed(svg)  # degrades to placeholder


# -- t_account -------------------------------------------------------------

def test_t_account_renders_debit_credit():
    svg = render_diagram({"type": "t_account", "params": {
        "title": "借贷记账",
        "accounts": [
            {"name": "银行存款",
             "debit": [{"text": "收到投资", "amount": "100000"}],
             "credit": [{"text": "购买设备", "amount": "60000"}]}]}})
    _wellformed(svg)
    assert "银行存款" in svg and "借方" in svg and "贷方" in svg
    assert "100000" in svg and "收到投资" in svg


def test_t_account_single_account_top_level():
    svg = render_diagram({"type": "t_account", "params": {
        "name": "现金", "debit": ["期初余额"], "credit": ["付工资"]}})
    _wellformed(svg)
    assert "现金" in svg and "期初余额" in svg and "付工资" in svg


def test_t_account_empty_degrades():
    svg = render_diagram({"type": "t_account", "params": {}})
    _wellformed(svg)  # placeholder, not a crash


# -- cycle_diagram ---------------------------------------------------------

def test_cycle_diagram_renders_steps_and_hub():
    svg = render_diagram({"type": "cycle_diagram", "params": {
        "title": "会计循环", "center": "循环",
        "steps": [{"label": "填制凭证"}, {"label": "登记账簿"},
                  {"label": "试算平衡"}, {"label": "编制报表"}]}})
    _wellformed(svg)
    for s in ("填制凭证", "登记账簿", "试算平衡", "编制报表"):
        assert s in svg
    assert "循环" in svg  # hub label
    assert "cy-arrow" in svg  # arrows between nodes


def test_cycle_diagram_needs_two_steps():
    svg = render_diagram({"type": "cycle_diagram",
                          "params": {"steps": [{"label": "只有一个"}]}})
    _wellformed(svg)  # degrades to placeholder


# -- comparison ------------------------------------------------------------

def test_comparison_two_columns():
    svg = render_diagram({"type": "comparison", "params": {
        "title": "两种确认基础",
        "columns": [
            {"label": "权责发生制", "points": ["按权责期确认", "反映经营成果"]},
            {"label": "收付实现制", "points": ["按收付确认", "核算简单"]}]}})
    _wellformed(svg)
    assert "权责发生制" in svg and "收付实现制" in svg
    assert "反映经营成果" in svg and "核算简单" in svg


def test_comparison_caps_at_three_columns():
    cols = [{"label": f"列{i}", "points": ["x"]} for i in range(5)]
    svg = render_diagram({"type": "comparison", "params": {"columns": cols}})
    _wellformed(svg)
    # only the first three are drawn (header labels)
    assert "列0" in svg and "列2" in svg and "列4" not in svg


def test_comparison_accepts_nested_side_objects():
    """The shape a live kepu short actually emitted, twice, rendering blank.

    ``left``/``right`` as objects rather than ``left_label``/``left_items``.
    """
    svg = render_diagram({"type": "comparison", "params": {
        "title": "One Minute In The Same Microwave",
        "left": {"label": "Two hundred grams soup",
                 "items": ["absorbs twenty-five thousand joules",
                           "warms about thirty degrees Celsius"]},
        "right": {"label": "Five hundred grams dry plate",
                  "items": ["absorbs two thousand joules"]},
        "style": "dark_board", "accent": "orange"}})
    _wellformed(svg)
    assert len(svg) > 400, "a populated comparison is not a 120-byte blank card"
    assert "Two hundred grams soup" in svg and "Five hundred grams dry plate" in svg
    # Long points wrap, so assert on words rather than the whole phrase.
    assert "twenty-five" in svg and "joules" in svg
    assert "thirty" in svg and "Celsius" in svg
    # Wrapping must not split a word: no line ends mid-token.
    assert "joules" in svg and "j</text>" not in svg


def test_comparison_accepts_a_bare_string_side():
    svg = render_diagram({"type": "comparison", "params": {
        "left": "Absorbs microwaves", "right": "Stays cool"}})
    _wellformed(svg)
    assert "Absorbs microwaves" in svg and "Stays cool" in svg


def test_comparison_accepts_a_bare_list_side():
    svg = render_diagram({"type": "comparison", "params": {
        "left": ["water molecules rotate"], "right": ["ceramic lattice does not"]}})
    _wellformed(svg)
    assert "water molecules rotate" in svg and "ceramic lattice does not" in svg


def test_comparison_prefixed_keys_still_win_over_nested():
    """A spec carrying both shapes must not lose the explicit one."""
    svg = render_diagram({"type": "comparison", "params": {
        "left_label": "explicit", "left_items": ["explicit point"],
        "left": {"label": "nested", "items": ["nested point"]},
        "right_label": "other"}})
    _wellformed(svg)
    assert "explicit" in svg and "explicit point" in svg
    assert "nested" not in svg


def test_comparison_with_no_usable_side_still_reports_empty():
    """The empty-card detector must keep firing for genuinely empty params."""
    svg = render_diagram({"type": "comparison", "params": {
        "style": "dark_board", "accent": "orange"}})
    _wellformed(svg)
    assert len(svg) < 400
