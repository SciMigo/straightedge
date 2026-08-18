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

These render on their own — no prompt, no planner, no generated code — and exist
to show the rule the library follows: *simulate the mechanism, assert the claim,
then animate the simulation*. They are Manim plus two things from the library
itself: `straightedge.qc`, which checks the picture they drew, and
`straightedge.style`, which is where their palette lives.

```bash
cd examples/systolic_array && manim -qm scene.py SystolicArray
cd examples/pipeline_schedules && manim -qm scene.py PipelineSchedules
cd examples/ring_allreduce && manim -qm scene.py RingAllReduce
cd examples/tensor_parallel && manim -qm scene.py TensorParallel
```

| Example | Scene | Shows |
|---|---|---|
| `systolic_array/` | `SystolicArray` | A weight-stationary matrix unit, one cycle at a time: why the input skew exists, and what the array buys in SRAM reads. |
| `pipeline_schedules/` | `PipelineSchedules` | GPipe against 1F1B, both simulated: the same bubble, four times the activation memory. |
| `ring_allreduce/` | `RingAllReduce` | Reduce-scatter then all-gather, executed: the bytes per rank stay under 2D at any ring size, and it is the serial hops that grow. |
| `tensor_parallel/` | `TensorParallel` | Why A is split by columns and B by rows: it is the only pairing an MLP block can cross the network *once*, and the wrong one is run alongside it to show it computes a different answer. |

Between them they cover the four axes a model is split along — the array inside
one chip, tensor parallelism inside one layer, the pipeline across stages, and
the all-reduce across data parallel replicas — which is why the set is worth
having rather than any one of them.

Two of them are also linear algebra wearing a hard hat. `systolic_array` is the
entry reading of a matrix product — `AB[i][j] = row_i(A) . col_j(B)` — executed
in silicon, and `tensor_parallel` is the outer-product reading — `AB = sum_k
col_k(A) (x) row_k(B)` — executed across devices, which is *why* A splits by
columns and B by rows rather than the other way round. Neither says so, because
neither is addressed to someone learning what a matrix product is. The concept
`linear_algebra/matmul_views` is: same four readings, animated as a lesson and
reachable from the catalog. These stay here as the argument that the readings
are load-bearing rather than decorative — the pairing a transformer depends on
is a statement about rank-1 terms.

## One set, more than one style

The four scenes share a palette, and it lives in `straightedge.style` rather than
in each file. That was not true at first: all three of the original scenes defined
the *same six hex values* independently, under different local names, which meant
the shared look was real but no caller could ask for a different one.

```bash
manim -qm scene.py TensorParallel                       # dataflow — the default
STRAIGHTEDGE_STYLE=paper manim -qm scene.py TensorParallel      # light, for print
STRAIGHTEDGE_STYLE=textbook manim -qm scene.py TensorParallel   # Manim's own palette
```

`examples/_layout.py` resolves the theme once for the whole directory, so the set
stays internally consistent whichever one is picked. An unknown name fails at
import, before Manim spends four minutes rendering in a style nobody asked for.

The tokens name a **visual role**, not a domain concept — `S.flow` and `S.hold`,
not `activation` and `weight`. The table in `straightedge/style.py` explains why:
the same amber is a stationary weight in the array, a backward pass in the
pipeline chart, and a packet in flight in the ring. Those have nothing in common
except being the counterpart to the blue, so each scene aliases the role to what
it means locally:

```python
from _layout import STYLE as S, assert_readable

WEIGHT = S.hold           # amber: stationary, in this scene
ACT = S.flow              # blue: streaming right
```

Colours, stroke widths, and fill opacities are themed. **Font sizes are not**,
beyond the scale in `Sizes` that new scenes draw from: the existing three had
their type hand-tuned against their own layout, and normalising it would have
moved text that `qc` has already signed off on. Porting them changed no pixel —
verified frame by frame, all 243 frames of `PipelineSchedules` byte-identical
before and after.

## What an example here is for

These are not decoration for the README. They are the argument that this library
does something a prompt cannot, and they follow one rule:

> **Simulate the mechanism, assert the claim, then animate the simulation.**

Concretely, in all four the picture is a *consequence* of a computation rather
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
- `tensor_parallel` runs the block both ways. The column/row pairing is asserted
  to reproduce the single-device answer exactly, at every split of the FFN
  dimension rather than at the two the animation happens to draw; and the wrong
  pairing is asserted to *disagree*, because "the pairing is forced, not
  conventional" is only a claim worth making if skipping the collective is shown
  to compute something else. The cells marked wrong on screen are read from that
  comparison, so changing the input matrices cannot leave a stale annotation
  behind. The collective count is taken from a communication log, not typed in.

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

**Known limitation, which these examples exposed.** All four draw numbers inside
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
