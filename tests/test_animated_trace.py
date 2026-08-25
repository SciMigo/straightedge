"""The lightweight animation lane composes existing SVG figures."""

import re

from straightedge.diagrams import DIAGRAM_REGISTRY, render_diagram
from straightedge.diagrams.registry import refusal_findings


def _frame(value):
    return {
        "label": f"state {value}",
        "visual": {"type": "array_state", "params": {"values": [value, value + 1]}},
    }


def test_template_is_registered():
    assert "animated_trace" in DIAGRAM_REGISTRY


def test_frames_are_embedded_with_smil_timelines():
    svg = render_diagram({
        "type": "animated_trace",
        "params": {"frames": [_frame(1), _frame(2)], "duration_s": 1, "loop": True},
    })
    assert "class=\"diagram animated-trace\"" in svg
    assert svg.count("data:image/svg+xml;base64,") == 2
    assert svg.count("<animate ") == 2
    assert 'dur="2.000s"' in svg
    assert 'repeatCount="indefinite"' in svg


def test_non_looping_animation_freezes_on_the_final_frame():
    svg = render_diagram({
        "type": "animated_trace",
        "params": {"frames": [_frame(1), _frame(2)], "loop": False},
    })
    assert 'repeatCount="1"' in svg
    animations = re.findall(r'<animate [^>]+>', svg)
    assert animations[-1].count("1;1") >= 1


def test_unknown_child_is_refused():
    params = {"frames": [{"visual": {"type": "not-a-template"}}]}
    findings = refusal_findings("animated_trace", params)
    assert findings[0].check == "animation_frame"
    assert render_diagram({"type": "animated_trace", "params": params}) == ""


def test_child_refusal_is_preserved():
    params = {"frames": [{"visual": {"type": "graph", "params": {
        "nodes": [{"id": x} for x in "ABC"],
        "edges": [{"from": "A", "to": "B"}, {"from": "B", "to": "C"},
                  {"from": "C", "to": "A"}],
        "layout": "bipartite",
    }}}]}
    findings = refusal_findings("animated_trace", params)
    assert findings[0].check == "animation_child"
    assert "bipartition" in findings[0].message


def test_duration_must_be_positive_and_finite():
    for value in (0, -1, float("inf"), True):
        findings = refusal_findings("animated_trace", {"frames": [_frame(1)],
                                                        "duration_s": value})
        assert findings[0].check == "animation_duration"


def test_trace_cannot_contain_itself():
    params = {"frames": [{"visual": {"type": "animated_trace", "params": {}}}]}
    assert refusal_findings("animated_trace", params)[0].check == "animation_frame"
