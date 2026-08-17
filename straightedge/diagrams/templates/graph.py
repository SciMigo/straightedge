"""Graph visualization template for CS/data structure diagrams."""

from __future__ import annotations

import hashlib
import math
from typing import Any, Dict, List, Tuple

from ..registry import register
from ..renderer import (
    DEFAULT_STYLES,
    circle,
    defs,
    line,
    path,
    style,
    svg_document,
    text,
)


STATE_COLORS = {
    "default": "#f8f9fa",
    "current": "#fff3cd",
    "visited": "#d1ecf1",
    "target": "#d4edda",
    "found": "#d4edda",
    "invalid": "#f8d7da",
    "rejected": "#f8d7da",
    "comparison": "#FF9800",
    "path": "#9C27B0",
}


def _normalize_highlight_nodes(highlights: Any) -> Dict[str, str]:
    if not isinstance(highlights, dict):
        return {}
    nodes = (
        highlights.get("nodes", {})
        if isinstance(highlights.get("nodes", {}), dict)
        else {}
    )
    result: Dict[str, str] = {}
    for key, state in nodes.items():
        if isinstance(state, str):
            result[str(key)] = state
    return result


def _normalize_highlight_edges(highlights: Any) -> List[Tuple[str, str]]:
    if not isinstance(highlights, dict):
        return []
    edges = highlights.get("edges", [])
    if not isinstance(edges, list):
        return []
    result = []
    for edge in edges:
        if not isinstance(edge, (list, tuple)) or len(edge) != 2:
            continue
        result.append((str(edge[0]), str(edge[1])))
    return result


def _scale_custom_position(value: float, min_val: float, max_val: float) -> float:
    if 0 <= value <= 1:
        return min_val + value * (max_val - min_val)
    return value


def _circular_layout(
    node_ids: List[str],
    width: int,
    height: int,
    padding: int,
) -> Dict[str, Tuple[float, float]]:
    count = len(node_ids)
    if count == 0:
        return {}
    center_x = width / 2
    center_y = height / 2
    radius = max(40, min(width, height) / 2 - padding)
    positions: Dict[str, Tuple[float, float]] = {}
    for idx, node_id in enumerate(node_ids):
        angle = 2 * math.pi * idx / count - math.pi / 2
        positions[node_id] = (
            center_x + radius * math.cos(angle),
            center_y + radius * math.sin(angle),
        )
    return positions


def _grid_layout(
    node_ids: List[str],
    width: int,
    height: int,
    padding: int,
) -> Dict[str, Tuple[float, float]]:
    count = len(node_ids)
    if count == 0:
        return {}
    columns = max(1, math.ceil(math.sqrt(count)))
    rows = math.ceil(count / columns)
    x_step = (width - 2 * padding) / max(columns - 1, 1)
    y_step = (height - 2 * padding) / max(rows - 1, 1)
    positions: Dict[str, Tuple[float, float]] = {}
    for idx, node_id in enumerate(node_ids):
        row = idx // columns
        col = idx % columns
        positions[node_id] = (
            padding + col * x_step,
            padding + row * y_step,
        )
    return positions


def _hierarchical_layout(
    node_ids: List[str],
    edges: List[Dict[str, Any]],
    width: int,
    height: int,
    padding: int,
    directed: bool,
) -> Dict[str, Tuple[float, float]]:
    if not node_ids:
        return {}
    adjacency: Dict[str, List[str]] = {node_id: [] for node_id in node_ids}
    for edge in edges:
        source = str(edge.get("from"))
        target = str(edge.get("to"))
        if source in adjacency and target in adjacency:
            adjacency[source].append(target)
            if not directed:
                adjacency[target].append(source)
    root = node_ids[0]
    levels: Dict[str, int] = {root: 0}
    queue = [root]
    while queue:
        current = queue.pop(0)
        for neighbor in adjacency.get(current, []):
            if neighbor not in levels:
                levels[neighbor] = levels[current] + 1
                queue.append(neighbor)
    max_level = max(levels.values(), default=0)
    for node_id in node_ids:
        if node_id not in levels:
            max_level += 1
            levels[node_id] = max_level
    grouped: Dict[int, List[str]] = {}
    for node_id, level in levels.items():
        grouped.setdefault(level, []).append(node_id)
    total_levels = max(grouped.keys()) + 1
    y_step = (height - 2 * padding) / max(total_levels - 1, 1)
    positions: Dict[str, Tuple[float, float]] = {}
    for level, level_nodes in grouped.items():
        x_step = (width - 2 * padding) / max(len(level_nodes) - 1, 1)
        for idx, node_id in enumerate(level_nodes):
            positions[node_id] = (
                padding + idx * x_step,
                padding + level * y_step,
            )
    return positions


