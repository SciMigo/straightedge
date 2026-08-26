# Graph theory: computed states in video and in SVG

`Topic.GRAPH` is the animation lane's graph-theory topic, and
`straightedge/graphs.py` is the one place its algorithms live. The Manim
scenes, the `graph_traversal` storyboard and the `graph_algorithm` storyboards
and animated SVGs all read the same computed step sequence, so a video and a
handout of the same request cannot disagree about which vertex was settled
third — and neither can show a state the algorithm did not reach.

That is the property that makes these usable as **labs**: a student's own graph
goes in as parameters, every intermediate state comes out computed, and an
input that makes the requested claim false is refused with the witness — the
odd cycle, the negative cycle, the vertices of odd degree — rather than drawn.

## The five video concepts

| Concept | `algorithm` | What the frame shows |
|---|---|---|
| `graph/traversal` | `bfs` (default), `dfs` | current vertex, frontier, visit numbers, tree edges; the queue or the recursion stack in the panel |
| `graph/shortest_path` | `dijkstra` (default), `bellman_ford` | tentative distances under every vertex and in a table; settled vertices; predecessor edges |
| `graph/spanning_tree` | `kruskal` (default), `prim` | accepted edges in the tree colour, **rejected edges dashed** (Kruskal), candidate edges (Prim); running weight |
| `graph/max_flow` | `edmonds_karp` | `flow/capacity` on every edge, each augmenting path, and the min cut the residual graph certifies |
| `graph/connectivity` | `low_link` | DFS discovery and low-link values, bridges, articulation vertices, and the resulting biconnected blocks |

Every concept is reachable by name, with a graph of your own:

```bash
straightedge render --template graph/shortest_path \
  --params '{"algorithm": "dijkstra", "start": "A",
             "nodes": [{"id": "A"}, {"id": "B"}, {"id": "C"}, {"id": "D"}],
             "edges": [{"from": "A", "to": "B", "weight": 2},
                       {"from": "A", "to": "C", "weight": 5},
                       {"from": "B", "to": "C", "weight": 1},
                       {"from": "B", "to": "D", "weight": 4},
                       {"from": "C", "to": "D", "weight": 1}]}'
```

and by prompt (`用 Dijkstra 算法求最短路`, `画网络流的最大流和最小割`, `用 DFS
遍历图`, `找出图中的桥和割点`), which draws the stock six-vertex graph or the stock
flow network.

### Parameters

| Name | Meaning |
|---|---|
| `nodes` | `[{"id", "label"?, "x"?, "y"?}]` — positions as fractions of the canvas, honoured when every vertex has one |
| `edges` | `[{"from", "to", "weight"?, "capacity"?}]` |
| `directed` | default `false`; a flow network must be directed |
| `algorithm` | one of the concept's algorithms above |
| `start` | traversal, Dijkstra, Bellman–Ford, Prim; default: the first vertex |
| `source`, `sink` | max flow; default: first and last vertex |
| `neighbor_order` | the tie-break a lecture writes on the board, so a traversal is reproducible |
| `layout` | `auto` (circle; left-to-right for a directed graph), `hierarchical` |
| `title` | overrides the default title |

### What is refused before a render

`preconditions.validate` runs the same algorithm the scene draws from, so a
plan that would not draw is reported with the reason:

- an edge to a vertex that does not exist, a loop, a repeated edge;
- a negative weight under Dijkstra (use `bellman_ford`), a **negative cycle**
  under Bellman–Ford, named vertex by vertex;
- a directed graph under Kruskal or Prim, an undirected one under max flow;
- a source equal to the sink, an edge without a capacity;
- more than 8 vertices, or an algorithm that takes more than 17 steps — one
  narration beat per step is the video's whole structure, and past that it is
  a log, not a lesson.

### Narration beats

The scene is emitted unrolled: beat `b01` draws the graph, and every step after
it is one `_beat` call, so `grep -o '_beat(self, "b[0-9]*"' scene.py` reads the
keys off the file as `docs/narration-timing.md` describes. The number of beats
is `1 + steps`, which depends on the input; the caption of each step is the
sentence the narration should say over it.

