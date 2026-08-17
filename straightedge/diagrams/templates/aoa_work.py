"""Activity-on-Arrow (双代号) work-representation teaching diagram.

Draws the 双代号 building block — numbered event nodes (circles) joined by an
arrow that carries the work name (above the arrow) and the duration (below).
Dummy work (虚工作) is a dashed arrow with no duration. Use this for 图6.5-style
"点和箭线" illustrations and small 虚工作 / 逻辑关系 examples; for a full computed
schedule with CPM numbers use ``project_network`` instead.

Nodes are placed on a (col, row) grid (defaults: col = position in the list,
row = 0). Arrows are drawn straight between node edges.

image_hint usage::

    {"type": "aoa_work", "params": {
        "title": "双代号：工作的表示方法",
        "nodes": [{"id": 1, "col": 0}, {"id": 2, "col": 1}],
        "arcs": [{"from": 1, "to": 2, "name": "A", "duration": 3}]}}

    # 虚工作示例
    {"type": "aoa_work", "params": {
        "title": "虚工作衔接逻辑",
        "nodes": [{"id": 1, "col": 0, "row": 0}, {"id": 2, "col": 1, "row": 0},
                   {"id": 3, "col": 1, "row": 1}, {"id": 4, "col": 2, "row": 0}],
        "arcs": [{"from": 1, "to": 2, "name": "A", "duration": 2},
                  {"from": 1, "to": 3, "name": "B", "duration": 3},
                  {"from": 2, "to": 3, "dummy": true},
                  {"from": 2, "to": 4, "name": "C", "duration": 4}]}}
"""
from __future__ import annotations

import math
from typing import Any, Dict, List

from ..registry import register
from ..renderer import circle, defs, style, svg_document, text

R = 24
COLW = 165
ROWH = 116
MARGIN = 30
TITLE_H = 36

_CSS = """
.aoa-node{stroke:#475569;stroke-width:2;fill:#ffffff}
.aoa-id{font:600 18px 'Noto Sans SC',sans-serif;fill:#1f2937}
.aoa-arrow{stroke:#475569;stroke-width:2;fill:none}
.aoa-arrow.dummy{stroke:#94a3b8;stroke-width:1.8;stroke-dasharray:7 5}
.aoa-name{font:600 16px 'Noto Sans SC',sans-serif;fill:#0f172a}
.aoa-dur{font:14px 'Noto Sans SC',sans-serif;fill:#2563eb}
.aoa-dummy-lab{font:13px 'Noto Sans SC',sans-serif;fill:#94a3b8}
.aoa-title{font:600 18px 'Noto Sans SC',sans-serif;fill:#0f172a}
"""

_ARROW = (
    '<marker id="aoa-tip" markerWidth="10" markerHeight="10" refX="8" refY="4.5" '
    'orient="auto"><path d="M0,0 L9,4.5 L0,9 Z" fill="#475569"/></marker>'
    '<marker id="aoa-tip-d" markerWidth="10" markerHeight="10" refX="8" refY="4.5" '
    'orient="auto"><path d="M0,0 L9,4.5 L0,9 Z" fill="#94a3b8"/></marker>'
)


def _title_width(title: str, px: int = 18) -> float:
    """Rough pixel width of a CJK/ASCII title at the given font size."""
    w = 0.0
    for ch in title:
        w += px if ord(ch) > 0x2E80 else px * 0.55
    return w


def _fmt(v: Any) -> str:
    try:
        f = float(v)
        return str(int(f)) if abs(f - round(f)) < 1e-9 else f"{f:g}"
    except (TypeError, ValueError):
        return str(v)


@register("aoa_work")
class AoaWorkTemplate:
    def render(self, params: Dict[str, Any]) -> str:
        params = params or {}
        title = str(params.get("title") or "").strip()
        nodes = params.get("nodes") or []
        arcs = params.get("arcs") or []

        # Resolve node grid positions.
        pos: Dict[Any, tuple] = {}
        max_col = max_row = 0
        for i, n in enumerate(nodes):
            nid = n.get("id", i + 1)
            col = int(n.get("col", i))
            row = int(n.get("row", 0))
            max_col = max(max_col, col)
            max_row = max(max_row, row)
            cx = MARGIN + col * COLW + R + 6
            cy = MARGIN + TITLE_H + row * ROWH + R + 6
            pos[nid] = (cx, cy)

        if not pos:
            return svg_document("", width=200, height=80, class_name="diagram aoa-work")

        diagram_w = MARGIN * 2 + max_col * COLW + 2 * R + 60
        title_w = (MARGIN * 2 + _title_width(title)) if title else 0
        width = int(max(diagram_w, title_w))
        height = int(MARGIN * 2 + TITLE_H + max_row * ROWH + 2 * R + 24)

        parts: List[str] = [defs(_ARROW + style(_CSS))]
        if title:
            parts.append(text(MARGIN, MARGIN + 16, title, **{"class": "aoa-title"}))

        # Arrows (under nodes).
        for a in arcs:
            s, t = a.get("from"), a.get("to")
            if s not in pos or t not in pos:
                continue
            (x1, y1), (x2, y2) = pos[s], pos[t]
            dx, dy = x2 - x1, y2 - y1
            dist = math.hypot(dx, dy) or 1.0
            ux, uy = dx / dist, dy / dist
            sx, sy = x1 + ux * R, y1 + uy * R
            ex, ey = x2 - ux * (R + 6), y2 - uy * (R + 6)
            dummy = bool(a.get("dummy"))
            cls = "aoa-arrow dummy" if dummy else "aoa-arrow"
            tip = "aoa-tip-d" if dummy else "aoa-tip"
            parts.append(
                f'<line x1="{sx:.1f}" y1="{sy:.1f}" x2="{ex:.1f}" y2="{ey:.1f}" '
                f'class="{cls}" marker-end="url(#{tip})"/>'
            )
            mx, my = (sx + ex) / 2, (sy + ey) / 2
            if dummy:
                parts.append(text(mx, my - 8, "虚工作", text_anchor="middle",
                                  **{"class": "aoa-dummy-lab"}))
            else:
                name = str(a.get("name") or "").strip()
                if name:
                    parts.append(text(mx, my - 9, name, text_anchor="middle",
                                      **{"class": "aoa-name"}))
                if a.get("duration") is not None:
                    parts.append(text(mx, my + 18, f"{_fmt(a['duration'])}",
                                      text_anchor="middle", **{"class": "aoa-dur"}))

        # Nodes (on top).
        for nid, (cx, cy) in pos.items():
            parts.append(circle(cx, cy, R, **{"class": "aoa-node"}))
            parts.append(text(cx, cy + 6, str(nid), text_anchor="middle",
                              **{"class": "aoa-id"}))

        return svg_document("".join(parts), width=width, height=height,
                            class_name="diagram aoa-work")
