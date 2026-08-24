from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Sequence

from .agent import run_agent_plan, run_agent_render, run_agent_scaffold
from .agent.llm import LLMError
from .aspect import ASPECTS, LANDSCAPE
from .style import TEXTBOOK, THEME_NAMES, theme
from .errors import (
    BlankFigureError, DependencyError, FontError, InputFileError, PreconditionError, RenderError, RequestError, StraightedgeError, UnknownTemplateError,
)
from .fonts import DEFAULT_CJK_FONT, font_status
from .labels import DEFAULT_LANGUAGE, LANGUAGES, needs_cjk_font, untranslated
from .catalog import as_dicts
from .estimate import estimate
from .planner import build_plan, plan_from_template
from .preconditions import Violation, blocking, validate
from .qc import check_sidecar, worst_severity
from .renderer import render_scene, write_scene
from .stt import transcribe_audio


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="straightedge")
    parser.add_argument("command", choices=[
        "plan", "scaffold", "render", "draw",
        "agent-plan", "agent-scaffold", "agent-render",
        "list-templates",
    ])
    parser.add_argument("text", nargs="?",
                        help="The request, in Chinese, routed to a template by "
                             "keyword. For English or an exact template, use "
                             "--template instead.")
    parser.add_argument("--template",
                        help="Render a named animation template directly, in any "
                             "language, no keyword routing. See `list-templates` "
                             "for the ids, e.g. calculus/derivative_tangent.")
    parser.add_argument("--params",
                        help="JSON object of parameters for --template, "
                             'e.g. \'{"expression": "x**2"}\'.')
    parser.add_argument("--audio", type=Path,
                        help="Transcribe an audio file into the request (Chinese "
                             "STT, opt-in). An alternative to typing the request.")
    parser.add_argument("--out", type=Path,
                        help="Where `draw` writes the SVG. Without it the "
                             "document goes to stdout, so it pipes.")
    parser.add_argument("--output-dir", type=Path, default=Path("generated"))
    parser.add_argument("--media-dir", type=Path, default=Path("media"),
                        help="Directory Manim writes rendered media into")
    parser.add_argument("--quality", default="l", choices=["l", "m", "h", "p", "k"],
                        help="Manim quality: l=480p m=720p h=1080p p=1440p k=2160p")
    parser.add_argument("--aspect", default=LANDSCAPE, choices=list(ASPECTS),
                        help="Frame shape: 16:9 landscape, 9:16 vertical (shorts)")
    parser.add_argument("--language", default=DEFAULT_LANGUAGE, choices=list(LANGUAGES),
                        help="On-screen label language, English by default "
                             "(narration is separate)")
    parser.add_argument("--beat-seconds", type=Path,
                        help="JSON file mapping beat key to measured narration "
                             "seconds, e.g. {\"b01\": 3.2}; each step then runs "
                             "as long as the voice over it")
    parser.add_argument("--style", default=TEXTBOOK.name, choices=list(THEME_NAMES),
                        help="Palette: textbook is Manim's own colours (default), "
                             "paper is light for print, dataflow is the dark "
                             "technical look the examples use")
    parser.add_argument("--font", default=DEFAULT_CJK_FONT,
                        help="CJK font for Chinese labels (must be installed)")
    parser.add_argument("--skip-font-check", action="store_true",
                        help="Skip the preflight CJK-font check before rendering")
    parser.add_argument("--model", help="LLM model for agent-* commands")
    parser.add_argument("--max-attempts", type=int, default=3,
                        help="Maximum LLM review/repair attempts for agent-* commands")
    parser.add_argument("--no-fallback", action="store_true",
                        help="Disable deterministic-template fallback for agent-render")
    parser.add_argument("--force", action="store_true",
                        help="Draw the plan even when a precondition says it will "
                             "not show what was asked for")
    parser.add_argument("--qc", action="store_true",
                        help="Check the rendered scene for empty, clipped, "
                             "off-frame and overlapping content")
    parser.add_argument("--qc-strict", action="store_true",
                        help="Exit non-zero when --qc reports an error finding")
    parser.add_argument("--qc-report", type=Path,
                        help="Write the QC findings to this file as JSON")
    parser.add_argument("--json", action="store_true", dest="json_out",
                        help="Emit one JSON result object to stdout instead of "
                             "human text — including on failure, where it carries "
                             "the error code and the remedy")
    args = parser.parse_args(argv)
    out = _Emitter(args.json_out)
    try:
        return _dispatch(args, out)
    except StraightedgeError as exc:
        return out.fail(args.command, exc)


