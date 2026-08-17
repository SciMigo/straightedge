"""Milestone timeline (时间轴 / 发展历程) — a horizontal line of dated events.

The infographic staple for a *history* or *evolution*: 会计发展简史, 会计准则的演进,
a company's milestones. Events sit as markers along a horizontal axis, captions
alternating above/below so labels stay readable. Distinct from :mod:`gantt`
(scheduled task bars) — this is point-in-time milestones.

image_hint usage::

    {"type": "timeline", "params": {
        "title": "会计发展简史",
        "events": [
            {"date": "远古", "label": "结绳记事", "desc": "简单计数"},
            {"date": "1494", "label": "复式记账", "desc": "帕乔利《算术》"},
            {"date": "20世纪", "label": "会计准则", "desc": "规范化"},
            {"date": "当代", "label": "会计信息化", "desc": "ERP与智能财务"}]}}

``events`` accepts alias ``items`` / ``milestones``; each event may use ``date`` /
``year`` / ``time`` for the marker date, ``label`` / ``title`` / ``name`` /
``text`` for the headline, and ``desc`` / ``description`` for the line under it.
"""
from __future__ import annotations

from typing import Any, Dict, List

from ..registry import register
from ..renderer import circle, group, line, rect, style, svg_document, text

MARGIN = 30
TITLE_H = 36
COL_W = 190          # horizontal span per event
AXIS_GAP = 34        # vertical gap between axis and a caption block
CARD_H = 82
DOT_R = 9
DEFAULT_ACCENT = "#e4572e"   # infographic warm red


def _events(raw: Any) -> List[Dict[str, str]]:
    if not isinstance(raw, list):
        return []
    out: List[Dict[str, str]] = []
    for it in raw:
        if isinstance(it, str):
            out.append({"date": "", "label": it.strip(), "desc": ""})
            continue
        if not isinstance(it, dict):
            continue
        date = str(it.get("date") or it.get("year") or it.get("time") or "").strip()
        label = str(it.get("label") or it.get("title") or it.get("name")
                    or it.get("text") or "").strip()
        desc = str(it.get("desc") or it.get("description") or "").strip()
        if date or label:
            out.append({"date": date, "label": label, "desc": desc})
    return out


def _wrap(s: str, n: int) -> List[str]:
    s = str(s or "").strip()
    if not s:
        return []
    lines, cur, w = [], "", 0.0
    for ch in s:
        cw = 1.0 if ord(ch) > 0x2E7F else 0.5
        if w + cw > n and cur:
            lines.append(cur)
            cur, w = ch, cw
        else:
            cur += ch
            w += cw
    if cur:
        lines.append(cur)
    return lines[:3]


@register("timeline")
class TimelineTemplate:
    def render(self, params: Dict[str, Any]) -> str:
        params = params or {}
        events = _events(params.get("events") or params.get("items")
                         or params.get("milestones"))
        if len(events) < 2:
            return svg_document("", width=200, height=80,
                                class_name="diagram timeline")

        accent = str(params.get("accent") or params.get("color")
                     or DEFAULT_ACCENT).strip() or DEFAULT_ACCENT
        title = str(params.get("title") or "").strip()

        n = len(events)
        top0 = MARGIN + (TITLE_H if title else 0)
        axis_y = top0 + CARD_H + AXIS_GAP       # captions above, then axis, then below
        width = MARGIN * 2 + n * COL_W
        height = axis_y + AXIS_GAP + CARD_H + MARGIN

        parts: List[str] = [style(self._css(accent))]
        if title:
            parts.append(text(width / 2, MARGIN + 18, title,
                              **{"class": "tl-title", "text-anchor": "middle"}))

        # the axis
        x0 = MARGIN + COL_W / 2
        x1 = MARGIN + (n - 0.5) * COL_W
        parts.append(line(x0, axis_y, x1, axis_y, **{"class": "tl-axis"}))

        for i, ev in enumerate(events):
            cx = MARGIN + (i + 0.5) * COL_W
            above = (i % 2 == 0)
            parts.append(circle(cx, axis_y, DOT_R, **{"class": "tl-dot"}))
            # connector stub
            cy = axis_y - AXIS_GAP if above else axis_y + AXIS_GAP
            parts.append(line(cx, axis_y, cx, cy, **{"class": "tl-stub"}))
            parts.append(self._caption(ev, cx, above, axis_y))
        return svg_document("\n".join(parts), width=width, height=height,
                            class_name="diagram timeline")

    def _caption(self, ev: Dict[str, str], cx: float, above: bool,
                 axis_y: float) -> str:
        label_lines = _wrap(ev["label"], 8)
        desc_lines = _wrap(ev["desc"], 11)
        block: List[str] = []
        # position: captions grow away from the axis
        if above:
            ty = axis_y - AXIS_GAP - 10 - (len(desc_lines) * 16) - (len(label_lines) * 20)
        else:
            ty = axis_y + AXIS_GAP + 26
        if ev["date"]:
            block.append(text(cx, ty, ev["date"],
                              **{"class": "tl-date", "text-anchor": "middle"}))
            ty += 22
        for ln in label_lines:
            block.append(text(cx, ty, ln, **{"class": "tl-label", "text-anchor": "middle"}))
            ty += 20
        for ln in desc_lines:
            block.append(text(cx, ty, ln, **{"class": "tl-desc", "text-anchor": "middle"}))
            ty += 16
        return group("\n".join(block))

    def _css(self, accent: str) -> str:
        return f"""
.tl-title{{font:600 19px 'Noto Sans SC',sans-serif;fill:#0f172a}}
.tl-axis{{stroke:{accent};stroke-width:3}}
.tl-dot{{fill:#ffffff;stroke:{accent};stroke-width:3}}
.tl-stub{{stroke:{accent};stroke-width:1.5;stroke-dasharray:3 3}}
.tl-date{{font:700 17px 'Noto Sans SC',sans-serif;fill:{accent}}}
.tl-label{{font:600 15px 'Noto Sans SC',sans-serif;fill:#1f2937}}
.tl-desc{{font:12px 'Noto Sans SC',sans-serif;fill:#5b6573}}
"""
