"""Check that a finished scene can actually be read.

Each example here already asserts its *arithmetic* at import time — the systolic
array checks its outputs against ``A @ B``, the pipeline schedules check that the
two makespans agree, the ring all-reduce checks that every rank ends holding the
true sum, and the tensor-parallel block checks both that the good split is exact
and that the bad one is *wrong*. A scene that renders is therefore a scene whose
numbers are right.

None of that says the picture is legible. A label can sit on another label, a
caption can run through a tick row, a curve can leave its axes, and every
assertion above still passes because none of them look at what was drawn. That
is a different failure mode and it needs a different check, which is exactly the
gap :mod:`straightedge.qc` exists to fill for the library's generated scenes.

So the examples use it too. The rule these files follow — simulate the
mechanism, assert the claim, then animate the simulation — gets one more clause:
and check that the animation can be read.

Practical notes:

* The check runs at the **end of construct**, because it needs the built scene.
  Manim clears ``scene.mobjects`` before ``tear_down``, so a hook there would
  measure an empty scene and report every render as ``empty``.
* An ``error`` raises. These are teaching artefacts, and a picture with two
  labels on the same spot teaches the wrong thing just as surely as a wrong
  schedule does — the same reason the arithmetic assertions are fatal.
* A ``warn`` prints and lets the render finish. A stroke crossing a label is
  usually deliberate here (a tangent line is *supposed* to touch the curve it
  labels), and failing on it would make the check something people switch off.

**A limitation these examples exposed.** All four draw numbers inside cells — a
PE in the array, a slot in the Gantt chart, a chunk on a rank — and ``qc`` reports
every one as ``text_obscured``: *'F0' is 100% covered by 'Rectangle'*. It is
true and it is the intended design. Text placed inside a filled shape is
probably the most common layout idiom there is, and the check cannot yet tell it
from the thing it is looking for.

The distinction it needs is containment: text sitting *wholly inside* a mark is
a label in a box, while text *straddling a mark's edge* is half-covered and
unreadable. That fix belongs in ``straightedge.qc``, not here, so the warnings
are summarised below rather than listed — thirteen true-but-uninteresting lines
per render is the same noise that made the cone_slice findings unreadable, and
the answer is to fix the check rather than to teach people to skim past it.
"""

from __future__ import annotations

import os
from collections import Counter

from straightedge.qc import boxes_from_scene, check, frame_from_scene
from straightedge.style import DATAFLOW, theme

#: The style every example in this directory draws in. Set once here rather than
#: per scene, because the four of them are meant to look like one set::
#:
#:     manim -qm scene.py TensorParallel                      # dataflow, the default
#:     STRAIGHTEDGE_STYLE=paper manim -qm scene.py TensorParallel
#:
#: An unknown name raises :class:`~straightedge.errors.RequestError` naming the
#: available themes, which is a better failure than rendering four minutes of
#: video in a style nobody asked for.
STYLE = theme(os.environ.get("STRAIGHTEDGE_STYLE") or DATAFLOW.name)


def assert_readable(scene) -> None:
    """Report what the finished scene looks like; raise if it is unreadable."""
    findings = check(boxes_from_scene(scene), frame=frame_from_scene(scene))
    name = type(scene).__name__
    errors = [f for f in findings if f.severity == "error"]
    warnings = [f for f in findings if f.severity != "error"]

    for finding in errors:
        print(f"  qc: {finding}")
    if warnings:
        # Counted, not listed: see the note above on labels inside their cells.
        kinds = ", ".join(f"{n}x {check_}"
                          for check_, n in Counter(f.check for f in warnings).items())
        print(f"  qc: {name}: {len(warnings)} warning(s) — {kinds}")
    if not findings:
        print(f"  qc: {name}: nothing to report")

    if errors:
        raise AssertionError(
            f"{name} drew {len(errors)} unreadable thing(s):\n"
            + "\n".join(f"  {f}" for f in errors)
        )
