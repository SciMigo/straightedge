# Designing this library for agents

Most libraries and CLIs were designed for people. This one should not be, and the
reason is specific rather than fashionable: **an LLM writing Manim is blind.** It
emits code, the code renders, and nothing tells it what came out. `qc.py` is the
thing that can tell it. That makes agent-friendliness and the project's actual
differentiator the same work, not two roadmaps.

Everything below is grounded in a real session where an agent drove this library
end to end — a 34-render sweep across every builder, in two languages, reading
findings back and fixing what they reported. The friction list is what actually
happened, not a checklist.

## What differs, in one line each

| | human | agent |
|---|---|---|
| finding out what exists | tries things, reads `--help` | must **enumerate** |
| reading results | reads prose | needs **structure** |
| judging output | looks at it | is **blind** — the system must describe it |
| recovering from an error | reads the message, adjusts | needs the error to **name the remedy** |
| context | holds it across a session | each call must be **self-describing** |
| spending ten minutes of CPU | notices and cancels | needs to **know the cost first** |

## What actually blocked the agent

Recorded during the sweep, in the order they hurt.

1. **Capabilities were undiscoverable.** Reaching every builder meant grepping the
   private `_SCENE_BUILDERS` dict and then *guessing Chinese phrasings* per
   concept. Two of them — `conic/cone_slice` and `calculus/tangent_shift` — turned
   out to be unreachable from any phrasing at all, which nothing reports.
2. **Parameter contracts were undiscoverable.** `mini_lecture` duplicates the
   concept catalog and ships `catalog_matches_straightedge()` purely to detect
   drift against it. A downstream consumer reverse-engineered an undocumented
   contract and then built a tripwire for it.
3. **Results came back as console prose.** `render_scene` inherits stdout, so
   Manim streams to the terminal, and the return value is an integer. Driving it
   programmatically meant writing a `subprocess` wrapper with
   `capture_output=True` — which is most of what `tools/qc_sweep.py` is.
4. **Errors print and exit.** `_precondition_gate` writes sentences to stderr. An
   agent has to pattern-match prose, and prose is allowed to change.
5. **Stale state read as success.** A leftover `qc.json` would be checked as
   though it described the current render. Worse in general: `write_scene` always
   writes `scene.py` into `output_dir`, so two concurrent callers collide
   silently.
6. **Cost was invisible until measured.** `3d/sphere_section` takes ~90s at 480p;
   `3d/three_views` takes ~3s. A 30× spread with no way to know in advance.

## The principle

**The library's job is to make the invisible visible to something that cannot
see.** That is what QC does for a blind code generator, and the same sentence
explains enumeration, structured errors, and cost prediction. Anything that only
a human staring at a terminal could act on is a gap.

## What to build, in dependency order

### Tier 1 — without these an agent cannot drive it at all

- **`list_templates()` returning JSON Schema per concept.** Topic, concept,
  required and optional parameters with types, and whether the planner can reach
  it from text. This closes three holes at once: agent discovery, the
  `mini_lecture` duplication, and the two unreachable concepts nothing reports.
- **Structured results everywhere.** `--json` on every command; a typed result
  object from every API call. `Finding` and `Violation` are already frozen
  dataclasses, so most of this is serialization, not design.
- **Typed errors that name the remedy.** Not
  `"Refusing to render: 2 preconditions failed"` but an exception carrying the
  violations, the concept, and the valid alternatives. The rule: **an error tells
  the caller what to do instead, in fields rather than sentences.**

### Tier 2 — these make the agent effective rather than merely able

- **Keep the perception loop first-class.** Findings should carry coordinates and
  the offending labels — enough for a model to fix a layout, not merely be told
  it is broken. This is the differentiator; it should be the best-specified thing
  in the library.
- **Separate the cheap steps from the expensive one.** plan → validate → render →
  check are already separable internally. Exposed, an agent can inspect a plan and
  stop *before* spending ten minutes of a core. Today `render` fuses all four into
  one blocking call.
- **Predict cost.** `estimate(plan) -> seconds`, even crudely. The 30× spread
  across builders is exactly what an agent needs to schedule around.
- **Distinguish refusal from failure.** `mini_lecture`'s
  `AnimationResult.refusal` is exactly right — a machine-readable marker
  separating "declined this topic" from "failed at it", because a crash is worth
  retrying and a missing builder never will be. That belongs here, not
  reinvented downstream.
- **Caller-named outputs.** `write_scene` should take a scene name. Fixed
  filenames make parallel work unsafe.

### Tier 3 — packaging, and only after the above

- **MCP server** over the typed API. Thin, once Tier 1 exists.
- **`SKILL.md`** teaching the loop: enumerate → fill parameters → validate →
  render → read findings → repair.
