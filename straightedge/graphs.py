"""Graph theory: one graph, many algorithms, every state computed.

This is the topic module for ``Topic.GRAPH`` in the animation lane, and the
one home for the graph algorithms both lanes draw. The SVG templates
(``graph_traversal``, ``graph_algorithm``) and the Manim scene builders read the
same :class:`Step` sequences, so a storyboard and a video of the same request
cannot disagree about which vertex was settled third.

The rule the figure lane already follows applies here too: **a state is
computed from the supplied graph, never authored**. A builder that wants to
show Dijkstra settling ``C`` gets that from :func:`dijkstra_steps`, and when the
input makes the claim false — a negative weight, a cycle in a DAG, a source
that is also the sink — the algorithm raises :class:`GraphError` and the
caller refuses with the witness, instead of drawing a confident picture of
something that is not so.

Steps carry *roles*, not colours: ``current``, ``frontier``, ``visited`` on
vertices; ``tree``, ``path``, ``rejected``, ``cut`` on edges. Each lane maps
the roles onto its own palette.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

from .models import Topic
from .topics import topic


class ConceptGraph:
    """Sub-topic identifiers under ``Topic.GRAPH``."""

    TRAVERSAL = "graph/traversal"
    SHORTEST_PATH = "graph/shortest_path"
    SPANNING_TREE = "graph/spanning_tree"
    MAX_FLOW = "graph/max_flow"
    CONNECTIVITY = "graph/connectivity"


class GraphError(ValueError):
    """The supplied graph cannot honestly produce the requested picture.

    ``witness`` is the structure that proves it — an odd cycle, a negative
    cycle, the vertices of odd degree — so a refusal can say *why* in terms a
    student can check, not merely that a check failed.
    """

    def __init__(self, message: str, witness: Any = None) -> None:
        super().__init__(message)
        self.witness = witness


EdgeKey = tuple[str, str]


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    weight: float | None = None
    capacity: float | None = None
    flow: float = 0.0


@dataclass(frozen=True)
class Graph:
    ids: tuple[str, ...]
    labels: dict[str, str]
    edges: tuple[Edge, ...]
    directed: bool = False
    #: Optional author-supplied positions as fractions of the canvas.
    positions: dict[str, tuple[float, float]] = field(default_factory=dict)

    def key(self, u: str, v: str) -> EdgeKey:
        """The identity of an edge: ordered when directed, sorted otherwise."""
        return (u, v) if self.directed else (min(u, v), max(u, v))

    def has_edge(self, u: str, v: str) -> bool:
        return self.key(u, v) in {self.key(e.source, e.target) for e in self.edges}

    def neighbors(self, vertex: str, order: list[str] | None = None) -> list[str]:
        """Adjacent vertices in first-appearance order, or in ``order``.

        Direction is honoured: on a directed graph only out-neighbours count.
        ``order`` is a global tie-break — the list a lecture writes on the board
        so a traversal is reproducible — and vertices it omits keep their input
        order after the ones it names.
        """
        seen: list[str] = []
        for edge in self.edges:
            if edge.source == vertex and edge.target not in seen:
                seen.append(edge.target)
            elif not self.directed and edge.target == vertex and edge.source not in seen:
                seen.append(edge.source)
        if order:
            rank = {v: i for i, v in enumerate(order)}
            fallback = len(rank)
            input_rank = {v: i for i, v in enumerate(self.ids)}
            seen.sort(key=lambda v: (rank.get(v, fallback), input_rank[v]))
        return seen

    def weight(self, u: str, v: str) -> float:
        for edge in self.edges:
            if (edge.source, edge.target) == (u, v) or (
                    not self.directed and (edge.source, edge.target) == (v, u)):
                return 0.0 if edge.weight is None else edge.weight
        raise KeyError((u, v))

    def degree(self, vertex: str) -> int:
        total = 0
        for edge in self.edges:
            if edge.source == vertex:
                total += 1
            if edge.target == vertex:
                total += 1
        return total


@dataclass(frozen=True)
class Step:
    """One state of an algorithm, described by roles rather than colours."""

    label: str
    caption: str
    node_states: dict[str, str] = field(default_factory=dict)
    edge_states: dict[EdgeKey, str] = field(default_factory=dict)
    badges: dict[str, str] = field(default_factory=dict)
    edge_labels: dict[EdgeKey, str] = field(default_factory=dict)
    panel: tuple[str, ...] = ()
    #: Algorithm-specific state a lane may want verbatim (a traversal's
    #: frontier list, say) rather than parsed back out of the caption.
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ConnectivityAnalysis:
    """Tarjan low-link result for an undirected graph.

    Blocks are vertex sets, not renderer geometry.  A bridge therefore appears
    as a two-vertex block and an isolated vertex as a one-vertex block.
    """

    discovery: dict[str, int]
    low: dict[str, int]
    parent: dict[str, str | None]
    bridges: tuple[EdgeKey, ...]
    articulations: tuple[str, ...]
    blocks: tuple[tuple[str, ...], ...]
    finish_order: tuple[str, ...]


# ------------------------------------------------------------------ coercion


def _is_number(value: Any) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def coerce_graph(params: dict[str, Any]) -> Graph:
    """Read the ``nodes`` / ``edges`` / ``directed`` shape every graph template
    uses, or raise :class:`GraphError` saying which part cannot be read."""
    nodes = params.get("nodes")
    edges = params.get("edges", [])
    if not isinstance(nodes, list) or not nodes:
        raise GraphError("nodes must be a non-empty array")
    if not isinstance(edges, list):
        raise GraphError("edges must be an array")
    ids: list[str] = []
    labels: dict[str, str] = {}
    positions: dict[str, tuple[float, float]] = {}
    for node in nodes:
        if not isinstance(node, dict) or node.get("id") is None:
            raise GraphError("every node must be an object with an id")
        node_id = str(node["id"])
        if node_id in labels:
            raise GraphError(f"vertex id {node_id!r} is repeated")
        ids.append(node_id)
        labels[node_id] = str(node.get("label", node_id))
        x, y = node.get("x"), node.get("y")
        if _is_number(x) and _is_number(y):
            positions[node_id] = (float(x), float(y))
    directed = bool(params.get("directed", False))
    known = set(ids)
    out: list[Edge] = []
    seen: set[EdgeKey] = set()
    for edge in edges:
        if not isinstance(edge, dict) or edge.get("from") is None or edge.get("to") is None:
            raise GraphError("every edge needs from and to endpoints")
        u, v = str(edge["from"]), str(edge["to"])
        if u not in known or v not in known:
            raise GraphError(f"edge {u!r}–{v!r} names an unknown vertex", witness=(u, v))
        if u == v:
            raise GraphError(f"edge {u!r}–{v!r} is a loop", witness=(u, v))
        key = (u, v) if directed else (min(u, v), max(u, v))
        if key in seen:
            raise GraphError(f"edge {u!r}–{v!r} is repeated", witness=(u, v))
        seen.add(key)
        weight, capacity = edge.get("weight"), edge.get("capacity")
        if weight is not None and not _is_number(weight):
            raise GraphError(f"edge {u!r}–{v!r} has a non-numeric weight", witness=(u, v))
        if capacity is not None and (not _is_number(capacity) or capacity < 0):
            raise GraphError(f"edge {u!r}–{v!r} needs a non-negative capacity", witness=(u, v))
        flow = edge.get("flow", 0)
        if not _is_number(flow) or flow < 0:
            raise GraphError(f"edge {u!r}–{v!r} has an invalid flow", witness=(u, v))
        out.append(Edge(u, v, None if weight is None else float(weight),
                        None if capacity is None else float(capacity), float(flow)))
    return Graph(tuple(ids), labels, tuple(out), directed, positions)


def require_weights(graph: Graph, *, nonnegative: bool = False) -> None:
    for edge in graph.edges:
        if edge.weight is None:
            raise GraphError(f"edge {edge.source!r}–{edge.target!r} has no weight",
                             witness=(edge.source, edge.target))
        if nonnegative and edge.weight < 0:
            raise GraphError(
                f"edge {edge.source!r}–{edge.target!r} has negative weight "
                f"{edge.weight:g}; Dijkstra requires nonnegative weights",
                witness=(edge.source, edge.target))


def require_vertex(graph: Graph, vertex: Any, role: str) -> str:
    name = str(vertex)
    if name not in graph.labels:
        raise GraphError(f"{role} {name!r} is not a vertex", witness=name)
    return name


def _fmt(value: float) -> str:
    return "∞" if not math.isfinite(value) else f"{value:g}"


def _edge_text(u: str, v: str, directed: bool) -> str:
    return f"{u}→{v}" if directed else f"{u}–{v}"


def require_tree(graph: Graph) -> None:
    """Refuse a directed, cyclic, or disconnected graph with a checkable witness."""
    if graph.directed:
        raise GraphError("a tree must be undirected")
    parent: dict[str, str | None] = {}

    def visit(vertex: str, previous: str | None, path: list[str]) -> list[str] | None:
        parent[vertex] = previous
        for neighbor in graph.neighbors(vertex):
            if neighbor == previous:
                continue
            if neighbor in parent:
                start = path.index(neighbor) if neighbor in path else 0
                return path[start:] + [neighbor]
            found = visit(neighbor, vertex, path + [neighbor])
            if found:
                return found
        return None

    cycle = visit(graph.ids[0], None, [graph.ids[0]])
    if cycle:
        raise GraphError("the graph has a cycle, so it is not a tree", witness=cycle)
    if len(parent) != len(graph.ids):
        first = list(parent)
        other = next(v for v in graph.ids if v not in parent)
        second: list[str] = []
        queue = [other]
        seen = {other}
        while queue:
            vertex = queue.pop(0)
            second.append(vertex)
            for neighbor in graph.neighbors(vertex):
                if neighbor not in seen:
                    seen.add(neighbor)
                    queue.append(neighbor)
        raise GraphError("the graph is disconnected, so it is not a tree",
                         witness=(tuple(first), tuple(second)))


# --------------------------------------------------------------- Prüfer code


def _vertex_sort_key(vertex: str) -> tuple[int, int | str]:
    """Numeric labels sort numerically; all other labels sort lexically."""
    try:
        return (0, int(vertex))
    except ValueError:
        return (1, vertex)


def prufer_encode_steps(graph: Graph, expect: list[Any] | None = None) -> list[Step]:
    """Delete the smallest leaf repeatedly and expose the resulting Prüfer code."""
    require_tree(graph)
    if len(graph.ids) < 2:
        raise GraphError("Prüfer encoding needs at least two vertices")
    adjacency = {v: list(graph.neighbors(v)) for v in graph.ids}
    remaining = set(graph.ids)
    code: list[str] = []
    removed: list[str] = []
    steps = [Step("Start", "Repeatedly delete the smallest leaf",
                  panel=("code: ()",), extras={"code": []})]
    while len(remaining) > 2:
        leaf = min((v for v in remaining
                    if sum(n in remaining for n in adjacency[v]) == 1),
                   key=_vertex_sort_key)
        neighbor = next(n for n in adjacency[leaf] if n in remaining)
        code.append(neighbor)
        removed.append(leaf)
        remaining.remove(leaf)
        nodes = {v: "rejected" for v in removed}
        nodes[leaf] = "current"
        steps.append(Step(
            f"Delete {leaf}",
            f"Delete smallest leaf {leaf}; append its neighbour {neighbor}",
            nodes, {graph.key(leaf, neighbor): "rejected"},
            panel=("code: (" + ", ".join(code) + ")",),
            extras={"code": list(code), "leaf": leaf, "neighbor": neighbor},
        ))
    if expect is not None:
        wanted = [str(value) for value in expect]
        for index in range(max(len(code), len(wanted))):
            actual = code[index] if index < len(code) else None
            claimed = wanted[index] if index < len(wanted) else None
            if actual != claimed:
                raise GraphError(
                    f"expected Prüfer code first differs at position {index + 1}: "
                    f"computed {actual!r}, expected {claimed!r}",
                    witness=(index + 1, actual, claimed),
                )
    return steps


def prufer_decode_graph(code: list[Any]) -> Graph:
    """Build the labelled tree on ``1..len(code)+2`` represented by ``code``."""
    if not isinstance(code, list):
        raise GraphError("code must be an array")
    n = len(code) + 2
    parsed: list[int] = []
    for index, value in enumerate(code):
        if isinstance(value, bool):
            value = -1
        try:
            entry = int(value)
        except (TypeError, ValueError):
            entry = -1
        if entry < 1 or entry > n or str(entry) != str(value):
            raise GraphError(f"code entry {value!r} at position {index + 1} is outside 1..{n}",
                             witness=(index + 1, value))
        parsed.append(entry)
    degree = {vertex: 1 for vertex in range(1, n + 1)}
    for vertex in parsed:
        degree[vertex] += 1
    edges: list[Edge] = []
    for vertex in parsed:
        leaf = min(v for v in degree if degree[v] == 1)
        edges.append(Edge(str(leaf), str(vertex)))
        degree[leaf] -= 1
        degree[vertex] -= 1
    last = [v for v in degree if degree[v] == 1]
    edges.append(Edge(str(last[0]), str(last[1])))
    ids = tuple(str(v) for v in range(1, n + 1))
    return Graph(ids, {v: v for v in ids}, tuple(edges))


def prufer_decode_steps(code: list[Any]) -> list[Step]:
    """Reveal the deterministic smallest-leaf decoding, one edge per step."""
    graph = prufer_decode_graph(code)
    parsed = [str(value) for value in code]
    steps = [Step("Start", f"Decode ({', '.join(parsed)}) on vertices 1..{len(parsed) + 2}",
                  panel=("remaining code: (" + ", ".join(parsed) + ")",),
                  extras={"visible_edges": []})]
    visible: list[EdgeKey] = []
    for index, edge in enumerate(graph.edges):
        key = graph.key(edge.source, edge.target)
        visible.append(key)
        remaining = parsed[index + 1:] if index < len(parsed) else []
        pointer = f"read {parsed[index]}" if index < len(parsed) else "join final leaves"
        steps.append(Step(
            f"Add {edge.source}–{edge.target}",
            f"{pointer}; add edge {edge.source}–{edge.target}",
            {edge.source: "current", edge.target: "frontier"},
            {candidate: "tree" for candidate in visible},
            panel=("remaining code: (" + ", ".join(remaining) + ")",),
            extras={"visible_edges": list(visible)},
        ))
    return steps


# ------------------------------------------------------------ Havel–Hakimi


def havel_hakimi_steps(sequence: list[Any], realize: bool = False) -> list[Step]:
    """Reduce a degree sequence and optionally unwind a labelled realization."""
    if not isinstance(sequence, list) or not sequence:
        raise GraphError("sequence must be a non-empty array")
    degrees: list[int] = []
    for index, value in enumerate(sequence):
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise GraphError(f"sequence entry {value!r} at position {index + 1} must be nonnegative",
                             witness=(index + 1, value))
        if value >= len(sequence):
            raise GraphError(f"degree {value} at position {index + 1} is at least n={len(sequence)}",
                             witness=(index + 1, value))
        degrees.append(value)
    if sum(degrees) % 2:
        raise GraphError(f"degree sum {sum(degrees)} is odd", witness=tuple(degrees))

    items = [(degree, str(index + 1)) for index, degree in enumerate(degrees)]
    items.sort(key=lambda item: (-item[0], _vertex_sort_key(item[1])))
    steps = [Step("Start", "Sort the degree sequence in non-increasing order",
                  panel=("sequence: (" + ", ".join(str(d) for d, _ in items) + ")",),
                  extras={"values": [d for d, _ in items], "highlights": {}})]
    batches: list[tuple[str, list[str]]] = []
    while items and items[0][0] > 0:
        degree, vertex = items.pop(0)
        if degree > len(items):
            witness = tuple([degree] + [d for d, _ in items])
            raise GraphError(f"reduction cannot connect degree {degree} to only {len(items)} entries",
                             witness=witness)
        neighbors = [name for _, name in items[:degree]]
        reduced = [(d - 1 if index < degree else d, name)
                   for index, (d, name) in enumerate(items)]
        raw = tuple(d for d, _ in reduced)
        if any(d < 0 for d in raw):
            raise GraphError("Havel–Hakimi reduction produced a negative entry: "
                             + str(raw), witness=raw)
        batches.append((vertex, neighbors))
        reduced.sort(key=lambda item: (-item[0], _vertex_sort_key(item[1])))
        displayed = [d for d, _ in reduced]
        highlights = {str(index): "comparison" for index in range(min(degree, len(reduced)))}
        steps.append(Step(
            f"Remove {degree}",
            f"Remove {degree}; decrement the next {degree} entries",
            panel=("sequence: (" + ", ".join(str(d) for d in displayed) + ")",),
            extras={"values": displayed, "highlights": highlights,
                    "removed": degree, "vertex": vertex},
        ))
        items = reduced
    if items and any(degree for degree, _ in items):
        witness = tuple(degree for degree, _ in items)
        raise GraphError("sequence does not reduce to zero", witness=witness)
    if not realize:
        return steps

    all_edges = [(vertex, neighbor) for vertex, neighbors in batches for neighbor in neighbors]
    visible: list[EdgeKey] = []
    for vertex, neighbors in reversed(batches):
        for neighbor in neighbors:
            visible.append((min(vertex, neighbor), max(vertex, neighbor)))
        steps.append(Step(
            f"Join {vertex}",
            f"Restore vertex {vertex} and join it to {', '.join(neighbors)}",
            {vertex: "current", **{neighbor: "frontier" for neighbor in neighbors}},
            {edge: "tree" for edge in visible},
            panel=(f"realized edges: {len(visible)} of {len(all_edges)}",),
            extras={"graph_nodes": [str(i) for i in range(1, len(degrees) + 1)],
                    "graph_edges": list(all_edges), "visible_edges": list(visible)},
        ))
    return steps


# ------------------------------------------------------------- tree centres


def tree_center_steps(graph: Graph, show_eccentricities: bool = False) -> list[Step]:
    """Strip all leaves by rounds until Jordan's one or two centres remain."""
    require_tree(graph)
    if len(graph.ids) == 1:
        return [Step("Center", f"{graph.ids[0]} is the center", {graph.ids[0]: "target"},
                     badges={graph.ids[0]: "ε=0"} if show_eccentricities else {},
                     panel=(f"center: {{{graph.ids[0]}}}", "radius = diameter = 0"),
                     extras={"centers": [graph.ids[0]], "radius": 0, "diameter": 0})]

    def distances(source: str) -> dict[str, int]:
        distance = {source: 0}
        queue = [source]
        while queue:
            vertex = queue.pop(0)
            for neighbor in graph.neighbors(vertex):
                if neighbor not in distance:
                    distance[neighbor] = distance[vertex] + 1
                    queue.append(neighbor)
        return distance

    eccentricity = {vertex: max(distances(vertex).values()) for vertex in graph.ids}
    diameter = max(eccentricity.values())
    radius = min(eccentricity.values())
    remaining = set(graph.ids)
    removed: list[str] = []
    round_number = 0
    initial_leaves = [v for v in graph.ids if graph.degree(v) <= 1]
    steps = [Step("Start", "Strip every leaf in simultaneous rounds",
                  {v: "frontier" for v in initial_leaves},
                  badges=({v: f"ε={eccentricity[v]}" for v in graph.ids}
                          if show_eccentricities else {}),
                  panel=("leaves: " + ", ".join(initial_leaves),))]
    while len(remaining) > 2:
        leaves = [v for v in graph.ids if v in remaining and
                  sum(neighbor in remaining for neighbor in graph.neighbors(v)) <= 1]
        round_number += 1
        remaining.difference_update(leaves)
        removed.extend(leaves)
        next_leaves = [v for v in graph.ids if v in remaining and
                       sum(neighbor in remaining for neighbor in graph.neighbors(v)) <= 1]
        nodes = {v: "rejected" for v in removed}
        nodes.update({v: "frontier" for v in next_leaves})
        steps.append(Step(
            f"Strip round {round_number}",
            f"Remove leaves {{{', '.join(leaves)}}}", nodes,
            badges=({v: f"ε={eccentricity[v]}" for v in graph.ids if v in remaining}
                    if show_eccentricities else {}),
            panel=("remaining: {" + ", ".join(v for v in graph.ids if v in remaining) + "}",),
            extras={"removed": list(leaves), "remaining": [v for v in graph.ids if v in remaining]},
        ))
    centers = [v for v in graph.ids if v in remaining]
    nodes = {v: "rejected" for v in removed}
    nodes.update({v: "target" for v in centers})
    steps.append(Step(
        "Center" if len(centers) == 1 else "Centers",
        "Jordan center" + ("" if len(centers) == 1 else "s") + ": {" + ", ".join(centers) + "}",
        nodes,
        badges=({v: f"ε={eccentricity[v]}" for v in centers}
                if show_eccentricities else {}),
        panel=("center: {" + ", ".join(centers) + "}",
               f"radius = {radius} · diameter = {diameter}"),
        extras={"centers": centers, "radius": radius, "diameter": diameter},
    ))
    return steps


