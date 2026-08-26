from straightedge import list_templates
from straightedge.diagrams import render_diagram
from straightedge.diagrams.registry import refusal_findings
from straightedge.diagrams.templates.mycielski import frames


C5 = {"nodes": [{"id": str(i)} for i in range(5)],
      "edges": [{"from": str(i), "to": str((i + 1) % 5)} for i in range(5)]}


def test_c5_constructs_and_colors_the_grotzsch_graph():
    svg = render_diagram({"type": "mycielski", "params": {**C5, "animate": False}})
    assert "Three layers" in svg and "Color w" in svg
    final = frames(C5)[-1]["visual"]["params"]
    assert len(final["nodes"]) == 11 and len(final["edges"]) == 20
    assert set(final["highlights"]["nodes"].values()) == {
        "color-1", "color-2", "color-3", "color-4"}


def test_output_cap_refusal_reports_base_and_result_counts():
    finding = refusal_findings("mycielski", {
        "nodes": [{"id": str(i)} for i in range(6)],
        "edges": [{"from": str(i), "to": str((i + 1) % 6)} for i in range(6)]})[0]
    assert "13 vertices" in finding.message and finding.label == "6→13"


def test_catalog_publishes_the_template_surface():
    template = {item.id: item for item in list_templates()}["mycielski"]
    assert {"nodes", "edges", "animate"} <= set(template.params)
    assert template.motion == "optional"
