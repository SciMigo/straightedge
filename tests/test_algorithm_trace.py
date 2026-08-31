"""A checked storyboard for the CS figure family."""
from __future__ import annotations

import json
import re
from xml.etree import ElementTree as ET

import pytest

from straightedge import cli, mcp_server
from straightedge.catalog import list_templates
from straightedge.diagrams import DIAGRAM_REGISTRY, render_diagram
from straightedge.diagrams.legibility import check_figure, smallest_font_px
from straightedge.diagrams.registry import count_data_marks
from straightedge.diagrams.templates.algorithm_trace import inspect_algorithm_trace


def array_step(values, label="state", **extra):
    return {"label": label, "visual": {"type": "array_state",
                                        "params": {"values": values, **extra}}}


def value_step(visual_type, values, label="state"):
    return {"label": label, "visual": {"type": visual_type,
                                         "params": {"values": values}}}


def priority_step(items):
    return {"visual": {"type": "priority_queue", "params": {
        "items": items, "operations": [], "animate": False,
    }}}


def graph_visual(states):
    return {"type": "graph", "params": {
        "nodes": [{"id": node} for node in "ABC"],
        "edges": [{"from": "A", "to": "B"}, {"from": "A", "to": "C"}],
        "layout": "hierarchical",
        "highlights": {"nodes": states},
    }}


def graph_queue_step(states, values, label="state"):
    return {"label": label, "visual": [
        graph_visual(states),
        {"type": "queue", "params": {"values": values}},
    ]}


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
    assert count_data_marks(render_diagram({"type": "algorithm_trace", "params": params})) == 0


def test_an_operation_cannot_claim_the_wrong_data_structure():
    params = {"steps": [array_step([1, 2]), array_step([1, 2, 3])]}
    params["steps"][0]["transition"] = {"type": "push", "value": 3}
    [finding] = inspect_algorithm_trace(params)
    assert finding["code"] == "STATE_TRANSITION_MISMATCH"
    assert "stack" in finding["message"]


class TestGraphAndContainerTransitions:
    def test_a_checked_bfs_trace_renders_composite_steps(self):
        steps = [
            graph_queue_step({"A": "frontier"}, ["A"], "Start"),
            graph_queue_step({"A": "visited"}, [], "Visit A"),
            graph_queue_step({"A": "visited", "B": "frontier"}, ["B"], "Discover B"),
            graph_queue_step({"A": "visited", "B": "visited"}, [], "Visit B"),
        ]
        steps[0]["transition"] = {"type": "dequeue", "value": "A"}
        steps[1]["transition"] = {"type": "enqueue", "value": "B"}
        steps[2]["transition"] = {"type": "dequeue", "value": "B"}
        params = {"steps": steps, "layout": "column", "panel_width": 1180}
        assert inspect_algorithm_trace(params) == []
        svg = render_diagram({"type": "algorithm_trace", "params": params})
        assert count_data_marks(svg) > 0 and svg.count("<image") == len(steps)
        assert smallest_font_px(svg, 1180) >= 11

    def test_discover_checks_the_edge_and_frontier_state(self):
        steps = [
            {"visual": graph_visual({"A": "visited"}),
             "transition": {"type": "discover", "node": "B", "from": "A"}},
            {"visual": graph_visual({"A": "visited", "B": "frontier"})},
        ]
        assert inspect_algorithm_trace({"steps": steps}) == []
        steps[1]["visual"]["params"]["highlights"]["nodes"]["B"] = "visited"
        [finding] = inspect_algorithm_trace({"steps": steps})
        assert finding["code"] == "STATE_TRANSITION_MISMATCH"
        assert "frontier" in finding["message"]

    def test_discover_respects_explicit_neighbor_order(self):
        before = graph_visual({"A": "visited"})
        before["params"]["neighbor_order"] = ["A", "C", "B"]
        after = graph_visual({"A": "visited", "B": "frontier"})
        steps = [{"visual": before,
                  "transition": {"type": "discover", "node": "B", "from": "A"}},
                 {"visual": after}]
        [finding] = inspect_algorithm_trace({"steps": steps})
        assert "expected 'C'" in finding["message"]

    def test_a_visited_node_cannot_revert(self):
        steps = [
            {"visual": graph_visual({"A": "visited", "B": "frontier"}),
             "transition": {"type": "settle", "node": "B"}},
            {"visual": graph_visual({"A": "unvisited", "B": "settled"})},
        ]
        [finding] = inspect_algorithm_trace({"steps": steps})
        assert "must stay visited" in finding["message"]

    def test_a_wrong_dequeue_order_is_refused_across_both_children(self):
        steps = [
            graph_queue_step({"A": "frontier", "B": "frontier"}, ["A", "B"]),
            graph_queue_step({"A": "frontier", "B": "visited"}, ["A"]),
        ]
        steps[0]["transition"] = {"type": "dequeue", "value": "B"}
        [finding] = inspect_algorithm_trace({"steps": steps})
        assert finding["code"] == "STATE_TRANSITION_MISMATCH"
        assert "removes" in finding["message"]