# --------------------------------------------------------- ear decomposition


def ear_decomposition_steps(graph: Graph, start_cycle: list[Any] | None = None) -> list[Step]:
    """Compute an open-ear decomposition of a 2-connected graph."""
    if graph.directed:
        raise GraphError("ear decomposition needs an undirected graph")
    if len(graph.ids) < 3:
        raise GraphError("a 2-connected graph needs at least three vertices", witness=graph.ids)
    analysis = connectivity_analysis(graph)
    if analysis.articulations:
        cut = analysis.articulations[0]
        raise GraphError(f"the graph is not 2-connected; {cut} is an articulation vertex",
                         witness=cut)
    reach = {graph.ids[0]}
    queue = [graph.ids[0]]
    while queue:
        vertex = queue.pop(0)
        for neighbor in graph.neighbors(vertex):
            if neighbor not in reach:
                reach.add(neighbor)
                queue.append(neighbor)
    if len(reach) != len(graph.ids):
        other = next(vertex for vertex in graph.ids if vertex not in reach)
        raise GraphError("the graph is disconnected, so it is not 2-connected",
                         witness=(graph.ids[0], other))

    if start_cycle is not None:
        if not isinstance(start_cycle, list) or len(start_cycle) < 4:
            raise GraphError("start_cycle must be a closed cycle with at least three vertices")
        cycle = [require_vertex(graph, vertex, "start_cycle entry") for vertex in start_cycle]
        if cycle[0] != cycle[-1] or len(set(cycle[:-1])) != len(cycle) - 1:
            raise GraphError("start_cycle must close once without repeating an internal vertex",
                             witness=cycle)
        missing = next(((u, v) for u, v in zip(cycle, cycle[1:])
                        if not graph.has_edge(u, v)), None)
        if missing:
            raise GraphError(f"start_cycle uses missing edge {missing[0]}–{missing[1]}",
                             witness=missing)
    else:
        found = _find_cycle(graph, list(graph.ids))
        if len(found) < 3:
            raise GraphError("the graph has no cycle, so it is not 2-connected")
        cycle = found + [found[0]]

    ears: list[list[str]] = [cycle]
    introduced = set(cycle[:-1])
    used: set[EdgeKey] = {graph.key(u, v) for u, v in zip(cycle, cycle[1:])}
    all_edges = [graph.key(edge.source, edge.target) for edge in graph.edges]

    def new_vertex_ear() -> list[str] | None:
        def extend(start: str, vertex: str, path: list[str]) -> list[str] | None:
            for neighbor in graph.neighbors(vertex):
                key = graph.key(vertex, neighbor)
                if key not in used and neighbor in introduced and neighbor != start:
                    return path + [neighbor]
            for neighbor in graph.neighbors(vertex):
                key = graph.key(vertex, neighbor)
                if key in used or neighbor in path:
                    continue
                if neighbor in introduced:
                    continue
                found_path = extend(start, neighbor, path + [neighbor])
                if found_path:
                    return found_path
            return None

        for start in graph.ids:
            if start not in introduced:
                continue
            for neighbor in graph.neighbors(start):
                if neighbor in introduced or graph.key(start, neighbor) in used:
                    continue
                found_path = extend(start, neighbor, [start, neighbor])
                if found_path:
                    return found_path
        return None

    while len(used) < len(all_edges):
        ear = new_vertex_ear()
        if ear is None:
            key = next((edge for edge in all_edges if edge not in used
                        and edge[0] in introduced and edge[1] in introduced), None)
            if key is None:
                remaining = next(edge for edge in all_edges if edge not in used)
                raise GraphError("could not extend an ear through the remaining edge",
                                 witness=remaining)
            ear = [key[0], key[1]]
        ears.append(ear)
        introduced.update(ear)
        used.update(graph.key(u, v) for u, v in zip(ear, ear[1:]))

    steps: list[Step] = []
    colored: dict[EdgeKey, str] = {}
    visible_nodes: set[str] = set()
    for index, ear in enumerate(ears):
        role = f"color-{index + 1}"
        new_edges = [graph.key(u, v) for u, v in zip(ear, ear[1:])]
        colored.update({edge: role for edge in new_edges})
        visible_nodes.update(ear)
        notation = "–".join(ear)
        steps.append(Step(
            f"P{index}", f"P{index} = {notation}",
            {vertex: "visited" for vertex in graph.ids if vertex in visible_nodes},
            dict(colored), panel=(f"P{index}: {notation}",),
            extras={"ears": [list(value) for value in ears[:index + 1]]},
        ))
    return steps


