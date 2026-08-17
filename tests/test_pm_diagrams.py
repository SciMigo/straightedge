"""Tests for the project-management diagrams (CPM engine + SVG templates)."""
from __future__ import annotations

import pytest

from straightedge.diagrams import DIAGRAM_REGISTRY, render_diagram
from straightedge.diagrams.cpm import compute_cpm

# The textbook worked example (Table 6.2) — unique correct schedule.
EXAMPLE = [
    {"id": "A", "duration": 3, "predecessors": []},
    {"id": "B", "duration": 4, "predecessors": ["A"]},
    {"id": "C", "duration": 5, "predecessors": ["A"]},
    {"id": "D", "duration": 2, "predecessors": ["C"]},
    {"id": "E", "duration": 6, "predecessors": ["B", "C"]},
    {"id": "F", "duration": 3, "predecessors": ["B"]},
    {"id": "G", "duration": 3, "predecessors": ["E", "D"]},
    {"id": "H", "duration": 5, "predecessors": ["E", "F"]},
    {"id": "I", "duration": 2, "predecessors": ["H", "G"]},
]


# -- CPM engine -------------------------------------------------------------

def test_cpm_forward_backward_and_critical_path():
    r = compute_cpm(EXAMPLE)
    assert r.project_duration == 21
    assert r.critical_path == ["A", "C", "E", "H", "I"]
    # spot-check the merge node E = max(EF_B=7, EF_C=8) = 8
    assert r.activities["E"].es == 8 and r.activities["E"].ef == 14
    # a non-critical activity has positive float
    assert r.activities["B"].total_float == 1
    assert r.activities["D"].total_float == 6
    # every critical activity has zero float
    assert all(r.activities[a].total_float == 0 for a in r.critical_path)


def test_cpm_levels_for_layout():
    r = compute_cpm(EXAMPLE)
    assert r.levels["A"] == 0
    assert r.levels["B"] == 1 and r.levels["C"] == 1
    assert r.levels["I"] == 4


def test_cpm_string_predecessors_are_parsed():
    # Chinese-style "B、C" and "E,D" predecessor strings must split.
    acts = [
        {"id": "A", "duration": 1, "predecessors": []},
        {"id": "B", "duration": 1, "predecessors": ["A"]},
        {"id": "C", "duration": 1, "predecessors": ["A"]},
        {"id": "E", "duration": 1, "predecessors": "B、C"},
    ]
    r = compute_cpm(acts)
    assert set(r.activities["E"].predecessors) == {"B", "C"}


def test_cpm_raises_on_cycle():
    cyclic = [
        {"id": "X", "duration": 1, "predecessors": ["Y"]},
        {"id": "Y", "duration": 1, "predecessors": ["X"]},
    ]
    with pytest.raises(ValueError):
        compute_cpm(cyclic)


def test_cpm_empty():
    r = compute_cpm([])
    assert r.project_duration == 0 and r.order == []


# -- Templates registered + render well-formed ------------------------------

def test_pm_templates_registered():
    for name in ("project_network", "gantt", "wbs"):
        assert name in DIAGRAM_REGISTRY


def _well_formed(svg: str) -> bool:
    return svg.startswith("<svg") and svg.rstrip().endswith("</svg>")


def test_project_network_renders_with_critical_path():
    svg = render_diagram({"type": "project_network",
                          "params": {"title": "例题", "activities": EXAMPLE}})
    assert _well_formed(svg)
    assert "crit" in svg                 # critical styling applied
    assert "关键路径" in svg and "A→C→E→H→I" in svg
    assert "工期 = 21" in svg


def test_project_network_cycle_is_graceful():
    svg = render_diagram({"type": "project_network", "params": {"activities": [
        {"id": "X", "duration": 1, "predecessors": ["Y"]},
        {"id": "Y", "duration": 1, "predecessors": ["X"]},
    ]}})
    assert _well_formed(svg)
    assert "循环" in svg                 # graceful message, not a crash


def test_gantt_from_activities():
    svg = render_diagram({"type": "gantt", "params": {"activities": EXAMPLE}})
    assert _well_formed(svg)
    assert "g-bar" in svg and "g-bar crit" in svg  # critical bars highlighted


def test_gantt_from_explicit_tasks():
    svg = render_diagram({"type": "gantt", "params": {"tasks": [
        {"name": "基础", "start": 0, "duration": 3, "critical": True},
        {"name": "主体", "start": 3, "duration": 5},
    ]}})
    assert _well_formed(svg)
    assert "基础" in svg and "主体" in svg


def test_wbs_from_root_tree():
    svg = render_diagram({"type": "wbs", "params": {"root": {
        "name": "项目", "children": [
            {"name": "设计", "children": [{"name": "方案"}, {"name": "施工图"}]},
            {"name": "施工"},
        ]}}})
    assert _well_formed(svg)
    assert "项目" in svg and "方案" in svg and "施工图" in svg
    assert "wbs-box root" in svg


def test_wbs_from_flat_nodes():
    svg = render_diagram({"type": "wbs", "params": {"nodes": [
        {"id": "r", "name": "根"},
        {"id": "a", "name": "甲", "parent": "r"},
        {"id": "b", "name": "乙", "parent": "r"},
    ]}})
    assert _well_formed(svg)
    assert "根" in svg and "甲" in svg and "乙" in svg


def test_unknown_diagram_type_returns_empty():
    assert render_diagram({"type": "not_a_real_type", "params": {}}) == ""
