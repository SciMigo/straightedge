"""Legibility across the whole figure lane, not one template at a time.

The animation lane has measured its own frames since the beginning. The figure
lane's only check was ``count_data_marks`` — "did anything get drawn" — so a
figure could put four labels in the same pixels and report success. Three
templates had grown a private version of this in their own test files; thirty-five
had nothing.

This runs :func:`straightedge.diagrams.legibility.check_figure` over every
registered template. It found fourteen errors on the first run, in six templates,
including the two label collisions in ``unit_circle`` and the unclipped geometry
in ``matrix_transform`` that a human reviewer had just reported by eye.

Six of those fourteen were the checker's own fault, and review caught it: it
measured every figure against a frame starting at the origin though a ``viewBox``
need not, and it measured a rotated label where an unrotated one would sit. Both
produced confident coordinates for text that was never outside anything. Eight
errors in four templates remain, and those are real.

That is the argument for the strict list rather than a threshold. A count that
may drift down for two reasons — a template being fixed, or the checker being
wrong — tells you nothing when it moves; a named list that fails when an entry
starts passing makes you look at which happened.

Those four are listed in :data:`KNOWN_ILLEGIBLE` and the list is **strict**: a
template on it that starts passing fails the suite, so the list can only shrink.
An open-ended allowlist is how a check like this becomes decoration.

Warnings are not gated. Text inside its own filled cell is 100% "covered" and
perfectly readable — ``SKILL.md`` says so — and the animation lane treats the
same case the same way. Consistency between the lanes is worth more than tuning
one of them.
"""
from __future__ import annotations

import pytest

from straightedge.diagrams import DIAGRAM_REGISTRY, render_diagram
from straightedge.diagrams.legibility import (
    boxes_from_svg,
    check_figure,
    styles_from_svg,
    unfilled_classes,
)
from straightedge.qc import Finding

