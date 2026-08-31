"""Checked graph-algorithm storyboards and dependency-free animated SVGs.

Every algorithm is computed by :mod:`straightedge.graphs` — the same code the
animation lane draws from — and this template only maps the resulting
:class:`~straightedge.graphs.Step` roles onto the ``graph`` template's states.
A request the algorithm cannot honestly answer (a negative cycle, a DAG with a
cycle, odd degrees where a circuit was asked for) is refused with the witness.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from ...graphs import (
    Graph, GraphError, Step, bellman_ford_steps, coerce_graph,
    connectivity_steps, degeneracy_ordering_steps, dijkstra_steps,
    ear_decomposition_steps, edge_coloring_steps,
    euler_steps,
    greedy_coloring_steps, hamiltonian_search_steps,
    kruskal_steps, matching_steps, max_flow_steps, prim_steps,
    prufer_decode_graph, prufer_decode_steps, prufer_encode_steps,
    require_vertex, scc_steps, stable_matching_graph, stable_matching_steps,
    topological_sort_steps, vertex_cover_steps,
    tree_center_steps,
)
from ...qc import Finding
from ..registry import DIAGRAM_REGISTRY, register

MAX_VERTICES = 11
#: A storyboard is an ``algorithm_trace`` (twelve panels); an animation an
#: ``animated_trace`` (twenty-four frames).
MAX_STORYBOARD_STEPS = 12
MAX_ANIMATED_STEPS = 24

ALGORITHMS = {
    "dijkstra", "bellman_ford", "kruskal", "prim", "topological_sort", "scc",
    "max_flow", "greedy_coloring", "bipartite_matching", "vertex_cover", "euler",
    "low_link",
    "prufer_encode", "prufer_decode",
    "tree_center", "ear_decomposition", "stable_matching", "hamiltonian_search",
    "edge_coloring",
    "degeneracy_ordering",
}
WEIGHTED = {"dijkstra", "bellman_ford", "kruskal", "prim"}
NEEDS_PARTITIONS = {"bipartite_matching", "vertex_cover", "stable_matching"}

#: Step roles → the ``graph`` template's node states.
_NODE_STATES = {"current": "current", "frontier": "target", "visited": "visited",
                "source": "current", "sink": "target", "articulation": "articulation"}


def _parts(params: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    nodes, edges = params.get("nodes", []), params.get("edges", [])
    return (nodes if isinstance(nodes, list) else [], edges if isinstance(edges, list) else [])


def _algorithm(params: Dict[str, Any]) -> str:
    return str(params.get("algorithm", "dijkstra")).strip().lower()


def _left_partition(params: Dict[str, Any], graph: Graph) -> List[str]:
    partitions = params.get("partitions")
    if not isinstance(partitions, dict):
        raise GraphError("bipartite_matching needs exactly two named partitions")
    keys = list(partitions)
    if "left" in partitions and "right" in partitions:
        keys = ["left", "right"]
    elif "left" in partitions or "right" in partitions:
        # Half-named sides fell through to dict order, so an array literally
        # named "right" beside any other key became the proposing *left* side.
        raise GraphError("partitions naming one of left/right must name both")
    if len(keys) != 2:
        raise GraphError("bipartite_matching needs exactly two named partitions")
    left, right = partitions.get(keys[0]), partitions.get(keys[1])
    if not isinstance(left, list) or not isinstance(right, list):
        raise GraphError("both named partitions must be arrays")
    left_ids = [require_vertex(graph, v, "left vertex") for v in left]
    right_ids = [require_vertex(graph, v, "right vertex") for v in right]
    if (set(left_ids) & set(right_ids)
            or set(left_ids) | set(right_ids) != set(graph.ids)
            or len(left_ids) + len(right_ids) != len(graph.ids)):
        raise GraphError("partitions must contain every vertex exactly once")
    for edge in graph.edges:
        if (edge.source in left_ids) == (edge.target in left_ids):
            raise GraphError(f"edge {edge.source!r}–{edge.target!r} does not cross the partition",
                             witness=(edge.source, edge.target))
    return left_ids


def _step_limit(params: Dict[str, Any]) -> int:
    """The lane's step budget: an animation holds more frames than a storyboard."""
    return (MAX_ANIMATED_STEPS if bool(params.get("animate", True))
            else MAX_STORYBOARD_STEPS)


