"""Environment diagram visualization template."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from ..registry import register
from ..renderer import DEFAULT_STYLES, defs, line, rect, style, svg_document, text


STATE_COLORS = {
    "default": "#f8f9fa",
    "current": "#fff3cd",
    "visited": "#d1ecf1",
    "target": "#d4edda",
    "found": "#d4edda",
    "invalid": "#f8d7da",
    "rejected": "#f8d7da",
}


def _normalize_state(state: Any) -> str:
    if isinstance(state, str) and state in STATE_COLORS:
        return state
    return "default"


def _arrow_marker() -> str:
    return (
        '<marker id="env-arrow" markerWidth="10" markerHeight="7" '
        'refX="9" refY="3.5" orient="auto">'
        '<polygon points="0 0, 10 3.5, 0 7" fill="#495057"/>'
        "</marker>"
    )


@register("environment_diagram")
class EnvironmentDiagramTemplate:
    """Render an environment diagram for closures and scope."""

    def render(self, params: Dict[str, Any]) -> str:
        frames = params.get("frames", [])
        functions = params.get("functions", [])
        highlights = params.get("highlights", {})
        caption = params.get("caption")

        if not isinstance(frames, list):
            frames = []
        if not isinstance(functions, list):
            functions = []

        frame_highlights = highlights.get("frames", {}) if isinstance(highlights, dict) else {}
        binding_highlights = highlights.get("bindings", {}) if isinstance(highlights, dict) else {}
        function_highlights = highlights.get("functions", {}) if isinstance(highlights, dict) else {}

        frame_width = int(params.get("frame_width", 260))
        frame_x = int(params.get("frame_x", 40))
        frame_y = int(params.get("frame_y", 30))
        frame_gap = int(params.get("frame_gap", 28))
        header_height = int(params.get("header_height", 24))
        row_height = int(params.get("row_height", 20))
        frame_padding = int(params.get("frame_padding", 8))

        func_width = int(params.get("function_width", 200))
        func_x = frame_x + frame_width + int(params.get("function_gap_horizontal", 120))
        func_line_height = int(params.get("function_line_height", 16))
        func_padding = int(params.get("function_padding", 8))
        func_gap = int(params.get("function_gap_vertical", 16))

        elements: List[str] = []
        elements.append(style(DEFAULT_STYLES + self._extra_styles()))
        elements.append(defs(_arrow_marker()))

        frame_positions: Dict[str, Tuple[int, int, int, int]] = {}
        current_y = frame_y
        for frame in frames:
            if not isinstance(frame, dict):
                continue
            bindings = frame.get("bindings", [])
            if not isinstance(bindings, list):
                bindings = []
            frame_height = header_height + frame_padding * 2 + max(1, len(bindings)) * row_height
            frame_id = str(frame.get("id", ""))
            frame_positions[frame_id] = (frame_x, current_y, frame_width, frame_height)
            current_y += frame_height + frame_gap

        functions_by_parent: Dict[str, List[Dict[str, Any]]] = {}
        for func in functions:
            if not isinstance(func, dict):
                continue
            parent = str(func.get("parent_frame", ""))
            functions_by_parent.setdefault(parent, []).append(func)

        func_positions: Dict[str, Tuple[int, int, int, int]] = {}
        for parent_id, func_list in functions_by_parent.items():
            if parent_id in frame_positions:
                base_y = frame_positions[parent_id][1] + 8
            else:
                base_y = frame_y
            offset = 0
            for func in func_list:
                func_id = str(func.get("id", ""))
                lines = 2
                func_height = func_padding * 2 + func_line_height * lines
                func_positions[func_id] = (
                    func_x,
                    int(base_y + offset),
                    func_width,
                    func_height,
                )
                offset += func_height + func_gap

        svg_width = max(
            func_x + func_width + 40,
            frame_x + frame_width + 40,
        )
        svg_height = max(
            current_y + (40 if caption else 20),
            frame_y + 60,
        )

        for frame in frames:
            if not isinstance(frame, dict):
                continue
            frame_id = str(frame.get("id", ""))
            if frame_id not in frame_positions:
                continue
            x, y, width, height = frame_positions[frame_id]
            state = _normalize_state(
                frame_highlights.get(frame_id) if isinstance(frame_highlights, dict) else None
            )
            elements.append(
                rect(
                    x,
                    y,
                    width,
                    height,
                    **{
                        "class": f"env-frame env-frame-{state}",
                        "rx": "6",
                        "ry": "6",
                    },
                )
            )
            elements.append(
                line(x, y + header_height, x + width, y + header_height, **{"class": "env-divider"})
            )
            label = frame.get("label", frame_id or "Frame")
            elements.append(
                text(
                    x + frame_padding,
                    y + header_height - 8,
                    str(label),
                    **{"class": "env-frame-title", "text_anchor": "start"},
                )
            )

            bindings = frame.get("bindings", [])
            if not isinstance(bindings, list):
                bindings = []
            if not bindings:
                bindings = [{"name": "(empty)", "value": ""}]
            for idx, binding in enumerate(bindings):
                if not isinstance(binding, dict):
                    continue
                row_y = y + header_height + frame_padding + idx * row_height
                binding_key = f"{frame_id}.{binding.get('name', '')}"
                binding_state = _normalize_state(
                    binding_highlights.get(binding_key) if isinstance(binding_highlights, dict) else None
                )
                elements.append(
                    rect(
                        x + 1,
                        row_y - row_height + 4,
                        width - 2,
                        row_height,
                        **{"class": f"env-binding env-binding-{binding_state}"},
                    )
                )
                name = binding.get("name", "")
                value = binding.get("value", "")
                elements.append(
                    text(
                        x + frame_padding,
                        row_y + 4,
                        str(name),
                        **{"class": "env-binding-name", "text_anchor": "start"},
                    )
                )
                elements.append(
                    text(
                        x + width - frame_padding,
                        row_y + 4,
                        str(value),
                        **{"class": "env-binding-value", "text_anchor": "end"},
                    )
                )

                if isinstance(value, str) and value.startswith("func:"):
                    func_id = value.split("func:", 1)[1]
                    if func_id in func_positions:
                        fx, fy, fwidth, fheight = func_positions[func_id]
                        elements.append(
                            line(
                                x + width,
                                row_y,
                                fx,
                                fy + fheight / 2,
                                **{
                                    "class": "env-arrow",
                                    "marker_end": "url(#env-arrow)",
                                },
                            )
                        )

            parent_id = frame.get("parent")
            if parent_id and str(parent_id) in frame_positions:
                parent_x, parent_y, parent_w, parent_h = frame_positions[str(parent_id)]
                elements.append(
                    line(
                        x + width / 2,
                        y,
                        parent_x + parent_w / 2,
                        parent_y + parent_h,
                        **{
                            "class": "env-parent-arrow",
                            "marker_end": "url(#env-arrow)",
                        },
                    )
                )

        for func in functions:
            if not isinstance(func, dict):
                continue
            func_id = str(func.get("id", ""))
            if func_id not in func_positions:
                continue
            fx, fy, fwidth, fheight = func_positions[func_id]
            state = _normalize_state(
                function_highlights.get(func_id) if isinstance(function_highlights, dict) else None
            )
            elements.append(
                rect(
                    fx,
                    fy,
                    fwidth,
                    fheight,
                    **{
                        "class": f"env-function env-function-{state}",
                        "rx": "12",
                        "ry": "12",
                    },
                )
            )
            params_list = func.get("params", [])
            if not isinstance(params_list, list):
                params_list = [str(params_list)]
            params_str = ", ".join(str(p) for p in params_list)
            body = func.get("body", "")
            elements.append(
                text(
                    fx + func_padding,
                    fy + func_padding + func_line_height - 2,
                    f"params: ({params_str})",
                    **{"class": "env-function-text", "text_anchor": "start"},
                )
            )
            elements.append(
                text(
                    fx + func_padding,
                    fy + func_padding + func_line_height * 2 - 2,
                    str(body),
                    **{"class": "env-function-body", "text_anchor": "start"},
                )
            )

            parent_frame = func.get("parent_frame")
            if parent_frame and str(parent_frame) in frame_positions:
                px, py, pw, ph = frame_positions[str(parent_frame)]
                elements.append(
                    line(
                        fx + fwidth,
                        fy + fheight / 2,
                        px + pw,
                        py + ph / 2,
                        **{
                            "class": "env-closure-arrow",
                            "marker_end": "url(#env-arrow)",
                        },
                    )
                )

        if caption:
            elements.append(
                text(
                    svg_width / 2,
                    svg_height - 10,
                    str(caption),
                    **{"class": "env-caption", "text_anchor": "middle"},
                )
            )

        return svg_document("\n".join(elements), svg_width, svg_height)

    @staticmethod
    def _extra_styles() -> str:
        return """
