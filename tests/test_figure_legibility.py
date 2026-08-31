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

Those two are listed in :data:`KNOWN_ILLEGIBLE` and the list is **strict**: a
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
    smallest_font_px,
    styles_from_svg,
    unfilled_classes,
)
from straightedge.qc import Finding


class TestDisplayWidthLegibility:
    SVG = ('<svg xmlns="http://www.w3.org/2000/svg" width="400" height="100" '
           'viewBox="0 0 400 100"><text x="10" y="30" font-size="12px">Label</text></svg>')

    def test_it_reports_the_smallest_font_after_slide_scaling(self):
        assert smallest_font_px(self.SVG, 400) == pytest.approx(12)
        assert smallest_font_px(self.SVG, 200) == pytest.approx(6)

    def test_display_width_flags_text_below_the_reading_floor(self):
        assert not [f for f in check_figure(self.SVG, display_width=400)
                    if f.check == "text_too_small"]
        [finding] = [f for f in check_figure(self.SVG, display_width=200)
                     if f.check == "text_too_small"]
        assert finding.severity == "error" and "6.0px" in finding.message

#: One representative hint per registered template. Declared rather than
#: discovered: a check over the whole lane needs a figure per template, and
#: `list_templates()` says what *can* be drawn without saying what a good
#: call looks like. Harvested from the per-template suites, so these are the
#: same payloads those tests already trust.
CORPUS: dict[str, dict] = {
    'algorithm_trace': {"title": "One bubble-sort pass", "steps": [{"label": "Compare", "visual": {"type": "array_state", "params": {"values": [4, 2, 3], "highlights": {"0-1": "comparison"}}}, "transition": {"type": "swap", "indices": [0, 1]}}, {"label": "Swap", "visual": {"type": "array_state", "params": {"values": [2, 4, 3], "highlights": {"1": "current"}}}}]},
    'animated_trace': {"title": "Traversal states", "frames": [{"label": "visit A", "visual": {"type": "array_state", "params": {"values": ["A", "B"], "highlights": {"0": "current"}}}}, {"label": "visit B", "visual": {"type": "array_state", "params": {"values": ["A", "B"], "highlights": {"0": "visited", "1": "current"}}}}], "loop": True},
    'aoa_work': {"title": "Network", "nodes": [{"id": 1}, {"id": 2}, {"id": 3}], "arcs": [{"from": 1, "to": 2, "name": "Design", "duration": 3}, {"from": 2, "to": 3, "name": "Build", "duration": 5}]},
    'aon_node': {"title": "Activity", "nodes": [{"code": "A", "name": "Design", "duration": 3}, {"code": "B", "name": "Build", "duration": 5}]},
    'architecture_diagram': {"style": "PowerPoint", "layout": "left-to-right", "color_coding": {"services": "light blue", "datastores": "light green", "queues": "light purple", "external_clients": "light gray"}, "elements": [{"id": "mobile_client", "kind": "external", "label": "Mobile Client"}, {"id": "gateway_cluster", "kind": "service_cluster", "label": "Gateway (WebSocket/MQTT)"}, {"id": "chat_service", "kind": "service", "label": "Chat Service"}, {"id": "fanout_queue", "kind": "queue", "label": "Fanout Queue"}, {"id": "presence_service", "kind": "service", "label": "Presence Service"}, {"id": "message_db", "kind": "database", "label": "Message DB (Cassandra)"}, {"id": "session_cache", "kind": "cache", "label": "Session Cache (Redis)"}], "connections": [{"from": "mobile_client", "to": "gateway_cluster", "label": "send message"}, {"from": "gateway_cluster", "to": "chat_service", "label": "route"}, {"from": "chat_service", "to": "message_db", "label": "persist"}, {"from": "chat_service", "to": "fanout_queue", "label": "enqueue"}, {"from": "fanout_queue", "to": "gateway_cluster", "label": "push to recipients"}, {"from": "gateway_cluster", "to": "session_cache", "label": "lookup session"}, {"from": "presence_service", "to": "session_cache", "label": "heartbeat"}], "notes": ["Idempotency via client message id to deduplicate retries", "Fanout queue decouples write latency from recipient count"]},
    'array_state': {"values": [1, 2, 3, 4], "indices": True, "pointers": [{"index": 0, "label": "left", "position": "above"}, {"index": 3, "label": "right", "position": "below"}], "annotations": [{"index": 1, "text": "pivot", "position": "above"}], "brackets": [{"from": 1, "to": 2, "label": "window", "position": "below"}], "caption": "Sliding window"},
    'binary_tree': {"root": {"value": 8, "left": {"value": 3, "right": {"value": 6}}, "right": {"value": 10}}, "highlights": {"8": "visited", "6": "current"}, "path": [8, 3, 6], "pointers": [{"value": 6, "label": "current"}], "annotations": [{"value": 8, "text": "root"}]},
    'block_cut_tree': {"nodes": [{"id": x} for x in "ABCD"], "edges": [{"from": "A", "to": "B"}, {"from": "B", "to": "C"}, {"from": "C", "to": "A"}, {"from": "C", "to": "D"}]},
    'call_stack': {"frames": [{"function": "fib", "args": {"n": 5}, "state": "waiting"}, {"function": "fib", "args": {"n": 4}, "state": "waiting"}, {"function": "fib", "args": {"n": 3}, "state": "waiting"}, {"function": "fib", "args": {"n": 2}, "state": "executing", "return": 1}], "highlights": {"3": "current"}, "show_return_values": True, "caption": "fib(2) returns 1"},
    'circle_chord_rational': {"params": {}},
    'comparison': {"title": "两种确认基础", "columns": [{"label": "权责发生制", "points": ["按权责期确认", "反映经营成果"]}, {"label": "收付实现制", "points": ["按收付确认", "核算简单"]}]},
    'construction': {"steps": ["A = 0, 0", "B = 1, 0", "( A B )", "( B A ) -> C D", "[ C D ]", "[ A B ]"], "claims": [{"claim": "perpendicular", "of": ["[ C D ]", "[ A B ]"]}]},
    'coordinate_plane': {"x_min": 0, "x_max": 1.5708, "y_min": -2.2, "y_max": 2.2, "show_grid": True, "title": "Phase choices near x=0", "curves": [{"function": "2*cos(x)", "label": "theta=pi/2", "style": "dashed"}, {"function": "-2*cos(x)", "label": "theta=3pi/2", "style": "solid"}]},
    'cycle_diagram': {"title": "会计循环", "center": "循环", "steps": [{"label": "填制凭证"}, {"label": "登记账簿"}, {"label": "试算平衡"}, {"label": "编制报表"}]},
    'descent_triangles': {"first": {"legs": ["p²−q²", "2pq"], "hyp": "p²+q²", "area": "pq(p−q)(p+q)", "size": 17}, "second": {"legs": ["d−c", "d+c"], "hyp": "2a", "area": "q = b²", "size": 4}, "note": "2a < a⁴+b⁴"},
    'dirichlet_function': {"title": "Dirichlet", "num_points": 40},
    'disjoint_set': {"elements": ["A", "B", "C", "D"], "operations": [{"type": "union", "a": "A", "b": "B"}, {"type": "union", "a": "C", "b": "D"}, {"type": "union", "a": "B", "b": "C"}, {"type": "find", "element": "D", "expect": "A"}]},
    'dp_table': {"values": [[0, 0, 0], [0, 1, 1], [0, 1, 2]], "row_labels": ["", "a", "b"], "col_labels": ["", "a", "b"], "highlights": {"2,2": "current", "1,2": "dependency"}, "arrows": [{"from": [1, 2], "to": [2, 2]}], "formula": "dp[i][j] = max(...)", "caption": "LCS example"},
    'environment_diagram': {"frames": [{"id": "global", "label": "Global", "parent": None, "bindings": [{"name": "make_adder", "value": "func:f0"}, {"name": "add5", "value": "func:f1"}]}, {"id": "f1", "label": "f1: make_adder", "parent": "global", "bindings": [{"name": "n", "value": "5"}]}], "functions": [{"id": "f0", "params": ["n"], "body": "lambda x: x + n", "parent_frame": "global"}, {"id": "f1", "params": ["x"], "body": "x + n", "parent_frame": "f1"}], "highlights": {"frames": {"f1": "current"}, "bindings": {"f1.n": "target"}, "functions": {"f1": "current"}}, "caption": "Environment after add5 = make_adder(5)"},
    'flow_diagram': {"title": "会计核算流程", "steps": [{"label": "填制凭证", "desc": "审核原始凭证"}, {"label": "登记账簿"}, {"label": "编制报表"}]},
    'floyd_warshall': {"directed": True, "nodes": [{"id": x} for x in "ABCD"], "edges": [{"from": a, "to": b, "weight": w} for a, b, w in [("A", "B", 3), ("B", "C", -2), ("A", "C", 5), ("C", "D", 1), ("D", "B", 4), ("A", "D", 10)]], "animate": False},
    'function_graph': {"function": "sqrt(x)", "x_min": 0, "x_max": 4, "fill_area": [{"from": 0.5, "to": 3.5, "from_label": "a", "to_label": "b"}]},
    'gantt': {"tasks": [{"name": "基础", "start": 0, "duration": 3, "critical": True}, {"name": "主体", "start": 3, "duration": 5}]},
    'graph': {"nodes": [{"id": "0", "label": "start", "x": 0.12, "y": 0.5}, {"id": "1", "label": "H", "x": 0.4, "y": 0.5}, {"id": "2", "label": "HT", "x": 0.68, "y": 0.5}], "edges": [{"from": "0", "to": "1", "weight": "H"}, {"from": "1", "to": "2", "weight": "T"}, {"from": "2", "to": "0", "weight": "T"}], "directed": True, "weighted": True, "layout": "custom", "width": 760, "height": 340, "node_radius": 32},
    'graph_representation': {"nodes": [{"id": x} for x in "ABC"], "edges": [{"from": "A", "to": "B"}, {"from": "B", "to": "C"}, {"from": "C", "to": "A"}]},
    'graph_algorithm': {"algorithm": "greedy_coloring", "nodes": [{"id": "A"}, {"id": "B"}, {"id": "C"}], "edges": [{"from": "A", "to": "B"}, {"from": "B", "to": "C"}, {"from": "C", "to": "A"}], "animate": True},
    'havel_hakimi': {"sequence": [3, 3, 2, 2, 2], "realize": True, "animate": False},
    'graph_traversal': {"algorithm": "bfs", "nodes": [{"id": x, "label": x} for x in "ABCDE"], "edges": [{"from": "A", "to": "B"}, {"from": "A", "to": "C"}, {"from": "B", "to": "D"}, {"from": "C", "to": "E"}], "start": "A", "neighbor_order": list("ABCDE"), "graph_layout": "hierarchical", "columns": 3},
    'hash_table': {"buckets": 6, "entries": [{"key": "apple", "value": 5, "bucket": 2}, {"key": "cherry", "value": 7, "bucket": 2}, {"key": "banana", "value": 3, "bucket": 4}], "collision_strategy": "chaining", "highlights": {"bucket": 2, "key": "cherry"}, "show_hash": True, "caption": "Collision at bucket 2"},
    'heatmap': {"title": "Attention", "values": [[0.1, 0.9], [0.7, 0.3]], "row_labels": ["q1", "q2"], "col_labels": ["k1", "k2"], "show_values": True},
    'lattice_grid': {"width": 5, "height": 5, "highlighted_points": [[2, 3], [4, 1]]},
    'linked_list': {"nodes": [{"value": 1, "id": "n1"}, {"value": 2, "id": "n2"}, {"value": 3, "id": "n3"}], "type": "singly", "pointers": [{"node": "n2", "label": "slow"}], "highlights": {"n1": "visited", "n2": "current"}, "cycle_to": "n1", "show_null": True},
    'matrix_state': {"values": [[1, 2, 3], [4, 5, 6], [7, 8, 9]], "highlights": {"0,0": "visited", "1,1": "current", "2,2": "target"}, "path": [[0, 0], [0, 1], [1, 1]], "row_labels": ["r0", "r1", "r2"], "col_labels": ["c0", "c1", "c2"], "arrows": [{"from": [0, 0], "to": [0, 1]}], "caption": "BFS traversal on grid"},
    'matrix_transform': {"matrix": [[2, 1], [1, 2]], "caption": "A shear", "show_basis": True, "show_eigenvectors": True},
    'mycielski': {"nodes": [{"id": str(i)} for i in range(5)], "edges": [{"from": str(i), "to": str((i + 1) % 5)} for i in range(5)], "animate": False},
    'network_flow': {"nodes": [{"id": x} for x in ("s", "a", "b", "t")], "edges": [{"from": "s", "to": "a", "capacity": 3, "flow": 2}, {"from": "s", "to": "b", "capacity": 2, "flow": 2}, {"from": "a", "to": "t", "capacity": 2, "flow": 2}, {"from": "b", "to": "t", "capacity": 2, "flow": 2}], "source": "s", "sink": "t", "cut": ["s", "a", "b"], "claim_max_flow": True},
    'org_chart': {"title": "SciMigo engineering", "root": {"name": "Ada Lovelace", "title": "CEO", "children": [{"name": "Grace Hopper", "title": "VP Engineering", "children": [{"name": "Ken Thompson", "title": "Staff Engineer"}]}, {"name": "Radia Perlman", "title": "VP Infrastructure", "children": [{"name": "Vint Cerf", "title": "Network Lead"}]}]}, "assistants": [{"name": "Chief of Staff"}], "dotted": [{"from": "Ken Thompson", "to": "Radia Perlman", "label": "security"}]},
    'polar_graph': {"functions": [{"expr": "1+cos(theta)", "color": "#FF0000"}, {"expr": "1-cos(theta)", "color": "#00FF00"}]},
    'priority_queue': {"items": [{"id": "A", "priority": 5}, {"id": "B", "priority": 2}, {"id": "C", "priority": 8}], "operations": [{"type": "decrease_key", "id": "C", "priority": 1}, {"type": "pop_min", "expect": "C"}]},
    'planar_graph': {"nodes": [{"id": "A", "x": 0.1, "y": 0.1}, {"id": "B", "x": 0.9, "y": 0.1}, {"id": "C", "x": 0.5, "y": 0.9}, {"id": "D", "x": 0.5, "y": 0.42}], "edges": [{"from": a, "to": b} for a, b in [("A", "B"), ("B", "C"), ("C", "A"), ("A", "D"), ("B", "D"), ("C", "D")]], "faces": 4},
    'project_network': {"title": "CPM", "activities": [{"id": "A", "name": "Design", "duration": 3, "predecessors": []}, {"id": "B", "name": "Build", "duration": 5, "predecessors": ["A"]}, {"id": "C", "name": "Test", "duration": 2, "predecessors": ["B"]}]},
    'queue': {"values": [3, 7, 2, 9], "type": "deque", "front_label": "front", "back_label": "back", "highlights": {"0": "dequeue", "2": "current"}, "operation": {"type": "enqueue", "value": 5, "end": "back"}, "caption": "Dequeue from front, enqueue 5 at back"},
    'riemann_sum': {"function": "x^2", "a": 0, "b": 2, "n": 5, "show_area_value": True},
    'roadmap': {"title": "Launch", "start_date": "2026-09-01", "end_date": "2027-02-28", "tracks": [{"id": "e", "label": "Engine"}, {"id": "s", "label": "Service"}], "items": [{"id": "t1", "title": "Renderer", "track": "e", "start_date": "2026-09-01", "end_date": "2026-10-15", "status": "active"}, {"id": "t2", "title": "API", "track": "s", "start_date": "2026-09-01", "end_date": "2026-10-31", "status": "planned"}], "milestones": [{"title": "Beta", "date": "2026-11-01"}]},
    'search_tree': {"kind": "avl", "values": [30, 20, 10, 25, 28], "show_balance": True},
    'stack': {"values": [3, 7, 2, 9], "orientation": "vertical", "top_label": "top →", "highlights": {"3": "current"}, "operation": {"type": "push", "value": 5}, "annotations": [{"index": 0, "text": "bottom"}], "caption": "Push 5 onto stack"},
    'step_function': {"transition_x": 5, "marker_positions": [2, 3, 5, 6, 7], "x_min": 1, "x_max": 10},
    'structure_chart': {"title": "Four features", "root": "Project finance", "children": [{"term": "Limited recourse", "desc": "Lenders rely on project cash flow"}, {"term": "Risk sharing", "desc": "Parties bear what they can control"}, {"term": "Off balance sheet", "desc": "Sponsor debt is not increased"}]},
    't_account': {"title": "借贷记账", "accounts": [{"name": "银行存款", "debit": [{"text": "收到投资", "amount": "100000"}], "credit": [{"text": "购买设备", "amount": "60000"}]}]},
    'timeline': {"title": "会计发展简史", "events": [{"date": "远古", "label": "结绳记事", "desc": "简单计数"}, {"date": "1494", "label": "复式记账", "desc": "帕乔利"}, {"date": "当代", "label": "会计信息化", "desc": "智能财务"}]},
    'tree': {"root": {"value": "root", "children": [{"value": "a"}, {"value": "b"}, {"value": "c"}]}, "path": ["root", "b"], "highlights": {"b": "current"}},
    'turan': {"n": 7, "r": 3, "highlight_clique_free": True},
    'unit_circle': {"angle": 45, "show_sin": True, "show_cos": True},
    'wbs': {"root": {"name": "项目", "children": [{"name": "设计", "children": [{"name": "方案"}, {"name": "施工图"}]}, {"name": "施工"}]}},
}


