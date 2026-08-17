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
