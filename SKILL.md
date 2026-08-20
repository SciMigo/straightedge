---
name: straightedge
description: >-
  Render a math or technical figure — animated (Manim → MP4) or static
  (Python → SVG) — from a natural-language request or a template name, and check
  that the result is actually legible before trusting it. Use when asked to draw
  a math concept, a diagram, or an explanatory animation, or when a figure needs
  verifying rather than eyeballing.
---

# Straightedge

You are drawing a figure you cannot see. Straightedge is the part that can: it
renders from a request and then **checks the rendered frame** for the defects a
human would otherwise catch by opening it — a caption through the axis labels,
two formulas on one spot, a plot off its frame. Treat the check as the point, not
a formality. A render is not done until it is checked.

## The loop

Run these in order. Each cheap step is a chance to stop before an expensive one.

1. **Discover** — `list_templates()` (or the `list-templates` CLI / MCP tool).
   Every template, both lanes, with how it is invoked and the parameters it
   reads. You cannot ask for what you have not enumerated. Note `invocation`:
   `prompt` means a request routes to it, `concept-id` means only naming it
   reaches it, `name` means it is a figure called by name.
2. **Plan** — `build_plan(request)`. Cheap. Turns the request into a plan without
   drawing. Read `.concept` to confirm it routed where you meant, and `.match`:
   `"concept"` means a specific builder matched, `"topic-fallback"` means it did
   *not* and you got a generic stand-in — do not present that as the thing that
   was asked for.
3. **Validate** — `validate(plan)`, then `blocking(violations)`. Still free. A
   blocking violation means the plan will draw the *wrong thing*; stop here and
   revise, because a render costs about ten minutes of one CPU core.
   `estimate(plan, quality)` tells you *which* render this is before you spend
   it: a `"quick"` scene is seconds, a `"slow"` (3D-camera) one is a minute-plus,
   and the spread is 30×. Read the `tier`; treat the `seconds` as a budget.
4. **Render** — `write_scene(plan, dir, qc_sidecar=…)` then `render_scene(…)`.
   The expensive step. Pass a `qc_sidecar` path so the check has data.
5. **Check** — `check_sidecar(sidecar)`. This is why the loop exists. Read the
   findings; do not skip to "rendered" and stop. Each finding carries a `box` —
   the `(x0, x1, y0, y1)` of the thing that is wrong — so you can locate the
   defect on the frame and adjust, not just know it exists.
6. **React** — an `error` finding means the frame is not publishable; revise and
   run the loop again. A `warn` is information (a curve grazing the label it
   names is usually fine). Judge, do not auto-fail on warnings.

A runnable version of exactly this is `examples/agent_loop.py`.

## Three ways to drive it

- **Python API** — import `straightedge`; everything above is a function. The
  core imports without Manim, so discovery and validation cost nothing on a host
  that cannot render.
- **CLI** — `straightedge <command> …`. Add `--json` to any command to get one
  result object on stdout instead of prose; failures come back as
  `{"ok": false, "error": {"code", "message", "remedy", "details"}}`.
- **MCP** — `pip install 'straightedge[mcp]'`, run `straightedge-mcp`. Tools:
  `list_templates`, `draw`, `plan`, `validate`, `render`. Same granularity as
  the loop, and `draw` is the figure lane's whole loop in one call — it costs
  milliseconds rather than minutes, so the plan/validate economics above do not
  apply to it. Read `data_marks` in its reply: zero means the template could not
  read the parameters and drew only its chrome. Same error shape throughout.

## Reading a failure

Failures are typed and carry the fix. Never scrape the message — branch on
`code` and act on `remedy`:

| `code` | means | what to do |
|---|---|---|
| `blocking_precondition` | the plan draws the wrong thing | revise the request, or pass `force` if you have read the reason |
| `render_failed` | Manim ran, no file | inspect the scene; try a simpler request |
| `font_unavailable` | no CJK font on this host | render in English, or install the font |
| `dependency_missing` | no Manim / no LLM key | install `straightedge[render]`, or use the cheap steps only |
| `bad_input_file` | an input could not be read | fix the path or the JSON |

## Two things to know

- **`force` is a real escape, not a retry.** A blocking precondition is a
  *prediction* that the render will be wrong. `force` says "I have read the
  reason and want it anyway." Use it deliberately, not reflexively.
- **A `warn` is not a failure.** These layouts are dense on purpose. Text inside
  its own cell, or a tangent line touching the curve it labels, reports as a
  warning and is correct. Only an `error` should stop a publish.

## When *not* to use this

For a chart of data — a bar chart, a line plot of a series — reach for a plotting
library. Straightedge draws math and technical *figures* (a labelled parabola, a
systolic array, a Gantt chart of a schedule), not statistical graphics.
