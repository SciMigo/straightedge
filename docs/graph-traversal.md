# BFS and DFS storyboards

`graph_traversal` computes a breadth-first or depth-first traversal and renders
the complete sequence as an `algorithm_trace`. Each panel shows the same graph
with the current vertex, discovered frontier, visited vertices, traversal-tree
edges, visit numbers, and the queue or stack state.

The template computes these states from `nodes` and `edges`; callers do not
write a sequence of highlights that could silently disagree with the graph.

## Breadth-first search

```python
from straightedge.diagrams import render_diagram

nodes = [{"id": vertex, "label": vertex} for vertex in "ABCDEFG"]
edges = [
    {"from": "A", "to": "B"},
    {"from": "A", "to": "C"},
    {"from": "B", "to": "D"},
    {"from": "B", "to": "E"},
    {"from": "C", "to": "F"},
    {"from": "C", "to": "G"},
]

bfs_svg = render_diagram({
    "type": "graph_traversal",
    "params": {
        "algorithm": "bfs",
        "nodes": nodes,
        "edges": edges,
        "start": "A",
        "neighbor_order": list("ABCDEFG"),
        "graph_layout": "hierarchical",
        "title": "Breadth-first search",
        "columns": 4,
    },
})
```

BFS removes from the front of its queue. A vertex is marked discovered when it
enters the queue, which prevents the same vertex being enqueued through two
different incoming edges. Each panel's queue is written front to back.

## Depth-first search

Use the same graph with `"algorithm": "dfs"`. DFS removes from the top of a
stack and pushes neighbors in reverse order, so the first neighbor in
`neighbor_order` is visited first. The displayed stack is written bottom to
top; its rightmost item is next.

This is the iterative, discovery-on-push form of DFS. Reversing the neighbor
push order makes the first declared neighbor the next one visited, while the
storyboard makes the otherwise implicit stack visible.

## Determinism and correctness

Traversal order is not unique until neighbor order is specified. By default,
neighbors retain their order of first appearance in `edges`. Supplying
`neighbor_order` gives a global tie-break order, making a lesson reproducible
even if edges are later regrouped.

The traversal follows only the component reachable from `start`. With
`directed: true`, edges are followed only from `from` to `to`; otherwise each
edge is traversable in both directions. Self-loops and repeated edges do not
cause repeated visits.

The figure is refused with structured findings when:

- the algorithm is not `bfs` or `dfs`;
- the start or an edge endpoint is unknown;
- vertex IDs or neighbor-order entries repeat;
- the neighbor order names an unknown vertex; or
- more than 11 reachable vertices would require more than the 12 readable
  panels supported by one `algorithm_trace` (initial state plus visits).

Use `straightedge.diagrams.registry.refusal_findings("graph_traversal", params)`
to inspect the reason before rendering. Divide a larger graph into conceptual
phases rather than shrinking the state labels until they are unreadable.

## Parameters

| Parameter | Meaning |
| --- | --- |
| `algorithm` | `bfs` (default) or `dfs` |
| `nodes`, `edges` | The same vertex and edge objects accepted by `graph` |
| `start` | Starting vertex ID; defaults to the first node |
| `neighbor_order` | Optional global tie-break order for adjacent vertices |
| `directed` | Follow only edge direction when true |
| `graph_layout` | Layout passed to each graph panel |
| `title` | Storyboard title |
| `columns` | Number of storyboard panels per row |
| `node_radius` | Vertex radius in each graph panel |
| `width`, `height` | Working area used to lay out each graph panel |