#: One representative hint per registered template. Declared rather than
#: discovered: a check over the whole lane needs a figure per template, and
#: `list_templates()` says what *can* be drawn without saying what a good
#: call looks like. Harvested from the per-template suites, so these are the
#: same payloads those tests already trust.
CORPUS: dict[str, dict] = {
    'aoa_work': {"title": "Network", "nodes": [{"id": 1}, {"id": 2}, {"id": 3}], "arcs": [{"from": 1, "to": 2, "name": "Design", "duration": 3}, {"from": 2, "to": 3, "name": "Build", "duration": 5}]},
    'aon_node': {"title": "Activity", "nodes": [{"code": "A", "name": "Design", "duration": 3}, {"code": "B", "name": "Build", "duration": 5}]},
    'architecture_diagram': {"style": "PowerPoint", "layout": "left-to-right", "color_coding": {"services": "light blue", "datastores": "light green", "queues": "light purple", "external_clients": "light gray"}, "elements": [{"id": "mobile_client", "kind": "external", "label": "Mobile Client"}, {"id": "gateway_cluster", "kind": "service_cluster", "label": "Gateway (WebSocket/MQTT)"}, {"id": "chat_service", "kind": "service", "label": "Chat Service"}, {"id": "fanout_queue", "kind": "queue", "label": "Fanout Queue"}, {"id": "presence_service", "kind": "service", "label": "Presence Service"}, {"id": "message_db", "kind": "database", "label": "Message DB (Cassandra)"}, {"id": "session_cache", "kind": "cache", "label": "Session Cache (Redis)"}], "connections": [{"from": "mobile_client", "to": "gateway_cluster", "label": "send message"}, {"from": "gateway_cluster", "to": "chat_service", "label": "route"}, {"from": "chat_service", "to": "message_db", "label": "persist"}, {"from": "chat_service", "to": "fanout_queue", "label": "enqueue"}, {"from": "fanout_queue", "to": "gateway_cluster", "label": "push to recipients"}, {"from": "gateway_cluster", "to": "session_cache", "label": "lookup session"}, {"from": "presence_service", "to": "session_cache", "label": "heartbeat"}], "notes": ["Idempotency via client message id to deduplicate retries", "Fanout queue decouples write latency from recipient count"]},
    'array_state': {"values": [1, 2, 3, 4], "indices": True, "pointers": [{"index": 0, "label": "left", "position": "above"}, {"index": 3, "label": "right", "position": "below"}], "annotations": [{"index": 1, "text": "pivot", "position": "above"}], "brackets": [{"from": 1, "to": 2, "label": "window", "position": "below"}], "caption": "Sliding window"},
    'binary_tree': {"root": {"value": 8, "left": {"value": 3, "right": {"value": 6}}, "right": {"value": 10}}, "highlights": {"8": "visited", "6": "current"}, "path": [8, 3, 6], "pointers": [{"value": 6, "label": "current"}], "annotations": [{"value": 8, "text": "root"}]},
    'call_stack': {"frames": [{"function": "fib", "args": {"n": 5}, "state": "waiting"}, {"function": "fib", "args": {"n": 4}, "state": "waiting"}, {"function": "fib", "args": {"n": 3}, "state": "waiting"}, {"function": "fib", "args": {"n": 2}, "state": "executing", "return": 1}], "highlights": {"3": "current"}, "show_return_values": True, "caption": "fib(2) returns 1"},
    'circle_chord_rational': {"params": {}},
    'comparison': {"title": "两种确认基础", "columns": [{"label": "权责发生制", "points": ["按权责期确认", "反映经营成果"]}, {"label": "收付实现制", "points": ["按收付确认", "核算简单"]}]},
    'construction': {"steps": ["A = 0, 0", "B = 1, 0", "( A B )", "( B A ) -> C D", "[ C D ]", "[ A B ]"], "claims": [{"claim": "perpendicular", "of": ["[ C D ]", "[ A B ]"]}]},
    'coordinate_plane': {"x_min": 0, "x_max": 1.5708, "y_min": -2.2, "y_max": 2.2, "show_grid": True, "title": "Phase choices near x=0", "curves": [{"function": "2*cos(x)", "label": "theta=pi/2", "style": "dashed"}, {"function": "-2*cos(x)", "label": "theta=3pi/2", "style": "solid"}]},
    'cycle_diagram': {"title": "会计循环", "center": "循环", "steps": [{"label": "填制凭证"}, {"label": "登记账簿"}, {"label": "试算平衡"}, {"label": "编制报表"}]},
    'descent_triangles': {"first": {"legs": ["p²−q²", "2pq"], "hyp": "p²+q²", "area": "pq(p−q)(p+q)", "size": 17}, "second": {"legs": ["d−c", "d+c"], "hyp": "2a", "area": "q = b²", "size": 4}, "note": "2a < a⁴+b⁴"},
    'dirichlet_function': {"title": "Dirichlet", "num_points": 40},
    'dp_table': {"values": [[0, 0, 0], [0, 1, 1], [0, 1, 2]], "row_labels": ["", "a", "b"], "col_labels": ["", "a", "b"], "highlights": {"2,2": "current", "1,2": "dependency"}, "arrows": [{"from": [1, 2], "to": [2, 2]}], "formula": "dp[i][j] = max(...)", "caption": "LCS example"},
    'environment_diagram': {"frames": [{"id": "global", "label": "Global", "parent": None, "bindings": [{"name": "make_adder", "value": "func:f0"}, {"name": "add5", "value": "func:f1"}]}, {"id": "f1", "label": "f1: make_adder", "parent": "global", "bindings": [{"name": "n", "value": "5"}]}], "functions": [{"id": "f0", "params": ["n"], "body": "lambda x: x + n", "parent_frame": "global"}, {"id": "f1", "params": ["x"], "body": "x + n", "parent_frame": "f1"}], "highlights": {"frames": {"f1": "current"}, "bindings": {"f1.n": "target"}, "functions": {"f1": "current"}}, "caption": "Environment after add5 = make_adder(5)"},
    'flow_diagram': {"title": "会计核算流程", "steps": [{"label": "填制凭证", "desc": "审核原始凭证"}, {"label": "登记账簿"}, {"label": "编制报表"}]},
    'function_graph': {"function": "sqrt(x)", "x_min": 0, "x_max": 4, "fill_area": [{"from": 0.5, "to": 3.5, "from_label": "a", "to_label": "b"}]},
    'gantt': {"tasks": [{"name": "基础", "start": 0, "duration": 3, "critical": True}, {"name": "主体", "start": 3, "duration": 5}]},
    'graph': {"nodes": [{"id": "0", "label": "start", "x": 0.12, "y": 0.5}, {"id": "1", "label": "H", "x": 0.4, "y": 0.5}, {"id": "2", "label": "HT", "x": 0.68, "y": 0.5}], "edges": [{"from": "0", "to": "1", "weight": "H"}, {"from": "1", "to": "2", "weight": "T"}, {"from": "2", "to": "0", "weight": "T"}], "directed": True, "weighted": True, "layout": "custom", "width": 760, "height": 340, "node_radius": 32},
    'hash_table': {"buckets": 6, "entries": [{"key": "apple", "value": 5, "bucket": 2}, {"key": "cherry", "value": 7, "bucket": 2}, {"key": "banana", "value": 3, "bucket": 4}], "collision_strategy": "chaining", "highlights": {"bucket": 2, "key": "cherry"}, "show_hash": True, "caption": "Collision at bucket 2"},
    'heatmap': {"title": "Attention", "values": [[0.1, 0.9], [0.7, 0.3]], "row_labels": ["q1", "q2"], "col_labels": ["k1", "k2"], "show_values": True},
    'lattice_grid': {"width": 5, "height": 5, "highlighted_points": [[2, 3], [4, 1]]},
    'linked_list': {"nodes": [{"value": 1, "id": "n1"}, {"value": 2, "id": "n2"}, {"value": 3, "id": "n3"}], "type": "singly", "pointers": [{"node": "n2", "label": "slow"}], "highlights": {"n1": "visited", "n2": "current"}, "cycle_to": "n1", "show_null": True},
    'matrix_state': {"values": [[1, 2, 3], [4, 5, 6], [7, 8, 9]], "highlights": {"0,0": "visited", "1,1": "current", "2,2": "target"}, "path": [[0, 0], [0, 1], [1, 1]], "row_labels": ["r0", "r1", "r2"], "col_labels": ["c0", "c1", "c2"], "arrows": [{"from": [0, 0], "to": [0, 1]}], "caption": "BFS traversal on grid"},
    'matrix_transform': {"matrix": [[2, 1], [1, 2]], "caption": "A shear", "show_basis": True, "show_eigenvectors": True},
    'org_chart': {"title": "SciMigo engineering", "root": {"name": "Ada Lovelace", "title": "CEO", "children": [{"name": "Grace Hopper", "title": "VP Engineering", "children": [{"name": "Ken Thompson", "title": "Staff Engineer"}]}, {"name": "Radia Perlman", "title": "VP Infrastructure", "children": [{"name": "Vint Cerf", "title": "Network Lead"}]}]}, "assistants": [{"name": "Chief of Staff"}], "dotted": [{"from": "Ken Thompson", "to": "Radia Perlman", "label": "security"}]},
    'polar_graph': {"functions": [{"expr": "1+cos(theta)", "color": "#FF0000"}, {"expr": "1-cos(theta)", "color": "#00FF00"}]},
    'project_network': {"title": "CPM", "activities": [{"id": "A", "name": "Design", "duration": 3, "predecessors": []}, {"id": "B", "name": "Build", "duration": 5, "predecessors": ["A"]}, {"id": "C", "name": "Test", "duration": 2, "predecessors": ["B"]}]},
    'queue': {"values": [3, 7, 2, 9], "type": "deque", "front_label": "front", "back_label": "back", "highlights": {"0": "dequeue", "2": "current"}, "operation": {"type": "enqueue", "value": 5, "end": "back"}, "caption": "Dequeue from front, enqueue 5 at back"},
    'riemann_sum': {"function": "x^2", "a": 0, "b": 2, "n": 5, "show_area_value": True},
    'roadmap': {"title": "Launch", "start_date": "2026-09-01", "end_date": "2027-02-28", "tracks": [{"id": "e", "label": "Engine"}, {"id": "s", "label": "Service"}], "items": [{"id": "t1", "title": "Renderer", "track": "e", "start_date": "2026-09-01", "end_date": "2026-10-15", "status": "active"}, {"id": "t2", "title": "API", "track": "s", "start_date": "2026-09-01", "end_date": "2026-10-31", "status": "planned"}], "milestones": [{"title": "Beta", "date": "2026-11-01"}]},
    'stack': {"values": [3, 7, 2, 9], "orientation": "vertical", "top_label": "top →", "highlights": {"3": "current"}, "operation": {"type": "push", "value": 5}, "annotations": [{"index": 0, "text": "bottom"}], "caption": "Push 5 onto stack"},
    'step_function': {"transition_x": 5, "marker_positions": [2, 3, 5, 6, 7], "x_min": 1, "x_max": 10},
    'structure_chart': {"title": "Four features", "root": "Project finance", "children": [{"term": "Limited recourse", "desc": "Lenders rely on project cash flow"}, {"term": "Risk sharing", "desc": "Parties bear what they can control"}, {"term": "Off balance sheet", "desc": "Sponsor debt is not increased"}]},
    't_account': {"title": "借贷记账", "accounts": [{"name": "银行存款", "debit": [{"text": "收到投资", "amount": "100000"}], "credit": [{"text": "购买设备", "amount": "60000"}]}]},
    'timeline': {"title": "会计发展简史", "events": [{"date": "远古", "label": "结绳记事", "desc": "简单计数"}, {"date": "1494", "label": "复式记账", "desc": "帕乔利"}, {"date": "当代", "label": "会计信息化", "desc": "智能财务"}]},
    'unit_circle': {"angle": 45, "show_sin": True, "show_cos": True},
    'wbs': {"root": {"name": "项目", "children": [{"name": "设计", "children": [{"name": "方案"}, {"name": "施工图"}]}, {"name": "施工"}]}},
}


