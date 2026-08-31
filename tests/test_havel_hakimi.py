from straightedge import list_templates
from straightedge.diagrams import render_diagram
from straightedge.diagrams.registry import refusal_findings
from straightedge.diagrams.templates.havel_hakimi import frames


def test_course_sequence_draws_reductions_and_optional_realization():
    svg = render_diagram({"type": "havel_hakimi", "params": {
        "sequence": [3, 3, 2, 2, 2], "realize": True}})
    assert "Remove 3" in svg and "Join 1" in svg
    trace = frames({"sequence": [3, 3, 2, 2, 2], "realize": True})
    assert trace[1]["visual"]["params"]["values"] == [2, 2, 1, 1]
    assert trace[-1]["visual"]["type"] == "graph"


def test_failing_course_sequence_names_the_negative_panel():
    finding = refusal_findings("havel_hakimi", {"sequence": [3, 3, 3, 1]})[0]
    assert finding.check == "havel_hakimi_sequence"
    assert finding.label == "(1, -1)"


def test_template_catalog_publishes_the_surface():
    template = {item.id: item for item in list_templates()}["havel_hakimi"]
    assert {"sequence", "realize", "animate"} <= set(template.params)
    assert template.motion == "optional"


def test_realization_frames_use_styled_node_states():
    """`frontier` is a step role, not a graph-template state: passed through
    raw it reached the renderer with no CSS rule behind it, so the vertices
    being joined drew exactly like untouched ones."""
    trace = frames({"sequence": [3, 3, 2, 2, 2], "realize": True})
    states = {state for frame in trace if frame["visual"]["type"] == "graph"
              for state in frame["visual"]["params"]["highlights"]["nodes"].values()}
    assert "frontier" not in states
    assert "target" in states and "current" in states