- **A worked agent-loop example** in `examples/`. The demo that makes the project
  interesting to anyone building with agents.

## Two things not to do

- **No separate "agent mode".** Two paths means one rots. The human CLI should be
  a thin shell over the same typed API the agent uses — the **first consumer** of
  the agent interface, not a parallel implementation of it.
- **No MCP before the API is right.** MCP over an unenumerable, prose-erroring
  library only moves the problem behind a protocol.

## What is already right, and worth protecting

The docstrings explain *why*, naming the specific defect that motivated each
check — `qc.py`'s table of what each check caught is the clearest case. That is
unusually good agent fuel: a model reading it learns the failure modes, not just
the signatures. Most libraries document what a function does; this one documents
what goes wrong without it.

Keep that as the codebase grows. It is cheaper than any amount of generated
API reference, and it is the part an agent can actually reason with.

## The determinism guarantee

**The same template and the same parameters produce byte-identical SVG — on any
machine, in any process, on any day.**

This is a guarantee, not an observation, and it is what makes the useful things
safe to build: caching a figure under the hash of its request, committing
generated SVG and reading the diff as a real change, regenerating a docs set in
CI and gating on `--check`, or comparing one render against the last to see what
moved. Every one of those is silently wrong if a figure can render two ways.

Concretely, the library promises that a render depends on nothing but its
arguments:

- **No clock, no locale, no filesystem, no network.** Nothing dated or
  machine-specific reaches the output, so a committed SVG does not diff
  tomorrow, or on someone else's laptop.
- **No hash-seed dependence.** Python randomises string hashing per process, so
  iterating a `set` reorders output between runs while looking perfectly stable
  within one. Output ordering comes from the input's order or from a declared
  constant — `roadmap`'s legend, for instance, is ordered by `STATUS_ORDER`
  rather than by whichever statuses happened to be present.
- **No global state, in either direction.** A figure that needs randomness seeds
  a generator of its own. `dirichlet_function` scatters points from a
  `random.Random(...)` instance, so its scatter is reproducible *and* your
  `random` stream is exactly where you left it. A figure is not entitled to
  reach outside its own output.
- **Stable catalog.** `list_templates()` returns the same ids, parameters and
  defaults in the same order every time, so an agent can cache what it learned.

### How it is checked

`tests/test_determinism.py`. The load-bearing test spends two subprocesses:
every figure is rendered under `PYTHONHASHSEED=0` and again under `99999`, and
the two sets of hashes must match. A same-process double-render cannot see a set
leak, so nothing less would do. (Dict iteration has been insertion-ordered since
Python 3.7 and is *not* seed-dependent — sets are the live hazard.)

The subtlety worth knowing if you extend this: a figure rendered with `{}` takes
its empty defaults and never enters the loops where ordering could vary. A sweep
over bare renders therefore agrees with itself no matter how badly ordered the
code beneath it is — it is a test that cannot fail. So every template has a real
example in `straightedge/examples.py`, and a separate test asserts that each one
actually changes the output. Verified the only way that means anything: with a
`set` deliberately introduced into `roadmap`'s legend ordering, the bare sweep
passed and the payload sweep failed.

## Examples

Every template publishes a worked `example` — arguments ready to paste, `type` +
`params` for a figure (the `draw` tool) and `template` + `params` for an
animation (`plan`, then `render`). Prompt-routed animations also publish an
`example_request`: routing is by keyword and Chinese-first, so the phrasing that
reaches a template is worth more to a caller than the rule that decides it.

They exist because types were not enough. `parameters` says `solid_spec` is an
object; it does not say the object is `{"kind", "params", "name"}` rather than
the string `"cube"`, and passing the string raises a bare `TypeError`. It says a
roadmap takes `tracks` and `items`; it does not say the figure draws an empty
frame until it is *also* given a top-level `start_date`. Both were found by
sitting down to write these, which is most of the argument for having written
them.

An unchecked example is worse than none — it is a wrong answer with the
library's name on it. So `tests/test_examples.py` holds each one to its claim:

- a figure example must render *differently* from the same template called with
  no parameters, so an example that quietly stopped being consumed fails
- an animation example must produce a plan with no blocking violations
- an `example_request` must route to the template it is filed under, not to a
  neighbour that would render something plausible and wrong
- no example may pass a parameter its template never reads

That last one is not hypothetical: the tests caught seven defects in these
examples before they were ever published — `x^2` where the parser wants `x**2`,
`sin(x)` where the Taylor precondition wants `sin`, a `half_angle_tan` of
`"1/2"` where a number was required, two parameters no template read, and two
request strings that routed to the wrong template.

`list_templates` grew about a third with examples in it. An agent that only
needs names can pass `examples=false`.