#: Templates whose figures currently carry an ``error``, with what it is. Strict:
#: a name here that starts passing fails the suite, so fixing one *requires*
#: removing it. The list is debt, recorded where it cannot be forgotten.
KNOWN_ILLEGIBLE: dict[str, str] = {
    "architecture_diagram": "labels overflow the fixed 140x44 box, and two collide",
    "binary_tree": "a node label runs past the frame",
    "linked_list": "a label runs 4px past the frame",
    "unit_circle": "the '1' tick labels collide with the axis names",
}


def _errors(name: str) -> list[Finding]:
    svg = render_diagram({"type": name, "params": CORPUS[name]})
    return [f for f in check_figure(svg) if f.severity == "error"]


class TestTheCorpusIsComplete:
    def test_every_registered_template_has_a_figure(self):
        """A lane-wide check needs one figure per template, or it is not
        lane-wide — and a template added without one would be silently exempt."""
        missing = sorted(set(DIAGRAM_REGISTRY) - set(CORPUS))
        assert not missing, f"no corpus entry for {missing}"

    def test_the_corpus_names_only_real_templates(self):
        unknown = sorted(set(CORPUS) - set(DIAGRAM_REGISTRY))
        assert not unknown, f"corpus entry for {unknown}, which is not registered"

    @pytest.mark.parametrize("name", sorted(CORPUS))
    def test_every_entry_actually_draws(self, name):
        """A blank figure passes every legibility check trivially."""
        from straightedge.diagrams.registry import count_data_marks

        svg = render_diagram({"type": name, "params": CORPUS[name]})
        assert count_data_marks(svg) > 0, f"{name} renders nothing"


