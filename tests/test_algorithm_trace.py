"""A checked storyboard for the CS figure family."""
from __future__ import annotations

import re
from xml.etree import ElementTree as ET

import pytest

from straightedge.catalog import list_templates
from straightedge.diagrams import DIAGRAM_REGISTRY, render_diagram
from straightedge.diagrams.registry import count_data_marks
from straightedge.diagrams.templates.algorithm_trace import inspect_algorithm_trace


def array_step(values, label="state", **extra):
    return {"label": label, "visual": {"type": "array_state",
                                        "params": {"values": values, **extra}}}


def value_step(visual_type, values, label="state"):
    return {"label": label, "visual": {"type": visual_type,
                                         "params": {"values": values}}}


def test_it_is_registered_and_catalogued_with_a_working_example():
    assert "algorithm_trace" in DIAGRAM_REGISTRY
    template = next(t for t in list_templates() if t.id == "algorithm_trace")
    assert {"steps", "layout", "columns", "panel_width", "panel_height"} <= set(template.params)
    svg = render_diagram(template.example)
    assert count_data_marks(svg) >= 3


def test_a_checked_sorting_trace_embeds_one_isolated_svg_per_step():
    steps = [
        array_step([4, 2, 3], "Compare", highlights={"0-1": "comparison"}),
        array_step([2, 4, 3], "Swapped", highlights={"1": "current"}),
        array_step([2, 3, 4], "Settled", highlights={"2": "found"}),
    ]
    steps[0]["transition"] = {"type": "swap", "indices": [0, 1]}
    steps[1]["transition"] = {"type": "swap", "indices": [1, 2]}
    svg = render_diagram({"type": "algorithm_trace",
                          "params": {"title": "Bubble sort", "steps": steps}})
    ET.fromstring(svg)
    assert svg.count("data:image/svg+xml;base64,") == 3
    assert all(label in svg for label in ("Compare", "Swapped", "Settled"))
    assert "swap 0 ↔ 1" in svg and "swap 1 ↔ 2" in svg


@pytest.mark.parametrize("visual_type,transition,next_values", [
    ("array_state", {"type": "swap", "indices": [0, 2]}, [3, 2, 1]),
    ("stack", {"type": "push", "value": 3}, [1, 2, 3]),
    ("stack", {"type": "pop", "value": 2}, [1]),
    ("queue", {"type": "enqueue", "value": 3}, [1, 2, 3]),
    ("queue", {"type": "enqueue", "value": 0, "end": "front"}, [0, 1, 2]),
    ("queue", {"type": "dequeue", "value": 1}, [2]),
    ("queue", {"type": "dequeue", "value": 2, "end": "back"}, [1]),
])
def test_supported_transitions_are_verified(visual_type, transition, next_values):
    before = [1, 2, 3] if transition["type"] == "swap" else [1, 2]
    params = {"steps": [value_step(visual_type, before),
                        value_step(visual_type, next_values)]}
    params["steps"][0]["transition"] = transition
    assert inspect_algorithm_trace(params) == []


def test_a_false_transition_is_refused_with_a_json_path():
    params = {"steps": [array_step([4, 2]), array_step([4, 2])]}
    params["steps"][0]["transition"] = {"type": "swap", "indices": [0, 1]}
    [finding] = inspect_algorithm_trace(params)
    assert finding["code"] == "STATE_TRANSITION_MISMATCH"
    assert finding["path"] == "$.steps[0].transition"
    assert render_diagram({"type": "algorithm_trace", "params": params}) == "" or \
        count_data_marks(render_diagram({"type": "algorithm_trace", "params": params})) == 0


def test_an_operation_cannot_claim_the_wrong_data_structure():
    params = {"steps": [array_step([1, 2]), array_step([1, 2, 3])]}
    params["steps"][0]["transition"] = {"type": "push", "value": 3}
    [finding] = inspect_algorithm_trace(params)
    assert finding["code"] == "STATE_TRANSITION_MISMATCH"
    assert "stack" in finding["message"]


def test_a_blank_child_names_the_step_that_needs_repair():
    params = {"steps": [{"visual": {"type": "graph", "params": {}}}]}
    [finding] = inspect_algorithm_trace(params)
    assert finding == {
        "code": "BLANK_STEP",
        "severity": "error",
        "message": "the child visual drew no data marks; check its params",
        "path": "$.steps[0].visual.params",
    }


@pytest.mark.parametrize("visual_type", ["array_state", "binary_tree", "graph",
                                          "linked_list", "stack", "queue", "dp_table"])
def test_it_composes_existing_cs_renderers(visual_type):
    examples = {t.id: t.example for t in list_templates() if t.lane == "figure"}
    child = examples[visual_type]
    step = {"label": visual_type, "visual": child}
    svg = render_diagram({"type": "algorithm_trace", "params": {"steps": [step]}})
    assert count_data_marks(svg) > 0
    assert "data:image/svg+xml;base64," in svg


def test_grid_dimensions_are_bounded_and_deterministic():
    steps = [array_step([i, i + 1], f"Step {i}") for i in range(7)]
    params = {"steps": steps, "columns": 3, "panel_width": 280, "panel_height": 180}
    first = render_diagram({"type": "algorithm_trace", "params": params})
    second = render_diagram({"type": "algorithm_trace", "params": params})
    assert first == second
    match = re.search(r'width="(\d+)" height="(\d+)"', first)
    assert match and int(match.group(1)) <= 1050 and int(match.group(2)) < 1000


@pytest.mark.parametrize("steps,code", [
    ([], "MISSING_STEPS"),
    ([{"label": "missing"}], "MISSING_VISUAL"),
    ([{"visual": {"type": "no-such-template", "params": {}}}], "UNKNOWN_VISUAL"),
    ([{"visual": {"type": "algorithm_trace", "params": {}}}], "RECURSIVE_TRACE"),
])
def test_bad_storyboard_shapes_are_explained(steps, code):
    assert inspect_algorithm_trace({"steps": steps})[0]["code"] == code


@pytest.mark.parametrize("extra,code,path", [
    ({"layout": "spiral"}, "INVALID_LAYOUT", "$.layout"),
    ({"columns": 0}, "INVALID_COLUMNS", "$.columns"),
    ({"panel_width": "wide"}, "INVALID_PANEL_SIZE", "$.panel_width"),
])
def test_layout_errors_are_structured(extra, code, path):
    [finding] = inspect_algorithm_trace({"steps": [array_step([1])], **extra})
    assert finding["code"] == code and finding["path"] == path