class _Emitter:
    """Renders a command's outcome as human text or as one JSON object.

    Not a second mode with its own code path — the same result, rendered
    differently. Human prose still goes where it always went (paths to stdout,
    warnings to stderr); ``--json`` collapses the whole outcome into a single
    object on stdout, success and failure alike, so an agent parses one thing
    and never scrapes a sentence.
    """

    def __init__(self, json_out: bool) -> None:
        self.json_out = json_out

    def say(self, message: str, *, err: bool = False) -> None:
        """Human prose. Silent under ``--json``, where the envelope carries it."""
        if not self.json_out:
            print(message, file=sys.stderr if err else sys.stdout)

    def ok(self, command: str, exit_code: int = 0, **result) -> int:
        if self.json_out:
            print(json.dumps({"ok": exit_code == 0, "command": command, **result},
                             ensure_ascii=False, indent=2))
        return exit_code

    def fail(self, command: str, exc: "StraightedgeError") -> int:
        if self.json_out:
            print(json.dumps({"ok": False, "command": command,
                              "error": exc.to_dict()},
                             ensure_ascii=False, indent=2))
        else:
            print(exc.message, file=sys.stderr)
            if exc.remedy:
                print(exc.remedy, file=sys.stderr)
        return 1


def _dispatch(args: argparse.Namespace, out: _Emitter) -> int:
    # Asking for the report or the exit code is asking for the check. Requiring
    # --qc as well would only create a way to request findings and silently get
    # none, which is the failure the flags exist to prevent.
    run_qc = args.qc or args.qc_strict or args.qc_report is not None

    # Enumeration needs no request; dispatch before one is demanded. This is the
    # command an agent runs first — to find out what the other commands can draw.
    if args.command == "list-templates":
        templates = as_dicts()
        if out.json_out:
            return out.ok("list-templates", templates=templates)
        print(json.dumps(templates, ensure_ascii=False, indent=2))
        return 0

    # `draw` is the figure lane's whole loop in one command: milliseconds, pure
    # standard library, no Manim. It exists because `list-templates` has listed
    # both lanes since it was written while every command reached only the
    # animation one — so the CLI advertised thirty-eight figure templates and
    # could draw none of them, and the honest error it gave for one sent the
    # caller to a Python function. The MCP server had the same gap; this closes
    # the other half of it.
    if args.command == "draw":
        from .diagrams import DIAGRAM_REGISTRY, render_diagram
        from .diagrams.legibility import check_figure
        from .diagrams.registry import count_data_marks

        name = (args.template or args.text or "").strip()
        if not name:
            raise RequestError(
                "no figure named",
                remedy="Give a figure id, e.g. `straightedge draw unit_circle`. "
                       "`list-templates` reports which ids are figures.")
        if name not in DIAGRAM_REGISTRY:
            raise UnknownTemplateError(
                f"unknown figure template: {name!r}",
                remedy="Run `list-templates` and use an id whose lane is 'figure'.",
                details={"template": name, "known": sorted(DIAGRAM_REGISTRY)})

        svg = render_diagram({"type": name, "params": _read_params(args.params)})
        marks = count_data_marks(svg)
        findings = check_figure(svg) if marks else []
        if marks == 0:
            # Chrome with no data is the one failure that looks like success, so
            # it is a refusal here as it is over MCP — and it must not leave a
            # blank file behind for someone to find later.
            from .diagrams.registry import refusal_findings, refusal_reason

            refused = refusal_findings(name, _read_params(args.params))
            if refused:
                # The parameters are fine; the figure asserts something false.
                # Sending this caller to check parameter shapes would point away
                # from the mistake.
                raise BlankFigureError(
                    f"{name!r} was refused: {refusal_reason(refused)}",
                    remedy="Fix what each finding names; the path in brackets "
                           "is the value it is about. The parameters are not "
                           "the problem.",
                    details={"template": name,
                             "findings": [str(f) for f in refused]})
            raise BlankFigureError(
                f"{name!r} drew no data marks",
                remedy="A parameter of the wrong type is read as absent; check "
                       "the shapes reported by `list-templates --json`.",
                details={"template": name})
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(svg, encoding="utf-8")
        if out.json_out:
            return out.ok("draw", template=name, data_marks=marks,
                          bytes=len(svg.encode("utf-8")),
                          findings=[asdict(f) for f in findings],
                          path=str(args.out) if args.out else None,
                          svg=None if args.out else svg)
        if args.out:
            out.say(f"wrote {args.out} ({len(svg.encode('utf-8'))} bytes, "
                    f"{marks} data marks)")
        else:
            print(svg)
        # After the document, and on stderr, so `draw > figure.svg` still yields
        # a figure. Legibility is a warning rather than a refusal: the template
        # drew what was asked for and a caller may still want it — but silence
        # would leave the defect for whoever opens the file.
        for finding in (f for f in findings if f.severity == "error"):
            out.say(f"  {finding}", err=True)
        return 0

    # A named template skips the keyword router entirely — the English-reachable
    # path. It has no request text and does not apply to the LLM agent commands,
    # which take a prompt by definition.
    if args.template is not None:
        if args.command.startswith("agent-"):
            raise RequestError(
                "--template is for the deterministic commands, not the agent ones.",
                remedy="Use `render`/`scaffold`/`plan` with --template, or give "
                       "the agent command a prompt.")
        plan = plan_from_template(args.template, _read_params(args.params))
        violations = validate(plan)
    else:
        request = _read_request(args.text, args.audio)
        if args.command.startswith("agent-"):
            return _run_agent_command(args, request, out)
        plan = build_plan(request)
        violations = validate(plan)

    if args.command == "plan":
        payload = plan.to_dict()
        payload["violations"] = [str(v) for v in violations]
        payload["match"] = plan.match
        payload["estimate"] = estimate(plan, args.quality).to_dict()
        if out.json_out:
            return out.ok("plan", plan=payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    _precondition_gate(violations, force=args.force, out=out)

    beat_seconds = _read_beat_seconds(args.beat_seconds)

    sidecar = args.output_dir / "qc.json" if run_qc else None
    scene_path = write_scene(plan, args.output_dir, font=args.font,
                             beat_seconds=beat_seconds,
                             aspect=args.aspect, language=args.language,
                             qc_sidecar=sidecar, style=theme(args.style))
    untranslated_labels = _warn_untranslated(
        scene_path.read_text(encoding="utf-8"), args.language, out)
    if args.command == "scaffold":
        out.say(str(scene_path))
        return out.ok("scaffold", scene=str(scene_path),
                      untranslated_labels=list(untranslated_labels))

    # A sidecar left over from an earlier run would otherwise be checked as if
    # it described this one — the worst kind of pass, since it looks like the
    # check ran.
    if sidecar is not None and sidecar.exists():
        sidecar.unlink()

    # An English scene has no CJK glyphs left to draw, so a missing CJK font is
    # not a reason to refuse the render.
    if not args.skip_font_check and needs_cjk_font(args.language):
        _font_preflight(args.font, out)

    try:
        # Under --json, Manim's own progress must not land on stdout beside the
        # result object; send it to stderr, where diagnostics belong.
        result = render_scene(scene_path, quality=args.quality,
                              media_dir=args.media_dir, aspect=args.aspect,
                              stdout=sys.stderr if out.json_out else None)
    except RuntimeError as exc:
        raise DependencyError(
            str(exc),
            remedy="Install the render extra: pip install 'straightedge[render]'.",
        ) from exc
    if result.returncode != 0 or result.output_path is None:
        raise RenderError(
            "Manim ran but did not produce the expected file.",
            remedy="Re-run without --json to see Manim's own output, or check "
                   "the scene compiles.",
            details={"returncode": result.returncode,
                     "scene": str(scene_path)},
        )

    out.say(f"Rendered: {result.output_path}")
    findings = _collect_qc(sidecar, report_path=args.qc_report) if sidecar else None
    exit_code = _qc_exit_code(findings, strict=args.qc_strict)
    _report_qc_human(findings, out)
    return out.ok("render", exit_code=exit_code,
                  output=str(result.output_path),
                  qc=[_finding_dict(f) for f in findings] if findings is not None else None)


def _collect_qc(sidecar: Path, *, report_path: Path | None) -> list:
    """Read the render's findings, and write the JSON report if one was asked for."""
    findings = check_sidecar(sidecar)
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps([asdict(f) for f in findings], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return findings


def _qc_exit_code(findings: list | None, *, strict: bool) -> int:
    """Fail only when asked to. A finished render is worth keeping — see below.

    Reported after the render rather than instead of it: the video exists by the
    time this runs, and a label two millimetres over another is a layout fix, not
    a reason to throw away ten minutes of a core. ``--qc-strict`` is for callers
    that would rather fail the pipeline than publish unseen.
    """
    if findings and strict and worst_severity(findings) == "error":
        return 1
    return 0


def _report_qc_human(findings: list | None, out: "_Emitter") -> None:
    if findings is None:
        return
    if not findings:
        out.say("QC: nothing to report.")
        return
    for finding in findings:
        out.say(str(finding), err=True)


def _finding_dict(finding) -> dict:
    return asdict(finding)


def _run_agent_command(args: argparse.Namespace, request: str,
                       out: "_Emitter") -> int:
    if args.command == "agent-plan":
        try:
            spec = run_agent_plan(request, model=args.model)
        except (LLMError, ValueError) as exc:
            raise _agent_error(exc) from exc
        if out.json_out:
            return out.ok("agent-plan", spec=spec.to_dict())
        print(json.dumps(spec.to_dict(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "agent-scaffold":
        try:
            result = run_agent_scaffold(
                request,
                args.output_dir,
                font=args.font,
                model=args.model,
                max_attempts=args.max_attempts,
                aspect=args.aspect,
                language=args.language,
            )
        except (LLMError, ValueError) as exc:
            raise _agent_error(exc) from exc
        out.say(str(result.scene_path))
        out.say(f"Agent concept: {result.spec.topic}/{result.spec.concept}")
        _report_untranslated(result.untranslated_labels, args.language, out)
        if not result.validated:
            out.say("Warning: scene was written without clearing the "
                    "safety/review guardrails; inspect it before rendering.",
                    err=True)
        return out.ok("agent-scaffold", scene=str(result.scene_path),
                      concept=f"{result.spec.topic}/{result.spec.concept}",
                      validated=result.validated,
                      untranslated_labels=list(result.untranslated_labels))

    # Same rule as the deterministic path: a scene with no CJK glyphs left to
    # draw does not need a CJK font, and refusing it would block a host that can
    # serve that render perfectly well.
    if not args.skip_font_check and needs_cjk_font(args.language):
        _font_preflight(args.font, out)
    try:
        result = run_agent_render(
            request,
            args.output_dir,
            args.media_dir,
            quality=args.quality,
            font=args.font,
            model=args.model,
            max_attempts=args.max_attempts,
            allow_fallback=not args.no_fallback,
            aspect=args.aspect,
            language=args.language,
        )
    except (LLMError, RuntimeError, ValueError) as exc:
        raise _agent_error(exc) from exc
    _report_untranslated(result.untranslated_labels, args.language, out)
    for violation in result.violations:
        out.say(violation, err=True)
    if result.output_path is None:
        raise RenderError(
            "The agent could not produce a render.",
            remedy="Try again, raise --max-attempts, or allow the deterministic "
                   "fallback (drop --no-fallback).",
            details={"logs": result.logs[-8000:] if result.logs else "",
                     "violations": list(result.violations)},
        )
    prefix = "Rendered with deterministic fallback" if result.fallback_used \
        else "Rendered"
    out.say(f"{prefix}: {result.output_path}")
    return out.ok("agent-render", output=str(result.output_path),
                  fallback_used=result.fallback_used,
                  violations=list(result.violations),
                  untranslated_labels=list(result.untranslated_labels))


def _agent_error(exc: Exception) -> StraightedgeError:
    """Wrap an agent failure as a typed error the caller can branch on."""
    if isinstance(exc, LLMError):
        return DependencyError(
            str(exc),
            remedy="Set OPENAI_API_KEY (and OPENAI_BASE_URL for a local model), "
                   "or use the non-agent commands.",
        )
    return StraightedgeError(str(exc))


def _read_beat_seconds(path: Path | None) -> dict[str, float] | None:
    """Measured narration lengths, keyed by beat.

    Supplied by the caller rather than measured here: the durations come from
    whatever produced the audio, and this project does not synthesise it. A file
    is the seam — a pipeline that runs TTS writes the map it already computed,
    and nothing has to guess.

    Validated strictly, because the failure it prevents is silent. A key that is
    not a beat is simply never looked up, so a typo'd map renders with default
    timings and a perfectly successful-looking result that ignores the voice.
    """
    if path is None:
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise InputFileError(
            f"Cannot read --beat-seconds file {path}: {exc}",
            remedy="Point --beat-seconds at a readable file, or omit it.",
            details={"path": str(path)}) from exc
    except json.JSONDecodeError as exc:
        raise InputFileError(
            f"--beat-seconds file {path} is not valid JSON: {exc}",
            remedy='The file must be a JSON object like {"b01": 3.2}.',
            details={"path": str(path)}) from exc

    if not isinstance(raw, dict):
        raise InputFileError(
            f"--beat-seconds file {path} must hold a JSON object mapping beat key "
            f'to seconds, e.g. {{"b01": 3.2}}; got {type(raw).__name__}',
            details={"path": str(path)})

    beats: dict[str, float] = {}
    for key, value in raw.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise InputFileError(
                f"--beat-seconds[{key!r}] must be a number of seconds, got {value!r}")
        if value <= 0:
            raise InputFileError(
                f"--beat-seconds[{key!r}] must be positive, got {value!r}; a beat "
                "with no narration should be left out, not set to zero")
        beats[str(key)] = float(value)
    return beats


def _precondition_gate(violations: Sequence[Violation], *, force: bool,
                       out: "_Emitter") -> None:
    """Refuse a plan that will not draw what was asked for, unless forced.

    Checked here rather than left to the caller because of what a render costs:
    roughly ten minutes of one core, and on a single-core lane that is also the
    queue. Spending it to produce the wrong function — beautifully laid out, with
    nothing logged — is the failure :mod:`straightedge.preconditions` exists to
    catch, and the only place it can be caught for free is before the render
    starts.

    ``warn`` violations print and proceed; only ``error`` raises. ``--force``
    overrides, because a human who has read the reason is a better judge than a
    static check, and a plan that is wrong in a way we predicted is still
    sometimes the plan you want to look at.
    """
    if not violations:
        return
    for violation in violations:
        out.say(str(violation), err=True)
    fatal = blocking(violations)
    if not fatal:
        return
    if force:
        out.say(f"Proceeding anyway: --force overrides {len(fatal)} blocking "
                f"precondition(s).", err=True)
        return
    raise PreconditionError(
        f"{len(fatal)} precondition(s) say this plan will not show what was "
        "requested.",
        remedy="Re-run with --force to draw it anyway.",
        details={"violations": [str(v) for v in fatal]})


def _warn_untranslated(code: str, language: str, out: "_Emitter") -> Sequence[str]:
    missing = untranslated(code, language)
    _report_untranslated(missing, language, out)
    return missing


def _report_untranslated(missing: Sequence[str], language: str,
                         out: "_Emitter") -> None:
    """Name the labels that will ship in the wrong language.

    A warning, not a failure. The render is correct in every other respect, and
    a Chinese caption on an English cut is a fix to the catalog rather than a
    reason to throw away a finished video.
    """
    if not missing:
        return
    shown = ", ".join(missing[:5]) + (" ..." if len(missing) > 5 else "")
    out.say(f"Warning: {len(missing)} on-screen label(s) have no {language} "
            f"translation and stay Chinese: {shown}", err=True)


def _font_preflight(font: str, out: "_Emitter") -> None:
    """Warn on a shaky font, raise on a missing one, before spending a render."""
    level, message = font_status(font)
    if level == "error":
        raise FontError(
            message,
            remedy="Install the font, pick another with --font, or skip the "
                   "check with --skip-font-check.",
            details={"font": font})
    if level == "warn":
        out.say(message, err=True)


def _read_request(text: str | None, audio: Path | None) -> str:
    if text:
        return text
    if audio:
        return transcribe_audio(audio)
    raise RequestError(
        "No request given.",
        remedy="Pass the request as an argument, --audio a file to transcribe, "
               "or name a --template.")


def _read_params(raw: str | None) -> dict:
    """Parse the --params JSON object, or an empty dict when absent."""
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise InputFileError(
            f"--params is not valid JSON: {exc}",
            remedy='Pass a JSON object, e.g. \'{"expression": "x**2"}\'.') from exc
    if not isinstance(value, dict):
        raise InputFileError(
            f"--params must be a JSON object, got {type(value).__name__}.",
            remedy='e.g. \'{"expression": "x**2"}\'.')
    return value


if __name__ == "__main__":
    raise SystemExit(main())
