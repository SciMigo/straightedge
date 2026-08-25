"""Tests for diagram rendering module."""

import logging
import re

import pytest

from straightedge.diagrams import render_diagram, DIAGRAM_REGISTRY
from straightedge.diagrams.registry import count_data_marks, is_blank_diagram, register
from straightedge.diagrams.renderer import (
    circle,
    line,
    rect,
    svg_document,
    text,
    group,
)


class TestSVGRenderer:
    """Tests for SVG rendering utilities."""

    def test_svg_document_basic(self):
        svg = svg_document("<circle/>", width=100, height=100)
        assert "<svg" in svg
        assert 'width="100"' in svg
        assert 'height="100"' in svg
        assert 'viewBox="0 0 100 100"' in svg
        assert "<circle/>" in svg

    def test_svg_document_custom_viewbox(self):
        svg = svg_document("", viewbox="-10 -10 20 20")
        assert 'viewBox="-10 -10 20 20"' in svg

    def test_circle(self):
        c = circle(50, 50, 10, fill="red")
        assert 'cx="50"' in c
        assert 'cy="50"' in c
        assert 'r="10"' in c
        assert 'fill="red"' in c

    def test_line(self):
        l = line(0, 0, 100, 100, stroke="black")
        assert 'x1="0"' in l
        assert 'y1="0"' in l
        assert 'x2="100"' in l
        assert 'y2="100"' in l
        assert 'stroke="black"' in l

    def test_rect(self):
        r = rect(10, 20, 30, 40)
        assert 'x="10"' in r
        assert 'y="20"' in r
        assert 'width="30"' in r
        assert 'height="40"' in r

    def test_text(self):
        t = text(50, 50, "Hello <World>")
        assert 'x="50"' in t
        assert 'y="50"' in t
        assert "Hello &lt;World&gt;" in t  # HTML escaped

    def test_group(self):
        g = group("<circle/>", id="my-group")
        assert '<g id="my-group">' in g
        assert "<circle/>" in g
        assert "</g>" in g

    def test_attrs_with_underscores_convert_to_hyphens(self):
        c = circle(0, 0, 5, stroke_width="2", font_size="12")
        assert 'stroke-width="2"' in c
        assert 'font-size="12"' in c


class TestDiagramRegistry:
    """Tests for diagram registry."""

    def test_registry_has_lattice_grid(self):
        assert "lattice_grid" in DIAGRAM_REGISTRY

    def test_render_diagram_with_valid_type(self):
        hint = {
            "type": "lattice_grid",
            "params": {"width": 5, "height": 5}
        }
        svg = render_diagram(hint)
        assert "<svg" in svg
        assert "circle" in svg

    def test_render_diagram_with_unknown_type(self):
        hint = {"type": "unknown_diagram_type", "params": {}}
        svg = render_diagram(hint)
        assert svg == ""

    def test_render_diagram_with_string_hint(self):
        svg = render_diagram("A simple description")
        assert svg == ""

    def test_render_diagram_with_none(self):
        svg = render_diagram(None)
        assert svg == ""

    def test_render_diagram_with_invalid_input(self):
        svg = render_diagram(123)  # type: ignore
        assert svg == ""

    def test_render_diagram_missing_params(self):
        hint = {"type": "lattice_grid"}  # no params
        svg = render_diagram(hint)
        assert "<svg" in svg  # Should use defaults


class TestLatticeGridTemplate:
    """Tests for lattice grid diagram template."""

    def test_basic_render(self):
        hint = {
            "type": "lattice_grid",
            "params": {"width": 5, "height": 5}
        }
        svg = render_diagram(hint)
        assert "<svg" in svg
        assert "</svg>" in svg
        # Should have multiple circle elements for points
        assert svg.count("<circle") > 20  # 6x6 = 36 points

    def test_highlight_visible_points(self):
        hint = {
            "type": "lattice_grid",
            "params": {"width": 5, "height": 5, "highlight": "visible"}
        }
        svg = render_diagram(hint)
        # Visible points have gcd(x,y)=1
        assert "diagram-point-visible" in svg
        assert "diagram-point-hidden" in svg

    def test_show_rays(self):
        hint = {
            "type": "lattice_grid",
            "params": {"width": 5, "height": 5, "show_rays": True}
        }
        svg = render_diagram(hint)
        assert "diagram-ray" in svg

    def test_show_axes(self):
        hint = {
            "type": "lattice_grid",
            "params": {"width": 5, "height": 5, "show_axes": True}
        }
        svg = render_diagram(hint)
        assert "diagram-axis" in svg

    def test_show_labels(self):
        hint = {
            "type": "lattice_grid",
            "params": {"width": 5, "height": 5, "labels": True}
        }
        svg = render_diagram(hint)
        assert "<text" in svg

    def test_highlighted_points(self):
        hint = {
            "type": "lattice_grid",
            "params": {
                "width": 5,
                "height": 5,
                "highlighted_points": [[2, 3], [4, 1]]
            }
        }
        svg = render_diagram(hint)
        assert "diagram-point-highlight" in svg

    def test_custom_dimensions(self):
        hint = {
            "type": "lattice_grid",
            "params": {
                "width": 10,
                "height": 8,
                "cell_size": 40,
                "padding": 50
            }
        }
        svg = render_diagram(hint)
        # Expected dimensions: 10*40 + 2*50 = 500 width, 8*40 + 2*50 = 420 height
        assert 'width="500"' in svg
        assert 'height="420"' in svg

    def test_origin_highlighting(self):
        hint = {
            "type": "lattice_grid",
            "params": {"width": 3, "height": 3, "show_origin": True}
        }
        svg = render_diagram(hint)
        assert "diagram-point-origin" in svg

    def test_highlight_all(self):
        hint = {
            "type": "lattice_grid",
            "params": {"width": 3, "height": 3, "highlight": "all"}
        }
        svg = render_diagram(hint)
        # With highlight="all", all interior points should be visible
        # Count should be higher than with "visible" mode
        visible_count = svg.count("diagram-point-visible")
        assert visible_count > 0

    def test_show_grid(self):
        hint = {
            "type": "lattice_grid",
            "params": {"width": 5, "height": 5, "show_grid": True}
        }
        svg = render_diagram(hint)
        assert "diagram-grid" in svg


class TestCoordinatePlaneTemplate:
    """Tests for coordinate plane diagram template."""

    def test_registry_has_coordinate_plane(self):
        assert "coordinate_plane" in DIAGRAM_REGISTRY

    def test_basic_render(self):
        hint = {
            "type": "coordinate_plane",
            "params": {"x_min": -5, "x_max": 5, "y_min": -5, "y_max": 5}
        }
        svg = render_diagram(hint)
        assert "<svg" in svg
        assert "</svg>" in svg

    def test_shows_grid(self):
        hint = {
            "type": "coordinate_plane",
            "params": {"show_grid": True}
        }
        svg = render_diagram(hint)
        assert "coord-grid" in svg

    def test_shows_axes(self):
        hint = {
            "type": "coordinate_plane",
            "params": {"show_axes": True}
        }
        svg = render_diagram(hint)
        assert "coord-axis" in svg

    def test_shows_tick_labels(self):
        hint = {
            "type": "coordinate_plane",
            "params": {"show_labels": True, "show_ticks": True}
        }
        svg = render_diagram(hint)
        assert "coord-label" in svg
        assert "coord-tick" in svg

    def test_plots_points(self):
        hint = {
            "type": "coordinate_plane",
            "params": {
                "points": [
                    {"x": 1, "y": 2, "label": "A"},
                    {"x": -1, "y": 3}
                ]
            }
        }
        svg = render_diagram(hint)
        assert "coord-point" in svg
        assert ">A<" in svg

    def test_plots_vectors(self):
        hint = {
            "type": "coordinate_plane",
            "params": {
                "vectors": [
                    {"x": 3, "y": 2, "color": "#FF0000"}
                ]
            }
        }
        svg = render_diagram(hint)
        assert "<line" in svg
        assert "#FF0000" in svg

    def test_with_title(self):
        hint = {
            "type": "coordinate_plane",
            "params": {"title": "My Coordinate Plane"}
        }
        svg = render_diagram(hint)
        assert "My Coordinate Plane" in svg
        assert "coord-title" in svg