class TestTheLaneIsLegible:
    @pytest.mark.parametrize(
        "name", sorted(set(CORPUS) - set(KNOWN_ILLEGIBLE)))
    def test_no_figure_carries_an_error(self, name):
        found = _errors(name)
        assert not found, "\n".join(f"  {f}" for f in found)

    @pytest.mark.parametrize("name", sorted(KNOWN_ILLEGIBLE))
    def test_the_known_failures_still_fail(self, name):
        """Strict, so the list can only shrink.

        A template here that starts passing means someone fixed it, and the fix
        is not finished until the name is removed — otherwise the entry sits
        there exempting a template that no longer needs exempting.
        """
        assert _errors(name), (
            f"{name} no longer produces an error: remove it from "
            f"KNOWN_ILLEGIBLE ({KNOWN_ILLEGIBLE[name]})")


class TestEveryFindingSaysWhere:
    """The point of the whole exercise.

    "Your diagram is wrong" is what a screenshot and a vision model can already
    tell you. "Your diagram is wrong *here*, at these coordinates" is what a
    caller can act on, and it is only available because this lane computes its
    own geometry instead of asking a browser for it.
    """

    @pytest.mark.parametrize("name", sorted(KNOWN_ILLEGIBLE))
    def test_an_error_carries_its_box(self, name):
        for finding in _errors(name):
            assert finding.box is not None, f"{finding} has no coordinates"
            x0, x1, y0, y1 = finding.box
            assert x1 >= x0 and y1 >= y0

    def test_a_collision_names_both_labels(self):
        [*found] = [f for f in _errors("unit_circle") if f.check == "text_overlap"]
        assert found
        assert all("'" in f.message for f in found), "a collision must name what collided"


