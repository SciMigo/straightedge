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
*i+1*.  Array swaps, stack push/pop, and queue enqueue/dequeue are verified
against the next state's values and against the ``operation`` the panel itself
draws; an inconsistent trace is refused rather than illustrated as if it were
true.  The refusal travels: :func:`inspect_algorithm_trace` returns it as
structured findings, and the template exposes the same findings through
``refusal_findings`` so the MCP ``draw`` tool and the CLI report *why* rather
than "check your parameter shapes".
"""
from __future__ import annotations

import base64
import math
from html import escape
from typing import Any, Dict, List, Tuple

from ...qc import Finding as QcFinding
from ..legibility import figure_frame
from ..registry import (DIAGRAM_REGISTRY, count_data_marks, hint_params, refusal_findings,
                        register)
from ..renderer import (defs, fit_text, group, path, rect, style, svg_document, text,
                        title as svg_title)


MAX_STEPS = 12
MIN_PANEL_WIDTH, MAX_PANEL_WIDTH = 220, 600
MIN_PANEL_HEIGHT, MAX_PANEL_HEIGHT = 160, 480
#: Horizontal inset of the child figure inside its card, each side.
PANEL_INSET = 10
#: Below this, a child's 12px labels are drawn under 8px tall. The documented
#: answer to a trace that does not fit is to divide it, not to shrink it until
#: it cannot be read, so the render is refused with the numbers attached.
MIN_CHILD_SCALE = 0.6
GAP_X = 74
GAP_Y = 56
MARGIN = 28
HEADER_H = 58
STEP_HEAD_H = 42

_TRANSITION_TYPES = {
    "swap", "push", "pop", "enqueue", "dequeue",
    "visit", "discover", "settle", "decrease_key", "pop_min",
}
_REQUIRED_VISUAL = {
    "swap": "array_state",
    "push": "stack",
    "pop": "stack",
    "enqueue": "queue",
    "dequeue": "queue",
    "decrease_key": "priority_queue",
    "pop_min": "priority_queue",
}
_QUEUE_ENDS = {"front", "back"}


Finding = Dict[str, str]


def _finding(code: str, message: str, path_: str) -> Finding:
    return {"code": code, "severity": "error", "message": message, "path": path_}


def _visuals(step: Dict[str, Any]) -> List[Dict[str, Any]] | None:
    value = step.get("visual")
    if isinstance(value, dict):
        return [value]
    if (isinstance(value, list) and 1 <= len(value) <= 2
            and all(isinstance(item, dict) for item in value)):
        return value
    return None


def _visual(step: Dict[str, Any], kind: str | None = None) -> Dict[str, Any] | None:
    visuals = _visuals(step)
    if not visuals:
        return None
    if kind is None:
        return visuals[0] if len(visuals) == 1 else None
    return next((visual for visual in visuals if visual.get("type") == kind), None)


def _child_params(visual: Dict[str, Any]) -> Dict[str, Any] | None:
    """The child's parameters in either envelope `render_diagram` accepts.

    ``None`` when a ``params`` slot is present but not an object — that is a
    shape mistake to report, not an empty figure to draw.
    """
    raw = visual.get("params")
    if raw is None:
        return hint_params(visual)
    return raw if isinstance(raw, dict) else None


def _values(step: Dict[str, Any], kind: str | None = None) -> List[Any] | None:
    visual = _visual(step, kind)
    params = _child_params(visual) if visual is not None else None
    if params is None:
        return None
    values = params.get("values")
    return list(values) if isinstance(values, list) else None


def _priority_items(step: Dict[str, Any]) -> List[Dict[str, Any]] | None:
    visual = _visual(step, "priority_queue")
    params = _child_params(visual) if visual is not None else None
    items = params.get("items") if params else None
    if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
        return None
    ids = [str(item.get("id")) for item in items if item.get("id") is not None]
    if len(ids) != len(items) or len(ids) != len(set(ids)):
        return None
    if any(not isinstance(item.get("priority"), (int, float))
           or isinstance(item.get("priority"), bool)
           or not math.isfinite(item["priority"]) for item in items):
        return None
    return [dict(item) for item in items]


def _is_index(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _queue_end(transition: Dict[str, Any], default: str) -> str | None:
    """The end a queue transition names, or ``None`` when it is not one."""
    if "end" not in transition:
        return default
    end = transition["end"]
    if not isinstance(end, str) or end.strip().lower() not in _QUEUE_ENDS:
        return None
    return end.strip().lower()


def _operation_disagreement(current: Dict[str, Any], kind: str,
                            transition: Dict[str, Any], end: str | None) -> str | None:
    """Why the panel's drawn ``operation`` is not the transition being verified.

    `stack` and `queue` draw an ``operation`` param — the value arriving, the
    end it arrives at. The checker verifies the values either side of the
    transition; without this it would approve a storyboard whose panel draws
    the opposite of what the arrow between the panels says.
    """
    visual = _visual(current, _REQUIRED_VISUAL[kind])
    params = _child_params(visual) if visual is not None else None
    operation = (params or {}).get("operation")
    if not isinstance(operation, dict) or not operation:
        return None
    drawn = str(operation.get("type") or "").strip().lower()
    if drawn != kind:
        return f"the panel draws operation {drawn or 'of no type'!s}, but the transition is {kind}"
    if "value" in operation and "value" in transition and operation["value"] != transition["value"]:
        return (f"the panel draws {kind} {operation['value']!r}, "
                f"but the transition says {transition['value']!r}")
    if kind in {"enqueue", "dequeue"} and "end" in operation and end is not None:
        # queue.py places the operation at the front only when told "front";
        # anything else is drawn at the back. Mirror that rather than the
        # transition's stricter vocabulary — it is the drawing being checked.
        drawn_end = "front" if str(operation["end"]).strip().lower() == "front" else "back"
        if drawn_end != end:
            return f"the panel draws {kind} at the {drawn_end}, but the transition says {end}"
    return None


def _transition_error(current: Dict[str, Any], following: Dict[str, Any],
                      transition: Dict[str, Any]) -> str | None:
    """Return why a supported state transition is false, or ``None``."""
    kind = str(transition.get("type") or "").strip().lower()
    if kind not in _TRANSITION_TYPES:
        return ("transition.type must be swap, push, pop, enqueue, dequeue, visit, "
                "discover, settle, decrease_key, or pop_min; "
                "omit transition for an unchecked explanatory step")

    if kind in {"visit", "discover", "settle"}:
        return _graph_transition_error(current, following, kind, transition)

    if kind in {"decrease_key", "pop_min"}:
        before_items, after_items = _priority_items(current), _priority_items(following)
        if before_items is None or after_items is None:
            return f"{kind} requires items arrays on adjacent priority_queue visuals"
        before_by_id = {str(item.get("id")): item.get("priority") for item in before_items}
        after_by_id = {str(item.get("id")): item.get("priority") for item in after_items}
        if kind == "decrease_key":
            item_id = str(transition.get("id", transition.get("node", "")))
            priority = transition.get("priority")
            if not item_id or item_id not in before_by_id:
                return "decrease_key needs the id of an existing item"
            if (not isinstance(priority, (int, float)) or isinstance(priority, bool)
                    or not math.isfinite(priority)):
                return "decrease_key needs a numeric priority"
            if priority > before_by_id[item_id]:
                return "decrease_key cannot increase a priority"
            expected = dict(before_by_id)
            expected[item_id] = priority
            if after_by_id != expected:
                return f"next priority queue must be {expected!r}, got {after_by_id!r}"
            return None
        if not before_items:
            return "cannot pop_min from an empty priority queue"
        minimum = min(enumerate(before_items), key=lambda pair: (
            pair[1].get("priority"), pair[0]
        ))[1]
        minimum_id = str(minimum.get("id"))
        claimed = transition.get("id", transition.get("value", transition.get("node")))
        if claimed is not None and str(claimed) != minimum_id:
            return f"pop_min says it removes {claimed!r}, not {minimum_id!r}"
        expected = dict(before_by_id)
        expected.pop(minimum_id)
        if after_by_id != expected:
            return f"next priority queue must be {expected!r}, got {after_by_id!r}"
        coupled = dict(transition)
        coupled["value"] = minimum_id
        return _coupled_frontier_error(current, following, kind, coupled)

    required_type = _REQUIRED_VISUAL[kind]
    current_visual = _visual(current, required_type)
    following_visual = _visual(following, required_type)
    if current_visual is None or following_visual is None:
        return f"{kind} requires adjacent {required_type} visuals"

    a, b = _values(current, required_type), _values(following, required_type)
    if a is None or b is None:
        return f"{kind} needs values arrays on both adjacent visuals"

    expected = list(a)
    end: str | None = None
    if kind == "swap":
        indices = transition.get("indices")
        if (not isinstance(indices, list) or len(indices) != 2
                or not all(_is_index(i) for i in indices)):
            return "swap needs exactly two integer indices"
        left, right = indices
        if not (0 <= left < len(expected) and 0 <= right < len(expected)):
            return "swap index is outside the values array"
        expected[left], expected[right] = expected[right], expected[left]
    elif kind in {"push", "pop"}:
        if "end" in transition:
            return f"{kind} does not take end; a stack has only its top"
        if kind == "push":
            if "value" not in transition:
                return "push needs value"
            expected.append(transition["value"])
        else:
            if not expected:
                return "cannot pop an empty state"
            removed = expected.pop()
            if "value" in transition and transition["value"] != removed:
                return f"pop says it removes {transition['value']!r}, not {removed!r}"
    elif kind == "enqueue":
        if "value" not in transition:
            return "enqueue needs value"
        end = _queue_end(transition, "back")
        if end is None:
            return "enqueue.end must be front or back"
        if end == "back":
            expected.append(transition["value"])
        else:
            expected.insert(0, transition["value"])
    else:  # dequeue
        if not expected:
            return "cannot dequeue an empty state"
        end = _queue_end(transition, "front")
        if end is None:
            return "dequeue.end must be front or back"
        removed = expected.pop(-1 if end == "back" else 0)
        if "value" in transition and transition["value"] != removed:
            return f"dequeue says it removes {transition['value']!r}, not {removed!r}"

    if b != expected:
        return f"next values must be {expected!r}, got {b!r}"
    disagreement = _operation_disagreement(current, kind, transition, end)
    if disagreement:
        return disagreement
    return _coupled_frontier_error(current, following, kind, transition)


def _graph_states(step: Dict[str, Any]) -> Dict[str, str] | None:
    visual = _visual(step, "graph")
    if visual is None:
        return None
    params = _child_params(visual) if visual is not None else None
    highlights = params.get("highlights") if params else None
    nodes = highlights.get("nodes") if isinstance(highlights, dict) else None
    if not isinstance(nodes, dict):
        return {}
    return {str(node): str(state).strip().lower() for node, state in nodes.items()}


def _graph_nodes(step: Dict[str, Any]) -> set[str]:
    visual = _visual(step, "graph")
    params = _child_params(visual) if visual is not None else None
    raw = params.get("nodes") if params else None
    return {str(node.get("id")) for node in raw if isinstance(node, dict) and node.get("id") is not None} \
        if isinstance(raw, list) else set()


def _graph_has_edge(step: Dict[str, Any], source: str, target: str) -> bool:
    visual = _visual(step, "graph")
    params = _child_params(visual) if visual is not None else None
    if not params:
        return False
    directed = bool(params.get("directed", False))
    for edge in params.get("edges", []):
        if not isinstance(edge, dict):
            continue
        left, right = str(edge.get("from")), str(edge.get("to"))
        if (left, right) == (source, target) or (not directed and (left, right) == (target, source)):
            return True
    return False


def _next_neighbor(step: Dict[str, Any], source: str,
                   states: Dict[str, str]) -> str | None:
    """First undiscovered neighbor using the caller's stable ordering contract."""
    visual = _visual(step, "graph")
    params = _child_params(visual) if visual is not None else None
    if not params:
        return None
    directed = bool(params.get("directed", False))
    neighbors: List[str] = []
    for edge in params.get("edges", []):
        if not isinstance(edge, dict):
            continue
        left, right = str(edge.get("from")), str(edge.get("to"))
        neighbor = right if left == source else left if not directed and right == source else None
        if neighbor is not None and neighbor not in neighbors:
            neighbors.append(neighbor)
    order = params.get("neighbor_order")
    if isinstance(order, list):
        rank = {str(node): index for index, node in enumerate(order)}
        neighbors.sort(key=lambda node: rank.get(node, len(rank)))
    return next((node for node in neighbors
                 if states.get(node, "unvisited") in {"default", "unvisited"}), None)