# ---------------------------------------------------------- stable matching


def stable_matching_graph(proposers: Any, receivers: Any) -> Graph:
    """Validate complete strict preferences and return their bipartite graph."""
    if not isinstance(proposers, dict) or not proposers:
        raise GraphError("proposers must be a non-empty object of preference arrays")
    if not isinstance(receivers, dict) or not receivers:
        raise GraphError("receivers must be a non-empty object of preference arrays")
    left = [str(value) for value in proposers]
    right = [str(value) for value in receivers]
    if set(left) & set(right):
        raise GraphError("proposer and receiver names must be disjoint")
    if len(left) != len(right):
        raise GraphError("stable matching needs equally sized sides",
                         witness=(len(left), len(right)))
    for raw_name, preferences in proposers.items():
        name = str(raw_name)
        values = [str(value) for value in preferences] if isinstance(preferences, list) else []
        if len(values) != len(right) or set(values) != set(right):
            raise GraphError(f"preferences for proposer {name} must be a permutation of receivers",
                             witness=name)
    for raw_name, preferences in receivers.items():
        name = str(raw_name)
        values = [str(value) for value in preferences] if isinstance(preferences, list) else []
        if len(values) != len(left) or set(values) != set(left):
            raise GraphError(f"preferences for receiver {name} must be a permutation of proposers",
                             witness=name)
    ids = tuple(left + right)
    edges = tuple(Edge(proposer, receiver) for proposer in left for receiver in right)
    return Graph(ids, {vertex: vertex for vertex in ids}, edges)


def stable_matching_steps(proposers: Any, receivers: Any,
                          check: Any = None) -> list[Step]:
    """Proposer-optimal Gale–Shapley, one proposal per step."""
    graph = stable_matching_graph(proposers, receivers)
    left = [str(value) for value in proposers]
    right = [str(value) for value in receivers]
    proposer_preferences = {str(name): [str(value) for value in values]
                            for name, values in proposers.items()}
    receiver_rank = {str(name): {str(value): index for index, value in enumerate(values)}
                     for name, values in receivers.items()}

    if check is not None:
        if not isinstance(check, dict):
            raise GraphError("check must map every proposer to one receiver")
        authored = {str(name): str(value) for name, value in check.items()}
        if set(authored) != set(left) or len(set(authored.values())) != len(right) \
                or set(authored.values()) != set(right):
            raise GraphError("check must be a one-to-one matching of both sides")
        partner = {receiver: proposer for proposer, receiver in authored.items()}
        for proposer in left:
            own = authored[proposer]
            for receiver in proposer_preferences[proposer]:
                if receiver == own:
                    break
                if receiver_rank[receiver][proposer] < receiver_rank[receiver][partner[receiver]]:
                    raise GraphError(
                        f"authored matching is unstable: ({proposer}, {receiver}) is a blocking pair",
                        witness=(proposer, receiver))

    held: dict[str, str] = {}
    next_choice = {proposer: 0 for proposer in left}
    free = list(left)
    steps = [Step("Start", "Every proposer is free", panel=("held offers: —",),
                  extras={"proposals": 0})]
    proposals = 0
    while free:
        proposer = free.pop(0)
        if next_choice[proposer] >= len(right):
            raise GraphError(f"proposer {proposer} exhausted every preference", witness=proposer)
        receiver = proposer_preferences[proposer][next_choice[proposer]]
        next_choice[proposer] += 1
        proposals += 1
        previous = held.get(receiver)
        rejected: str | None = None
        if previous is None or receiver_rank[receiver][proposer] < receiver_rank[receiver][previous]:
            held[receiver] = proposer
            if previous is not None:
                rejected = previous
                free.append(previous)
        else:
            rejected = proposer
            free.append(proposer)
        held_edges = {graph.key(value, key): "tree" for key, value in held.items()}
        if rejected is not None:
            held_edges[graph.key(rejected, receiver)] = "rejected"
        nodes = {value: "visited" for pair in held_edges for value in pair}
        nodes[proposer] = "current"
        nodes[receiver] = "frontier"
        held_text = ", ".join(f"{value}–{key}" for key, value in held.items())
        outcome = (f"{receiver} holds {held[receiver]}"
                   if rejected is None else f"{receiver} rejects {rejected}; holds {held[receiver]}")
        steps.append(Step(
            f"{proposer} proposes to {receiver}", outcome, nodes, held_edges,
            panel=("held: " + held_text,), extras={"proposals": proposals, "held": dict(held)},
        ))
    matching = {proposer: receiver for receiver, proposer in held.items()}
    final_edges = {graph.key(proposer, receiver): "path"
                   for proposer, receiver in matching.items()}
    steps.append(Step(
        "Stable matching", f"No proposer is free after {proposals} proposals",
        {vertex: "visited" for vertex in graph.ids}, final_edges,
        panel=("matching: " + ", ".join(f"{p}–{matching[p]}" for p in left),
               f"proposals = {proposals}"),
        extras={"matching": matching, "proposals": proposals},
    ))
    return steps


# ------------------------------------------------------ Hamiltonian search


