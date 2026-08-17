# QC sweep across every builder

One 480p render per concept, in both languages — 34 renders — with the extents
sidecar on, then `qc.check_sidecar` over each. Run 2026-08-16, after the
false-positive fix and the `calculus/derivative_tangent` layout fix.

Reproduce with `tools/qc_sweep.py`; raw findings in its `sweep.json`.

## Results

Final state, after the 3D projection fix and the three defect fixes. Every
concept rendered, 34 of 34.

| concept | en | zh | |
|---|---|---|---|
| `calculus/derivative_tangent` | 0E 1W | 0E 1W | |
| `calculus/riemann_integral` | 0E 4W | 0E 2W | was 5E |
| `calculus/ftc_accumulation` | 0E 2W | 0E 2W | |
| `calculus/taylor_series` | 0E 4W | 0E 4W | was 1E |
| `calculus/tangent_shift` | 0E 3W | 0E 3W | |
| `trig` (generic) | 0E 1W | 0E 1W | |
| `trig/graph_transform` | 0E 1W | 0E 1W | |
| `trig/unit_circle_to_sine` | 0E 2W | 0E 2W | |
| `conic/ellipse_foci` | 0E 0W | 0E 0W | |
| `conic/parabola_focus_directrix` | 0E 1W | 0E 1W | was 1E, English only |
| `conic/cone_slice` | 0E 34W | 0E 34W | 3D |
| `3d/solid_overview` | 0E 9W | 0E 9W | 3D |
| `3d/cube_section` | 0E 4W | 0E 4W | 3D |
| `3d/sphere_section` | 0E 0W | 0E 0W | 3D |
| `3d/three_views` | 0E 0W | 0E 0W | |
| `geometry` (generic) | 0E 1W | 0E 1W | |
| `function` (generic) | 0E 2W | 0E 3W | |

**No errors, in either language, anywhere.** The whole arc, from the first time
these checks were pointed at a real render:

| | first run | after 3D projection | after the fixes | after collapsing |
|---|---|---|---|---|
| errors (en) | 13 | 7 | **0** | **0** |
| warnings (en) | 106 | 74 | 69 | **32** |
| clean in both languages | 11/17 | 14/17 | **17/17** | **17/17** |

Six of the thirteen original errors were never defects at all — they were the 3D
measurement artifact. The other seven were real and are fixed.

The last column is measured differently and more precisely: rather than
re-rendering, the collapsing change was run against the **same sidecars** the
previous sweep produced. Identical geometry in, both versions of the checks over
it, so the delta is the code change alone with no render variance in it. The
sidecar is a plain record of what was drawn, which makes this possible.

### Re-running the sweep is the point

Fixing `taylor_series` meant moving its axes onto the shared caption budget,
which raised a curve label anchored above those axes into the title — a *new*
error, in English only, in the concept that had just been verified clean. The
per-concept check after the edit did not catch it because the check ran before
the edit. The sweep did.

## What the first run found: the checks were not valid for 3D scenes

Before the fix the totals split like this:

| | errors | warnings |
|---|---|---|
| 3D scenes (4 concepts) | 6 | **80** |
| 2D scenes (13 concepts) | 7 | 26 |

`boxes_from_scene` measured world coordinates and never consulted the camera —
`get_left()[0]` and `get_bottom()[1]`, x and y, ignoring z. Under
`set_camera_orientation(phi=70°, theta=-50°)` that is not what the viewer sees.

`3d/cube_section` was the clean demonstration: `'A' and 'A_{1}' overlap by
100%`, four times, one per vertex pair. (Repeats of that shape are now collapsed
into one finding — see the symmetric-key note below.) A cube's `A` at `(x, y, 0)` and `A₁` at
`(x, y, h)` differ **only in z**, so their measured boxes were identical, while
on screen the camera separates them by a quarter of the frame.

**Fixed.** The camera is consulted now, minding the two kinds of mobject that
must not be projected — `fixed_in_frame_mobjects` (already frame coordinates)
and `fixed_orientation_mobjects` (billboards: position projects, size does
not). Every fallback lands on the behaviour a 2D scene already had.

| | before | after |
|---|---|---|
| 3D errors | 6 | **0** |
| total warnings (en) | 106 | **74** |
| `conic/cone_slice` warnings | 76 | 34 |

Two things surfaced while fixing it:

- **Anchor sampling was wrong.** Manim stores **four** points per cubic, so the
  stride of 3 used by the stroke-path work picked handles rather than anchors —
  measured on a unit circle, points reaching 3.5% off the curve. The stride now
  comes from the mobject's own `n_points_per_curve`.
- **Subpath boundaries have to be honoured**, or a mobject that is several
  disconnected strokes (a pair of axes) gets a segment drawn across the middle
  of the picture that nothing ever rendered.

