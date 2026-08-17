"""An MCP server that lets an agent drive the renderer over a protocol.

This is the concrete answer to "usable by an AI agent": an MCP client can list
what the library draws, plan cheaply, check a plan before committing, and only
then spend a render — reading the QC findings back and iterating. It is a thin
shell over the same typed API the CLI uses; the tool boundaries are the design.

The boundaries matter more than the code. The tools are deliberately *granular* —
``list_templates``, ``plan``, ``validate`` are cheap and answer "what and
whether"; ``render`` is the one that costs ten minutes of a core. An agent that
can call the cheap ones first stops before wasting the expensive one, which is
the whole reason plan/validate/render are separate calls rather than one
``make_video`` that fuses them and discovers the plan was wrong too late.

Failures come back as data, not exceptions. Every tool catches
:class:`~straightedge.errors.StraightedgeError` and returns the same
``{ok: false, error: {code, message, remedy, details}}`` shape the CLI's
``--json`` mode emits, so an agent branches on ``code`` and follows ``remedy``
rather than reading a stack trace.

Run it:  ``python -m straightedge.mcp_server``  (stdio transport)
Install: ``pip install 'straightedge[mcp]'``
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .catalog import as_dicts
from .errors import StraightedgeError
from .estimate import estimate
from .planner import build_plan
from .preconditions import blocking, validate as _validate
from .qc import check_sidecar
from .renderer import render_scene, write_scene


def build_server():
    """Construct the MCP server. Imported lazily so the SDK is an optional dep."""
    try:
        from mcp.server import MCPServer
    except ImportError as exc:  # pragma: no cover - exercised by the extra's absence
        raise StraightedgeError(
            "The MCP server needs the mcp extra.",
            remedy="Install it: pip install 'straightedge[mcp]'.",
        ) from exc

    server = MCPServer(
        name="straightedge",
        version="0.1",
        instructions=(
            "Render math animations and figures from a request. Call "
            "list_templates to see what exists and how each is invoked, plan to "
            "turn a request into a plan cheaply, validate to check a plan will "
            "draw what was asked before spending a render, and render only once "
            "the plan looks right — render is the expensive step."
        ),
    )

    @server.tool(
        description=(
            "List every template the library can draw, across both lanes — "
            "animation (Manim → MP4) and figure (Python → SVG) — each with how "
            "it is invoked and the parameters it reads. Call this first."
        ),
    )
    def list_templates() -> dict[str, Any]:
        return {"ok": True, "templates": as_dicts()}

    @server.tool(
        description=(
            "Turn a request into an animation plan without rendering. Cheap. "
            "Give either a natural-language request (routed by keyword, "
            "Chinese-first) or a template id from list_templates (exact, any "
            "language). Returns the plan and any precondition violations."
        ),
    )
    def plan(request: str = "", template: str = "",
             params: dict | None = None) -> dict[str, Any]:
        return _guarded(lambda: _plan_payload(request, template, params))

    @server.tool(
        description=(
            "Check whether a plan will draw what was asked, without rendering. "
            "Give a request or a template id (see plan). Returns blocking "
            "violations (which stop a render), warnings (which do not), whether "
            "it matched a specific builder or fell back to a generic one, and a "
            "rough render-time estimate. The decision point before the render."
        ),
    )
    def validate(request: str = "", quality: str = "l", template: str = "",
                 params: dict | None = None) -> dict[str, Any]:
        def go():
            built = _plan_for(request, template, params)
            violations = _validate(built)
            fatal = blocking(violations)
            return {
                "ok": True,
                "concept": built.concept or built.topic,
                "match": built.match,
                "blocking": [str(v) for v in fatal],
                "warnings": [str(v) for v in violations if v not in fatal],
                "renderable": not fatal,
                "estimate": estimate(built, quality).to_dict(),
            }
        return _guarded(go)

    @server.tool(
        description=(
            "Render to an MP4 and check the result. Expensive — about ten "
            "minutes of one CPU core. Give a request or a template id (see "
            "plan); a template renders in any language with no keyword routing. "
            "Refuses a plan with a blocking precondition unless force=True. "
            "Returns the output path and the QC findings on the finished frame."
        ),
    )
    def render(request: str = "", language: str = "en", quality: str = "l",
               force: bool = False, template: str = "",
               params: dict | None = None) -> dict[str, Any]:
        return _guarded(
            lambda: _render(request, language, quality, force, template, params))

    return server


# --------------------------------------------------------------- tool bodies


def _plan_for(request: str, template: str, params: dict | None):
    """Build a plan from a request or a named template — the caller gives one.

    A template skips the keyword router, so it is the language-independent path
    to a named animation; a request is routed by keyword.
    """
    from .errors import RequestError
    from .planner import plan_from_template

    if template:
        return plan_from_template(template, params)
    if not request:
        raise RequestError(
            "Give a request or a template.",
            remedy="Pass request text, or a template id from list_templates.")
    return build_plan(request)


def _plan_payload(request: str, template: str = "",
                  params: dict | None = None) -> dict[str, Any]:
    built = _plan_for(request, template, params)
    payload = built.to_dict()
    payload["violations"] = [str(v) for v in _validate(built)]
    payload["match"] = built.match
    payload["estimate"] = estimate(built).to_dict()
    return {"ok": True, "plan": payload}


def _render(request: str, language: str, quality: str, force: bool,
            template: str = "", params: dict | None = None) -> dict[str, Any]:
    from .errors import PreconditionError, RenderError

    built = _plan_for(request, template, params)
    violations = _validate(built)
    fatal = blocking(violations)
    if fatal and not force:
        raise PreconditionError(
            f"{len(fatal)} precondition(s) say this plan will not show what was "
            "requested.",
            remedy="Call render again with force=true to draw it anyway, or plan "
                   "a different request.",
            details={"violations": [str(v) for v in fatal]})

    # Each render gets its own directory so concurrent tool calls never clobber
    # one another's scene.py or sidecar — the isolation the library leaves to the
    # caller, which for a shared server is this server's job.
    work = Path(tempfile.mkdtemp(prefix="straightedge-mcp-"))
    try:
        sidecar = work / "qc.json"
        scene = write_scene(built, work, language=language, qc_sidecar=sidecar)
        # Stdio transport owns stdout for the JSON-RPC stream. Manim inherits
        # stdout by default, so its progress would corrupt the protocol channel
        # and break the client — send it to stderr, where it is harmless.
        result = render_scene(scene, quality=quality, media_dir=work / "media",
                              stdout=sys.stderr)
        if result.returncode != 0 or result.output_path is None:
            raise RenderError(
                "Manim ran but did not produce the expected file.",
                remedy="Try a different request, or plan it first to inspect the "
                       "scene.",
                details={"returncode": result.returncode})

        # Copy the MP4 out of the temp dir before it is removed; hand back a path
        # the caller can actually open.
        out = work.parent / result.output_path.name
        shutil.copy2(result.output_path, out)
        findings = check_sidecar(sidecar) if sidecar.exists() else []
        return {
            "ok": True,
            "output": str(out),
            "concept": built.concept or built.topic,
            "qc": [asdict(f) for f in findings],
            "violations": [str(v) for v in violations],
        }
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _guarded(fn) -> dict[str, Any]:
    """Run a tool body, turning an expected failure into a data result.

    An agent should branch on a returned ``error`` object, not catch an
    exception across the protocol — so a StraightedgeError becomes the same
    ``{ok: false, error: {...}}`` shape the CLI emits. Anything else is a bug and
    is left to propagate, because hiding it behind a code would make it look
    handled.
    """
    try:
        return fn()
    except StraightedgeError as exc:
        return {"ok": False, "error": exc.to_dict()}


def main() -> None:
    """Entry point: run the server over stdio."""
    import asyncio

    asyncio.run(build_server().run_stdio_async())


if __name__ == "__main__":
    main()
