# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project aims to
follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **A `graph` topic in the animation lane.** `graph/traversal` (BFS, DFS),
  `graph/shortest_path` (Dijkstra, Bellman–Ford), `graph/spanning_tree`
  (Kruskal, Prim) and `graph/max_flow` (Edmonds–Karp with its min cut) render
  as Manim videos from a graph passed in parameters, or from a stock graph
  by prompt. The algorithm runs at generation time in the new
  `straightedge/graphs.py`, one beat per computed step, and
  `preconditions.validate` refuses — with the witness — a negative weight
  under Dijkstra, a negative cycle, a source equal to the sink, or a graph
  too large for one frame. Documented in `docs/graph-animations.md`.

- **`graph_algorithm` covers most of a first graph-theory course.** Added
  `bellman_ford`, `prim`, `topological_sort`, `scc`, `max_flow`,
  `vertex_cover` (König) and `euler` to the existing four, all computed by the
  same module the video lane uses. Kruskal now draws the edges it rejects,
  dashed, and refusals name the negative cycle, the DAG's cycle or the
  odd-degree vertices that make the request false.

- **`graph_algorithm` computes checked teaching traces.** Dijkstra shortest
  paths, Kruskal minimum spanning forests, greedy vertex colouring, and
  augmenting-path bipartite matching now render as either printable
  storyboards or dependency-free animated SVG. The public catalogue also
  publishes each figure's motion capability and stronger template checks for
  hosted agents to discover.

