# Graph-theory course: the algorithms and figures still missing

A work list for the templates a 34-module graph-theory course
(`../graph-theory`, 24 core modules + 10 interview modules) asks for and
Straightedge 0.7.0 does not yet draw. Each item is scoped to be one PR in the
shape of #28: a computed step trace, a `graph_algorithm` (or new) template
that refuses a false request with the witness, an example, a legibility-corpus
entry, and tests. The course's own `TEMPLATE GAP:` markers, in each module's
`topic.md` under `## Programming and Visualization`, carry the exact JSON the
author wanted to send; read them before designing a parameter surface.

The larger picture — what the course spec promises that the library does not
do, and the structural features (composite panels, richer state vocabulary,
multigraphs) that several items below depend on — is in the gap map that
accompanied the 0.7.0 review. This document is the algorithm half of it.

## How an algorithm is added (the #28 pattern)

1. **Compute.** A `<name>_steps(graph, ...) -> list[Step]` in
   `straightedge/graphs.py`, next to `connectivity_steps`. Every state the
   figure shows must come from this function; a false request raises
   `GraphError(message, witness=...)` naming the structure that proves it.
   Iterate lists, not sets, wherever order reaches a caption — the output is
   byte-compared across `PYTHONHASHSEED`s (`tests/test_determinism.py`).
2. **Expose in the figure lane.** Add the name to `ALGORITHMS` in
   `straightedge/diagrams/templates/graph_algorithm.py` and route it in
   `compute_steps`; `frames_from_steps` already turns node roles
   (`current`, `frontier`, `visited`, `articulation`, `color-N`) and edge roles
   (`tree`, `path`, `cut`, `rejected`) into `graph` calls. Add the role → CSS
   mapping in `templates/graph.py` if a new role is needed, then regenerate
   the checked site SVGs (`python tools/build_site_figures.py`) because the
   stylesheet is shared.
3. **Optionally expose in the animation lane.** A `ConceptGraph` member,
   `CONCEPT_ALGORITHMS`, `steps_for`, the planner keyword row in
   `straightedge/planner.py::_GRAPH_CONCEPT_WORDS` (specific words only —
   bare `桥`/`bridge` hijacked unrelated requests once), the precondition
   registration in `straightedge/preconditions.py`, a `CANONICAL_PROMPTS`
   entry, and a row in the `tests/test_smoke_render.py` parametrisation.
   Manim frames hold at most 8 vertices and 17 beats (`graph_scene.py`).
4. **Publish.** `straightedge/examples.py::EXAMPLES` (one working call),
   `tests/test_figure_legibility.py::CORPUS` (the suite fails on a registered
   template without one), a paragraph in `docs/graph-animations.md` or
   `docs/graph-connectivity-structures.md`, and a CHANGELOG bullet.
