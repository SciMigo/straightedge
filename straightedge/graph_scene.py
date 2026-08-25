"""Manim scenes for ``Topic.GRAPH``, generated from computed steps.

One builder serves every graph concept. The algorithm runs *here*, at
generation time, through :func:`straightedge.graphs.steps_for`; the emitted
scene is a fixed sequence of state changes, one narration beat per step, and
draws nothing it did not compute. That is the same contract the figure lane
keeps: a wrong input is refused before the picture exists, and the picture
cannot show a state the algorithm did not reach.

Lives in its own module rather than in :mod:`straightedge.templates` because
the emission is data-driven (roles → colours, steps → beats) and shares nothing
with the hand-written scenes there. :mod:`straightedge.templates` imports this
module so the ``@scene_for`` registration happens whenever scenes are built.
"""

from __future__ import annotations

import math
from typing import Any

from .graphs import (ConceptGraph, Graph, GraphError, Step, coerce_graph,
                     STOCK_GRAPH, STOCK_NETWORK, steps_for)
from .models import AnimationPlan, Topic
from .topics import scene_for

#: A beat per step plus one to draw the graph. Beyond this a video stops being
#: one lesson and starts being a log; the precondition refuses larger inputs.
MAX_STEPS = 17

#: Vertices a 16:9 frame can show with legible labels and a side panel.
MAX_VERTICES = 8

NODE_RADIUS = 0.34

#: Role → (fill colour constant, fill opacity). Absent role: neutral.
NODE_STYLES: dict[str, tuple[str, float]] = {
    "current": ("C_WARN", 0.9),
    "frontier": ("C_HOLD", 0.65),
    "visited": ("C_DONE", 0.6),
    "source": ("C_FLOW", 0.8),
    "sink": ("C_WARM", 0.8),
}
NEUTRAL_NODE = ("C_WELL", 1.0)
COLOR_CLASSES = ("C_FLOW", "C_HOLD", "C_DONE", "C_AUX", "C_WARM", "C_DEEP", "C_WARN", "C_MUTED")

#: Role → (stroke colour constant, stroke width, opacity).
EDGE_STYLES: dict[str, tuple[str, float, float]] = {
    "tree": ("C_FLOW", 6.0, 1.0),
    "path": ("C_WARN", 7.0, 1.0),
    "rejected": ("C_WARM", 3.0, 0.45),
    "cut": ("C_WARM", 6.0, 1.0),
    "frontier": ("C_HOLD", 4.0, 0.9),
}
NEUTRAL_EDGE = ("C_MUTED", 3.0, 0.9)

DEFAULT_TITLES = {
    ("graph/traversal", "bfs"): "Breadth-first search from {start}",
    ("graph/traversal", "dfs"): "Depth-first search from {start}",
    ("graph/shortest_path", "dijkstra"): "Dijkstra's algorithm from {start}",
    ("graph/shortest_path", "bellman_ford"): "Bellman–Ford from {start}",
    ("graph/spanning_tree", "kruskal"): "Kruskal's algorithm",
    ("graph/spanning_tree", "prim"): "Prim's algorithm from {start}",
    ("graph/max_flow", "edmonds_karp"): "Max flow and min cut",
}


def _node_style(role: str | None) -> tuple[str, float]:
    if role is None:
        return NEUTRAL_NODE
    if role.startswith("color-"):
        return COLOR_CLASSES[(int(role.split("-")[1]) - 1) % len(COLOR_CLASSES)], 0.7
    return NODE_STYLES.get(role, NEUTRAL_NODE)


# ------------------------------------------------------------------ layout


