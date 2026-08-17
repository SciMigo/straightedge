"""Tensor parallelism: why A is split by columns and B by rows.

Every explainer of Megatron-style tensor parallelism shows the same two boxes
labelled "column parallel" and "row parallel", and treats the pairing as a
convention you memorise. It is not a convention. It is the only pairing that
lets an MLP block cross the network **once**, and the reason is the
nonlinearity between the two matmuls.

The block is::

    Y = f(X @ A) @ B          f elementwise (GeLU in Megatron; ReLU here,
                              because the argument is identical and the
                              numbers stay readable)

Split ``A`` by **columns**. Rank ``r`` holds ``A[:, c_r]`` and computes
``H_r = f(X @ A[:, c_r])`` — a *complete* answer for its own slice of the hidden
dimension, because ``f`` is elementwise and a column of ``X @ A`` depends on one
column of ``A`` and nothing else. No communication. Now split ``B`` by **rows**
along the same partition. Rank ``r`` holds ``B[c_r, :]`` and computes
``Y_r = H_r @ B[c_r, :]``: full-size, but a partial sum. One all-reduce over
``Y`` finishes the block.

    total collectives per block: **one**

Split ``A`` by rows instead and every step of that breaks. ``X_r @ A_r`` is a
partial sum of ``X @ A``, so the ranks must all-reduce *before* ``f`` can be
applied — and they cannot skip it and apply ``f`` locally, because

    f(a + b)  ≠  f(a) + f(b)

for any nonlinearity worth having. That is the whole argument, and this module
executes it: the wrong pairing is run alongside the right one and asserted to
disagree, so the claim on screen is a claim the code has checked rather than one
a script author remembered.

The waste is not marginal, either. The tensor the good pairing avoids sending is
the *hidden* activation, and in a real transformer the FFN dimension is 4x the
model dimension — so the collective you skip is four times the size of the one
you keep. Asserted below at both toy and realistic dimensions.

    manim -qm scene.py TensorParallel
"""

from __future__ import annotations

import numpy as np
from manim import (
    DOWN, LEFT, RIGHT, UP,
    FadeIn, FadeOut, Flash, Transform, Write,
    Scene, VGroup,
    Arrow, Rectangle, Text,
)

import sys
from pathlib import Path

# The layout check lives one directory up, shared by every example. Python puts
# this file's directory on the path, not examples/, so it needs saying.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _layout import STYLE as S, assert_readable

# --- the block -------------------------------------------------------------

#: Two tokens, model dim 3, FFN dim 4. Small enough to read at 200px wide, and
#: chosen so ``X @ A`` has negative entries: the ReLU has to visibly *do*
#: something, or a viewer can believe the nonlinearity is decoration.
X = np.array([[1, 2, -1],
              [0, 1,  2]])
A = np.array([[ 2, -1,  1,  0],
              [ 1,  2, -1,  1],
              [-1,  1,  2,  1]])
B = np.array([[ 1,  0,  2],
              [ 2,  1, -1],
              [ 0,  1,  1],
              [ 1, -1,  0]])

RANKS = 2
D_MODEL, D_FFN = A.shape


def relu(t: np.ndarray) -> np.ndarray:
    """The nonlinearity. Elementwise — which is the property the split exploits."""
    return np.maximum(t, 0)


PRE = X @ A                  # before the nonlinearity
H = relu(PRE)                # the hidden activation, on one device
Y = H @ B                    # the answer every arrangement below must reproduce


def shards(width: int, ranks: int) -> list[np.ndarray]:
    """Contiguous index blocks over the FFN dimension, one per rank."""
    return np.array_split(np.arange(width), ranks)


# --- the right pairing: column-parallel A, row-parallel B -------------------


