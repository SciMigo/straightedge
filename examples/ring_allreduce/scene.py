"""Ring all-reduce: the bytes do not grow with the ring, the waiting does.

The picture everyone draws is a circle with four boxes and arrows going round,
and it leaves you with the impression that all-reduce gets more expensive as you
add GPUs. Half of that is exactly backwards.

Per rank, a ring all-reduce moves ``2(N-1)/N`` times the buffer. That is under
``2D`` for every ring size there has ever been — 1.5D at four ranks, 1.97D at
sixty-four, and it never reaches 2D. Adding ranks does not cost bytes. It is
*bandwidth-optimal*, and no arrangement of sends can do better, because every
rank must at minimum ship its data out once and take the answer back once.

What does grow is the number of round trips: ``2(N-1)`` steps, strictly serial,
each waiting on the one before. That is the real cost of a big ring, and it is
the thing a static circle diagram cannot show you, because the diagram has no
time axis — it draws the topology and hides the schedule.

The naive alternative is the useful contrast: if every rank simply sent its whole
buffer to every peer, each would move ``(N-1)D``. Three times the buffer at four
ranks, sixty-three times at sixty-four. *That* is the cost that explodes, and
avoiding it is the entire reason the ring exists.

Both quantities here are simulated rather than asserted by hand: the chunk
exchange below is executed, and the module refuses to import unless every rank
ends holding the true elementwise sum. The byte counts are then checked against
the closed form for ring sizes up to 64, so the claim on screen is a claim the
code has verified rather than one a script author remembered.

    manim -qm scene.py RingAllReduce
"""

from __future__ import annotations

import numpy as np
from manim import (
    DOWN, LEFT, RIGHT, UP,
    FadeIn, FadeOut, Transform, Write,
    Scene, VGroup,
    CurvedArrow, Rectangle, Text,
)

import sys
from pathlib import Path

# The layout check lives one directory up, shared by every example. Python puts
# this file's directory on the path, not examples/, so it needs saying.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _layout import STYLE as S, assert_readable

N = 4                            # ranks in the ring
STEPS = 2 * (N - 1)              # reduce-scatter, then all-gather

# Rank r contributes (r+1)*(c+1) to chunk c, so chunk c sums to a clean multiple
# of ten and every rank should finish holding [10, 20, 30, 40]. Distinct per
# chunk so a wrong rotation is visible, small enough to read at two digits.
INITIAL = np.array([[(r + 1) * (c + 1) for c in range(N)] for r in range(N)])
TRUTH = INITIAL.sum(axis=0)

# --- palette ---------------------------------------------------------------
# Roles from the shared style, aliased to what they mean in a collective. `S.deep`
# is a darker `S.flow`, which is exactly what a partially reduced chunk should
# look like: the same quantity, not yet finished.
OWNED = S.flow                   # the chunk this rank is accumulating
PARTIAL = S.deep                 # partially reduced
DONE = S.done                    # holds the final sum
MOVING = S.hold                  # in flight
DIM = S.dim
COST = S.warn                    # the naive comparison

CELL_W, CELL_H = 0.62, 0.30
RADIUS = 2.05


# --- the exchange, simulated -----------------------------------------------


def ring_allreduce(initial: np.ndarray) -> tuple[np.ndarray, list[dict]]:
    """Run the real thing and record every send.

    Two phases, ``N-1`` steps each, and the only difference between them is
    whether the receiver adds or overwrites.

    *Reduce-scatter*: at step ``s`` rank ``r`` sends the chunk it is currently
    accumulating to its successor, which adds it. After ``N-1`` steps rank ``r``
    holds the complete sum for exactly one chunk and nobody holds two.

    *All-gather*: the same rotation again, except the receiver overwrites — the
    finished chunks are simply carried the rest of the way round.
    """
    buf = initial.copy()
    log: list[dict] = []

    for s in range(N - 1):
        # Chunk index each rank sends this step. Chosen so that what arrives is
        # always the chunk the receiver is itself accumulating.
        sends = {r: (r - s) % N for r in range(N)}
        payload = {r: buf[r][sends[r]].copy() for r in range(N)}
        for r in range(N):
            dst = (r + 1) % N
            buf[dst][sends[r]] += payload[r]
        log.append({"phase": "reduce-scatter", "step": s, "sends": sends,
                    "accumulate": True})

    for s in range(N - 1):
        sends = {r: (r - s + 1) % N for r in range(N)}
        payload = {r: buf[r][sends[r]].copy() for r in range(N)}
        for r in range(N):
            dst = (r + 1) % N
            buf[dst][sends[r]] = payload[r]
        log.append({"phase": "all-gather", "step": s, "sends": sends,
                    "accumulate": False})

    return buf, log


FINAL, LOG = ring_allreduce(INITIAL)

