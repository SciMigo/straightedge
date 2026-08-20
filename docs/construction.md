# Constructions

Compass and straightedge, in exact arithmetic, with claims that are decided
rather than measured.

The library is named after a tool it could not draw with until this lane
existed. What distinguishes it from drawing two circles and a line is that a
construction can **assert what it demonstrates**, and is refused when the
assertion is false.

## Why exact, and what "exact" means here

`preconditions` validates a plan's shape. `qc` measures boxes on a rendered
frame. `labels` checks translation. Not one of them can tell you that the line
you drew through two circle intersections *is* the perpendicular bisector. That
is a fourth failure mode — **the picture is legible and the mathematics is
wrong** — and it is what this lane decides.

Deciding it needs arithmetic that does not round. Ruler and compass reach
exactly the tower of quadratic extensions of the rationals: a straightedge
through two known points gives a linear equation, a compass gives a quadratic
one, and nothing either tool can do escapes `Q(√r₁)(√r₂)…(√rₙ)`. That is the
classical theorem, and it is why the cube cannot be doubled — a cube root has
degree 3 and every element here has degree a power of two.

So `straightedge.geometry.exact` is not an approximation of the geometry. It is
the geometry's own arithmetic. An element at level *k* is `a + b√gₖ` with `a`
and `b` from level *k-1*, and `Fraction` at the bottom. Sign is decidable by
recursion, so `is_zero` is a proof:

```
sign(a + b√g), with g > 0 and therefore √g > 0:
    a, b both ≥ 0   →  positive (or zero if both are)
    a, b both ≤ 0   →  negative (or zero if both are)
    opposite signs  →  compare a² against b²g, recursively
```

No tolerance appears anywhere in that path.

## The notation

One line per step. The brackets are the drawing, so a reader can tell which tool
made which element.

| form | means |
|---|---|
| `A = 0, 0` | a given point, named |
| `* 1, 0` | a given point, named for you |
| `[ A B ]` | the line through `A` and `B` |
| `( A B )` | the circle on `A` through `B` |
| `< A B C >` | a polygon on those points |
| `/ A B C /` | a section: three collinear points |
| `( A B ) guide` | drawn, but excluded from intersection |
| `# anything` | a comment |

Coordinates are integers, `p/q` fractions, or decimals — and a decimal is read
as the exact rational it denotes, so `0.1` is one tenth rather than the binary
float nearest to it.

Parsing is strict. A line that is not a form is rejected **with its number and
the form it nearly was**, and the parse is all-or-nothing: a construction
missing the step you mistyped does not make a smaller drawing, it makes a
different one that still looks finished.

```python
from straightedge.diagrams import render_diagram

svg = render_diagram({"type": "construction", "params": {
    "steps": ["A = 0, 0", "B = 1, 0", "( A B )", "( B A )", "[ C D ]"],
}})
```

The structured form — `{"circle": ["A", "B"]}` — is accepted equally, and the
two may be mixed. An agent writing JSON reaches for one and a person writing a
construction by hand reaches for the other; both arrive at the same steps.

## Points you did not name

Only `A` and `B` are given above. Crossing the two circles produces `C` and `D`,
which is why the line can name them. Add `[ A B ]` and you also get `E` and `F`
where it meets each circle, and `G` where the two lines cross.

They are exact. `G` is `(1/2, 0)` and `C` is `(1/2, √3/2)` — not values near
them — and the whole construction costs the field one generator, `√3`.

Re-drawing something already present is a no-op rather than a duplicate,
because "the same point" is decided rather than measured.

## Claims

| claim | holds when |
|---|---|
| `on(P, s)` | `P` satisfies the line's or circle's equation |
| `collinear(A, B, C)` | the triangle's area is zero |
| `parallel(l₁, l₂)` | the direction cross product is zero |
| `perpendicular(l₁, l₂)` | the direction dot product is zero |
| `congruent(s₁, s₂, …)` | squared lengths are equal |
| `midpoint(M, A, B)` | `2M == A + B` |
| `equilateral(poly)` | every squared side length is equal |
| `tangent(c, l)` | distance² equals radius² |
| `concurrent(l₁, l₂, l₃, …)` | all pass through one point |
| `ratio(/A B C/, r)` | `\|AB\| / \|BC\| == r` |
| `golden(/A B C/)` | that ratio is φ |
| `harmonic(A, B, C, D)` | the cross ratio is −1 |

```python
from straightedge.diagrams.templates.construction import verify

findings = verify({"steps": [...], "claims": [
    {"claim": "perpendicular", "of": ["[ C D ]", "[ A B ]"]},
]})
```

`verify` returns `qc.Finding` values, so every existing consumer reports them
unchanged. **A claim that holds is silent**; one that fails is an `error`; one
that could not be certified is a `warn` saying it is neither proved nor
disproved — never a pass. A construction with a failing claim renders nothing,
which is the rule `AGENTS.md` states for the example scenes applied to a figure.

An assertion about an element that does not exist is a *failed* assertion, not a
skipped one. Passing it would report a construction as verified against a claim
nothing in it was ever checked by.

### Why `golden` is worth reading

`AB/BC == φ` looks like it needs `√5`. Written as "the whole is to the greater
part as the greater is to the lesser" it is `AB² == AC·BC`, and squaring that
gives `AB⁴ == AC²·BC²` — an identity among squared lengths with no root in it.
The predicate is exact *and* adjoins nothing.

It accepts φ and rejects 1.618. The two differ by about `3.4 × 10⁻⁵`: far above
any floating-point epsilon, far below what a drawing shows, and every checker
that compares a measured ratio against a tolerance calls the second one golden.

## What the caps mean

Two limits, and both **refuse** rather than fall back to floats.

`MAX_DEPTH` (6) bounds how many roots a construction may adjoin. Each level
doubles the rationals a coordinate costs, so a level-6 value is 64 of them.
Classroom constructions — the vesica, the bisector, the pentagon — are depth 1
to 3. Roots already in the field are reused: `√6` over a tower holding `√2` and
`√3` is assembled from them rather than adjoining a third generator.

`MAX_BITS` (4096) bounds any single numerator or denominator, because repeated
division grows integers without adjoining anything.

Breaching either raises `PrecisionError`, carrying `code`, a `remedy`, and which
limit it hit. Where that happens during a claim it becomes a `warn` — the
drawing is unchanged and the claim is neither proved nor disproved. It is never
silently a yes, because a tolerance-based yes on a claim nobody could certify is
exactly the plausible falsehood this lane exists to prevent.

## Over MCP

`draw` renders any figure template, `construction` included, in milliseconds
with no Manim. `verify_construction` decides the claims **without drawing**, and
reports `holds`, `worst`, and `would_draw` — the last a statement about what
`draw` will actually do with the same input.

Check before you draw. It is the same economics as `validate` before `render`,
at a much smaller scale.

## Credit

The notation's shape — identifiers that look like the tool that drew them, and
the two-stage predicate of a cheap numeric reject before an exact confirmation —
is borrowed from the MIT-licensed [`geometor/model`](https://github.com/geometor/model)
and [`geometor/divine`](https://github.com/geometor/divine). No code was taken
and there is no dependency; the arithmetic, the model and the predicates here
are written from scratch over `fractions.Fraction`.

One thing was deliberately **not** ported. Their harmonic-range test compares
`AD/CD` against `AC/BC`; the cross ratio needs `BD` where that uses `CD`, which
is a different quantity and a different predicate. The condition here is derived
from the cross ratio and pinned against a set worked out by hand — including one
the mistaken form accepts and this one rejects.