The more accurate anchors also found one new true positive in a *2D* scene:
`geometry` now reports `'Angle' is drawn through 'A'`.

### The warnings on 3D scenes, and why there were so many

`conic/cone_slice` reported **34** warnings and `3d/solid_overview` **9**, almost
entirely `'…' is N% covered by 'ThreeDVMobject'`. A filled 3D surface is built
from many small quads, each a separate mobject, so one label sitting on one cone
reported once per facet it touched. Every finding was true; together they
described a single defect, which is the same noise problem in a new place.

- [x] **Collapsed.** Collisions are now grouped by
      `(check, subject, other, crossed)` before being worded, with the count kept
      in the message rather than discarded — `'\alpha' is 100% covered by
      'ThreeDVMobject' (24 collisions)`.
      **`cone_slice` 34 → 3, `solid_overview` 9 → 6, total 69 → 32, errors still
      0.** A single collision reads exactly as it did before, with no count and
      no "up to", so the common case did not get noisier.

      Grouping on the *labels* rather than the mobjects is what makes it work and
      is also its limit: two genuinely different labels that render the same
      string collapse together. The count keeps that visible instead of hiding it.

      The count is of **collisions, not locations** — ten facets of one cone
      shading one label is ten collisions in a single place, which is why it is
      not worded as "places".

- [x] **And the percentage had to follow.** Collapsing by taking the largest
      per-pair percentage understated exactly the defect the collapsing exists to
      report. Those ratios are normalised by the *smaller* box, which for a
      many-facet surface is the facet: twenty facets each covering a tenth of a
      label each report a fifth of *themselves*, so the merged finding read
      `up to 20% covered` for a label that was entirely buried — true-but-noisy
      turned into quiet-and-misleading, which is worse than the noise.

      `text_obscured` now reports the union of everything shading the label
      divided by the label's own area. A union rather than a sum, so genuinely
      overlapping marks cannot push a label past 100%. `text_overlap` keeps the
      per-pair maximum and its "up to" hedge, because both boxes there are text
      and neither is the obvious denominator.

      The pair is also sorted before it becomes a key, since text-on-text is
      symmetric: left in scan order, one collision found as `(A, B)` and again as
      `(B, A)` survived as two error-severity findings.

      The totals in the table above were measured before this percentage fix.
      They are counts, and the fix changes wording rather than grouping — except
      for the symmetric-key change, which can only merge further. Re-running the
      sweep would be needed to restate them exactly.

## The real defects, and what fixed them

All were confirmed against extracted frames before being touched, and after.

- [x] **`calculus/riemann_integral` — 5 errors, two distinct bugs.**
      Four were the caption-over-tick-row collision already fixed by hand in
      `derivative_tangent`: `'1'`/`'2'` against `'Narrower rectangles, closer to
      the true area'` at 18%. The fifth was the `\Delta x \to 0` label, which
      hung under a brace that already hangs under the plot — it landed on the
      integral, and once the plot was raised it landed on the conclusion
      instead. It sits beside the brace now.
- [x] **`calculus/taylor_series` — 1 error.** `'Most accurate near 0 first'` sat
      entirely inside `'More terms widen the range of good fit'`; the
      neighbourhood label was never faded out. It fades with the note it belongs
      to. Its axes moved onto the shared budget as well — the approximations are
      clamped just inside `y_range`, so a plot reaching into the caption band
      dragged the clamped tails through the conclusion.
- [x] **`conic/parabola_focus_directrix` — 1 error, English only.**
      `'d(P,directrix)'` against `'Equidistant from the focus and the directrix'`
      at 27% — the one real instance in the sweep of the problem `_t()` exists
      for. The legend sat at a hand-tuned height off the corner that cleared the
      Chinese caption and not the English one, which is three times longer. It
      stacks above the caption now, so it holds in whatever language the caption
      is written in.

## The shared caption budget

Three builders had the same collision from the same cause: axes tall enough and
low enough to reach into the band at the bottom of the frame where the captions
live, putting the tick row through the text. The budget is now stated once, in
the preamble, as `PLOT_Y_LENGTH` and `PLOT_SHIFT`, and
`derivative_tangent`, `riemann_integral` and `taylor_series` all size themselves
from it. Fixing the number fixes all three.

The pattern that keeps producing this class is **anchoring a label to something
that moves independently of the thing it must stay clear of**. Every fix here is
the same shape: anchor the legend to the caption, the curve label to the title,
the plot to a stated budget.

## Also worth knowing

- `3d/sphere_section` takes ~90s to render at 480p, `conic/cone_slice` ~64s, and
  `3d/solid_overview` ~59s, against 2–12s for everything else. If renders get
  billed per core-minute, those three are most of the bill.
- Two concepts are unreachable from any phrasing — see the plan.