def hamiltonian_search_steps(graph: Graph, start: Any = None, max_frames: int = 20,
                             expect: str | None = None) -> list[Step]:
    """Backtrack over simple paths, bounding only the rendered trace, not the search."""
    start_vertex = require_vertex(graph, graph.ids[0] if start is None else start, "start")
    if not isinstance(max_frames, int) or isinstance(max_frames, bool) or not 2 <= max_frames <= 24:
        raise GraphError("max_frames must be an integer from 2 to 24")
    if expect is not None and expect not in {"cycle", "none"}:
        raise GraphError("expect must be cycle or none")
    path = [start_vertex]
    found: list[str] | None = None
    explored = 1
    events: list[tuple[str, str, list[str], str | None]] = []

    def search(vertex: str) -> bool:
        nonlocal explored, found
        if len(path) == len(graph.ids):
            if graph.has_edge(path[-1], start_vertex):
                found = list(path) + [start_vertex]
                return True
            return False
        for neighbor in graph.neighbors(vertex):
            if neighbor in path:
                continue
            path.append(neighbor)
            explored += 1
            events.append((f"Try {neighbor}", f"Extend the partial path to {neighbor}",
                           list(path), None))
            if search(neighbor):
                return True
            rejected = path.pop()
            events.append((f"Backtrack {rejected}",
                           f"No Hamiltonian cycle extends through {rejected}; backtrack",
                           list(path), rejected))
        return False

    search(start_vertex)
    if expect == "cycle" and found is None:
        raise GraphError(f"no Hamiltonian cycle exists; exhausted {explored} search states",
                         witness=("exhausted", explored))
    if expect == "none" and found is not None:
        raise GraphError("a Hamiltonian cycle exists: " + " → ".join(found), witness=found)

    def state(label: str, caption: str, current_path: list[str], rejected: str | None) -> Step:
        nodes = {vertex: "visited" for vertex in current_path}
        nodes[current_path[-1]] = "current"
        if rejected is not None:
            nodes[rejected] = "rejected"
        edges = {graph.key(u, v): "path" for u, v in zip(current_path, current_path[1:])}
        return Step(label, caption, nodes, edges,
                    panel=("path: " + " → ".join(current_path),),
                    extras={"path": list(current_path), "explored": explored})

    steps = [state("Start", f"Start backtracking at {start_vertex}", [start_vertex], None)]
    for event in events[:max(0, max_frames - 2)]:
        steps.append(state(*event))
    if found is not None:
        nodes = {vertex: "visited" for vertex in graph.ids}
        nodes[start_vertex] = "current"
        edges = {graph.key(u, v): "path" for u, v in zip(found, found[1:])}
        steps.append(Step("Hamiltonian cycle", "Found a cycle through every vertex exactly once",
                          nodes, edges,
                          panel=("cycle: " + " → ".join(found), f"explored states = {explored}"),
                          extras={"cycle": found, "explored": explored}))
    else:
        steps.append(Step("Exhausted search",
                          f"All {explored} partial-path states are exhausted; no cycle exists",
                          {start_vertex: "current"}, {},
                          panel=("Hamiltonian cycle: none", f"explored states = {explored}"),
                          extras={"cycle": None, "explored": explored}))
    return steps


# --------------------------------------------------------- Floyd–Warshall


def floyd_warshall_steps(graph: Graph) -> list[Step]:
    """All-pairs shortest paths, exposing the table after each intermediate."""
    if not graph.directed:
        raise GraphError("Floyd–Warshall here needs a directed graph")
    require_weights(graph)
    n = len(graph.ids)
    index = {vertex: i for i, vertex in enumerate(graph.ids)}
    distance = [[math.inf] * n for _ in range(n)]
    for i in range(n):
        distance[i][i] = 0.0
    for edge in graph.edges:
        i, j = index[edge.source], index[edge.target]
        distance[i][j] = min(distance[i][j], float(edge.weight))

    def values() -> list[list[str]]:
        return [[_fmt(value) for value in row] for row in distance]

    steps = [Step("D(0)", "Direct-edge distances before intermediate vertices",
                  extras={"values": values(), "changed": [], "k": None,
                          "labels": list(graph.ids)})]
    for k, intermediate in enumerate(graph.ids):
        changed: list[tuple[int, int]] = []
        before = [list(row) for row in distance]
        for i in range(n):
            for j in range(n):
                candidate = before[i][k] + before[k][j]
                if candidate < distance[i][j]:
                    distance[i][j] = candidate
                    changed.append((i, j))
        negative = next((graph.ids[i] for i in range(n) if distance[i][i] < 0), None)
        if negative is not None:
            witness: Any = negative
            try:
                bellman_ford_steps(graph, negative)
            except GraphError as exc:
                if "negative cycle" in str(exc):
                    witness = exc.witness
            raise GraphError(
                f"negative cycle detected: diagonal entry D[{negative},{negative}] became negative",
                witness=witness)
        steps.append(Step(
            f"Via {intermediate}",
            f"Allow {intermediate} as an intermediate vertex; {len(changed)} entries improve",
            panel=(f"k = {intermediate}", f"changed entries = {len(changed)}"),
            extras={"values": values(), "changed": changed, "k": intermediate,
                    "labels": list(graph.ids)},
        ))
    return steps


# ---------------------------------------------------------- Mycielski graph


def chromatic_number(graph: Graph) -> int:
    """Exact chromatic number for the small graphs accepted by figure templates."""
    order = sorted(graph.ids, key=lambda vertex: (-graph.degree(vertex), graph.ids.index(vertex)))

    def colorable(limit: int) -> bool:
        colors: dict[str, int] = {}

        def assign(index: int) -> bool:
            if index == len(order):
                return True
            vertex = order[index]
            forbidden = {colors[neighbor] for neighbor in graph.neighbors(vertex)
                         if neighbor in colors}
            for color in range(1, limit + 1):
                if color not in forbidden:
                    colors[vertex] = color
                    if assign(index + 1):
                        return True
                    del colors[vertex]
            return False

        return assign(0)

    return next(limit for limit in range(1, len(graph.ids) + 1) if colorable(limit))


def _has_triangle(graph: Graph) -> bool:
    for i, first in enumerate(graph.ids):
        for j in range(i + 1, len(graph.ids)):
            second = graph.ids[j]
            if not graph.has_edge(first, second):
                continue
            for third in graph.ids[j + 1:]:
                if graph.has_edge(first, third) and graph.has_edge(second, third):
                    return True
    return False


def mycielski_graph(base: Graph) -> Graph:
    """Construct M(G), with ids ``u0..``, ``v0..``, and hub ``w``."""
    if base.directed:
        raise GraphError("Mycielski construction needs an undirected base graph")
    output_size = 2 * len(base.ids) + 1
    if output_size > 11:
        raise GraphError(f"M(G) has {output_size} vertices; at most 11 fit",
                         witness=(len(base.ids), output_size))
    u = [f"u{i}" for i in range(len(base.ids))]
    v = [f"v{i}" for i in range(len(base.ids))]
    index = {vertex: i for i, vertex in enumerate(base.ids)}
    edges: list[Edge] = []
    for edge in base.edges:
        i, j = index[edge.source], index[edge.target]
        edges.extend((Edge(u[i], u[j]), Edge(v[i], u[j]), Edge(v[j], u[i])))
    edges.extend(Edge("w", shadow) for shadow in v)
    ids = tuple(u + v + ["w"])
    return Graph(ids, {vertex: vertex for vertex in ids}, tuple(edges))


def mycielski_steps(base: Graph) -> list[Step]:
    """Show the three-layer construction, then a deterministic greedy coloring."""
    graph = mycielski_graph(base)
    n = len(base.ids)
    base_chi = chromatic_number(base)
    result_chi = chromatic_number(graph)
    base_triangle_free = not _has_triangle(base)
    result_triangle_free = not _has_triangle(graph)
    steps = [Step(
        "Three layers", "Copy G as u, add shadow vertices v, then join hub w to every v",
        {**{f"u{i}": "visited" for i in range(n)},
         **{f"v{i}": "frontier" for i in range(n)}, "w": "target"},
        panel=(f"|V(M(G))| = {len(graph.ids)}", f"|E(M(G))| = {len(graph.edges)}"),
        extras={"graph": graph, "base_chi": base_chi, "result_chi": result_chi,
                "triangle_free": result_triangle_free},
    )]
    colors: dict[str, int] = {}
    for vertex in graph.ids:
        used = {colors[neighbor] for neighbor in graph.neighbors(vertex) if neighbor in colors}
        colors[vertex] = next(color for color in range(1, len(graph.ids) + 1)
                              if color not in used)
        final = vertex == graph.ids[-1]
        panel = ((f"χ(G) = {base_chi} · χ(M(G)) = {result_chi}",
                  "triangle-free: " + ("yes" if base_triangle_free and result_triangle_free else "no"))
                 if final else (f"colors used: {max(colors.values())}",))
        steps.append(Step(
            f"Color {vertex}", f"Assign {vertex} the smallest available color {colors[vertex]}",
            {name: f"color-{color}" for name, color in colors.items()}, panel=panel,
            extras={"graph": graph, "colors": dict(colors), "base_chi": base_chi,
                    "result_chi": result_chi, "triangle_free": result_triangle_free},
        ))
    return steps


# ------------------------------------------------------------ edge coloring


def _edge_coloring_with_k(graph: Graph, limit: int) -> dict[EdgeKey, int] | None:
    edges = [graph.key(edge.source, edge.target) for edge in graph.edges]
    adjacent = {edge: {other for other in edges if other != edge and set(edge) & set(other)}
                for edge in edges}
    order = sorted(edges, key=lambda edge: (-len(adjacent[edge]), edges.index(edge)))
    colors: dict[EdgeKey, int] = {}

    def assign(index: int) -> bool:
        if index == len(order):
            return True
        edge = order[index]
        forbidden = {colors[other] for other in adjacent[edge] if other in colors}
        highest = max(colors.values(), default=0)
        for color in range(1, min(limit, highest + 1) + 1):
            if color not in forbidden:
                colors[edge] = color
                if assign(index + 1):
                    return True
                del colors[edge]
        return False

    return dict(colors) if assign(0) else None


