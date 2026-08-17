"""The worked example runs the loop it documents.

An example that has drifted from the API teaches the wrong thing, so this pins
the two outcomes it exists to show: a plan that validates cleanly reaches the
render, and a plan a precondition blocks stops before one. The render is mocked
— the loop's logic is the subject, not Manim.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parent.parent / "examples" / "agent_loop.py"


def _load():
    spec = importlib.util.spec_from_file_location("agent_loop", _PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_clean_plan_runs_the_whole_loop(monkeypatch, tmp_path, capsys):
    loop = _load()

    class Result:
        returncode = 0
        output_path = tmp_path / "GeneratedScene.mp4"

    monkeypatch.setattr(loop.se, "render_scene",
                        lambda *a, **k: Result())
    monkeypatch.setattr(loop.se, "write_scene",
                        lambda plan, d, **k: tmp_path / "scene.py")
    # No sidecar written, so the check reads nothing and reports clean.
    import straightedge.qc as qc
    monkeypatch.setattr(qc, "check_sidecar", lambda p: [])

    code = loop.run("画 y=x^2 的导数")
    out = capsys.readouterr().out
    assert code == 0
    for step in ("discover", "plan", "validate", "render", "check", "react"):
        assert step in out, f"the loop should reach {step}"


def test_a_blocked_plan_stops_before_rendering(monkeypatch, capsys):
    loop = _load()
    from straightedge.preconditions import Violation

    monkeypatch.setattr(loop.se, "validate",
                        lambda plan: [Violation("c", "p", "boom")])
    rendered = []
    monkeypatch.setattr(loop.se, "render_scene",
                        lambda *a, **k: rendered.append(1))

    code = loop.run("画 y=sin(x)")
    out = capsys.readouterr().out
    assert code == 1
    assert "stop" in out
    assert not rendered, "a blocked plan must never reach the render"


def test_an_error_finding_makes_it_unpublishable(monkeypatch, tmp_path, capsys):
    loop = _load()
    from straightedge.qc import Finding

    class Result:
        returncode = 0
        output_path = tmp_path / "v.mp4"

    monkeypatch.setattr(loop.se, "render_scene", lambda *a, **k: Result())
    monkeypatch.setattr(loop.se, "write_scene",
                        lambda plan, d, **k: tmp_path / "scene.py")
    import straightedge.qc as qc
    monkeypatch.setattr(qc, "check_sidecar",
                        lambda p: [Finding("text_overlap", "error", "two labels")])

    code = loop.run("画 y=x^2")
    assert code == 1
    assert "not publishable" in capsys.readouterr().out