def compute_steps(params: Dict[str, Any]) -> List[Step]:
    """The algorithm's states for ``params``, or :class:`GraphError`."""
    algorithm = _algorithm(params)
    if algorithm not in ALGORITHMS:
        raise GraphError("algorithm must be one of " + ", ".join(sorted(ALGORITHMS)))
    if algorithm == "prufer_decode":
        graph = prufer_decode_graph(params.get("code"))
        if len(graph.ids) > MAX_VERTICES:
            raise GraphError(f"at most {MAX_VERTICES} vertices fit in one readable trace")
        return prufer_decode_steps(params.get("code"))
    if algorithm == "stable_matching":
        graph = stable_matching_graph(params.get("proposers"), params.get("receivers"))
        if len(graph.ids) > MAX_VERTICES:
            raise GraphError(f"at most {MAX_VERTICES} vertices fit in one readable trace")
        return stable_matching_steps(params.get("proposers"), params.get("receivers"),
                                     params.get("check"))
    graph = coerce_graph(params)
    if len(graph.ids) > MAX_VERTICES:
        raise GraphError(f"at most {MAX_VERTICES} vertices fit in one readable trace")
    start = params.get("start", graph.ids[0])
    if algorithm == "prufer_encode":
        expect = params.get("expect")
        if expect is not None and not isinstance(expect, list):
            raise GraphError("expect must be an array")
        return prufer_encode_steps(graph, expect)
    if algorithm == "tree_center":
        return tree_center_steps(graph, bool(params.get("show_eccentricities", False)))
    if algorithm == "ear_decomposition":
        start_cycle = params.get("start_cycle")
        if start_cycle is not None and not isinstance(start_cycle, list):
            raise GraphError("start_cycle must be an array", kind="input")
        return ear_decomposition_steps(graph, start_cycle)
    if algorithm == "hamiltonian_search":
        # The producer already truncates its trace at max_frames, so the
        # default is sized to the lane: 20 frames fit an animation, but a
        # storyboard holds only 12 panels and would otherwise refuse its own
        # default parameters.
        default_frames = min(20, _step_limit(params))
        return hamiltonian_search_steps(graph, start,
                                        params.get("max_frames", default_frames),
                                        params.get("expect"))
    if algorithm == "edge_coloring":
        return edge_coloring_steps(graph, params.get("classes"), params.get("expect"))
    if algorithm == "degeneracy_ordering":
        return degeneracy_ordering_steps(graph)
    if algorithm == "dijkstra":
        return dijkstra_steps(graph, start)
    if algorithm == "bellman_ford":
        return bellman_ford_steps(graph, start)
    if algorithm == "kruskal":
        return kruskal_steps(graph)
    if algorithm == "prim":
        return prim_steps(graph, start)
    if algorithm == "topological_sort":
        return topological_sort_steps(graph, str(params.get("tie_break", "input")))
    if algorithm == "scc":
        condensation = params.get("condensation")
        if condensation is not None:
            return scc_steps(graph, condensation=bool(condensation))
        steps = scc_steps(graph)
        # The condensation DAG is a summary panel, not part of the trace.
        # When appending it is exactly what pushes a storyboard past its
        # panel budget, it yields — a figure that rendered before this panel
        # existed still renders. Ask for it explicitly to be refused instead.
        limit = _step_limit(params)
        if len(steps) == limit + 1:
            return steps[:-1]
        return steps
    if algorithm == "max_flow":
        return max_flow_steps(graph, params.get("source", graph.ids[0]),
                              params.get("sink", graph.ids[-1]))
    if algorithm == "greedy_coloring":
        order = params.get("vertex_order")
        if order is not None and (not isinstance(order, list)
                                  or len({str(x) for x in order}) != len(order)):
            raise GraphError("vertex_order must be a unique list of known vertices")
        return greedy_coloring_steps(graph, [str(x) for x in order] if order else None)
    if algorithm == "euler":
        return euler_steps(graph)
    if algorithm == "low_link":
        return connectivity_steps(graph)
    left = _left_partition(params, graph)
    if algorithm == "bipartite_matching":
        return matching_steps(graph, left)[0]
    return vertex_cover_steps(graph, left)