def edge_coloring_steps(graph: Graph, classes: Any = None,
                        expect: Any = None) -> list[Step]:
    """Compute or verify a proper edge coloring of a simple undirected graph."""
    if graph.directed:
        raise GraphError("edge coloring here needs an undirected graph")
    delta = max((graph.degree(vertex) for vertex in graph.ids), default=0)
    if expect is not None:
        if not isinstance(expect, int) or isinstance(expect, bool) or expect < 0:
            raise GraphError("expect must be a nonnegative integer")
        if expect < delta:
            raise GraphError(f"expect {expect} is below maximum degree Δ={delta}", witness=delta)

    colors: dict[EdgeKey, int]
    if classes is not None:
        if not isinstance(classes, list) or not classes:
            raise GraphError("classes must be a non-empty array of edge arrays")
        colors = {}
        for color, edge_class in enumerate(classes, 1):
            if not isinstance(edge_class, list):
                raise GraphError(f"class {color} must be an array")
            used_vertices: set[str] = set()
            for raw in edge_class:
                if isinstance(raw, dict):
                    raw = [raw.get("from"), raw.get("to")]
                if not isinstance(raw, (list, tuple)) or len(raw) != 2:
                    raise GraphError(f"class {color} contains an invalid edge")
                u, v = str(raw[0]), str(raw[1])
                if not graph.has_edge(u, v):
                    raise GraphError(f"class {color} contains non-edge {u}–{v}", witness=(u, v))
                shared = next((vertex for vertex in (u, v) if vertex in used_vertices), None)
                if shared is not None:
                    raise GraphError(f"two edges in class {color} share vertex {shared}", witness=shared)
                key = graph.key(u, v)
                if key in colors:
                    raise GraphError(f"edge {u}–{v} occurs in more than one class", witness=key)
                colors[key] = color
                used_vertices.update((u, v))
        missing = [graph.key(edge.source, edge.target) for edge in graph.edges
                   if graph.key(edge.source, edge.target) not in colors]
        if missing:
            raise GraphError("classes omit edge " + f"{missing[0][0]}–{missing[0][1]}",
                             witness=missing[0])
    else:
        colors = {}
        for limit in range(delta, delta + 2):
            found = _edge_coloring_with_k(graph, limit)
            if found is not None:
                colors = found
                break
        if graph.edges and not colors:  # Vizing guarantees this cannot happen for a simple graph.
            raise GraphError("could not compute an edge coloring")
    chromatic_index = max(colors.values(), default=0)
    if expect is not None and expect != chromatic_index:
        raise GraphError(f"expected edge chromatic number {expect}, computed {chromatic_index}",
                         witness=(expect, chromatic_index))

    steps = [Step("Start", f"Maximum degree Δ={delta}", panel=(f"Δ = {delta}",))]
    revealed: dict[EdgeKey, str] = {}
    for color in range(1, chromatic_index + 1):
        current = [edge for edge in colors if colors[edge] == color]
        revealed.update({edge: f"color-{color}" for edge in current})
        notation = ", ".join(f"{u}–{v}" for u, v in current)
        steps.append(Step(
            f"Color class {color}", f"Class {color}: {notation}", {}, dict(revealed),
            panel=(f"class {color}: {notation}", f"colors used: {color}"),
            extras={"classes": [[edge for edge in colors if colors[edge] == value]
                                for value in range(1, color + 1)],
                    "chromatic_index": chromatic_index, "delta": delta},
        ))
    return steps


# -------------------------------------------------------------- degeneracy


def degeneracy_ordering_steps(graph: Graph) -> list[Step]:
    """Smallest-last deletion followed by greedy coloring in reverse order."""
    if graph.directed:
        raise GraphError("degeneracy ordering here needs an undirected graph")
    remaining = set(graph.ids)
    order: list[str] = []
    removed: list[str] = []
    degeneracy = 0
    steps = [Step("Start", "Repeatedly delete a current minimum-degree vertex",
                  panel=("degeneracy so far: 0",))]
    while remaining:
        degree = {vertex: sum(neighbor in remaining for neighbor in graph.neighbors(vertex))
                  for vertex in graph.ids if vertex in remaining}
        minimum = min(degree.values())
        vertex = next(value for value in graph.ids
                      if value in remaining and degree[value] == minimum)
        degeneracy = max(degeneracy, minimum)
        remaining.remove(vertex)
        order.append(vertex)
        removed.append(vertex)
        nodes = {value: "rejected" for value in removed}
        nodes[vertex] = "current"
        steps.append(Step(
            f"Delete {vertex}", f"Delete minimum-degree vertex {vertex} (degree {minimum})",
            nodes, badges={value: f"deg {degree[value]}" for value in degree},
            panel=("order: " + ", ".join(order), f"degeneracy so far: {degeneracy}"),
            extras={"order": list(order), "degree": minimum, "degeneracy": degeneracy},
        ))
    colors: dict[str, int] = {}
    for vertex in reversed(order):
        used = {colors[neighbor] for neighbor in graph.neighbors(vertex) if neighbor in colors}
        colors[vertex] = next(color for color in range(1, degeneracy + 2)
                              if color not in used)
    classes = [[vertex for vertex in graph.ids if colors[vertex] == color]
               for color in range(1, max(colors.values(), default=0) + 1)]
    steps.append(Step(
        "Reverse greedy coloring",
        f"Color in reverse deletion order using {len(classes)} ≤ {degeneracy + 1} colors",
        {vertex: f"color-{colors[vertex]}" for vertex in graph.ids},
        panel=(f"degeneracy = {degeneracy}",
               "classes: " + " | ".join("{" + ",".join(group) + "}" for group in classes)),
        extras={"order": order, "degeneracy": degeneracy, "colors": colors,
                "classes": classes},
    ))
    return steps


# ---------------------------------------------------------------- traversal


def traversal_steps(graph: Graph, start: str, algorithm: str = "bfs",
                    order: list[str] | None = None) -> list[Step]:
    """BFS with its queue, or textbook recursive DFS with its call stack.

    BFS discovers a vertex when it joins the queue, so the queue is the
    frontier. DFS follows the recursion: a vertex is visited when the recursion
    reaches it, and the stack shown is the path from ``start`` to the current
    vertex. The discovery-on-push stack variant is deliberately not used — it
    visits in a different order and draws "DFS trees" with cross edges, which
    no depth-first search of an undirected graph produces.
    """
    start = require_vertex(graph, start, "start")
    if algorithm not in {"bfs", "dfs"}:
        raise GraphError("algorithm must be bfs or dfs")
    visited: list[str] = []
    tree: list[EdgeKey] = []
    steps: list[Step] = []
    frontier_name = "queue" if algorithm == "bfs" else "stack"

    def state(current: str | None, frontier: list[str]) -> Step:
        nodes = {v: "visited" for v in visited}
        nodes.update({v: "frontier" for v in frontier})
        if current is not None:
            nodes[current] = "current"
        edges = {graph.key(u, v): "tree" for u, v in tree}
        badges = {v: f"#{i + 1}" for i, v in enumerate(visited)}
        frontier_text = ", ".join(frontier) if frontier else "∅"
        order_text = ", ".join(visited) if visited else "∅"
        label = "Initial frontier" if current is None else f"Visit {current}"
        caption = (f"{frontier_name}: [{frontier_text}] · order: [{order_text}]")
        return Step(label, caption, nodes, edges, badges,
                    panel=(f"{frontier_name}: [{frontier_text}]", f"order: [{order_text}]"),
                    extras={"current": current, "frontier": list(frontier),
                            "visited": list(visited), "tree_edges": list(tree)})

    steps.append(state(None, [start]))
    if algorithm == "bfs":
        queue, discovered = [start], {start}
        while queue:
            current = queue.pop(0)
            visited.append(current)
            for neighbor in graph.neighbors(current, order):
                if neighbor in discovered:
                    continue
                discovered.add(neighbor)
                tree.append((current, neighbor))
                queue.append(neighbor)
            steps.append(state(current, queue))
        return steps

    visited.append(start)
    stack: list[tuple[str, int]] = [(start, 0)]
    steps.append(state(start, [start]))
    while stack:
        vertex, index = stack[-1]
        neighbors = graph.neighbors(vertex, order)
        while index < len(neighbors) and neighbors[index] in visited:
            index += 1
        if index == len(neighbors):
            stack.pop()
            continue
        neighbor = neighbors[index]
        stack[-1] = (vertex, index + 1)
        visited.append(neighbor)
        tree.append((vertex, neighbor))
        stack.append((neighbor, 0))
        steps.append(state(neighbor, [entry[0] for entry in stack]))
    return steps


# ------------------------------------------------------------ shortest paths


def _distance_panel(graph: Graph, dist: dict[str, float]) -> tuple[str, ...]:
    return tuple(f"{v}: {_fmt(dist[v])}" for v in sorted(graph.ids))


def dijkstra_steps(graph: Graph, start: str) -> list[Step]:
    """Settle the closest tentative vertex, relax its edges, repeat."""
    require_weights(graph, nonnegative=True)
    start = require_vertex(graph, start, "start")
    dist = {v: math.inf for v in graph.ids}
    dist[start] = 0.0
    previous: dict[str, str] = {}
    settled: list[str] = []
    steps = [Step("Initialize", f"Set d({start}) = 0 and every other distance to ∞",
                  {start: "frontier"}, {}, {v: _fmt(d) for v, d in dist.items()},
                  panel=_distance_panel(graph, dist))]
    while True:
        choices = [v for v in graph.ids if v not in settled and math.isfinite(dist[v])]
        if not choices:
            break
        current = min(choices, key=lambda v: (dist[v], graph.ids.index(v)))
        settled.append(current)
        relaxed: list[str] = []
        for neighbor in graph.neighbors(current):
            candidate = dist[current] + graph.weight(current, neighbor)
            if candidate < dist[neighbor]:
                dist[neighbor], previous[neighbor] = candidate, current
                relaxed.append(f"d({neighbor}) = {_fmt(candidate)}")
        nodes = {v: "visited" for v in settled}
        nodes.update({v: "frontier" for v in graph.ids
                      if v not in settled and math.isfinite(dist[v])})
        nodes[current] = "current"
        edges = {graph.key(u, v): "tree" for v, u in previous.items()}
        caption = f"Settle {current} (d = {_fmt(dist[current])})"
        caption += "; relax: " + ", ".join(relaxed) if relaxed else "; nothing improves"
        steps.append(Step(f"Settle {current}", caption, nodes, edges,
                          {v: _fmt(d) for v, d in dist.items()},
                          panel=_distance_panel(graph, dist)))
    return steps


