"""Weight-stationary systolic array, animated one cycle at a time.

Every systolic-array explainer on YouTube draws the same picture: a static grid
with numbers sliding in diagonally, a 2x2 example, and a cut to the next topic.
The thing that actually needs seeing is never shown — *why the diagonal skew is
there*, and what the array buys you: each weight is fetched from SRAM once and
then reused for the whole activation stream, while each activation is fetched
once and reused across the whole row of outputs.

So this scene is cycle-accurate rather than illustrative. Nothing moves that a
real weight-stationary array would not move on that cycle, and the value in
every cell is the value that would be there.

    Y = A @ B,   A streams in from the left,   B sits still in the PEs

Indexing, which is the part that goes wrong when this is hand-waved:

* ``PE(k, j)`` holds the stationary weight ``B[k][j]``.
* Activation ``A[m][k]`` enters row ``k`` from the left and moves one cell right
  per cycle, so it reaches column ``j`` at cycle ``m + k + j``.
* Partial sums move one cell *down* per cycle. The psum for output ``Y[m][j]``
  is at row ``k`` on exactly the cycle when ``A[m][k]`` arrives there — which is
  the whole trick, and the reason row ``k`` of the stream is delayed by ``k``.
* ``Y[m][j]`` leaves the bottom of column ``j`` at cycle ``m + K + j``.

The result is asserted against ``A @ B`` at import time, so a scene that renders
is a scene whose arithmetic is right.

    manim -qm scene.py SystolicArray
"""

from __future__ import annotations

import numpy as np
from manim import (
    DOWN, LEFT, RIGHT, UP, ORIGIN,
    Create, FadeIn, FadeOut, Flash, Indicate, Transform, Write,
    AnimationGroup, Scene, VGroup,
    RoundedRectangle, Square, Text, Line, Arrow,
)

import sys
from pathlib import Path

# The layout check lives one directory up, shared by every example. Python puts
# this file's directory on the path, not examples/, so it needs saying.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _layout import STYLE as S, assert_readable

# --- the problem -----------------------------------------------------------

A = np.array([[1, 2, 3],
              [4, 5, 6],
              [7, 8, 9]])          # activations: one row enters per cycle
B = np.array([[1, 0, 2],
              [0, 1, 1],
              [2, 1, 0]])          # weights: loaded once, never move
Y = A @ B
M, K = A.shape
_, N = B.shape

# --- palette ---------------------------------------------------------------

# The style names visual roles; this scene names what they mean here. `S.hold` is
# whatever the blue's counterpart is in a given picture — in this one it is a
# weight that never moves, which is why the alias exists rather than a token
# called `weight` that two of the other three examples would have to misuse.
WEIGHT = S.hold           # amber: stationary
ACT = S.flow              # blue: streaming right
PSUM = S.done             # green: falling down
DIM = S.dim
HOT = S.warn

CELL = 1.16               # PE pitch, in scene units
ARRAY_AT = np.array([-1.35, -0.45, 0.0])   # centre of the PE grid
RESULT_AT = np.array([4.35, -0.45, 0.0])   # centre of the Y matrix
INPUT_AT = np.array([-5.45, -0.45, 0.0])   # centre of the A matrix
RCELL = 0.86              # pitch of the result matrix
ACELL = 0.78              # pitch of the input matrix

#: Where the three things inside a PE live, so they never share a spot: the
#: weight is a badge in the corner, the activation passes through the middle,
#: and the running sum hangs off the lower edge on its way down.
W_OFFSET = np.array([-0.40, 0.38, 0.0])
A_OFFSET = np.array([-0.02, 0.02, 0.0])
P_OFFSET = np.array([0.30, -0.34, 0.0])


def _cell_center(row: int, col: int) -> np.ndarray:
    """Scene position of PE(row, col)."""
    x = (col - (N - 1) / 2) * CELL
    y = ((K - 1) / 2 - row) * CELL
    return ARRAY_AT + np.array([x, y, 0.0])


def _result_slot(m: int, j: int) -> np.ndarray:
    """Where Y[m][j] belongs in the result matrix."""
    x = (j - (N - 1) / 2) * RCELL
    y = ((M - 1) / 2 - m) * RCELL
    return RESULT_AT + np.array([x, y, 0.0])


