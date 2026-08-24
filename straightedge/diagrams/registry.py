"""Diagram template registry and rendering dispatcher."""

from __future__ import annotations

import logging
import re
from typing import Any, Callable, Dict, List, Protocol

from ..qc import Finding

logger = logging.getLogger(__name__)

# Chrome a diagram draws whether or not it has anything to say: grid, axes,
# ticks, tick labels, title, legend. A template that cannot interpret its params
# still renders all of it, so *size* cannot tell a full plot from an empty one —
# a bare coordinate plane is several kilobytes of grid lines. Count the marks
# that carry data instead, and treat "chrome only" as blank.
_CHROME_CLASS_HINTS = ("grid", "axis", "axes", "tick", "label", "title", "legend")
_DRAWABLE_RE = re.compile(
    r"<(?:path|circle|rect|polygon|polyline|ellipse|image|use|line)\b([^>]*)>"
)
_CLASS_RE = re.compile(r'class="([^"]*)"')
_STYLE_BLOCK_RE = re.compile(r"<style\b.*?</style>", re.DOTALL)
# Nothing inside <defs> is painted by being there: an arrowhead <marker> is a
# <polygon> that only appears where a path references it. Twenty templates
# define one, so an empty array, stack or queue used to score exactly one mark
# and pass as drawn.
_DEFS_BLOCK_RE = re.compile(r"<defs\b.*?</defs>", re.DOTALL)

# A geometry attribute that came out non-finite. An expression that does not
# reduce to a number yields NaN coordinates, and `height="nan"` is not markup a
# renderer draws — but it *is* a <rect>, so counting elements alone reported a
# broken figure as a full one. The check belongs here rather than in each
# template: any of the 35 can produce this, and only one of them was audited.
_NON_FINITE_RE = re.compile(r'\b(?:nan|-?inf(?:inity)?)\b', re.IGNORECASE)


def count_data_marks(svg: str) -> int:
    """Count drawable elements that carry data rather than chrome.

    Used by callers with different severities: :func:`render_diagram` warns,
    while an application gating a deck before it pays to render can refuse.
    Sharing the predicate is the point — the two used to hold independent byte
    thresholds that were "kept in sync" by comment, and both were blind to the
    same failure.
    """
    if not svg:
        return 0
    body = _DEFS_BLOCK_RE.sub("", _STYLE_BLOCK_RE.sub("", svg))
    marks = 0
    for attrs in _DRAWABLE_RE.findall(body):
        class_match = _CLASS_RE.search(attrs)
        classes = class_match.group(1).lower() if class_match else ""
        if any(hint in classes for hint in _CHROME_CLASS_HINTS):
            continue
        if _NON_FINITE_RE.search(attrs):
            continue                    # drawn from a value that is not a number
        marks += 1
    return marks


def is_blank_diagram(svg: str) -> bool:
    """True when an SVG rendered chrome but no data — a params-shape mismatch."""
    return count_data_marks(svg) == 0


class DiagramTemplate(Protocol):
    """Protocol for diagram templates."""

    def render(self, params: Dict[str, Any]) -> str:
        """Render diagram as SVG string."""
        ...


# Global registry of diagram templates
DIAGRAM_REGISTRY: Dict[str, DiagramTemplate] = {}


def register(name: str) -> Callable:
    """Decorator to register a diagram template.

    Usage:
        @register("lattice_grid")
        class LatticeGridTemplate:
            def render(self, params: Dict[str, Any]) -> str:
                ...
    """

    def decorator(cls: type) -> type:
        DIAGRAM_REGISTRY[name] = cls()
        return cls

    return decorator


def hint_params(hint: Dict[str, Any]) -> Dict[str, Any]:
    """The parameters of a structured hint, in either envelope it accepts.

    ``{"type": t, "params": {...}}`` is the documented form; ``{"type": t,
    ...}`` with the parameters beside the type is the flat form callers have
    always been able to send. Anything else in the ``params`` slot is read as
    nothing. Shared so a template that nests other templates — `algorithm_trace`
    — accepts the same envelopes as :func:`render_diagram` rather than drawing
    an empty child for the flat one.
    """
    params = hint.get("params")
    if params is None:
        return {k: v for k, v in hint.items() if k != "type"}
    return params if isinstance(params, dict) else {}


def refusal_findings(diagram_type: str, params: Dict[str, Any]) -> List[Finding]:
    """Why a template refused to draw, when it can say — otherwise empty.

    A blank figure is usually a parameter-shape mismatch, and the callers that
    see one say so. But a template that *checks* its input — `construction`
    against its claims, `algorithm_trace` against its transitions — blocks a
    drawing deliberately, and telling that caller to check shapes that are
    already correct sends them to look in the wrong place. A template that can
    say why exposes ``refusal_findings(params)``; this is the one place the MCP
    `draw` tool and the CLI `draw` command ask.
    """
    template = DIAGRAM_REGISTRY.get(diagram_type)
    refuse = getattr(template, "refusal_findings", None)
    if not callable(refuse):
        return []
    return list(refuse(params if isinstance(params, dict) else {}))


def refusal_reason(findings: List[Finding]) -> str:
    """The first finding's message, and how many stand behind it."""
    reason = findings[0].message
    if len(findings) > 1:
        reason += f" (and {len(findings) - 1} more)"
    return reason


def render_diagram(hint: Dict[str, Any] | str | None) -> str:
    """Render a structured image_hint to SVG.

    Args:
        hint: Either a structured dict with "type" and "params",
              or a string (legacy format, returns empty),
              or None (returns empty).

    Returns:
        SVG string, or empty string if diagram type is unknown or hint is invalid.
    """
    if hint is None:
        return ""

    if isinstance(hint, str):
        # Legacy string hint - cannot render structured diagram
        return ""

    if not isinstance(hint, dict):
        return ""

    diagram_type = hint.get("type")
    if not diagram_type:
        return ""
    if diagram_type not in DIAGRAM_REGISTRY:
        logger.warning(
            "Unknown diagram type %r — slide will have no diagram", diagram_type
        )
        return ""

    params = hint_params(hint)

    try:
        template = DIAGRAM_REGISTRY[diagram_type]
        svg = template.render(params)
    except Exception as exc:
        # Fail gracefully - return empty on any rendering error
        logger.warning("Diagram %r failed to render: %s", diagram_type, exc)
        return ""

    if svg and is_blank_diagram(svg):
        # Rendered, but with nothing in it: almost always a params-shape
        # mismatch the template could not interpret.
        logger.warning(
            "Diagram %r rendered %d bytes of chrome but no data marks — check "
            "params keys: %s",
            diagram_type, len(svg), sorted(params)[:8],
        )
    return svg