def column_row_parallel(ranks: int) -> tuple[np.ndarray, list[dict], list[dict]]:
    """Run the block the Megatron way and record every collective.

    Returns the summed output, the per-rank intermediates (for the animation),
    and the communication log. The log is what the byte counts on screen are
    counted from — stating "one all-reduce" is only worth anything if the number
    comes from the run.
    """
    per_rank, comm = [], []
    for r, cols in enumerate(shards(D_FFN, ranks)):
        h = relu(X @ A[:, cols])          # complete for these columns: no comm
        y = h @ B[cols, :]                # full size, partial sum
        per_rank.append({"rank": r, "cols": cols, "h": h, "y": y})
    # One collective, at the end of the block, over the output activation.
    comm.append({"op": "all-reduce", "tensor": "Y", "shape": Y.shape,
                 "elements": int(Y.size)})
    total = sum(p["y"] for p in per_rank)
    return total, per_rank, comm


TOTAL, PER_RANK, COMM = column_row_parallel(RANKS)

# The claim the animation makes, checked before a frame is drawn.
assert np.array_equal(TOTAL, Y), "the partial sums must reproduce the single-device Y"
assert len(COMM) == 1, "a column/row-parallel MLP block crosses the network once"

# And not by luck of picking two ranks: every split of the FFN dimension works,
# because the argument is about which axis is sharded, not how finely.
for _r in (1, 2, 4):
    _total, _parts, _comm = column_row_parallel(_r)
    assert np.array_equal(_total, Y), f"{_r} ranks gave the wrong answer"
    assert len(_comm) == 1, f"{_r} ranks needed more than one collective"
    # Each rank's hidden slice is exactly its columns of the true H — the
    # property that makes the pre-nonlinearity all-reduce unnecessary.
    for _p in _parts:
        assert np.array_equal(_p["h"], H[:, _p["cols"]]), "hidden slice is wrong"


# --- the wrong pairing: row-parallel A --------------------------------------


def row_parallel_first_layer(ranks: int) -> tuple[np.ndarray, np.ndarray, list[dict]]:
    """Split ``A`` by rows, and watch the block need two collectives.

    ``X_r @ A_r`` is a partial sum of the whole ``X @ A``, so nothing elementwise
    can be applied to it yet. Returns what a correct implementation gets (after
    paying for an extra all-reduce) and what skipping that all-reduce would
    produce, which is the interesting one because it is *wrong* rather than slow.
    """
    comm = []
    partials = [X[:, rows] @ A[rows, :] for rows in shards(D_MODEL, ranks)]

    # Correct, but it costs a collective over the hidden activation — the big
    # tensor, the one the column split never sends.
    comm.append({"op": "all-reduce", "tensor": "X@A", "shape": PRE.shape,
                 "elements": int(PRE.size)})
    correct = relu(sum(partials)) @ B
    comm.append({"op": "all-reduce", "tensor": "Y", "shape": Y.shape,
                 "elements": int(Y.size)})

    # What you get if you try to avoid that collective by applying the
    # nonlinearity to a partial sum. This is the number that shows the pairing
    # is forced rather than conventional.
    skipped = sum(relu(p) for p in partials)
    return correct, skipped, comm


ROW_CORRECT, ROW_SKIPPED, ROW_COMM = row_parallel_first_layer(RANKS)

assert np.array_equal(ROW_CORRECT, Y), "with both collectives, a row split is correct"
assert len(ROW_COMM) == 2, "a row-parallel first layer needs a collective mid-block"
# The load-bearing assertion of this example: skipping the mid-block all-reduce
# does not merely lose precision, it computes something else entirely.
assert not np.array_equal(ROW_SKIPPED, H), (
    "sum(relu(partials)) must differ from relu(sum(partials)), or the whole "
    "argument for the column/row pairing collapses"
)
WRONG_ENTRIES = int(np.count_nonzero(ROW_SKIPPED != H))
assert WRONG_ENTRIES > 0

# --- what the pairing saves -------------------------------------------------

KEPT = sum(c["elements"] for c in COMM)              # column/row: Y only
PAID = sum(c["elements"] for c in ROW_COMM)          # row-parallel: X@A and Y
assert PAID > KEPT, "the good pairing must move less"

