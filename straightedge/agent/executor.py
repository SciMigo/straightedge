from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from straightedge.aspect import LANDSCAPE, with_frame_config
from straightedge.renderer import expected_output, manim_command, manim_missing_error


@dataclass(frozen=True)
class CapturedRenderResult:
    returncode: int
    output_path: Path | None
    logs: str


def write_code_scene(code: str, output_dir: Path, aspect: str = LANDSCAPE) -> Path:
    """Write model-authored scene code, with its frame guaranteed.

    The writer prompt asks for the frame declaration, but a prompt is a request.
    Enforcing it here means a vertical render composes against the frame it is
    actually rendered into even when the model forgets — see
    :func:`~straightedge.aspect.with_frame_config` for why a missing declaration
    is silent rather than loud.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    scene_path = output_dir / "scene.py"
    scene_path.write_text(with_frame_config(code, aspect).rstrip() + "\n", encoding="utf-8")
    return scene_path


def render_scene_captured(
    scene_path: Path,
    quality: str = "l",
    media_dir: Path = Path("media"),
    aspect: str = LANDSCAPE,
) -> CapturedRenderResult:
    # Same invocation as renderer.render_scene, but capture logs so the agent
    # repair loop can feed render failures back to the LLM.
    #
    # ``aspect`` reaches both calls below on purpose. It changes the pixels
    # Manim is asked for *and* the directory those pixels land in; passing it to
    # only the command would report every successful vertical render as a
    # failure, and the repair loop would then feed a clean render back to the
    # model as something to fix.
    try:
        completed = subprocess.run(
            manim_command(scene_path, quality, media_dir, aspect),
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise manim_missing_error("agent-scaffold") from exc
    logs = (completed.stdout or "") + (completed.stderr or "")
    output_path = expected_output(scene_path, quality, media_dir, aspect)
    if completed.returncode == 0 and output_path.exists():
        return CapturedRenderResult(completed.returncode, output_path, logs)
    return CapturedRenderResult(completed.returncode, None, logs)