@register("graph")
class GraphTemplate:
    """Render a graph diagram with nodes, edges, and highlights."""

    def render(self, params: Dict[str, Any]) -> str:
        nodes = params.get("nodes", [])
        edges = params.get("edges", [])
        if not isinstance(nodes, list):
            nodes = []
        if not isinstance(edges, list):
            edges = []

        directed = bool(params.get("directed", False))
        weighted = bool(params.get("weighted", False))
        layout = str(params.get("layout", "force"))
        caption = params.get("caption")
        distance_labels = params.get("distance_labels", {})
        if not isinstance(distance_labels, dict):
            distance_labels = {}
        path_nodes = params.get("path", [])
        if not isinstance(path_nodes, list):
            path_nodes = []

        node_radius = int(params.get("node_radius", 20))
        svg_width = int(params.get("width", 600))
        svg_height = int(params.get("height", 360))
        padding = int(params.get("padding", 50))

        node_ids = [str(node.get("id")) for node in nodes if isinstance(node, dict)]

        positions: Dict[str, Tuple[float, float]] = {}
        if layout == "custom":
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                node_id = str(node.get("id"))
                if not node_id:
                    continue
                x = node.get("x")
                y = node.get("y")
                if isinstance(x, (int, float)) and isinstance(y, (int, float)):
                    positions[node_id] = (
                        _scale_custom_position(x, padding, svg_width - padding),
                        _scale_custom_position(y, padding, svg_height - padding),
                    )
        if not positions:
            if layout == "grid":
                positions = _grid_layout(node_ids, svg_width, svg_height, padding)
            elif layout == "hierarchical":
                positions = _hierarchical_layout(
                    node_ids,
                    edges,
                    svg_width,
                    svg_height,
                    padding,
                    directed,
                )
            else:
                positions = _circular_layout(node_ids, svg_width, svg_height, padding)

        highlight_nodes = _normalize_highlight_nodes(params.get("highlights", {}))
        highlight_edges = set(_normalize_highlight_edges(params.get("highlights", {})))
        path_edges = set(zip(path_nodes, path_nodes[1:]))

        # Ordered endpoint pairs, so an edge can tell whether its opposite
        # also exists and the two need to be bowed apart.
        reciprocal_pairs = {
            (str(e.get("from")), str(e.get("to")))
            for e in edges
            if isinstance(e, dict) and str(e.get("from")) != str(e.get("to"))
        }

        # The marker id must be unique per diagram, not per template.
        #
        # Every graph used to define `id="graph-arrow"`, which is fine alone and
        # wrong the moment two graphs share a page — and the freeform deck
        # inlines every figure into one HTML document. A browser resolves
        # `url(#graph-arrow)` to the first match in the *document*, so the first
        # diagram kept its arrowheads and every later one silently lost them:
        # its reference pointed into a different SVG tree, which Chromium will
        # not paint. Rendering one SVG on its own cannot reproduce it, which is
        # how it reached a video with two arrowless state machines in it.
        marker_id = "graph-arrow-" + hashlib.sha1(
            repr(sorted(positions.items())).encode("utf-8")
            + repr([(str(e.get("from")), str(e.get("to")), str(e.get("weight")))
                    for e in edges if isinstance(e, dict)]).encode("utf-8")
            # Labels too: two chains can share a geometry and say different
            # things, and those are different diagrams on the same page.
            + repr([(str(n.get("id")), str(n.get("label")))
                    for n in nodes if isinstance(n, dict)]).encode("utf-8")
        ).hexdigest()[:10]

        elements: List[str] = []
        elements.append(style(DEFAULT_STYLES + self._extra_styles()))
        if directed:
            elements.append(defs(self._arrow_marker(marker_id)))

        # Draw edges first (behind nodes)
        for edge in edges:
            if not isinstance(edge, dict):
                continue
            source = str(edge.get("from"))
            target = str(edge.get("to"))
            if source not in positions or target not in positions:
                continue
            x1, y1 = positions[source]
            x2, y2 = positions[target]

            # A self-loop is the same point twice, which `line()` draws as a
            # zero-length segment — invisible, with its weight stamped on top
            # of the node label. Markov chains and automata are mostly
            # self-loops ("stay in Bull with probability 0.9"), so draw an arc
            # above the node instead.
            if source == target:
                loop_r = node_radius * 0.85
                start_x = x1 - node_radius * 0.55
                start_y = y1 - node_radius * 0.75
                end_x = x1 + node_radius * 0.55
                end_y = start_y
                loop_attrs: Dict[str, Any] = {
                    "class": (
                        "graph-edge graph-edge-highlight"
                        if (source, target) in highlight_edges
                        else "graph-edge"
                    ),
                    "fill": "none",
                }
                if directed:
                    loop_attrs["marker_end"] = f"url(#{marker_id})"
                elements.append(
                    path(
                        f"M {start_x:.1f} {start_y:.1f} "
                        f"A {loop_r:.1f} {loop_r:.1f} 0 1 1 {end_x:.1f} {end_y:.1f}",
                        **loop_attrs,
                    )
                )
                weight = edge.get("weight")
                if weighted or weight is not None:
                    elements.append(
                        text(
                            x1,
                            start_y - loop_r - 4,
                            "" if weight is None else str(weight),
                            **{"class": "graph-edge-weight", "text_anchor": "middle"},
                        )
                    )
                continue

            is_path_edge = (source, target) in path_edges
            if not directed and (target, source) in path_edges:
                is_path_edge = True
            is_highlighted = (source, target) in highlight_edges
            if not directed and (target, source) in highlight_edges:
                is_highlighted = True
            edge_class = "graph-edge"
            if is_path_edge:
                edge_class = "graph-edge graph-edge-path"
            elif is_highlighted:
                edge_class = "graph-edge graph-edge-highlight"
            edge_attrs = {"class": edge_class}
            if directed:
                edge_attrs["marker_end"] = f"url(#{marker_id})"

            # Trim the edge to the node boundary. Drawn centre-to-centre, a
            # directed edge hides its own arrowhead under the target circle,
            # which is how a chain loses the direction it exists to show.
            span_x, span_y = x2 - x1, y2 - y1
            span = math.hypot(span_x, span_y) or 1.0
            ux, uy = span_x / span, span_y / span
            sx, sy = x1 + ux * node_radius, y1 + uy * node_radius
            tx, ty = x2 - ux * node_radius, y2 - uy * node_radius

            # A and B each transitioning to the other is the normal shape of a
            # Markov chain, and drawn as two straight lines they are the *same*
            # line with both probabilities stamped on the same midpoint —
            # unreadable, and the probabilities are the content. Bow the pair
            # apart, each to its own side, and label each on its own curve.
            # An edge that runs straight through a node it does not connect is
            # drawn over that node and its label lands on top of it. This is the
            # normal shape of a fallback arrow in a pattern-matching chain
            # ("HT, then a tail, back to the start"), where the whole point of
            # the picture is the long arrow home — so it must not be the one
            # thing the picture ruins.
            blocked = False
            for other_id, (ox, oy) in positions.items():
                if other_id in (source, target):
                    continue
                # Distance from the node's centre to the segment.
                t = ((ox - x1) * span_x + (oy - y1) * span_y) / (span * span)
                if not 0.0 < t < 1.0:
                    continue
                px, py = x1 + t * span_x, y1 + t * span_y
                if math.hypot(ox - px, oy - py) < node_radius * 1.6:
                    blocked = True
                    break

            if blocked or ((target, source) in reciprocal_pairs and directed):
                # The perpendicular (-uy, ux) is taken from the traversal
                # direction, which already reverses for the opposite edge — so
                # the pair bows apart on its own. Do not also flip by node
                # order: two flips cancel and both edges bow the same way.
                # Clear the node it would have crossed, not merely separate
                # from its twin.
                bow = max(18.0, span * 0.12)
                if blocked:
                    bow = max(bow, node_radius * 2.2)
                mid_x, mid_y = (sx + tx) / 2, (sy + ty) / 2
                ctrl_x, ctrl_y = mid_x - uy * bow, mid_y + ux * bow
                elements.append(
                    path(
                        f"M {sx:.1f} {sy:.1f} Q {ctrl_x:.1f} {ctrl_y:.1f} {tx:.1f} {ty:.1f}",
                        **{**edge_attrs, "fill": "none"},
                    )
                )
                # The quadratic's own midpoint, nudged clear of the stroke.
                curve_x = 0.25 * sx + 0.5 * ctrl_x + 0.25 * tx
                curve_y = 0.25 * sy + 0.5 * ctrl_y + 0.25 * ty
                label_x = curve_x - uy * 9
                label_y = curve_y + ux * 9 + 4
                weight = edge.get("weight")
                if weighted or weight is not None:
                    elements.append(
                        text(
                            label_x,
                            label_y,
                            "" if weight is None else str(weight),
                            **{"class": "graph-edge-weight", "text_anchor": "middle"},
                        )
                    )
                continue

            elements.append(line(sx, sy, tx, ty, **edge_attrs))

            weight = edge.get("weight")
            if weighted or weight is not None:
                label = "" if weight is None else str(weight)
                mid_x = (sx + tx) / 2
                mid_y = (sy + ty) / 2 - 6
                elements.append(
                    text(
                        mid_x,
                        mid_y,
                        label,
                        **{"class": "graph-edge-weight", "text_anchor": "middle"},
                    )
                )

        # Draw nodes
        for node in nodes:
            if not isinstance(node, dict):
                continue
            node_id = str(node.get("id"))
            if node_id not in positions:
                continue
            label = node.get("label", node_id)
            x, y = positions[node_id]
            state = highlight_nodes.get(node_id, "default")
            node_class = f"graph-node graph-node-{state}"
            elements.append(circle(x, y, node_radius, **{"class": node_class}))
            elements.append(
                text(
                    x,
                    y + 5,
                    str(label),
                    **{"class": "graph-node-label", "text_anchor": "middle"},
                )
            )

            distance = distance_labels.get(node_id)
            if distance is not None:
                elements.append(
                    text(
                        x,
                        y + node_radius + 16,
                        str(distance),
                        **{
                            "class": "graph-distance-label",
                            "text_anchor": "middle",
                        },
                    )
                )

        # Crop the canvas to what was actually drawn.
        #
        # The caller declares a width and height, but the drawing rarely fills
        # them: a row of three nodes in a 700x340 box occupied 48% of its width
        # and 21% of its height, and the slide showed a small diagram adrift in
        # a large white card. Nothing is moved — the viewBox is narrowed to the
        # content's bounding box, so the same picture arrives at the slide
        # without the empty border around it.
        if positions:
            radii = node_radius * 2.0  # node + its self-loop arc and label
            min_x = min(x for x, _ in positions.values()) - radii
            max_x = max(x for x, _ in positions.values()) + radii
            min_y = min(y for _, y in positions.values()) - radii
            max_y = max(y for _, y in positions.values()) + radii
        else:
            min_x, min_y, max_x, max_y = 0.0, 0.0, float(svg_width), float(svg_height)

        caption_gap = 30.0 if caption else 0.0
        if caption:
            # Sit the caption just under the drawing rather than at the foot of
            # a box that no longer exists.
            elements.append(
                text(
                    (min_x + max_x) / 2,
                    max_y + caption_gap - 8,
                    str(caption),
                    **{"class": "graph-caption", "text_anchor": "middle"},
                )
            )

        margin = 12.0
        view_x = min_x - margin
        view_y = min_y - margin
        view_w = max(max_x - min_x + 2 * margin, 1.0)
        view_h = max(max_y - min_y + caption_gap + 2 * margin, 1.0)
        return svg_document(
            "\n".join(elements),
            round(view_w),
            round(view_h),
            viewbox=f"{view_x:.1f} {view_y:.1f} {view_w:.1f} {view_h:.1f}",
        )

    @staticmethod
    def _extra_styles() -> str:
        return """
.graph-node { stroke: #343a40; stroke-width: 1.4; fill: #f8f9fa; }
.graph-node-current { fill: #fff3cd; }
.graph-node-visited { fill: #d1ecf1; }
.graph-node-target { fill: #d4edda; }
.graph-node-found { fill: #d4edda; }
.graph-node-invalid { fill: #f8d7da; }
.graph-node-rejected { fill: #f8d7da; }
.graph-node-comparison { fill: #FF9800; }
.graph-node-path { fill: #9C27B0; }
.graph-node-label { font-size: 13px; font-family: sans-serif; fill: #212529; }
.graph-edge { stroke: #868e96; stroke-width: 2; }
.graph-edge-highlight { stroke: #9C27B0; stroke-width: 2.5; }
.graph-edge-path { stroke: #9C27B0; stroke-width: 3; }
.graph-edge-weight { font-size: 11px; font-family: sans-serif; fill: #495057; }
.graph-distance-label { font-size: 11px; font-family: sans-serif; fill: #495057; }
.graph-caption { font-size: 13px; font-family: sans-serif; fill: #333; }
"""

    @staticmethod
    def _arrow_marker(marker_id: str = "graph-arrow") -> str:
        """The arrowhead, under an id unique to the diagram that defines it.

        Two graphs on one page both defining ``graph-arrow`` is the failure
        this argument exists for: the browser resolves the reference to the
        first one in the document, and every later diagram loses its arrows.
        """
        return f"""
<marker id="{marker_id}" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
  <polygon points="0 0, 10 3.5, 0 7" fill="#495057"/>
</marker>
"""
