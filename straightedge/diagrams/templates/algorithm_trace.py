"""Multi-step algorithm storyboard composed from existing figure templates.

One state is not an algorithm.  The individual CS templates deliberately draw
one state well; this template gives those states an ordered, checked home rather
than growing a second array, tree, graph, stack, and queue renderer.

Example::

    {"type": "algorithm_trace", "params": {
        "title": "Bubble-sort pass",
        "steps": [
            {"label": "Compare", "visual": {"type": "array_state",
             "params": {"values": [4, 2, 3], "highlights": {"0-1": "comparison"}}},
             "transition": {"type": "swap", "indices": [0, 1]}},
            {"label": "Swap", "visual": {"type": "array_state",
             "params": {"values": [2, 4, 3], "highlights": {"1": "current"}}}}
        ]}}

The optional transition on step *i* describes the change that produces step
*i+1*.  Array swaps, stack push/pop, and queue enqueue/dequeue are verified;
an inconsistent trace is refused rather than illustrated as if it were true.
"""
from __future__ import annotations

import base64
import math
from html import escape
from typing import Any, Dict, List, Tuple

from ..registry import count_data_marks, register
from ..renderer import defs, fit_text, path, rect, style, svg_document, text


MAX_STEPS = 12
DEFAULT_PANEL_WIDTH = 340
DEFAULT_PANEL_HEIGHT = 250
GAP_X = 74
GAP_Y = 56
MARGIN = 28
HEADER_H = 58
STEP_HEAD_H = 42


Finding = Dict[str, str]


def _finding(code: str, message: str, path_: str) -> Finding:
    return {"code": code, "severity": "error", "message": message, "path": path_}


def _visual(step: Dict[str, Any]) -> Dict[str, Any] | None:
    value = step.get("visual")
    return value if isinstance(value, dict) else None


def _values(step: Dict[str, Any]) -> List[Any] | None:
    visual = _visual(step)
    if visual is None or not isinstance(visual.get("params"), dict):
        return None
    values = visual["params"].get("values")
    return list(values) if isinstance(values, list) else None


def _transition_error(current: Dict[str, Any], following: Dict[str, Any],
                      transition: Dict[str, Any]) -> str | None:
    """Return why a supported state transition is false, or ``None``."""
    kind = str(transition.get("type") or "").strip().lower()
    if kind not in {"swap", "push", "pop", "enqueue", "dequeue"}:
        return ("transition.type must be swap, push, pop, enqueue, or dequeue; "
                "omit transition for an unchecked explanatory step")

    current_visual, following_visual = _visual(current), _visual(following)
    current_type = current_visual.get("type") if current_visual else None
    following_type = following_visual.get("type") if following_visual else None
    required_type = {
        "swap": "array_state",
        "push": "stack",
        "pop": "stack",
        "enqueue": "queue",
        "dequeue": "queue",
    }[kind]
    if current_type != required_type or following_type != required_type:
        return f"{kind} requires adjacent {required_type} visuals"

    a, b = _values(current), _values(following)
    if a is None or b is None:
        return f"{kind} needs values arrays on both adjacent visuals"

    expected = list(a)
    if kind == "swap":
        indices = transition.get("indices")
        if (not isinstance(indices, list) or len(indices) != 2
                or not all(isinstance(i, int) for i in indices)):
            return "swap needs exactly two integer indices"
        left, right = indices
        if not (0 <= left < len(expected) and 0 <= right < len(expected)):
            return "swap index is outside the values array"
        expected[left], expected[right] = expected[right], expected[left]
    elif kind in {"push", "enqueue"}:
        if "value" not in transition:
            return f"{kind} needs value"
        end = str(transition.get("end") or ("back" if kind == "enqueue" else "top"))
        if kind == "push" or end in {"back", "right"}:
            expected.append(transition["value"])
        elif end in {"front", "left"}:
            expected.insert(0, transition["value"])
        else:
            return "enqueue.end must be front or back"
    elif kind in {"pop", "dequeue"}:
        if not expected:
            return f"cannot {kind} an empty state"
        end = str(transition.get("end") or ("front" if kind == "dequeue" else "top"))
        index = -1 if kind == "pop" or end in {"back", "right"} else 0
        if kind == "dequeue" and end not in {"front", "left", "back", "right"}:
            return "dequeue.end must be front or back"
        removed = expected.pop(index)
        if "value" in transition and transition["value"] != removed:
            return f"{kind} says it removes {transition['value']!r}, not {removed!r}"

    if b != expected:
        return f"next values must be {expected!r}, got {b!r}"
    return None