class TestTheExtractor:
    def test_it_reads_the_font_shorthand(self):
        """A dozen templates write `font: 600 18px ...`, and reading only the
        longhand would measure every label in them at the default size."""
        styles = styles_from_svg(
            '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
            "<style>.a{font:600 18px sans-serif}.b{font-size:11px}</style></svg>")
        assert styles["a"] == (18.0, True)
        assert styles["b"] == (11.0, False)

    def test_an_unfilled_shape_is_a_stroke_not_a_surface(self):
        """A circle with `fill: none` is a ring of ink. Judged by its bounding
        box it covers everything inside, which reported four false warnings on
        the unit circle alone."""
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
               '<style>.ring{fill:none}</style>'
               '<circle cx="50" cy="50" r="40" class="ring"/></svg>')
        assert unfilled_classes(svg) == {"ring"}
        [box] = boxes_from_svg(svg)
        assert box.path, "an outline must carry where its ink is"

    def test_a_filled_shape_is_its_box(self):
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
               '<rect x="10" y="10" width="20" height="20" fill="#eee"/></svg>')
        [box] = boxes_from_svg(svg)
        assert not box.path

    def test_an_arc_command_is_not_read_as_a_coordinate(self):
        """`A rx ry rot large sweep x y` starts with radii and flags. Counting
        them as positions puts phantom ink at the origin."""
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="400" height="400">'
               '<path d="M 300 200 A 100 100 0 0 0 100 200" fill="none"/></svg>')
        [box] = boxes_from_svg(svg)
        assert box.x0 >= 99 and box.x1 <= 301, f"phantom point: {box}"

    def test_a_malformed_document_is_not_an_exception(self):
        assert boxes_from_svg("not svg at all") == []
        assert check_figure("") == []

    def test_the_background_is_not_treated_as_ink(self):
        """Every template paints a full-bleed rectangle. Judged as a mark it
        covers the canvas, so every label would report as obscured — one finding
        per label, which is the shape of noise nobody reads."""
        svg = render_diagram({"type": "org_chart", "params": CORPUS["org_chart"]})
        blamed = {f.message.split("covered by ")[-1].strip("'")
                  for f in check_figure(svg) if "covered by" in f.message}
        assert not any(hint in name for name in blamed
                       for hint in ("grid-paper", "background", "backdrop")), blamed


# ------------------------------------------------- the checker's own mistakes
#
# Three ways the checker reported text as misplaced when it was not. Each one
# produced coordinates, a severity and a confident sentence, which is what made
# them worth guarding: a checker that is wrong quietly is worse than no checker,
# because the list it produces gets believed and templates get "fixed" to suit
# it. Two of the six templates originally listed as illegible were only ever
# these bugs.

def _svg(body: str, view_box: str = "0 0 200 100") -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="200" height="100" '
            f'viewBox="{view_box}">{body}</svg>')


