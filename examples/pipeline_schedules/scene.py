"""GPipe against 1F1B: the same bubble, five times the memory.

The common claim about 1F1B is that it shrinks the pipeline bubble. It does
not. With ``P`` stages and ``M`` microbatches both schedules finish at the same
time and idle for exactly the same number of stage-slots — the bubble is
``(P-1)/M`` either way, because it is set by how long it takes to fill and
drain a pipeline, and 1F1B changes the *order* of the work, not its shape.

What 1F1B buys is memory. A forward pass has to stash its activations until the
matching backward consumes them. GPipe runs every forward before any backward,
so a stage holds ``M`` sets of activations at the peak; 1F1B starts the
backwards as soon as the pipeline is full, so a stage holds about ``P``. That is
the difference between fitting a model and not fitting it, and it is invisible
in every static diagram of these schedules, because a static diagram draws the
boxes and not what is being held while the boxes run.

Both schedules here are *simulated*, not drawn: the ops are placed by a
dependency-respecting scheduler, and the assertions below fail the render if the
two makespans ever disagree. Unit-time ops (a real backward is ~2x a forward),
which keeps the grid readable without changing the argument.

    manim -qm scene.py PipelineSchedules
"""

from __future__ import annotations

from manim import (
    DOWN, LEFT, RIGHT, UP,
    FadeIn, FadeOut, GrowFromEdge, Write,
    AnimationGroup, Scene, VGroup,
    Line, Rectangle, Text,
    BLACK, GREY_B, GREY_D, WHITE,
)

import sys
from pathlib import Path

# The layout check lives one directory up, shared by every example. Python puts
# this file's directory on the path, not examples/, so it needs saying.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _layout import assert_readable

P, M = 4, 6                      # pipeline stages, microbatches

INK = "#0d1117"
FWD = "#4aa8ff"                  # forward pass
BWD = "#f2b45b"                  # backward pass
IDLE = "#1c2534"                 # bubble
MEM = "#E5533D"                  # stashed activations
DIM = "#5a6885"
GOOD = "#4CAF50"

COL = 0.60                       # time-slot width
ROW = 0.40                       # stage-row height
GAUGE_H = 0.42                   # height budget for the memory gauge
TOP_Y, BOTTOM_Y = 1.35, -1.50    # chart centres


# --- the schedules, simulated ----------------------------------------------


def _gpipe(stage: int) -> list[tuple[str, int]]:
    """Every forward, then every backward. The simple thing, and the memory hog."""
    return [("F", m) for m in range(M)] + [("B", m) for m in range(M)]


def _one_f_one_b(stage: int) -> list[tuple[str, int]]:
    """Fill the pipeline, then alternate: one forward, one backward, per stage.

    The warmup length is what staggers the stages — the last stage starts its
    backwards immediately, the first stage waits ``P-1`` forwards.
    """
    warmup = P - 1 - stage
    ops: list[tuple[str, int]] = [("F", m) for m in range(warmup)]
    steady = M - warmup
    for i in range(steady):
        ops.append(("F", warmup + i))
        ops.append(("B", i))
    ops += [("B", m) for m in range(steady, M)]
    return ops


def simulate(order_for_stage) -> tuple[dict[tuple[str, int, int], int], int]:
    """Place every op at the first cycle its dependencies allow.

    Forward ``m`` needs forward ``m`` on the previous stage; backward ``m`` needs
    backward ``m`` on the *next* stage, or its own forward on the last stage. A
    stage runs its ops strictly in the order the schedule gives it, which is the
    only thing that differs between GPipe and 1F1B.
    """
    todo = {p: list(order_for_stage(p)) for p in range(P)}
    start: dict[tuple[str, int, int], int] = {}
    finished: set[tuple[str, int, int]] = set()
    free_at = {p: 0 for p in range(P)}
    cycle = 0
    while any(todo.values()):
        for p in range(P):
            if not todo[p] or free_at[p] > cycle:
                continue
            kind, m = todo[p][0]
            if kind == "F":
                ready = p == 0 or ("F", m, p - 1) in finished
            else:
                ready = (("B", m, p + 1) in finished if p < P - 1
                         else ("F", m, P - 1) in finished)
            if ready:
                start[(kind, m, p)] = cycle
                finished.add((kind, m, p))
                free_at[p] = cycle + 1
                todo[p].pop(0)
        cycle += 1
        if cycle > 400:                     # a deadlocked schedule is a bug
            raise RuntimeError("schedule made no progress")
    return start, max(start.values()) + 1


