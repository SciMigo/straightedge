"""SVG rendering utilities for diagram templates."""

from __future__ import annotations

from html import escape
from typing import Any, Dict, List, Optional


def _attrs_to_str(attrs: Dict[str, Any]) -> str:
    """Convert attribute dict to HTML attribute string."""
    parts = []
    for key, value in attrs.items():
        # Convert underscores to hyphens for CSS-style attributes
        attr_name = key.replace("_", "-")
        parts.append(f'{attr_name}="{escape(str(value))}"')
    return " ".join(parts)


def svg_document(
    content: str,
    width: int = 400,
    height: int = 300,
    viewbox: Optional[str] = None,
    class_name: str = "diagram",
) -> str:
    """Wrap content in an SVG document.

    Args:
        content: Inner SVG elements
        width: SVG width in pixels
        height: SVG height in pixels
        viewbox: Custom viewBox string (defaults to "0 0 width height")
        class_name: CSS class for the SVG element

    Returns:
        Complete SVG document string
    """
    vb = viewbox or f"0 0 {width} {height}"
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="{vb}" class="{class_name}">
{content}
</svg>'''


def circle(cx: float, cy: float, r: float, **attrs: Any) -> str:
    """Create an SVG circle element."""
    attr_str = _attrs_to_str(attrs)
    return f'<circle cx="{cx}" cy="{cy}" r="{r}" {attr_str}/>'


def rect(x: float, y: float, width: float, height: float, **attrs: Any) -> str:
    """Create an SVG rectangle element."""
    attr_str = _attrs_to_str(attrs)
    return f'<rect x="{x}" y="{y}" width="{width}" height="{height}" {attr_str}/>'


def line(x1: float, y1: float, x2: float, y2: float, **attrs: Any) -> str:
    """Create an SVG line element."""
    attr_str = _attrs_to_str(attrs)
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" {attr_str}/>'


def polyline(points: List[tuple[float, float]], **attrs: Any) -> str:
    """Create an SVG polyline element."""
    points_str = " ".join(f"{x},{y}" for x, y in points)
    attr_str = _attrs_to_str(attrs)
    return f'<polyline points="{points_str}" {attr_str}/>'


def path(d: str, **attrs: Any) -> str:
    """Create an SVG path element."""
    attr_str = _attrs_to_str(attrs)
    return f'<path d="{d}" {attr_str}/>'


def text(x: float, y: float, content: str, **attrs: Any) -> str:
    """Create an SVG text element."""
    attr_str = _attrs_to_str(attrs)
    return f'<text x="{x}" y="{y}" {attr_str}>{escape(content)}</text>'


def group(content: str, **attrs: Any) -> str:
    """Create an SVG group element."""
    attr_str = _attrs_to_str(attrs)
    if attr_str:
        return f'<g {attr_str}>{content}</g>'
    return f'<g>{content}</g>'


def defs(content: str) -> str:
    """Create an SVG defs element for reusable definitions."""
    return f'<defs>{content}</defs>'


def use(href: str, x: float = 0, y: float = 0, **attrs: Any) -> str:
    """Create an SVG use element to reference a definition."""
    attr_str = _attrs_to_str(attrs)
    return f'<use href="#{href}" x="{x}" y="{y}" {attr_str}/>'


def style(css: str) -> str:
    """Create an embedded SVG style element."""
    return f'<style>{css}</style>'


# Common style definitions
DEFAULT_STYLES = """
.diagram-point { fill: #666; }
.diagram-point-visible { fill: #4CAF50; }
.diagram-point-hidden { fill: #ccc; }
.diagram-point-origin { fill: #2196F3; }
.diagram-point-highlight { fill: #FF9800; }
.diagram-ray { stroke: #999; stroke-width: 1; stroke-dasharray: 4,2; fill: none; }
.diagram-axis { stroke: #333; stroke-width: 2; fill: none; }
.diagram-grid { stroke: #eee; stroke-width: 1; fill: none; }
.diagram-label { font-size: 12px; font-family: sans-serif; fill: #333; }
.diagram-label-small { font-size: 10px; font-family: sans-serif; fill: #666; }
"""


def wrap_units(s: str, max_units: float, max_lines: int = 2) -> List[str]:
    """Greedy wrap counting CJK as full-width (1.0) and Latin as ~half (0.5).

    Breaks at a space when the overflowing line has one, so Latin wraps on word
    boundaries ("thousand" / "joules") instead of mid-word ("thousand j" /
    "oules"). CJK has no spaces, so it keeps the character-greedy behaviour.

    Shared because this bug has now shipped twice — flow_diagram wrapped English
    mid-word, and so did comparison. One wrapper, one fix.
    """
    if not s:
        return []
    lines: List[str] = []
    cur, width = "", 0.0
    for ch in s:
        w = 1.0 if ord(ch) > 0x2E7F else 0.5
        if width + w > max_units and cur:
            head, sep, tail = cur.rpartition(" ")
            if sep and head.strip():
                lines.append(head.rstrip())
                cur = tail + ch
                width = sum(1.0 if ord(c) > 0x2E7F else 0.5 for c in cur)
            else:
                lines.append(cur)
                cur, width = ch, w
        else:
            cur += ch
            width += w
    if cur.strip():
        lines.append(cur.strip())
    return lines[:max_lines]