def bellman_ford_steps(graph: Graph, start: str) -> list[Step]:
    """Relax every edge, |V|−1 rounds; a further improvement is a negative cycle.

    Raises :class:`GraphError` carrying the cycle when one exists, because a
    "shortest path" through a negative cycle is not a quantity to draw.
    """
    require_weights(graph)
    start = require_vertex(graph, start, "start")
    dist = {v: math.inf for v in graph.ids}
    dist[start] = 0.0
    previous: dict[str, str] = {}
    arcs = [(e.source, e.target, e.weight or 0.0) for e in graph.edges]
    if not graph.directed:
        arcs += [(e.target, e.source, e.weight or 0.0) for e in graph.edges]
    steps = [Step("Initialize", f"Set d({start}) = 0 and every other distance to ∞",
                  {start: "frontier"}, {}, {v: _fmt(d) for v, d in dist.items()},
                  panel=_distance_panel(graph, dist))]

    def relax_all() -> list[str]:
        changed = []
        for u, v, w in arcs:
            if math.isfinite(dist[u]) and dist[u] + w < dist[v] - 1e-12:
                dist[v], previous[v] = dist[u] + w, u
                changed.append(f"d({v}) = {_fmt(dist[v])}")
        return changed

    for round_no in range(1, len(graph.ids)):
        changed = relax_all()
        nodes = {v: "visited" for v in graph.ids if math.isfinite(dist[v])}
        nodes[start] = "current"
        edges = {graph.key(u, v): "tree" for v, u in previous.items()}
        caption = f"Round {round_no}: " + (", ".join(changed) if changed else "no change")
        steps.append(Step(f"Round {round_no}", caption, nodes, edges,
                          {v: _fmt(d) for v, d in dist.items()},
                          panel=_distance_panel(graph, dist)))
        if not changed:
            break
    if relax_all():
        # Walk back |V| predecessors from an improved vertex to land on the
        # cycle, then read it off.
        improved = next(v for v in graph.ids if v in previous)
        vertex = improved
        for _ in graph.ids:
            vertex = previous.get(vertex, vertex)
        cycle, current = [vertex], previous[vertex]
        while current != vertex:
            cycle.append(current)
            current = previous[current]
        cycle.reverse()
        raise GraphError("the graph has a negative cycle: " + " → ".join(cycle + [cycle[0]]),
                         witness=cycle)
    return steps


# ------------------------------------------------------------- spanning trees


def kruskal_steps(graph: Graph) -> list[Step]:
    """Take edges by weight; accept one that joins two components, reject one
    that would close a cycle. The rejections are shown — they are the lesson."""
    require_weights(graph)
    if graph.directed:
        raise GraphError("Kruskal requires an undirected graph")
    parent = {v: v for v in graph.ids}

    def root(v: str) -> str:
        while parent[v] != v:
            parent[v] = parent[parent[v]]
            v = parent[v]
        return v

    chosen: dict[EdgeKey, str] = {}
    total = 0.0
    steps = [Step("Start", "Sort the edges by weight; the forest is empty",
                  panel=("forest weight = 0",))]
    ordered = sorted(enumerate(graph.edges), key=lambda p: (p[1].weight or 0.0, p[0]))
    for _, edge in ordered:
        u, v = edge.source, edge.target
        key = graph.key(u, v)
        in_tree = {x for k in chosen if chosen[k] == "tree" for x in k}
        if root(u) == root(v):
            chosen[key] = "rejected"
            caption = f"Reject {u}–{v} ({edge.weight:g}): it would close a cycle"
            label = f"Reject {u}–{v}"
        else:
            parent[root(u)] = root(v)
            chosen[key] = "tree"
            total += edge.weight or 0.0
            in_tree |= {u, v}
            caption = f"Accept {u}–{v} ({edge.weight:g}): it joins two components"
            label = f"Accept {u}–{v}"
        nodes = {x: "visited" for x in in_tree}
        steps.append(Step(label, caption, nodes, dict(chosen),
                          panel=(f"forest weight = {total:g}",)))
    return steps


def prim_steps(graph: Graph, start: str) -> list[Step]:
    """Grow one tree from ``start`` by the cheapest edge leaving it."""
    require_weights(graph)
    if graph.directed:
        raise GraphError("Prim requires an undirected graph")
    start = require_vertex(graph, start, "start")
    in_tree = [start]
    chosen: dict[EdgeKey, str] = {}
    total = 0.0
    steps = [Step("Start", f"Begin the tree at {start}", {start: "current"},
                  panel=("tree weight = 0",))]
    while True:
        candidates = []
        for edge in graph.edges:
            u, v = edge.source, edge.target
            if (u in in_tree) != (v in in_tree):
                inside, outside = (u, v) if u in in_tree else (v, u)
                candidates.append((edge.weight or 0.0, graph.ids.index(outside), inside, outside))
        if not candidates:
            break
        weight, _, inside, outside = min(candidates)
        in_tree.append(outside)
        chosen[graph.key(inside, outside)] = "tree"
        total += weight
        nodes = {v: "visited" for v in in_tree}
        nodes[outside] = "current"
        frontier = {graph.key(u, v): "frontier" for _, _, u, v in candidates
                    if graph.key(u, v) not in chosen}
        steps.append(Step(f"Add {outside}",
                          f"Cheapest edge leaving the tree: {inside}–{outside} ({weight:g})",
                          nodes, {**frontier, **chosen}, panel=(f"tree weight = {total:g}",)))
    return steps


# --------------------------------------------------------------- DAG / SCC


def _find_cycle(graph: Graph, among: Iterable[str]) -> list[str]:
    """A directed cycle inside ``among``, by DFS colouring."""
    allowed = set(among)
    colour: dict[str, int] = {}
    stack: list[str] = []

    def visit(v: str) -> list[str] | None:
        colour[v] = 1
        stack.append(v)
        for w in graph.neighbors(v):
            if w not in allowed:
                continue
            if colour.get(w) == 1:
                return stack[stack.index(w):]
            if w not in colour:
                found = visit(w)
                if found:
                    return found
        stack.pop()
        colour[v] = 2
        return None

    for v in graph.ids:
        if v in allowed and v not in colour:
            found = visit(v)
            if found:
                return found
    return []


def topological_sort_steps(graph: Graph, tie_break: str = "fifo") -> list[Step]:
    """Kahn's algorithm: repeatedly remove a vertex with no incoming edge."""
    if not graph.directed:
        raise GraphError("topological order needs a directed graph")
    if tie_break not in {"min", "fifo"}:
        raise GraphError("tie_break must be min or fifo")
    indegree = {v: 0 for v in graph.ids}
    for edge in graph.edges:
        indegree[edge.target] += 1
    order: list[str] = []
    removed: set[EdgeKey] = set()
    steps = [Step("Start", "Count incoming edges; vertices with none can go first",
                  {v: "frontier" for v in graph.ids if indegree[v] == 0}, {},
                  {v: f"in {d}" for v, d in indegree.items()},
                  panel=("order: ∅",))]
    ready = [v for v in graph.ids if indegree[v] == 0]
    while ready:
        if tie_break == "min":
            current = min(ready, key=_vertex_sort_key)
            ready.remove(current)
        else:
            current = ready.pop(0)
        order.append(current)
        for w in graph.neighbors(current):
            indegree[w] -= 1
            removed.add((current, w))
            if indegree[w] == 0:
                ready.append(w)
        nodes = {v: "visited" for v in order}
        nodes.update({v: "frontier" for v in ready})
        nodes[current] = "current"
        steps.append(Step(f"Remove {current}",
                          f"Take {current} (no incoming edges left); position {len(order)}",
                          nodes, {k: "tree" for k in removed},
                          {v: f"in {d}" for v, d in indegree.items()},
                          panel=("order: " + ", ".join(order),),
                          extras={"tie_break": tie_break, "ready": list(ready)}))
    if len(order) != len(graph.ids):
        cycle = _find_cycle(graph, [v for v in graph.ids if v not in order])
        raise GraphError("the graph has a cycle, so it has no topological order: "
                         + " → ".join(cycle + cycle[:1]), witness=cycle)
    return steps


def scc_steps(graph: Graph) -> list[Step]:
    """Kosaraju: finish order on G, then components peeled off the reverse."""
    if not graph.directed:
        raise GraphError("strongly connected components need a directed graph")
    finished: list[str] = []
    seen: set[str] = set()

    def visit(v: str) -> None:
        seen.add(v)
        for w in graph.neighbors(v):
            if w not in seen:
                visit(w)
        finished.append(v)

    for v in graph.ids:
        if v not in seen:
            visit(v)
    steps = [Step("Finish order", "Depth-first search finishes vertices in this order",
                  {}, {}, {v: f"f={i + 1}" for i, v in enumerate(finished)},
                  panel=("finish order: " + ", ".join(finished),))]
    reverse = {v: [] for v in graph.ids}
    for edge in graph.edges:
        reverse[edge.target].append(edge.source)
    assigned: dict[str, int] = {}
    components: list[list[str]] = []
    for v in reversed(finished):
        if v in assigned:
            continue
        component, stack = [], [v]
        assigned[v] = len(components) + 1
        while stack:
            x = stack.pop()
            component.append(x)
            for w in reverse[x]:
                if w not in assigned:
                    assigned[w] = len(components) + 1
                    stack.append(w)
        components.append(component)
        nodes = {x: f"color-{c}" for x, c in assigned.items()}
        edges = {graph.key(e.source, e.target): "tree" for e in graph.edges
                 if assigned.get(e.source) == assigned.get(e.target)}
        steps.append(Step(f"Component {len(components)}",
                          f"From {v} on the reversed graph: {{{', '.join(component)}}}",
                          nodes, edges, {x: f"f={i + 1}" for i, x in enumerate(finished)},
                          panel=tuple(f"C{i + 1} = {{{', '.join(c)}}}"
                                      for i, c in enumerate(components))))
    return steps


# ------------------------------------------------------------------ flows