# At real dimensions the avoided tensor is the larger one, because the FFN
# dimension is a multiple of the model dimension. Checked over the ratios that
# actually ship rather than asserted from the toy shapes above.
for _mult in (2, 4, 8):
    _tokens, _d = 1024, 4096
    _kept = _tokens * _d                             # the output activation
    _extra = _tokens * _d * _mult                    # the hidden activation
    assert _extra == _kept * _mult
    assert _extra > _kept, "the collective avoided is the bigger one"

FFN_MULTIPLE = 4          # the ratio a real transformer uses, for the closing line


# --- drawing ----------------------------------------------------------------

CELL_W, CELL_H = 0.54, 0.46
RANK_COLOR = (S.flow, S.hold)       # rank 0, rank 1 — the two shard colours


def matrix(values: np.ndarray, *, name: str, color: str | None = None,
           column_colors: list[str] | None = None,
           row_colors: list[str] | None = None,
           fill: float | None = None) -> VGroup:
    """A labelled grid of numbers, with a handle on every cell.

    ``column_colors`` / ``row_colors`` tint per column or per row, which is how
    the two shardings are shown: the same matrix, cut two different ways. The
    returned group carries ``.cells`` so a later beat can recolour one entry
    without rebuilding the matrix and losing its position, and ``.grid`` so a
    caller can centre on the numbers rather than on the numbers *plus* a caption
    whose width it did not choose.
    """
    grid = VGroup()
    cells: dict[tuple[int, int], VGroup] = {}
    rows, cols = values.shape
    for i in range(rows):
        for j in range(cols):
            tint = color or S.rule
            if column_colors is not None:
                tint = column_colors[j]
            elif row_colors is not None:
                tint = row_colors[i]
            box = Rectangle(
                width=CELL_W, height=CELL_H,
                stroke_color=tint, stroke_width=S.width.hairline,
                fill_color=tint if tint != S.rule else S.well,
                fill_opacity=S.opacity.tint if fill is None else fill,
            )
            box.move_to([(j - (cols - 1) / 2) * CELL_W,
                         ((rows - 1) / 2 - i) * CELL_H, 0])
            label = Text(f"{values[i][j]}", font_size=S.size.tiny, color=S.muted)
            cell = VGroup(box, label.move_to(box.get_center()))
            cells[(i, j)] = cell
            grid.add(cell)

    tag = Text(name, font_size=S.size.small, color=S.dim)
    tag.next_to(grid, UP, buff=0.11)
    group = VGroup(grid, tag)
    group.cells = cells          # type: ignore[attr-defined]
    group.grid = grid            # type: ignore[attr-defined]
    return group


def centre_grids_at(group: VGroup, grids: VGroup, x: float, y: float) -> None:
    """Move ``group`` so its *grids* sit at (x, y), captions notwithstanding.

    Arranging by bounding box centres the captions too, and a matrix whose tag
    is six words longer than its neighbour's then sits visibly off-axis. The
    numbers are what a viewer aligns against, so the numbers are what is placed.
    """
    at = grids.get_center()
    group.shift([x - at[0], y - at[1], 0])


