from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from straightedge.aspect import LANDSCAPE
from straightedge.fonts import DEFAULT_CJK_FONT
from straightedge.labels import DEFAULT_LANGUAGE, untranslated
from straightedge.planner import build_plan
from straightedge.preconditions import blocking, validate
from straightedge.renderer import write_scene
from straightedge.templates import scene_code_for

from .executor import render_scene_captured, write_code_scene
from .llm import OpenAICompatibleClient
from .planner import plan_with_llm
from .repair import repair_code_with_llm
from .reviewer import review_code_with_llm, review_to_text
from .safety import check_scene_code
from .schemas import AnimationSpec
from .writer import write_code_with_llm


@dataclass(frozen=True)
class AgentResult:
    spec: AnimationSpec
    scene_path: Path
    code: str
    output_path: Path | None = None
    attempts: int = 0
    fallback_used: bool = False
    # True once the code has passed safety + review (or for a trusted
    # deterministic fallback). False means it was written without clearing the
    # guardrails — the caller should treat the scene as unvalidated.
    validated: bool = False
    logs: str = ""
    # On-screen labels left in the authored language because nothing translated
    # them. Reported, not raised: the geometry is right and the video is worth
    # keeping while the wording is fixed. Empty for a same-language render.
    untranslated_labels: tuple[str, ...] = ()
    # Precondition violations on the deterministic fallback's plan, as strings.
    # Only ever populated on the fallback path: preconditions are keyed on
    # ``plan.concept``, and LLM-written code has no plan to key on.
    violations: tuple[str, ...] = ()


def run_agent_plan(
    request_zh: str,
    *,
    client: OpenAICompatibleClient | None = None,
    model: str | None = None,
) -> AnimationSpec:
    client = client or OpenAICompatibleClient.from_env(model=model)
    return plan_with_llm(client, request_zh)


def run_agent_scaffold(
    request_zh: str,
    output_dir: Path,
    *,
    font: str = DEFAULT_CJK_FONT,
    client: OpenAICompatibleClient | None = None,
    model: str | None = None,
    max_attempts: int = 2,
    aspect: str = LANDSCAPE,
    language: str = DEFAULT_LANGUAGE,
) -> AgentResult:
    client = client or OpenAICompatibleClient.from_env(model=model)
    spec = plan_with_llm(client, request_zh)
    code = write_code_with_llm(client, spec, font=font, aspect=aspect, language=language)
    code, logs, attempts, validated = _review_and_repair(
        client, spec, code, max_attempts=max_attempts,
        aspect=aspect, language=language)
    scene_path = write_code_scene(code, output_dir, aspect=aspect)
    # Read back rather than checked in memory: ``write_code_scene`` may inject
    # the frame declaration, so the file is the artifact and the string is not.
    written = scene_path.read_text(encoding="utf-8")
    return AgentResult(
        spec=spec,
        scene_path=scene_path,
        code=code,
        attempts=attempts,
        validated=validated,
        logs=logs,
        untranslated_labels=tuple(untranslated(written, language)),
    )


def run_agent_render(
    request_zh: str,
    output_dir: Path,
    media_dir: Path,
    *,
    quality: str = "l",
    font: str = DEFAULT_CJK_FONT,
    client: OpenAICompatibleClient | None = None,
    model: str | None = None,
    max_attempts: int = 3,
    allow_fallback: bool = True,
    aspect: str = LANDSCAPE,
    language: str = DEFAULT_LANGUAGE,
) -> AgentResult:
    client = client or OpenAICompatibleClient.from_env(model=model)
    spec = plan_with_llm(client, request_zh)
    code = write_code_with_llm(client, spec, font=font, aspect=aspect, language=language)
    logs = ""
    attempts = 0

    for attempt in range(1, max_attempts + 1):
        attempts = attempt
        safety = check_scene_code(code)
        if not safety.ok:
            logs = "\n".join(safety.errors)
            code = repair_code_with_llm(
                client, spec, code, logs, language, aspect=aspect)
            continue

        review = review_code_with_llm(
            client, spec, code, aspect=aspect, language=language)
        if not review.approved:
            logs = review_to_text(review)
            code = repair_code_with_llm(
                client, spec, code, logs, language, aspect=aspect)
            continue

        scene_path = write_code_scene(code, output_dir, aspect=aspect)
        render = render_scene_captured(
            scene_path, quality=quality, media_dir=media_dir, aspect=aspect)
        logs = render.logs
        if render.returncode == 0 and render.output_path is not None:
            return AgentResult(
                spec=spec,
                scene_path=scene_path,
                code=code,
                output_path=render.output_path,
                attempts=attempts,
                validated=True,
                logs=logs,
                untranslated_labels=tuple(
                    untranslated(scene_path.read_text(encoding="utf-8"), language)),
            )
        code = repair_code_with_llm(
            client, spec, code, logs[-8000:], language, aspect=aspect)

    if allow_fallback:
        return _fallback_render(request_zh, output_dir, media_dir, quality, font,
                                logs, attempts, aspect=aspect, language=language)
    scene_path = write_code_scene(code, output_dir, aspect=aspect)
    return AgentResult(
        spec=spec, scene_path=scene_path, code=code, attempts=attempts, logs=logs,
        untranslated_labels=tuple(
            untranslated(scene_path.read_text(encoding="utf-8"), language)),
    )


