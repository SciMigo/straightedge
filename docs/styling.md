# Styling

One scene, more than one look. Colours, stroke widths, and fill opacities are
named by **visual role** in `straightedge.style`, and a theme is the table that
gives those roles values.

```bash
straightedge render "riemann sum of x squared" --style paper
```

| Theme | What it is |
|---|---|
| `textbook` | Manim's own palette — **the default**, and exactly what every render used before themes existed |
| `paper` | Light ground, for print and slides |
| `dataflow` | The dark technical look the `examples/` scenes use |

## The tokens name a role, not a thing

```python
from straightedge.style import DATAFLOW as S

S.flow      # the primary thing in motion
S.hold      # its counterpart — stationary, or the other phase
S.done      # complete, verified, correct
S.warn      # the cost, the naive baseline, the hot spot
S.aux       # a tracked measurement: an angle being varied, a moving pair of dots
S.warm      # a second warm accent, when two related quantities must be told apart
S.fg  S.muted  S.dim  S.rule  S.ink  S.well  S.inert  S.on_fill  S.deep
S.size.title  S.width.mark  S.opacity.panel
```

Roles rather than domain names, because the same amber is a stationary weight in
the systolic array, a backward pass in the pipeline chart, and a packet in flight
in the ring. A token called `weight` would be wrong in two of the three. Each
scene aliases the role to what it means locally:

```python
WEIGHT = S.hold           # amber: stationary, in this scene
```

## Two paths, and they differ

**Generated scenes** (`templates.py`) take the theme as a parameter. It is
resolved at generation time and written into the emitted source as constants:

```python
# Palette: paper. Resolved from straightedge.style at
# generation time, so this scene needs only Manim to render.
C_INK = ManimColor("#fbfaf7")
C_FLOW = ManimColor("#1f6feb")
```

Baked rather than imported, because the emitted scene must render on a host that
has Manim and **not** this package — see `templates.qc_tail_source`. Reachable
from `scene_code_for(plan, style=…)`, `write_scene(…, style=…)`, and `--style`.

**Hand-written example scenes** (`examples/`) read one theme for the whole
directory from an environment variable, so the set stays internally consistent:

```bash
STRAIGHTEDGE_STYLE=paper manim -qm scene.py TensorParallel
```

## Two traps worth knowing

**`ManimColor`, not a hex string.** Manim accepts a string almost everywhere,
which makes the exception easy to miss: `interpolate_color` calls a method on its
first argument, so a bare string raises `AttributeError: 'str' object has no
attribute 'interpolate'` — *during* the render, and only in builders that
gradient something. The palette constructs its colours for this reason.

**A theme has to reach what no builder names a colour for.** Manim's background
is black and its unstyled text is white regardless of any palette. A scene that
themes only the marks it names renders dark-on-dark under `paper` and looks like
a broken builder rather than a missing wire, so the preamble sets:

```python
config.background_color = C_INK
Text.set_default(color=C_FG)
MathTex.set_default(color=C_FG)
Tex.set_default(color=C_FG)
DecimalNumber.set_default(color=C_FG)   # axis tick labels: neither Text nor MathTex
Axes.set_default(axis_config={"color": C_FG})
```

`DecimalNumber` is the one that bites. Miss it and a light theme loses every
number on both axes while everything else looks right.

## What is not themed

- **Font sizes in the three original dataflow examples.** Their type was tuned
  against their own layouts and `qc` has signed off on it; `Sizes` is there for
  new scenes to draw from. `tensor_parallel` uses it.
- **Geometry and timing**, deliberately. A theme swap must change only the
  palette — `tests/test_template_style.py` asserts that line for line.

## Adding a theme

Add a `Style` to `straightedge/style.py` and register it in `THEMES`; the CLI
choices, the lookup, and every test parametrised over `THEMES` pick it up. The
suite checks each theme is complete, that `fg` reads against `ink`, that the four
accents are distinct, and that `on_fill` survives all of them.

The one thing a new theme must not do is change `textbook` or `dataflow` — both
are pinned hex by hex, because `textbook` is what every existing generated render
used and `dataflow` is what the published example videos were drawn in.