class TestCoordinatePlaneExpressionCurves:
    """Curves given as an expression in x.

    Regression: this shape used to fall through every ``type`` branch and be
    dropped, so a two-curve comparison shipped as bare axes — chrome big enough
    to clear the old byte-based empty check.
    """

    #: Verbatim from the spec that shipped blank (GaoKao trig lecture, slide 4).
    SHIPPED_HINT = {
        "type": "coordinate_plane",
        "params": {
            "x_min": 0, "x_max": 1.5708, "y_min": -2.2, "y_max": 2.2,
            "show_grid": True, "title": "Phase choices near x=0",
            "curves": [
                {"function": "2*cos(x)", "label": "theta=pi/2", "style": "dashed"},
                {"function": "-2*cos(x)", "label": "theta=3pi/2", "style": "solid"},
            ],
        },
    }

    def test_shipped_hint_now_plots_both_curves(self):
        svg = render_diagram(self.SHIPPED_HINT)
        assert svg.count("<path") == 2
        assert not is_blank_diagram(svg)

    def test_expr_is_accepted_as_an_alias(self):
        hint = {"type": "coordinate_plane",
                "params": {"curves": [{"expr": "x^2"}]}}
        assert "<path" in render_diagram(hint)

    def test_style_dashed_is_honoured(self):
        svg = render_diagram(self.SHIPPED_HINT)
        # Must be on the curve itself — the default stylesheet also mentions
        # stroke-dasharray (.diagram-ray), so a bare substring check passes
        # even when no curve is drawn at all.
        dashed_paths = re.findall(r"<path[^>]*stroke-dasharray", svg)
        assert len(dashed_paths) == 1, svg

    def test_curves_get_distinct_default_colors(self):
        svg = render_diagram(self.SHIPPED_HINT)
        strokes = set(re.findall(r'stroke="(#[0-9A-Fa-f]{6})"', svg))
        # Two curves that default to one colour read as a single curve.
        assert len(strokes) >= 2

    def test_curve_label_is_drawn(self):
        svg = render_diagram(self.SHIPPED_HINT)
        assert "theta=pi/2" in svg

    def test_poles_break_the_stroke(self):
        # One polyline through tan's pole draws a vertical line across the
        # plot that reads as part of the curve.
        hint = {"type": "coordinate_plane", "params": {
            "x_min": -3, "x_max": 3, "y_min": -5, "y_max": 5,
            "curves": [{"function": "tan(x)"}]}}
        assert render_diagram(hint).count("<path") > 1

    def test_typed_curves_still_render(self):
        for curve in ({"type": "line", "slope": 1, "intercept": 0},
                      {"type": "parabola_up", "a": 1},
                      {"type": "vertical_line", "x": 2}):
            hint = {"type": "coordinate_plane", "params": {"curves": [curve]}}
            svg = render_diagram(hint)
            assert "<path" in svg, curve

    def test_unrenderable_curve_is_logged(self, caplog):
        hint = {"type": "coordinate_plane",
                "params": {"curves": [{"shape": "mystery"}]}}
        with caplog.at_level(logging.WARNING):
            render_diagram(hint)
        assert "no renderable shape" in caplog.text


class TestBlankDiagramDetection:
    """``is_blank_diagram`` keys on data marks, not bytes.

    A bare coordinate plane is kilobytes of grid, axes and tick labels, so the
    byte threshold this replaced could not distinguish it from a full plot.
    """

    def test_chrome_only_plane_is_blank(self):
        svg = render_diagram({"type": "coordinate_plane",
                              "params": {"show_grid": True, "title": "t"}})
        assert len(svg) > 1000, "guard: this is not a small SVG"
        assert is_blank_diagram(svg)

    def test_plane_with_a_curve_is_not_blank(self):
        svg = render_diagram({"type": "coordinate_plane",
                              "params": {"curves": [{"function": "x^2"}]}})
        assert not is_blank_diagram(svg)

    def test_plotted_points_count_as_data(self):
        svg = render_diagram({"type": "coordinate_plane",
                              "params": {"points": [{"x": 1, "y": 2}]}})
        assert not is_blank_diagram(svg)

    def test_chrome_classes_are_not_counted(self):
        chrome = (
            '<svg><line class="coord-grid"/><line class="coord-axis"/>'
            '<line class="coord-tick"/><text class="coord-label">1</text>'
            '<text class="coord-title">T</text></svg>'
        )
        assert count_data_marks(chrome) == 0

    def test_unclassed_marks_are_counted(self):
        assert count_data_marks('<svg><path d="M0 0 L1 1"/></svg>') == 1

    def test_style_block_is_not_mistaken_for_content(self):
        # The stylesheet names every chrome class and would otherwise match.
        styled = '<svg><style>.coord-grid { stroke: #eee; }</style><circle/></svg>'
        assert count_data_marks(styled) == 1

    def test_a_marker_definition_is_not_content(self):
        # An arrowhead is a <polygon> inside <defs>; it is painted only where a
        # path references it, so an empty array with a marker drew "one mark".
        defined = ('<svg><defs><marker id="a"><polygon points="0 0,9 3.5,0 7"/>'
                   '</marker></defs></svg>')
        assert count_data_marks(defined) == 0
        assert count_data_marks(defined.replace("</svg>", '<path d="M0 0 L1 1"/></svg>')) == 1

    def test_empty_string_is_blank(self):
        assert is_blank_diagram("")


class TestArrayStateTemplate:
    """Tests for array state diagram template."""

    def test_registry_has_array_state(self):
        assert "array_state" in DIAGRAM_REGISTRY

    def test_basic_render_with_highlights(self):
        hint = {
            "type": "array_state",
            "params": {
                "values": [3, 7, 2, 9],
                "indices": True,
                "highlights": {"2": "current", "0-1": "visited"},
            },
        }
        svg = render_diagram(hint)
        assert "<svg" in svg
        assert "array-cell-current" in svg
        assert "array-cell-visited" in svg
        assert ">3<" in svg
        assert ">0<" in svg

    def test_pointers_annotations_brackets_and_caption(self):
        hint = {
            "type": "array_state",
            "params": {
                "values": [1, 2, 3, 4],
                "indices": True,
                "pointers": [
                    {"index": 0, "label": "left", "position": "above"},
                    {"index": 3, "label": "right", "position": "below"},
                ],
                "annotations": [{"index": 1, "text": "pivot", "position": "above"}],
                "brackets": [{"from": 1, "to": 2, "label": "window", "position": "below"}],
                "caption": "Sliding window",
            },
        }
        svg = render_diagram(hint)
        assert "array-pointer-label" in svg
        assert "array-annotation" in svg
        assert "array-bracket-label" in svg
        assert "Sliding window" in svg

    def test_remaining_state(self):
        """Test the 'remaining' highlight state for unprocessed elements."""
        hint = {
            "type": "array_state",
            "params": {
                "values": [1, 2, 3, 4, 5],
                "highlights": {"0-1": "visited", "2": "current", "3-4": "remaining"},
            },
        }
        svg = render_diagram(hint)
        assert "array-cell-remaining" in svg
        assert "array-cell-visited" in svg
        assert "array-cell-current" in svg

    def test_custom_cell_dimensions(self):
        """Test custom cell width and height."""
        hint = {
            "type": "array_state",
            "params": {
                "values": [1, 2, 3],
                "cell_width": 80,
                "cell_height": 60,
            },
        }
        svg = render_diagram(hint)
        assert "<svg" in svg
        # Check that SVG is wider than default (3 * 80 + padding)
        assert 'width="280"' in svg  # 3 * 80 + 2 * 20