def _persistent_graph_error(current: Dict[str, str], following: Dict[str, str],
                            changing: str) -> str | None:
    for node, state in current.items():
        after = following.get(node)
        if node == changing:
            continue
        if state == "settled" and after != "settled":
            return f"settled node {node!r} must stay settled"
        if state == "visited" and after not in {"visited", "settled"}:
            return f"visited node {node!r} must stay visited"
    return None


def _graph_transition_error(current: Dict[str, Any], following: Dict[str, Any],
                            kind: str, transition: Dict[str, Any]) -> str | None:
    before, after = _graph_states(current), _graph_states(following)
    if before is None or after is None:
        return f"{kind} requires adjacent graph visuals"
    if "node" not in transition:
        return f"{kind} needs node"
    node = str(transition["node"])
    if node not in _graph_nodes(current) or node not in _graph_nodes(following):
        return f"{kind} names unknown graph node {node!r}"
    persistent = _persistent_graph_error(before, after, node)
    if persistent:
        return persistent
    if kind == "discover":
        if "from" not in transition:
            return "discover needs from"
        source = str(transition["from"])
        if source not in _graph_nodes(current) or not _graph_has_edge(current, source, node):
            return f"discover needs an edge from {source!r} to {node!r}"
        expected = _next_neighbor(current, source, before)
        if expected is not None and node != expected:
            return (f"discover must follow neighbor order from {source!r}: "
                    f"expected {expected!r}, got {node!r}")
        if after.get(node) != "frontier":
            return f"discovered node {node!r} must be frontier in the next graph"
    elif kind == "visit":
        if after.get(node) != "visited":
            return f"visited node {node!r} must be visited in the next graph"
    else:
        if before.get(node) != "frontier" or after.get(node) != "settled":
            return f"settle must move node {node!r} from frontier to settled"
    return None


