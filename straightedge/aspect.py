"""Aspect ratio: the frame a scene is drawn in, and the pixels it renders to.

Two different numbers hide behind one word, and conflating them is how a
vertical render goes wrong:

* **Frame units** are Manim's internal coordinate space (``config.frame_width`` /
  ``frame_height``). They decide where ``LEFT * 5`` lands and therefore whether a
  label sits inside the picture. QC judges against these.
* **Pixels** are the output resolution. They decide the shape of the MP4.

Setting only the pixels leaves Manim deriving frame width from the default
height, which for 9:16 gives a 4.5-unit-wide frame — every scene authored for
landscape then draws off the sides. Setting only the units gives a correctly
composed scene rendered into a landscape file. A vertical cut needs both, which
is why they live together here rather than one at each call site.

This module is the single source of truth for the pair. It imports nothing from
the rest of the package so both ``templates`` (which writes the frame into the
scene) and ``renderer`` (which puts the pixels on the command line) can use it.
"""

from __future__ import annotations

LANDSCAPE = "16:9"
VERTICAL = "9:16"

#: Every aspect the renderer knows how to produce.
ASPECTS = (LANDSCAPE, VERTICAL)

#: Manim CE's default landscape frame, and the vertical frame that replaces it.
#: The vertical numbers are deliberately not the landscape ones transposed —
#: 16 units tall gives a vertical cut room to stack, which is the whole reason
#: to shoot one.
FRAME_UNITS: dict[str, tuple[float, float]] = {
    LANDSCAPE: (14.222222222222221, 8.0),
    VERTICAL: (9.0, 16.0),
}

#: Landscape ``(pixel_width, pixel_height, fps)`` per Manim quality flag. A
#: vertical render swaps the first two; the frame rate is unaffected.
QUALITY_RESOLUTIONS: dict[str, tuple[int, int, int]] = {
    "l": (854, 480, 15),
    "m": (1280, 720, 30),
    "h": (1920, 1080, 60),
    "p": (2560, 1440, 60),
    "k": (3840, 2160, 60),
}


def normalize(aspect: str | None) -> str:
    """An unknown or absent aspect is landscape, never an error.

    Matches ``frame_for``'s long-standing behaviour on the engine side: the
    aspect arrives from a job payload that has already validated it, so a second
    rejection here would only turn a typo into a crash deep in the renderer.
    """
    value = (aspect or "").strip()
    return value if value in ASPECTS else LANDSCAPE


def is_vertical(aspect: str | None) -> bool:
    return normalize(aspect) == VERTICAL


def frame_for(aspect: str | None) -> tuple[float, float]:
    """Scene units for an aspect — what QC measures against."""
    return FRAME_UNITS[normalize(aspect)]


def resolution_for(
    quality: str, aspect: str | None = None, fps: int | None = None
) -> tuple[int, int, int] | None:
    """``(pixel_width, pixel_height, fps)``, or ``None`` for an unknown quality.

    ``None`` rather than a raise: ``expected_output`` has always accepted an
    unrecognised quality and echoed it back as a directory name, and a caller
    passing Manim a flag this table has not caught up with should still get the
    render it asked for.

    ``fps`` overrides the rate the quality letter implies. The letter bundles a
    rate with a resolution — ``h`` means 1080p *and* 60fps — and there is no
    letter for 1080p30, which is the one worth having: it halves the frames for
    a difference nobody watching a narrated proof will notice.
    """
    entry = QUALITY_RESOLUTIONS.get(quality)
    if entry is None:
        return None
    width, height, fps_default = entry
    fps = fps_default if fps is None else fps
    if is_vertical(aspect):
        return height, width, fps
    return width, height, fps


def frame_config_source(aspect: str | None = None) -> str:
    """The lines a generated scene states its frame with.

    Emitted as source rather than set on ``config`` from the host process,
    because the scene is rendered by a *separate* ``python -m manim`` run — the
    only configuration that survives is what the file itself carries.

    Shared with the LLM path rather than copied into the writer prompt. A
    hand-copied preamble is how the prompt's ``_t`` drifted a version behind the
    template's, and a frame declaration that drifts is worse than one that is
    missing: the scene composes against numbers the renderer is not using.
    """
    frame_width, frame_height = frame_for(aspect)
    return (f"config.frame_width = {frame_width!r}\n"
            f"config.frame_height = {frame_height!r}")


def declares_frame(code: str) -> bool:
    """Whether ``code`` already sets its own frame.

    Deliberately a substring test for the assignment rather than a parse: the
    check guards an *injection*, so the only question is whether adding the
    lines would duplicate what is there. A false positive leaves the scene's own
    (possibly different) declaration alone, which is the safe direction.
    """
    return "config.frame_width" in code and "config.frame_height" in code


def with_frame_config(code: str, aspect: str | None = None) -> str:
    """``code`` guaranteed to declare its frame, for a non-landscape aspect.

    The writer prompt asks the model for these lines; this makes it true. An LLM
    that drops them yields a scene composed for a 4.5-unit-wide frame — every
    label off both sides — and nothing downstream would notice, because the file
    renders fine and only *looks* wrong.

    Left untouched for landscape, where the values are Manim's own defaults and
    the injection would change nothing. This code has already cleared the safety
    check and the reviewer, so the edit is kept to the case that cannot work
    without it — what ships should be as close as possible to what was approved.
    """
    if not is_vertical(aspect) or declares_frame(code):
        return code
    lines = code.splitlines()
    for index, line in enumerate(lines):
        # After the manim import, which is what brings ``config`` into scope.
        if line.startswith("from manim import") or line.startswith("import manim"):
            insert_at = index + 1
            break
    else:
        insert_at = 0
    block = ["", *frame_config_source(aspect).splitlines(), ""]
    return "\n".join(lines[:insert_at] + block + lines[insert_at:])


def output_dir_name(
    quality: str, aspect: str | None = None, fps: int | None = None
) -> str:
    """The directory Manim writes into, which is ``{pixel_height}p{fps}``.

    Verified against Manim CE 0.20: rendering ``-ql -r 480,854`` lands in
    ``854p15``, not ``480p15``. So a vertical cut is filed under the *landscape*
    width, and a resolver that assumes the quality flag alone names the folder
    looks in the wrong place and reports a successful render as a failure.
    """
    resolved = resolution_for(quality, aspect, fps)
    if resolved is None:
        return quality
    _, pixel_height, resolved_fps = resolved
    return f"{pixel_height}p{resolved_fps}"