## The SVG lane: every algorithm

`graph_algorithm` (storyboard with `animate: false`, animated SVG by default)
accepts everything the video does and more:

| `algorithm` | Needs | Refuses with |
|---|---|---|
| `dijkstra` | weights ≥ 0, `start` | a negative weight |
| `bellman_ford` | weights, `start` | the negative cycle |
| `kruskal` | undirected, weights | — (rejected edges are drawn dashed) |
| `prim` | undirected, weights, `start` | — |
| `topological_sort` | directed; `tie_break` is `"fifo"` or `"min"` | the cycle, or an unknown tie-break policy |
| `scc` | directed | — (components are coloured, finish times badged) |
| `max_flow` | directed, capacities, `source`, `sink` | source = sink, an uncapacitated edge |
| `greedy_coloring` | optional `vertex_order` | — |
| `bipartite_matching` | `partitions.left/right` | an edge inside one side |
| `vertex_cover` | `partitions.left/right` | — (König's cover from the maximum matching) |
| `euler` | undirected, connected edges | the odd-degree vertices, when there are not 0 or 2 |
| `low_link` | undirected | — (bridges, articulation vertices and blocks are computed together) |
| `prufer_encode` | a tree; optional `expect` | a cycle, disconnected components, or first mismatching code position |
| `prufer_decode` | `code` on vertices `1..len(code)+2` | the first code entry outside that range |
| `tree_center` | a tree; optional `show_eccentricities` | a cycle or disconnected components |
| `ear_decomposition` | a 2-connected graph; optional `start_cycle` | an articulation vertex or disconnected components |
| `stable_matching` | complete `proposers` / `receivers` preference objects; optional `check` | a malformed preference list or the first blocking pair |
| `hamiltonian_search` | `start`, optional `max_frames` and `expect` | a false expected cycle/non-cycle claim, with the cycle or exhausted-state count |
| `edge_coloring` | optional authored `classes` and `expect` | adjacent same-class edges, omitted edges, or an impossible expectation below Δ |
| `degeneracy_ordering` | an undirected graph | the shared 11-vertex trace cap |

A storyboard holds 12 panels and an animation 24 frames; a longer trace is
refused as unreadable rather than truncated.

`havel_hakimi` is a separate array-first storyboard. Pass `sequence` and it
sorts and reduces the degrees one panel at a time; `realize: true` appends the
computed graph as the recursive reductions unwind. It refuses an odd sum, a
degree at least `n`, or the first negative reduction and includes that failing
sequence as the witness.

`floyd_warshall` is a table-first storyboard: it emits the initial distance
matrix and one `dp_table` after each permitted intermediate vertex, highlighting
exactly the entries that improved. A negative diagonal refuses the figure with
the responsible vertex and reconstructed negative cycle. The graph/table
side-by-side composition remains part of the separately tracked composite-panel
work.

`mycielski` accepts an undirected base graph and constructs all three layers of
`M(G)` itself. The coloring frames are computed, as are the exact chromatic
numbers for the small accepted graphs and the triangle-free check. Since the
output must fit the figure lane, `2|V(G)|+1` may not exceed 11; in particular,
`M(C₅)` is the 11-vertex, 20-edge Grötzsch graph with chromatic number four.

## Building a lab on this

The pattern the `examples/` directory argues for applies: **compute, assert,
then draw.** A lab hands the student's graph to the algorithm, checks the
claim the exercise is about (the cut equals the flow; the cover has the
matching's size; Prim and Kruskal agree), and only then renders — so a wrong
answer fails before it becomes a convincing picture. The `GraphError` a
refusal raises carries `.witness`, which is the structure to show the student:

```python
from straightedge.graphs import GraphError, coerce_graph, topological_sort_steps

try:
    steps = topological_sort_steps(coerce_graph(student_graph))
except GraphError as refused:
    print(refused)           # "the graph has a cycle ...: A → B → C → A"
    print(refused.witness)   # ['A', 'B', 'C']
```
