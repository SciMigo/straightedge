# Graph-theory figures

The `graph` figure template draws ordinary, directed, weighted, and bipartite
graphs as dependency-free SVG. It is general enough for a sequence of lessons:
the same vertex IDs can persist while `highlights`, `path`, distance labels, or
degree labels change from one figure to the next.

## A checked bipartite graph

```python
from straightedge.diagrams import render_diagram

svg = render_diagram({
    "type": "graph",
    "params": {
        "nodes": [
            {"id": "u1", "label": "u₁"},
            {"id": "u2", "label": "u₂"},
            {"id": "v1", "label": "v₁"},
            {"id": "v2", "label": "v₂"},
            {"id": "v3", "label": "v₃"},
        ],
        "edges": [
            {"from": "u1", "to": "v1"},
            {"from": "u1", "to": "v2"},
            {"from": "u2", "to": "v2"},
            {"from": "u2", "to": "v3"},
        ],
        "layout": "bipartite",
        "partitions": {
            "left": ["u1", "u2"],
            "right": ["v1", "v2", "v3"],
        },
        "partition_labels": {"left": "U", "right": "V"},
        "show_degrees": True,
        "caption": "A bipartite graph G = (U ∪ V, E)",
    },
})
```

`partitions` is optional. When it is omitted, the template deterministically
two-colours every connected component. When it is supplied, the template
checks that every vertex occurs exactly once and every edge crosses between the
two sets. A self-loop, odd cycle, unknown endpoint, or edge inside one declared
set is refused rather than arranged into a convincing but false bipartite
figure. Call `straightedge.diagrams.registry.refusal_findings("graph", params)`
to obtain the structured reason.

## Common parameters

| Parameter | Meaning |
| --- | --- |
| `nodes` | Array of `{id, label}` objects; custom layouts also accept `x`, `y` |
| `edges` | Array of `{from, to}` objects, optionally with `weight` |
| `directed` | Add arrowheads and compute separate in/out degrees |
| `weighted` | Reserve labels for edge weights; an explicit weight is always shown |
| `layout` | `circular`, `grid`, `hierarchical`, `custom`, or checked `bipartite` |
| `partitions` | Optional `{left: [...], right: [...]}` vertex IDs for bipartite layout |
| `partition_labels` | Optional labels above the two bipartite columns |
| `show_degrees` | Compute degree labels; an undirected loop contributes two |
| `highlights` | `{nodes: {id: state}, edges: [[from, to], ...]}` |
| `path` | Ordered vertex IDs whose connecting edges are emphasized |
| `distance_labels` | Mapping from vertex ID to an algorithm-specific value |

For a custom layout, coordinates between `0` and `1` are scaled into the
drawing area. Other numbers are treated as SVG coordinates. Edges are trimmed
at vertex boundaries, self-loops are visible arcs, reciprocal directed edges
bow apart, and long edges bow around unrelated vertices.

## Traversal or shortest-path frames

```python
params = {
    "nodes": [{"id": x, "label": x} for x in "ABCDE"],
    "edges": [
        {"from": "A", "to": "B", "weight": 2},
        {"from": "A", "to": "C", "weight": 5},
        {"from": "B", "to": "D", "weight": 1},
        {"from": "D", "to": "E", "weight": 3},
    ],
    "weighted": True,
    "layout": "hierarchical",
    "highlights": {"nodes": {"D": "current"}},
    "path": ["A", "B", "D"],
    "distance_labels": {"A": 0, "B": 2, "C": 5, "D": 3},
}
```

Change only the highlights, path, and distance labels between frames. Keeping
the input order stable keeps the layout stable, which prevents an algorithm
animation from appearing to move the graph while it explores it.