class TestMatrixStateTemplate:
    """Tests for matrix state diagram template."""

    def test_registry_has_matrix_state(self):
        assert "matrix_state" in DIAGRAM_REGISTRY

    def test_basic_render_with_highlights_path_and_arrows(self):
        hint = {
            "type": "matrix_state",
            "params": {
                "values": [
                    [1, 2, 3],
                    [4, 5, 6],
                    [7, 8, 9],
                ],
                "highlights": {"0,0": "visited", "1,1": "current", "2,2": "target"},
                "path": [[0, 0], [0, 1], [1, 1]],
                "row_labels": ["r0", "r1", "r2"],
                "col_labels": ["c0", "c1", "c2"],
                "arrows": [{"from": [0, 0], "to": [0, 1]}],
                "caption": "BFS traversal on grid",
            },
        }
        svg = render_diagram(hint)
        assert "<svg" in svg
        assert "matrix-cell-current" in svg
        assert "matrix-cell-visited" in svg
        assert "matrix-cell-target" in svg
        assert "matrix-path" in svg
        assert "matrix-arrow" in svg
        assert "BFS traversal on grid" in svg

class TestLinkedListTemplate:
    """Tests for linked list diagram template."""

    def test_registry_has_linked_list(self):
        assert "linked_list" in DIAGRAM_REGISTRY

    def test_basic_render_with_pointers_and_cycle(self):
        hint = {
            "type": "linked_list",
            "params": {
                "nodes": [
                    {"value": 1, "id": "n1"},
                    {"value": 2, "id": "n2"},
                    {"value": 3, "id": "n3"},
                ],
                "type": "singly",
                "pointers": [{"node": "n2", "label": "slow"}],
                "highlights": {"n1": "visited", "n2": "current"},
                "cycle_to": "n1",
                "show_null": True,
            },
        }
        svg = render_diagram(hint)
        assert "<svg" in svg
        assert "linked-node-current" in svg
        assert "linked-node-visited" in svg
        assert "linked-pointer-label" in svg
        assert "linked-list-cycle" in svg
        assert "null" in svg

    def test_doubly_linked_list(self):
        hint = {
            "type": "linked_list",
            "params": {
                "nodes": [
                    {"value": "A", "id": "a"},
                    {"value": "B", "id": "b"},
                ],
                "type": "doubly",
                "show_null": False,
            },
        }
        svg = render_diagram(hint)
        assert "linked-list-back-arrow" in svg


class TestBinaryTreeTemplate:
    """Tests for binary tree diagram template."""

    def test_registry_has_binary_tree(self):
        assert "binary_tree" in DIAGRAM_REGISTRY

    def test_basic_render_with_path_and_pointers(self):
        hint = {
            "type": "binary_tree",
            "params": {
                "root": {
                    "value": 8,
                    "left": {"value": 3, "right": {"value": 6}},
                    "right": {"value": 10},
                },
                "highlights": {"8": "visited", "6": "current"},
                "path": [8, 3, 6],
                "pointers": [{"value": 6, "label": "current"}],
                "annotations": [{"value": 8, "text": "root"}],
            },
        }
        svg = render_diagram(hint)
        assert "<svg" in svg
        assert "tree-node-current" in svg
        assert "tree-edge-path" in svg
        assert "tree-pointer-label" in svg
        assert "tree-annotation" in svg

    def test_heap_mode_with_array(self):
        hint = {
            "type": "binary_tree",
            "params": {
                "array": [None, 90, 80, 70],
                "heap_mode": True,
                "highlights": {"1": "current"},
            },
        }
        svg = render_diagram(hint)
        assert "tree-node-current" in svg


class TestStackTemplate:
    """Tests for stack diagram template."""

    def test_registry_has_stack(self):
        assert "stack" in DIAGRAM_REGISTRY

    def test_basic_render_with_operation_and_annotation(self):
        hint = {
            "type": "stack",
            "params": {
                "values": [3, 7, 2, 9],
                "orientation": "vertical",
                "top_label": "top →",
                "highlights": {"3": "current"},
                "operation": {"type": "push", "value": 5},
                "annotations": [{"index": 0, "text": "bottom"}],
                "caption": "Push 5 onto stack",
            },
        }
        svg = render_diagram(hint)
        assert "<svg" in svg
        assert "stack-cell-current" in svg
        assert "top →" in svg
        assert "push(5)" in svg
        assert "bottom" in svg

    def test_comparison_state_highlight(self):
        hint = {
            "type": "stack",
            "params": {
                "values": [1, 4, 2, 3],
                "highlights": {"1-2": "comparison"},
            },
        }
        svg = render_diagram(hint)
        assert "stack-cell-comparison" in svg


class TestCallStackTemplate:
    """Tests for call stack diagram template."""

    def test_registry_has_call_stack(self):
        assert "call_stack" in DIAGRAM_REGISTRY

    def test_basic_render_with_highlights_and_returns(self):
        hint = {
            "type": "call_stack",
            "params": {
                "frames": [
                    {"function": "fib", "args": {"n": 5}, "state": "waiting"},
                    {"function": "fib", "args": {"n": 4}, "state": "waiting"},
                    {"function": "fib", "args": {"n": 3}, "state": "waiting"},
                    {"function": "fib", "args": {"n": 2}, "state": "executing", "return": 1},
                ],
                "highlights": {"3": "current"},
                "show_return_values": True,
                "caption": "fib(2) returns 1",
            },
        }
        svg = render_diagram(hint)
        assert "<svg" in svg
        assert "call-stack-frame-current" in svg
        assert "fib(n=2) → returns 1" in svg
        assert "executing" in svg
        assert "fib(2) returns 1" in svg


class TestQueueTemplate:
    """Tests for queue diagram template."""

    def test_registry_has_queue(self):
        assert "queue" in DIAGRAM_REGISTRY

    def test_basic_render_with_enqueue_and_dequeue(self):
        hint = {
            "type": "queue",
            "params": {
                "values": [3, 7, 2, 9],
                "type": "deque",
                "front_label": "front",
                "back_label": "back",
                "highlights": {"0": "dequeue", "2": "current"},
                "operation": {"type": "enqueue", "value": 5, "end": "back"},
                "caption": "Dequeue from front, enqueue 5 at back",
            },
        }
        svg = render_diagram(hint)
        assert "<svg" in svg
        assert "queue-cell-dequeue" in svg
        assert "queue-cell-current" in svg
        assert "enqueue 5" in svg
        assert ">front<" in svg
        assert ">back<" in svg


class TestHashTableTemplate:
    """Tests for hash table diagram template."""

    def test_registry_has_hash_table(self):
        assert "hash_table" in DIAGRAM_REGISTRY

    def test_render_hash_table_with_chaining(self):
        hint = {
            "type": "hash_table",
            "params": {
                "buckets": 6,
                "entries": [
                    {"key": "apple", "value": 5, "bucket": 2},
                    {"key": "cherry", "value": 7, "bucket": 2},
                    {"key": "banana", "value": 3, "bucket": 4},
                ],
                "collision_strategy": "chaining",
                "highlights": {"bucket": 2, "key": "cherry"},
                "show_hash": True,
                "caption": "Collision at bucket 2",
            },
        }
        svg = render_diagram(hint)
        assert "<svg" in svg
        assert "hash-bucket-highlight" in svg
        assert "hash-entry-highlight" in svg
        assert "hash-chain-arrow" in svg
        assert "h(cherry)=2" in svg
        assert "Collision at bucket 2" in svg


class TestDPTableTemplate:
    """Tests for DP table diagram template."""

    def test_registry_has_dp_table(self):
        assert "dp_table" in DIAGRAM_REGISTRY

    def test_basic_render_with_highlights_and_arrows(self):
        hint = {
            "type": "dp_table",
            "params": {
                "values": [
                    [0, 0, 0],
                    [0, 1, 1],
                    [0, 1, 2],
                ],
                "row_labels": ["", "a", "b"],
                "col_labels": ["", "a", "b"],
                "highlights": {
                    "2,2": "current",
                    "1,2": "dependency",
                },
                "arrows": [
                    {"from": [1, 2], "to": [2, 2]},
                ],
                "formula": "dp[i][j] = max(...)",
                "caption": "LCS example",
            },
        }
        svg = render_diagram(hint)
        assert "<svg" in svg
        assert "dp-cell-current" in svg
        assert "dp-cell-dependency" in svg
        assert "dp-arrow" in svg
        assert "dp[i][j]" in svg
        assert "LCS example" in svg