class TensorParallel(Scene):
    """One MLP block, split across two ranks, crossing the network once."""

    def construct(self) -> None:
        self.camera.background_color = S.ink

        title = Text("Tensor parallelism", font_size=S.size.title, color=S.fg,
                     weight="BOLD").to_edge(UP, buff=0.24)
        sub = Text("A by columns, B by rows — the only pairing that crosses "
                   "the network once",
                   font_size=S.size.body, color=S.dim).next_to(title, DOWN, buff=0.10)
        self.play(Write(title), FadeIn(sub))

        self._act_one_the_paired_split()
        self._act_two_each_rank_runs()
        self._act_three_one_all_reduce()
        self._act_four_why_not_rows()

        assert_readable(self)

    # -- act 1: the split is paired -----------------------------------------

    def _act_one_the_paired_split(self) -> None:
        """A cut by columns, B cut by rows, in the same two colours.

        Drawn together and in one shot, because the pairing is the fact — shown
        one at a time it reads as two independent decisions.
        """
        col_tint = [RANK_COLOR[0]] * 2 + [RANK_COLOR[1]] * 2
        x = matrix(X, name="X   (2 tokens x 3)")
        a = matrix(A, name="A   (3x4)   split by columns", column_colors=col_tint)
        b = matrix(B, name="B   (4x3)   split by rows", row_colors=col_tint)

        row = VGroup(x, a, b).arrange(RIGHT, buff=1.15)
        centre_grids_at(row, VGroup(x.grid, a.grid, b.grid), 0.0, 0.35)
        self.play(FadeIn(x), run_time=0.5)
        self.play(FadeIn(a), FadeIn(b), run_time=0.9)

        note = Text("the same partition, both times — rank 0 owns A's first two "
                    "columns and B's first two rows",
                    font_size=S.size.label, color=S.muted)
        note.next_to(row, DOWN, buff=0.44)
        self.play(FadeIn(note))
        self.wait(1.4)
        self.play(FadeOut(row), FadeOut(note), run_time=0.5)

    # -- act 2: local work, no communication --------------------------------

    def _act_two_each_rank_runs(self) -> None:
        """Both ranks compute a complete hidden slice, then a partial output."""
        panels, self.partial_outputs, keep_out = VGroup(), [], VGroup()
        for part in PER_RANK:
            r = part["rank"]
            tint = RANK_COLOR[r]
            a_shard = matrix(A[:, part["cols"]], name=f"A[:, {r}]", color=tint)
            h = matrix(part["h"], name=f"relu(X @ A_{r})", color=tint,
                       fill=S.opacity.panel)
            b_shard = matrix(B[part["cols"], :], name=f"B[{r}, :]", color=tint)
            y = matrix(part["y"], name=f"Y_{r}   (partial)", color=tint,
                       fill=S.opacity.panel)

            chain = VGroup(a_shard, h, b_shard, y).arrange(RIGHT, buff=0.68)
            tag = Text(f"rank {r}", font_size=S.size.small, color=tint,
                       weight="BOLD")
            tag.next_to(chain, LEFT, buff=0.36)
            panels.add(VGroup(tag, chain))
            self.partial_outputs.append(y)
            # Everything except the partial output, which act three keeps.
            keep_out.add(tag, a_shard, h, b_shard)

        panels.arrange(DOWN, buff=0.70).move_to([0.0, -0.30, 0])
        self.play(FadeIn(panels), run_time=1.1)
        self.chain_scaffolding = keep_out

        quiet = Text("no communication yet — relu is elementwise, so a column "
                     "shard of the hidden dim is self-contained",
                     font_size=S.size.label, color=S.done)
        quiet.to_edge(DOWN, buff=0.30)
        self.play(Write(quiet), run_time=1.2)
        self.wait(1.4)
        self.play(FadeOut(quiet), run_time=0.4)

    # -- act 3: the single collective ---------------------------------------

    def _act_three_one_all_reduce(self) -> None:
        """Add the two partials and check the result against one device.

        Drawn as an equation rather than as arrows into a corner. An all-reduce
        of partial sums *is* an addition, and the first version of this beat —
        two long arrows from the rank rows down to a result — had them crossing
        the matrices they came from, which made the picture about the arrows.
        """
        y0, y1 = self.partial_outputs
        answer = matrix(TOTAL, name="Y   after one all-reduce", color=S.done,
                        fill=S.opacity.panel)
        plus = Text("+", font_size=S.size.heading, color=S.muted)
        equals = Text("=", font_size=S.size.heading, color=S.muted)

        # The scaffolding goes first, so the equation has the frame to itself.
        self.play(FadeOut(self.chain_scaffolding), run_time=0.5)

        # Lay out a ghost row to find the positions, then move the real partials
        # into them. The ghosts are never added to the scene.
        ghost0, ghost1 = y0.copy(), y1.copy()
        row = VGroup(ghost0, plus, ghost1, equals, answer).arrange(RIGHT, buff=0.52)
        centre_grids_at(row, VGroup(ghost0.grid, ghost1.grid, answer.grid), 0.0, -0.20)

        self.play(y0.animate.move_to(ghost0.get_center()),
                  y1.animate.move_to(ghost1.get_center()),
                  FadeIn(plus), FadeIn(equals), run_time=0.9)
        self.play(FadeIn(answer), run_time=0.7)

        # The assertion already ran at import; the flash is where the viewer gets
        # to check it, so it points at the cells rather than at a caption.
        self.play(*[Flash(cell.get_center(), color=S.done, line_length=0.11,
                          num_lines=8, flash_radius=CELL_W * 0.60, run_time=0.7)
                    for cell in answer.cells.values()])

        verdict = Text(f"identical to the single-device Y   ·   {len(COMM)} "
                       f"collective, {KEPT} elements across the wire",
                       font_size=S.size.body, color=S.done, weight="BOLD")
        verdict.to_edge(DOWN, buff=0.34)
        self.play(Write(verdict), run_time=1.0)
        self.wait(1.6)
        self.play(FadeOut(VGroup(y0, y1, plus, equals, answer, verdict)),
                  run_time=0.6)

    # -- act 4: why the other pairing is not an option -----------------------

    def _act_four_why_not_rows(self) -> None:
        """Run the row split with the mid-block collective skipped, and compare.

        The wrong matrix is drawn *neutral* and only the disagreeing cells are
        marked. Colouring the whole thing red states the conclusion instead of
        showing it — and "4 of 8 entries are wrong" is a claim the viewer should
        be able to count off the screen.
        """
        heading = Text("so why not split A by rows?", font_size=S.size.heading,
                       color=S.fg, weight="BOLD")
        heading.move_to([0, 2.20, 0])
        because = Text("because X_r @ A_r is a partial sum, and relu of a "
                       "partial sum is not a partial sum of relu",
                       font_size=S.size.label, color=S.dim)
        because.next_to(heading, DOWN, buff=0.18)
        self.play(Write(heading), FadeIn(because))

        right = matrix(H, name="relu(X @ A)   —   correct", color=S.done,
                       fill=S.opacity.tint)
        wrong = matrix(ROW_SKIPPED,
                       name="sum of relu(X_r @ A_r)   —   all-reduce skipped")
        pair = VGroup(right, wrong).arrange(RIGHT, buff=1.6)
        centre_grids_at(pair, VGroup(right.grid, wrong.grid), 0.0, -0.05)
        self.play(FadeIn(right), run_time=0.6)
        self.play(FadeIn(wrong), run_time=0.6)
        self.wait(0.5)

        # Mark exactly the cells the two disagree on, read from the arrays — so a
        # change to the numbers at the top of this file cannot leave a stale
        # annotation behind.
        marks = []
        for (i, j), cell in wrong.cells.items():
            if ROW_SKIPPED[i][j] != H[i][j]:
                marks.append(cell[0].animate
                             .set_stroke(S.warn, S.width.mark)
                             .set_fill(S.warn, S.opacity.tint))
                marks.append(cell[1].animate.set_color(S.fg))
                marks.append(Flash(cell.get_center(), color=S.warn,
                                   line_length=0.13, num_lines=10,
                                   flash_radius=CELL_W * 0.66, run_time=0.8))
        self.play(*marks)

        lines = VGroup(
            Text(f"{WRONG_ENTRIES} of {H.size} entries are simply wrong",
                 font_size=S.size.body, color=S.warn, weight="BOLD"),
            Text(f"a row split can be made correct — for a second all-reduce, "
                 f"{PAID} elements against {KEPT}",
                 font_size=S.size.label, color=S.muted),
            Text(f"and the tensor it adds is the hidden one, which a real "
                 f"transformer makes {FFN_MULTIPLE}x the size of the output",
                 font_size=S.size.label, color=S.hold),
        ).arrange(DOWN, buff=0.15).to_edge(DOWN, buff=0.30)

        self.play(Write(lines[0]), run_time=0.9)
        self.wait(0.5)
        self.play(FadeIn(lines[1]))
        self.wait(0.4)
        self.play(FadeIn(lines[2]))
        self.wait(2.0)
