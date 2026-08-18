"""Linear algebra: one general builder, parameterised by the map itself.

Every other topic in this catalog is a set of bespoke scenes — a builder per
concept, each with its geometry worked out by hand. That is why the output is
trustworthy, and it is also why coverage grows one scene at a time.

Linear algebra does not need that shape. A 2x2 matrix acting on the plane *is*
the subject: vector addition, a linear transformation, the span of a set, the
determinant as signed area, and the eigen-directions are all readings of the
same picture. So this module ships one concept, ``linear_algebra/linear_map``,
and lets the parameters decide which reading a given lesson gets:

===========================  ======================================
lesson                       parameters
===========================  ======================================
vectors and their sum        ``matrix`` omitted (identity), ``vectors``
a linear transformation      ``matrix``
span / subspace              ``show_span``
determinant as area          ``show_determinant``
eigenvalues, eigenvectors    ``show_eigenvectors``
===========================  ======================================

The geometry is computed here, in ordinary Python, and baked into the emitted
scene as numbers. Two reasons. It keeps the render deterministic — the scene
draws constants rather than deriving them at animation time — and it means a
matrix whose eigenvectors do not exist can be *refused* before Manim is
started, rather than producing a confident picture of nothing. A rotation has
no invariant direction to draw, and drawing one anyway is precisely the
wrong-but-plausible output this library exists to prevent.

The refusal itself lives in :mod:`straightedge.preconditions`, with every other
concept's, rather than in a function here that a caller would have to know to
call. This module supplies the maths those checks are decided by.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Sequence

from .models import Topic
from .topics import topic


class ConceptLinAlg:
    """Concept ids for the linear-algebra topic."""

    LINEAR_MAP = "linear_algebra/linear_map"
    MATMUL_VIEWS = "linear_algebra/matmul_views"


#: The identity, used when a caller names vectors but no map — the "just show
#: me these vectors" case that opens most first lectures.
IDENTITY: tuple[tuple[float, float], tuple[float, float]] = ((1.0, 0.0), (0.0, 1.0))


def coerce_matrix(value: Any) -> tuple[tuple[float, float], tuple[float, float]]:
    """A 2x2 of floats, or the identity if the input is not one.

    Deliberately total rather than raising: a malformed matrix in a lesson spec
    should still render the vectors it came with. The substitution is not
    silent, though — :mod:`straightedge.preconditions` reports it against the
    plan, which is the difference between a forgiving renderer and a lying one.
    """
    try:
        rows = [list(row) for row in value]
        if len(rows) != 2 or any(len(row) != 2 for row in rows):
            return IDENTITY
        return (
            (float(rows[0][0]), float(rows[0][1])),
            (float(rows[1][0]), float(rows[1][1])),
        )
    except (TypeError, ValueError):
        return IDENTITY


def coerce_vectors(value: Any) -> list[tuple[float, float]]:
    """The plane vectors in ``value``, dropping any entry that is not one.

    Shared by the scene builder and the precondition check on purpose. The
    builder had its own inline copy of this loop, which is how a drop can become
    silent: the two agreed today and nothing made them agree tomorrow. One
    function means the check reports exactly the vectors the scene will draw.

    A three-component entry is dropped rather than truncated. This is a builder
    for the plane, so ``[1, 2, 3]`` is a caller who meant something else, and
    quietly using its first two coordinates answers a question nobody asked.

    Total for *any* input, including input that is not a container at all.
    ``vectors=42`` used to raise ``TypeError`` from inside validation — a check
    that crashes on bad input is not a check — and ``vectors="nope"`` iterated
    character by character, dropped every one, reported nothing, and rendered
    the stock pair. Both now yield ``[]``; :func:`is_vector_list` is what lets
    the precondition tell "no usable vectors" from "not a list of vectors".
    """
    if not is_vector_list(value):
        return []
    out: list[tuple[float, float]] = []
    for item in value:
        vec = _coerce_vector(item)
        if vec is not None:
            out.append(vec)
    return out


def is_vector_list(value: Any) -> bool:
    """Whether ``value`` is the *shape* a vector list has, ignoring contents.

    A string is not one, though it iterates. Neither is a number, though the
    caller who passed it plainly meant something. Separating the container
    question from the element question is what lets a malformed ``vectors`` be
    reported as malformed rather than as empty.
    """
    return isinstance(value, (list, tuple))


def determinant(matrix: Sequence[Sequence[float]]) -> float:
    (a, b), (c, d) = coerce_matrix(matrix)
    return a * d - b * c


def eigenpairs(
    matrix: Sequence[Sequence[float]],
) -> list[tuple[float, tuple[float, float]]]:
    """Real eigenvalue/eigenvector pairs of a 2x2, largest ``|lambda|`` first.

    Empty when the eigenvalues are complex — a rotation turns every direction,
    so there is nothing invariant to draw and saying so is the honest answer.

    Solved in closed form rather than by an iterative solver: for a 2x2 the
    characteristic polynomial is a quadratic, so the answer is exact up to
    floating point and identical on every machine, which an iterative method
    would not guarantee.
    """
    (a, b), (c, d) = coerce_matrix(matrix)

    # A scalar matrix scales every direction equally, so *every* direction is
    # invariant and the eigenspace is the whole plane. Falling through to the
    # general solve gets this wrong in a way that looks right: both repeated
    # roots take the already-diagonal branch, both return the x-axis, and the
    # duplicate is then removed — leaving one dashed line, which tells a viewer
    # the other directions do turn. Two independent directions is the smallest
    # honest answer; callers wanting to say "all of them" can check for it with
    # ``len(pairs) == 2 and pairs[0][0] == pairs[1][0]``.
    if abs(b) < 1e-12 and abs(c) < 1e-12 and abs(a - d) < 1e-12:
        return [(a, (1.0, 0.0)), (a, (0.0, 1.0))]

    trace = a + d
    det = a * d - b * c
    disc = trace * trace - 4.0 * det
    if disc < 0:
        return []

    root = math.sqrt(disc)
    values = [(trace + root) / 2.0, (trace - root) / 2.0]

    pairs: list[tuple[float, tuple[float, float]]] = []
    for lam in values:
        # (A - lambda I) v = 0. Rows [a-lam, b] and [c, d-lam] are proportional,
        # so either non-zero row gives the direction; pick the better-conditioned
        # one rather than a fixed choice, which divides by ~0 for some matrices.
        if abs(b) > 1e-12:
            vec = (b, lam - a)
        elif abs(c) > 1e-12:
            vec = (lam - d, c)
        elif abs(a - lam) < 1e-12:
            vec = (1.0, 0.0)      # already diagonal: this lambda is a's axis
        else:
            vec = (0.0, 1.0)
        norm = math.hypot(*vec)
        if norm < 1e-12:
            continue
        pairs.append((lam, (vec[0] / norm, vec[1] / norm)))

    # Repeated eigenvalue with a one-dimensional eigenspace lists one direction,
    # not two copies of it.
    if len(pairs) == 2 and _parallel(pairs[0][1], pairs[1][1]) and \
            abs(pairs[0][0] - pairs[1][0]) < 1e-9:
        pairs = pairs[:1]

    pairs.sort(key=lambda pair: -abs(pair[0]))
    return pairs


def span_dimension(vectors: Sequence[Sequence[float]]) -> int:
    """0, 1 or 2 — how much of the plane the given vectors reach.

    What makes a subspace picture correct: two vectors that happen to be
    parallel span a line, and drawing them as if they filled the plane is the
    error a "span" animation most easily makes.
    """
    nonzero = [v for v in coerce_vectors(vectors) if math.hypot(*v) > 1e-12]
    if not nonzero:
        return 0
    first = nonzero[0]
    for other in nonzero[1:]:
        if not _parallel(first, other):
            return 2
    return 1


# ------------------------------------------------------- the matrix product
#
# ``linear_map`` is about one matrix acting on the plane. This is about two
# matrices meeting, which is a different subject and the one students actually
# get wrong: AB is taught as a rule for filling in entries, and the three other
# readings of the same product — which are the ones that explain what a matrix
# product is *for* — are usually never shown at all.
#
# Two of those readings already exist in this repository as hardware examples.
# ``examples/systolic_array`` is the entry reading executed in silicon, and
# ``examples/tensor_parallel`` is the outer-product reading executed across
# devices ("A split by columns, B by rows" is exactly the rank-1 factorisation).
# Neither is reachable as a lesson, which is what this concept fixes.

#: The four readings, in teaching order: the rule, then what the rule means.
VIEWS = ("entry", "column", "row", "outer")

#: The largest product that fits. The scene solves its own cell size, so bigger
#: shapes shrink rather than overflow — but only up to a point: ``qc`` reports a
#: clean 4x4 and ten ``text_overlap`` errors at 5x5, where the bottom row of the
#: product reaches the running caption. ``examples/README.md`` argues the same
#: cap from the other direction: three stages and six microbatches carry the
#: point that thirty-two would.
MAX_DIM = 4

Grid = tuple[tuple[float, ...], ...]


@dataclass(frozen=True)
class Step:
    """One step of a product, under whichever reading was asked for.

    Uniform across all four views on purpose, so the scene builder draws one
    thing and the readings differ only in the steps handed to it — and so the
    correctness claim can be stated once, for every view at once:

        the contributions of a view's steps sum to ``A @ B``

    That is true of the partitions (entry, column, row fill disjoint parts of
    the product) and of the accumulation (outer adds four full-size rank-1
    terms), which is what makes them the same statement rather than four.
    """

    caption: str
    #: Cells read from A and from B, and cells of the product this step settles.
    a_cells: tuple[tuple[int, int], ...]
    b_cells: tuple[tuple[int, int], ...]
    out_cells: tuple[tuple[int, int], ...]
    #: Full-size, zero outside what this step contributes. Summing these over a
    #: view's steps reproduces the product; see :func:`check_view`.
    contribution: Grid


def coerce_grid(value: Any) -> Grid | None:
    """A rectangular, non-empty grid of floats, or ``None`` if it is not one.

    ``None`` rather than a fallback, unlike :func:`coerce_matrix`. A single map
    with no sensible value can default to the identity; a *product* cannot —
    substituting some other matrix here would animate arithmetic the caller
    never asked about, and the shapes have to agree for it to exist at all.
    """
    try:
        rows = [list(row) for row in value]
    except TypeError:
        return None
    if not rows or any(not isinstance(r, list) or not r for r in rows):
        return None
    width = len(rows[0])
    if any(len(r) != width for r in rows):
        return None
    try:
        return tuple(tuple(float(x) for x in row) for row in rows)
    except (TypeError, ValueError):
        return None


def shape(grid: Grid) -> tuple[int, int]:
    return (len(grid), len(grid[0]))


def matmul(a: Grid, b: Grid) -> Grid:
    """``A @ B`` by the definition, which is the thing every view is checked against.

    Deliberately the naive triple loop and deliberately stdlib. This is the
    reference the four readings are asserted to reproduce, so it has to be the
    boring one — a reference that shares a clever implementation with the thing
    it checks is not a reference.
    """
    (m, k), (k2, n) = shape(a), shape(b)
    if k != k2:
        raise ValueError(f"shapes {shape(a)} and {shape(b)} do not conform")
    return tuple(
        tuple(sum(a[i][t] * b[t][j] for t in range(k)) for j in range(n))
        for i in range(m)
    )


def _zeros(m: int, n: int) -> list[list[float]]:
    return [[0.0] * n for _ in range(m)]


def _frozen(grid: list[list[float]]) -> Grid:
    return tuple(tuple(row) for row in grid)


def steps_for(a: Grid, b: Grid, view: str) -> list[Step]:
    """The product broken into steps, read the way ``view`` asks.

    entry
        ``AB[i][j] = row_i(A) . col_j(B)``. The rule as taught: one entry at a
        time, and the only reading most students are ever given.
    column
        ``col_j(AB) = A . col_j(B)``. Each column of the product is A applied to
        the corresponding column of B — the reading that connects a product to
        ``linear_map``, because it is the same action, once per column.
    row
        ``row_i(AB) = row_i(A) . B``. Each row of the product is a combination of
        the rows of B, weighted by a row of A.
    outer
        ``AB = sum_k col_k(A) (x) row_k(B)``. The product as a sum of rank-1
        terms. This is the reading that explains low-rank approximation, and the
        one ``examples/tensor_parallel`` shards across devices.
    """
    (m, k), (_, n) = shape(a), shape(b)

    if view == "entry":
        out = []
        for i in range(m):
            for j in range(n):
                contribution = _zeros(m, n)
                contribution[i][j] = sum(a[i][t] * b[t][j] for t in range(k))
                terms = " + ".join("%s*%s" % (fmt(a[i][t]), fmt(b[t][j]))
                                   for t in range(k))
                out.append(Step(
                    caption="AB[%d][%d] = %s = %s" % (
                        i + 1, j + 1, terms, fmt(contribution[i][j])),
                    a_cells=tuple((i, t) for t in range(k)),
                    b_cells=tuple((t, j) for t in range(k)),
                    out_cells=((i, j),),
                    contribution=_frozen(contribution),
                ))
        return out

    if view == "column":
        out = []
        for j in range(n):
            contribution = _zeros(m, n)
            for i in range(m):
                contribution[i][j] = sum(a[i][t] * b[t][j] for t in range(k))
            out.append(Step(
                caption="column %d of AB = A times column %d of B" % (j + 1, j + 1),
                a_cells=tuple((i, t) for i in range(m) for t in range(k)),
                b_cells=tuple((t, j) for t in range(k)),
                out_cells=tuple((i, j) for i in range(m)),
                contribution=_frozen(contribution),
            ))
        return out

    if view == "row":
        out = []
        for i in range(m):
            contribution = _zeros(m, n)
            for j in range(n):
                contribution[i][j] = sum(a[i][t] * b[t][j] for t in range(k))
            out.append(Step(
                caption="row %d of AB = row %d of A times B" % (i + 1, i + 1),
                a_cells=tuple((i, t) for t in range(k)),
                b_cells=tuple((t, j) for t in range(k) for j in range(n)),
                out_cells=tuple((i, j) for j in range(n)),
                contribution=_frozen(contribution),
            ))
        return out

    if view == "outer":
        out = []
        for t in range(k):
            contribution = _zeros(m, n)
            for i in range(m):
                for j in range(n):
                    contribution[i][j] = a[i][t] * b[t][j]
            out.append(Step(
                caption="column %d of A (x) row %d of B  (rank 1)" % (t + 1, t + 1),
                a_cells=tuple((i, t) for i in range(m)),
                b_cells=tuple((t, j) for j in range(n)),
                out_cells=tuple((i, j) for i in range(m) for j in range(n)),
                contribution=_frozen(contribution),
            ))
        return out

    raise ValueError("unknown view %r; expected one of %r" % (view, VIEWS))


def check_view(a: Grid, b: Grid, view: str) -> Grid:
    """Run the view's own rule and verify it reproduces ``A @ B``. Returns it.

    The rule this repository's examples follow — *simulate the mechanism, assert
    the claim, then animate the simulation* — applied to a lesson rather than to
    a dataflow. The animation's whole claim is that four different-looking
    procedures compute the same product, so the builder computes all four and
    refuses to emit a scene where one of them does not.
    """
    total = _zeros(*shape(matmul(a, b)))
    for step in steps_for(a, b, view):
        for i, row in enumerate(step.contribution):
            for j, value in enumerate(row):
                total[i][j] += value
    got, want = _frozen(total), matmul(a, b)
    if any(abs(g - w) > 1e-9 for gr, wr in zip(got, want) for g, w in zip(gr, wr)):
        raise ValueError(
            "the %r view does not reproduce A @ B: %r vs %r" % (view, got, want))
    return want


def fmt(value: float) -> str:
    """A number as a lesson would write it: ``2`` not ``2.00``, ``-1.5`` not ``-1.50``.

    Shared so a value in a caption and the same value in a cell cannot be
    formatted two ways, which is the sort of mismatch a viewer reads as an
    error in the arithmetic.
    """
    text = "%.2f" % value
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text



# ------------------------------------------------------------------ internals


def _coerce_vector(value: Any) -> tuple[float, float] | None:
    try:
        parts = list(value)
        if len(parts) != 2:
            return None
        return (float(parts[0]), float(parts[1]))
    except (TypeError, ValueError):
        return None


def _parallel(u: Sequence[float], v: Sequence[float]) -> bool:
    return abs(u[0] * v[1] - u[1] * v[0]) < 1e-9


def _is_identity(raw: Any) -> bool:
    try:
        rows = [list(row) for row in raw]
        return [[float(x) for x in row] for row in rows] == [[1.0, 0.0], [0.0, 1.0]]
    except (TypeError, ValueError):
        return False


@topic(Topic.LINEAR_ALGEBRA, priority=0,
       keywords=("线性变换", "线性代数", "矩阵变换", "特征值", "特征向量",
              "张成", "基底", "行列式", "eigen", "eigenvalue", "eigenvector",
              "span", "basis", "determinant", "linear map", "linear transformation",
              "矩阵乘法", "矩阵相乘", "矩阵乘积", "外积", "秩一", "内积视角",
              "matmul", "matrix multiplication", "matrix product", "outer product",
              "rank-1", "rank one"))
class LinearAlgebra:
    """One matrix acting on the plane, or two matrices meeting."""

    concepts = ConceptLinAlg
