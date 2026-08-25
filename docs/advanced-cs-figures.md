# Checked CS figures and dependency-free animation

Straightedge's SVG lane includes checked templates for graph traversal, search
trees, planar embeddings, and network flow. These figures require only the
Python standard library. They may also be combined into standalone animated
SVGs; Manim and ffmpeg are not involved.

## Computed graph algorithms

`graph_algorithm` accepts `dijkstra`, `kruskal`, `greedy_coloring`, or
`bipartite_matching`. It computes the states from the graph, so a lecture agent
does not author plausible-looking intermediate answers. Set `animate: true` for
native animated SVG or `false` for an `algorithm_trace` storyboard.

```python
svg = render_diagram({
    "type": "graph_algorithm",
    "params": {
        "algorithm": "dijkstra",
        "nodes": [{"id": x} for x in "ABCD"],
        "edges": [
            {"from": "A", "to": "B", "weight": 2},
            {"from": "A", "to": "C", "weight": 5},
            {"from": "B", "to": "C", "weight": 1},
            {"from": "C", "to": "D", "weight": 1},
        ],
        "start": "A",
        "graph_layout": "hierarchical",
        "animate": True,
    },
})
```

Dijkstra refuses negative or nonnumeric weights. Kruskal requires an
undirected weighted graph. Greedy colouring records its deterministic vertex
order and exposes the selected colours. Bipartite matching validates the
partition and computes augmenting states.

## Animate any figure sequence

`animated_trace` accepts frames containing the same `{type, params}` envelope
as `render_diagram`. It embeds each child SVG and cross-fades between them with
SVG's native SMIL timing.

```python
from straightedge.diagrams import render_diagram

svg = render_diagram({
    "type": "animated_trace",
    "params": {
        "title": "Traversal states",
        "duration_s": 1.2,       # per frame
        "loop": True,
        "frames": [
            {
                "label": "visit A",
                "visual": {"type": "array_state", "params": {
                    "values": ["A", "B"], "highlights": {"0": "current"},
                }},
            },
            {
                "label": "visit B",
                "visual": {"type": "array_state", "params": {
                    "values": ["A", "B"],
                    "highlights": {"0": "visited", "1": "current"},
                }},
            },
        ],
    },
})
```

Every child must be a registered, nonblank figure and must pass its own refusal
checks. A false planar claim or invalid red-black tree therefore cannot be
smuggled into an animation. `loop: false` plays once and freezes on the final
frame. Reduced-motion clients see the first frame without cross-fading.
Frames are drawn at their own size and centred on a card large enough for
the largest of them, so a figure that grows between states keeps one scale
rather than shrinking from frame to frame.

## BST, AVL, and red-black trees

`search_tree` either constructs a tree from insertion order or verifies an
explicit tree.

```python
avl = render_diagram({
    "type": "search_tree",
    "params": {
        "kind": "avl",
        "values": [30, 20, 10, 25, 28],
        "show_balance": True,
        "animate": True,
        "duration_s": 1.0,
    },
})

red_black = render_diagram({
    "type": "search_tree",
    "params": {
        "kind": "red_black",
        "values": [7, 3, 18, 10, 22, 8, 11, 26],
    },
})
```

Construction uses ordinary BST insertion, AVL rotations, or left-leaning
red-black insertion. Duplicate or incomparable keys are refused. Explicit
trees are checked for strict BST order; AVL trees additionally require every
balance factor to be in `[-1, 1]`; red-black trees require a black root, valid
colors, no red parent with a red child, and equal black-height on every path.

The permissive `binary_tree` template remains available for trees that are not
search trees. It now understands optional `color: "red" | "black"` on nodes,
but it deliberately makes no search-tree claim.

## Planar embeddings

`planar_graph` checks a supplied straight-line embedding. Coordinates are
required because “this graph is planar” and “these drawn edges do not cross”
are different claims.

```python
svg = render_diagram({
    "type": "planar_graph",
    "params": {
        "nodes": [
            {"id": "A", "x": 0.1, "y": 0.1},
            {"id": "B", "x": 0.9, "y": 0.1},
            {"id": "C", "x": 0.5, "y": 0.9},
            {"id": "D", "x": 0.5, "y": 0.42},
        ],
        "edges": [
            {"from": "A", "to": "B"}, {"from": "B", "to": "C"},
            {"from": "C", "to": "A"}, {"from": "A", "to": "D"},
            {"from": "B", "to": "D"}, {"from": "C", "to": "D"},
        ],
        "faces": 4,
    },
})
```

The checked surface is a simple straight-line graph: loops, parallel edges,
coincident vertices, unknown endpoints, and crossings are refused. If `faces`
is supplied, the component-aware Euler identity `V - E + F = 1 + C` is also
verified. This validates an embedding; it is not a general abstract planarity
solver that searches for a different embedding.

## Network flow

`network_flow` computes the flow value and checks bounds and conservation
before drawing `flow/capacity` labels.

```python
svg = render_diagram({
    "type": "network_flow",
    "params": {
        "nodes": [{"id": x} for x in ("s", "a", "b", "t")],
        "edges": [
            {"from": "s", "to": "a", "capacity": 3, "flow": 2},
            {"from": "s", "to": "b", "capacity": 2, "flow": 2},
            {"from": "a", "to": "t", "capacity": 2, "flow": 2},
            {"from": "b", "to": "t", "capacity": 2, "flow": 2},
        ],
        "source": "s",
        "sink": "t",
        "cut": ["s", "a", "b"],
        "claim_max_flow": True,
    },
})
```

The checker enforces `0 <= flow <= capacity`, conservation at nonterminals,
equal source and sink values, optional claimed value, valid cuts, and positive
residual capacity along an optional `augmenting_path`. A `claim_max_flow`
requires a cut whose capacity equals the computed flow value—the max-flow
min-cut certificate. `show_residual: true` replaces flow/capacity labels with
positive forward and reverse residual capacities.

To animate Ford–Fulkerson or Edmonds–Karp, render one checked `network_flow`
frame after each augmentation inside `animated_trace`. The animation wrapper
rechecks every state, so an intermediate conservation error blocks the result.