def layout(graph: Graph, kind: str) -> dict[str, tuple[float, float]]:
    """Scene coordinates for every vertex, in the left two-thirds of the frame.

    Author positions win when every vertex has one (fractions of the canvas,
    as the figure lane reads them). A directed graph or an explicit
    ``hierarchical`` request is levelled left to right so a flow network reads
    source → sink; anything else goes on a circle.
    """
    x0, x1, y0, y1 = -6.2, 2.0, -2.2, 2.3
    if len(graph.positions) == len(graph.ids) and all(
            0 <= x <= 1 and 0 <= y <= 1 for x, y in graph.positions.values()):
        return {v: (x0 + fx * (x1 - x0), y1 - fy * (y1 - y0))
                for v, (fx, fy) in graph.positions.items()}
    if kind == "hierarchical" or (kind == "auto" and graph.directed):
        levels: dict[str, int] = {graph.ids[0]: 0}
        queue = [graph.ids[0]]
        while queue:
            u = queue.pop(0)
            for v in graph.neighbors(u):
                if v not in levels:
                    levels[v] = levels[u] + 1
                    queue.append(v)
        for v in graph.ids:
            if v not in levels:
                levels[v] = max(levels.values()) + 1
        columns: dict[int, list[str]] = {}
        for v in graph.ids:
            columns.setdefault(levels[v], []).append(v)
        width = max(columns) or 1
        out = {}
        for level, members in columns.items():
            x = x0 + 0.4 + (level / width) * (x1 - x0 - 0.8)
            gap = min(1.7, (y1 - y0) / max(len(members) - 1, 1))
            top = (len(members) - 1) * gap / 2
            for i, v in enumerate(members):
                out[v] = (x, top - i * gap)
        return out
    cx, cy, r = (x0 + x1) / 2, (y0 + y1) / 2 - 0.1, 2.25
    n = len(graph.ids)
    return {v: (cx + r * math.cos(math.pi / 2 - 2 * math.pi * i / n),
                cy + r * math.sin(math.pi / 2 - 2 * math.pi * i / n))
            for i, v in enumerate(graph.ids)}


def _shorten(a: tuple[float, float], b: tuple[float, float],
             by_start: float, by_end: float) -> tuple[tuple[float, float], tuple[float, float]]:
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy) or 1.0
    ux, uy = dx / length, dy / length
    return ((a[0] + ux * by_start, a[1] + uy * by_start),
            (b[0] - ux * by_end, b[1] - uy * by_end))


def _r(value: float) -> float:
    return round(value, 3)


def _badge_positions(positions: dict[str, tuple[float, float]]) -> dict[str, tuple[float, float]]:
    """Where a vertex's badge (its distance, its visit number) sits.

    Radially outward from the drawing's centroid rather than always below:
    on a circle that is outside the circle, clear of the edges and their
    labels, where 'below' put the top vertex's badge on the edge under it.
    """
    cx = sum(x for x, _ in positions.values()) / len(positions)
    cy = sum(y for _, y in positions.values()) / len(positions)
    out = {}
    for v, (x, y) in positions.items():
        dx, dy = x - cx, y - cy
        length = math.hypot(dx, dy)
        ux, uy = (dx / length, dy / length) if length > 1e-9 else (0.0, -1.0)
        out[v] = (x + ux * (NODE_RADIUS + 0.34), y + uy * (NODE_RADIUS + 0.34))
    return out


# ----------------------------------------------------------------- builder


def _resolve(plan: AnimationPlan) -> tuple[str, dict[str, Any], Graph, list[Step], str]:
    concept = plan.concept or ConceptGraph.TRAVERSAL
    params = dict(plan.parameters or {})
    stock = STOCK_NETWORK if concept == ConceptGraph.MAX_FLOW else STOCK_GRAPH
    if params.get("nodes") is None:
        params = {**stock, **params}
    graph = coerce_graph(params)
    steps = steps_for(concept, params)
    algorithm = str(params.get("algorithm", "")).strip().lower() or {
        ConceptGraph.TRAVERSAL: "bfs", ConceptGraph.SHORTEST_PATH: "dijkstra",
        ConceptGraph.SPANNING_TREE: "kruskal", ConceptGraph.MAX_FLOW: "edmonds_karp",
    }[concept]
    return concept, params, graph, steps, algorithm


