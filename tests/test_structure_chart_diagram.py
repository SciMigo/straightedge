"""Tests for the structure_chart diagram template (结构图 / 思维导图)."""

from straightedge.diagrams import render_diagram
from straightedge.diagrams.registry import DIAGRAM_REGISTRY


def _hint(**params):
    return {"type": "structure_chart", "params": params}


def test_registered():
    assert "structure_chart" in DIAGRAM_REGISTRY


def test_renders_root_and_children():
    svg = render_diagram(_hint(
        root="项目融资",
        title="项目融资的四个特点",
        children=[
            {"term": "有限追索", "desc": "依赖项目现金流偿债"},
            {"term": "风险分担", "desc": "各方分担风险"},
            {"term": "表外融资"},
            {"term": "结构复杂"},
        ],
    ))
    assert svg.startswith("<svg")
    assert svg.rstrip().endswith("</svg>")
    for t in ("项目融资", "有限追索", "风险分担", "表外融资", "结构复杂"):
        assert t in svg


def test_child_aliases_and_bare_strings():
    svg = render_diagram(_hint(
        root="X",
        children=["A", "B", {"name": "C", "description": "d", "subitems": ["p1"]}],
    ))
    assert all(t in svg for t in ("A", "B", "C", "d", "p1"))


def test_nodes_alias_for_children():
    svg = render_diagram(_hint(root="X", nodes=[{"label": "Alpha"}]))
    assert "Alpha" in svg


def test_empty_children_returns_minimal_svg():
    svg = render_diagram(_hint(root="X", children=[]))
    assert svg.startswith("<svg")
    # no card content, just a tiny placeholder document
    assert "structure-chart" in svg


def test_width_grows_with_child_count():
    import re

    def width(n):
        svg = render_diagram(_hint(
            root="R", children=[{"term": f"c{i}"} for i in range(n)]))
        return int(re.search(r'width="(\d+)"', svg).group(1))

    assert width(5) > width(2)


def test_long_description_wraps_without_overflow():
    # A long CJK desc must be split into multiple <text> lines, not one run.
    long_desc = "贷款人主要依赖项目自身的现金流和资产作为偿还贷款的保证而非发起人的整体信用"
    svg = render_diagram(_hint(root="X", children=[{"term": "T", "desc": long_desc}]))
    assert svg.count('class="sc-desc"') >= 2


def test_latin_description_wraps_on_words():
    svg = render_diagram(_hint(
        root="Funding",
        children=[{"term": "Recourse", "desc": "lenders rely on project cash flows only"}],
    ))
    # words stay intact across wrapped lines
    assert "project" in svg and "lenders" in svg
