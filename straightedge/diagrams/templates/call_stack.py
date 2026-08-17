"""Call stack visualization template for CS/data structure diagrams."""

from __future__ import annotations

from typing import Any, Dict, List

from ..registry import register
from ..renderer import DEFAULT_STYLES, rect, style, svg_document, text


STATE_COLORS = {
    "default": "#f8f9fa",
    "waiting": "#f8f9fa",
    "executing": "#fff3cd",
    "current": "#fff3cd",
    "visited": "#d1ecf1",
    "target": "#d4edda",
    "found": "#d4edda",
    "invalid": "#f8d7da",
    "rejected": "#f8d7da",
}


def _normalize_highlights(highlights: Any, count: int) -> Dict[int, str]:
    if not isinstance(highlights, dict):
        return {}
    result: Dict[int, str] = {}
    for key, state in highlights.items():
        if not isinstance(state, str):
            continue
        if isinstance(key, int):
            idx = key
        else:
            key_str = str(key)
            if not key_str.strip().isdigit():
                continue
            idx = int(key_str)
        if 0 <= idx < count:
            result[idx] = state
    return result


def _format_args(args: Any) -> str:
    if isinstance(args, dict):
        if not args:
            return ""
        parts = [f"{key}={value}" for key, value in args.items()]
        return ", ".join(parts)
    if args is None:
        return ""
    return str(args)


@register("call_stack")
class CallStackTemplate:
    """Render a call stack visualization for recursion frames."""

    def render(self, params: Dict[str, Any]) -> str:
        frames = params.get("frames", [])
        if not isinstance(frames, list):
            frames = []

        highlights = _normalize_highlights(params.get("highlights", {}), len(frames))
        show_return_values = bool(params.get("show_return_values", False))
        caption = params.get("caption")
        title = params.get("title", "Call Stack")

        frame_width = int(params.get("frame_width", 320))
        frame_height = int(params.get("frame_height", 38))
        padding_x = 20
        padding_top = 20

        title_space = 24 if title else 0
        bottom_margin = 20 + (20 if caption else 0)
        stack_height = max(1, len(frames)) * frame_height
        svg_width = padding_x * 2 + frame_width
        svg_height = padding_top + title_space + stack_height + bottom_margin

        elements: List[str] = []
        elements.append(style(DEFAULT_STYLES + self._extra_styles()))

        current_y = padding_top
        if title:
            elements.append(
                text(
                    svg_width / 2,
                    current_y + 14,
                    str(title),
                    **{"class": "call-stack-title", "text_anchor": "middle"},
                )
            )
            current_y += title_space

        # Render frames with most recent call at the top.
        for display_idx, frame in enumerate(reversed(frames)):
            if not isinstance(frame, dict):
                continue
            idx = len(frames) - 1 - display_idx
            state = highlights.get(idx) or frame.get("state", "default")
            state_key = state if state in STATE_COLORS else "default"

            x = padding_x
            y = current_y + display_idx * frame_height
            elements.append(
                rect(
                    x,
                    y,
                    frame_width,
                    frame_height,
                    **{"class": f"call-stack-frame call-stack-frame-{state_key}"},
                )
            )

            function = frame.get("function", "fn")
            args_str = _format_args(frame.get("args"))
            if args_str:
                label = f"{function}({args_str})"
            else:
                label = f"{function}()"

            if show_return_values and "return" in frame:
                label = f"{label} → returns {frame.get('return')}"

            elements.append(
                text(
                    x + 12,
                    y + frame_height / 2 + 5,
                    label,
                    **{"class": "call-stack-label", "text_anchor": "start"},
                )
            )

            frame_state = frame.get("state")
            if isinstance(frame_state, str) and frame_state:
                elements.append(
                    text(
                        x + frame_width - 10,
                        y + frame_height / 2 + 5,
                        frame_state,
                        **{
                            "class": "call-stack-state",
                            "text_anchor": "end",
                        },
                    )
                )

        if caption:
            elements.append(
                text(
                    svg_width / 2,
                    svg_height - 8,
                    str(caption),
                    **{"class": "call-stack-caption", "text_anchor": "middle"},
                )
            )

        return svg_document("\n".join(elements), svg_width, svg_height)

    @staticmethod
    def _extra_styles() -> str:
        return """
.call-stack-frame { stroke: #343a40; stroke-width: 1.2; fill: #f8f9fa; }
.call-stack-frame-waiting { fill: #f8f9fa; }
.call-stack-frame-executing { fill: #fff3cd; }
.call-stack-frame-current { fill: #fff3cd; }
.call-stack-frame-visited { fill: #d1ecf1; }
.call-stack-frame-target { fill: #d4edda; }
.call-stack-frame-found { fill: #d4edda; }
.call-stack-frame-invalid { fill: #f8d7da; }
.call-stack-frame-rejected { fill: #f8d7da; }
.call-stack-title { font-size: 14px; font-family: sans-serif; font-weight: 600; fill: #212529; }
.call-stack-label { font-size: 13px; font-family: sans-serif; fill: #212529; }
.call-stack-state { font-size: 12px; font-family: sans-serif; fill: #6c757d; }
.call-stack-caption { font-size: 12px; font-family: sans-serif; fill: #333; }
"""
