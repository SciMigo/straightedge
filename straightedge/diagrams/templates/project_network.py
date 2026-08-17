"""Activity-on-Node (单代号/AON) project network diagram with CPM annotation.

Renders a precise, correct schedule network from structured activity data — the
canonical project-management diagram. Each activity is drawn as the standard
six-cell CPM node box::

    +------+------+------+
    |  ES  | Dur  |  EF  |
    +------+------+------+
    |      <id/name>     |
    +------+------+------+
    |  LS  |  TF  |  LF  |
    +------+------+------+

The forward/backward pass (:mod:`straightedge.diagrams.cpm`) computes ES/EF/LS/LF and
total float; the **critical path** (float = 0) is highlighted. Because this is
computed, not drawn by an image model, the topology and every number are exactly
right — which is the entire point for a worked example.

image_hint usage::

    {"type": "project_network",
     "params": {"title": "例题 6.2 双代号网络图",
                "activities": [
                  {"id": "A", "duration": 3, "predecessors": []},
                  {"id": "B", "duration": 4, "predecessors": ["A"]},
                  ...],
                "show_cpm": true}}
"""
from __future__ import annotations

from typing import Any, Dict, List

from ..cpm import compute_cpm
from ..registry import register
from ..renderer import defs, rect, style, svg_document, text

BOX_W = 138
BOX_H = 84
COL = BOX_W / 3
ROW = BOX_H / 3
HGAP = 78
VGAP = 36
MARGIN = 28
TITLE_H = 40

_CSS = """
.pn-box{stroke:#94a3b8;stroke-width:1.5;fill:#ffffff}
.pn-box.crit{stroke:#d64545;stroke-width:2.5;fill:#fdecea}
.pn-cell{stroke:#cbd5e1;stroke-width:1;fill:none}
.pn-id{font:600 20px 'Noto Sans SC',sans-serif;fill:#1f2937}
.pn-id.crit{fill:#b91c1c}
.pn-val{font:13px 'Noto Sans SC',sans-serif;fill:#475569}
.pn-edge{stroke:#94a3b8;stroke-width:1.6;fill:none}
.pn-edge.crit{stroke:#d64545;stroke-width:2.4}
.pn-title{font:600 18px 'Noto Sans SC',sans-serif;fill:#0f172a}
.pn-legend{font:12px 'Noto Sans SC',sans-serif;fill:#64748b}
"""

_ARROW = (
    '<marker id="pn-arrow" markerWidth="9" markerHeight="9" refX="8" refY="4.5" '
    'orient="auto"><path d="M0,0 L9,4.5 L0,9 Z" fill="#94a3b8"/></marker>'
    '<marker id="pn-arrow-c" markerWidth="9" markerHeight="9" refX="8" refY="4.5" '
    'orient="auto"><path d="M0,0 L9,4.5 L0,9 Z" fill="#d64545"/></marker>'
)


def _fmt(v: float) -> str:
    return str(int(v)) if abs(v - round(v)) < 1e-9 else f"{v:g}"


def _cell_text(cx: float, cy: float, label: str, cls: str = "pn-val") -> str:
    return text(cx, cy + 4, label, text_anchor="middle", **{"class": cls})


@register("project_network")
class ProjectNetworkTemplate:
    def render(self, params: Dict[str, Any]) -> str:
        params = params or {}
        activities = params.get("activities") or []
        show_cpm = params.get("show_cpm", True)
        title = str(params.get("title") or "").strip()

        try:
            cpm = compute_cpm(activities)
        except ValueError:
            return svg_document(
                text(20, 40, "网络图存在循环依赖，无法计算", **{"class": "pn-title"}),
                width=420, height=80, class_name="diagram project-network",
            )
        if not cpm.activities:
            return svg_document("", width=200, height=80, class_name="diagram project-network")

        # Assign a vertical slot per layout level.
        by_level: Dict[int, List[str]] = {}
        for aid in cpm.order:
            by_level.setdefault(cpm.levels[aid], []).append(aid)
        max_level = max(by_level) if by_level else 0
        max_slots = max((len(v) for v in by_level.values()), default=1)

        pos: Dict[str, tuple] = {}
        for lvl, ids in by_level.items():
            x = MARGIN + lvl * (BOX_W + HGAP)
            # center this level's stack vertically within the tallest column
            total = len(ids) * BOX_H + (len(ids) - 1) * VGAP
            full = max_slots * BOX_H + (max_slots - 1) * VGAP
            y0 = MARGIN + TITLE_H + (full - total) / 2
            for slot, aid in enumerate(ids):
                pos[aid] = (x, y0 + slot * (BOX_H + VGAP))

        width = MARGIN * 2 + (max_level + 1) * BOX_W + max_level * HGAP
        height = MARGIN * 2 + TITLE_H + max_slots * BOX_H + (max_slots - 1) * VGAP + 24

        parts: List[str] = [defs(_ARROW + style(_CSS))]
        if title:
            parts.append(text(MARGIN, MARGIN + 18, title, **{"class": "pn-title"}))

        # Edges first (under boxes).
        for aid in cpm.order:
            a = cpm.activities[aid]
            ax, ay = pos[aid]
            for p in a.predecessors:
                px, py = pos[p]
                x1, y1 = px + BOX_W, py + BOX_H / 2
                x2, y2 = ax, ay + BOX_H / 2
                crit = cpm.activities[p].critical and a.critical
                cls = "pn-edge crit" if crit else "pn-edge"
                marker = "pn-arrow-c" if crit else "pn-arrow"
                midx = (x1 + x2) / 2
                d = f"M{x1},{y1} C{midx},{y1} {midx},{y2} {x2-2},{y2}"
                parts.append(f'<path d="{d}" class="{cls}" marker-end="url(#{marker})"/>')

        # Boxes.
        for aid in cpm.order:
            a = cpm.activities[aid]
            x, y = pos[aid]
            crit = " crit" if a.critical else ""
            parts.append(rect(x, y, BOX_W, BOX_H, rx=6, **{"class": f"pn-box{crit}"}))
            label = a.name or a.id
            parts.append(_cell_text(x + BOX_W / 2, y + ROW + ROW / 2 - 2,
                                    label, cls=f"pn-id{crit}"))
            if show_cpm:
                # row separators + column separators (top & bottom rows only)
                for ry in (ROW, 2 * ROW):
                    parts.append(f'<line x1="{x}" y1="{y+ry}" x2="{x+BOX_W}" y2="{y+ry}" class="pn-cell"/>')
                for cx in (COL, 2 * COL):
                    parts.append(f'<line x1="{x+cx}" y1="{y}" x2="{x+cx}" y2="{y+ROW}" class="pn-cell"/>')
                    parts.append(f'<line x1="{x+cx}" y1="{y+2*ROW}" x2="{x+cx}" y2="{y+BOX_H}" class="pn-cell"/>')
                top = [_fmt(a.es), _fmt(a.duration), _fmt(a.ef)]
                bot = [_fmt(a.ls), _fmt(a.total_float), _fmt(a.lf)]
                for i, val in enumerate(top):
                    parts.append(_cell_text(x + COL * i + COL / 2, y + ROW / 2, val))
                for i, val in enumerate(bot):
                    parts.append(_cell_text(x + COL * i + COL / 2, y + 2 * ROW + ROW / 2, val))

        if show_cpm:
            ly = height - 8
            parts.append(text(MARGIN, ly,
                              f"工期 = {_fmt(cpm.project_duration)}　关键路径: "
                              + "→".join(cpm.critical_path),
                              **{"class": "pn-legend"}))

        return svg_document("".join(parts), width=int(width), height=int(height),
                            class_name="diagram project-network")