def _input_slot(m: int, k: int) -> np.ndarray:
    """Where A[m][k] sits in the input matrix on the left."""
    x = (k - (K - 1) / 2) * ACELL
    y = ((M - 1) / 2 - m) * ACELL
    return INPUT_AT + np.array([x, y, 0.0])


def _chip(value: int, color: str, width: int = 1) -> VGroup:
    """A moving datum: a rounded tile with its value.

    ``width`` pads the number with leading zeros. That is not decoration: a
    Manim ``Transform`` zips the two mobjects' families, so "0" -> "16" raises
    rather than animating. Fixed-width digits keep every psum tile the same
    shape, and a zero-padded register is what the hardware would show anyway.
    """
    box = RoundedRectangle(
        width=0.56, height=0.52, corner_radius=0.11,
        stroke_color=color, stroke_width=S.width.chip,
        fill_color=color, fill_opacity=0.20,
    )
    label = Text(f"{value:0{width}d}", font_size=S.size.body, color=S.fg,
                 weight="BOLD")
    return VGroup(box, label.move_to(box.get_center()))


class SystolicArray(Scene):
    """Y = A @ B on a 3x3 weight-stationary array, cycle by cycle."""

    def construct(self) -> None:
        self.camera.background_color = S.ink

        title = Text("Weight-stationary systolic array", font_size=S.size.title,
                     color=S.fg, weight="BOLD").to_edge(UP, buff=0.45)
        subtitle = Text("the weights never move — the data flows past them",
                        font_size=22, color=DIM).next_to(title, DOWN, buff=0.18)
        self.play(Write(title), FadeIn(subtitle, shift=UP * 0.1))

        in_cells, in_numbers, in_caption = self._build_inputs()
        self.play(Create(in_cells), FadeIn(in_caption), run_time=0.9)
        self.play(AnimationGroup(*[FadeIn(n, scale=0.7) for n in in_numbers.values()],
                                 lag_ratio=0.05))

        grid, weight_labels = self._build_grid()
        weight_caption = Text("B  loaded once, then still", font_size=20,
                              color=WEIGHT, weight="BOLD")
        self.play(Create(grid), run_time=1.0)
        self.play(AnimationGroup(*[FadeIn(w, scale=0.6) for w in weight_labels],
                                 lag_ratio=0.06))
        weight_caption.next_to(grid, UP, buff=0.26)
        self.play(FadeIn(weight_caption))

        # Weights are loaded once. Say it while it is visibly true.
        legend = self._legend()
        legend.next_to(subtitle, DOWN, buff=0.30)
        self.play(FadeIn(legend))

        slots, caption = self._build_result()
        self.play(Create(slots), FadeIn(caption), run_time=0.8)

        cycle_label = Text("cycle 00", font_size=S.size.display, color=S.fg,
                           weight="BOLD")
        cycle_label.to_corner(UP + LEFT, buff=0.6)
        self.play(FadeIn(cycle_label))

        self._run(grid, cycle_label, in_numbers)

        self.wait(0.6)

        assert_readable(self)

    def _legend(self) -> VGroup:
        """What the three colours mean, said once and left on screen."""
        row = VGroup()
        for color, caption in ((WEIGHT, "weight · stays put"),
                               (ACT, "activation · moves right"),
                               (PSUM, "partial sum · moves down")):
            swatch = RoundedRectangle(width=0.26, height=0.26, corner_radius=0.06,
                                      stroke_color=color, stroke_width=S.width.accent,
                                      fill_color=color, fill_opacity=0.35)
            label = Text(caption, font_size=S.size.label, color=S.muted)
            row.add(VGroup(swatch, label.next_to(swatch, RIGHT, buff=0.13)))
        return row.arrange(RIGHT, buff=0.75)

    # -- construction -------------------------------------------------------

    def _build_grid(self) -> tuple[VGroup, list[Text]]:
        cells, labels = VGroup(), []
        for k in range(K):
            for j in range(N):
                square = Square(side_length=CELL * 0.92)
                square.set_stroke(S.rule, S.width.accent).set_fill(S.well, 0.35)
                square.move_to(_cell_center(k, j))
                cells.add(square)
                # A badge in the corner, not a number in the middle: the middle
                # is a thoroughfare, and a weight drawn there is hidden by the
                # first activation that passes over it.
                w = Text(str(B[k][j]), font_size=22, color=WEIGHT, weight="BOLD")
                labels.append(w.move_to(_cell_center(k, j) + W_OFFSET))
        return cells, labels

    def _build_inputs(self) -> tuple[VGroup, dict[tuple[int, int], Text], VGroup]:
        """The activation matrix, drawn where the data comes from.

        Without it the streaming tiles are unlabelled numbers appearing from
        off-screen. With it, the entries that light up on cycle t are exactly
        the anti-diagonal m + k = t — so the skew explains itself.
        """
        cells, numbers = VGroup(), {}
        for m in range(M):
            for k in range(K):
                cell = Square(side_length=ACELL * 0.86)
                cell.set_stroke(S.rule, 1.6).set_fill(S.well, S.opacity.tint)
                cell.move_to(_input_slot(m, k))
                cells.add(cell)
                num = Text(str(A[m][k]), font_size=22, color=ACT, weight="BOLD")
                numbers[(m, k)] = num.move_to(_input_slot(m, k))
        caption = Text("A  streams in", font_size=20, color=ACT, weight="BOLD")
        caption.next_to(cells, UP, buff=0.26)
        return cells, numbers, VGroup(caption)

    def _build_result(self) -> tuple[VGroup, VGroup]:
        """Empty slots for Y, so the viewer can watch it fill in."""
        slots, frame = VGroup(), VGroup()
        for m in range(M):
            for j in range(N):
                slot = Square(side_length=RCELL * 0.86)
                slot.set_stroke(S.rule, 1.6).set_fill(S.well, S.opacity.tint)
                slot.move_to(_result_slot(m, j))
                slots.add(slot)
        caption = Text("Y = A · B", font_size=22, color=PSUM, weight="BOLD")
        caption.next_to(slots, UP, buff=0.28)
        frame.add(caption)
        return slots, frame

    # -- the schedule -------------------------------------------------------

    def _run(self, grid: VGroup, cycle_label: Text,
             in_numbers: dict[tuple[int, int], Text]) -> None:
        """One animation group per cycle, driven by the real dataflow.

        ``act[(m, k)]`` is the chip carrying A[m][k]; it exists from the cycle it
        enters row k until it falls off the right edge. ``psum[(m, j)]`` is the
        running total for Y[m][j], created above the array and moved down one row
        per cycle. Both are keyed by what they *are*, not by where they are, so
        the positions below are derived rather than tracked by hand.
        """
        last_cycle = M - 1 + K - 1 + N - 1 + 1
        act: dict[tuple[int, int], VGroup] = {}
        psum: dict[tuple[int, int], VGroup] = {}
        psum_value: dict[tuple[int, int], int] = {}
        outputs: list[VGroup] = []

        for cycle in range(last_cycle + 1):
            moves, births, deaths, flashes = [], [], [], []

            # 1. Activations that enter this cycle: A[m][k] enters row k at
            #    cycle m + k, which is exactly the diagonal skew.
            for m in range(M):
                for k in range(K):
                    if m + k == cycle:
                        # The chip is the entry leaving A: fly it out of its
                        # slot rather than fading it in from nowhere, and dim
                        # the slot behind it so "already sent" is legible.
                        chip = _chip(int(A[m][k]), ACT)
                        chip.move_to(_input_slot(m, k))
                        act[(m, k)] = chip
                        births.append(FadeIn(chip, scale=0.7))
                        moves.append(chip.animate.move_to(
                            _cell_center(k, -1) + A_OFFSET))
                        # Flash the slot, not the number: Indicate restores the
                        # mobject it animates, which silently undid the dimming
                        # queued in the same play — the matrix never faded.
                        flashes.append(Flash(_input_slot(m, k), color=ACT,
                                             line_length=0.12, num_lines=10,
                                             flash_radius=ACELL * 0.5,
                                             run_time=0.5))
                        deaths.append(in_numbers[(m, k)].animate
                                      .set_color(DIM).set_opacity(0.35))

            # 2. Partial sums that start this cycle: the psum for Y[m][j] is
            #    born above column j so that it reaches row k when A[m][k] does.
            for m in range(M):
                for j in range(N):
                    if m + j == cycle:
                        chip = _chip(0, PSUM, width=2)
                        chip.move_to(_cell_center(-1, j) + P_OFFSET)
                        psum[(m, j)] = chip
                        psum_value[(m, j)] = 0
                        births.append(FadeIn(chip, shift=DOWN * 0.3))

            # 3. Everything that is inside the array on this cycle moves one
            #    step, and every coincidence of an activation and a psum in the
            #    same PE is a multiply-accumulate.
            for (m, k), chip in list(act.items()):
                col = cycle - m - k - 1        # where it is now
                if col >= N:                   # it has left the array
                    deaths.append(FadeOut(chip, shift=RIGHT * 0.4))
                    del act[(m, k)]
                    continue
                moves.append(chip.animate.move_to(_cell_center(k, col + 1) + A_OFFSET))

            for (m, j), chip in list(psum.items()):
                row = cycle - m - j - 1
                if row >= K:                   # it is the finished output
                    continue
                target = row + 1
                if target < K:
                    contribution = int(A[m][target] * B[target][j])
                    psum_value[(m, j)] += contribution
                    new = _chip(psum_value[(m, j)], PSUM, width=2)
                    new.move_to(_cell_center(target, j) + P_OFFSET)
                    moves.append(Transform(chip, new))
                    flashes.append(Flash(_cell_center(target, j), color=HOT,
                                         line_length=0.16, num_lines=10,
                                         flash_radius=CELL * 0.55, run_time=0.45))
                else:
                    # Out of the bottom: this psum is Y[m][j], complete.
                    assert psum_value[(m, j)] == Y[m][j], (
                        f"cycle {cycle}: Y[{m}][{j}] came out "
                        f"{psum_value[(m, j)]}, expected {Y[m][j]}"
                    )
                    # Finished sums fly to their slot in Y rather than piling
                    # up under the array, where two outputs of the same column
                    # landed on top of each other.
                    final = _chip(psum_value[(m, j)], PSUM, width=2)
                    final.move_to(_result_slot(m, j))
                    moves.append(Transform(chip, final))
                    outputs.append(chip)
                    del psum[(m, j)]

            # Zero-padded for the same reason the psum tiles are: a Transform
            # between Texts of different glyph counts mangles the label.
            new_label = Text(f"cycle {cycle:02d}", font_size=S.size.display,
                             color=S.fg, weight="BOLD").move_to(cycle_label)
            steps = births + moves + deaths
            if steps:
                # Deliberately unhurried. Every step here is a fact the viewer
                # is meant to check against the cell it came from, and at 0.6s
                # a cycle the eye cannot follow both a moving activation and
                # the sum it lands on.
                self.play(Transform(cycle_label, new_label),
                          *steps, *flashes, run_time=1.15)
                self.wait(0.22)
            else:
                self.play(Transform(cycle_label, new_label), run_time=0.5)

        # Everything that came out the bottom is Y.
        # The whole argument for the array, in one line: a naive GEMM re-reads
        # a weight for every output it touches (M*K*N reads); the array reads
        # each weight once (K*N) and lets M activations stream past it.
        naive = M * K * N
        held = K * N
        done = VGroup(
            Text(f"{last_cycle + 1} cycles, and Y came out the bottom",
                 font_size=22, color=PSUM),
            Text(f"weight reads from SRAM:  {held}   —   a naive GEMM would do {naive}",
                 font_size=22, color=WEIGHT, weight="BOLD"),
        ).arrange(DOWN, buff=0.16).to_edge(DOWN, buff=0.42)
        self.play(FadeIn(done[0]), *[Indicate(o, color=PSUM) for o in outputs])
        self.wait(0.4)
        self.play(Write(done[1]))
        self.wait(1.4)


# The arithmetic is checked when the module loads, so a scene that renders at
# all is a scene whose numbers are right.
assert (A @ B == Y).all()
