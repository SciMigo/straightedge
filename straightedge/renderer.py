from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .aspect import LANDSCAPE, output_dir_name, resolution_for
from .fonts import DEFAULT_CJK_FONT
from .labels import DEFAULT_LANGUAGE
from .models import AnimationPlan
from .style import TEXTBOOK, Style
from .templates import SCENE_CLASS_NAME, scene_code_for

# Manim quality flag (-q{x}) -> the resolution folder name Manim writes under.
# Derived rather than written out, so it cannot drift from the resolution table
# the vertical path reads. Landscape only; see aspect.output_dir_name.
QUALITY_DIRS = {q: output_dir_name(q) for q in ("l", "m", "h", "p", "k")}


@dataclass
class RenderResult:
    returncode: int
    output_path: Path | None  # set only when the expected MP4 was produced


def write_scene(
    plan: AnimationPlan,
    output_dir: Path,
    font: str = DEFAULT_CJK_FONT,
    beat_seconds: dict[str, float] | None = None,
    aspect: str = LANDSCAPE,
    language: str = DEFAULT_LANGUAGE,
    qc_sidecar: Path | None = None,
    name: str = "scene",
    style: Style = TEXTBOOK,
) -> Path:
    """Write the scene Manim will render.

    ``beat_seconds`` maps a beat key to the measured length of its narration
    clip; see :func:`~straightedge.templates.scene_code_for`. This is the only
    writer, so a caller that has measured its narration has nowhere else to hand
    the numbers over — omitting the parameter here left the feature reachable
    only by callers willing to render the source themselves.

    ``aspect`` sets the *frame* the scene composes into. The matching pixel
    resolution is a separate argument to :func:`manim_command`, and a vertical
    cut needs both — see :mod:`straightedge.aspect`.

    ``language`` sets the on-screen labels — see :mod:`straightedge.labels`.

    ``style`` picks the palette — see :mod:`straightedge.style`. Threaded here
    for the same reason ``beat_seconds`` is: this is the only writer, so a
    parameter missing from it is a feature only reachable by callers willing to
    render the source themselves. The default is Manim's own palette, which is
    what every existing render already used.

    ``qc_sidecar`` asks the scene to record its extents there as it finishes, so
    the caller can run :func:`straightedge.qc.check_sidecar` once Manim exits.
    An absolute path is used in the emitted source: Manim runs the scene from
    its own working directory, and a relative one would land somewhere neither
    side agreed on.

    ``name`` is the scene file's stem — ``scene`` by default, so the file is
    ``scene.py``. Two renders sharing an ``output_dir`` otherwise overwrite one
    another's ``scene.py`` silently, which is the collision a concurrent caller
    hits; a distinct ``name`` per render keeps them apart. The render path keys
    off whatever stem is passed, so nothing else needs telling.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    scene_path = output_dir / f"{name}.py"
    scene_path.write_text(
        scene_code_for(plan, font=font, beat_seconds=beat_seconds, style=style,
                       aspect=aspect, language=language,
                       qc_sidecar=str(qc_sidecar.resolve()) if qc_sidecar else None) + "\n",
        encoding="utf-8",
    )
    return scene_path


def manim_command(
    scene_path: Path,
    quality: str,
    media_dir: Path,
    aspect: str = LANDSCAPE,
    fps: int | None = None,
) -> list[str]:
    """The argv used to render ``scene_path`` with Manim in the active interpreter.

    A non-landscape aspect adds ``-r WIDTH,HEIGHT``, which overrides the shape
    the quality flag implies. The flag is kept as well: it still carries the
    frame rate, and dropping it would silently drop that too.

    ``fps`` overrides that rate, and has to go on the command line. Setting
    ``frame_rate`` in a ``manim.cfg`` looks like it works and does nothing —
    the command line outranks the config file, so ``-qh`` puts 60 back, the
    render succeeds at the wrong rate, and costs what the wrong rate costs.
    Measured 2026-08-08: 1080p60 took 306s and 1080p30 took 168s for the same
    scene, so getting this wrong is 45% of the bill.

    Whatever is passed here must also reach :func:`expected_output`, which
    names the directory Manim writes into after the frame rate.
    """
    argv = [
        sys.executable,
        "-m",
        "manim",
        f"-q{quality}",
    ]
    if fps is not None:
        argv += ["--fps", str(fps)]
    resolved = resolution_for(quality, aspect, fps)
    if resolved is not None and aspect != LANDSCAPE:
        pixel_width, pixel_height, _ = resolved
        argv += ["-r", f"{pixel_width},{pixel_height}"]
    argv += [
        "--media_dir",
        str(media_dir),
        str(scene_path),
        SCENE_CLASS_NAME,
    ]
    return argv


def expected_output(
    scene_path: Path,
    quality: str,
    media_dir: Path,
    aspect: str = LANDSCAPE,
    fps: int | None = None,
) -> Path:
    """Path of the MP4 Manim is expected to write for ``scene_path``.

    The folder is named for the pixel *height*, so a vertical cut is filed under
    the landscape width — ``-ql -r 480,854`` lands in ``854p15``. Assuming the
    quality flag alone names it makes a successful vertical render look like a
    failed one, because the resolver looks in a directory nothing wrote to.
    """
    resolution = output_dir_name(quality, aspect, fps)
    return media_dir / "videos" / scene_path.stem / resolution / f"{SCENE_CLASS_NAME}.mp4"


def manim_missing_error(scaffold_command: str) -> RuntimeError:
    """Shared hint raised when the ``manim`` module is not importable."""
    return RuntimeError(
        "Manim is not installed in the active Python environment. Install it with "
        f"`pip install '.[render]'` or use `{scaffold_command}` to write the scene only."
    )


def render_scene(
    scene_path: Path,
    quality: str = "l",
    media_dir: Path = Path("media"),
    aspect: str = LANDSCAPE,
    fps: int | None = None,
    stdout=None,
) -> RenderResult:
    # Inherit stdout/stderr (no capture) so Manim's progress streams live.
    # ``stdout`` lets a caller send Manim's chatter somewhere other than the
    # process stdout — a JSON caller passes ``sys.stderr`` so the one result
    # object is the only thing on stdout, with Manim's diagnostics still visible.
    try:
        completed = subprocess.run(
            manim_command(scene_path, quality, media_dir, aspect, fps),
            check=False, stdout=stdout)
    except FileNotFoundError as exc:
        raise manim_missing_error("scaffold") from exc

    output_path = expected_output(scene_path, quality, media_dir, aspect, fps)
    if completed.returncode == 0 and output_path.exists():
        return RenderResult(returncode=0, output_path=output_path)
    return RenderResult(returncode=completed.returncode, output_path=None)