5. **Test the refusal, not only the drawing.** One test that the algorithm
   draws the course's instance, one that a false request is refused with the
   expected witness, and — if the trace reveals a conclusion mid-way — one
   that the reveal happens on the step that proves it and not before
   (#28's articulation-vertex bug).

Limits to respect: `graph_algorithm` accepts ≤ 11 vertices, 12 storyboard
panels, 24 animated frames; `algorithm_trace` 12 panels; `animated_trace` 24
frames. A course instance that does not fit should be refused with the count,
never drawn small.

## The course's named instances

Every module draws and computes on the same few graphs so figures and code
agree. Until a `named_graph()` helper exists, each item below says which
instance its tests should use; the exact vertex labels are in
`../graph-theory/reference/unit*.md`. The recurring ones: the Petersen graph
(2-subset labels `"12".."45"` in units 1 and 5; integers 0–9 with outer
5-cycle + spokes + pentagram in units 4, 6 and 7), `Q₃` (binary strings),
`K₃,₃` (`a0..a2 / b0..b2` in unit 6, `0..5` elsewhere), `K₄`, `K₅`, `K₆`,
`C₅`, the prism `C₃□K₂`, the bowtie, `tail_graph()`, `W₅`, the octahedron
`K₂,₂,₂`, the Grötzsch graph, and the Turán graphs `T₆,₂`, `T₆,₃`, `T₇,₃`.

## Work list

Ordered by how many modules each unblocks, then by syllabus order. "Modules"
are directory prefixes under `../graph-theory/modules/`; `iNN` is the
interview track.

- [x] 1 `prufer_encode` / `prufer_decode`
- [x] 2 `havel_hakimi`
- [x] 3 `tree_center`
- [x] 4 `ear_decomposition`
- [x] 5 `stable_matching`
- [x] 6 `hamiltonian_search`
- [ ] 7 `turan(n, r)`
- [x] 8 `floyd_warshall`
- [x] 9 `mycielski`
- [x] 10 `edge_coloring`
- [ ] 11 `degeneracy_ordering`
- [ ] 12 `topological_sort` tie-break
- [ ] 13 `scc` finish-order and condensation
- [ ] 14 `bipartite_matching` Hall violator

### 1. ✅ `prufer_encode` / `prufer_decode` — module 08

- **Shows.** Encoding: each step deletes the smallest leaf, appends its
  neighbour to the code; the tree with the deleted vertex as `rejected`, the
  current leaf as `current`, and the code so far in the panel. Decoding: the
  tree grows one edge per step from the code; panel shows the remaining code
  with a pointer.
- **Inputs.** `nodes`, `edges` (a tree) for encoding; `code: [...]` for
  decoding (the vertex set is `1..len(code)+2`).
- **Refuse.** Not a tree (cycle or disconnected — witness the cycle or the
  two components); a code entry outside `1..n`; `expect` code that does not
  match the computed one (witness the first differing position).
- **Instance.** Tree `H` on `[6]`, edges 13, 23, 34, 45, 46 → code `(3,3,4,4)`.
- **Note.** The course wants the tree and the code side by side per step;
  until composite panels exist, put the code in the caption/panel line as
  `dijkstra` does with distances.

### 2. ✅ `havel_hakimi` — module 05

- **Shows.** One panel per reduction: the sequence as an `array_state` with
  the removed entry highlighted and the next `d` entries decremented, then
  the joining step that realises the graph (edges added as `tree`).
- **Inputs.** `sequence: [int]`; optional `realize: true` to also draw the
  graph built on the way back up.
- **Refuse.** Odd degree sum; a negative entry mid-reduction (witness the
  panel `(1, −1)` the course uses as its failing example `(3,3,3,1)`); an
  entry ≥ n.
- **Instance.** `(3,3,2,2,2)` → `(2,2,1,1)` → `(1,1,0)` → `(0,0)`.
- **Note.** This is an `array_state` storyboard first and a graph second;
  it may fit better as its own template than as a `graph_algorithm` value.

### 3. ✅ `tree_center` (leaf stripping) — module 07

- **Shows.** Jordan's theorem: strip all leaves each round (as `rejected`),
  until one or two vertices remain (`target`); panel carries eccentricity
  per remaining vertex if `show_eccentricities`.
- **Inputs.** `nodes`, `edges` (a tree).
- **Refuse.** Not a tree.
- **Instance.** Tree `T` on 1..8 (12, 23, 34, 45, 56, 37, 48) → centre {3, 4},
  radius 3, diameter 5.
- **Also wanted by 07.** A `graph` param for per-vertex annotations
  (eccentricity, later disc/low and DP values) so labels stop being abused
  as `"3 (ε=3)"`.

### 4. ✅ `ear_decomposition` — module 15

- **Shows.** One ear per panel: `P₀` a cycle, each `Pᵢ` a path whose ends
  lie on earlier ears; ears numbered and each drawn in its own colour.
- **Inputs.** `nodes`, `edges` (2-connected); optional `start_cycle`.
- **Refuse.** Not 2-connected — witness the articulation vertex, which
  `connectivity_analysis` already computes.
- **Instance.** Prism: `P₀ = 2,1,0,2`; `P₁ = 0,3,4,1`; `P₂ = 2,5,4`; `P₃ = 3,5`.
- **Needs.** N distinguishable edge colours (`color-N` edge roles, like the
  existing `color-N` node roles) — this also unblocks 16's three disjoint
  paths and 22's edge colourings.

### 5. ✅ `stable_matching` (Gale–Shapley) — module 12

- **Shows.** One panel per proposal round: proposers, receivers, the held
  offer per receiver, the rejected proposal as `rejected`; final matching
  as `path` edges; optional blocking-pair check on a supplied matching.
- **Inputs.** `proposers: {A: [prefs]}`, `receivers: {1: [prefs]}`; optional
  `check: {A: "1", ...}` to verify stability of an authored matching.
- **Refuse.** Preference lists that are not permutations of the other side;
  a `check` matching with a blocking pair (witness the pair).
- **Instance.** Instance `I` (A–D / 1–4): GS output `{A1, B4, C2, D3}` after
  10 proposals; the unstable `{A4, B3, C1, D2}` has blocking pair `(D, 3)`.

### 6. ✅ `hamiltonian_search` (backtracking frames) — modules 23, 24

- **Shows.** The partial path as `visited` with the tip `current`, the
  pruned neighbour as `rejected`, and either the cycle found (`path`) or the
  exhausted search; bounded to the frame limit with the count reported.
- **Inputs.** `nodes`, `edges`, `start`, `max_frames`; optional
  `expect: "cycle" | "none"`.
- **Refuse.** `expect: "cycle"` on a graph with none (witness: the
  exhausted search, or Dirac/Ore-style certificate when cheap — e.g.
  `c(G − S) > |S|` with the set `S`); over the vertex cap.
- **Instances.** Octahedron (search state), Petersen (Hamiltonian path
  `0,1,2,3,4,9,6,8,5,7` but no cycle), dodecahedron (Icosian puzzle — 20
  vertices, so static `graph` + `path` only, not this template).
- **Note.** Exercise 7.5 in the course emits frames "ready for
  `animated_trace` once a search template lands"; match that shape.

### 7. `turan(n, r)` builder — module 24

- **Shows.** The complete `r`-partite graph on `n` vertices with parts as
  equal as possible; parts as N-way partitions; edge count in the caption.
- **Inputs.** `n`, `r`; optional `highlight_clique_free: true`.
- **Refuse.** `r > n`, `r < 1`.
- **Instances.** `T₆,₂ = K₃,₃` (9 edges), `T₆,₃ = K₂,₂,₂` (12), `T₇,₃` (16).
- **Needs.** `partitions` with more than two parts in the `graph` template
  (today exactly `left`/`right`). Also wanted by i09 (three SCCs) and 20
  (three colour classes).

### 8. ✅ `floyd_warshall` as a `dp_table` sequence — module i07

- **Shows.** One `dp_table` per intermediate vertex `k`, changed entries
  highlighted, `∞` rendered; the digraph beside it.
- **Inputs.** `nodes`, `edges` (directed, weighted).
- **Refuse.** A negative cycle (witness: the vertex whose diagonal goes
  negative and the cycle).
- **Instance.** `F₄` in `i07/topic.md`.
- **Note.** `bellman_ford` should also mark round boundaries and show the
  edge order (i07's other gap); the negative cycle wants an edge role
  `cycle` for the highlight.

### 9. ✅ `mycielski` construction — module 21

- **Shows.** Three layers: the original ring `u₀..u₄`, the shadow ring
  `v₀..v₄` joined to each `uᵢ`'s neighbours, the hub `w` joined to all `vᵢ`;
  then a greedy colouring showing χ rises by one while triangle-free.
- **Inputs.** `nodes`, `edges` of the base graph; layout is fixed by the
  template.
- **Refuse.** Base graph over the cap (Mycielski triples the vertex count
  plus one, so base ≤ 3 for the 11-vertex figure cap; document this).
- **Instance.** `M(C₅)` = Grötzsch graph, 11 vertices, 20 edges, χ = 4.

### 10. ✅ `edge_coloring` — module 22

- **Shows.** A proper edge colouring, one colour class per `color-N` edge
  role with a legend; for bipartite graphs the König/Vizing alternating
  chain (Kempe swap) as a `path`.
- **Inputs.** `nodes`, `edges`; optional `classes: [[edge...]]` to verify an
  authored colouring; optional `expect: k`.
- **Refuse.** Two adjacent edges in one class (witness the shared vertex);
  `expect` below Δ.
- **Instances.** `K₆` round-robin (χ′ = 5), `K₄` (three perfect matchings),
  `C₅` (χ′ = 3), `K₃,₃` Kempe swap `a2, b0, a0, b2`, the bridged cubic graph
  `B` (class 2). The Shannon triangle needs multigraphs — out of scope here.
- **Needs.** `color-N` edge roles (see item 4).

### 11. `degeneracy_ordering` (smallest-last) — module 20

- **Shows.** One panel per deletion of a minimum-degree vertex (`rejected`),
  the degeneracy `d` in the panel, then the greedy colouring in reverse
  order using ≤ d + 1 colours.
- **Inputs.** `nodes`, `edges`.
- **Refuse.** Over the cap.
- **Instance.** Petersen, degeneracy 3, 3-colourable via classes
  `{0,2,6}, {1,3,5,9}, {4,7,8}`.
- **Note.** `greedy_coloring` with an explicit `vertex_order` already covers
  the Brooks ordering slide (21); this template computes the order.

### 12. `topological_sort` `tie_break` — module i03

- **Change.** Accept `tie_break: "min" | "fifo"` so the storyboard's peel
  order matches the lecture's stated order; refuse an unknown value.
- **Instance.** `D₈` in `i03/topic.md`.
- **Also wanted.** A three-colour (white/gray/black) DFS storyboard with a
  stack panel for cycle detection — a `graph_traversal` option rather than a
  new algorithm.

### 13. `scc` names its algorithm; finish-order panel — module i09

- **Change.** State in the summary that `scc` is Kosaraju; emit the first
  pass's finish order as an `array_state`-style panel line and show the
  second pass's DFS trees emerging one component at a time; add the
  condensation DAG as a final frame (hierarchical layout).
- **Instance.** `S₈` (A..H, 10 arcs) → components `ABC`, `DEF`, `GH`.

### 14. `bipartite_matching` final panel: the Hall violator — modules 10, 11, i10

- **Change.** When the last augmentation search fails, highlight the
  alternating reach `Z` from the unsaturated vertex, `S = X ∩ Z` and
  `N(S) = Y ∩ Z`, and state `|N(S)| < |S|` in the panel; this is the same
  data `vertex_cover` uses for the König cover, so the two should share it.
- **Instances.** `H` (a..e / 1..5) in module 11 — violator
  `S = {a,b,c,d}`, `N(S) = {1,2,3}`; `A₅` in i10 — `S = {4,5}`, `N(S) = {d}`.

## Blocked on structural work (not algorithms)

These course requests cannot be met by adding an algorithm; they are listed
so nobody scopes them into one of the items above by accident.

- **Multigraphs and self-loops** in `coerce_graph` (Königsberg in 01 and 04,
  de Bruijn `B(2,3)` in 06 — that module's one animation — and the Shannon
  triangle in 22).
- **Manim `MAX_VERTICES = 8`** blocks 03 (BFS on Petersen) and i08 (DFS on
  `B₉`); raising it to 10 with the panel narrowed is a scene-layout change.
- **Composite panel** (graph beside a heap / stack / parent array / code,
  both updating): i03, i05, i06, i08, 08, 12. `disjoint_set` and
  `priority_queue` exist as standalone figures; the lesson wants them next to
  Dijkstra and Kruskal.
- **N-way `partitions` and set shading** (S and N(S), components outlined,
  G − S with odd components counted): 11, 13, 14, i09, 24.
- **State vocabulary**: node `deleted`/hollow, per-node annotations,
  `color-N` edge roles, dashed back edges, `cycle`; distinct `tree` vs `path`
  styling in the SVG lane.
- **Planar**: list-valued `faces` (the course sends `faces: [[...]]`, the
  template takes an integer), face shading, dual overlay, contraction: 18, 19.
- **Grid and implicit graphs**: `grid_traversal` for i02/i06/i04 and a
  successor-function graph for i01.
- **`comparison` with figure children** — the course uses it 12 times as
  "two figures side by side"; today it takes text bullets only.

## Definition of done for one item

- `python -m pytest -q` green, including the determinism and legibility suites.
- The course's instance renders in both the storyboard and the animated
  form where the template has `motion: optional`.
- A false request from the course's own text (its "failing example") is
  refused with the witness named in the finding's `label`.
- `python tools/build_site_figures.py --check` still passes.
- The module's `TEMPLATE GAP:` line in `../graph-theory` can be deleted.