GPIPE, GPIPE_END = simulate(_gpipe)
ONEFONEB, ONEFONEB_END = simulate(_one_f_one_b)

# The claim the animation makes, checked before a frame is drawn.
assert GPIPE_END == ONEFONEB_END, "the two schedules must finish together"
MAKESPAN = GPIPE_END


def stashed(start: dict[tuple[str, int, int], int], cycle: int) -> int:
    """Activation sets held across the whole cluster at this cycle.

    A forward's activations are live from the moment it finishes until the
    matching backward on that stage begins.
    """
    live = 0
    for (kind, m, p), begin in start.items():
        if kind != "F" or begin + 1 > cycle:
            continue
        if start.get(("B", m, p), 10**9) > cycle:
            live += 1
    return live


GPIPE_PEAK = max(stashed(GPIPE, c) for c in range(MAKESPAN + 1))
ONEFONEB_PEAK = max(stashed(ONEFONEB, c) for c in range(MAKESPAN + 1))
assert GPIPE_PEAK > ONEFONEB_PEAK, "1F1B is supposed to hold less"

BUBBLE = P * MAKESPAN - len(GPIPE)          # idle stage-slots, same for both
assert P * MAKESPAN - len(ONEFONEB) == BUBBLE


class PipelineSchedules(Scene):
    """Two Gantt charts filling in step by step, with a memory gauge each."""

    def construct(self) -> None:
        self.camera.background_color = INK

        title = Text("GPipe vs 1F1B", font_size=36, color=WHITE, weight="BOLD")
        title.to_edge(UP, buff=0.22)
        sub = Text(f"{P} stages · {M} microbatches · one cell = one cycle",
                   font_size=19, color=DIM).next_to(title, DOWN, buff=0.10)
        legend = self._legend().next_to(sub, DOWN, buff=0.12)
        self.play(Write(title), FadeIn(sub), FadeIn(legend))

        top = self._chart("GPipe — all forwards, then all backwards", TOP_Y)
        bottom = self._chart("1F1B — start the backwards as soon as it is full",
                             BOTTOM_Y)
        self.play(FadeIn(top["frame"]), FadeIn(bottom["frame"]))

        self._run(top, bottom)

        assert_readable(self)

    # -- pieces -------------------------------------------------------------

    def _legend(self) -> VGroup:
        row = VGroup()
        for color, caption in ((FWD, "forward"), (BWD, "backward"),
                               (IDLE, "bubble"), (MEM, "activations held")):
            # The bubble swatch is the deck's own empty-cell colour, so it
            # needs a visible edge or it reads as a gap in the legend.
            swatch = Rectangle(width=0.24, height=0.24,
                               stroke_color=GREY_D if color == IDLE else color,
                               stroke_width=2,
                               fill_color=color, fill_opacity=0.55)
            row.add(VGroup(swatch, Text(caption, font_size=16, color=GREY_B)
                           .next_to(swatch, RIGHT, buff=0.11)))
        return row.arrange(RIGHT, buff=0.62)

    def _chart(self, caption: str, y: float) -> dict:
        """An empty Gantt grid plus its memory gauge, positioned at height y."""
        left = -COL * MAKESPAN / 2 - 0.9
        cells: dict[tuple[int, int], Rectangle] = {}
        frame = VGroup()

        label = Text(caption, font_size=18, color=WHITE, weight="BOLD")
        label.move_to([left + 0.9, y + ROW * P / 2 + 0.30, 0]).align_to(
            [left, 0, 0], LEFT)
        frame.add(label)

        for p in range(P):
            row_y = y + (P / 2 - p - 0.5) * ROW
            tag = Text(f"stage {p}", font_size=14, color=DIM)
            tag.move_to([left - 0.05, row_y, 0]).align_to([left - 0.1, 0, 0], RIGHT)
            frame.add(tag)
            for c in range(MAKESPAN):
                cell = Rectangle(width=COL * 0.92, height=ROW * 0.82,
                                 stroke_color=GREY_D, stroke_width=0.8,
                                 fill_color=BLACK, fill_opacity=0.55)
                cell.move_to([left + (c + 0.5) * COL, row_y, 0])
                cells[(p, c)] = cell
                frame.add(cell)

        # The memory gauge sits under its own chart, so the two are compared
        # against the same time axis rather than against a remembered number.
        gauge_y = y - ROW * P / 2 - 0.16
        base = Line([left, gauge_y, 0], [left + COL * MAKESPAN, gauge_y, 0],
                    stroke_color=GREY_D, stroke_width=1.2)
        frame.add(base)
        return {"frame": frame, "cells": cells, "left": left,
                "gauge_y": gauge_y, "bars": {}}

    # -- the sweep ----------------------------------------------------------

    def _run(self, top: dict, bottom: dict) -> None:
        top_read = Text("", font_size=18)
        bottom_read = Text("", font_size=18)
        readouts = VGroup(top_read, bottom_read)

        for cycle in range(MAKESPAN):
            anims = []
            for chart, schedule in ((top, GPIPE), (bottom, ONEFONEB)):
                for (kind, m, p), begin in schedule.items():
                    if begin != cycle:
                        continue
                    cell = chart["cells"][(p, cycle)]
                    color = FWD if kind == "F" else BWD
                    filled = cell.copy().set_fill(color, 0.85).set_stroke(color, 1.2)
                    tag = Text(f"{kind}{m}", font_size=13, color=BLACK,
                               weight="BOLD").move_to(cell.get_center())
                    anims.append(cell.animate.become(filled))
                    anims.append(FadeIn(tag, run_time=0.25))

                # Memory: one tick per activation set currently held.
                # Both gauges share one scale — GPipe's peak sets the top of
                # the budget — or the comparison would be a lie told with axes.
                held = stashed(schedule, cycle + 1)
                h = max(0.025, GAUGE_H * held / GPIPE_PEAK)
                bar = Rectangle(width=COL * 0.5, height=h,
                                stroke_width=0, fill_color=MEM, fill_opacity=0.9)
                bar.move_to([chart["left"] + (cycle + 0.5) * COL,
                             chart["gauge_y"] - h / 2, 0])
                anims.append(GrowFromEdge(bar, UP, run_time=0.3))

            # Slow enough to follow one cell into the next: the point is that
            # the two rows advance together while the gauges diverge.
            self.play(*anims, run_time=0.62)

        self.wait(0.5)
        self._verdict(top, bottom)

    def _verdict(self, top: dict, bottom: dict) -> None:
        """State the two facts the charts just demonstrated."""
        same = Text(f"same finish: {MAKESPAN} cycles   ·   same bubble: "
                    f"{BUBBLE} idle stage-slots",
                    font_size=20, color=GOOD, weight="BOLD")
        memory = Text(f"activations held at the peak:   GPipe {GPIPE_PEAK}"
                      f"   ·   1F1B {ONEFONEB_PEAK}",
                      font_size=20, color=MEM, weight="BOLD")
        lines = VGroup(same, memory).arrange(DOWN, buff=0.13)
        lines.to_edge(DOWN, buff=0.16)
        self.play(Write(same))
        self.wait(0.5)
        self.play(Write(memory))
        self.wait(1.6)
