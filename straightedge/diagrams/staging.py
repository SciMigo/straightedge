"""Staged reveal: one static SVG that a beat-driven page can build up step by step.

A figure template draws its final state. Some figures are procedures — a ladder
of squares climbed one rung at a time, a grid struck out one prime at a time —
and a narrated page wants each step to appear with the sentence that explains
it. ``animated_trace`` cannot do that: it plays on its own clock, and the
narration's clock is the page's.

So the contract is markup, not motion. A template that supports it groups its
drawing into *natural steps*, in order, and the caller's ``reveal`` list says
which *stage* each step belongs to:

* The scaffold (everything that is not a step) carries no attribute and is
  always shown.
* Each step is wrapped in ``<g data-stage="k">`` with ``k >= 1`` taken from
  ``reveal``. Several steps may share a stage, so seven rungs can land on four
  beats: ``reveal: [1, 1, 2, 2, 3, 3, 4]``.
* Without ``reveal`` (or with an empty one) no attribute is emitted at all and the figure is exactly
  the static one.
* A consumer that ignores the attribute shows the final state, which is
  complete and correct on its own. A consumer that honours it shows stage ``k``
  together with its own ``k``-th reveal.
* ``upto: k`` draws only steps whose stage is ``<= k`` and emits no stage
  attributes — a still of the figure part-way through, for pages that cannot
  reveal.

``reveal`` is checked like any other input: a list of the wrong length, a
non-integer, a stage below 1 or a stage that goes backwards is refused with a
finding rather than drawn in an order the caller did not ask for.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from ..qc import Finding


def reveal_findings(params: Dict[str, Any], steps: Sequence[str]) -> List[Finding]:
    """Why ``params['reveal']`` / ``params['upto']`` cannot be honoured."""
    findings: List[Finding] = []
    reveal = params.get("reveal")
    if reveal is not None and reveal != []:
        if not isinstance(reveal, list):
            findings.append(Finding("stage_input", "error",
                                    "reveal must be a list of stage numbers, one per step"))
        elif len(reveal) != len(steps):
            findings.append(Finding(
                "stage_input", "error",
                f"reveal has {len(reveal)} entries but this figure has {len(steps)} "
                f"steps ({', '.join(steps)})"))
        else:
            last = 1
            for i, value in enumerate(reveal):
                if isinstance(value, bool) or not isinstance(value, int):
                    findings.append(Finding("stage_input", "error",
                                            f"reveal[{i}] = {value!r} is not an integer",
                                            label=str(value)))
                    break
                if value < 1:
                    findings.append(Finding("stage_input", "error",
                                            f"reveal[{i}] = {value} is below 1; stage 0 is "
                                            f"the always-visible scaffold", label=str(value)))
                    break
                if value < last:
                    findings.append(Finding(
                        "stage_input", "error",
                        f"reveal[{i}] = {value} comes after stage {last}: steps are drawn "
                        f"in order, so stages may not go backwards", label=str(value)))
                    break
                last = value
    upto = params.get("upto")
    if upto is not None and (isinstance(upto, bool) or not isinstance(upto, int) or upto < 0):
        findings.append(Finding("stage_input", "error",
                                f"upto must be a non-negative integer, not {upto!r}",
                                label=str(upto)))
    return findings


class Stager:
    """Wraps each natural step in the group its stage asks for."""

    def __init__(self, params: Dict[str, Any], steps: Sequence[str]):
        reveal = params.get("reveal")
        # An empty plan is no plan: the figure is the static one.
        self.stages: Optional[List[int]] = list(reveal) if isinstance(reveal, list) and reveal else None
        upto = params.get("upto")
        self.upto: Optional[int] = upto if isinstance(upto, int) and not isinstance(upto, bool) else None
        self.steps = list(steps)

    def stage_of(self, index: int) -> int:
        if self.stages is None:
            return index + 1
        return self.stages[index]

    def wrap(self, index: int, content: str) -> str:
        """``content`` for step ``index`` — grouped, plain, or omitted."""
        if not content:
            return ""
        stage = self.stage_of(index)
        if self.upto is not None:
            return content if stage <= self.upto else ""
        if self.stages is None:
            return content
        return f'<g data-stage="{stage}" data-step="{self.steps[index]}">{content}</g>'


__all__ = ["Stager", "reveal_findings"]
