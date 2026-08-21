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

``draw`` is the figure lane's counterpart to ``render`` and is nothing like it
in cost: milliseconds, pure standard library, no Manim and no video. It exists
because ``list_templates`` advertised both lanes from the beginning while every
other tool reached only the animation one — so an agent could see thirty-eight
figure templates listed and had no way to draw a single one of them. It returns
the SVG together with ``data_marks``, because a template handed parameters it
cannot interpret renders its chrome and nothing else, and several kilobytes of
empty axes is the one failure that looks exactly like success.

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
import subprocess
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

from . import __version__
from .catalog import as_dicts
from .diagrams import DIAGRAM_REGISTRY, render_diagram
from .diagrams.legibility import check_figure
from .diagrams.registry import count_data_marks
from .errors import BlankFigureError, RequestError, StraightedgeError, UnknownTemplateError
from .estimate import estimate
from .planner import build_plan
from .preconditions import blocking, validate as _validate
from .qc import check_sidecar, worst_severity
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
        # Read from the package rather than restated, so a release bump cannot
        # leave clients being told they are talking to an older server.
        version=__version__,
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
            "it is invoked, the parameters it reads, and a worked `example` "
            "that is arguments ready to paste: `type` + `params` into draw for "
            "a figure, `template` + `params` into plan or render for an "
            "animation. `example_request` is the other door into the animation "
            "lane — routing is by keyword and Chinese-first, so it is the "
            "phrasing that actually reaches that template. Every example is "
            "checked by the test suite, so it draws. Call this first. Pass "
            "examples=false for a listing about a third smaller, if the "
            "parameter names alone are enough."
        ),
    )
    def list_templates(examples: bool = True) -> dict[str, Any]:
        rows = as_dicts()
        if not examples:
            rows = [{k: v for k, v in row.items()
                     if k not in ("example", "example_request")} for row in rows]
        return {"ok": True, "templates": rows}

    @server.tool(
        description=(
            "Draw a figure — one of the SVG templates from list_templates — and "
            "return the SVG. Cheap: milliseconds, pure standard library, no "
            "Manim and no video, so this is the tool for diagrams rather than "
            "animations. Give the template id as `type` and its parameters as "
            "`params` (list_templates reports which parameters each one reads). "
            "Check `data_marks` in the reply: a template given parameters it "
            "cannot interpret still draws its axes and frame, so zero marks "
            "means the figure is empty however many bytes came back. Read "
            "`findings` too: each one carries the box of the defect it names, so "
            "an `error` — two labels in the same pixels, a caption past the edge "
            "— tells you where to move something rather than only that the "
            "figure is wrong."
        ),
    )
    def draw(type: str = "", params: dict | None = None) -> dict[str, Any]:
        return _guarded(lambda: _draw_payload(type, params))

    @server.tool(
        description=(
            "Decide what a compass-and-straightedge construction asserts about "
            "itself, without drawing it. Give the same `steps` the construction "
            "figure takes (the notation or the structured form) plus `claims` — "
            "for example {\"claim\": \"perpendicular\", \"of\": [\"[ C D ]\", "
            "\"[ A B ]\"]}. Every claim is decided by exact arithmetic rather "
            "than measured, so a result is a proof and not a tolerance. Empty "
            "findings means every claim held; an `error` means the construction "
            "does not satisfy it and `draw` will refuse to render it; a `warn` "
            "means it could not be certified and is neither proved nor "
            "disproved. Check before you draw."
        ),
    )
    def verify_construction(steps: Any = None,
                            claims: list | None = None) -> dict[str, Any]:
        return _guarded(lambda: _verify_payload(steps, claims))

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


def _parameters_for(name: str) -> list[dict]:
    """What the named figure template reads, with types where the code says."""
    from .catalog import list_templates

    for template in list_templates():
        if template.id == name:
            return template.parameters
    return []


def _verify_payload(steps: Any, claims: list | None) -> dict[str, Any]:
    """Decide a construction's claims, drawing nothing.

    The cheap step before the cheap step: `draw` already costs milliseconds, but
    a construction whose claim is false is refused there and comes back blank
    with no reason attached, because a template returns a string. This returns
    the reasons.
    """
    from .diagrams.templates.construction import verify as _verify

    if not steps:
        raise RequestError(
            "no construction to verify",
            remedy="Pass `steps` as the notation or the structured step list.",
        )
    findings = _verify({"steps": steps, "claims": claims or []})
    return {
        "ok": True,
        "findings": [asdict(f) for f in findings],
        "holds": not findings,
        "worst": worst_severity(findings),
        # An error blocks the drawing; a warning does not. Saying so here spares
        # the caller re-deriving the policy from the severities.
        "would_draw": worst_severity(findings) != "error",
    }