def test_priority_queue_transitions_are_checked_between_trace_steps():
    before = priority_step([{"id": "A", "priority": 5}, {"id": "B", "priority": 2}])
    changed = priority_step([{"id": "A", "priority": 1}, {"id": "B", "priority": 2}])
    before["transition"] = {"type": "decrease_key", "id": "A", "priority": 1}
    assert inspect_algorithm_trace({"steps": [before, changed]}) == []
    changed["transition"] = {"type": "pop_min", "value": "A"}
    after = priority_step([{"id": "B", "priority": 2}])
    assert inspect_algorithm_trace({"steps": [changed, after]}) == []
    changed["transition"]["value"] = "B"
    [finding] = inspect_algorithm_trace({"steps": [changed, after]})
    assert "not 'A'" in finding["message"]


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


VESICA = ["A = 0, 0", "B = 1, 0", "( A B )", "( B A ) -> C D", "[ C D ]", "[ A B ]"]


def false_swap():
    params = {"steps": [array_step([4, 2]), array_step([4, 2])]}
    params["steps"][0]["transition"] = {"type": "swap", "indices": [0, 1]}
    return params


class TestARefusalSaysWhyOnEveryTransport:
    """The inspector's findings are worth nothing if only Python callers see them.

    `draw` over MCP and the CLI report a blank figure as a parameter-shape
    mismatch, which for a refused trace sends the caller to fix parameters
    that are already right. The template exposes its findings the way
    `construction` does, and both transports carry them.
    """

    def test_the_mcp_draw_tool_reports_the_finding_and_its_path(self):
        out = mcp_server._guarded(lambda: mcp_server._draw_payload(
            "algorithm_trace", false_swap()))
        error = out["error"]
        assert error["code"] == "blank_figure"
        assert "refused" in error["message"] and "[2, 4]" in error["message"]
        assert "parameter" not in error["remedy"].split("The parameters")[0]
        [finding] = error["details"]["findings"]
        assert finding["check"] == "trace:state_transition_mismatch"
        assert finding["label"] == "$.steps[0].transition"

    def test_the_cli_reports_the_same_refusal(self, capsys):
        code = cli.main(["draw", "algorithm_trace", "--json", "--params",
                         json.dumps(false_swap())])
        error = json.loads(capsys.readouterr().out)["error"]
        assert code != 0 and error["code"] == "blank_figure"
        assert "refused" in error["message"]
        assert "parameters are not the problem" in error["remedy"]
        assert "trace:state_transition_mismatch [$.steps[0].transition]" in \
            error["details"]["findings"][0]

    def test_a_construction_refusal_still_names_its_claim(self):
        """Generalising the hook must not cost the template it was built for."""
        out = mcp_server._guarded(lambda: mcp_server._draw_payload(
            "construction", {"steps": VESICA, "claims": [
                {"claim": "parallel", "of": ["[ C D ]", "[ A B ]"]}]}))
        assert out["error"]["details"]["findings"][0]["check"] == "claim:parallel"
        assert "verify_construction" in out["error"]["remedy"]


class TestThePanelMustAgreeWithTheTransition:
    """`stack` and `queue` draw an `operation`; the arrow between panels must
    describe the same one, or the storyboard illustrates a falsehood the
    values alone cannot catch."""

    def test_an_enqueue_drawn_at_the_front_cannot_claim_the_back(self):
        params = {"steps": [
            {"visual": {"type": "queue", "params": {
                "values": [1, 2, 3],
                "operation": {"type": "enqueue", "value": 9, "end": "front"}}},
             "transition": {"type": "enqueue", "value": 9}},
            value_step("queue", [1, 2, 3, 9])]}
        [finding] = inspect_algorithm_trace(params)
        assert finding["code"] == "STATE_TRANSITION_MISMATCH"
        assert "front" in finding["message"] and "back" in finding["message"]

    def test_a_panel_drawing_another_value_is_refused(self):
        params = {"steps": [
            {"visual": {"type": "stack", "params": {
                "values": [1, 2], "operation": {"type": "push", "value": 7}}},
             "transition": {"type": "push", "value": 3}},
            value_step("stack", [1, 2, 3])]}
        [finding] = inspect_algorithm_trace(params)
        assert "7" in finding["message"] and "3" in finding["message"]

    def test_an_agreeing_operation_passes(self):
        params = {"steps": [
            {"visual": {"type": "queue", "params": {
                "values": [1, 2], "operation": {"type": "enqueue", "value": 3}}},
             "transition": {"type": "enqueue", "value": 3, "end": "back"}},
            value_step("queue", [1, 2, 3])]}
        assert inspect_algorithm_trace(params) == []