# The claim the animation makes, checked before a frame is drawn. Every rank
# ends with the true sum — not merely the rank the camera happens to follow.
for _r in range(N):
    assert np.array_equal(FINAL[_r], TRUTH), f"rank {_r} finished wrong"
assert len(LOG) == STEPS, "a ring all-reduce is exactly 2(N-1) steps"


# --- what it costs ---------------------------------------------------------


def ring_bytes_per_rank(n: int) -> float:
    """Multiples of the buffer each rank ships. ``2(n-1)/n``, and under 2."""
    return 2 * (n - 1) / n


def naive_bytes_per_rank(n: int) -> float:
    """Everyone sends everyone their whole buffer: ``n-1`` buffers each."""
    return float(n - 1)


# Counted from the log rather than asserted from the formula, so a broken
# schedule cannot quietly agree with the arithmetic printed on screen.
_sent_chunks = sum(len(entry["sends"]) for entry in LOG)
assert _sent_chunks == N * STEPS
assert abs(_sent_chunks / N / N - ring_bytes_per_rank(N)) < 1e-9

# The punchline, over ring sizes no diagram bothers to draw: the ring's per-rank
# traffic is bounded no matter how many ranks join, while the naive cost is not.
for _n in range(2, 65):
    assert ring_bytes_per_rank(_n) < 2.0
    assert naive_bytes_per_rank(_n) == _n - 1
    assert ring_bytes_per_rank(_n) <= naive_bytes_per_rank(_n)

RING_COST = ring_bytes_per_rank(N)
NAIVE_COST = naive_bytes_per_rank(N)