def max_flow_steps(graph: Graph, source: str, sink: str) -> list[Step]:
    """Edmonds–Karp: augment along shortest residual paths; end with the cut.

    The final step is the certificate — the vertices the residual graph still
    reaches from the source, and the saturated edges leaving that set, whose
    capacities sum to the flow value.
    """
    if not graph.directed:
        raise GraphError("a flow network is directed")
    source = require_vertex(graph, source, "source")
    sink = require_vertex(graph, sink, "sink")
    if source == sink:
        raise GraphError("source and sink must differ")
    capacity: dict[EdgeKey, float] = {}
    for edge in graph.edges:
        if edge.capacity is None:
            raise GraphError(f"edge {edge.source!r}→{edge.target!r} has no capacity",
                             witness=(edge.source, edge.target))
        capacity[(edge.source, edge.target)] = edge.capacity
    flow: dict[EdgeKey, float] = {k: 0.0 for k in capacity}

    def residual(u: str, v: str) -> float:
        return capacity.get((u, v), 0.0) - flow.get((u, v), 0.0) + flow.get((v, u), 0.0)

    def labels() -> dict[EdgeKey, str]:
        return {k: f"{flow[k]:g}/{capacity[k]:g}" for k in capacity}

    value = 0.0
    steps = [Step("Zero flow", "Every edge carries 0 of its capacity",
                  {source: "source", sink: "sink"}, {}, {}, labels(),
                  panel=("flow value = 0",))]
    while True:
        parent: dict[str, str] = {}
        queue = [source]
        while queue and sink not in parent:
            u = queue.pop(0)
            for v in graph.ids:
                if v != source and v not in parent and residual(u, v) > 1e-9:
                    parent[v] = u
                    queue.append(v)
        if sink not in parent:
            break
        path = [sink]
        while path[-1] != source:
            path.append(parent[path[-1]])
        path.reverse()
        bottleneck = min(residual(u, v) for u, v in zip(path, path[1:]))
        for u, v in zip(path, path[1:]):
            if (u, v) in flow:
                pushed = min(bottleneck, capacity[(u, v)] - flow[(u, v)])
                flow[(u, v)] += pushed
                remainder = bottleneck - pushed
                if remainder > 1e-9:
                    flow[(v, u)] -= remainder
            else:
                flow[(v, u)] -= bottleneck
        value += bottleneck
        edges = {(u, v) if (u, v) in flow else (v, u): "path" for u, v in zip(path, path[1:])}
        steps.append(Step(f"Augment {bottleneck:g}",
                          f"Augmenting path {' → '.join(path)} with bottleneck {bottleneck:g}",
                          {source: "source", sink: "sink", **{v: "current" for v in path[1:-1]}},
                          edges, {}, labels(), panel=(f"flow value = {value:g}",)))
    reach = {source}
    queue = [source]
    while queue:
        u = queue.pop(0)
        for v in graph.ids:
            if v not in reach and residual(u, v) > 1e-9:
                reach.add(v)
                queue.append(v)
    cut = {k: "cut" for k in capacity if k[0] in reach and k[1] not in reach}
    cut_capacity = sum(capacity[k] for k in cut)
    nodes = {v: "visited" for v in reach}
    nodes.update({source: "source", sink: "sink"})
    steps.append(Step("Min cut", f"No augmenting path remains; the cut {{{', '.join(sorted(reach))}}} "
                      f"has capacity {cut_capacity:g} = flow value {value:g}",
                      nodes, cut, {}, labels(),
                      panel=(f"flow value = {value:g}", f"cut capacity = {cut_capacity:g}")))
    return steps


# ---------------------------------------------------- colouring and matching


def bipartition(graph: Graph) -> tuple[dict[str, int], list[str]]:
    """A two-colouring, or the odd cycle that prevents one.

    Returns ``(colours, [])`` when bipartite and ``(partial, cycle)`` otherwise,
    where ``cycle`` lists the vertices of an odd cycle in order.
    """
    colours: dict[str, int] = {}
    parent: dict[str, str | None] = {}
    for root in graph.ids:
        if root in colours:
            continue
        colours[root], parent[root] = 0, None
        queue = [root]
        while queue:
            u = queue.pop(0)
            for v in graph.neighbors(u):
                if v not in colours:
                    colours[v], parent[v] = 1 - colours[u], u
                    queue.append(v)
                elif colours[v] == colours[u]:
                    return colours, _odd_cycle(parent, u, v)
    return colours, []


def _odd_cycle(parent: dict[str, str | None], u: str, v: str) -> list[str]:
    def path_to_root(x: str) -> list[str]:
        out = [x]
        while parent.get(out[-1]) is not None:
            out.append(parent[out[-1]])  # type: ignore[arg-type]
        return out

    pu, pv = path_to_root(u), path_to_root(v)
    common = next(x for x in pu if x in pv)
    return pu[:pu.index(common) + 1] + list(reversed(pv[:pv.index(common)]))


def greedy_coloring_steps(graph: Graph, order: list[str] | None = None) -> list[Step]:
    sequence = [require_vertex(graph, v, "vertex_order entry") for v in (order or [])]
    sequence += [v for v in graph.ids if v not in sequence]
    colours: dict[str, int] = {}
    steps = [Step("Initialize", "No vertices coloured")]
    for vertex in sequence:
        used = {colours[n] for n in graph.neighbors(vertex) if n in colours}
        if not graph.directed:
            used |= {colours[e.source] for e in graph.edges
                     if e.target == vertex and e.source in colours}
        colours[vertex] = next(c for c in range(1, len(graph.ids) + 1) if c not in used)
        steps.append(Step(f"Color {vertex}",
                          f"Assign {vertex} the smallest available color: {colours[vertex]}",
                          {v: f"color-{c}" for v, c in colours.items()},
                          panel=(f"colours used: {max(colours.values())}",)))
    return steps


def matching_steps(graph: Graph, left: list[str]) -> tuple[list[Step], dict[str, str]]:
    """Kuhn's augmenting paths; returns the steps and the final matching
    keyed by the right-hand vertex."""
    left = [require_vertex(graph, v, "left vertex") for v in left]
    match_r: dict[str, str] = {}
    steps = [Step("Empty matching", "No edges matched", panel=("matching size = 0",))]

    def augment(u: str, seen: set[str]) -> bool:
        for v in graph.neighbors(u):
            if v in seen:
                continue
            seen.add(v)
            if v not in match_r or augment(match_r[v], seen):
                match_r[v] = u
                return True
        return False

    for u in left:
        if augment(u, set()):
            edges = {graph.key(l, r): "tree" for r, l in match_r.items()}
            nodes = {x: "visited" for pair in edges for x in pair}
            steps.append(Step(f"Augment from {u}", f"Augmenting path from {u} grows the matching",
                              nodes, edges, panel=(f"matching size = {len(match_r)}",)))
    return steps, match_r


def konig_cover(graph: Graph, left: list[str], match_r: dict[str, str]) -> list[str]:
    """A minimum vertex cover from a maximum matching (König's theorem).

    Alternating paths from the unmatched left vertices reach a set ``Z``; the
    cover is ``(L − Z) ∪ (R ∩ Z)``, and it has exactly the matching's size.
    """
    matched_left = set(match_r.values())
    z = {u for u in left if u not in matched_left}
    queue = list(z)
    while queue:
        u = queue.pop(0)
        for v in graph.neighbors(u):
            if v in z or match_r.get(v) == u:
                continue
            z.add(v)
            partner = match_r.get(v)
            if partner is not None and partner not in z:
                z.add(partner)
                queue.append(partner)
    cover = [u for u in left if u not in z] + [v for v in graph.ids if v not in left and v in z]
    return cover


def vertex_cover_steps(graph: Graph, left: list[str]) -> list[Step]:
    steps, match_r = matching_steps(graph, left)
    cover = konig_cover(graph, left, match_r)
    nodes = {v: "current" for v in cover}
    edges = {graph.key(l, r): "tree" for r, l in match_r.items()}
    steps.append(Step("Vertex cover",
                      f"König: cover {{{', '.join(cover)}}} of size {len(cover)} "
                      f"= matching size {len(match_r)}",
                      nodes, edges, panel=(f"matching size = {len(match_r)}",
                                           f"cover size = {len(cover)}")))
    return steps


# ---------------------------------------------------------------- Euler


def euler_steps(graph: Graph) -> list[Step]:
    """An Euler circuit (all degrees even) or trail (exactly two odd), by
    Hierholzer's algorithm; anything else is refused with the odd vertices."""
    if graph.directed:
        raise GraphError("Euler circuits here are for undirected graphs")
    odd = [v for v in graph.ids if graph.degree(v) % 2 == 1]
    if odd and len(odd) != 2:
        raise GraphError(f"{len(odd)} vertices have odd degree ({', '.join(odd)}); "
                         "an Euler trail needs 0 or 2", witness=odd)
    with_edges = [v for v in graph.ids if graph.degree(v) > 0]
    if not with_edges:
        raise GraphError("the graph has no edges")
    reach, stack = {with_edges[0]}, [with_edges[0]]
    while stack:
        u = stack.pop()
        for v in graph.neighbors(u):
            if v not in reach:
                reach.add(v)
                stack.append(v)
    if set(with_edges) - reach:
        raise GraphError("the edges do not lie in one connected component",
                         witness=sorted(set(with_edges) - reach))
    remaining = {graph.key(e.source, e.target) for e in graph.edges}
    start = odd[0] if odd else with_edges[0]
    stack, circuit = [start], []
    while stack:
        u = stack[-1]
        nxt = next((v for v in graph.neighbors(u) if graph.key(u, v) in remaining), None)
        if nxt is None:
            circuit.append(stack.pop())
        else:
            remaining.discard(graph.key(u, nxt))
            stack.append(nxt)
    circuit.reverse()
    kind = "trail" if odd else "circuit"
    steps = [Step("Start", f"Every vertex has even degree; start the circuit at {start}"
                  if not odd else f"{odd[0]} and {odd[1]} have odd degree; the trail runs "
                  f"from {odd[0]} to {odd[1]}", {start: "current"},
                  badges={v: f"deg {graph.degree(v)}" for v in graph.ids})]
    used: dict[EdgeKey, str] = {}
    for i, (u, v) in enumerate(zip(circuit, circuit[1:])):
        used[graph.key(u, v)] = "path"
        steps.append(Step(f"Edge {i + 1}", f"Traverse {u}–{v} (edge {i + 1} of {len(graph.edges)})",
                          {**{x: "visited" for x in circuit[:i + 2]}, v: "current"},
                          dict(used), {v: f"deg {graph.degree(v)}" for v in graph.ids},
                          panel=(f"{kind}: " + " → ".join(circuit[:i + 2]),)))
    return steps