class TestTheFrameIsTheViewBox:

    def test_an_origin_away_from_zero_is_respected(self):
        """`graph` emits viewBox="53.2 94.0 521.6 152.0". Measuring its labels
        against a frame running from 0 put five of them outside it; every one
        sits comfortably inside."""
        from straightedge.diagrams.legibility import _canvas

        assert _canvas(_svg("", "53.2 94.0 521.6 152.0")) == (53.2, 94.0, 521.6, 152.0)

    def test_a_label_inside_a_shifted_view_box_is_not_clipped(self):
        svg = _svg('<text x="120" y="140" font-size="10">inside</text>',
                   "100 100 200 100")
        assert not [f for f in check_figure(svg) if f.check == "text_clipped"]

    def test_a_label_outside_a_shifted_view_box_is_still_caught(self):
        """The fix must not simply stop reporting: text past the shifted frame
        is still past it."""
        svg = _svg('<text x="290" y="140" font-size="10">hanging off</text>',
                   "100 100 200 100")
        assert [f for f in check_figure(svg) if f.check == "text_clipped"]

    def test_the_view_box_wins_over_width_and_height(self):
        from straightedge.diagrams.legibility import _canvas

        assert _canvas(_svg("", "0 0 50 25"))[2:] == (50.0, 25.0)


class TestTransformsAreApplied:

    def test_a_rotated_label_is_measured_where_it_is_drawn(self):
        """The step-function y-axis title is written horizontally and turned a
        quarter turn. Measured unrotated it is a long label hanging 20 units off
        the frame; it is a tall narrow one well inside."""
        svg = _svg('<text x="15" y="60" text-anchor="middle" font-size="10" '
                   'transform="rotate(-90 15 60)">feasible(k)</text>')
        box = next(b for b in boxes_from_svg(svg) if b.kind == "text")
        assert box.y1 - box.y0 > box.x1 - box.x0, "still measured as horizontal"
        assert not [f for f in check_figure(svg) if f.check == "text_clipped"]

    def test_a_translate_moves_the_box(self):
        svg = _svg('<g transform="translate(40 20)">'
                   '<rect x="0" y="0" width="10" height="10"/></g>')
        box = next(b for b in boxes_from_svg(svg) if b.label == "rect")
        assert (box.x0, box.y0) == (40.0, 20.0)

    def test_nested_transforms_compose(self):
        svg = _svg('<g transform="translate(10 10)"><g transform="translate(5 5)">'
                   '<rect x="0" y="0" width="4" height="4"/></g></g>')
        box = next(b for b in boxes_from_svg(svg) if b.label == "rect")
        assert (box.x0, box.y0) == (15.0, 15.0)

    def test_an_unsupported_transform_is_omitted_not_misplaced(self):
        """A wrong box is worse than a missing one: it is a finding about
        something that is not there."""
        svg = _svg('<rect x="0" y="0" width="10" height="10" transform="skewX(20)"/>')
        assert not [b for b in boxes_from_svg(svg) if b.label == "rect"]


class TestDefinitionsAreNotInk:

    def test_a_shape_inside_defs_is_not_a_mark(self):
        svg = _svg('<defs><rect x="0" y="0" width="200" height="100"/></defs>'
                   '<text x="20" y="50" font-size="10">readable</text>')
        assert not [b for b in boxes_from_svg(svg) if b.label == "rect"]
        assert not [f for f in check_figure(svg) if f.check == "text_obscured"]

    def test_a_clip_path_does_not_cover_the_text_it_bounds(self):
        """`matrix_transform` draws a panel and clips to a copy of it. Counting
        the copy reported every label as colliding twice — once with the panel
        it sits on, and once with a rectangle that is not drawn at all."""
        svg = _svg('<clipPath id="c"><rect x="0" y="0" width="200" height="100"/></clipPath>'
                   '<rect x="0" y="0" width="200" height="100" fill="white"/>'
                   '<text x="20" y="50" font-size="10">label</text>')
        assert len([b for b in boxes_from_svg(svg) if b.label == "rect"]) == 1

    def test_a_marker_is_not_drawn_where_it_is_defined(self):
        svg = _svg('<defs><marker id="a"><polygon points="0 0, 8 3, 0 6"/></marker></defs>'
                   '<text x="20" y="50" font-size="10">label</text>')
        assert not [b for b in boxes_from_svg(svg) if b.label == "polygon"]