- **Checked advanced-CS figures plus a dependency-free animation lane.**
  `animated_trace` cross-fades any sequence of registered SVG figures using
  native SVG timing and preserves every child's refusal checks. `search_tree`
  constructs or validates BST, AVL and red-black trees (insertion is the
  left-leaning variant, so a tree built here can differ in shape from one
  built by CLRS's procedure) and can animate an insertion sequence; `planar_graph` checks straight-line crossings and the
  component-aware Euler formula; `network_flow` checks capacity bounds, flow
  conservation, residual paths, cuts and max-flow/min-cut certificates.
  Documented together in `docs/advanced-cs-figures.md`.

- **The `graph` template is ready for graph-theory lessons.** A checked
  `bipartite` layout either infers a deterministic two-colouring or verifies
  declared left/right vertex sets; odd cycles, self-loops, unknown endpoints,
  incomplete partitions and within-set edges are refused with structured
  findings rather than drawn as a false bipartite graph. Optional partition
  headings and computed degree labels cover both undirected degree (loops count
  twice) and separate directed in/out degrees. Copyable examples and the full
  parameter contract live in `docs/graph-theory.md`.

- **`graph_traversal` computes BFS and DFS storyboards.** Given a graph, start
  vertex and optional neighbor order, it derives every state instead of asking
  an author to hand-write plausible highlights: the current vertex, discovered
  frontier, visit order, traversal-tree edges, and queue or stack appear on
  each panel. Directed reachability and BFS/DFS tie-breaking are explicit;
  invalid endpoints, starts and orders are refused, as are traces too large to
  keep readable. Documented in `docs/graph-traversal.md`.
- **`environment_diagram` can lay its frames out in a row.** `layout: "row"`
  places frames left to right with the parent arrows running back along the
  row. Three stacked frames are a tall, narrow figure that a 16:9 slide shows
  small; the same frames in a row fill the slide's width and keep their labels
  legible. The column layout stays the default and renders unchanged.

- **`algorithm_trace`: a checked multi-step storyboard for the CS figures.**
  One state is not an algorithm. The template composes the existing
  `array_state`, `stack`, `queue`, tree, graph and table renderers into an
  ordered grid of panels, and verifies the transition claimed between adjacent
  panels — an array swap, a stack push/pop, a queue enqueue/dequeue — against
  both the next panel's values and the `operation` the panel itself draws. A
  trace that asserts something false is refused rather than illustrated, and
  the refusal says why: `inspect_algorithm_trace` returns findings with a JSON
  path, and the MCP `draw` tool and `straightedge draw --json` report the same
  findings as a `blank_figure` refusal instead of "check your parameter shapes".
  Documented in `docs/algorithm-trace.md`.

- **A template can say why it refused to draw.** `refusal_findings` now lives in
  `diagrams.registry` and asks the template: any template exposing
  `refusal_findings(params)` has its findings carried by both `draw` transports.
  `construction` moved onto the hook unchanged; `algorithm_trace` is the second
  template on it.

- **The legibility check opens embedded SVG images.** A `data:` URI `<image>`
  used to be invisible to `check_figure`, so a storyboard's every child label
  went unchecked; the check now walks the child in the space its image paints
  it — scaled, offset and clipped as a viewer would — and reports a clipped or
  overlapped child label on the storyboard.

- **Four pure-SVG templates accept a discoverable `theme` parameter:**
  `roadmap`, `org_chart`, `unit_circle` and `linked_list`. Each template owns
  its family of themes and publishes exactly those names through the catalog,
  so an agent reads the enum rather than guessing from one global list.
  `professional` is the byte-identical default — each template declares its
  professional palette from the constants it always drew with and reads the
  theme unconditionally, and a test holds the default to those literals.
  Presentation, friendly, classroom, playful, pastel, dark, high-contrast and
  print-friendly variants are offered where they fit the visual family; every
  palette keeps the roles a reader tells categories apart by measurably apart,
  and a name a family does not offer draws the default and is logged.
- `straightedge.diagrams.themes` supplies the dependency-free semantic colour
  roles those renderers share, `family()` for a template to declare its
  themes, and `readable_on()` for text drawn over a saturated role colour.

### Fixed

- **`environment_diagram` no longer reserves a function-object column it does
  not use.** The canvas always made room on the right for `functions`, so a
  diagram of frames alone carried an empty right half, and a consumer fitting
  the canvas to a box — a slide, an `algorithm_trace` panel — shrank the frames
  to make room for nothing. The column is laid out only when functions are
  given.

- Binary-tree annotations now contribute to the canvas padding, so balance
  factors, heights, and existing notes no longer run beyond the SVG frame.

- **An arrowhead is not a data mark.** `count_data_marks` stripped `<style>` but
  not `<defs>`, so the `<marker>` polygon that twenty templates define counted as
  one mark and an empty array, stack, queue or linked list passed as drawn —
  through `render_diagram`'s warning, the MCP `draw` tool's `blank_figure`, and
  every check built on them.

### Documentation

- Added `docs/diagram-themes.md`, including the distinction between SVG diagram
  themes and the existing Manim animation styles.

## [0.6.0] - 2026-08-21

A minor release about telling the truth: about what a figure looks like, and
about what running one costs.

0.5.0 shipped a legibility check and eight errors it had found. Six of those are
fixed here — `architecture_diagram` drew every unanchored note at the same
coordinates, so two notes were painted over each other on the template this
project offers as its answer to Mermaid for system architecture; `unit_circle`
drew an axis name through its own tick label and labelled the shown angle twice;
`matrix_transform` let a guide cross the gutter and leave the figure. Two remain
and are listed as known.

The check itself was wrong about a ninth. It skipped boxes with no *area*, and a
level line is zero-area however long it is — so a guide, an axis, a gridline or
a connector could leave the canvas entirely and go unreported. Fixing that
immediately found a `riemann_sum` gridline 8px off the right edge, which had
been there all along.

The other half is the animation lane admitting what it is. It needs Manim,
ffmpeg, LaTeX, dvisvgm and the `standalone` class, and pip installs one of the
five. The MCP server used to advertise `render` regardless, so on a bare host it
was a tool an agent picks because it is listed and gets a dependency error from.
It is now offered only where it runs, every template publishes what running it
requires, and the README leads with the lane that needs nothing.

New public surface — `requires` on `Template`, `diagrams.renderer.title` — and a
checker that reports findings it used to skip, so a minor rather than a patch.
`requires` is appended after the existing fields, so positional construction
written against 0.5 still means what it did.

### Changed

- **The MCP server offers `render` only where it can run.** The animation lane
  needs Manim, ffmpeg, LaTeX, dvisvgm and the `standalone` document class; pip
  installs one of the five. Advertised
  regardless, `render` was a tool an agent picks because it is listed, waits on,
  and gets a dependency error from — the guard that raises that error already
  existed, it just fired after the caller had committed. A host without the
  runtime now sees five tools that all work rather than six with a trap, and the
  server's instructions say what is missing and that `draw`, `plan` and
  `validate` are unaffected.

- **A template says what running it costs.** `lane` and `output` said an
  animation is an MP4; neither said producing one needs five things on the host.
  Every entry now carries `requires` — empty for the figure lane, the five
  packages for the animation lane — so an agent can choose between milliseconds
  and a ten-minute render without discovering the difference by failing.

  The runtime probe builds its checks *from* that list rather than keeping its
  own, so the names a caller reads and the names the host is held to cannot
  drift. They had: the probe also refused a TeX installation missing
  `standalone.cls`, which the catalog never mentioned, so a caller could install
  everything published and still be denied.

- **The README leads with the figure lane.** It is the part that needs nothing,
  runs in milliseconds and checks its own output; the animation lane is now
  below a rule, with its real host dependencies stated rather than implied by an
  extras name. The claim about checking is narrowed to what actually happens:
  the CLI and the MCP server return legibility findings with a drawn figure,
  which is not the same as every call to `render_diagram` doing so.

### Fixed

- **`architecture_diagram` drew every unanchored note at the same coordinates.**
  Two notes meant one painted over the other, and the reader saw neither — the
  template this project proposes as its answer to Mermaid for system
  architecture, with its notes illegible. They stack now, one line each, and
  are left-aligned rather than centred on the left margin, which is what used
  to throw most of a 300px note off the canvas.

- **A component label is fitted to the box it sits in.** Drawn at whatever
  width it happened to be, "Gateway (WebSocket/MQTT)" measured 186px in a 140px
  box and reached far enough out to collide with the label on the connection
  leaving it. It wraps to two lines now — the box is 44px tall and the text is
  the diagram's content, so there is room for it rather than a reason to trim.
  Where even two lines cannot hold it the line is trimmed with a visible
  ellipsis, and each component is wrapped in a `<g>` whose first child is a
  `<title>` carrying the whole label — so it is that component's accessible
  name and tooltip, not the document's. The same applies to a note in the
  bottom stack, which wraps onto reserved lines and keeps its full text: it
  used to be trimmed to one line with the remainder held nowhere, so on a
  narrow diagram the note the caller supplied was not in the output at all.

  Between them these were four of the eight legibility errors 0.5.0 shipped
  with.

- **The frame check no longer skips axis-aligned strokes.** It skipped on
  *area*, and a level line is zero-area however long it is — so a guide, an
  axis, a gridline or a connector could leave the canvas entirely and the one
  check that exists to catch that said nothing. `matrix_transform` drew its
  eigenvector ray to x=477 on a 460-wide canvas. A point is still skipped:
  there is nothing to clip and no extent to report an overhang of.

- **`unit_circle`'s labels no longer collide.** Three separate causes, all
  reported by a human opening the picture and looking, which is the loop the
  checker exists to replace. An axis name sat level with the tick label nearest
  it — `x` five pixels from its own `1` — so each name was drawn through a
  tick. The common-angle label was drawn on the ray the figure was already
  marking, so at `π/4` the label and the `(0.71, 0.71)` readout overlapped by
  half and the reader lost both, including the one they asked for; the angle
  being shown is no longer labelled twice. And the readout ran off the canvas
  near the edges — a third of `(1.00, 0.00)` was never painted at 0° — so it
  turns back inward when the natural side does not fit.

  Swept across every 15°: 51 errors to 4. The match against the shown angle is a
  circular distance rather than a bare modulus — `%` is non-negative, so
  `(45 - 45.2) % 360` is 359.8 and a figure drawn at 45.2° kept the 45° label
  on the same ray.

- **`matrix_transform`'s eigenvector rays are clipped to their panel.** They
  are drawn 1.5x the panel range deliberately, so the direction reads as a line
  rather than a segment — which is only right if the panel cuts them off, and
  nothing did. A ray crossed the gutter, the other panel and the edge of the
  figure, ending 17px past a 460px canvas. The grid beside it was clipped; the
  clip was emitted inside the grid branch, so the rays had nothing to reach for
  and turning the grid off took it away entirely. The label stays outside the
  clip: cutting a guide short is the point, and cutting its label short is the
  defect. A repeated eigenvalue also drew the same ray twice, which is darker
  rather than clearer.

  This is the second piece of evidence in #14, and the piece the 0.5.0 checker
  could not see.

- **`riemann_sum` drew one gridline past each edge of its plot**, found by the
  check above the moment it could see them: the grid loops ran to
  `int(max) + 2` where the integers inside the plot stop at `int(max)`. One
  line landed 8px off the right edge of the figure, invisible and unreported.

## [0.5.0] - 2026-08-21

A minor release about whether the output is any good, and whether a caller can
find out. The figure lane gained a check it never had — the animation lane has
measured its own frames since the beginning, while a figure's only test was
"did anything get drawn", so a diagram could stack four labels in the same
pixels and report success. `check_figure` reads an emitted figure back as
geometry and returns findings with the coordinates of what they name.

The other half is the catalog telling the truth about itself. It published
parameter names with no types beside them, because it understood one of the six
ways this codebase states a default; a caller with nothing in front of them
guesses, which is how `angle` once arrived as `pi/4`. It now reads all six, and
every template ships a worked example that the suite holds to its claim — a
figure example must draw, an animation example must plan, a request must route
where it says. Determinism is stated as a guarantee and tested across hash
seeds in separate interpreters rather than assumed.

New public surface — `example` and `example_request` on `Template`,
`diagrams.legibility.check_figure`, an `examples` flag on the MCP listing — so
a minor rather than a patch. Nothing was removed and nothing renamed: the new
fields are appended after `summary`, so positional construction against 0.4
still means what it did.

### Added
- **A legibility check over the whole figure lane, and findings that say where.**
  The animation lane has measured its own frames since the beginning; the figure
  lane's only check was `count_data_marks` — "did anything get drawn" — so a
  figure could put four labels in the same pixels and report success. Three
  templates had grown a private version of this in their own test files and
  thirty-five had nothing.

  `diagrams.legibility.check_figure(svg)` reads an emitted figure back as
  geometry and feeds the *existing* `qc.check`, so a figure and a scene report
  the same findings in the same shape — and every finding carries the `box` of
  what it names. "Your diagram is wrong" is what a screenshot and a vision model
  already give you; "wrong *here*, at these coordinates" is what a caller can
  act on, and it is only available because this lane computes its own geometry
  instead of asking a browser for it. `draw` returns them over MCP, and the CLI
  prints errors to stderr *after* the document, so a redirect still yields a
  figure.

  Two things had to be right before the findings were worth reading. An unfilled
  shape is a **stroke**, not a surface — judged by its bounding box a circle
  covers everything inside it, which alone produced four false warnings on the
  unit circle — and the full-bleed background every template paints would
  otherwise obscure every label on the page. Both are the parabola confusion the
  scene lane already hit, where one mistake produced 31 of 39 findings and
  buried the 8 that were real.

  The first sweep found **fourteen errors in six of thirty-eight templates**,
  among them the two `unit_circle` label collisions and the `matrix_transform`
  overflow a reviewer had just found by eye. Those six are recorded in
  `KNOWN_ILLEGIBLE`, and the list is strict: a template on it that starts
  passing fails the suite, so it can only shrink. An open-ended allowlist is how
  a check like this becomes decoration.

  The fourteen are **not** fixed here — six templates' layouts is its own change,
  and mixing it with the machinery that found them would make both harder to
  review.
- **`publish.yml` creates the GitHub Release**, not only the PyPI upload. Those
  were two steps and only one was automated, so the Releases page skipped 0.3.0,
  0.3.1 and 0.3.2 — all three tagged, all three on the index — and read as though
  the project had gone from 0.2.0 straight to 0.4.0.

  It runs *after* the upload, deliberately: a release announcing a version that
  failed to publish sends people to `pip install` something that is not there,
  while the reverse leaves a version on the index with no notes, which can be
  fixed by hand. Prereleases are marked as such.
- `tools/changelog_section.py`, which the step above reads its notes from. The
  extraction is a script rather than a `sed` in the workflow because a release
  body is the one artifact nobody proofreads before it is public: a one-liner
  that silently emitted an empty string would publish an empty release and
  report success. It refuses instead — on a version with no section, naming the
  ones that exist, and on a section that is empty — and a test asserts every
  shipped version still has notes to publish.
- A worked example for every one of the 58 templates, published through the
  catalog as `example` (arguments ready to paste — `type` + `params` for a
  figure, `template` + `params` for an animation) and `example_request` (a
  phrasing that actually reaches a prompt-routed animation through the keyword
  router). Types said what shape to send; they did not say what a working call
  looks like. Nothing in `parameters` reveals that `solid_spec` is a dict of
  `{kind, params, name}` rather than the string `"cube"`, or that a roadmap
  given tracks and items draws an empty frame until it also gets a top-level
  `start_date` — both found by writing the examples.

  Every example is checked rather than illustrative: a figure example must
  render differently from a bare call, an animation example must plan without
  blocking violations, a request must route to the template it is filed under,
  and no example may use a parameter its template never reads. The `draw` and
  `plan` tools and the CLI all read the same catalog, so all of them gained it.
  `list_templates` grew about a third; MCP callers that only need names can pass
  `examples=false`. `example` and `example_request` are appended after
  `summary`, so `Template(id, lane, output, invocation, params, parameters,
  summary)` — positional, as 0.4 allowed — still means what it did.

  Writing them is also what turned up that extraction was missing parameters
  read inside a helper — six templates' worth, including `gantt`, which had
  never listed `tasks`, the only parameter it really has. That is fixed above,
  so the examples and the catalog now agree exactly: a test asserts no example
  uses a key the catalog does not publish.
- A stated determinism guarantee (`docs/agent-interface.md`) and the tests that
  hold it: the same template and parameters produce byte-identical SVG on any
  machine, in any process, on any day. Checked across two hash seeds in separate
  interpreters, because Python randomises string hashing per process and a
  `set` that reaches output reorders between runs while looking stable inside
  one.
- `straightedge/examples.py`, a real parameter payload for every figure
  template. Determinism checked against bare `{}` renders is a test that cannot
  fail — a template given no parameters takes its empty defaults and never
  enters the loops where ordering could vary. Each payload is asserted to put
  data marks on its figure, not merely to change the output — a template handed
  something it cannot use still returns a document, and refusal chrome differs
  from a bare render while drawing nothing at all.

### Changed

- The catalog now reads five more ways a template can state a parameter's type,
  taking typed coverage from 219 of 334 parameters to 287 of 358. It previously
  understood only `params.get("x", default)`; the lane writes
  `params.get("x") or default` exactly as often (72 reads each), so half of
  every parameter was published as a bare name with nothing beside it. Also read
  now: a coercion (`float(params.get("angle") or D)` says "number" however the
  fallback is spelled), a named default resolved to its value
  (`or DEFAULT_WIDTH` → `640`), and any module-level helper the template hands
  the params dict to, followed by position so a helper may rename it. That last
  one closed real gaps rather than only untyped ones: two templates did all
  their reading in a delegated `_render` and so reported *no parameters at all*
  (which reads as a template needing no input, not one whose input is
  undocumented), and four more kept `render` as an outline over helpers like
  `_tasks_from_params(params)` — `gantt` had never listed `tasks`, the only
  parameter it really has.

  A published default is verified against behaviour, not just parsed: for all
  278 of them, passing the default renders byte-identical output to omitting the
  parameter. Both the CLI and the MCP server read the same catalog, so both
  gained this.

### Fixed

- `dirichlet_function` seeded the process-wide random generator to place its
  scatter, so rendering that one figure silently reset the `random` sequence of
  whatever called it. It now seeds a generator of its own: the scatter stays
  reproducible, and it no longer depends on — or disturbs — global state.

## [0.4.0] - 2026-08-21

A minor release, and a new lane. The library is named after a tool it could not
draw with; this is that tool — compass-and-straightedge constructions computed
in exact arithmetic, able to assert what they demonstrate and refused when the
assertion is false.

That refusal is the point. `preconditions` validates a plan's shape, `qc`
measures a rendered frame, `labels` checks translation — and none of them can
tell you that the line you drew through two circle intersections *is* the
perpendicular bisector. This decides that, and draws the conventional marks for
the claims it decided, so a right-angle square on the figure is evidence rather
than decoration.

New public surface: `Construction`, `Exact`, `Tower`, `PrecisionError`, the
`straightedge.geometry` namespace, a `construction` figure template, the
`verify_construction` MCP tool and a `draw` CLI command. Nothing was removed;
code written against 0.3.2 keeps working.

### Fixed
- The exact kernel's bit ceiling was not enforced on plain rationals. `__add__`,
  `__mul__` and `inverse` returned early on the level-0 path without checking,
  so a construction of large rational coordinates — the commonest way integers
  grow at all — was the one case the cap did not cover. Found by a test written
  to exercise the cap, which reported no finding because nothing had raised.
- **`draw` answered `ok: true` for a figure with nothing on it.** Asked for the
  unit circle at `"pi/4"`, it returned zero bytes, zero data marks and
  `blank: true` — alongside `ok: true`. The mark count is the tool's own
  evidence that nothing landed, so claiming success beside it is a claim it has
  already disproved. A figure with no marks now raises `blank_figure`, and the
  failure carries the parameters the template actually reads, so a caller can
  correct it in one step rather than guess again.
- **`render` advertised a lane this host could not run.** Without Manim it
  failed deep in the pipeline with "Manim ran but did not produce the expected
  file", which sends a caller to look at their plan rather than their machine.
  It now checks the runtime once the plan has been judged — preconditions still
  refuse first, because an invalid plan is the caller's to fix whatever the host
  has — and names each missing piece. `pip install 'straightedge[render]'` is
  not the whole answer either: ffmpeg and LaTeX are system packages, and the
  error says so. The whole chain is checked rather than its headline parts —
  scenes use `MathTex`, so Manim goes LaTeX → DVI → SVG, and a host with manim,
  ffmpeg and latex but no `dvisvgm` failed deep in the render exactly as before.
  A TeX installation that cannot find `standalone.cls` is reported too, and only
  when `kpsewhich` is there to answer: absent, it means unknown rather than
  missing, and a guess would send a caller to install what they already have.

### Added
- **A constructive-geometry lane**, and with it the check the library did not
  have. `preconditions` validates a plan's shape, `qc` measures a rendered
  frame, and `labels` checks translation — not one of them can tell you that the
  line you drew through two circle intersections *is* the perpendicular
  bisector. That is a fourth failure mode, the picture is legible and the
  mathematics is wrong, and it is what this lane exists to decide.
  - `straightedge.geometry.exact` — arithmetic over the tower of quadratic
    extensions of Q, which is exactly what ruler and compass reach. Sign is
    decidable by recursion, so `is_zero` is a proof rather than a tolerance.
    Both caps refuse with a typed `PrecisionError` rather than falling back to
    floats. Stdlib only.
  - `straightedge.geometry.model` — `Point`, `Line`, `Circle`, `Segment`,
    `Section`, `Polygon` and the `Construction` that holds them in the order
    they were drawn, with automatic intersection, exact deduplication, and
    `parents`/`children` kept apart.
  - `construction`, a figure template: construction steps in, SVG out, with
    circles drawn whole and lines run to the frame. `to_svg_steps()` gives one
    frame per step against a fixed viewBox, which is the bridge to the
    animation lane.
  - `straightedge.geometry.notation` — `A = 0, 0`, `[ A B ]` for the line
    through two points, `( A B )` for the compass on the first through the
    second. The brackets are the drawing, so a reader can tell which tool made
    which element. Strict in the way `expr.py` is strict: one branch per form,
    no `eval`, and an unrecognised line rejected **with its number and the form
    it nearly was** rather than repaired into something that draws. The
    documented forms and the accepted forms are one tuple, and a test parses
    every one — which is how a published implementation of this idea came to
    advertise a section syntax its parser did not accept.
  - `straightedge.geometry.claims` — twelve predicates (`on`, `collinear`,
    `parallel`, `perpendicular`, `congruent`, `midpoint`, `equilateral`,
    `tangent`, `concurrent`, `ratio`, `golden`, `harmonic`), each reducing to
    `is_zero` on an exact value and returning `qc.Finding`, so every existing
    consumer reports them unchanged. A claim that holds is silent, a claim that
    fails is an `error`, and one that could not be certified is a `warn` that
    says so — never a pass. A `construction` whose claim is false does not get
    drawn, which is the rule `AGENTS.md` states for the example scenes applied
    to a figure.

    `golden` is the one worth reading: `AB/BC == φ` looks like it needs `√5`,
    but squaring twice makes it `AB⁴ == AC²·BC²` — exact, and it adjoins
    nothing. It accepts φ and rejects 1.618, which is the entire argument for
    the exact kernel in one test.
- **A step can name the points it produces** — `( B A ) -> C D`, and they are
  ordered by geometry rather than by algebra: upper first, then left to right.
  Automatic names shift when an earlier step consumes a letter, so inserting one
  anonymous point moved the vesica's crossings from `C, D` to `D, E` and a line
  written as `[ C D ]` silently joined two different points — no error, a
  plausible figure. The geometric order is what makes a name mean something:
  which crossing is "upper" is a fact about the drawing, while which one the
  algebra emits first depends on the sign of a line coefficient. Naming more
  points than a step makes is refused rather than ignored.
- **`straightedge draw`**, so the CLI can draw a figure. `list-templates` had
  listed both lanes since it was written while every command reached only the
  animation one, so the CLI advertised 38 figure templates and could draw none
  of them — the same gap the MCP server had before `draw`, on the other
  transport. It writes to `--out` or pipes the document to stdout, reports
  `data_marks` and the UTF-8 byte count under `--json`, and refuses a blank
  figure rather than leaving an empty file behind. A test asserts the listing
  and `draw` read one registry.
- **A proved claim earns its mark on the figure.** A right-angle square where
  `perpendicular` was decided, ticks on segments decided `congruent`, chevrons on
  proved parallels — the conventional annotations, drawn *because the arithmetic
  decided them*. Every other tool draws a right-angle square because a human
  asserted the angle; here the square is evidence. A claim that fails earns
  nothing and blocks the drawing; one that could not be certified earns nothing
  either, because an uncertified right angle drawn as certain is precisely the
  confident falsehood this lane refuses.

  Groups are numbered by stroke count so two congruences read apart, and only a
  claim that actually draws groups consumes a number — counting `perpendicular`
  made the first congruence draw two strokes and sent a reader looking for a
  single-tick pair that was never there. A tick whose midpoint lands on a
  right-angle corner slides along its own segment: in the vesica the midpoint of
  `AB` *is* that corner, and both marks are correct and together unreadable.
- **Arcs**, written `( O A ~ B )` — the arc of the circle on `O`, counterclockwise
  from `A` to `B`. Circles are drawn whole everywhere else in this lane and
  deliberately so, because a clipped element hides the relationships it is not
  currently being used for; an arc is the exception a *sectional* figure needs.
  A hemisphere in section is a semicircle, and drawing the whole circle says
  something false about the solid.

  Both ends must lie on the circle. Taking an arbitrary direction and finding
  where it meets the circle needs the square root of a length, which is not in
  general constructible — so such an arc could only be placed approximately, in
  the one lane where nothing is approximate. An arc restricts what is *drawn*,
  never what is known: intersections and claims run against the whole circle, so
  a point on the hidden part is still found and still drawn. Its extent, though,
  is its own sweep — reserving the whole circle for a semicircle wasted half the
  page on nothing, which is the reason arcs were wanted.
- **A mark needs something to mark on.** `congruent` claimed on four radii that
  were never drawn put four ticks in the middle of empty space, which reads as a
  rendering fault rather than as a proof. A segment is not an element — it exists
  where a drawn line passes through both ends, or where two adjacent corners of a
  drawn polygon are. The claim still holds and is still reported; it simply earns
  no annotation when there is nothing on the page for one to sit against.
- **Labels are placed in the first free slot** rather than always to the right.
  `P` and `Q`, one unit apart on a 200-unit figure, were drawn in the same pixels
  — and a figure that cannot tell you which point is which has lost the thing
  labels are for. Six slots are tried in turn, and a label with nowhere to go is
  dropped rather than stacked: an unlabelled point is a gap a reader can see, two
  labels in one place is one they cannot.
- **`tangent` accepts two circles**, not only a circle and a line. Written on the
  stored `r²` it is one identity covering internal and external contact —
  `(d² − r₁² − r₂²)² = 4r₁²r₂²` — exact, and needing no square root. The AIME
  hemisphere problem is the case it was missing: a 42-sphere resting inside a
  200-hemisphere touches it at exactly `r = 20√58`.
- **`verify_construction`, an MCP tool.** `draw` refuses a construction whose
  claim is false and returns a blank, and a template has nowhere to put the
  reason. This returns the findings without drawing: `holds`, `worst`, and
  `would_draw` — the last a claim about what `draw` will actually do, with a
  test that checks the two agree. Same economics as `validate` before `render`,
  at a smaller scale.
- **`tools/build_site_figures.py`**, and a test behind it. `build_site_assets.py`
  was written because every MP4 on the site was made by hand and nothing could
  reproduce it; the SVG figures had exactly the same problem and were never
  covered. Each declared figure now names the hint that made it, `--check` fails
  when one drifts, and the `pages` workflow gates the deploy on it the way it
  already gates the feed.

  The eight pre-existing figures are deliberately **not** declared: their inputs
  were never recorded, and a guess that renders something plausible would
  replace the site's artwork and report success. They are named in the script as
  outstanding rather than quietly implied to be covered.
- A post, *The picture is not the proof*, and a third series on the blog. 1.618
  is right to three places, is not φ, and every checker that compares a measured
  ratio against a tolerance says it is.
- `Arc` joins the `straightedge.geometry` namespace. It was reachable through
  `Element.geometry` and not importable, so a caller received a type they could
  not name or check against. The guard added with it is written against the
  *set* of the model's exports rather than against `Arc` — a class added to the
  model and forgotten in the package is how this one was missed, and the next
  one would have gone the same way.
- Four further review findings, all reproduced first:
  - **A circle was tangent to itself.** The squared identity is satisfied by a
    circle and its own copy — `d² = 0` and `r₁ = r₂` make both sides `4r⁴` — but
    coincident circles meet at every one of their points, which is the opposite
    of touching at one. Dedup makes this easy to reach: redrawing a circle
    returns the first one, so the two operands are the same element.
  - **A requested name could be eaten by a crossing that already existed.** The
    name was spent before the insert, and inserting a point already in the model
    returns the existing one — so `[ C D ] -> M` met `C` and `D` again on its way
    to the midpoint, `M` was consumed by a point that already had a name, and the
    midpoint fell back to an automatic letter. `M` then referred to nothing,
    silently, which is the failure the naming form exists to prevent. Names are
    spent only on points a step actually creates.
  - **A zero-sweep arc drew nothing and reasoned as a whole circle.**
    `( O A ~ A )` was accepted; SVG renders an arc from a point to itself as
    nothing at all, while the model still intersected against the full circle —
    so the figure carried geometry a reader cannot see and a claim could turn on
    it. Refused, and the refusal names `( O A )` as the way to say "the whole
    circle".
  - **The CLI reported a refusal as a parameter mistake.** A construction whose
    claim is false renders blank, and the generic remedy sent the caller to check
    parameter shapes that were already correct. The MCP path distinguished this
    and the CLI did not, so the same refusal read differently by transport. One
    implementation now, beside `verify`, used by both.
- Five review findings on the lane above, all reproduced before being fixed and
  all gaps the suite could not see:
  - **Float coordinates were silently approximated.** `limit_denominator(10**9)`
    turned `0.333333333334` into exactly `1/3`, `1.000000000001` into `1` and
    `1e-12` into `0` — an approximation in the one lane whose premise is that
    nothing is approximated, and enough to prove a claim exactly of a number
    nobody supplied. A float is now read through its `repr`, the shortest
    decimal that round-trips, so `0.1` is one tenth and `0.333333333334` stays
    itself. A non-finite float is refused.
  - **Degenerate figures proved arbitrary claims.** Every squared length of a
    section on one repeated point is zero, so `AB² == r²·BC²` held for *every*
    `r`: the collapsed section was reported as being in ratio 12345 and as
    golden, by exact arithmetic, with total confidence. A predicate now owns its
    domain — sections need parts with length, harmonic ranges need four distinct
    points, and a ratio of lengths must be positive, since squaring loses the
    sign and `-2` was satisfied by `2`.
  - **A malformed claim crashed instead of reporting.** The predicates read
    `claim.of` positionally, so `midpoint` with one name raised out of an
    unpacking and reached the MCP tool as a `ValueError`. Arity is declared per
    claim and checked before dispatch.
  - **Square-free reduction could run effectively forever.** Trial division to
    `√n` is unbounded on an integer this class carries to `MAX_BITS`: a 50-bit
    prime took four seconds, and a construction with a large coordinate reaches
    it through a circle intersection — so an ordinary request could pin the
    process. The search is bounded now; an unreduced radicand is still a
    radicand, so the cost is a generator that might have been shared, never an
    answer. 4.4s to 0.012s on the reported case.
  - **Hashing disagreed with equality.** `Exact.rational(Fraction(1, 3))` equals
    `Fraction(1, 3)` while their rounded-float hashes differed, so a dict keyed
    on one could not be read with the other — a silent loss of membership rather
    than an error. `Exact`, `Point`, `Line` and `Circle` are unhashable; nothing
    hashed them, and no cheap hash agrees with exact algebraic equality.
- `draw` distinguishes a **refusal** from a parameter mistake. A construction
  blocked by a false claim has correct parameters, and the blank-figure remedy
  sent its caller to check them; it now names the failing claim and points at
  `verify_construction`. A construction that could not be *built* still reports
  parameter shapes, because that is what is wrong with it.
- `sympy` joins the `dev` extra as a **test oracle** for the exact kernel —
  never a runtime path. Random expressions are built twice and required to
  agree on sign, zero and order, which covers the mistakes nobody has made yet.
  The shipped package still imports nothing but the standard library.
- **Parameter shapes in the catalog.** `Template.parameters` reports each
  parameter with its type and default where the code states one, beside the
  existing `params` name list. Names alone are what let an agent send `"pi/4"`
  for a field that wanted `45`: nothing in the listing said `angle` is a number
  of degrees. Inferred from the default in `params.get(name, default)`, since
  that is the one place a template says what it expects. A parameter read
  without a usable default is reported by name alone rather than with a guess,
  because saying nothing is recoverable and saying "string" about a number is
  not — and a default whose contents cannot be read literally keeps its type and
  drops its value, since publishing `[]` for a matrix that defaults to
  `[[1, 0], [0, 1]]` is a wrong answer where no answer was available. The animation lane reports names only — its parameters are declared by
  preconditions, which carry no default to read a type from.

## [0.3.2] - 2026-08-20

Three review findings on 0.3.1, and the reason the second of them shipped.

### Fixed
- **An assistant row collapsed to an ellipsis on a narrow chart.** With no more
  than one top-level unit the canvas was sized for the root card alone, leaving
  34px beside it, so "Chief of Staff" rendered as `…`. The 0.3.1 change that let
  columns grow had made the canvas *tighter* for the row hanging off the spine.
  The width is now solved for the card and the assistant together, so a one-unit
  chart is 1,020px rather than 568.
- **`draw` reported characters as `bytes`.** `len(svg)` counts code points, so a
  figure with Chinese labels under-reported its payload by the width of every
  multi-byte glyph — 1,807 against 1,851. It is UTF-8 length now, with the code
  point count kept beside it as `characters`. A field named `bytes` that is not
  bytes is worse than no field.
- **The MCP tool-set assertion still named four tools** after `draw` made five.
  It failed for anyone with the SDK installed.
- **…and the reason nobody noticed: that test never ran.** It is guarded by
  `importorskip("mcp")` and CI installs only `.[dev]`, which did not include the
  SDK — so the one check that asserts the exact tool surface was skipped on
  every build, and a stale assertion survived a tool being added. `mcp>=2.0`
  joins the `dev` extra, and `test_mcp_server.py` goes from 16 passed with 2
  skipped to 18 passed. The same extra now carries NumPy, which
  `test_cone_slice.py` imports during collection, instead of relying on a
  CI-only install that left the documented local dev setup unable to collect
  the suite. A test that never runs is not a test.
- A check on the declaration itself, because the first attempt at the line above
  did not take and was reported as done anyway. It reads the `dev` extra out of
  `pyproject.toml` rather than asking whether `mcp` imports: an import check
  passes in any environment where someone installed the SDK by hand, which is
  precisely how a missing declaration was verified as present. What has to hold
  is that the *declared* test extra installs it, and only the file says that.

## [0.3.1] - 2026-08-20

A patch release in effect and a small feature in fact: the figure lane became
reachable over MCP, where it had been listed but not drawable since the server
was written. Everything else here is a fix. Nothing was removed.

### Added
- **`draw`, an MCP tool for the figure lane.** `list_templates` advertised both
  lanes from the start while every other tool reached only the animation one, so
  an agent could see all 37 figure templates listed and had no way to draw a
  single one — the only drawing tool was `render`, which is Manim, ten minutes
  of a core, and fails outright without the `render` extra. `draw` takes a
  template id and its params and returns the SVG in milliseconds with no Manim
  at all. It reports `data_marks` alongside, because a template handed
  parameters it cannot read still draws its axes and frame, and several
  kilobytes of empty chrome is the one failure that looks exactly like success.
  Reported by a downstream plugin that had promised users those figures.
- `UnknownTemplateError` (`unknown_template`), so naming a template that does
  not exist is distinguishable from having named nothing at all. `RequestError`
  means "no request to work from"; an agent that typed `orgchart` has a request
  and a typo, and a code saying otherwise sends it looking in the wrong place.
  `details["known"]` carries the ids that do exist.

### Fixed
- **`org_chart` trimmed labels while a third of the canvas stayed empty.**
  Columns were pinned to a 206px constant rather than to the space they had, so
  a three-unit chart used 662px of 1,160 and cut five names that would have
  fitted whole. Columns now fill the width, bounded by a readable maximum so a
  single unit does not become one page-wide card; the same chart now spans the
  full canvas and trims nothing. Trimming is correct only when there is nothing
  left to trim into.
- **`org_chart` drew a dotted-line label nowhere near its line.** The curve was
  bowed by a fixed multiple of the card height and the label placed against that
  multiple rather than against the curve, so "security" rendered beside the CEO
  while the line it named arced far below. The control point is now solved for
  the apex the curve should actually reach, and the label sits on it.
- **`org_chart` dotted lines ended at the centre of the card they pointed at**,
  drawing themselves through that person's own name. They attach to the edge
  now, so an arc between two people obscures neither.

## [0.3.0] - 2026-08-20

A minor release on both lanes. The animation lane gains its first topic outside
the exam-shaped catalog — linear algebra, as two general builders rather than
five narrow ones. The figure lane gains two templates that existed only as
misuses of a neighbouring one — `roadmap`, which `gantt` was standing in for,
and `org_chart`, which `wbs` was — and, underneath both, one shared answer to
"how wide is this string" in place of the seven the templates had grown
separately. Four silent-truncation bugs fell out of writing it. Nothing was
removed; code written against 0.2.0 keeps working.

### Added
- **`org_chart`, reporting lines in the shape an organisation is read in.**
  `wbs` packs a tree by subtree width, which is right for a work breakdown and
  unusable for an organisation, because there the leaves are people: width grows
  with the *leaf count*, so a 157-person org rendered 18,528px wide at a 51:1
  aspect and a 685-person one 88,730px at 193:1. The new template follows the
  convention org charts have used since they were drawn on paper — the level
  under the top in a horizontal row, everything below it stacked in indented
  columns — and the same 157 people come out 1,160x2,150. Width is hard-bounded
  at 1,160px however large the org gets, because depth adds rows rather than
  columns, and columns past the width wrap into banks.

  It also says the three things a work-breakdown tree has no way to: a node is a
  **person and a role** rather than one label; a **dotted line** is secondary or
  matrix reporting, drawn dashed and named in a legend rather than left to be
  guessed; and an **assistant** hangs off the side of the spine, below the
  person it assists and above that person's own reports. `vacant` and `interim`
  are drawn states rather than text, so a status cannot be lost to truncation.
  A flat `{id, name, title, reports_to}` export is accepted as well as a nested
  tree, and a cycle or an unknown manager in one is survived — an unreachable
  person is attached to the root rather than dropped, because a person missing
  from an org chart is a worse failure than one drawn in the wrong place.
- **Shared text measurement** in `diagrams.renderer`: `text_width`, `fit_text`
  and `char_em`. Seven templates had grown seven private answers to "how wide is
  this string" — five held their own factor, two sliced at a character count,
  and one measured CJK as though it were Latin. The widths are now measured per
  character rather than averaged, because a single factor cannot describe a
  proportional face: "Ken Thompson" and "Chief of Staff" are the same length and
  differ by 25%, and an averaged estimate under-measured the first by 14%. The
  tables were read off a rasteriser and agree with the published Helvetica
  metrics.

  `text_width(..., safe=True)` adds headroom for the face resolving wider than
  the one measured — every template asks for `'Noto Sans SC'` first, and where
  that is absent fontconfig substitutes a face whose Latin glyphs run ~15%
  wider. A fit decision carries the margin because over-measuring costs
  whitespace and under-measuring puts one label on top of another.
- **`roadmap`, a calendar diagram for dated work in swim lanes.** `gantt` places
  bars on a *unit* axis for a CPM exercise: ticks are integers, every task owns a
  row, and there is nowhere to put a track or a milestone. A product roadmap is
  none of those things, and expressing one through `gantt` loses the lane, the
  milestone and the date — a six-month plan handed over as day units rendered
  ~4,800px wide with a 0..180 axis, captions cut at eight characters. The new
  template takes `start_date`/`end_date`, `tracks`, dated `items` with a
  `status`, `milestones` and `depends_on`; it packs overlapping items in a track
  into sub-rows so bars never collide, labels the axis with calendar dates, and
  draws a dependency whose target starts before its source finishes by routing
  around rather than backwards through the lane. Width is fixed, so a five-year
  plan and a one-month plan produce the same shape.
- A legibility check for the above, rather than a smoke test: the suite parses
  the emitted SVG and asserts no caption is drawn outside the viewBox, in any
  anchoring. A label that overflows is clipped, so it reads as *missing* — the
  failure a byte-count or element-count assertion cannot see.

- **A blog layout, rather than an article page listing articles.** `site/posts/`
  was `<main class="post">` with the post list bolted into its body — literally
  an article — which reads as one long page whatever is on it and has nowhere to
  put a date, a thumbnail, or a second series. It has its own `.blog` layout now:
  a masthead, series as self-contained sections, and a responsive card grid with
  poster thumbnails, dates and tags. A series that outgrows the index can be
  lifted out without restyling.
- Datelines on every post, in the page and in its `datePublished` structured
  data. A blog without dates reads as a static page.
- `site/posts/feed.xml`, an Atom feed, generated by `tools/build_blog_feed.py`
  from the posts themselves — title from the `<h1>`, date from the dateline,
  summary from the description meta tag, read with an HTML parser so entities
  are decoded once and inline markup in a headline never reaches a reader. A
  feed maintained beside the posts is exactly the file that rots: nothing
  renders it during review, and the first person to notice it is stale is a
  subscriber. A post missing any of the three fields is reported rather than
  skipped, and freshness is enforced in two places — `tests/test_blog_feed.py`
  on every PR, and `--check` in the `pages` workflow before it uploads, because
  those two workflows race on a push to main and only the second is between a
  stale feed and a subscriber.
- **Linear algebra**, the first topic outside the exam-shaped catalog described
  in issue #13. One concept, `linear_algebra/linear_map`, parameterised by the
  map itself: `matrix`, `vectors`, `labels`, `show_eigenvectors`, `show_span`,
  `show_determinant`. Vector addition, a linear transformation, the span of a
  set, the determinant as signed area and the eigen-directions are all readings
  of the same picture, so they are one builder rather than five — the `function`
  pattern, applied where it fits.
- `straightedge.linalg`: closed-form 2x2 eigenpairs, determinant, span
  dimension, and the coercions the builder and its checks share. The geometry is
  resolved in Python and baked into the emitted scene as constants, which is
  what lets a request be *refused* before Manim starts: a rotation has no
  invariant direction, so asking for its eigenvectors draws none rather than
  inventing one.
- **`linear_algebra/matmul_views`**, the second general builder: `A @ B` under
  each of the four readings of the same product — `entry` (the rule as taught),
  `column` (`col_j(AB) = A · col_j(B)`), `row`, and `outer` (`Σ_k col_k(A) ⊗
  row_k(B)`). Parameters are `a`, `b`, `view`.

  Two of those readings were already in this repository as hardware examples and
  reachable as neither prompt nor template. `examples/systolic_array` is the
  entry reading executed in silicon; `examples/tensor_parallel` is the outer
  reading executed across devices — "A split by columns, B by rows" is exactly
  the rank-1 factorisation, and that argument was doing linear-algebra teaching
  inside a networking video where no student learning matrix multiplication
  would find it.

  The scene follows the rule `examples/README.md` states for those examples —
  *simulate the mechanism, assert the claim, then animate the simulation*. Each
  view's own rule is run in Python, its steps are asserted to reproduce `A @ B`,
  and a view that does not raises before a frame is drawn. Every value, caption
  and highlighted index in the emitted scene is a computed constant, so changing
  the input matrices cannot leave a stale number behind.

  The arithmetic is stdlib — a triple loop and closed forms, no numpy, no sympy.
  `pyproject.toml` declares no dependencies on purpose, and determinism needs it:
  an eigenvector's sign convention varies between LAPACK builds, and a picture
  that flips between machines is not a picture the library can stand behind.

  The three grids are laid out by solving for the cell size, not by fixed
  offsets, and the type scales with it. The block is `(k + n)` cells wide and `(k + m)` tall — both grow with
  the inner dimension — so no fixed offset can be right for more than one shape,
  and the first attempt, tuned against a 2x2, put grid B on top of the product at
  4x4. `qc` reports clean at every shape up to the 4x4 cap, and the cap is there
  because 5x5 is where the bottom row measurably reaches the caption.
- Preconditions for `linear_algebra/linear_map`, registered in
  `straightedge.preconditions` alongside every other concept's. This is the one
  builder with no picture of its own — the parameters *are* the lesson — so a
  dropped parameter is not a detail rendered differently but a different lesson
  rendered confidently. A malformed `matrix` blocks, because falling back to the
  identity narrates a transformation over a video that shows none; vectors the
  scene cannot draw are reported with the count; eigenvectors on a rotation and
  a singular determinant warn, since the scene already degrades honestly. It
  also gives `list_templates()` the five parameter names it previously published
  as an empty list, for the one concept whose entire interface is its
  parameters.

- `tools/build_site_assets.py` — renders, stills, and publishes the site's demo
  assets. Every MP4, poster and GIF under `site/assets/` was made by hand and
  nothing could reproduce any of them, so a scene builder could change and the
  landing page would keep showing output the library no longer produces. Each
  scene now declares the exact input that made its file, including the seven
  that predate the script.

  Binaries go to the public `scimigo-cdn` bucket under `straightedge/assets/`
  rather than into git — `site/assets/` is already 3.3M against a 5.1M `.git`.
  Renders stage in `build/` (already gitignored) and the page references the
  published URL. Credentials are read from the environment only.

  The demo reel is declared rather than taken from `list_templates()`: the
  catalog says what *can* be drawn, and a landing page wants a curated subset.
  Each template render is passed through `preconditions.validate` first, because
  a front-page asset that trips a blocking check is the worst possible place for
  the failure this project exists to refuse.
- **The writeups section is now a blog** (`site/posts/`), with the three dataflow
  pieces grouped under a "Dataflow, executed" heading and room for series beside
  it. The directory keeps its `/posts/` path: three of its URLs are already in
  the sitemap and indexed, and renaming it to `/blog/` would 404 them to buy a
  nicer path.
- `site/posts/matrix-product-four-ways.html` — the first post outside dataflow.
  `AB` under its four readings, and the observation that two of them were
  already on this site without saying so: the systolic array executes the entry
  reading in silicon, and tensor parallelism executes the outer reading across
  devices. "Split A by columns and B by rows" is usually offered as a
  convention; it is the rank-1 factorisation, which is why each device can
  compute a whole partial sum and the block crosses the network once.
- Two linear-algebra cards on the landing page gallery: `linear_algebra/linear_map`
  showing the eigen-directions of `[[2,1],[1,2]]`, and `linear_algebra/matmul_views`
  building `AB` as a sum of rank-1 terms — the same reading the systolic-array
  and tensor-parallel examples further down the page already execute.

### Changed
- The linear-algebra post is titled "Matrix multiplication, four ways". The
  previous title spoke to whoever had already built the systolic array and
  tensor-parallel scenes, not to a reader arriving at the site.
- **The site's MP4s and posters left git for R2.** 2.8M of binaries against a
  5.1M `.git`, regenerated rather than edited, and read by nothing but two HTML
  pages. They now live in the public `scimigo-cdn` bucket under
  `straightedge/assets/` and the pages reference them by URL; `site/` fell from
  3.3M to 464K. The exact bytes were uploaded rather than re-rendered, so the
  live site is unchanged.

  The GIFs stayed. `README.md` embeds them through `raw.githubusercontent.com`,
  so moving them would make the project's GitHub and PyPI landing images depend
  on a bucket binding rather than on the repository — 292K is not the weight
  worth that. `site/assets/README.md` records the split.
- **Topics now declare themselves.** `straightedge.topics` is a registry: a topic
  states its id, keywords, tie-break priority and concepts in the module that
  owns it, and its plan and scene builders attach themselves with `@plan_for` /
  `@scene_for` where they are defined. Four hardcoded lists are gone — `Topic.ALL`,
  the concept-enum tuple in `catalog.py`, `planner._PLAN_BUILDERS` and
  `templates._SCENE_BUILDERS` — along with `planner.TOPIC_KEYWORDS` and
  `TOPIC_PRIORITY`.

  This is the figure lane's design, which has never had a central list:
  `diagrams/__init__.py` imports its templates for the side effect of
  registering them, and `preconditions.register` is the same pattern again. The
  animation lane was the exception, and adding linear algebra measured the cost
  — one topic, five files, and each omission failing differently and silently. A
  concept missing from the catalog's tuple renders perfectly and is invisible to
  every agent; a topic missing from `_SCENE_BUILDERS` quietly draws the
  *geometry* scene. `topics.verify()` runs when the package finishes importing
  and raises on any of them, so a half-registered topic cannot reach a caller at
  all.

  Registration is internal only — no entry points. The catalog earns its
  authority by *probing* (rendering a bare prompt to see if a topic is generic,
  running each canonical prompt to see which concepts are truly reachable), and
  those guarantees hold because everything listed shipped in this package.
  Opening that up is a decision about what `list_templates()` means, not a
  loader to add.

  New public names: `topic_ids()`, `topic_spec()`, `TopicSpec`.

  **Breaking:** `Topic.ALL` is removed. Use `straightedge.topic_ids()`. The
  `Topic.*` constants are unchanged, but they are now names only — what a topic
  *does* lives on its declaration, and a constant with no declaration is an
  import-time error rather than a topic that half-works.

### Fixed
Review findings on PR #2, all reproduced before being fixed.

- **Labels and span did not follow their vectors through the map.** `ApplyMatrix`
  transformed the plane and the arrows only, so a labelled `u` stayed at the old
  arrow's tip while the arrow left, and a requested span kept pointing the old
  way. This was the landing-page example, which supplies labels with a
  non-identity matrix. The tags are now *moved* rather than transformed —
  feeding text to `ApplyMatrix` shears the letterforms, so it would arrive in
  the right place unreadable — and a span *line* is carried through the map
  while a spanned *plane* is not, because the image of the plane is the plane
  and shearing that rectangle would draw a subspace the span never became.
- **`coerce_vectors` was not total.** `vectors=42` raised `TypeError` from inside
  validation — a check that crashes on bad input is not a check — and
  `vectors="nope"` iterated character by character, dropped every one, reported
  nothing, and rendered the stock pair. Both now yield `[]`, and `is_vector_list`
  lets the precondition report a malformed container as malformed rather than as
  empty.
- **The zero subspace was described as a line.** `span_dimension` correctly
  returned 0, but the scene grouped dimensions 0 and 1 together, drew a
  zero-length `Line`, and captioned it "the span is a line: these vectors are
  parallel". The span of zero vectors is `{0}`; it now draws the origin and says
  so. A single vector is also no longer called parallel to anything.
- **The readability floor voided the frame-fit guarantee**, and the guarantee
  never covered the arrows in the first place. `NumberPlane` keeps a unit size of
  one scene unit per plane unit whatever range it is given, so sizing the grid
  never moved the vectors: under `10I` the vector `(1, 0)` was drawn one scene
  unit long and `ApplyMatrix` sent it to `(10, 0)`, outside the frame, under a
  grid that "fitted" — and at any scale a 1-unit arrow spanning several grid
  squares misstates the vector it draws. The plane's `x_length` now carries a
  single scale that everything placed through `c2p` inherits, solved from the
  content; the grid is sized separately so its own image stays in frame, which
  is what `qc` polices. A map too violent to draw legibly is refused rather than
  rendered as a smudge.
- **A scalar matrix lost its two-dimensional eigenspace.** For `2I` both repeated
  roots took the already-diagonal branch, both returned the x-axis, and the
  duplicate was removed — leaving one dashed line, which tells a viewer the other
  directions turn. Every direction is invariant, so two independent basis
  directions are returned. A *defective* repeated eigenvalue still lists one.
- **`show_span` was supported, documented, changelogged, and read by no check**,
  so `list_templates()` published five parameters for a six-parameter concept and
  the feature was invisible to any caller trusting the catalog. The check now
  reads it, and is load-bearing rather than decorative: it reports the case where
  the subspace drawn is the origin alone.
- Bottom-of-frame captions are stacked. Span, area and eigen captions each
  claimed `to_edge(DOWN)` independently; with span and determinant both on, `qc`
  measured the area line 87% covered by the span note.

- Linear-algebra concepts were never checked for untranslated labels.
  `tests/test_labels._every_concept` hand-listed four concept classes and had
  not been updated for the fifth, so `linear_algebra/*` fell outside the
  coverage sweep. It reads the topic registry now, and a new topic joins that
  coverage by existing.
- `coordinate_plane` drew vectors as bare line segments. It referenced
  `url(#arrowhead)` and defined no such marker, so every vector lost the
  arrowhead that makes it a vector; the `label` documented for vectors since the
  template was written was never read; and all vectors defaulted to one blue,
  which the curve palette had already been introduced to avoid. Markers now
  carry an id derived from the vector data, so two diagrams on one page cannot
  resolve to each other's arrowhead — the collision `graph.py` documents.
- A generated linear-algebra scene sizes its plane so the *image* under the
  matrix fits the frame, rather than drawing a fixed grid that a large
  eigenvalue then pushes off-screen. QC measured 11.8 units outside a 14.2-unit
  frame before; the same scene now reports no errors.

- **`gantt` no longer grows without bound.** `MIN_UNIT_PX` floored the scale at
  26px per unit with no ceiling on the total, so width grew linearly with the
  unit count — fine for a 12-week textbook schedule, ~4,800px for the same plan
  expressed in days, with one gridline and one tick label per day. The scale now
  falls below the floor when the units are dense enough to need it, and the axis
  draws at most 24 ticks. A 180-unit schedule went from 4,844px to 1,064px.
- `gantt` row labels are trimmed to the width of the gutter they are drawn in,
  with an ellipsis when they are cut. The fixed `[:8]` was blind to the gutter
  and truncated mid-word with no sign anything had been dropped.
- **`wbs` cut names at `[:10]`, with no mark and no regard for the box.**
  "Dr. Alexandra Whitfield" rendered as "Dr. Alexan", which reads as a name
  rather than as a cut. This is the same defect as the `gantt` `[:8]` fixed
  above, one file over; both now trim to the width they are drawn in and mark
  the cut.
- **`comparison` cut descriptions at `[:22]`**, a character count with no
  relation to `COL_W`, applied to Chinese text at the same count as English
  despite being twice as wide per character.
- **`roadmap` measured CJK captions as half-width.** `text_width` was
  `len(value) * size * 0.55`, so a nine-glyph Chinese caption measured 57px and
  renders ~103px — and that number decides whether a caption goes *inside* its
  bar, so a Chinese roadmap put captions inside bars they overflowed. This is
  the failure the template exists to prevent, in the language this library
  targets most heavily.
- **`wrap_units` dropped everything past `max_lines` in silence.** An
  82-character caption came back as 37 characters that read like the whole
  thing, with nothing downstream able to tell that 44 had gone. The last kept
  line is now marked.
- The README's registry summary drifted from the registry. It advertised 35
  templates against 36, omitted `roadmap`, and listed "state machines" among the
  computer-science figures as though one were registered — there is no
  `state_machine` template, and a reader who went looking for it by the name the
  README used would not find it. A state machine is `graph` with `directed`
  edges, which the README now says.

## [0.2.0] - 2026-08-17

A minor rather than a patch release: the public API grew by seven names and a
CLI flag, and nothing was removed or changed. Code written against 0.1.0 keeps
working — `style` is the last parameter of `scene_code_for` and defaults to
`textbook`, which is tested against Manim's own palette, so existing renders are
unchanged unless a theme is asked for.

### Added
- A style layer (`straightedge.style`) naming colours, stroke widths, and fill
  opacities by **visual role** rather than by what they happen to depict, so one
  scene can be drawn more than one way. Three themes ship: `textbook` (Manim's
  own palette, the default), `paper` (light, for print and slides), and
  `dataflow` (the dark look the `examples/` scenes use). Select one with
  `--style` on the CLI, or `theme("paper")` from Python.
- `examples/tensor_parallel`: tensor parallelism given the same treatment as the
  other dataflow examples — simulated, asserted, and only then animated.
- [`docs/styling.md`](https://github.com/SciMigo/straightedge/blob/main/docs/styling.md),
  covering the token vocabulary and why generated scenes resolve a theme at
  generation time while hand-written scenes import it.

### Fixed
- The MCP server advertised `version="0.1"` to connected clients, hardcoded and
  already stale through the whole 0.1.x line. The version is now written once as
  `straightedge.__version__`; `pyproject.toml` derives its own from that
  attribute and the server reads it, so a release bump cannot be applied by
  halves. Regression-tested, including a check that no module reintroduces a
  second copy — which runs without the `mcp` extra, unlike the server test it
  backs up.

### Changed
- The package summary no longer scopes the project to lectures. It now reads
  "Generate deterministic, machine-checkable SVG diagrams and Manim animations
  from structured data, templates, or a prompt", matching the wording used in
  the README and on the gallery — three descriptions of the same library made it
  harder to place, for readers and for search alike. Package metadata is
  immutable once published, so 0.1.0 keeps the old wording on PyPI.

## [0.1.0] - 2026-08-17

The first public release. Everything below is new relative to the project's
private history as `math-voice`.

### Added
- Natural-language and named-template rendering of math figures — animated
  (Manim → MP4) and static (Python → SVG) — from one library.
- `list_templates()` and the `list-templates` command: enumerate every template
  across both lanes, with how each is invoked and the parameters it reads.
- `--template` (and the MCP `template` argument): render any shipped animation by
  name, in any language, with no keyword routing and no LLM.
- Automated visual QC (`qc.py`): checks the built scene for empty, clipped,
  off-frame, and overlapping content. Findings carry the defect's coordinates.
- Preconditions (`preconditions.py`): refuse a plan that would draw the wrong
  thing before spending a render.
- `estimate(plan, quality)`: a render-time budget before the render.
- `AnimationPlan.match`: whether a request reached a specific builder or a
  generic fallback.
- Structured CLI output (`--json`) and typed errors (`errors.py`) that carry a
  `code` and a `remedy`.
- An MCP server (`straightedge.mcp_server`, `straightedge[mcp]`) exposing
  `list_templates`, `plan`, `validate`, and `render` as tools.
- `SKILL.md` and `examples/agent_loop.py`: the agent workflow, documented and
  runnable.

### Security
- The agent lane runs generated code behind an AST allowlist (`agent/safety.py`);
  the figure lane evaluates expressions behind a strict allowlist (`expr.py`).
  See [`SECURITY.md`](SECURITY.md).