def _coupled_frontier_error(current: Dict[str, Any], following: Dict[str, Any],
                            kind: str, transition: Dict[str, Any]) -> str | None:
    before, after = _graph_states(current), _graph_states(following)
    if before is None and after is None:
        return None
    if before is None or after is None:
        return f"a coupled {kind} needs a graph in both adjacent composite visuals"
    value = transition.get("value")
    if value is None:
        return None
    node = str(value)
    if node not in _graph_nodes(current):
        return f"{kind} value {node!r} is not a graph node"
    persistent = _persistent_graph_error(before, after, node)
    if persistent:
        return persistent
    if kind in {"enqueue", "push"} and after.get(node) != "frontier":
        return f"{kind} node {node!r} must be frontier in the next graph"
    if kind in {"dequeue", "pop", "pop_min"}:
        if before.get(node) != "frontier":
            return f"{kind} node {node!r} must be frontier in the current graph"
        if after.get(node) == "frontier":
            return f"{kind} node {node!r} must leave the frontier in the next graph"
    return None


def _positive_number(value: Any) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and value > 0)


def _envelope_findings(params: Dict[str, Any]) -> Tuple[List[Finding], List[Any]]:
    """Structural findings, and the steps they were read from."""
    steps = params.get("steps")
    if not isinstance(steps, list) or not steps:
        return [_finding("MISSING_STEPS", "steps must be a non-empty array", "$.steps")], []
    findings: List[Finding] = []
    layout = params.get("layout")
    if layout is not None and (not isinstance(layout, str)
                               or layout not in {"grid", "row", "column"}):
        findings.append(_finding(
            "INVALID_LAYOUT", "layout must be grid, row, or column", "$.layout"))
    columns = params.get("columns")
    if columns is not None and (not _is_index(columns) or columns < 1):
        findings.append(_finding(
            "INVALID_COLUMNS", "columns must be a positive integer", "$.columns"))
    for name in ("panel_width", "panel_height"):
        value = params.get(name)
        if value is not None and not _positive_number(value):
            findings.append(_finding(
                "INVALID_PANEL_SIZE", f"{name} must be a positive number", f"$.{name}"))
    if len(steps) > MAX_STEPS:
        findings.append(_finding(
            "TOO_MANY_STEPS", f"at most {MAX_STEPS} steps fit in one storyboard", "$.steps"))

    for index, step in enumerate(steps):
        step_path = f"$.steps[{index}]"
        if not isinstance(step, dict):
            findings.append(_finding("INVALID_STEP", "step must be an object", step_path))
            continue
        visuals = _visuals(step)
        if visuals is None:
            findings.append(_finding(
                "MISSING_VISUAL",
                "step needs visual: {type, params}, or a list of one or two visuals",
                f"{step_path}.visual"))
            continue
        for visual_index, visual in enumerate(visuals):
            suffix = f"[{visual_index}]" if isinstance(step.get("visual"), list) else ""
            visual_path = f"{step_path}.visual{suffix}"
            kind = visual.get("type")
            if kind == "algorithm_trace":
                findings.append(_finding(
                    "RECURSIVE_TRACE", "an algorithm trace cannot contain itself",
                    f"{visual_path}.type"))
            elif not isinstance(kind, str) or kind not in DIAGRAM_REGISTRY:
                findings.append(_finding(
                    "UNKNOWN_VISUAL", f"unknown visual type {kind!r}", f"{visual_path}.type"))
            if _child_params(visual) is None:
                findings.append(_finding(
                    "INVALID_PARAMS", "visual.params must be an object",
                    f"{visual_path}.params"))

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
    return findings, steps


