"""Render one scene per builder and collect its QC findings.

Not a test: it renders for real, which is minutes per scene, and its output is a
table to read rather than an assertion. The point is to find out whether the
caption/tick collision fixed in calculus/derivative_tangent is one builder's
bug or a shared layout habit.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

# Run from a checkout without installing. Python puts *this file's* directory on
# the path, not the repo root, so the imports below fail on a venv that has
# Manim but no editable install of the package they are here to exercise —
# which is the state a fresh clone is in, and the state this script was
# published in.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from straightedge import build_plan
from straightedge.calculus import ConceptCalculus
from straightedge.conics import ConceptConic
from straightedge.models import AnimationPlan, Topic
from straightedge.qc import check_sidecar
from straightedge.renderer import manim_command, write_scene

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "sweep-out")

# Requests that reach each concept through the planner, so the sweep exercises
# the same route a user takes.
BY_REQUEST = [
    ("calculus/derivative_tangent", "画 y=x^2 的导数，用割线逼近切线"),
    ("calculus/riemann_integral", "画 y=x^2+1 的积分面积，用黎曼矩形展示"),
    ("calculus/ftc_accumulation", "用 y=x^2 展示微积分基本定理，变上限面积函数 F(x)"),
    ("calculus/taylor_series", "画 sin(x) 的泰勒展开，多项式逼近"),
    ("trig (generic)", "画一个正弦函数，标出周期和振幅"),
    ("trig/graph_transform", "画 y=2sin(3x)+1 的图像"),
    ("trig/unit_circle_to_sine", "用单位圆展示正弦函数的生成"),
    ("conic/ellipse_foci", "画一个圆锥曲线中的椭圆，显示焦点和长轴"),
    ("conic/parabola_focus_directrix", "画抛物线的焦点和准线"),
    ("3d/solid_overview", "画一个圆柱"),
    ("3d/three_views", "画一个正方体，展示三视图"),
    ("3d/cube_section", "画一个正方体的截面，过 A B C 三点"),
    ("3d/sphere_section", "球的截面是什么形状"),
    ("geometry (generic)", "画一个三角形，展示相似"),
    ("function (generic)", "画 y=x^2-4x+3，标出顶点和零点"),
]

# No phrasing routes to these; they are reachable only by a caller that names
# the concept, which is how the job API drives them. Worth a finding of its own.
BY_PLAN = [
    ("conic/cone_slice", AnimationPlan(
        topic=Topic.CONIC, title_zh="Where the Conics Come From",
        objective_zh="目标", english_prompt="cone",
        concept=ConceptConic.CONE_SLICE, parameters={})),
    ("calculus/tangent_shift", AnimationPlan(
        topic=Topic.CALCULUS, title_zh="Lift the curve",
        objective_zh="objective", english_prompt="tangent shift",
        concept=ConceptCalculus.TANGENT_SHIFT, parameters={})),
]


def run(name: str, plan: AnimationPlan, language: str) -> dict:
    slug = name.replace("/", "_").replace(" ", "_").replace("(", "").replace(")", "")
    work = OUT / language / slug
    work.mkdir(parents=True, exist_ok=True)
    sidecar = work / "qc.json"
    if sidecar.exists():
        sidecar.unlink()

    scene = write_scene(plan, work, aspect="16:9", language=language,
                        qc_sidecar=sidecar)
    started = time.time()
    completed = subprocess.run(
        manim_command(scene, "l", work / "media", "16:9"),
        capture_output=True, text=True)
    elapsed = time.time() - started

    if completed.returncode != 0:
        tail = (completed.stderr or completed.stdout or "").strip().splitlines()
        return {"concept": name, "language": language, "rendered": False,
                "seconds": round(elapsed, 1),
                "error": tail[-1][:160] if tail else "render failed"}

    findings = check_sidecar(sidecar)
    return {
        "concept": name,
        "language": language,
        "rendered": True,
        "seconds": round(elapsed, 1),
        "errors": sum(1 for f in findings if f.severity == "error"),
        "warnings": sum(1 for f in findings if f.severity == "warn"),
        "findings": [{"check": f.check, "severity": f.severity,
                      "message": f.message, "label": f.label} for f in findings],
    }


def main() -> int:
    jobs = [(n, build_plan(r)) for n, r in BY_REQUEST] + BY_PLAN
    results = []
    for language in ("en", "zh"):
        for name, plan in jobs:
            result = run(name, plan, language)
            results.append(result)
            mark = ("FAIL" if not result["rendered"]
                    else f"{result['errors']}E {result['warnings']}W")
            print(f"  [{language}] {name:34s} {mark:>10s} "
                  f"{result['seconds']:6.1f}s", flush=True)
            OUT.mkdir(parents=True, exist_ok=True)
            (OUT / "sweep.json").write_text(
                json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
