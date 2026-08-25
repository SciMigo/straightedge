"""Dependency-free animation of any registered SVG figure sequence."""

from __future__ import annotations

import base64
import math
from html import escape
from typing import Any, Dict, List, Tuple

from ...qc import Finding
from ..legibility import check_figure, figure_frame
from ..registry import DIAGRAM_REGISTRY, count_data_marks, hint_params, refusal_findings, register
from ..renderer import style, svg_document, text


MAX_FRAMES = 24


def _frames(params: Dict[str, Any]) -> List[Any]:
    frames = params.get("frames", [])
    return frames if isinstance(frames, list) else []


def _visual(frame: Any) -> Dict[str, Any] | None:
    if not isinstance(frame, dict):
        return None
    visual = frame.get("visual")
    return visual if isinstance(visual, dict) else None


def _render_frames(params: Dict[str, Any]) -> Tuple[List[Finding], List[Tuple[str, str]]]:
    findings: List[Finding] = []
    rendered: List[Tuple[str, str]] = []
    frames = _frames(params)
    if not frames:
        return [Finding("animation_frames", "error", "frames must be a non-empty array")], []
    if len(frames) > MAX_FRAMES:
        findings.append(Finding(
            "animation_frames", "error",
            f"at most {MAX_FRAMES} frames fit in one SVG animation",
        ))
    for index, frame in enumerate(frames):
        visual = _visual(frame)
        if visual is None:
            findings.append(Finding(
                "animation_frame", "error", f"frame {index} needs visual: {{type, params}}"
            ))
            continue
        kind = visual.get("type")
        if not isinstance(kind, str) or kind not in DIAGRAM_REGISTRY:
            findings.append(Finding(
                "animation_frame", "error", f"frame {index} has unknown visual {kind!r}"
            ))
            continue
        if kind == "animated_trace":
            findings.append(Finding(
                "animation_frame", "error", "an animated trace cannot contain itself"
            ))
            continue
        child_params = hint_params(visual)
        refused = refusal_findings(kind, child_params)
        if refused:
            findings.append(Finding(
                "animation_child", "error",
                f"frame {index} was refused: {refused[0].check}: {refused[0].message}",
            ))
            continue
        try:
            child = DIAGRAM_REGISTRY[kind].render(child_params)
        except Exception as exc:
            findings.append(Finding(
                "animation_child", "error", f"frame {index} failed to render: {exc}"
            ))
            continue
        if count_data_marks(child) == 0:
            findings.append(Finding(
                "animation_child", "error", f"frame {index} drew no data marks"
            ))
            continue
        errors = [finding for finding in check_figure(child) if finding.severity == "error"]
        if errors:
            findings.append(Finding(
                "animation_child_legibility", "error",
                f"frame {index} is illegible: {errors[0].check}: {errors[0].message}",
            ))
            continue
        label = str(frame.get("label", "")) if isinstance(frame, dict) else ""
        rendered.append((child, label))
    return findings, rendered


def _animation_tag(index: int, count: int, duration: float, loop: bool) -> str:
    """One opacity timeline with a short cross-fade at each frame boundary."""
    start, end = index / count, (index + 1) / count
    fade = min(0.012, 0.15 / count)
    if index == 0:
        values = "1;1;0;0"
        times = f"0;{max(end - fade, 0):.6f};{end:.6f};1"
    elif index == count - 1 and not loop:
        values = "0;0;1;1"
        times = f"0;{start:.6f};{min(start + fade, 1):.6f};1"
    else:
        values = "0;0;1;1;0;0"
        times = (
            f"0;{start:.6f};{min(start + fade, end):.6f};"
            f"{max(end - fade, start):.6f};{end:.6f};1"
        )
    repeat = "indefinite" if loop else "1"
    return (
        f'<animate attributeName="opacity" values="{values}" keyTimes="{times}" '
        f'dur="{duration:.3f}s" repeatCount="{repeat}" fill="freeze"/>'
    )


@register("animated_trace")
class AnimatedTraceTemplate:
    """Cross-fade registered SVG figures without Manim, ffmpeg, or JavaScript."""

    motion = "animated"
    checks = ["registered child figures", "child refusal checks", "child legibility"]

    def refusal_findings(self, params: Dict[str, Any]) -> List[Finding]:
        duration = params.get("duration_s", 1.5)
        if (not isinstance(duration, (int, float)) or isinstance(duration, bool)
                or not math.isfinite(duration) or duration <= 0):
            return [Finding(
                "animation_duration", "error", "duration_s must be a positive number"
            )]
        findings, _ = _render_frames(params)
        return findings

    def render(self, params: Dict[str, Any]) -> str:
        duration_per_frame = float(params.get("duration_s", 1.5))
        loop = bool(params.get("loop", True))
        title_value = params.get("title")
        background = str(params.get("background", "#ffffff"))
        findings, rendered = _render_frames(params)
        if findings or not rendered:
            return ""

        frames = [figure_frame(svg) for svg, _ in rendered]
        width = max(frame[2] for frame in frames) + 32
        height = max(frame[3] for frame in frames) + 68
        total = duration_per_frame * len(rendered)
        parts = [style("""
.animated-trace-bg{fill:var(--animated-bg,#fff)}
.animated-trace-label{font:600 14px Inter,Helvetica,Arial,sans-serif;fill:#27313b}
@media (prefers-reduced-motion:reduce){
  .animated-trace-frame{opacity:0!important}
  .animated-trace-first{opacity:1!important}
}
""")]
        parts.append(
            f'<rect class="animated-trace-bg" x="0" y="0" width="{width:.1f}" '
            f'height="{height:.1f}" style="--animated-bg:{escape(background)}"/>'
        )
        if title_value is not None:
            parts.append(text(
                width / 2, 20, str(title_value),
                **{"class": "animated-trace-label", "text_anchor": "middle"},
            ))
        top = 28 if title_value is not None else 8
        content_h = height - top - 34
        for index, ((child, label), frame) in enumerate(zip(rendered, frames)):
            encoded = base64.b64encode(child.encode("utf-8")).decode("ascii")
            initial = "1" if index == 0 else "0"
            animation = _animation_tag(index, len(rendered), total, loop)
            label_svg = ""
            if label:
                label_svg = text(
                    width / 2, height - 12, label,
                    **{"class": "animated-trace-label", "text_anchor": "middle"},
                )
            frame_class = "animated-trace-frame animated-trace-first" if index == 0 else "animated-trace-frame"
            parts.append(
                f'<g class="{frame_class}" opacity="{initial}">'
                f'<image href="data:image/svg+xml;base64,{encoded}" x="16" y="{top}" '
                f'width="{width - 32:.1f}" height="{content_h:.1f}" '
                f'preserveAspectRatio="xMidYMid meet"/>{label_svg}{animation}</g>'
            )
        return svg_document(
            "\n".join(parts), round(width), round(height),
            class_name="diagram animated-trace",
        )