class TestFunctionGraphTemplate:
    """Tests for function graph diagram template."""

    def test_registry_has_function_graph(self):
        assert "function_graph" in DIAGRAM_REGISTRY

    def test_basic_render(self):
        hint = {
            "type": "function_graph",
            "params": {"function": "x^2"}
        }
        svg = render_diagram(hint)
        assert "<svg" in svg
        assert "<path" in svg  # Function curve


    def test_builtin_functions(self):
        """Test various built-in function expressions."""
        functions = ["x", "x^2", "sin(x)", "cos(x)", "e^x", "sqrt(x)"]
        for func in functions:
            hint = {
                "type": "function_graph",
                "params": {"function": func}
            }
            svg = render_diagram(hint)
            assert "<svg" in svg

    def test_tangent_line(self):
        hint = {
            "type": "function_graph",
            "params": {"function": "x^2", "tangent_at": 1}
        }
        svg = render_diagram(hint)
        assert "stroke-dasharray" in svg  # Tangent uses dashed line

    def test_show_extrema(self):
        hint = {
            "type": "function_graph",
            "params": {"function": "sin(x)", "x_min": 0, "x_max": 6.28, "show_extrema": True}
        }
        svg = render_diagram(hint)
        # sin(x) has max at π/2 and min at 3π/2
        assert "func-point-max" in svg or "func-point-min" in svg

    def test_multiple_functions(self):
        hint = {
            "type": "function_graph",
            "params": {
                "functions": [
                    {"expr": "x^2", "color": "#FF0000", "label": "f(x)"},
                    {"expr": "x^3", "color": "#00FF00", "label": "g(x)"}
                ]
            }
        }
        svg = render_diagram(hint)
        assert "#FF0000" in svg
        assert "#00FF00" in svg
        assert "f(x)" in svg
        assert "g(x)" in svg

    def test_fill_area(self):
        hint = {
            "type": "function_graph",
            "params": {
                "function": "x^2",
                "fill_area": [{"from": 0, "to": 2, "color": "rgba(255,0,0,0.3)"}]
            }
        }
        svg = render_diagram(hint)
        assert "rgba(255,0,0,0.3)" in svg

    def test_extra_points(self):
        hint = {
            "type": "function_graph",
            "params": {
                "function": "x",
                "points": [{"x": 1, "y": 1, "label": "P", "color": "#FF9800"}]
            }
        }
        svg = render_diagram(hint)
        assert "#FF9800" in svg
        assert ">P<" in svg

    def test_axis_color_overrides_default_for_dark_decks(self):
        # Default keeps #333 (light backgrounds); an explicit axis_color must be
        # used for the axis stroke so it stays legible on a dark-themed deck.
        light = render_diagram({"type": "function_graph",
                                "params": {"function": "x^2", "x_min": -1, "x_max": 2}})
        assert 'stroke="#333"' in light
        dark = render_diagram({"type": "function_graph",
                               "params": {"function": "x^2", "x_min": -1, "x_max": 2,
                                          "axis_color": "#eaf0fa"}})
        assert 'stroke="#eaf0fa"' in dark

    def test_fill_area_bound_labels_mark_a_and_b(self):
        # from_label / to_label draw the integration bounds (drop-line + tick).
        hint = {"type": "function_graph",
                "params": {"function": "sqrt(x)", "x_min": 0, "x_max": 4,
                           "fill_area": [{"from": 0.5, "to": 3.5,
                                          "from_label": "a", "to_label": "b"}]}}
        svg = render_diagram(hint)
        assert ">a<" in svg and ">b<" in svg
        assert "stroke-dasharray" in svg          # boundary drop-lines drawn
        # No labels requested -> no stray a/b ticks.
        plain = render_diagram({"type": "function_graph",
                                "params": {"function": "sqrt(x)", "x_min": 0, "x_max": 4,
                                           "fill_area": [{"from": 0.5, "to": 3.5}]}})
        assert ">a<" not in plain and ">b<" not in plain

    def test_implicit_multiplication_linear(self):
        """Test implicit multiplication for linear expressions."""
        from straightedge.diagrams.templates.function_graph import _safe_eval

        # 2x + 3 at x=2 should be 7
        assert abs(_safe_eval("2x+3", 2) - 7) < 0.001
        assert abs(_safe_eval("2x + 3", 2) - 7) < 0.001
        # -3x + 1 at x=2 should be -5
        assert abs(_safe_eval("-3x+1", 2) - (-5)) < 0.001

    def test_implicit_multiplication_quadratic(self):
        """Test implicit multiplication for quadratic expressions."""
        from straightedge.diagrams.templates.function_graph import _safe_eval

        # 2x^2 at x=3 should be 18
        assert abs(_safe_eval("2x^2", 3) - 18) < 0.001
        # x^2 + 2x + 1 at x=3 should be 16
        assert abs(_safe_eval("x^2+2x+1", 3) - 16) < 0.001
        # 3x^2 - 2x + 1 at x=2 should be 9
        assert abs(_safe_eval("3x^2-2x+1", 2) - 9) < 0.001


class TestGraphTemplate:
    """Tests for graph diagram template."""

    def test_registry_has_graph(self):
        assert "graph" in DIAGRAM_REGISTRY

    def test_basic_render_with_highlights_and_weights(self):
        hint = {
            "type": "graph",
            "params": {
                "nodes": [
                    {"id": "A", "label": "A"},
                    {"id": "B", "label": "B"},
                    {"id": "C", "label": "C"},
                ],
                "edges": [
                    {"from": "A", "to": "B", "weight": 4},
                    {"from": "B", "to": "C", "weight": 2},
                ],
                "weighted": True,
                "layout": "grid",
                "highlights": {
                    "nodes": {"B": "current"},
                    "edges": [["A", "B"]],
                },
                "path": ["A", "B", "C"],
                "distance_labels": {"A": 0, "B": 4, "C": 6},
                "caption": "Dijkstra sample",
            },
        }
        svg = render_diagram(hint)
        assert "<svg" in svg
        assert "graph-node-current" in svg
        assert "graph-edge-highlight" in svg or "graph-edge-path" in svg
        assert "graph-edge-weight" in svg
        assert "graph-distance-label" in svg
        assert "Dijkstra sample" in svg

    def test_directed_edges_render_markers(self):
        hint = {
            "type": "graph",
            "params": {
                "nodes": [
                    {"id": "A", "label": "A"},
                    {"id": "B", "label": "B"},
                ],
                "edges": [{"from": "A", "to": "B"}],
                "directed": True,
                "layout": "circular",
            },
        }
        svg = render_diagram(hint)
        # The id carries a per-diagram suffix so two graphs on one page cannot
        # collide — see TestGraphMarkerIdCollision.
        marker = re.search(r'<marker id="(graph-arrow-[0-9a-f]+)"', svg)
        assert marker, svg[:400]
        assert f'marker-end="url(#{marker.group(1)})"' in svg
        assert 'marker-end="None"' not in svg

    def test_implicit_multiplication_trig(self):
        """Test implicit multiplication with trig functions."""
        from straightedge.diagrams.templates.function_graph import _safe_eval
        import math

        # 2sin(x) at x=pi/2 should be 2
        assert abs(_safe_eval("2sin(x)", math.pi / 2) - 2) < 0.001
        # 3cos(x) at x=0 should be 3
        assert abs(_safe_eval("3cos(x)", 0) - 3) < 0.001

    def test_implicit_multiplication_constants(self):
        """Test implicit multiplication with constants like pi, tau, phi."""
        from straightedge.diagrams.templates.function_graph import _safe_eval
        import math

        # 2pi should be approximately 6.283
        assert abs(_safe_eval("2pi", 0) - 2 * math.pi) < 0.001
        # tau/2 should equal pi
        assert abs(_safe_eval("tau/2", 0) - math.pi) < 0.001

    def test_implicit_multiplication_parentheses(self):
        """Test implicit multiplication with parentheses."""
        from straightedge.diagrams.templates.function_graph import _safe_eval

        # 2(x+1) at x=2 should be 6
        assert abs(_safe_eval("2(x+1)", 2) - 6) < 0.001
        # (x+1)(x-1) at x=3 should be 8 (difference of squares: 4*2)
        assert abs(_safe_eval("(x+1)(x-1)", 3) - 8) < 0.001
        # (x+1)x at x=2 should be 6
        assert abs(_safe_eval("(x+1)x", 2) - 6) < 0.001
        # x(x+1) at x=2 should be 6
        assert abs(_safe_eval("x(x+1)", 2) - 6) < 0.001

    def test_implicit_multiplication_conversion(self):
        """Test the _add_implicit_multiplication function directly."""
        from straightedge.diagrams.templates.function_graph import _add_implicit_multiplication

        assert _add_implicit_multiplication("2x") == "2*x"
        assert _add_implicit_multiplication("2sin(x)") == "2*sin(x)"
        assert _add_implicit_multiplication("2pi") == "2*pi"
        assert _add_implicit_multiplication("2(x+1)") == "2*(x+1)"
        assert _add_implicit_multiplication("(x+1)(x-1)") == "(x+1)*(x-1)"
        assert _add_implicit_multiplication("(x+1)x") == "(x+1)*x"
        # Function names should NOT get * inserted
        assert _add_implicit_multiplication("sin(x)") == "sin(x)"
        assert _add_implicit_multiplication("cos(2x)") == "cos(2*x)"

    def test_implicit_multiplication_in_render(self):
        """Test that implicit multiplication works in full diagram render."""
        # Linear function with implicit multiplication
        hint = {
            "type": "function_graph",
            "params": {"function": "2x+1", "x_min": -2, "x_max": 2}
        }
        svg = render_diagram(hint)
        assert "<svg" in svg
        assert "<path" in svg

        # Quadratic with implicit multiplication
        hint = {
            "type": "function_graph",
            "params": {"function": "x^2+2x+1", "x_min": -3, "x_max": 1}
        }
        svg = render_diagram(hint)
        assert "<svg" in svg
        assert "<path" in svg