# --------------------------------------------------------- connectivity / blocks


def connectivity_analysis(graph: Graph, start: Any = None) -> ConnectivityAnalysis:
    """Compute bridges, articulation vertices, and vertex-biconnected blocks.

    This is Tarjan's low-link DFS with an edge stack.  It deliberately accepts
    disconnected graphs: every component is analysed, and isolated vertices
    become singleton blocks so the block-cut forest loses nothing.  ``start``
    roots the first DFS tree; the remaining components follow in vertex order.
    """
    if graph.directed:
        raise GraphError("bridges and biconnected blocks here require an undirected graph")
    roots = list(graph.ids)
    if start is not None:
        first = require_vertex(graph, start, "start")
        roots.remove(first)
        roots.insert(0, first)
    discovery: dict[str, int] = {}
    low: dict[str, int] = {}
    parent: dict[str, str | None] = {v: None for v in graph.ids}
    bridges: list[EdgeKey] = []
    articulations: set[str] = set()
    blocks: list[tuple[str, ...]] = []
    edge_stack: list[EdgeKey] = []
    finish: list[str] = []
    clock = 0
    rank = {v: i for i, v in enumerate(graph.ids)}

    def block_through(stop: EdgeKey) -> None:
        vertices: set[str] = set()
        while edge_stack:
            edge = edge_stack.pop()
            vertices.update(edge)
            if edge == stop:
                break
        if vertices:
            blocks.append(tuple(sorted(vertices, key=rank.get)))

    def visit(u: str) -> None:
        nonlocal clock
        clock += 1
        discovery[u] = low[u] = clock
        children = 0
        for v in graph.neighbors(u):
            key = graph.key(u, v)
            if v not in discovery:
                parent[v] = u
                children += 1
                edge_stack.append(key)
                visit(v)
                low[u] = min(low[u], low[v])
                if low[v] > discovery[u]:
                    bridges.append(key)
                if low[v] >= discovery[u]:
                    if parent[u] is not None or children > 1:
                        articulations.add(u)
                    block_through(key)
            elif v != parent[u] and discovery[v] < discovery[u]:
                edge_stack.append(key)
                low[u] = min(low[u], discovery[v])
        finish.append(u)

    for root in roots:
        if root in discovery:
            continue
        before = len(discovery)
        visit(root)
        if len(discovery) == before + 1 and graph.degree(root) == 0:
            blocks.append((root,))
        if edge_stack:  # defensive: a component's final block
            vertices = {v for edge in edge_stack for v in edge}
            edge_stack.clear()
            blocks.append(tuple(sorted(vertices, key=rank.get)))

    return ConnectivityAnalysis(
        discovery=dict(discovery), low=dict(low), parent=dict(parent),
        bridges=tuple(bridges),
        articulations=tuple(v for v in graph.ids if v in articulations),
        blocks=tuple(blocks), finish_order=tuple(finish),
    )


def connectivity_steps(graph: Graph, start: Any = None) -> list[Step]:
    """A bounded low-link trace ending on the bridge/articulation certificate.

    A vertex is painted as a bridge endpoint or an articulation vertex on the
    step that proves it, not before: the finished child whose ``low`` value
    cannot climb above its parent's discovery time is the certificate, and
    the DFS root needs a second such child.
    """
    analysis = connectivity_analysis(graph, start)
    tree_edges = {graph.key(parent, child): "tree" for child, parent in analysis.parent.items()
                  if parent is not None}
    steps = [Step("Initialize", "Start a DFS; d is discovery time and low is the earliest reachable time",
                  badges={v: "d — · low —" for v in graph.ids},
                  panel=("bridges: —", "articulations: —"))]
    finished: set[str] = set()
    # A list, in the order the DFS proves them: a set would print the panel
    # in hash order and the same request would render differently per run.
    revealed_bridges: list[EdgeKey] = []
    revealed_cuts: set[str] = set()
    root_children: dict[str, int] = {}
    for vertex in analysis.finish_order:
        finished.add(vertex)
        parent = analysis.parent[vertex]
        if parent is not None:
            key = graph.key(parent, vertex)
            if key in analysis.bridges:
                revealed_bridges.append(key)
            if analysis.low[vertex] >= analysis.discovery[parent]:
                if analysis.parent[parent] is not None:
                    revealed_cuts.add(parent)
                else:
                    root_children[parent] = root_children.get(parent, 0) + 1
                    if root_children[parent] > 1:
                        revealed_cuts.add(parent)
        nodes = {v: "visited" for v in finished}
        nodes.update({v: "articulation" for v in revealed_cuts})
        nodes[vertex] = "current"
        edges = dict(tree_edges)
        edges.update({edge: "cut" for edge in revealed_bridges})
        steps.append(Step(
            f"Finish {vertex}",
            f"Finish {vertex}: d={analysis.discovery[vertex]}, low={analysis.low[vertex]}",
            nodes, edges,
            badges={v: f"d {analysis.discovery[v]} · low {analysis.low[v]}" for v in finished},
            panel=("bridges: " + (", ".join(f"{u}–{v}" for u, v in revealed_bridges) or "—"),
                   "articulations: " + (", ".join(v for v in graph.ids if v in revealed_cuts) or "—")),
            extras={"analysis": analysis},
        ))
    final_nodes = {v: ("articulation" if v in analysis.articulations else "visited")
                   for v in graph.ids}
    final_edges = {key: ("cut" if key in analysis.bridges else "tree")
                   for key in tree_edges}
    steps.append(Step(
        "Block structure", f"{len(analysis.blocks)} blocks; articulation vertices join the blocks",
        final_nodes, final_edges,
        badges={v: f"d {analysis.discovery[v]} · low {analysis.low[v]}" for v in graph.ids},
        panel=("bridges: " + (", ".join(f"{u}–{v}" for u, v in analysis.bridges) or "none"),
               "blocks: " + " | ".join("{" + ",".join(block) + "}" for block in analysis.blocks)),
        extras={"analysis": analysis},
    ))
    return steps


# ---------------------------------------------------------------- topic


#: The stock graph the animation lane draws when a request names none.
STOCK_GRAPH: dict[str, Any] = {
    # Listed in the order they sit on the circle: this order draws the stock
    # graph without a crossing, which A–F would not.
    "nodes": [{"id": v} for v in "ACEDFB"],
    "edges": [
        {"from": "A", "to": "B", "weight": 4}, {"from": "A", "to": "C", "weight": 2},
        {"from": "B", "to": "C", "weight": 5}, {"from": "B", "to": "D", "weight": 10},
        {"from": "C", "to": "E", "weight": 3}, {"from": "E", "to": "D", "weight": 4},
        {"from": "D", "to": "F", "weight": 11},
    ],
}

#: The stock flow network: directed, with capacities, source ``s``, sink ``t``.
STOCK_NETWORK: dict[str, Any] = {
    "directed": True,
    "nodes": [{"id": v} for v in ("s", "a", "b", "c", "d", "t")],
    "edges": [
        {"from": "s", "to": "a", "capacity": 10}, {"from": "s", "to": "c", "capacity": 10},
        {"from": "a", "to": "b", "capacity": 4}, {"from": "a", "to": "c", "capacity": 2},
        {"from": "a", "to": "d", "capacity": 8}, {"from": "b", "to": "t", "capacity": 10},
        {"from": "c", "to": "d", "capacity": 9}, {"from": "d", "to": "b", "capacity": 6},
        {"from": "d", "to": "t", "capacity": 10},
    ],
}

#: The algorithm each concept runs by default, and the ones it accepts.
CONCEPT_ALGORITHMS: dict[str, tuple[str, ...]] = {
    ConceptGraph.TRAVERSAL: ("bfs", "dfs"),
    ConceptGraph.SHORTEST_PATH: ("dijkstra", "bellman_ford"),
    ConceptGraph.SPANNING_TREE: ("kruskal", "prim"),
    ConceptGraph.MAX_FLOW: ("edmonds_karp",),
    ConceptGraph.CONNECTIVITY: ("low_link",),
}


def steps_for(concept: str, params: dict[str, Any]) -> list[Step]:
    """The computed states for a concept's parameters, or :class:`GraphError`.

    One entry point for the scene builder, the precondition check and the
    catalog, so they cannot disagree about what a request produces.
    """
    algorithms = CONCEPT_ALGORITHMS[concept]
    algorithm = str(params.get("algorithm", algorithms[0])).strip().lower()
    if algorithm not in algorithms:
        raise GraphError(f"{concept} runs {' or '.join(algorithms)}, not {algorithm!r}")
    stock = STOCK_NETWORK if concept == ConceptGraph.MAX_FLOW else STOCK_GRAPH
    graph = coerce_graph(params if params.get("nodes") is not None else {**stock, **params})
    start = params.get("start", graph.ids[0])
    if concept == ConceptGraph.TRAVERSAL:
        order = params.get("neighbor_order")
        return traversal_steps(graph, start, algorithm,
                               [str(v) for v in order] if isinstance(order, list) else None)
    if concept == ConceptGraph.SHORTEST_PATH:
        return (dijkstra_steps if algorithm == "dijkstra" else bellman_ford_steps)(graph, start)
    if concept == ConceptGraph.SPANNING_TREE:
        return kruskal_steps(graph) if algorithm == "kruskal" else prim_steps(graph, start)
    if concept == ConceptGraph.CONNECTIVITY:
        return connectivity_steps(graph, start)
    return max_flow_steps(graph, params.get("source", graph.ids[0]),
                          params.get("sink", graph.ids[-1]))


@topic(Topic.GRAPH, priority=20,
       keywords=("图论", "最短路", "生成树", "网络流", "最大流", "最小割",
                 "广度优先", "深度优先", "拓扑排序", "二分图",
                 "割点", "割边", "图中的桥", "图的桥", "找桥", "求桥", "双连通",
                 "bfs", "dfs", "dijkstra", "kruskal", "prim's", "bellman",
                 "graph theory", "spanning tree", "shortest path", "max flow",
                 "bridges", "cut vertex", "cut vertices", "articulation", "biconnected",
                 "block-cut", "low-link", "connectivity",
                 "min cut", "adjacency"))
class GraphTheory:
    """Five graph lessons, including connectivity, with every state computed."""

    concepts = ConceptGraph
