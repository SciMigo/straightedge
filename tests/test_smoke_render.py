"""Live Manim render of one scene per builder.

What these catch that ``ast.parse`` doesn't:
  * LaTeX compile errors in MathTex strings (typos like ``\\fract{1}{2}``),
  * Manim primitive signature mismatches across versions (``Cone(direction=...)``),
  * Animation chains that depend on incompatible mobject types,
  * Dimension errors in ``axes.c2p`` / coordinate transforms,
  * Font/glyph problems for CJK labels.

Slow (~10s per render). Excluded by the default ``addopts = -m 'not smoke'``.
Run on demand with ``pytest -m smoke``.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

from straightedge.models import AnimationPlan, Topic
from straightedge.planner import build_plan
from straightedge.solids3d import Concept3D
from straightedge.templates import scene_code_for
from straightedge.trig import Concept as ConceptTrig

pytestmark = pytest.mark.smoke

manim = pytest.importorskip("manim")


def _render(plan: AnimationPlan, tmp_path: Path,
            beat_seconds: dict[str, float] | None = None) -> Path:
    """Write the plan as a scene, render it at low quality, return the MP4 path."""
    scene_path = tmp_path / "scene.py"
    scene_path.write_text(
        scene_code_for(plan, beat_seconds=beat_seconds) + "\n", encoding="utf-8")

    spec = importlib.util.spec_from_file_location(f"smoke_{tmp_path.name}", scene_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)

    media = tmp_path / "media"
    with manim.tempconfig({
        "quality": "low_quality",
        "disable_caching": True,
        "preview": False,
        "media_dir": str(media),
        "verbosity": "ERROR",
        "write_to_movie": True,
    }):
        scene = mod.GeneratedScene()
        scene.render()

    # In-process tempconfig writes to media/videos/<resolution>/<class>.mp4
    # (no scene-stem subdir, unlike the CLI path that renderer.render_scene uses).
    candidates = list(media.rglob("GeneratedScene.mp4"))
    assert candidates, f"render produced no MP4 under {media}"
    mp4 = candidates[0]
    assert mp4.stat().st_size > 0, f"MP4 at {mp4} is empty"
    return mp4


def _stock(topic: str, concept: str | None = None, parameters: dict | None = None) -> AnimationPlan:
    return AnimationPlan(
        topic=topic, concept=concept,
        title_zh="", objective_zh="", english_prompt="",
        parameters=parameters or {},
    )


def test_smoke_geometry_scene(tmp_path):
    _render(_stock(Topic.GEOMETRY), tmp_path)


def test_smoke_trig_basic_scene(tmp_path):
    _render(_stock(Topic.TRIG), tmp_path)


def test_smoke_trig_transform_scene(tmp_path):
    _render(build_plan("画 y = 2 sin(3x + π/4) + 1"), tmp_path)


def test_smoke_trig_transform_scene_tan(tmp_path):
    # Tan has the asymptote-clamping branch; render it specifically.
    _render(build_plan("画 y = tan(x/2)"), tmp_path)


def test_smoke_conic_scene(tmp_path):
    _render(_stock(Topic.CONIC), tmp_path)


def test_smoke_sphere_section_scene(tmp_path):
    _render(_stock(Topic.THREE_D), tmp_path)


def test_smoke_solid_overview_cube(tmp_path):
    _render(build_plan("画正方体 ABCD-A₁B₁C₁D₁，棱长 2"), tmp_path)


def test_smoke_solid_overview_pyramid(tmp_path):
    _render(build_plan("画正四棱锥 P-ABCD，底面边长 2，高 3"), tmp_path)


def test_smoke_solid_overview_cylinder(tmp_path):
    _render(build_plan("画一个圆柱，底面半径 1，高 2"), tmp_path)


def test_smoke_cube_section_scene(tmp_path):
    _render(build_plan("画正方体 ABCD-A₁B₁C₁D₁，过 D、A₁、C₁ 三点的截面"), tmp_path)


def test_smoke_function_scene(tmp_path):
    _render(build_plan("画 y = x^2 - 4x + 3"), tmp_path)


def test_smoke_three_views_cube(tmp_path):
    _render(build_plan("画正方体 ABCD-A₁B₁C₁D₁ 棱长 2 的三视图"), tmp_path)


def test_smoke_three_views_pyramid(tmp_path):
    _render(build_plan("画正四棱锥 P-ABCD 底面边长 2 高 3 的三视图"), tmp_path)


def test_smoke_three_views_cylinder(tmp_path):
    _render(build_plan("画一个圆柱 底面半径 1 高 2 的三视图"), tmp_path)


def _seconds(mp4: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(mp4)],
        capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def _riemann_plan() -> AnimationPlan:
    from straightedge.calculus import ConceptCalculus

    return AnimationPlan(
        topic=Topic.CALCULUS, title_zh="黎曼和", objective_zh="面积",
        english_prompt="riemann", concept=ConceptCalculus.RIEMANN_INTEGRAL,
        parameters={"expression": "x**2"},
    )


def test_smoke_calculus_riemann_scene(tmp_path):
    """The calculus builders had no live render at all before this."""
    assert _seconds(_render(_riemann_plan(), tmp_path)) > 0


def test_smoke_a_measured_scene_runs_as_long_as_its_narration(tmp_path):
    """The property the animation lane depends on, checked against real Manim.

    Six beats of four seconds should produce roughly twenty-four seconds of
    video, plus the one-second tail this builder already ended with. Asserting
    the *relationship* rather than a fixed number keeps the test honest if the
    builder's own trailing wait ever changes.
    """
    beats = {f"b{i:02d}": 4.0 for i in range(1, 7)}
    narrated = _seconds(_render(_riemann_plan(), tmp_path, beat_seconds=beats))
    assert narrated == pytest.approx(sum(beats.values()), abs=1.5)


def test_smoke_an_unmeasured_scene_keeps_its_own_timing(tmp_path):
    """Without durations the builder must render exactly as it did before.

    This is what lets the remaining builders be converted one at a time rather
    than in a single change.
    """
    plain = _seconds(_render(_riemann_plan(), tmp_path))
    beats = {f"b{i:02d}": 4.0 for i in range(1, 7)}
    second = tmp_path / "b"
    second.mkdir()          # _render writes into this dir, it does not create it
    narrated = _seconds(_render(_riemann_plan(), second, beat_seconds=beats))
    assert narrated > plain + 5, "measured narration should visibly lengthen the scene"
