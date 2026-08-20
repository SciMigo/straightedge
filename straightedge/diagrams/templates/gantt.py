"""Gantt chart (横道图) for project schedules.

Accepts either explicit ``tasks`` (each with ``start`` + ``duration``) or the
same ``activities`` list as ``project_network`` — in which case the CPM forward
pass schedules every task at its earliest start and flags the critical ones.
Bars sit on a unit time axis; critical tasks are highlighted.

image_hint usage::

    {"type": "gantt", "params": {"title": "进度横道图",
        "activities": [{"id": "A", "duration": 3, "predecessors": []}, ...]}}
    # or
    {"type": "gantt", "params": {"tasks": [
        {"name": "基础", "start": 0, "duration": 3, "critical": true}, ...]}}
"""
from __future__ import annotations

from typing import Any, Dict, List

from ..cpm import compute_cpm
from ..registry import register
from ..renderer import rect, style, svg_document, text

ROW_H = 34
BAR_H = 20
LABEL_W = 116
MARGIN = 24
TITLE_H = 34
AXIS_H = 22
MIN_UNIT_PX = 26
MAX_CHART_W = 900     # a long schedule scales down rather than growing without bound
MAX_TICKS = 24        # beyond this the axis is a grey block, not a scale

_CSS = """
.g-label{font:14px 'Noto Sans SC',sans-serif;fill:#334155}
.g-bar{fill:#2f7d72;rx:4}
.g-bar.crit{fill:#d64545}
.g-grid{stroke:#e5e7eb;stroke-width:1}
.g-axis{font:11px 'Noto Sans SC',sans-serif;fill:#94a3b8}
.g-title{font:600 18px 'Noto Sans SC',sans-serif;fill:#0f172a}
.g-dur{font:11px 'Noto Sans SC',sans-serif;fill:#ffffff}
"""


def _fmt(v: float) -> str:
    return str(int(v)) if abs(v - round(v)) < 1e-9 else f"{v:g}"


def _fit(name: str, width: float = LABEL_W - 10, size: float = 14) -> str:
    """Trim a row label to the label gutter, with an ellipsis when it is cut.

    The previous fixed ``[:8]`` was blind to the gutter it was cutting for, and
    silently truncated mid-word with no sign anything had been dropped.
    """
    budget = max(4, int(width / (size * 0.55)))
    return name if len(name) <= budget else name[: budget - 1].rstrip() + "\u2026"


def _tasks_from_params(params: Dict[str, Any]) -> List[Dict[str, Any]]:
    if params.get("activities"):
        cpm = compute_cpm(params["activities"])
        return [
            {"name": cpm.activities[aid].name or aid,
             "start": cpm.activities[aid].es,
             "duration": cpm.activities[aid].duration,
             "critical": cpm.activities[aid].critical}
            for aid in cpm.order
        ]
    out: List[Dict[str, Any]] = []
    for t in params.get("tasks") or []:
        if not isinstance(t, dict):
            continue
        out.append({
            "name": str(t.get("name") or t.get("id") or "").strip(),
            "start": float(t.get("start", 0) or 0),
            "duration": float(t.get("duration", t.get("dur", 0)) or 0),
            "critical": bool(t.get("critical", False)),
        })
    return out


@register("gantt")
class GanttTemplate:
    def render(self, params: Dict[str, Any]) -> str:
        params = params or {}
        try:
            tasks = _tasks_from_params(params)
        except ValueError:
            return svg_document(text(20, 40, "进度数据存在循环依赖", **{"class": "g-title"}),
                                width=360, height=80, class_name="diagram gantt")
        if not tasks:
            return svg_document("", width=200, height=80, class_name="diagram gantt")

        title = str(params.get("title") or "").strip()
        max_t = max((t["start"] + t["duration"] for t in tasks), default=0) or 1
        scale = max(MIN_UNIT_PX, min(60, 560 / max_t))
        # MIN_UNIT_PX alone means the chart grows linearly with the unit count: a
        # schedule expressed in days rather than weeks rendered ~4,800px wide with
        # one gridline per day. Below the floor the units are dense, so fit them.
        if max_t * scale > MAX_CHART_W:
            scale = MAX_CHART_W / max_t

        chart_x = MARGIN + LABEL_W
        width = int(chart_x + max_t * scale + MARGIN)
        top = MARGIN + (TITLE_H if title else 0)
        height = int(top + AXIS_H + len(tasks) * ROW_H + MARGIN)

        parts: List[str] = ['<defs>' + style(_CSS) + '</defs>']
        if title:
            parts.append(text(MARGIN, MARGIN + 16, title, **{"class": "g-title"}))

        # Vertical gridlines + axis ticks (integer units).
        grid_top = top + AXIS_H
        grid_bot = grid_top + len(tasks) * ROW_H
        n_ticks = int(max_t) + 1
        step = max(1, -(-n_ticks // MAX_TICKS))
        for u in range(0, n_ticks, step):
            gx = chart_x + u * scale
            parts.append(f'<line x1="{gx}" y1="{grid_top}" x2="{gx}" y2="{grid_bot}" class="g-grid"/>')
            parts.append(text(gx, top + 14, _fmt(u), text_anchor="middle", **{"class": "g-axis"}))

        # Rows.
        for i, t in enumerate(tasks):
            ry = grid_top + i * ROW_H
            parts.append(text(MARGIN, ry + ROW_H / 2 + 4, _fit(t["name"]), **{"class": "g-label"}))
            bx = chart_x + t["start"] * scale
            bw = max(2, t["duration"] * scale)
            by = ry + (ROW_H - BAR_H) / 2
            crit = " crit" if t["critical"] else ""
            parts.append(rect(bx, by, bw, BAR_H, rx=4, **{"class": f"g-bar{crit}"}))
            if t["duration"] > 0:
                parts.append(text(bx + bw / 2, by + BAR_H / 2 + 4, _fmt(t["duration"]),
                                  text_anchor="middle", **{"class": "g-dur"}))

        return svg_document("".join(parts), width=width, height=height,
                            class_name="diagram gantt")