class TestUnitCircleTemplate:
    """Tests for unit circle diagram template."""

    def test_registry_has_unit_circle(self):
        assert "unit_circle" in DIAGRAM_REGISTRY

    def test_basic_render(self):
        hint = {
            "type": "unit_circle",
            "params": {"angle": 45}
        }
        svg = render_diagram(hint)
        assert "<svg" in svg
        assert "uc-circle" in svg

    def test_shows_reference_triangle(self):
        hint = {
            "type": "unit_circle",
            "params": {"angle": 30, "show_triangle": True}
        }
        svg = render_diagram(hint)
        assert "uc-triangle" in svg

    def test_shows_sin_cos(self):
        hint = {
            "type": "unit_circle",
            "params": {"angle": 45, "show_sin": True, "show_cos": True}
        }
        svg = render_diagram(hint)
        assert "sin=" in svg
        assert "cos=" in svg

    def test_shows_tangent(self):
        hint = {
            "type": "unit_circle",
            "params": {"angle": 45, "show_tan": True}
        }
        svg = render_diagram(hint)
        # Tangent line is drawn in purple
        assert "#9C27B0" in svg

    def test_shows_common_angles(self):
        hint = {
            "type": "unit_circle",
            "params": {"show_common_angles": True}
        }
        svg = render_diagram(hint)
        # Should show angle labels like π/6, π/4, etc
        assert "uc-angle-label" in svg
        assert "π" in svg

    def test_shows_angle_arc(self):
        hint = {
            "type": "unit_circle",
            "params": {"angle": 60, "show_arc": True}
        }
        svg = render_diagram(hint)
        assert "uc-arc" in svg
        assert "60" in svg and "°" in svg  # Angle shown with degree symbol

    def test_shows_coordinates(self):
        hint = {
            "type": "unit_circle",
            "params": {"angle": 45, "show_coordinates": True}
        }
        svg = render_diagram(hint)
        assert "uc-coord-label" in svg
        # Should show coordinate like (0.71, 0.71)
        assert "0.7" in svg

    def test_point_on_circle(self):
        hint = {
            "type": "unit_circle",
            "params": {"angle": 90}
        }
        svg = render_diagram(hint)
        assert "uc-point" in svg


class TestRiemannSumTemplate:
    """Tests for Riemann sum diagram template."""

    def test_registry_has_riemann_sum(self):
        assert "riemann_sum" in DIAGRAM_REGISTRY

    def test_basic_render(self):
        hint = {
            "type": "riemann_sum",
            "params": {"function": "x^2", "a": 0, "b": 2, "n": 5}
        }
        svg = render_diagram(hint)
        assert "<svg" in svg
        assert "<rect" in svg or "<path" in svg  # Rectangles or trapezoids

    def test_left_method(self):
        hint = {
            "type": "riemann_sum",
            "params": {"function": "x^2", "a": 0, "b": 2, "n": 4, "method": "left"}
        }
        svg = render_diagram(hint)
        # left/right/midpoint draw n axis-aligned rectangles (method name is no
        # longer printed as debug text — that was a chart artifact).
        assert "<svg" in svg
        assert svg.count("<rect") >= 4

    def test_right_method(self):
        hint = {
            "type": "riemann_sum",
            "params": {"function": "x^2", "a": 0, "b": 2, "n": 4, "method": "right"}
        }
        svg = render_diagram(hint)
        assert "<svg" in svg and svg.count("<rect") >= 4

    def test_midpoint_method(self):
        hint = {
            "type": "riemann_sum",
            "params": {"function": "x^2", "a": 0, "b": 2, "n": 4, "method": "midpoint"}
        }
        svg = render_diagram(hint)
        assert "<svg" in svg and svg.count("<rect") >= 4

    def test_trapezoid_method(self):
        hint = {
            "type": "riemann_sum",
            "params": {"function": "x^2", "a": 0, "b": 2, "n": 4, "method": "trapezoid"}
        }
        svg = render_diagram(hint)
        # trapezoid rule draws filled polygons (paths), not axis-aligned rects
        assert "<svg" in svg and "<path" in svg

    def test_shows_curve(self):
        hint = {
            "type": "riemann_sum",
            "params": {"function": "x^2", "show_curve": True}
        }
        svg = render_diagram(hint)
        assert "<path" in svg

    def test_shows_area_value(self):
        hint = {
            "type": "riemann_sum",
            "params": {"function": "x^2", "a": 0, "b": 2, "n": 5, "show_area_value": True}
        }
        svg = render_diagram(hint)
        assert "Area" in svg
        assert "rs-area-label" in svg

    def test_shows_bounds(self):
        hint = {
            "type": "riemann_sum",
            "params": {"function": "x^2", "a": 1, "b": 3}
        }
        svg = render_diagram(hint)
        assert "a=1" in svg
        assert "b=3" in svg

    def test_different_functions(self):
        functions = ["x", "x^2", "sin(x)", "1/(1+x^2)"]
        for func in functions:
            hint = {
                "type": "riemann_sum",
                "params": {"function": func, "a": 0, "b": 2}
            }
            svg = render_diagram(hint)
            assert "<svg" in svg