@scene_for(Topic.GRAPH)
def graph_scene(plan: AnimationPlan) -> str:
    """The scene for any graph concept: draw the graph, then replay the steps.

    Every state change is a Manim animation inside one ``_beat``, keyed
    ``b01``… in emission order, so a measured narration drives the pacing
    exactly as for the hand-written scenes. Emitted unrolled — one ``_beat``
    call per step in the source — so the beat keys can be read off the file.
    """
    try:
        concept, params, graph, steps, algorithm = _resolve(plan)
    except GraphError as exc:
        # The precondition reports this before a render; the builder still has
        # to return a scene, so it says on screen what it could not draw.
        return _refusal_scene(str(exc))
    steps = steps[:MAX_STEPS]
    start = str(params.get("start", graph.ids[0]))
    title = str(params.get("title") or DEFAULT_TITLES.get(
        (concept, algorithm), concept).format(start=start))
    positions = layout(graph, str(params.get("layout", "auto")))
    badge_at = _badge_positions(positions)
    weighted = concept in {ConceptGraph.SHORTEST_PATH, ConceptGraph.SPANNING_TREE}
    keys = [graph.key(e.source, e.target) for e in graph.edges]
    index_of = {key: i for i, key in enumerate(keys)}
    beats = _Beats()
    L: list[str] = []
    emit = L.append

    emit("class GeneratedScene(Scene):")
    emit("    def construct(self):")
    emit("        title = _t(%r, font_size=34).to_edge(UP, buff=0.3)" % title)
    emit("        nodes, labels, edges, weights = {}, {}, {}, {}")
    for edge_index, edge in enumerate(graph.edges):
        a, b = positions[edge.source], positions[edge.target]
        tip = 0.06 if graph.directed else 0.0
        (sx, sy), (tx, ty) = _shorten(a, b, NODE_RADIUS, NODE_RADIUS + tip)
        colour, width, opacity = NEUTRAL_EDGE
        if graph.directed:
            emit("        edges[%d] = Arrow([%r, %r, 0], [%r, %r, 0], buff=0, color=%s, "
                 "stroke_width=%r, max_tip_length_to_length_ratio=0.14, "
                 "max_stroke_width_to_length_ratio=8)"
                 % (edge_index, _r(sx), _r(sy), _r(tx), _r(ty), colour, width))
        else:
            emit("        edges[%d] = Line([%r, %r, 0], [%r, %r, 0], color=%s, stroke_width=%r)"
                 % (edge_index, _r(sx), _r(sy), _r(tx), _r(ty), colour, width))
        emit("        edges[%d].set_opacity(%r)" % (edge_index, opacity))
        label = None
        if concept == ConceptGraph.MAX_FLOW:
            label = f"0/{edge.capacity:g}"
        elif weighted and edge.weight is not None:
            label = f"{edge.weight:g}"
        if label is not None:
            mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            dx, dy = b[0] - a[0], b[1] - a[1]
            length = math.hypot(dx, dy) or 1.0
            nx, ny = -dy / length * 0.3, dx / length * 0.3
            emit("        weights[%d] = _t(%r, font_size=20, color=C_MUTED).move_to([%r, %r, 0])"
                 % (edge_index, label, _r(mx + nx), _r(my + ny)))
            emit("        weights[%d].add_background_rectangle(color=C_INK, opacity=0.85, buff=0.04)"
                 % edge_index)
    for v in graph.ids:
        x, y = positions[v]
        colour, opacity = NEUTRAL_NODE
        emit("        nodes[%r] = Circle(radius=%r, color=C_FG, stroke_width=3, "
             "fill_color=%s, fill_opacity=%r).move_to([%r, %r, 0])"
             % (v, NODE_RADIUS, colour, opacity, _r(x), _r(y)))
        emit("        labels[%r] = _t(%r, font_size=24).move_to(nodes[%r])"
             % (v, graph.labels[v], v))
    emit("        badges = {}")
    emit("        panel = VGroup(*[_t(line, font_size=22) for line in %r])"
         ".arrange(DOWN, aligned_edge=LEFT, buff=0.18).move_to([4.7, 1.2, 0])"
         % (list(_first_panel(steps)),))
    emit("        caption = _t(%r, font_size=24).to_edge(DOWN, buff=0.35)" % steps[0].caption)
    emit("        %s(self, %s, Write(title), *[Create(e) for e in edges.values()], "
         "*[FadeIn(n) for n in nodes.values()], *[Write(l) for l in labels.values()], "
         "*[FadeIn(w) for w in weights.values()], FadeIn(panel), Write(caption))"
         % ("_beat", beats.next()))

    previous = Step("", "", panel=_first_panel(steps))
    badges_present: set[str] = set()
    for step in steps:
        anims: list[str] = []
        for v in graph.ids:
            role_now, role_before = step.node_states.get(v), previous.node_states.get(v)
            if role_now != role_before:
                colour, opacity = _node_style(role_now)
                anims.append("nodes[%r].animate.set_fill(%s, opacity=%r)" % (v, colour, opacity))
        for key, edge_index in index_of.items():
            role_now, role_before = step.edge_states.get(key), previous.edge_states.get(key)
            if role_now != role_before:
                colour, width, opacity = EDGE_STYLES.get(role_now or "", NEUTRAL_EDGE)
                anims.append("edges[%d].animate.set_color(%s).set_stroke(width=%r)"
                             ".set_opacity(%r)" % (edge_index, colour, width, opacity))
            label_now, label_before = step.edge_labels.get(key), previous.edge_labels.get(key)
            if label_now is not None and label_now != label_before and edge_index in _weight_indices(graph, concept, weighted):
                anims.append("Transform(weights[%d], _t(%r, font_size=20, color=C_MUTED)"
                             ".move_to(weights[%d]).add_background_rectangle("
                             "color=C_INK, opacity=0.85, buff=0.04))"
                             % (edge_index, label_now, edge_index))
        for v in graph.ids:
            text_now, text_before = step.badges.get(v), previous.badges.get(v)
            if text_now is None or text_now == text_before:
                continue
            x, y = badge_at[v]
            target = ("_t(%r, font_size=19, color=C_MUTED).move_to([%r, %r, 0])"
                      % (text_now, _r(x), _r(y)))
            if v in badges_present:
                anims.append("Transform(badges[%r], %s)" % (v, target))
            else:
                badges_present.add(v)
                emit("        badges[%r] = %s" % (v, target))
                anims.append("FadeIn(badges[%r])" % v)
        panel_now = step.panel or previous.panel
        if panel_now != previous.panel:
            anims.append("Transform(panel, VGroup(*[_t(line, font_size=22) for line in %r])"
                         ".arrange(DOWN, aligned_edge=LEFT, buff=0.18).move_to([4.7, 1.2, 0]))"
                         % (list(panel_now),))
        if step.caption != previous.caption:
            anims.append("Transform(caption, _t(%r, font_size=24).to_edge(DOWN, buff=0.35))"
                         % step.caption)
        emit("        # %s" % step.label)
        emit("        _beat(self, %s, %s)" % (beats.next(), ", ".join(anims) or "Wait(0.2)"))
        previous = Step(step.label, step.caption, step.node_states, step.edge_states,
                        {**previous.badges, **step.badges},
                        {**previous.edge_labels, **step.edge_labels}, panel_now)
    emit("        self.wait(1)")
    return "\n".join(L)


def _weight_indices(graph: Graph, concept: str, weighted: bool) -> set[int]:
    if concept == ConceptGraph.MAX_FLOW:
        return set(range(len(graph.edges)))
    return {i for i, e in enumerate(graph.edges) if weighted and e.weight is not None}


def _first_panel(steps: list[Step]) -> tuple[str, ...]:
    for step in steps:
        if step.panel:
            return step.panel
    return (steps[0].label,)


class _Beats:
    def __init__(self) -> None:
        self._n = 0

    def next(self) -> str:
        self._n += 1
        return '"b%02d"' % self._n


def _refusal_scene(reason: str) -> str:
    """A scene that states the refusal, for a caller that skipped the check."""
    return "\n".join([
        "class GeneratedScene(Scene):",
        "    def construct(self):",
        "        title = _t(%r, font_size=34).to_edge(UP)" % "Nothing to draw",
        "        reason = _t(%r, font_size=26)" % reason,
        "        self.play(Write(title), FadeIn(reason))",
        "        self.wait(2)",
    ])