def _render_visual(index: int, visual_index: int,
                   visual: Dict[str, Any]) -> Tuple[Finding | None, str]:
    """One child figure, or the finding that stands in for it.

    The child template is called directly rather than through
    :func:`render_diagram`, which swallows an exception into an empty string —
    and an empty string here would be reported as "check its params" whether
    the child crashed, refused a false claim, or genuinely drew nothing.
    Those are three different repairs, so they are three findings.
    """
    kind = str(visual.get("type"))
    params = _child_params(visual) or {}
    suffix = f"[{visual_index}]" if visual_index >= 0 else ""
    path_ = f"$.steps[{index}].visual{suffix}.params"
    refused = refusal_findings(kind, params)
    if refused:
        reason = "; ".join(f"{f.check}: {f.message}" for f in refused)
        return _finding("CHILD_REFUSED",
                        f"the child visual refused to draw: {reason}", path_), ""
    try:
        svg = DIAGRAM_REGISTRY[kind].render(params)
    except Exception as exc:  # noqa: BLE001 - any child failure is this step's finding
        return _finding("CHILD_RENDER_ERROR",
                        f"the child visual failed to render: {exc}", path_), ""
    if count_data_marks(svg) == 0:
        return _finding("BLANK_STEP",
                        "the child visual drew no data marks; check its params", path_), ""
    return None, svg