class TestTransitionVocabularyIsWhatTheDocsSay:
    @pytest.mark.parametrize("transition,fragment", [
        ({"type": "enqueue", "value": 0, "end": "left"}, "front or back"),
        ({"type": "enqueue", "value": 0, "end": ""}, "front or back"),
        ({"type": "dequeue", "end": "top"}, "front or back"),
    ])
    def test_queue_ends_are_front_or_back_only(self, transition, fragment):
        before = [1, 2]
        after = ([0] + before if transition["type"] == "enqueue" else before[1:])
        params = {"steps": [value_step("queue", before), value_step("queue", after)]}
        params["steps"][0]["transition"] = transition
        [finding] = inspect_algorithm_trace(params)
        assert fragment in finding["message"]

    def test_ends_are_read_case_insensitively_like_types(self):
        params = {"steps": [value_step("queue", [1, 2]), value_step("queue", [1, 2, 3])]}
        params["steps"][0]["transition"] = {"type": "Enqueue", "value": 3, "end": "Back"}
        assert inspect_algorithm_trace(params) == []

    def test_a_stack_operation_does_not_take_an_end(self):
        params = {"steps": [value_step("stack", [1, 2]), value_step("stack", [1, 2, 0])]}
        params["steps"][0]["transition"] = {"type": "push", "value": 0, "end": "bottom"}
        [finding] = inspect_algorithm_trace(params)
        assert "does not take end" in finding["message"]

    def test_swap_indices_are_integers_not_booleans(self):
        params = {"steps": [array_step([1, 2]), array_step([2, 1])]}
        params["steps"][0]["transition"] = {"type": "swap", "indices": [True, False]}
        [finding] = inspect_algorithm_trace(params)
        assert "two integer indices" in finding["message"]


class TestEveryShapeMistakeIsAFindingNotACrash:
    @pytest.mark.parametrize("extra,code", [
        ({"layout": ["row"]}, "INVALID_LAYOUT"),
        ({"panel_width": float("nan")}, "INVALID_PANEL_SIZE"),
        ({"panel_height": float("inf")}, "INVALID_PANEL_SIZE"),
        ({"columns": True}, "INVALID_COLUMNS"),
    ])
    def test_unhashable_and_non_finite_values_are_reported(self, extra, code):
        [finding] = inspect_algorithm_trace({"steps": [array_step([1])], **extra})
        assert finding["code"] == code

    def test_a_null_layout_means_the_default(self):
        assert inspect_algorithm_trace({"steps": [array_step([1])], "layout": None}) == []

    def test_every_step_is_checked_even_past_the_cap(self):
        steps = [array_step([1]) for _ in range(14)]
        steps[13] = {"label": "no visual"}
        codes = {f["code"] for f in inspect_algorithm_trace({"steps": steps})}
        assert codes == {"TOO_MANY_STEPS", "MISSING_VISUAL"}