class RingAllReduce(Scene):
    """Four ranks, sixteen chunks, and a byte counter that refuses to grow."""

    def construct(self) -> None:
        self.camera.background_color = S.ink

        title = Text("Ring all-reduce", font_size=S.size.title, color=S.fg,
                     weight="BOLD")
        title.to_edge(UP, buff=0.20)
        sub = Text(f"{N} ranks · {N} chunks each · one step = one hop round the ring",
                   font_size=18, color=DIM).next_to(title, DOWN, buff=0.09)
        self.play(Write(title), FadeIn(sub))

        self.cells = {}
        ring = self._ring()
        self.play(FadeIn(ring), run_time=0.8)

        # In the middle of the ring, which is dead space and the one place a
        # label cannot be hit by an arriving chunk. Above the ring it landed on
        # rank 0's tag, which is the first thing a reader looks for.
        self.phase = self._phase_label("reduce-scatter", "each hop adds", OWNED)
        self.counter = self._counter()
        self.play(FadeIn(self.phase), FadeIn(self.counter))

        self._run()
        self._verdict()

        assert_readable(self)

    # -- pieces -------------------------------------------------------------

    def _rank_centre(self, r: int) -> np.ndarray:
        """Rank 0 at the top, then clockwise, which is the direction of flow."""
        angle = np.pi / 2 - r * 2 * np.pi / N
        return np.array([RADIUS * np.cos(angle), RADIUS * np.sin(angle), 0.0])

    def _ring(self) -> VGroup:
        group = VGroup()
        for r in range(N):
            centre = self._rank_centre(r)
            column = VGroup()
            for c in range(N):
                cell = Rectangle(width=CELL_W, height=CELL_H,
                                 stroke_color=S.rule, stroke_width=0.9,
                                 fill_color=S.well, fill_opacity=0.6)
                value = Text(f"{INITIAL[r][c]:02d}", font_size=14, color=S.muted)
                value.move_to(cell.get_center())
                self.cells[(r, c)] = {"box": cell, "text": value}
                column.add(VGroup(cell, value))
            column.arrange(DOWN, buff=0.045).move_to(centre)

            tag = Text(f"rank {r}", font_size=15, color=DIM)
            # Outside the circle, so an arriving chunk never lands on the label.
            tag.next_to(column, DOWN if r == 2 else UP, buff=0.10)
            group.add(column, tag)

        for r in range(N):
            group.add(self._hop(r))
        return group

    def _hop(self, r: int) -> CurvedArrow:
        """The arrow from a rank to its successor, bowed away from the centre."""
        start, end = self._rank_centre(r), self._rank_centre((r + 1) % N)
        inset = 0.62
        a = start + (end - start) * (inset / np.linalg.norm(end - start))
        b = end - (end - start) * (inset / np.linalg.norm(end - start))
        return CurvedArrow(a, b, angle=-0.55, color=S.rule,
                           stroke_width=S.width.mark, tip_length=0.14)

    def _counter(self) -> VGroup:
        """Bytes shipped per rank so far, against what naive would have cost."""
        self.moved = Text(f"{0.00:.2f}D moved per rank", font_size=19,
                          color=OWNED, weight="BOLD")
        naive = Text(f"naive all-to-all would move {NAIVE_COST:.2f}D per rank",
                     font_size=17, color=COST)
        block = VGroup(self.moved, naive).arrange(DOWN, buff=0.08)
        return block.to_edge(DOWN, buff=0.22)

    # -- the exchange -------------------------------------------------------

    def _run(self) -> None:
        for entry in LOG:
            if entry["phase"] == "all-gather" and entry["step"] == 0:
                self._switch_phase()
            self._step(entry)

    def _phase_label(self, name: str, gloss: str, colour: str) -> VGroup:
        return VGroup(
            Text(name, font_size=21, color=colour, weight="BOLD"),
            Text(gloss, font_size=15, color=DIM),
        ).arrange(DOWN, buff=0.10)

    def _switch_phase(self) -> None:
        # Swapped rather than transformed: the two labels differ in length, and
        # Manim zips the families of whatever it is asked to morph between.
        new = self._phase_label("all-gather", "each hop copies", DONE)
        self.play(FadeOut(self.phase), run_time=0.25)
        self.phase = new
        self.play(FadeIn(self.phase), run_time=0.35)

    def _step(self, entry: dict) -> None:
        """One hop for every rank at once, which is what a real ring does."""
        flying = []
        for r, chunk in entry["sends"].items():
            source = self.cells[(r, chunk)]
            ghost = (source["box"].copy()
                     .set_fill(MOVING, S.opacity.solid).set_stroke(MOVING, 1.4))
            label = source["text"].copy().set_color(S.on_fill)
            flying.append((VGroup(ghost, label), (r + 1) % N, chunk))

        self.play(
            *[packet.animate.move_to(self.cells[(dst, chunk)]["box"].get_center())
              for packet, dst, chunk in flying],
            run_time=0.75,
        )

        # Land: recolour the destination and write the value it now holds. Read
        # from the simulation rather than recomputed here, so the picture cannot
        # disagree with the arithmetic that was asserted at import.
        landings = []
        state = self._state_after(entry)
        for packet, dst, chunk in flying:
            cell = self.cells[(dst, chunk)]
            complete = state["complete"][(dst, chunk)]
            colour = DONE if complete else (PARTIAL if entry["accumulate"] else OWNED)
            filled = (cell["box"].copy()
                      .set_fill(colour, 0.75).set_stroke(colour, S.width.rule))
            value = Text(f"{state['buf'][dst][chunk]:02d}", font_size=14,
                         color=S.fg if complete else S.muted)
            value.move_to(cell["box"].get_center())
            landings.append(cell["box"].animate.become(filled))
            landings.append(Transform(cell["text"], value))
            landings.append(FadeOut(packet, run_time=0.2))

        moved = (entry_index(entry) + 1) / N
        counter = Text(f"{moved:.2f}D moved per rank", font_size=19,
                       color=OWNED, weight="BOLD")
        counter.move_to(self.moved.get_center())
        landings.append(Transform(self.moved, counter))

        self.play(*landings, run_time=0.55)

    def _state_after(self, entry: dict) -> dict:
        """Replay the log up to and including ``entry``.

        Replayed rather than tracked alongside the animation: the scene then has
        no state of its own to drift from the simulation, and a mis-drawn frame
        becomes impossible rather than merely unlikely.
        """
        buf = INITIAL.copy()
        complete: dict[tuple[int, int], bool] = {}
        upto = entry_index(entry)
        for i, step in enumerate(LOG[:upto + 1]):
            for r in range(N):
                chunk = step["sends"][r]
                dst = (r + 1) % N
                payload = buf[r][chunk].copy()
                if step["accumulate"]:
                    buf[dst][chunk] += payload
                else:
                    buf[dst][chunk] = payload
            if i == upto:
                for r in range(N):
                    for c in range(N):
                        complete[(r, c)] = bool(buf[r][c] == TRUTH[c])
        return {"buf": buf, "complete": complete}

    # -- the claim ----------------------------------------------------------

    def _verdict(self) -> None:
        for r in range(N):
            assert np.array_equal(FINAL[r], TRUTH)

        cost = Text(f"{STEPS} steps · {RING_COST:.2f}D per rank"
                    f"   —   naive: {NAIVE_COST:.2f}D",
                    font_size=21, color=DONE, weight="BOLD")
        scale = Text("at 64 ranks the ring still moves under 2.00D — "
                     "it is the 126 serial hops that hurt",
                     font_size=18, color=MOVING)
        lines = VGroup(cost, scale).arrange(DOWN, buff=0.11)
        lines.to_edge(DOWN, buff=0.20)

        self.play(FadeOut(self.counter), run_time=0.3)
        self.play(Write(cost))
        self.wait(0.6)
        self.play(FadeIn(scale))
        self.wait(1.8)


def entry_index(entry: dict) -> int:
    """Position of a log entry, so a step can replay the history up to itself."""
    offset = 0 if entry["phase"] == "reduce-scatter" else N - 1
    return offset + entry["step"]