def _compose_children(children: List[str]) -> str:
    if len(children) == 1:
        return children[0]
    frames = [figure_frame(svg) for svg in children]
    target_height = max(frame[3] for frame in frames)
    gap = 18.0
    widths = [frame[2] * target_height / frame[3] if frame[3] > 0 else frame[2]
              for frame in frames]
    total_width = sum(widths) + gap * (len(children) - 1)
    x = 0.0
    parts: List[str] = []
    for child_index, (svg, width) in enumerate(zip(children, widths)):
        parts.append(_embedded_svg(svg, x, 0, width, target_height,
                                   f"Composite visual {child_index + 1}"))
        x += width + gap
    return svg_document("".join(parts), round(total_width), round(target_height),
                        class_name="diagram algorithm-trace-composite")


def _render_child(index: int, step: Dict[str, Any]) -> Tuple[Finding | None, str]:
    visuals = _visuals(step) or []
    rendered: List[str] = []
    composite = isinstance(step.get("visual"), list)
    for visual_index, visual in enumerate(visuals):
        finding, svg = _render_visual(index, visual_index if composite else -1, visual)
        if finding:
            return finding, ""
        rendered.append(svg)
    return None, _compose_children(rendered)


def _clamp(value: float, low: int, high: int) -> int:
    return max(low, min(high, int(value)))