class TestPolarGraphTemplate:
    """Tests for polar graph diagram template."""

    def test_registry_has_polar_graph(self):
        assert "polar_graph" in DIAGRAM_REGISTRY

    def test_basic_render(self):
        hint = {
            "type": "polar_graph",
            "params": {"function": "1+cos(theta)"}
        }
        svg = render_diagram(hint)
        assert "<svg" in svg
        assert "<path" in svg  # Curve

    def test_cardioid(self):
        hint = {
            "type": "polar_graph",
            "params": {"function": "1+cos(theta)"}
        }
        svg = render_diagram(hint)
        assert "<svg" in svg

    def test_rose_curve(self):
        hint = {
            "type": "polar_graph",
            "params": {"function": "cos(3*theta)"}
        }
        svg = render_diagram(hint)
        assert "<svg" in svg

    def test_spiral(self):
        hint = {
            "type": "polar_graph",
            "params": {"function": "theta/pi"}
        }
        svg = render_diagram(hint)
        assert "<svg" in svg

    def test_shows_polar_grid(self):
        hint = {
            "type": "polar_graph",
            "params": {"function": "1", "show_grid": True}
        }
        svg = render_diagram(hint)
        assert "polar-grid" in svg

    def test_shows_radial_rays(self):
        hint = {
            "type": "polar_graph",
            "params": {"function": "1", "show_rays": True}
        }
        svg = render_diagram(hint)
        assert "polar-ray" in svg
        # Should show angle labels like 30°, 60°, etc
        assert "°" in svg

    def test_shows_axes(self):
        hint = {
            "type": "polar_graph",
            "params": {"function": "1", "show_axes": True}
        }
        svg = render_diagram(hint)
        assert "polar-axis" in svg

    def test_point_highlight(self):
        hint = {
            "type": "polar_graph",
            "params": {"function": "1+cos(theta)", "point_at": 1.57}
        }
        svg = render_diagram(hint)
        assert "polar-point" in svg
        assert "polar-coord-label" in svg

    def test_multiple_functions(self):
        hint = {
            "type": "polar_graph",
            "params": {
                "functions": [
                    {"expr": "1+cos(theta)", "color": "#FF0000"},
                    {"expr": "1-cos(theta)", "color": "#00FF00"}
                ]
            }
        }
        svg = render_diagram(hint)
        assert "#FF0000" in svg
        assert "#00FF00" in svg

    def test_custom_theta_range(self):
        hint = {
            "type": "polar_graph",
            "params": {
                "function": "theta",
                "theta_min": 0,
                "theta_max": 6.28  # 2π
            }
        }
        svg = render_diagram(hint)
        assert "<svg" in svg

    def test_with_title(self):
        hint = {
            "type": "polar_graph",
            "params": {"function": "1+cos(theta)", "title": "Cardioid"}
        }
        svg = render_diagram(hint)
        assert "Cardioid" in svg
        assert "polar-title" in svg


class TestStepFunctionTemplate:
    """Tests for step function diagram template (binary search visualization)."""

    def test_registry_has_step_function(self):
        assert "step_function" in DIAGRAM_REGISTRY

    def test_basic_render(self):
        hint = {
            "type": "step_function",
            "params": {"transition_x": 4}
        }
        svg = render_diagram(hint)
        assert "<svg" in svg
        assert "<line" in svg  # Step function lines

    def test_transition_point(self):
        """Test that transition point is rendered with circles."""
        hint = {
            "type": "step_function",
            "params": {"transition_x": 5, "x_min": 1, "x_max": 10}
        }
        svg = render_diagram(hint)
        assert "<circle" in svg  # Filled and open circles at transition

    def test_region_labels(self):
        """Test that region labels appear."""
        hint = {
            "type": "step_function",
            "params": {
                "transition_x": 4,
                "left_label": "Infeasible",
                "right_label": "Feasible"
            }
        }
        svg = render_diagram(hint)
        assert "Infeasible" in svg
        assert "Feasible" in svg

    def test_default_labels(self):
        """Test default False/True labels."""
        hint = {
            "type": "step_function",
            "params": {"transition_x": 4}
        }
        svg = render_diagram(hint)
        assert "False" in svg
        assert "True" in svg

    def test_custom_colors(self):
        """Test custom colors for regions."""
        hint = {
            "type": "step_function",
            "params": {
                "transition_x": 4,
                "left_color": "#FF0000",
                "right_color": "#00FF00"
            }
        }
        svg = render_diagram(hint)
        assert "#FF0000" in svg
        assert "#00FF00" in svg

    def test_transition_label(self):
        """Test label at transition point."""
        hint = {
            "type": "step_function",
            "params": {
                "transition_x": 4,
                "transition_label": "k* = 4"
            }
        }
        svg = render_diagram(hint)
        assert "k* = 4" in svg

    def test_axis_labels(self):
        """Test custom axis labels."""
        hint = {
            "type": "step_function",
            "params": {
                "transition_x": 4,
                "x_label": "capacity",
                "y_label": "canFinish(c)"
            }
        }
        svg = render_diagram(hint)
        assert "capacity" in svg
        assert "canFinish(c)" in svg

    def test_show_markers(self):
        """Test X and checkmark markers."""
        hint = {
            "type": "step_function",
            "params": {
                "transition_x": 4,
                "show_markers": True,
                "x_min": 1,
                "x_max": 7
            }
        }
        svg = render_diagram(hint)
        # Should have X markers (rendered as text "X")
        assert ">X<" in svg
        # Should have checkmark markers (Unicode ✓)
        assert "✓" in svg or "\\u2713" in svg or ">✓<" in svg

    def test_hide_markers(self):
        """Test markers can be hidden."""
        hint = {
            "type": "step_function",
            "params": {
                "transition_x": 4,
                "show_markers": False
            }
        }
        svg = render_diagram(hint)
        # Should NOT have X markers
        assert ">X<" not in svg

    def test_custom_marker_positions(self):
        """Test custom marker positions."""
        hint = {
            "type": "step_function",
            "params": {
                "transition_x": 5,
                "marker_positions": [2, 3, 5, 6, 7],
                "x_min": 1,
                "x_max": 10
            }
        }
        svg = render_diagram(hint)
        assert "<svg" in svg

    def test_show_grid(self):
        """Test grid lines."""
        hint = {
            "type": "step_function",
            "params": {
                "transition_x": 4,
                "show_grid": True
            }
        }
        svg = render_diagram(hint)
        assert "grid-line" in svg

    def test_hide_grid(self):
        """Test grid can be hidden."""
        hint = {
            "type": "step_function",
            "params": {
                "transition_x": 4,
                "show_grid": False
            }
        }
        svg = render_diagram(hint)
        # Check for actual grid line elements, not CSS class definition
        assert 'class="grid-line"' not in svg

    def test_with_title(self):
        """Test title rendering."""
        hint = {
            "type": "step_function",
            "params": {
                "transition_x": 4,
                "title": "Binary Search on Answer Space"
            }
        }
        svg = render_diagram(hint)
        assert "Binary Search on Answer Space" in svg

    def test_custom_dimensions(self):
        """Test custom SVG dimensions."""
        hint = {
            "type": "step_function",
            "params": {
                "transition_x": 4,
                "width": 500,
                "height": 350
            }
        }
        svg = render_diagram(hint)
        assert 'width="500"' in svg
        assert 'height="350"' in svg

    def test_custom_x_range(self):
        """Test custom x-axis range."""
        hint = {
            "type": "step_function",
            "params": {
                "transition_x": 50,
                "x_min": 10,
                "x_max": 100
            }
        }
        svg = render_diagram(hint)
        assert "<svg" in svg
        # Tick labels should include values in range
        assert ">50<" in svg  # Transition point highlighted