class TestChildrenAreDrawnAsRenderDiagramWouldDrawThem:
    def test_the_flat_envelope_draws_the_child_it_names(self):
        steps = [{"visual": {"type": "array_state", "values": [1, 2]},
                  "transition": {"type": "swap", "indices": [0, 1]}},
                 {"visual": {"type": "array_state", "values": [2, 1]}}]
        assert inspect_algorithm_trace({"steps": steps}) == []
        nested = render_diagram({"type": "algorithm_trace", "params": {"steps": [
            array_step([1, 2]), array_step([2, 1])]}})
        flat = render_diagram({"type": "algorithm_trace", "params": {"steps": steps}})
        assert count_data_marks(flat) == count_data_marks(nested) > 0

    @pytest.mark.parametrize("visual_type", ["array_state", "linked_list"])
    def test_an_empty_child_is_blank_despite_its_arrowhead_marker(self, visual_type):
        """The marker <polygon> in <defs> is not a data mark."""
        [finding] = inspect_algorithm_trace(
            {"steps": [value_step(visual_type, [])]})
        assert finding["code"] == "BLANK_STEP"

    @pytest.mark.parametrize("visual_type", ["stack", "queue"])
    def test_an_empty_container_is_a_visible_algorithm_state(self, visual_type):
        assert inspect_algorithm_trace({"steps": [value_step(visual_type, [])]}) == []

    def test_a_child_that_crashes_says_so_rather_than_check_its_params(self):
        [finding] = inspect_algorithm_trace(
            {"steps": [array_step([1], cell_width="x")]})
        assert finding["code"] == "CHILD_RENDER_ERROR"
        assert "invalid literal" in finding["message"]
        assert finding["path"] == "$.steps[0].visual.params"

    def test_a_child_refused_for_a_false_claim_carries_the_claim(self):
        child = {"visual": {"type": "construction", "params": {
            "steps": VESICA,
            "claims": [{"claim": "parallel", "of": ["[ C D ]", "[ A B ]"]}]}}}
        [finding] = inspect_algorithm_trace({"steps": [child]})
        assert finding["code"] == "CHILD_REFUSED"
        assert "claim:parallel" in finding["message"]

    def test_each_child_is_rendered_exactly_once(self, monkeypatch):
        template = DIAGRAM_REGISTRY["array_state"]
        calls = []
        original = template.render

        def counting(params):
            calls.append(params)
            return original(params)

        monkeypatch.setattr(template, "render", counting)
        steps = [array_step([i, i + 1]) for i in range(3)]
        render_diagram({"type": "algorithm_trace", "params": {"steps": steps}})
        assert len(calls) == 3


class TestTheStoryboardIsAsLegibleAsItsChildren:
    def test_the_checker_sees_text_inside_the_embedded_children(self):
        """A data-URI image is opaque to the legibility check unless it opens
        it — and a storyboard whose every label is invisible to the check
        would pass with nothing to say."""
        examples = {t.id: t.example for t in list_templates() if t.lane == "figure"}
        child = examples["linked_list"]
        alone = {f.check for f in check_figure(render_diagram(child)) if f.severity == "error"}
        assert "text_clipped" in alone, "the corpus figure this test relies on was fixed"
        inside = render_diagram({"type": "algorithm_trace",
                                 "params": {"steps": [{"visual": child}]}})
        assert {f.check for f in check_figure(inside) if f.severity == "error"} == alone

    def test_a_child_shrunk_below_reading_size_is_refused_with_the_numbers(self):
        [finding] = inspect_algorithm_trace({"steps": [array_step(list(range(20)))]})
        assert finding["code"] == "UNREADABLE_STEP"
        assert "1040" in finding["message"] and "%" in finding["message"]
        assert finding["path"] == "$.steps[0].visual"

    def test_panels_are_sized_to_their_children_by_default(self):
        small = render_diagram({"type": "algorithm_trace",
                                "params": {"steps": [array_step([1, 2])]}})
        wide = render_diagram({"type": "algorithm_trace",
                               "params": {"steps": [array_step(list(range(9)))]}})
        widths = [int(re.search(r'width="(\d+)"', svg).group(1)) for svg in (small, wide)]
        assert widths[0] < widths[1]

    def test_an_explicit_panel_width_is_not_clamped(self):
        svg = render_diagram({"type": "algorithm_trace", "params": {
            "layout": "column", "panel_width": 1180,
            "steps": [array_step([1, 2, 3])],
        }})
        image_width = float(re.search(r'<image[^>]+width="([\d.]+)"', svg).group(1))
        assert image_width == 1160

    def test_an_explicit_row_layout_is_not_overridden_by_columns(self):
        steps = [array_step([i]) for i in range(4)]
        row = render_diagram({"type": "algorithm_trace",
                              "params": {"steps": steps, "layout": "row", "columns": 2}})
        assert row.count("<image") == 4
        [(width, height)] = re.findall(r'width="(\d+)" height="(\d+)"', row)[:1]
        assert int(width) > 4 * 220 and int(height) < 400

    def test_a_shortened_label_keeps_its_full_text_as_a_title(self):
        long = "Partition around pivot 37 using the Lomuto scheme, then recurse"
        svg = render_diagram({"type": "algorithm_trace", "params": {
            "title": long, "panel_width": 220,
            "steps": [{"label": long, "visual": array_step([1])["visual"],
                       "transition": {"type": "swap", "indices": [0, 0], "label": long}},
                      array_step([1])]}})
        assert svg.count(f"<title>{long}</title>") == 3
