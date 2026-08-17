import subprocess
import sys

import pytest

from straightedge import renderer
from straightedge.templates import SCENE_CLASS_NAME


def test_render_scene_builds_command_and_reports_path(monkeypatch, tmp_path):
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(cmd, returncode=0)

    monkeypatch.setattr(renderer.subprocess, "run", fake_run)

    media_dir = tmp_path / "media"
    expected = media_dir / "videos" / "scene" / "1080p60" / f"{SCENE_CLASS_NAME}.mp4"
    expected.parent.mkdir(parents=True)
    expected.touch()  # simulate Manim producing the file

    result = renderer.render_scene(tmp_path / "scene.py", quality="h", media_dir=media_dir)

    assert captured["cmd"][:3] == [sys.executable, "-m", "manim"]
    assert "-qh" in captured["cmd"]
    assert SCENE_CLASS_NAME in captured["cmd"]
    assert "--media_dir" in captured["cmd"]
    # Output must stream live, not be captured.
    assert captured["kwargs"].get("capture_output") is not True
    assert result.returncode == 0
    assert result.output_path == expected


def test_render_scene_reports_no_path_on_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(
        renderer.subprocess, "run",
        lambda cmd, **kw: subprocess.CompletedProcess(cmd, returncode=1),
    )
    result = renderer.render_scene(tmp_path / "scene.py", media_dir=tmp_path / "media")
    assert result.returncode == 1
    assert result.output_path is None


def test_render_scene_missing_manim_raises_runtimeerror(monkeypatch, tmp_path):
    def boom(cmd, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(renderer.subprocess, "run", boom)
    with pytest.raises(RuntimeError):
        renderer.render_scene(tmp_path / "scene.py")