.env-frame { stroke: #343a40; stroke-width: 1.2; fill: #f8f9fa; }
.env-frame-default { fill: #f8f9fa; }
.env-frame-current { fill: #fff3cd; }
.env-frame-visited { fill: #d1ecf1; }
.env-frame-target { fill: #d4edda; }
.env-frame-found { fill: #d4edda; }
.env-frame-invalid { fill: #f8d7da; }
.env-frame-rejected { fill: #f8d7da; }
.env-divider { stroke: #adb5bd; stroke-width: 1; }
.env-frame-title { font-size: 12px; font-family: sans-serif; font-weight: 600; fill: #212529; }
.env-binding { fill: transparent; }
.env-binding-default { fill: transparent; }
.env-binding-current { fill: #fff3cd; }
.env-binding-visited { fill: #d1ecf1; }
.env-binding-target { fill: #d4edda; }
.env-binding-found { fill: #d4edda; }
.env-binding-invalid { fill: #f8d7da; }
.env-binding-rejected { fill: #f8d7da; }
.env-binding-name { font-size: 12px; font-family: sans-serif; fill: #212529; }
.env-binding-value { font-size: 12px; font-family: sans-serif; fill: #495057; }
.env-function { stroke: #343a40; stroke-width: 1.2; fill: #f8f9fa; }
.env-function-default { fill: #f8f9fa; }
.env-function-current { fill: #fff3cd; }
.env-function-visited { fill: #d1ecf1; }
.env-function-target { fill: #d4edda; }
.env-function-found { fill: #d4edda; }
.env-function-invalid { fill: #f8d7da; }
.env-function-rejected { fill: #f8d7da; }
.env-function-text { font-size: 11px; font-family: monospace; fill: #212529; }
.env-function-body { font-size: 11px; font-family: monospace; fill: #495057; }
.env-arrow { stroke: #495057; stroke-width: 1.2; }
.env-parent-arrow { stroke: #6c757d; stroke-width: 1.2; stroke-dasharray: 4,2; }
.env-closure-arrow { stroke: #6c757d; stroke-width: 1.2; stroke-dasharray: 4,2; }
.env-caption { font-size: 12px; font-family: sans-serif; fill: #333; }
"""