def inspect_algorithm_trace(params: Dict[str, Any]) -> List[Finding]:
    """Check structure and the transition claims between adjacent states."""
    from ..registry import DIAGRAM_REGISTRY

    steps = params.get("steps")
    if not isinstance(steps, list) or not steps:
        return [_finding("MISSING_STEPS", "steps must be a non-empty array", "$.steps")]
    findings: List[Finding] = []
    layout = params.get("layout", "grid")
    if layout not in {"grid", "row", "column"}:
        findings.append(_finding(
            "INVALID_LAYOUT", "layout must be grid, row, or column", "$.layout"))
    columns = params.get("columns")
    if columns is not None and (not isinstance(columns, int) or isinstance(columns, bool)
                                or columns < 1):
        findings.append(_finding(
            "INVALID_COLUMNS", "columns must be a positive integer", "$.columns"))
    for name in ("panel_width", "panel_height"):
        value = params.get(name)
        if value is not None and (not isinstance(value, (int, float))
                                  or isinstance(value, bool) or value <= 0):
            findings.append(_finding(
                "INVALID_PANEL_SIZE", f"{name} must be a positive number", f"$.{name}"))
    if len(steps) > MAX_STEPS:
        findings.append(_finding(
            "TOO_MANY_STEPS", f"at most {MAX_STEPS} steps fit in one storyboard", "$.steps"))

    for index, step in enumerate(steps[:MAX_STEPS]):
        step_path = f"$.steps[{index}]"
        if not isinstance(step, dict):
            findings.append(_finding("INVALID_STEP", "step must be an object", step_path))
            continue
        visual = _visual(step)
        if visual is None:
            findings.append(_finding(
                "MISSING_VISUAL", "step needs visual: {type, params}", f"{step_path}.visual"))
            continue
        kind = visual.get("type")
        if kind == "algorithm_trace":
            findings.append(_finding(
                "RECURSIVE_TRACE", "an algorithm trace cannot contain itself",
                f"{step_path}.visual.type"))
        elif not isinstance(kind, str) or kind not in DIAGRAM_REGISTRY:
            findings.append(_finding(
                "UNKNOWN_VISUAL", f"unknown visual type {kind!r}", f"{step_path}.visual.type"))
        raw_params = visual.get("params", {})
        if not isinstance(raw_params, dict):
            findings.append(_finding(
                "INVALID_PARAMS", "visual.params must be an object", f"{step_path}.visual.params"))

        transition = step.get("transition")
        if transition is None:
            continue
        if index + 1 >= len(steps):
            findings.append(_finding(
                "TRAILING_TRANSITION", "the final step has no following state",
                f"{step_path}.transition"))
        elif not isinstance(transition, dict):
            findings.append(_finding(
                "INVALID_TRANSITION", "transition must be an object",
                f"{step_path}.transition"))
        elif isinstance(steps[index + 1], dict):
            error = _transition_error(step, steps[index + 1], transition)
            if error:
                findings.append(_finding(
                    "STATE_TRANSITION_MISMATCH", error, f"{step_path}.transition"))

    # Structural errors make a render meaningless, and trying an unknown child
    # would only repeat them. Once the envelopes are sound, verify that every
    # child produces actual data rather than axes or an empty frame.
    if not findings:
        from ..registry import render_diagram

        for index, step in enumerate(steps):
            visual = _visual(step) or {}
            svg = render_diagram({"type": visual.get("type"),
                                  "params": visual.get("params", {})})
            if count_data_marks(svg) == 0:
                findings.append(_finding(
                    "BLANK_STEP", "the child visual drew no data marks; check its params",
                    f"$.steps[{index}].visual.params"))
    return findings


def _transition_label(transition: Any) -> str:
    if not isinstance(transition, dict):
        return ""
    if transition.get("label"):
        return str(transition["label"])
    kind = str(transition.get("type") or "")
    if kind == "swap" and isinstance(transition.get("indices"), list):
        return f"swap {transition['indices'][0]} ↔ {transition['indices'][1]}"
    if kind in {"push", "enqueue"}:
        return f"{kind} {transition.get('value', '')}".strip()
    if kind in {"pop", "dequeue"}:
        return kind
    return ""


def _embedded_svg(svg: str, x: float, y: float, width: float, height: float,
                  label: str) -> str:
    """Isolate a child SVG's CSS and ids inside a data-URI image."""
    payload = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return (f'<image x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" height="{height:.1f}" '
            f'preserveAspectRatio="xMidYMid meet" aria-label="{escape(label, quote=True)}" '
            f'href="data:image/svg+xml;base64,{payload}" class="at-visual"/>')