def _panel_size(params: Dict[str, Any], rendered: List[str]) -> Tuple[int, int]:
    """Card interior, from the request or from the largest child drawn.

    Sized to the children unless told otherwise, so a figure is drawn at its
    own scale wherever the bounds allow rather than shrunk into a fixed card.
    """
    frames = [figure_frame(svg) for svg in rendered]
    widest = max((frame[2] for frame in frames), default=0.0)
    tallest = max((frame[3] for frame in frames), default=0.0)
    width = params.get("panel_width")
    height = params.get("panel_height")
    panel_width = (max(1, int(width)) if width is not None else
                   _clamp(widest + 2 * PANEL_INSET, MIN_PANEL_WIDTH, MAX_PANEL_WIDTH))
    panel_height = (max(1, int(height)) if height is not None else
                    _clamp(tallest, MIN_PANEL_HEIGHT, MAX_PANEL_HEIGHT))
    return panel_width, panel_height


def _child_scale(svg: str, panel_width: int, panel_height: int) -> float:
    """The factor a child is drawn at inside its card (``meet`` fitting)."""
    _, _, width, height = figure_frame(svg)
    if width <= 0 or height <= 0:
        return 1.0
    return min((panel_width - 2 * PANEL_INSET) / width, panel_height / height)


def _inspect(params: Dict[str, Any]) -> Tuple[List[Finding], List[str]]:
    """Findings, and the child figures rendered while finding them.

    Structural errors make a render meaningless, and trying an unknown child
    would only repeat them. Once the envelopes are sound, every child is
    rendered exactly once — the renders come back so :meth:`render` does not
    draw them all a second time.
    """
    findings, steps = _envelope_findings(params)
    if findings:
        return findings, []
    rendered: List[str] = []
    for index, step in enumerate(steps):
        finding, svg = _render_child(index, step)
        if finding:
            findings.append(finding)
        rendered.append(svg)
    if findings:
        return findings, []
    panel_width, panel_height = _panel_size(params, rendered)
    for index, svg in enumerate(rendered):
        scale = _child_scale(svg, panel_width, panel_height)
        if scale < MIN_CHILD_SCALE:
            _, _, width, height = figure_frame(svg)
            findings.append(_finding(
                "UNREADABLE_STEP",
                f"the child figure is {width:.0f}×{height:.0f} and would be drawn at "
                f"{scale:.0%} in a {panel_width}×{panel_height} panel; raise "
                f"panel_width/panel_height or divide the trace",
                f"$.steps[{index}].visual"))
    return findings, rendered


def inspect_algorithm_trace(params: Dict[str, Any]) -> List[Finding]:
    """Check structure, the transition claims between adjacent states, and
    that every child draws something readable."""
    return _inspect(params or {})[0]


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
    if kind in {"visit", "settle", "pop_min"}:
        return f"{kind} {transition.get('node', transition.get('value', ''))}".strip()
    if kind == "discover":
        return f"discover {transition.get('node', '')}".strip()
    if kind == "decrease_key":
        item_id = transition.get("id", transition.get("node", ""))
        return f"decrease {item_id} → {transition.get('priority', '')}".strip()
    return ""