class TestEnvironmentDiagramTemplate:
    """Tests for environment diagram template."""

    def test_basic_render(self):
        hint = {
            "type": "environment_diagram",
            "params": {
                "frames": [
                    {
                        "id": "global",
                        "label": "Global",
                        "parent": None,
                        "bindings": [
                            {"name": "make_adder", "value": "func:f0"},
                            {"name": "add5", "value": "func:f1"},
                        ],
                    },
                    {
                        "id": "f1",
                        "label": "f1: make_adder",
                        "parent": "global",
                        "bindings": [{"name": "n", "value": "5"}],
                    },
                ],
                "functions": [
                    {
                        "id": "f0",
                        "params": ["n"],
                        "body": "lambda x: x + n",
                        "parent_frame": "global",
                    },
                    {
                        "id": "f1",
                        "params": ["x"],
                        "body": "x + n",
                        "parent_frame": "f1",
                    },
                ],
                "highlights": {
                    "frames": {"f1": "current"},
                    "bindings": {"f1.n": "target"},
                    "functions": {"f1": "current"},
                },
                "caption": "Environment after add5 = make_adder(5)",
            },
        }
        svg = render_diagram(hint)
        assert "<svg" in svg
        assert "Environment after add5 = make_adder(5)" in svg
        assert "env-frame-current" in svg
        assert "env-binding-target" in svg
        assert "env-function-current" in svg

    def test_handles_empty_inputs(self):
        hint = {"type": "environment_diagram", "params": {}}
        svg = render_diagram(hint)
        assert "<svg" in svg

    FRAMES_ONLY = [
        {"id": "global", "label": "Global",
         "bindings": [{"name": "make_adder", "value": "func make_adder(n)"}]},
        {"id": "f1", "label": "f1: make_adder", "parent": "global",
         "bindings": [{"name": "n", "value": "3"}]},
        {"id": "f2", "label": "f2: adder", "parent": "f1",
         "bindings": [{"name": "x", "value": "4"}, {"name": "return", "value": "7"}]},
    ]

    @staticmethod
    def _canvas(svg):
        import re
        match = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg)
        return float(match.group(1)), float(match.group(2))

    def test_frames_alone_do_not_reserve_the_function_column(self):
        """A diagram of frames carried an empty right half reserved for
        function objects it did not have; a consumer fitting the canvas to a
        box then shrank the frames to make room for nothing."""
        svg = render_diagram({"type": "environment_diagram",
                              "params": {"frames": self.FRAMES_ONLY}})
        width, _ = self._canvas(svg)
        assert width == 40 + 260 + 40   # frame_x + frame_width + margin

    def test_function_column_is_kept_when_functions_are_given(self):
        svg = render_diagram({"type": "environment_diagram", "params": {
            "frames": self.FRAMES_ONLY,
            "functions": [{"id": "f0", "params": ["x"], "body": "x + n", "parent_frame": "f1"}],
        }})
        width, _ = self._canvas(svg)
        assert width > 40 + 260 + 40
        assert "env-function" in svg

    def test_row_layout_places_frames_side_by_side(self):
        import re
        svg = render_diagram({"type": "environment_diagram",
                              "params": {"frames": self.FRAMES_ONLY, "layout": "row"}})
        width, height = self._canvas(svg)
        xs = sorted({float(m) for m in re.findall(r'class="env-frame env-frame-\w+"[^>]*\bx="([\d.]+)"', svg)}
                    | {float(m) for m in re.findall(r'<rect[^>]*\bx="([\d.]+)"[^>]*class="env-frame ', svg)})
        assert len(xs) == 3, xs                      # three distinct columns
        assert width == 40 + 3 * 260 + 2 * 28 + 40    # frames in a row, tight canvas
        assert height < width                         # a landscape figure
        assert svg.count('class="env-parent-arrow"') == 2

    def test_column_layout_is_the_default_and_unchanged(self):
        stacked = render_diagram({"type": "environment_diagram",
                                  "params": {"frames": self.FRAMES_ONLY}})
        explicit = render_diagram({"type": "environment_diagram",
                                   "params": {"frames": self.FRAMES_ONLY, "layout": "column"}})
        assert stacked == explicit
        row = render_diagram({"type": "environment_diagram",
                              "params": {"frames": self.FRAMES_ONLY, "layout": "row"}})
        col_w, col_h = self._canvas(stacked)
        row_w, row_h = self._canvas(row)
        assert col_h > row_h and col_w < row_w   # the column stacks, the row spreads


class TestGraphSelfLoops:
    """A self-loop is the same node twice — the common shape in Markov chains
    and automata ("stay in Bull with probability 0.9").

    Drawn as a straight line it collapses to a zero-length segment: invisible,
    with its weight label stamped on top of the node label. It must render as
    an arc above the node instead.
    """

    CHAIN = {
        "type": "graph",
        "params": {
            "nodes": [{"id": "Bull", "label": "Bull"}, {"id": "Bear", "label": "Bear"}],
            "edges": [
                {"from": "Bull", "to": "Bear", "weight": "0.1"},
                {"from": "Bear", "to": "Bull", "weight": "0.2"},
                {"from": "Bull", "to": "Bull", "weight": "0.9"},
                {"from": "Bear", "to": "Bear", "weight": "0.8"},
            ],
            "directed": True,
            "weighted": True,
            "layout": "circular",
        },
    }

    def test_self_loop_renders_an_arc(self):
        svg = render_diagram(self.CHAIN)
        assert len(re.findall(r"<path[^>]*\sA\s", svg)) == 2

    def test_no_zero_length_edge_is_emitted(self):
        svg = render_diagram(self.CHAIN)
        assert not re.search(r'x1="([\d.]+)"\s+y1="([\d.]+)"\s+x2="\1"\s+y2="\2"', svg)

    def test_every_transition_probability_is_labelled(self):
        svg = render_diagram(self.CHAIN)
        for weight in ("0.9", "0.8", "0.1", "0.2"):
            assert weight in svg

    def test_self_loop_weight_sits_above_the_node(self):
        """Not on top of the node label, which is what the bug produced."""
        svg = render_diagram(self.CHAIN)
        node_ys = [float(m) for m in re.findall(r'<circle[^>]*cy="([\d.]+)"', svg)]
        loop_label_ys = [
            float(y)
            for y, txt in re.findall(
                r'<text[^>]*y="([\d.-]+)"[^>]*class="graph-edge-weight"[^>]*>([^<]*)<', svg
            )
            if txt in ("0.9", "0.8")
        ]
        if not loop_label_ys:  # attribute order differs; fall back to any weight label
            loop_label_ys = [
                float(y)
                for y in re.findall(
                    r'<text[^>]*class="graph-edge-weight"[^>]*y="([\d.-]+)"', svg
                )
            ]
        assert loop_label_ys, "self-loop weight label was not emitted"
        assert min(loop_label_ys) < min(node_ys)

    def test_undirected_self_loop_still_renders(self):
        params = {**self.CHAIN["params"], "directed": False}
        svg = render_diagram({"type": "graph", "params": params})
        assert len(re.findall(r"<path[^>]*\sA\s", svg)) == 2

    def test_transitions_between_states_still_render(self):
        """The loops must not swallow the transitions.

        Bull↔Bear is a reciprocal pair, so these draw as two bowed curves
        rather than two straight lines — see TestGraphReciprocalEdges.
        """
        svg = render_diagram(self.CHAIN)
        assert len(re.findall(r"<path[^>]*\sQ\s", svg)) == 2


class TestGraphReciprocalEdges:
    """A→B alongside B→A is the normal shape of a Markov chain.

    Drawn as two straight lines they are the *same* line, with both weights
    stamped on the same midpoint. On a transition diagram the probabilities
    are the content, so overlapping them loses the slide.
    """

    CHAIN = {
        "type": "graph",
        "params": {
            "nodes": [
                {"id": "Bull", "label": "Bull", "x": 0.25, "y": 0.55},
                {"id": "Bear", "label": "Bear", "x": 0.75, "y": 0.55},
            ],
            "edges": [
                {"from": "Bull", "to": "Bear", "weight": "0.1"},
                {"from": "Bear", "to": "Bull", "weight": "0.2"},
            ],
            "directed": True,
            "weighted": True,
            "layout": "custom",
            "width": 640,
            "height": 360,
            "node_radius": 34,
        },
    }

    @staticmethod
    def _weight_labels(svg):
        return re.findall(
            r'<text x="([\d.-]+)" y="([\d.-]+)" class="graph-edge-weight"[^>]*>([^<]*)<',
            svg,
        )

    def test_opposite_weights_do_not_share_a_position(self):
        labels = self._weight_labels(render_diagram(self.CHAIN))
        positions = [(x, y) for x, y, _ in labels]
        assert len(positions) == 2
        assert len(set(positions)) == 2

    def test_reciprocal_pair_bows_to_opposite_sides(self):
        """Not merely different positions — one above the line, one below."""
        labels = self._weight_labels(render_diagram(self.CHAIN))
        ys = sorted(float(y) for _, y, _ in labels)
        midline = 50 + 0.55 * (360 - 100)  # the shared y of both nodes
        assert ys[0] < midline < ys[1]

    def test_reciprocal_edges_render_as_curves(self):
        svg = render_diagram(self.CHAIN)
        assert len(re.findall(r"<path[^>]*\sQ\s", svg)) == 2
        assert "<line" not in svg

    def test_a_lone_edge_stays_straight(self):
        """Only a reciprocated edge needs bowing; one-way edges stay simple."""
        params = {**self.CHAIN["params"], "edges": [{"from": "Bull", "to": "Bear", "weight": "0.1"}]}
        svg = render_diagram({"type": "graph", "params": params})
        assert len(re.findall(r"<line", svg)) == 1
        assert not re.findall(r"<path[^>]*\sQ\s", svg)

    def test_directed_edge_stops_short_of_the_node(self):
        """Centre-to-centre hides the arrowhead under the target circle."""
        svg = render_diagram(
            {"type": "graph", "params": {**self.CHAIN["params"],
                                         "edges": [{"from": "Bull", "to": "Bear"}]}}
        )
        m = re.search(r'<line x1="([\d.]+)" y1="[\d.]+" x2="([\d.]+)"', svg)
        assert m
        x1, x2 = float(m.group(1)), float(m.group(2))
        node_x1, node_x2 = 50 + 0.25 * 540, 50 + 0.75 * 540
        radius = 34
        assert x1 == pytest.approx(node_x1 + radius, abs=1.0)
        assert x2 == pytest.approx(node_x2 - radius, abs=1.0)