def _check_name(message: str) -> str:
    """A stable finding id for the kind of refusal, read off the message."""
    lowered = message.lower()
    for word, name in (("weight", "graph_algorithm_weight"), ("capacity", "graph_algorithm_capacity"),
                       ("partition", "graph_algorithm_bipartite"), ("cross the partition", "graph_algorithm_bipartite"),
                       ("negative cycle", "graph_algorithm_negative_cycle"), ("cycle", "graph_algorithm_cycle"),
                       ("odd degree", "graph_algorithm_parity"), ("vertex_order", "graph_algorithm_order"),
                       ("source", "graph_algorithm_terminals"), ("sink", "graph_algorithm_terminals"),
                       ("start", "graph_algorithm_start"), ("directed", "graph_algorithm_direction"),
                       ("vertices fit", "graph_algorithm_size"), ("algorithm must", "graph_algorithm"),
                       ("node", "graph_algorithm_nodes"), ("vertex", "graph_algorithm_nodes"),
                       ("edge", "graph_algorithm_edges")):
        if word in lowered:
            return name
    return "graph_algorithm_refused"


def _refusal(exc: GraphError) -> Finding:
    check = (f"graph_algorithm_{exc.kind}" if exc.kind
             else _check_name(str(exc)))
    witness = exc.witness
    label = None
    if isinstance(witness, (list, tuple)):
        # Prefer the producer's structured witness shape. Legacy errors
        # retain the old inference until they are converted one by one.
        joiner = {"walk": " → ", "edge": "–", "list": ", "}.get(
            exc.witness_kind,
            " → " if "cycle" in check else ("–" if len(witness) == 2 else ", "),
        )
        label = joiner.join(str(x) for x in witness)
    elif witness is not None:
        label = str(witness)
    return Finding(check, "error", str(exc), label=label)


def _step_limit_findings(params: Dict[str, Any], steps: List[Step]) -> List[Finding]:
    limit = _step_limit(params)
    if len(steps) > limit:
        return [Finding("graph_algorithm_size", "error",
                        f"the algorithm takes {len(steps)} steps; at most {limit} fit one "
                        + ("animation" if limit == MAX_ANIMATED_STEPS else "storyboard"))]
    return []


def _findings(params: Dict[str, Any]) -> List[Finding]:
    try:
        steps = compute_steps(params)
    except GraphError as exc:
        return [_refusal(exc)]
    return _step_limit_findings(params, steps)


def _base(params: Dict[str, Any]) -> Dict[str, Any]:
    algorithm = _algorithm(params)
    if algorithm == "prufer_decode":
        graph = prufer_decode_graph(params.get("code"))
        nodes = [{"id": vertex} for vertex in graph.ids]
        edges = [{"from": edge.source, "to": edge.target} for edge in graph.edges]
    elif algorithm == "stable_matching":
        graph = stable_matching_graph(params.get("proposers"), params.get("receivers"))
        nodes = [{"id": vertex} for vertex in graph.ids]
        edges = [{"from": edge.source, "to": edge.target} for edge in graph.edges]
    else:
        nodes, edges = _parts(params)
    return {"nodes": nodes, "edges": edges, "directed": bool(params.get("directed", False)),
            "weighted": algorithm in WEIGHTED or algorithm == "max_flow",
            "layout": str(params.get("graph_layout", "circular")),
            "node_radius": int(params.get("node_radius", 20)),
            "width": int(params.get("width", 600)), "height": int(params.get("height", 360))}


def frames_from_steps(params: Dict[str, Any], steps: List[Step]) -> List[Dict[str, Any]]:
    """``graph`` template calls, one per step, for a storyboard or animation."""
    base = _base(params)
    algorithm = _algorithm(params)
    graph = (prufer_decode_graph(params.get("code")) if algorithm == "prufer_decode"
             else stable_matching_graph(params.get("proposers"), params.get("receivers"))
             if algorithm == "stable_matching" else coerce_graph(params))
    out = []
    for step in steps:
        frame_base = base
        frame_graph = graph
        override = step.extras.get("graph_override")
        if isinstance(override, dict):
            override_nodes = override.get("nodes", [])
            override_edges = override.get("edges", [])
            frame_base = {**base, "nodes": override_nodes, "edges": override_edges,
                          "directed": bool(override.get("directed", False)),
                          "layout": str(override.get("layout", "circular"))}
            frame_graph = coerce_graph(frame_base)
        nodes = {v: _NODE_STATES.get(role, role) for v, role in step.node_states.items()}
        highlighted = [list(key) for key, role in step.edge_states.items()
                       if role in {"tree", "path"}]
        # A bridge or a min-cut edge is the certificate; drawn like a tree
        # edge it would exist only in the caption.
        cut = [list(key) for key, role in step.edge_states.items() if role == "cut"]
        rejected = [list(key) for key, role in step.edge_states.items() if role == "rejected"]
        color_edges: Dict[str, List[List[str]]] = {}
        for key, role in step.edge_states.items():
            if role.startswith("color-"):
                color_edges.setdefault(role, []).append(list(key))
        edges = frame_base["edges"]
        if "visible_edges" in step.extras:
            visible = set(step.extras["visible_edges"])
            edges = [edge for edge in edges
                     if frame_graph.key(str(edge["from"]), str(edge["to"])) in visible]
        if step.edge_labels:
            edges = [{**edge, "weight": step.edge_labels.get(
                frame_graph.key(str(edge["from"]), str(edge["to"])), edge.get("weight"))}
                for edge in frame_base["edges"]]
        # A one- or two-line panel (a running total, a matching size) fits
        # after the caption; a distance table does not, and its numbers are
        # already on the vertices as badges.
        caption = step.caption
        if 0 < len(step.panel) <= 2:
            caption += " · " + " · ".join(step.panel)
        frame = {**frame_base, "edges": edges, "caption": caption,
                 "highlights": {"nodes": nodes, "edges": highlighted,
                                "rejected_edges": rejected, "cut_edges": cut,
                                "color_edges": color_edges}}
        if step.badges:
            frame["distance_labels"] = dict(step.badges)
        if _algorithm(params) in NEEDS_PARTITIONS:
            frame["layout"] = "bipartite"
            frame["partitions"] = ({"left": list(params.get("proposers", {})),
                                    "right": list(params.get("receivers", {}))}
                                   if algorithm == "stable_matching"
                                   else params.get("partitions"))
        out.append({"label": step.label, "visual": {"type": "graph", "params": frame}})
    return out