@register("algorithm_trace")
class AlgorithmTraceTemplate:
    """Render ordered, optionally verified states of an algorithm."""

    def render(self, params: Dict[str, Any]) -> str:
        from ..registry import render_diagram

        params = params or {}
        if inspect_algorithm_trace(params):
            return svg_document("", width=200, height=80,
                                class_name="diagram algorithm-trace")

        steps = params.get("steps", [])[:MAX_STEPS]
        title = str(params.get("title") or "").strip()
        layout = str(params.get("layout", "grid"))
        panel_width = max(220, min(600, int(params.get("panel_width", DEFAULT_PANEL_WIDTH))))
        panel_height = max(160, min(480, int(params.get("panel_height", DEFAULT_PANEL_HEIGHT))))
        show_numbers = bool(params.get("show_step_numbers", True))

        requested_columns = params.get("columns")
        if isinstance(requested_columns, int) and requested_columns > 0:
            columns = min(len(steps), requested_columns)
        elif layout == "row":
            columns = len(steps)
        elif layout == "column":
            columns = 1
        else:
            columns = min(3, len(steps))
        rows = math.ceil(len(steps) / columns)

        top = MARGIN + (HEADER_H if title else 0)
        card_height = STEP_HEAD_H + panel_height + 14
        width = int(2 * MARGIN + columns * panel_width + (columns - 1) * GAP_X)
        height = int(top + rows * card_height + (rows - 1) * GAP_Y + MARGIN)

        rendered: List[str] = []
        for index, step in enumerate(steps):
            visual = _visual(step) or {}
            svg = render_diagram({"type": visual.get("type"),
                                  "params": visual.get("params", {})})
            if count_data_marks(svg) == 0:
                return svg_document("", width=200, height=80,
                                    class_name="diagram algorithm-trace")
            rendered.append(svg)

        parts: List[str] = [defs(self._arrow() + style(self._css()))]
        parts.append(rect(0, 0, width, height, fill="#fbfaf7", **{"class": "at-paper"}))
        if title:
            parts.append(text(MARGIN, MARGIN + 28,
                              fit_text(title, width - 2 * MARGIN, 23, bold=True),
                              **{"class": "at-title"}))

        positions: List[Tuple[float, float]] = []
        for index, (step, svg) in enumerate(zip(steps, rendered)):
            row, column = divmod(index, columns)
            x = MARGIN + column * (panel_width + GAP_X)
            y = top + row * (card_height + GAP_Y)
            positions.append((x, y))
            parts.append(rect(x, y, panel_width, card_height, rx=10,
                              **{"class": "at-card"}))
            if show_numbers:
                parts.append(rect(x + 12, y + 10, 25, 22, rx=11,
                                  **{"class": "at-number-disc"}))
                parts.append(text(x + 24.5, y + 26, str(index + 1), text_anchor="middle",
                                  **{"class": "at-number"}))
            label = str(step.get("label") or step.get("caption") or f"Step {index + 1}")
            label_x = x + (47 if show_numbers else 14)
            parts.append(text(label_x, y + 26,
                              fit_text(label, x + panel_width - 12 - label_x, 14, bold=True),
                              **{"class": "at-step-label"}))
            parts.append(_embedded_svg(
                svg, x + 10, y + STEP_HEAD_H, panel_width - 20, panel_height,
                f"Step {index + 1}: {label}"))

        # Connect reading-order neighbours. Row wraps route through the gutter
        # below the current row, so an arrow never crosses a panel's content.
        for index in range(len(steps) - 1):
            x, y = positions[index]
            nx, ny = positions[index + 1]
            same_row = abs(y - ny) < 0.1
            if same_row:
                x1, y1 = x + panel_width, y + card_height / 2
                x2, y2 = nx, ny + card_height / 2
                d = f"M {x1 + 6:.1f} {y1:.1f} H {x2 - 8:.1f}"
                lx, ly = (x1 + x2) / 2, y1 - 9
            else:
                x1, y1 = x + panel_width / 2, y + card_height
                x2, y2 = nx + panel_width / 2, ny
                gutter_y = y1 + GAP_Y / 2
                d = (f"M {x1:.1f} {y1 + 5:.1f} V {gutter_y:.1f} "
                     f"H {x2:.1f} V {y2 - 8:.1f}")
                lx, ly = (x1 + x2) / 2, gutter_y - 7
            parts.append(path(d, marker_end="url(#at-arrow)", **{"class": "at-arrow"}))
            transition_label = _transition_label(steps[index].get("transition"))
            if transition_label:
                label_budget = max(36.0, abs(x2 - x1) - 12) if same_row else panel_width
                parts.append(text(lx, ly, fit_text(transition_label, label_budget, 10, bold=True),
                                  text_anchor="middle",
                                  **{"class": "at-transition"}))

        return svg_document("".join(parts), width=width, height=height,
                            class_name="diagram algorithm-trace")

    @staticmethod
    def _arrow() -> str:
        return ('<marker id="at-arrow" markerWidth="9" markerHeight="7" refX="8" '
                'refY="3.5" orient="auto"><polygon points="0 0,9 3.5,0 7" '
                'fill="#7b8794"/></marker>')

    @staticmethod
    def _css() -> str:
        return """
.at-title{font-size:23px;font-weight:700;font-family:Inter,Helvetica,Arial,sans-serif;fill:#17202a}
.at-card{fill:#ffffff;stroke:#d9dde2;stroke-width:1.2}
.at-number-disc{fill:#315fbd}
.at-number{font-size:12px;font-weight:700;font-family:Inter,Helvetica,Arial,sans-serif;fill:#ffffff}
.at-step-label{font-size:14px;font-weight:650;font-family:Inter,Helvetica,Arial,sans-serif;fill:#17202a}
.at-arrow{fill:none;stroke:#7b8794;stroke-width:1.5}
.at-transition{font-size:10px;font-weight:600;font-family:Inter,Helvetica,Arial,sans-serif;fill:#68717a}
"""
