# Graph connectivity and CS structure figures

These templates are the reusable visual building blocks for a graph-theory or
data-structures lab. They are pure standard-library SVG: no browser, Manim or
ffmpeg is needed. Each operation is computed before it is drawn, and a supplied
expected result is treated as an assertion rather than a caption.

## Low-link connectivity

`graph_algorithm` accepts `algorithm: "low_link"`; the animation lane exposes
the same computation as `graph/connectivity`. Both run a depth-first search and
derive discovery times, low-link values, bridges, articulation vertices and
vertex-biconnected blocks from the same step sequence.

```python
from straightedge.diagrams import render_diagram

graph = {
    "nodes": [{"id": v} for v in "ABCD"],
    "edges": [
        {"from": "A", "to": "B"}, {"from": "B", "to": "C"},
        {"from": "C", "to": "A"}, {"from": "C", "to": "D"},
    ],
}
svg = render_diagram({"type": "graph_algorithm", "params": {
    **graph, "algorithm": "low_link", "animate": True,
}})
```

The algorithm requires an undirected simple graph. A bridge is also emitted as
a two-vertex block, and an isolated vertex as a singleton block. `start` roots
the depth-first search (the first vertex by default); any other component is
visited afterwards in vertex order. A vertex is painted as an articulation
vertex on the step that proves it — the finished child whose low value cannot
climb above the parent's discovery time, or the root's second child — and a
bridge is drawn as a `cut` edge, thick and red, so it is told apart from the
tree edges around it in the SVG lane as well as in Manim.

## Block-cut forest

`block_cut_tree` accepts the ordinary `nodes`, `edges`, and optional `title`,
`caption`, `width`, and `height` fields. It does not accept authored blocks:
block membership and articulation incidence are derived from the graph. At
most eleven vertices are accepted — the `graph_algorithm` limit — and, unless
`height` is given, the figure grows with its rows so a long path does not
stack its blocks on top of each other.

```python
svg = render_diagram({"type": "block_cut_tree", "params": graph})
```

Block nodes are named `B1`, `B2`, ... and carry their vertex set as a nearby
label. Articulation nodes connect exactly the blocks that contain them.

## Disjoint-set union

`disjoint_set` computes union-by-rank and path compression. Set `animate` to
`false` for a printable storyboard; it defaults to an animated SVG.

```python
svg = render_diagram({"type": "disjoint_set", "params": {
    "elements": ["A", "B", "C", "D"],
    "operations": [
        {"type": "union", "a": "A", "b": "B"},
        {"type": "union", "a": "C", "b": "D"},
        {"type": "union", "a": "B", "b": "C"},
        {"type": "find", "element": "D", "expect": "A"},
    ],
}})
```

Unknown operands, repeated elements and a false `expect` value are refused.

## Min-priority queue

`priority_queue` uses a binary min-heap and supports `insert`, `decrease_key`,
and `pop_min`. Item ids are unique while present; priorities are finite
numbers. `pop_min.expect` turns the lecture's claimed answer into a check.

```python
svg = render_diagram({"type": "priority_queue", "params": {
    "items": [{"id": "A", "priority": 5}, {"id": "B", "priority": 2}],
    "operations": [
        {"type": "decrease_key", "id": "A", "priority": 1},
        {"type": "pop_min", "expect": "A"},
    ],
}})
```

The heap tree and its array order are shown together. Popping the last item
produces an explicit empty-queue frame instead of a blank child figure.

## Four equivalent graph representations

`graph_representation` derives an adjacency list, adjacency matrix and
incidence matrix beside the source graph. Directed incidence uses `-1` at an
edge's source and `+1` at its target; undirected incidence uses `1` at both
ends. Edge weights appear in the adjacency matrix when supplied.

```python
svg = render_diagram({"type": "graph_representation", "params": graph})
```

The four-panel layout is capped at six vertices and eight edges so its labels
remain useful in a lecture deck.
