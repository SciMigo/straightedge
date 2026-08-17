"""The loop an agent runs to make a figure it can trust, end to end.

Not a wrapper around one call — the point is the *sequence*, because each step
lets the loop stop before the next one costs anything:

    discover  →  plan  →  validate  →  render  →  read the check  →  react

An LLM writing this animation by hand is blind: it emits code, the code renders,
and nothing tells it the caption ran through the axis labels. This library is the
thing that can see. So the loop does not end at "rendered" — it ends at "checked",
and the finding is what an agent acts on.

Run it (needs the render extra):

    pip install 'straightedge[render]'
    python examples/agent_loop.py "画 y=x^2 的导数，用割线逼近切线"

It prints each step as JSON, the way an agent would read it, and exits non-zero
if the render came back with a blocking QC finding — so this doubles as a check
you can put in front of a publish.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import straightedge as se


def run(request: str) -> int:
    # 1. Discover. An agent cannot use what it cannot enumerate; this is the
    #    call that says what exists and how each thing is invoked.
    catalogue = se.list_templates()
    reachable = [t for t in catalogue
                 if t.lane == "animation" and t.invocation == "prompt"]
    _step("discover", {"templates": len(catalogue),
                       "prompt_reachable_animation": len(reachable)})

    # 2. Plan. Cheap: turn the request into a plan without drawing anything.
    plan = se.build_plan(request)
    _step("plan", {"concept": plan.concept or plan.topic})

    # 3. Validate. Still free. A blocking violation means the plan will not draw
    #    what was asked — the moment to stop, before a render costs ten minutes.
    violations = se.validate(plan)
    blocking = se.blocking(violations)
    _step("validate", {"blocking": [str(v) for v in blocking],
                       "renderable": not blocking})
    if blocking:
        _step("stop", {"reason": "a precondition says this will draw the wrong "
                                 "thing; not spending a render on it"})
        return 1

    # 4. Render, with the visual check switched on. This is the expensive step,
    #    and the only one reached once the cheap ones have cleared the plan.
    work = Path(tempfile.mkdtemp(prefix="straightedge-loop-"))
    sidecar = work / "qc.json"
    scene = se.write_scene(plan, work, qc_sidecar=sidecar)
    result = se.render_scene(scene, media_dir=work / "media", stdout=sys.stderr)
    if result.returncode != 0 or result.output_path is None:
        _step("render", {"ok": False})
        return 1
    _step("render", {"ok": True, "output": str(result.output_path)})

    # 5. Read the check. The findings are the reason the loop exists — an agent
    #    reads these, not the video it cannot watch.
    from straightedge.qc import check_sidecar, worst_severity
    findings = check_sidecar(sidecar)
    _step("check", {"findings": [str(f) for f in findings] or "clean",
                    "worst": worst_severity(findings)})

    # 6. React. An error means the frame is not publishable as-is; a warning is
    #    information. What an agent does here — adjust the request, pick another
    #    concept, escalate to the LLM path — is the interesting part, and it can
    #    only happen because step 5 gave it something to read.
    if worst_severity(findings) == "error":
        _step("react", {"verdict": "not publishable — the render has a blocking "
                                   "visual defect; revise and run the loop again"})
        return 1
    _step("react", {"verdict": "publishable"})
    return 0


def _step(name: str, payload: dict) -> None:
    print(f"{name}: {json.dumps(payload, ensure_ascii=False)}")


if __name__ == "__main__":
    request = sys.argv[1] if len(sys.argv) > 1 else "画 y=x^2 的导数，用割线逼近切线"
    raise SystemExit(run(request))
