# Staged reveal

A figure template draws its final state. Some figures are procedures — a ladder
of squares climbed one rung at a time, a grid struck out one prime at a time —
and a narrated page wants each step to appear with the sentence that explains
it. `animated_trace` cannot do that: it plays on its own clock, and a narrated
page runs on the narration's.

So staged reveal is markup, not motion. The SVG is still one static figure; it
only says which parts belong to which step.

## The contract

- The **scaffold** — everything that is not a step — carries no attribute and is
  always shown.
- Each **natural step** is wrapped in `<g data-stage="k" data-step="name">`,
  with integer `k >= 1`.
- `reveal` is a list with one stage number per natural step: non-decreasing
  integers, each at least 1. Several steps may share a stage, so seven rungs can
  land on four beats with `[1, 1, 2, 2, 3, 3, 4]`.
- Without `reveal` **no attribute is emitted at all**, and the figure is exactly
  the static one.
- A consumer that ignores the attribute shows the final state, which is complete
  and correct on its own. A consumer that honours it shows stage `k` together
  with its own `k`-th reveal.
- `upto: k` draws only the steps whose stage is `<= k` and emits no stage
  attributes: a still of the figure part-way through, for a page that cannot
  reveal. With no `reveal`, step `i` (from 1) is stage `i`.

A plan of the wrong length, a non-integer, a stage below 1 or a stage that goes
backwards is refused: the figure renders blank and `refusal_findings` reports a
`stage_input` finding naming the problem, rather than revealing steps in an
order nobody asked for.

## Learning a figure's steps

The number of steps depends on the parameters — a ladder for `n = 117` has seven
rungs, for `n = 10` four — so ask rather than count:

```python
from straightedge.diagrams import natural_steps, render_diagram

params = {"base": 3, "modulus": 19, "n": 117, "select": True}
natural_steps("squaring_ladder", params)
# ['rung_1', 'rung_2', 'rung_4', 'rung_8', 'rung_16', 'rung_32', 'rung_64', 'select']

svg = render_diagram({"type": "squaring_ladder",
                      "params": {**params, "reveal": [1, 1, 2, 2, 3, 3, 4, 4]}})
```

`natural_steps` returns `[]` for a template that does not stage.

## Templates that stage

| Template | Natural steps, in order |
|---|---|
| `bit_selection` | `bits`, `sum`, then `powers` (with `base`), then `residues` and `multiply_1` … (with `modulus`) |
| `squaring_ladder` | `rung_1`, `rung_2`, `rung_4`, … one per rung, then `select` (with `select: true`) |
| `residue_tiles` | `tile_1` … `tile_<p-1>`, `match`, `conclude` |
| `coprime_grid` | `strike_<q>` for each prime factor `q` of `n`, smallest first, then `survivors` |

## Showing stages in a page

The markup is renderer-agnostic. A slide deck that already reveals content step
by step can show a diagram's stages with CSS alone: hide `[data-stage]` groups
by default and show stage `k` once the slide's `k`-th step is visible. Clamp
`k` to the slide's last step, so a plan with more stages than the slide has
steps still ends on the complete figure.