#: Templates whose figures currently carry an ``error``, with what it is. Strict:
#: a name here that starts passing fails the suite, so fixing one *requires*
#: removing it. The list is debt, recorded where it cannot be forgotten.
KNOWN_ILLEGIBLE: dict[str, str] = {
    "linked_list": "a label runs 4px past the frame",
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
        """Against a figure built to collide, not against whichever template
        happens to be broken today. This used to read `unit_circle`, which was
        illegible when it was written and no longer is — so the test went from
        checking the message format to depending on a defect staying unfixed."""
        svg = _svg('<text x="20" y="50" font-size="12">alpha</text>'
                   '<text x="24" y="50" font-size="12">beta</text>')
        found = [f for f in check_figure(svg) if f.check == "text_overlap"]
        assert found, "two labels in the same pixels went unreported"
        for f in found:
            assert "'alpha'" in f.message and "'beta'" in f.message, (
                f"a collision must name what collided: {f.message}")


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


class TestClipsAreHonoured:
    """A `clip-path` on a visible group is not decoration: the browser paints
    only what falls inside it. `matrix_transform` puts its transformed grid in
    `<g clip-path="url(#clip-240)">` and lets the lines run well past the panel,
    which is exactly right on screen and produced eighteen warnings about ink
    that is never drawn."""

    def test_a_clipped_line_is_measured_only_where_it_shows(self):
        svg = _svg('<clipPath id="c"><rect x="0" y="0" width="50" height="50"/></clipPath>'
                   '<g clip-path="url(#c)"><line x1="10" y1="10" x2="400" y2="10"/></g>')
        box = next(b for b in boxes_from_svg(svg) if b.label == "line")
        assert box.x1 == 50, f"line measured out to {box.x1}, past its clip"

    def test_geometry_wholly_outside_its_clip_is_not_ink(self):
        svg = _svg('<clipPath id="c"><rect x="0" y="0" width="50" height="50"/></clipPath>'
                   '<g clip-path="url(#c)"><line x1="100" y1="80" x2="180" y2="90"/></g>')
        assert not [b for b in boxes_from_svg(svg) if b.label == "line"]

    def test_an_unclipped_line_past_the_frame_is_still_reported(self):
        """The fix must not become a way of not looking: ink that really does
        leave the frame still leaves it."""
        svg = _svg('<text x="20" y="50" font-size="10">label</text>'
                   '<line x1="10" y1="10" x2="400" y2="90"/>')
        assert [f for f in check_figure(svg) if f.check == "out_of_frame"]

    def test_a_clipped_line_and_an_unclipped_one_are_told_apart(self):
        """The same line, drawn twice: only the clipped one is invisible out
        past the panel, and only it should go unreported. (Both slope, because
        `qc` skips a zero-area box and a level line has none.)"""
        line = '<line x1="10" y1="10" x2="400" y2="90"/>'
        clip = '<clipPath id="c"><rect x="0" y="0" width="50" height="50"/></clipPath>'
        label = '<text x="20" y="50" font-size="10">label</text>'
        bare = check_figure(_svg(label + line))
        clipped = check_figure(_svg(clip + label + f'<g clip-path="url(#c)">{line}</g>'))
        assert [f for f in bare if f.check == "out_of_frame"]
        assert not [f for f in clipped if f.check == "out_of_frame"]

    def test_a_clip_is_resolved_in_the_space_of_the_element_using_it(self):
        svg = _svg('<clipPath id="c"><rect x="0" y="0" width="50" height="50"/></clipPath>'
                   '<g transform="translate(100 0)" clip-path="url(#c)">'
                   '<line x1="0" y1="10" x2="400" y2="10"/></g>')
        box = next(b for b in boxes_from_svg(svg) if b.label == "line")
        assert (box.x0, box.x1) == (100.0, 150.0), f"clip landed at {box.x0}..{box.x1}"

    def test_a_clip_this_module_cannot_represent_draws_nothing(self):
        """Rather than measuring the whole thing and reporting on pixels that
        are clipped away."""
        svg = _svg('<clipPath id="c"><circle cx="25" cy="25" r="25"/></clipPath>'
                   '<g clip-path="url(#c)"><line x1="10" y1="10" x2="400" y2="10"/></g>')
        assert not [b for b in boxes_from_svg(svg) if b.label == "line"]

    def test_nested_clips_intersect(self):
        svg = _svg('<clipPath id="a"><rect x="0" y="0" width="80" height="80"/></clipPath>'
                   '<clipPath id="b"><rect x="0" y="0" width="40" height="80"/></clipPath>'
                   '<g clip-path="url(#a)"><g clip-path="url(#b)">'
                   '<line x1="0" y1="10" x2="400" y2="10"/></g></g>')
        box = next(b for b in boxes_from_svg(svg) if b.label == "line")
        assert box.x1 == 40


class TestAClipDoesNotHideTruncation:
    """Clipping a label to its visible fragment is right for deciding what it
    overlaps and wrong as the whole story.

    A label running x=40..120 under a clip ending at x=50 becomes an
    unremarkable ten-unit box sitting well inside the frame, indistinguishable
    from a label that is simply short — which turns the one check this module
    exists for into a pass. The clip is a boundary the reader loses text at,
    exactly as the frame edge is.

    Every case runs twice, with and without an unrelated visible label. The
    first version of these tests always included one, and that single shared
    fixture hid the worst case of the lot: a label lying *entirely* outside its
    clip leaves no visible box at all, so a figure containing nothing else took
    an early return and reported nothing. The fixture, not the checker, is what
    decided that path was never reached.
    """

    CLIP = '<clipPath id="c"><rect x="0" y="0" width="50" height="100"/></clipPath>'
    OTHER = '<text x="10" y="90" font-size="10">elsewhere</text>'

    def _svg_with(self, label_x, text, other):
        return _svg(self.CLIP + other +
                    f'<g clip-path="url(#c)"><text x="{label_x}" y="50" '
                    f'font-size="10">{text}</text></g>')

    def _cut(self, label_x, text="a long truncated label", other=""):
        return [f for f in check_figure(self._svg_with(label_x, text, other))
                if f.check == "text_clipped"]

    @pytest.mark.parametrize("other", ["", OTHER], ids=["alone", "with-other-text"])
    def test_a_partly_clipped_label_is_an_error(self, other):
        cut = self._cut(40, other=other)
        assert cut, "a label with most of its glyphs unpainted reported nothing"
        assert cut[0].severity == "error"
        assert cut[0].label == "a long truncated label"

    @pytest.mark.parametrize("other", ["", OTHER], ids=["alone", "with-other-text"])
    def test_a_wholly_clipped_label_is_an_error(self, other):
        """The worst case, and the one that leaves no visible box behind: every
        glyph is missing, so there is nothing for the box checks to look at."""
        cut = self._cut(120, other=other)
        assert cut, "a label with no visible glyphs at all reported nothing"
        assert cut[0].severity == "error"

    @pytest.mark.parametrize("other", ["", OTHER], ids=["alone", "with-other-text"])
    def test_a_label_inside_its_clip_is_not_reported(self, other):
        assert not self._cut(5, "ok", other=other)

    def test_the_fragment_being_inside_the_frame_is_not_a_defence(self):
        """The visible ten units sit comfortably in a 200x100 frame. That is
        precisely why the frame check cannot see this one."""
        boxes = [b for b in boxes_from_svg(self._svg_with(40, "a long truncated label", ""))
                 if b.kind == "text"]
        assert boxes and boxes[0].x1 <= 50, "fragment should still be clipped for overlap"
        assert self._cut(40)

    def test_it_is_located_where_the_missing_glyphs_were(self):
        """Not at the fragment: the fragment is not where the reader is looking
        for the rest of the word."""
        cut = self._cut(40)[0]
        assert cut.box is not None and cut.box[1] - cut.box[0] > 50, (
            "reported the surviving fragment rather than the whole label")

    def test_a_clipped_shape_is_still_not_a_defect(self):
        """Geometry deliberately runs past its panel — that is what the clip is
        for. Only text going missing is a legibility defect."""
        body = (self.CLIP + self.OTHER +
                '<g clip-path="url(#c)"><line x1="10" y1="10" x2="400" y2="90"/></g>')
        assert not [f for f in check_figure(_svg(body))
                    if f.check in ("text_clipped", "out_of_frame")]

    def test_a_figure_with_no_declared_size_reports_nothing(self):
        """Deliberate, and stated here so it is a decision rather than another
        early return nobody looked at: without a viewBox or width/height there
        is no coordinate system to report a finding in, and every other finding
        this module emits is positioned in one."""
        svg = ('<svg xmlns="http://www.w3.org/2000/svg">' + self.CLIP +
               '<g clip-path="url(#c)"><text x="120" y="50">hidden</text></g></svg>')
        assert check_figure(svg) == []


class TestTheFrameComesFromTheRootElement:
    """`_canvas` used to search the raw string for the first
    `width=... height=...` pair, which is the root's only because `<svg>` is
    written first. Nothing enforced that."""

    def test_a_size_on_an_inner_element_is_not_the_frame(self):
        from straightedge.diagrams.legibility import _canvas

        svg = ('<svg xmlns="http://www.w3.org/2000/svg">'
               '<clipPath id="c"><rect x="0" y="0" width="50" height="100"/></clipPath>'
               '</svg>')
        assert _canvas(svg) == (0.0, 0.0, 0.0, 0.0), "took a clip rect for the canvas"

    def test_height_written_before_width_is_still_read(self):
        from straightedge.diagrams.legibility import _canvas

        svg = '<svg xmlns="http://www.w3.org/2000/svg" height="100" width="200"></svg>'
        assert _canvas(svg) == (0.0, 0.0, 200.0, 100.0)

    def test_a_unit_suffix_is_tolerated(self):
        from straightedge.diagrams.legibility import _canvas

        svg = '<svg xmlns="http://www.w3.org/2000/svg" width="200px" height="100px"></svg>'
        assert _canvas(svg) == (0.0, 0.0, 200.0, 100.0)


class TestUnitCircleLabelsClearEachOther:
    """The collisions a human reviewer reported by eye, before this module
    existed — and the ones fixing those turned up.

    An axis name sat level with the tick label nearest it (`x` five pixels from
    its own `1`), the common-angle label was drawn on the ray the figure was
    already marking, so `π/4` and `(0.71, 0.71)` overlapped by half, and the
    coordinate readout ran off the canvas near the edges.
    """

    FULL = {"angle": 45, "show_common_angles": True, "show_tan": True,
            "show_coordinates": True, "show_triangle": True,
            "show_sin": True, "show_cos": True}

    def _errors(self, **over):
        params = {**self.FULL, **over}
        return [f for f in check_figure(render_diagram(
            {"type": "unit_circle", "params": params})) if f.severity == "error"]

    def test_the_reported_figure_is_clean(self):
        assert not self._errors(), [f.message for f in self._errors()]

    def test_an_axis_name_clears_its_tick_label(self):
        svg = render_diagram({"type": "unit_circle", "params": self.FULL})
        by = {}
        for b in boxes_from_svg(svg):
            if b.kind == "text" and b.label in ("x", "y", "1"):
                by.setdefault(b.label, []).append(b)
        for name in ("x", "y"):
            for tick in by["1"]:
                a = by[name][0]
                assert not (a.x0 < tick.x1 and tick.x0 < a.x1
                            and a.y0 < tick.y1 and tick.y0 < a.y1), (
                    f"axis name {name!r} overlaps a '1' tick")

    def test_the_shown_angle_is_not_also_labelled_as_a_common_one(self):
        """Both labels sit on the same ray, so drawing both loses both."""
        svg = render_diagram({"type": "unit_circle", "params": self.FULL})
        labels = [b.label for b in boxes_from_svg(svg) if b.kind == "text"]
        assert "(0.71, 0.71)" in labels
        assert "π/4" not in labels, "the angle being shown was labelled twice"

    def test_a_common_angle_is_still_labelled_when_it_is_not_the_one_shown(self):
        """The suppression must be one label, not the whole set."""
        svg = render_diagram({"type": "unit_circle", "params": {**self.FULL, "angle": 20}})
        labels = [b.label for b in boxes_from_svg(svg) if b.kind == "text"]
        assert "π/4" in labels

    @pytest.mark.parametrize("angle", [0, 45, 90, 180, 270, 300])
    def test_the_readout_stays_on_the_canvas(self, angle):
        svg = render_diagram({"type": "unit_circle", "params": {**self.FULL, "angle": angle}})
        for b in boxes_from_svg(svg):
            if b.kind == "text" and b.label.startswith("("):
                assert b.x0 >= 0 and b.x1 <= 400, f"readout at x {b.x0:.0f}..{b.x1:.0f}"

    @pytest.mark.parametrize("angle", range(0, 360, 3))
    def test_every_angle_is_clean(self, angle):
        """The static positions were only ever checked at the review angles:
        `x` moved above the axis cleared the tick and landed on the `sin=`
        readout for 8°..27°, `y` moved right landed on the 90° coordinate
        readout, and the readout's edge flip at 355° landed on `cos=1.00`.
        Each fix traded one collision for another until the labels started
        dodging what is actually drawn — which only a sweep can hold."""
        assert not self._errors(angle=angle), (
            [f.message for f in self._errors(angle=angle)])

    @pytest.mark.parametrize("angle", [90, 96, 262, 278, 354])
    def test_a_tick_is_not_under_the_travelling_point(self, angle):
        """The `1` moved inward sat exactly where the point passes just after
        90° — 100% covered, warn severity, invisible to the error sweep."""
        svg = render_diagram({"type": "unit_circle", "params": {**self.FULL, "angle": angle}})
        assert not [f for f in check_figure(svg)
                    if f.check == "text_obscured" and "uc-point" in f.message]

    def test_the_shown_angle_keeps_its_label_when_nothing_else_names_it(self):
        """Suppressing the common-angle label is justified by the readout or
        arc label on the same ray; with both off it deleted the only label the
        taught angle had — a figure teaching π/4 marked every common angle
        except π/4."""
        svg = render_diagram({"type": "unit_circle", "params": {
            "angle": 45, "show_common_angles": True,
            "show_coordinates": False, "show_arc": False}})
        labels = [b.label for b in boxes_from_svg(svg) if b.kind == "text"]
        assert "π/4" in labels
        assert "π/6" in labels


class TestMatrixTransformKeepsItsGuidesInThePanel:
    """The second piece of evidence in issue #14.

    The eigenvector ray is drawn 1.5x the panel range on purpose, so the
    direction reads as a line rather than a segment. That is only right if the
    panel cuts it off, and nothing did: it crossed the gutter, the other panel
    and the edge of the figure, ending 17px past a 460px canvas. The grid beside
    it was clipped; the clip was emitted inside the grid branch, so the rays had
    nothing to reach for.
    """

    PARAMS = {"matrix": [[1, 1], [0, 1]], "shape": "unit_square",
              "show_eigenvectors": True, "show_grid": True}

    def _svg(self, **over):
        return render_diagram({"type": "matrix_transform",
                               "params": {**self.PARAMS, **over}})

    def test_no_ink_leaves_the_figure(self):
        assert not [f for f in check_figure(self._svg())
                    if f.check == "out_of_frame"]

    def test_the_panel_clip_exists_without_a_grid(self):
        """It used to be emitted inside `if show_grid`, so turning the grid off
        took the clip away from everything else that needed it."""
        assert "<clipPath" in self._svg(show_grid=False)
        assert not [f for f in check_figure(self._svg(show_grid=False))
                    if f.check == "out_of_frame"]

    def test_a_repeated_eigenvalue_draws_one_ray(self):
        """[[1,1],[0,1]] has one eigenvector and returns it twice. The same
        dashed line drawn over itself is darker, not clearer."""
        import re

        assert len(re.findall(r'stroke-dasharray="6,3"', self._svg())) == 1

    def test_distinct_eigenvectors_still_draw_two(self):
        """The de-duplication must remove a repeat, not a direction."""
        import re

        svg = self._svg(matrix=[[2, 0], [0, 3]])
        assert len(re.findall(r'stroke-dasharray="6,3"', svg)) == 2

    def test_the_eigenvalue_label_is_not_clipped(self):
        """Clipping the ray is right and clipping its label is not: a label the
        reader cannot finish is the defect this whole module is about. The label
        sits outside the clipped group for that reason."""
        assert not [f for f in check_figure(self._svg())
                    if f.check == "text_clipped"]

    @pytest.mark.parametrize("matrix", [[[2, 0], [0, 3]], [[1, 0], [0, 1]],
                                        [[-2, 0], [0, 3]], [[3, 0], [0, 1]],
                                        [[0, 0], [-1, 1]], [[0, -1], [1, 0]]])
    def test_the_eigenvalue_label_clears_the_basis_labels(self, matrix):
        """An eigenvector parallel to a basis image — any diagonal matrix —
        put λ at the same tip with the same (+4, -4) offset as Ae1, two 10px
        labels drawn on top of each other. Distance heuristics only moved the
        failure: [[0,0],[-1,1]] puts a basis image at *both* ray ends, so the
        spot has to be chosen by measuring the candidate text boxes against
        the labels already placed."""
        assert not [f for f in check_figure(self._svg(matrix=matrix))
                    if f.check == "text_overlap"]

    def test_the_clip_id_names_its_geometry(self):
        """Fragment ids resolve across the whole page, first match wins, so
        two figures inlined into one document share the namespace. An id
        minted from the full clip geometry makes a collision harmless by
        construction: two clipPaths with the same id cut the same rectangle,
        and it stops mattering whose definition the browser picks."""
        import re

        clips = re.findall(
            r'<clipPath id="([^"]+)"><rect x="([^"]+)" y="([^"]+)" '
            r'width="([^"]+)" height="([^"]+)"', self._svg())
        assert clips, "no panel clip found"
        for cid, x, y, w, h in clips:
            assert cid == (f"mt-clip-{float(x):.0f}-{float(y):.0f}"
                           f"-{float(w):.0f}x{float(h):.0f}"), (
                f"{cid!r} does not pin the geometry it clips")


class TestRiemannGridStaysInsideThePlot:
    """`int()` truncates toward zero, so on a domain that does not straddle
    zero the gridline loop still ran to an integer outside the plot: a=-3,
    b=-1 has x_max=-0.5, `int()` makes that 0, and the 0-gridline landed 8px
    past the right edge of the data area — the exact defect the `+ 1` fix
    claimed to close, surviving for every all-negative or all-positive domain.
    The corpus figure uses a=0, b=2 and never saw it."""

    @pytest.mark.parametrize("a,b", [(-3, -1), (1, 3), (0, 2), (-2.5, 2.5),
                                     (0.5, 3.5)])
    def test_no_gridline_leaves_the_figure(self, a, b):
        svg = render_diagram({"type": "riemann_sum", "params": {
            "expression": "x^2", "a": a, "b": b, "n": 4}})
        errors = [f for f in check_figure(svg)
                  if f.check == "out_of_frame" and f.severity == "error"]
        assert not errors, [f.message for f in errors]


class TestTheShownAngleIsMatchedCircularly:
    """`abs((deg - angle_deg) % 360) < 0.5` is asymmetric: `%` is non-negative,
    so `(45 - 45.2) % 360` is 359.8 and a figure drawn at 45.2° kept the 45°
    label sitting on the same ray. Wrong by a fifth of a degree, on one side."""

    @pytest.mark.parametrize("angle", [45.0, 45.2, 44.8, 0.0, 0.2, 359.8])
    def test_a_common_angle_within_half_a_degree_is_not_labelled_twice(self, angle):
        svg = render_diagram({"type": "unit_circle", "params": {
            "angle": angle, "show_common_angles": True, "show_coordinates": True}})
        labels = [b.label for b in boxes_from_svg(svg) if b.kind == "text"]
        # The property is that the label for the ray being shown is gone — not
        # that the figure has no overlaps at all, which would also catch the
        # `sin=`/`cos=` crowding at shallow angles that this does not touch.
        expected = {0.0: "0", 45.0: "π/4", 90.0: "π/2", 180.0: "π", 270.0: "3π/2"}
        nearest = min(expected, key=lambda d: abs((d - angle + 180) % 360 - 180))
        if abs((nearest - angle + 180) % 360 - 180) < 0.5:
            assert expected[nearest] not in labels, (
                f"at {angle}° the {expected[nearest]} label was drawn on the "
                "ray the figure is already marking")

    def test_a_genuinely_different_angle_keeps_its_labels(self):
        """Half a degree is the tolerance, not a licence to drop neighbours."""
        svg = render_diagram({"type": "unit_circle", "params": {
            "angle": 47, "show_common_angles": True, "show_coordinates": True}})
        assert "π/4" in [b.label for b in boxes_from_svg(svg) if b.kind == "text"]
