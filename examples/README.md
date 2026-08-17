# Examples

## Driving the library from an agent

[`agent_loop.py`](agent_loop.py) is the loop an agent runs to produce a figure it
can trust: **discover → plan → validate → render → read the check → react**. Each
cheap step is a chance to stop before an expensive one, and it does not end at
"rendered" — it ends at "checked", because the QC finding is the thing an agent
acts on when it cannot watch the video itself.

```bash
pip install 'straightedge[render]'
python examples/agent_loop.py "画 y=x^2 的导数，用割线逼近切线"
```

It prints each step as JSON and exits non-zero on a blocking visual defect, so it
also works as a check in front of a publish. The workflow it embodies is written
up for agents in [`SKILL.md`](../SKILL.md).

## Standalone scenes

These render on their own — pure Manim, no library calls — and exist to show the
rule the library follows: *simulate the mechanism, assert the claim, then animate
the simulation*.

```bash
cd examples/systolic_array && manim -qm scene.py SystolicArray
cd examples/pipeline_schedules && manim -qm scene.py PipelineSchedules
cd examples/ring_allreduce && manim -qm scene.py RingAllReduce
```

| Example | Scene | Shows |
|---|---|---|
| `systolic_array/` | `SystolicArray` | A weight-stationary matrix unit, one cycle at a time: why the input skew exists, and what the array buys in SRAM reads. |
| `pipeline_schedules/` | `PipelineSchedules` | GPipe against 1F1B, both simulated: the same bubble, four times the activation memory. |
| `ring_allreduce/` | `RingAllReduce` | Reduce-scatter then all-gather, executed: the bytes per rank stay under 2D at any ring size, and it is the serial hops that grow. |

Between them they cover the three ways a model is split across devices — the
array inside one chip, the pipeline across stages, the all-reduce across data
parallel replicas — which is why the set is worth having rather than any one of
them.

## What an example here is for

These are not decoration for the README. They are the argument that this library
does something a prompt cannot, and they follow one rule:

> **Simulate the mechanism, assert the claim, then animate the simulation.**

Concretely, in both scenes the picture is a *consequence* of a computation rather
than a drawing of one:

- `systolic_array` places every activation and partial sum from the dataflow's own
  timing rules, and asserts each output against `A @ B` as it leaves the array.
  Get the skew wrong and the render fails instead of teaching the wrong schedule.
- `pipeline_schedules` places every op at the first cycle its dependencies allow,
  then asserts that the two schedules finish together — which is the claim the
  video makes on screen. If a future edit made 1F1B finish earlier, the module
  would refuse to render rather than publish a plausible lie.
- `ring_allreduce` actually performs the chunk exchange and refuses to import
  unless *every* rank ends holding the true elementwise sum — not merely the one
  the camera follows. The byte counts on screen are counted from the send log
  rather than copied from the formula, so a broken rotation cannot quietly agree
  with the arithmetic it prints.

That property is worth more than the animation. An LLM asked to draw a systolic
array will produce something that looks right and schedules wrong, and nothing
downstream will notice; the same is true of every hand-placed Gantt chart of
GPipe you have seen. A scene that computes what it shows cannot drift from it.

## The scenes check themselves twice

Each example asserts its **arithmetic** at import time, and its **layout** at the
end of `construct()` — `assert_readable()` in `_layout.py` runs the library's own
`straightedge.qc` over the built scene. A scene that renders is therefore one
whose numbers are right *and* whose picture can be read.

Those are genuinely different failures. Every arithmetic assertion here passes on
a scene with two labels printed on the same spot, because none of them look at
what was drawn. That is exactly the gap `qc` exists to fill.

An `error` raises — a picture that teaches the wrong thing is as bad as a wrong
schedule. A `warn` prints and lets the render finish, because a stroke touching a
label is often deliberate: a tangent line is *supposed* to meet its curve.

**Known limitation, which these examples exposed.** All three draw numbers inside
cells, and `qc` reports every one as `text_obscured` — *'F0' is 100% covered by
'Rectangle'*. True, and the intended design. Text inside a filled shape is
probably the most common layout idiom there is, and the check cannot yet tell it
from the thing it is hunting. The distinction it needs is containment: text
wholly *inside* a mark is a label in a box; text straddling a mark's *edge* is
half-covered and unreadable. That fix belongs in `straightedge.qc`, so until it
lands `_layout.py` summarises these warnings rather than listing them.

## Notes for anyone adding one

- **Fixed-width numbers when a label changes.** Manim's `Transform` zips the two
  mobjects' families, so `"0" -> "16"` raises rather than animating. Zero-pad.
- **`Indicate` restores what it animates.** Queue a dimming in the same `play()`
  and it is silently undone; flash a *position* instead, or dim in a later step.
- **Reserve the middle of a cell for whatever moves through it.** Static labels
  belong in a corner, or the first thing that passes hides them.
- Keep the numbers small enough to read at 200px wide. Three stages and six
  microbatches make the same point as thirty-two and a thousand.