def _named(full: str, drawn: str, element: str) -> str:
    """``element`` with the whole label attached where only part was drawn."""
    return element if drawn == full else group(svg_title(full) + element)


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

    def refusal_findings(self, params: Dict[str, Any]) -> List[QcFinding]:
        """The inspector's findings in the shape `draw` reports refusals in."""
        return [QcFinding(f"trace:{f['code'].lower()}", f["severity"], f["message"],
                          label=f["path"])
                for f in inspect_algorithm_trace(params)]

    def render(self, params: Dict[str, Any]) -> str:
        params = params or {}
        findings, rendered = _inspect(params)
        if findings:
            return svg_document("", width=200, height=80,
                                class_name="diagram algorithm-trace")

        steps: List[Dict[str, Any]] = params["steps"]
        title = str(params.get("title") or "").strip()
        layout = params.get("layout") or "grid"
        panel_width, panel_height = _panel_size(params, rendered)
        show_numbers = bool(params.get("show_step_numbers", True))
        label_size = float(params.get("label_size", params.get("font_size", 14)))
        title_size = float(params.get("title_size", 23))

        # An explicit row or column is a layout; `columns` tunes the grid.
        if layout == "row":
            columns = len(steps)
        elif layout == "column":
            columns = 1
        elif _is_index(params.get("columns")) and params["columns"] > 0:
            columns = min(len(steps), params["columns"])
        else:
            columns = min(3, len(steps))
        rows = math.ceil(len(steps) / columns)

        top = MARGIN + (HEADER_H if title else 0)
        card_height = STEP_HEAD_H + panel_height + 14
        width = int(2 * MARGIN + columns * panel_width + (columns - 1) * GAP_X)
        height = int(top + rows * card_height + (rows - 1) * GAP_Y + MARGIN)

        parts: List[str] = [defs(self._arrow() + style(self._css(
            label_size, title_size
        )))]
        parts.append(rect(0, 0, width, height, fill="#fbfaf7", **{"class": "at-background"}))
        if title:
            drawn = fit_text(title, width - 2 * MARGIN, title_size, bold=True)
            parts.append(_named(title, drawn, text(MARGIN, MARGIN + 28, drawn,
                                                   **{"class": "at-title"})))

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
            drawn = fit_text(label, x + panel_width - 12 - label_x, label_size, bold=True)
            parts.append(_named(label, drawn, text(label_x, y + 26, drawn,
                                                   **{"class": "at-step-label"})))
            parts.append(_embedded_svg(
                svg, x + PANEL_INSET, y + STEP_HEAD_H, panel_width - 2 * PANEL_INSET,
                panel_height, f"Step {index + 1}: {label}"))

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
                drawn = fit_text(transition_label, label_budget, 12, bold=True)
                parts.append(_named(transition_label, drawn,
                                    text(lx, ly, drawn, text_anchor="middle",
                                         **{"class": "at-transition"})))

        return svg_document("".join(parts), width=width, height=height,
                            class_name="diagram algorithm-trace")

    @staticmethod
    def _arrow() -> str:
        return ('<marker id="at-arrow" markerWidth="9" markerHeight="7" refX="8" '
                'refY="3.5" orient="auto"><polygon points="0 0,9 3.5,0 7" '
                'fill="#7b8794"/></marker>')

    @staticmethod
    def _css(label_size: float = 14.0, title_size: float = 23.0) -> str:
        return """
.at-card{fill:#ffffff;stroke:#d9dde2;stroke-width:1.2}
.at-number-disc{fill:#315fbd}
.at-number{font-size:12px;font-weight:700;font-family:Inter,Helvetica,Arial,sans-serif;fill:#ffffff}
.at-arrow{fill:none;stroke:#7b8794;stroke-width:1.5}
.at-transition{font-size:12px;font-weight:600;font-family:Inter,Helvetica,Arial,sans-serif;fill:#68717a}
""" + f"""
.at-title{{font-size:{title_size:g}px;font-weight:700;font-family:Inter,Helvetica,Arial,sans-serif;fill:#17202a}}
.at-step-label{{font-size:{label_size:g}px;font-weight:650;font-family:Inter,Helvetica,Arial,sans-serif;fill:#17202a}}
"""