def _frames(params: Dict[str, Any]) -> List[Dict[str, Any]]:
    return frames_from_steps(params, compute_steps(params))


# Kept as the names the tests and earlier callers use.
def _dijkstra(params: Dict[str, Any]) -> List[Dict[str, Any]]:
    return _frames({**params, "algorithm": "dijkstra"})


def _kruskal(params: Dict[str, Any]) -> List[Dict[str, Any]]:
    return _frames({**params, "algorithm": "kruskal"})


def _coloring(params: Dict[str, Any]) -> List[Dict[str, Any]]:
    return _frames({**params, "algorithm": "greedy_coloring"})


def _matching(params: Dict[str, Any]) -> List[Dict[str, Any]]:
    return _frames({**params, "algorithm": "bipartite_matching"})


@register("graph_algorithm")
class GraphAlgorithmTemplate:
    """Compute shortest-path, spanning-tree, ordering, flow, colouring, matching
    or Euler-circuit states, and draw only what was computed."""

    motion = "optional"
    checks = ["valid vertices and endpoints", "algorithm-specific assumptions",
              "nonnegative Dijkstra weights", "negative-cycle and DAG-cycle witnesses",
              "bipartition integrity", "Euler degree parity", "low-link bridge and block invariants",
              "computed intermediate states"]

    def refusal_findings(self, params: Dict[str, Any]) -> List[Finding]:
        return _findings(params)

    def render(self, params: Dict[str, Any]) -> str:
        # Read the public surface here so catalog discovery publishes it.
        algorithm = _algorithm(params)
        params.get("nodes", [])
        params.get("edges", [])
        params.get("start")
        params.get("source")
        params.get("sink")
        params.get("directed", False)
        params.get("partitions")
        params.get("vertex_order")
        params.get("code")
        params.get("expect")
        params.get("show_eccentricities", False)
        params.get("start_cycle")
        params.get("proposers")
        params.get("receivers")
        params.get("check")
        params.get("max_frames", 20)
        params.get("classes")
        params.get("tie_break", "input")
        params.get("graph_layout", "circular")
        animate = bool(params.get("animate", True))
        duration_s = float(params.get("duration_s", 1.2))
        loop = bool(params.get("loop", True))
        title = params.get("title")
        columns = int(params.get("columns", 3))
        params.get("node_radius", 20)
        params.get("width", 600)
        params.get("height", 360)
        # Compute once and share the steps with the refusal check: several
        # algorithms here are exponential searches, and running the search
        # again for the frames doubles every render.
        try:
            steps = compute_steps(params)
        except GraphError:
            return ""
        if _step_limit_findings(params, steps):
            return ""
        frames = frames_from_steps(params, steps)
        heading = str(title) if title is not None else algorithm.replace("_", " ").title()
        if animate:
            return DIAGRAM_REGISTRY["animated_trace"].render({
                "title": heading, "frames": frames, "duration_s": duration_s, "loop": loop})
        return DIAGRAM_REGISTRY["algorithm_trace"].render({
            "title": heading, "steps": frames, "columns": columns, "show_step_numbers": True})