def _draw_payload(diagram_type: str, params: dict | None) -> dict[str, Any]:
    """Render one figure, and say whether anything actually landed on it."""
    name = (diagram_type or "").strip()
    if not name:
        raise RequestError(
            "no figure named",
            remedy="Pass `type` as one of the figure template ids from list_templates.",
        )
    if name not in DIAGRAM_REGISTRY:
        raise UnknownTemplateError(
            f"unknown figure template: {name!r}",
            remedy="Call list_templates and use an id whose lane is 'figure'.",
            details={"known": sorted(DIAGRAM_REGISTRY)},
        )
    svg = render_diagram({"type": name, "params": params or {}})
    marks = count_data_marks(svg)
    if marks == 0:
        # The tool can tell from its own mark count that nothing landed, so
        # `ok: true` beside zero marks would be a claim of success it has
        # already disproved. The accepted parameters travel with the failure,
        # because a blank figure is almost always a parameter-shape mismatch and
        # the caller cannot fix what it cannot see: an agent asked for the unit
        # circle at "pi/4" and got an empty result reported as fine.
        # A blank is almost always a parameter-shape mismatch — but not always.
        # A construction that asserts something false is *refused*, and telling
        # its caller to check parameter shapes sends them to look at input that
        # is already correct. Where the template can say why, it says why.
        from .diagrams.templates.construction import refusal_findings

        refused = [asdict(f) for f in refusal_findings(name, params or {})]
        if refused:
            raise BlankFigureError(
                f"{name!r} was refused: it asserts something it does not satisfy",
                remedy="Fix the construction or drop the claim; call "
                       "verify_construction with the same steps to see each "
                       "finding. The parameters are not the problem.",
                details={"type": name, "findings": refused},
            )
        raise BlankFigureError(
            f"{name!r} drew no data marks",
            remedy="Check the parameter shapes in `details.parameters` — a value "
                   "of the wrong type is read as absent — then call draw again.",
            details={"type": name, "given": sorted((params or {})),
                     "parameters": _parameters_for(name)},
        )
    return {
        "ok": True,
        "type": name,
        "svg": svg,
        # UTF-8 length, not character count. `len(svg)` counts code points, so a
        # figure with Chinese labels under-reported its payload by the width of
        # every multi-byte glyph in it — and a field called `bytes` that is not
        # bytes is worse than no field.
        "bytes": len(svg.encode("utf-8")),
        "characters": len(svg),
        "data_marks": marks,
        # Where the figure is *wrong*, not merely that it rendered. Each finding
        # carries the box of the thing it is about, which is the answer a caller
        # can act on — and is only available because this lane computes its own
        # geometry rather than asking a browser for it.
        "findings": [asdict(f) for f in check_figure(svg)],
        # Kept for callers that branch on it; it is now always False, because a
        # figure with no marks raises BlankFigureError instead.
        "blank": False,
    }


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


def _tex_has(cls: str) -> bool:
    """Whether this TeX installation can find one class or package file."""
    try:
        found = subprocess.run(["kpsewhich", cls], capture_output=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return True          # cannot tell; absence of evidence is not evidence
    return found.returncode == 0 and bool(found.stdout.strip())


def _missing_render_runtime() -> list[str]:
    """What the animation lane needs and this host does not have.

    The whole chain, not the headline parts: scenes use MathTex, so Manim goes
    LaTeX -> DVI -> SVG, and a host with manim, ffmpeg and latex but no dvisvgm
    fails deep in the render — the failure this check exists to pre-empt. The
    same is true of a TeX installation missing the class the emitted preamble
    asks for, which is why the smoke workflow installs texlive-latex-extra.
    """
    missing: list[str] = []
    try:
        import manim  # noqa: F401
    except ImportError:
        missing.append("manim (pip install 'straightedge[render]')")
    for binary, note in (("ffmpeg", "ffmpeg"),
                         ("latex", "a LaTeX distribution"),
                         ("dvisvgm", "dvisvgm (Manim's DVI to SVG step)")):
        if shutil.which(binary) is None:
            missing.append(note)
    # Only probed when TeX is present enough to answer: kpsewhich missing means
    # unknown, not absent, and reporting a guess would send a caller to install
    # something they may already have.
    if shutil.which("kpsewhich") and not _tex_has("standalone.cls"):
        missing.append("standalone.cls (texlive-latex-extra)")
    return missing


def _render(request: str, language: str, quality: str, force: bool,
            template: str = "", params: dict | None = None) -> dict[str, Any]:
    from .errors import DependencyError, PreconditionError, RenderError

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

    # After the plan is judged, before any work is spent. An invalid plan is the
    # caller's to fix whatever this host has; a missing runtime is the host's.
    # Without this the lane failed deep in the pipeline with "Manim ran but did
    # not produce the expected file", which sends a caller to their plan rather
    # than their machine — and the extra alone does not fix it, because ffmpeg
    # and LaTeX are system packages pip cannot install.
    missing = _missing_render_runtime()
    if missing:
        raise DependencyError(
            "the animation lane needs " + ", ".join(missing),
            remedy="Install them on this host, or use `draw` for a figure — it "
                   "is pure standard library and needs none of them.",
            details={"missing": missing, "lane": "animation"})

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