def _review_and_repair(
    client: OpenAICompatibleClient,
    spec: AnimationSpec,
    code: str,
    *,
    max_attempts: int,
    aspect: str = LANDSCAPE,
    language: str = DEFAULT_LANGUAGE,
) -> tuple[str, str, int, bool]:
    logs = ""
    for attempt in range(1, max_attempts + 1):
        safety = check_scene_code(code)
        if not safety.ok:
            logs = "\n".join(safety.errors)
            code = repair_code_with_llm(
                client, spec, code, logs, language, aspect=aspect)
            continue
        review = review_code_with_llm(
            client, spec, code, aspect=aspect, language=language)
        if review.approved:
            return code, logs, attempt, True
        logs = review_to_text(review)
        code = repair_code_with_llm(
            client, spec, code, logs, language, aspect=aspect)
    return code, logs, max_attempts, False


def _fallback_render(
    request_zh: str,
    output_dir: Path,
    media_dir: Path,
    quality: str,
    font: str,
    logs: str,
    attempts: int,
    aspect: str = LANDSCAPE,
    language: str = DEFAULT_LANGUAGE,
) -> AgentResult:
    plan = build_plan(request_zh)
    violations = validate(plan)
    # The same aspect and language the agent path was asked for. A fallback that
    # quietly reverts to landscape Chinese is the worst outcome available: the
    # render succeeds, so nothing reports a problem, and the caller receives a
    # video in the wrong shape and the wrong language for its channel.
    scene_path = write_scene(plan, output_dir, font=font, aspect=aspect, language=language)
    code = scene_code_for(plan, font=font, aspect=aspect, language=language)

    # A fallback that draws the wrong thing is the one outcome worse than
    # admitting the lane could not serve this request. The agent path has
    # already failed by the time we get here, so the render is the last chance
    # to spend ten minutes of a core — and a blocking precondition is a
    # prediction, made for free, that those minutes produce the wrong function
    # under a title claiming otherwise. Nothing downstream would catch it: the
    # scene builds, the geometry is sound, and the video looks finished.
    fatal = blocking(violations)
    if fatal:
        return AgentResult(
            spec=_fallback_spec(plan, request_zh),
            scene_path=scene_path,
            code=code,
            attempts=attempts,
            fallback_used=True,
            logs=(logs + "\n\nFallback not rendered:\n"
                  + "\n".join(str(v) for v in fatal)).strip(),
            untranslated_labels=tuple(untranslated(code, language)),
            violations=tuple(str(v) for v in violations),
        )

    render = render_scene_captured(
        scene_path, quality=quality, media_dir=media_dir, aspect=aspect)
    return AgentResult(
        spec=_fallback_spec(plan, request_zh),
        scene_path=scene_path,
        code=code,
        output_path=render.output_path,
        attempts=attempts,
        fallback_used=True,
        validated=True,
        logs=(logs + "\n\nFallback logs:\n" + render.logs).strip(),
        untranslated_labels=tuple(untranslated(code, language)),
        violations=tuple(str(v) for v in violations),
    )


def _fallback_spec(plan, request_zh: str) -> AnimationSpec:
    """Describe a deterministic-template render in the agent's own vocabulary.

    The caller should not have to know which path produced the result, so the
    fallback reports itself as a spec like any other — with ``constraints``
    naming what actually happened.
    """
    return AnimationSpec(
        language="zh",
        topic=plan.topic,
        concept=plan.concept or plan.topic,
        title_zh=plan.title_zh,
        objective_zh=plan.objective_zh,
        math_objects=plan.elements,
        animation_steps=plan.narration_zh,
        labels_zh=[],
        narration_zh=plan.narration_zh,
        constraints={"fallback": "deterministic_template"},
        source_request_zh=request_zh,
    )