class TestGraphLongRangeEdges:
    """An edge must not be drawn through a node it does not connect.

    The shape this protects is the fallback arrow in a pattern-matching chain —
    "you had HT, you threw a tail, go back to the start" — where the long arrow
    home is the entire point of the picture. Drawn straight it crosses the node
    between, and its label lands on top of that node.
    """

    CHAIN = {
        "type": "graph",
        "params": {
            "nodes": [
                {"id": "0", "label": "start", "x": 0.12, "y": 0.5},
                {"id": "1", "label": "H", "x": 0.40, "y": 0.5},
                {"id": "2", "label": "HT", "x": 0.68, "y": 0.5},
            ],
            "edges": [
                {"from": "0", "to": "1", "weight": "H"},
                {"from": "1", "to": "2", "weight": "T"},
                {"from": "2", "to": "0", "weight": "T"},
            ],
            "directed": True,
            "weighted": True,
            "layout": "custom",
            "width": 760,
            "height": 340,
            "node_radius": 32,
        },
    }

    def test_an_edge_that_would_cross_a_node_is_bowed(self):
        svg = render_diagram(self.CHAIN)
        # 2 -> 0 skips node 1, so it must be a curve; the neighbours stay straight.
        assert len(re.findall(r"<path[^>]*\sQ\s", svg)) == 1
        assert len(re.findall(r"<line", svg)) == 2

    def test_neighbouring_edges_are_left_straight(self):
        """Only the crossing edge changes; adjacent hops keep their simple line."""
        params = {**self.CHAIN["params"],
                  "edges": [{"from": "0", "to": "1", "weight": "H"},
                            {"from": "1", "to": "2", "weight": "T"}]}
        svg = render_diagram({"type": "graph", "params": params})
        assert not re.findall(r"<path[^>]*\sQ\s", svg)
        assert len(re.findall(r"<line", svg)) == 2

    def test_every_label_survives(self):
        svg = render_diagram(self.CHAIN)
        labels = re.findall(r'class="graph-edge-weight"[^>]*>([^<]*)<', svg)
        assert sorted(labels) == ["H", "T", "T"]


class TestGraphCanvasFit:
    """The canvas is cropped to the drawing, not left at the declared size.

    A row of three nodes in a 700x340 box filled 48% of its width and 21% of
    its height, and the slide showed a small diagram adrift inside a large
    white card. Nothing moves — the viewBox narrows to the content.
    """

    WIDE = {
        "type": "graph",
        "params": {
            "nodes": [{"id": "A", "label": "A", "x": 0.3, "y": 0.5},
                      {"id": "B", "label": "B", "x": 0.7, "y": 0.5}],
            "edges": [{"from": "A", "to": "B", "weight": "1"}],
            "directed": True, "weighted": True, "layout": "custom",
            "width": 900, "height": 600, "node_radius": 30,
        },
    }

    def test_canvas_is_smaller_than_the_declared_box(self):
        svg = render_diagram(self.WIDE)
        w = int(re.search(r'width="(\d+)"', svg).group(1))
        h = int(re.search(r'height="(\d+)"', svg).group(1))
        assert w < 900 and h < 600

    def test_a_viewbox_is_emitted(self):
        svg = render_diagram(self.WIDE)
        assert re.search(r'viewBox="[-\d. ]+"', svg)

    def test_the_drawing_fills_most_of_the_canvas(self):
        """The defect was a drawing filling a fifth of its height."""
        svg = render_diagram(self.WIDE)
        h = int(re.search(r'height="(\d+)"', svg).group(1))
        radius = 30
        # Two nodes on one row: content height is the node plus its loop room.
        assert h < radius * 8

    def test_a_caption_still_renders_below_the_drawing(self):
        params = {**self.WIDE["params"], "caption": "flow balance"}
        svg = render_diagram({"type": "graph", "params": params})
        assert "flow balance" in svg
        captioned_h = int(re.search(r'height="(\d+)"', svg).group(1))
        bare_h = int(re.search(r'height="(\d+)"', render_diagram(self.WIDE)).group(1))
        assert captioned_h > bare_h  # room was made for it

    def test_every_edge_label_survives_the_crop(self):
        params = {**self.WIDE["params"],
                  "edges": [{"from": "A", "to": "B", "weight": "0.1"},
                            {"from": "B", "to": "A", "weight": "0.2"},
                            {"from": "A", "to": "A", "weight": "0.9"}]}
        svg = render_diagram({"type": "graph", "params": params})
        for weight in ("0.1", "0.2", "0.9"):
            assert weight in svg


class TestGraphMarkerIdCollision:
    """Two graphs on one page must not share an arrowhead id.

    Every graph used to define `id="graph-arrow"`. That is correct in
    isolation and wrong the moment a page holds two, which the freeform deck
    always does — it inlines every figure into one HTML document. A browser
    resolves `url(#graph-arrow)` to the first match in the *document*, so the
    first diagram kept its arrows and every later one lost them: its reference
    pointed into a different SVG tree, which Chromium will not paint.

    Rendering one SVG alone cannot reproduce this, which is exactly how it
    shipped in a video with two arrowless state machines.
    """

    @staticmethod
    def _graph(label: str):
        return {
            "type": "graph",
            "params": {
                "nodes": [{"id": "A", "label": label, "x": 0.3, "y": 0.5},
                          {"id": "B", "label": "B", "x": 0.7, "y": 0.5}],
                "edges": [{"from": "A", "to": "B", "weight": "1"}],
                "directed": True, "weighted": True, "layout": "custom",
                "width": 600, "height": 300, "node_radius": 30,
            },
        }

    def test_two_diagrams_get_different_marker_ids(self):
        first = render_diagram(self._graph("first"))
        second = render_diagram(self._graph("second"))
        id_a = re.search(r'<marker id="([^"]+)"', first).group(1)
        id_b = re.search(r'<marker id="([^"]+)"', second).group(1)
        assert id_a != id_b

    def test_each_diagram_references_its_own_marker(self):
        for label in ("one", "two"):
            svg = render_diagram(self._graph(label))
            marker = re.search(r'<marker id="([^"]+)"', svg).group(1)
            refs = set(re.findall(r"url\(#([^)]+)\)", svg))
            assert refs == {marker}, (label, marker, refs)

    def test_the_same_diagram_is_still_deterministic(self):
        """Re-rendering identical input must not churn the id."""
        a = render_diagram(self._graph("same"))
        b = render_diagram(self._graph("same"))
        assert a == b

    def test_concatenated_documents_have_no_duplicate_ids(self):
        """The shape the deck actually produces: several SVGs, one page."""
        page = "".join(render_diagram(self._graph(x)) for x in ("a", "b", "c"))
        ids = re.findall(r'<marker id="([^"]+)"', page)
        assert len(ids) == 3
        assert len(set(ids)) == 3
