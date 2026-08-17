from __future__ import annotations

from straightedge.aspect import LANDSCAPE, frame_config_source, is_vertical
from straightedge.labels import AUTHORED_LANGUAGE, DEFAULT_LANGUAGE, normalize

from .schemas import AnimationSpec

#: What the model is told to call its on-screen labels, per label language.
#: The spec it is handed carries Chinese (``labels_zh``, ``narration_zh``) in
#: every case, so without an instruction the model writes Chinese into the
#: frame regardless of who the video is for.
_LABEL_INSTRUCTIONS = {
    "zh": "Write all on-screen labels in Chinese, matching the spec's labels_zh.",
    "en": (
        "Write all on-screen labels in English, translating the spec's Chinese "
        "labels_zh. The spec is written in Chinese because that is the teacher's "
        "language, not the viewer's. Keep each label short — English runs roughly "
        "three times longer than the Chinese it replaces, and these layouts were "
        "positioned for the Chinese. Narration stays as the spec gives it."
    ),
}


MANIM_RULES = """
You generate Manim Community Edition Python for this local project.
Hard requirements:
- Define exactly one class named GeneratedScene.
- Use `from manim import *`; it exposes NumPy as `np`. Explicit `math` and `numpy.linalg` imports are also allowed. Do not import other Manim/NumPy submodules, os, sys, subprocess, pathlib, requests, urllib, socket, or external assets.
- Chinese text must use `_t("中文", ...)`; math formulas should use MathTex.
- The runtime provides:
  CJK_FONT = "<font>"
  def _t(text, **kwargs): kwargs.setdefault("font", CJK_FONT); return Text(text, **kwargs)
- Keep scenes deterministic, self-contained, and short enough for classroom preview.
- Prefer stable primitives: Axes, NumberPlane, VGroup, MathTex, ValueTracker, always_redraw, TracedPath, Transform, ReplacementTransform, FadeIn, Create, Write.
- Avoid network, filesystem, shell commands, eval, exec, open, or user input.
- Avoid unsupported experimental APIs and avoid dark/blank screens.
""".strip()


PLANNER_SYSTEM = f"""
You are a senior math-animation planner for Chinese classroom Manim videos.
Return only valid JSON. No markdown.

Create a structured animation spec from the teacher's Chinese request.
Use concise Chinese labels and narration. Choose precise topic/concept names.

{MANIM_RULES}
""".strip()


PLANNER_USER_TEMPLATE = """
Teacher request:
{request}

Return JSON with exactly these top-level keys:
language, topic, concept, title_zh, objective_zh, math_objects, animation_steps,
labels_zh, narration_zh, constraints, source_request_zh.
""".strip()


WRITER_SYSTEM = f"""
You are a Manim Community Edition code writer.
Return only Python source code. No markdown fences. No explanation.

{MANIM_RULES}
""".strip()


def writer_preamble(font: str, aspect: str = LANDSCAPE) -> str:
    """The preamble the model is told to open its scene with.

    Built from :func:`~straightedge.aspect.frame_config_source` rather than typed
    out here, because this prompt and ``templates._preamble`` are two copies of
    the same thing and this one had already fallen behind: the ``_t`` it dictated
    lost the shrink-to-fit the templates gained, so LLM scenes kept drawing long
    labels off the edge after the template scenes had stopped.
    """
    return f"""from manim import *

{frame_config_source(aspect)}


CJK_FONT = "{font}"


def _t(text, **kwargs):
    kwargs.setdefault("font", CJK_FONT)
    mob = Text(text, **kwargs)
    limit = config.frame_width * 0.92
    if mob.width > limit > 0:
        mob.scale(limit / mob.width)
    return mob"""


def writer_user_prompt(
    spec: AnimationSpec,
    font: str,
    aspect: str = LANDSCAPE,
    language: str = DEFAULT_LANGUAGE,
) -> str:
    shape = (
        "The frame is 9 units wide by 16 tall — a vertical short. Stack content "
        "vertically and keep it inside x = [-4.5, 4.5]; a layout that assumes a "
        "wide frame will run off both sides."
        if is_vertical(aspect) else
        "The frame is 14.22 units wide by 8 tall — standard landscape."
    )
    labels = _LABEL_INSTRUCTIONS.get(normalize(language),
                                     _LABEL_INSTRUCTIONS[AUTHORED_LANGUAGE])
    return f"""
Write a complete Manim Python scene for this spec:
{spec.to_dict()}

Frame: {shape}
Labels: {labels}

Use this preamble exactly at the top:
{writer_preamble(font, aspect)}


Then define class GeneratedScene(Scene) or GeneratedScene(ThreeDScene).
""".strip()


REVIEWER_SYSTEM = f"""
You are a strict Manim code reviewer.
Return only valid JSON. No markdown.

Review whether code follows the spec and these rules:
{MANIM_RULES}
""".strip()


def reviewer_user_prompt(
    spec: AnimationSpec,
    code: str,
    aspect: str = LANDSCAPE,
    language: str = DEFAULT_LANGUAGE,
) -> str:
    shape = (
        "9:16 vertical; all content must fit x = [-4.5, 4.5]"
        if is_vertical(aspect) else
        "16:9 landscape"
    )
    labels = _LABEL_INSTRUCTIONS.get(normalize(language),
                                     _LABEL_INSTRUCTIONS[AUTHORED_LANGUAGE])
    return f"""
Spec:
{spec.to_dict()}

Requested frame: {shape}
Requested labels: {labels}

Code:
{code}

Return JSON:
{{"approved": true|false, "issues": [{{"severity": "high|medium|low", "message": "...", "suggestion": "..."}}]}}
""".strip()


REPAIR_SYSTEM = f"""
You repair Manim Community Edition code.
Return only the full corrected Python source code. No markdown fences. No explanation.

{MANIM_RULES}
""".strip()


def repair_user_prompt(
    spec: AnimationSpec,
    code: str,
    failure: str,
    aspect: str = LANDSCAPE,
    language: str = DEFAULT_LANGUAGE,
) -> str:
    shape = (
        "9:16 vertical; keep all content inside x = [-4.5, 4.5]"
        if is_vertical(aspect) else
        "16:9 landscape"
    )
    labels = _LABEL_INSTRUCTIONS.get(normalize(language),
                                     _LABEL_INSTRUCTIONS[AUTHORED_LANGUAGE])
    return f"""
Spec:
{spec.to_dict()}

Requested frame: {shape}
Requested labels: {labels}

Current code:
{code}

Failure/review feedback:
{failure}

Return a full corrected scene.py that still defines GeneratedScene and satisfies the spec.
""".strip()
