"""Calendar roadmap (路线图) — dated work in swim lanes, with milestones.

Distinct from :mod:`gantt`, which places bars on a *unit* axis for a CPM
exercise: its ticks are integers and every task owns a row. A roadmap is dated
work owned by tracks — "Rendering engine", "Hosted service" — where several
items share a lane, the axis carries calendar dates, and point-in-time
milestones cut across every lane. Expressing one through the other loses the
lane, the milestone and the date: a six-month plan handed to ``gantt`` as day
units renders ~4,800px wide with a 0..180 axis.

image_hint usage::

    {"type": "roadmap", "params": {
        "title": "Launch roadmap",
        "start_date": "2026-09-01", "end_date": "2027-02-28",
        "tracks": [{"id": "engine", "label": "Rendering engine"}],
        "items": [{"id": "t1", "title": "Renderer", "track": "engine",
                   "start_date": "2026-09-01", "end_date": "2026-10-15",
                   "status": "active", "depends_on": []}],
        "milestones": [{"title": "Private beta", "date": "2026-11-01"}]}}

``status`` is one of ``planned``, ``active``, ``at-risk``, ``complete``,
``tentative`` and only colours the bar. ``depends_on`` draws a connector between
two placed items; a dependency whose target starts before its source finishes is
routed around rather than drawn backwards through the lane.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Tuple

from ..registry import register
from ..renderer import path, rect, style, svg_document, text
from ..renderer import text_width as _measure

WIDTH = 1160
MARGIN = 28
LABEL_W = 168
BAR_H = 24
SUBROW_H = 32
TRACK_PAD = 13
HEADER_H = 152
LEGEND_H = 44
MIN_BAR_W = 6
AXIS_TICKS = 6

STATUS_COLORS = {
    "planned": "#4c78a8",
    "active": "#2a9d8f",
    "at-risk": "#e76f51",
    "complete": "#5b8c5a",
    "tentative": "#8d79a8",
}
STATUS_ORDER = ("planned", "active", "at-risk", "complete", "tentative")
MILESTONE = "#d97706"

# Longhand, with a conservative family list. The `font:` shorthand combined with
# CSS4 generics (`ui-sans-serif`, `system-ui`) is mis-parsed by some SVG
# rasterisers — cairosvg reads the *weight* as the size and renders 700px text —
# and this output is meant to survive conversion outside a browser.
_CSS = """
.r-t{font-size:23px;font-weight:700;fill:#17202a}
.r-sub{font-size:12px;fill:#68717a}
.r-trk{font-size:13px;font-weight:650;fill:#17202a}
.r-axis{font-size:11px;fill:#68717a}
.r-bar-text{font-size:11.5px;font-weight:600;fill:#17202a}
.r-bar-text-in{font-size:11.5px;font-weight:600;fill:#ffffff}
.r-ms{font-size:11px;font-weight:600;fill:#d97706}
.r-dep{stroke:#9aa4ad;stroke-width:1.2;fill:none;opacity:0.75}
text{font-family:Inter,Helvetica,Arial,sans-serif}
"""


def _date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def text_width(value: str, size: float, bold: bool = False) -> float:
    """Advance width of a caption, delegating to the shared measurement.

    It decides whether a caption fits inside its bar, and a caption that
    overflows its bar is the failure this template exists to avoid — so it has
    to be right for the text actually drawn. The private `len(value) * 0.55`
    this replaced counted a Chinese glyph as half an em: nine characters
    measured 57px and rendered ~103px, and the caption went inside a bar it
    overflowed. `renderer.text_width` counts CJK full-width and distinguishes a
    semi-bold em from a regular one.
    """
    return _measure(value, size, bold=bold)


def pack_lanes(items: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    """Greedy interval packing — a new sub-row only when bars would overlap."""
    rows: List[List[Dict[str, Any]]] = []
    for item in sorted(items, key=lambda i: (i["start"], i["end"])):
        for row in rows:
            if item["start"] > row[-1]["end"]:
                row.append(item)
                break
        else:
            rows.append([item])
    return rows


def _ticks(start: date, end: date) -> List[date]:
    span = max(1, (end - start).days)
    return [start + timedelta(days=round(span * i / (AXIS_TICKS - 1)))
            for i in range(AXIS_TICKS)]


@register("roadmap")
class RoadmapTemplate:
    def render(self, params: Dict[str, Any]) -> str:
        params = params or {}
        start = _date(params.get("start_date"))
        end = _date(params.get("end_date"))
        tracks = [t for t in params.get("tracks") or [] if isinstance(t, dict)]
        if start is None or end is None or end < start or not tracks:
            return svg_document("", width=200, height=80, class_name="diagram roadmap")

        span = max(1, (end - start).days + 1)
        chart_x = MARGIN + LABEL_W
        chart_w = WIDTH - chart_x - MARGIN

        def x_for(value: date, edge: bool = False) -> float:
            offset = (value - start).days + (1 if edge else 0)
            return chart_x + chart_w * min(max(offset, 0), span) / span

        by_track: Dict[str, List[Dict[str, Any]]] = {str(t.get("id")): [] for t in tracks}
        for raw in params.get("items") or []:
            if not isinstance(raw, dict):
                continue
            track_id = str(raw.get("track"))
            item_start, item_end = _date(raw.get("start_date")), _date(raw.get("end_date"))
            if track_id not in by_track or item_start is None or item_end is None:
                continue
            by_track[track_id].append({
                "id": str(raw.get("id") or ""),
                "title": str(raw.get("title") or ""),
                "start": item_start,
                "end": max(item_start, item_end),
                "status": str(raw.get("status") or "planned"),
                "depends_on": [str(d) for d in raw.get("depends_on") or []],
            })

        layout: List[Tuple[Dict[str, Any], List[List[Dict[str, Any]]], float, float]] = []
        placed: Dict[str, Dict[str, Any]] = {}
        y = float(HEADER_H)
        for track in tracks:
            rows = pack_lanes(by_track[str(track.get("id"))]) or [[]]
            height = TRACK_PAD * 2 + len(rows) * SUBROW_H
            layout.append((track, rows, y, height))
            for row_index, row in enumerate(rows):
                for item in row:
                    item["y"] = y + TRACK_PAD + row_index * SUBROW_H + (SUBROW_H - BAR_H) / 2
                    if item["id"]:
                        placed[item["id"]] = item
            y += height
        bottom = y
        height_total = int(bottom + LEGEND_H + MARGIN)

        p: List[str] = ["<defs>" + style(_CSS) + "</defs>"]
        p.append(rect(0, 0, WIDTH, height_total, fill="#fbfaf7", **{"class": "grid-paper"}))

        title = str(params.get("title") or "").strip()
        count = sum(len(v) for v in by_track.values())
        if title:
            p.append(text(MARGIN, 42, title, **{"class": "r-t"}))
        p.append(text(MARGIN, 63,
                      f"{start.isoformat()} → {end.isoformat()} · {len(tracks)} tracks "
                      f"· {count} items", **{"class": "r-sub"}))

        for milestone in params.get("milestones") or []:
            if not isinstance(milestone, dict):
                continue
            when = _date(milestone.get("date"))
            if when is None:
                continue
            mx = x_for(when)
            label = str(milestone.get("title") or "")
            flip = mx + 11 + text_width(label, 11, bold=True) > WIDTH - MARGIN
            anchor, tx = ("end", mx - 11) if flip else ("start", mx + 11)
            p.append(path(f"M {mx:.1f} 88 L {mx + 6:.1f} 95 L {mx:.1f} 102 "
                          f"L {mx - 6:.1f} 95 Z", fill=MILESTONE, **{"class": "r-ms-mark"}))
            p.append(path(f"M {mx:.1f} 102 V {bottom:.1f}", stroke=MILESTONE,
                          stroke_dasharray="2 4", opacity="0.5", fill="none",
                          **{"class": "grid-ms"}))
            p.append(text(tx, 99, label, text_anchor=anchor, **{"class": "r-ms"}))

        for tick in _ticks(start, end):
            tx = x_for(tick)
            p.append(path(f"M {tx:.1f} {HEADER_H - 14} V {bottom:.1f}", stroke="#e1e5e9",
                          fill="none", **{"class": "grid-axis"}))
            p.append(text(tx, HEADER_H - 22, tick.strftime("%b %d"),
                          text_anchor="middle", **{"class": "r-axis"}))

        for item in placed.values():
            for dependency in item["depends_on"]:
                source = placed.get(dependency)
                if source is None or source is item:
                    continue
                sx, sy = x_for(source["end"], edge=True), source["y"] + BAR_H / 2
                tx2, ty = x_for(item["start"]), item["y"] + BAR_H / 2
                if tx2 >= sx + 14:
                    mid = tx2 - 7
                    d = f"M {sx:.1f} {sy:.1f} H {mid:.1f} V {ty:.1f} H {tx2 - 4:.1f}"
                else:
                    # Target starts before its source finishes: route through the
                    # gap above the target row rather than drawing backwards.
                    vy = ty - SUBROW_H / 2 if ty > sy else ty + SUBROW_H / 2
                    d = (f"M {sx:.1f} {sy:.1f} H {sx + 10:.1f} V {vy:.1f} "
                         f"H {tx2 - 12:.1f} V {ty:.1f} H {tx2 - 4:.1f}")
                p.append(path(d, **{"class": "r-dep"}))
                p.append(path(f"M {tx2:.1f} {ty:.1f} l -5 -3.4 v 6.8 Z", fill="#9aa4ad",
                              **{"class": "r-dep-head"}))

        for index, (track, rows, top, height) in enumerate(layout):
            if index % 2 == 0:
                p.append(rect(MARGIN, top, WIDTH - 2 * MARGIN, height, rx=8,
                              fill="#f4f2ec", **{"class": "grid-lane"}))
            p.append(text(MARGIN + 12, top + height / 2 + 4,
                          str(track.get("label") or track.get("id") or ""),
                          **{"class": "r-trk"}))
            for row in rows:
                for item in row:
                    bx = x_for(item["start"])
                    bw = max(MIN_BAR_W, x_for(item["end"], edge=True) - bx)
                    colour = STATUS_COLORS.get(item["status"], STATUS_COLORS["planned"])
                    p.append(rect(bx, item["y"], bw, BAR_H, rx=6, fill=colour,
                                  **{"class": "r-bar"}))
                    caption, ty = item["title"], item["y"] + BAR_H / 2 + 4
                    if text_width(caption, 11.5, bold=True) + 16 <= bw:
                        p.append(text(bx + 8, ty, caption, **{"class": "r-bar-text-in"}))
                    elif bx + bw + 8 + text_width(caption, 11.5, bold=True) <= WIDTH - MARGIN:
                        p.append(text(bx + bw + 8, ty, caption, **{"class": "r-bar-text"}))
                    else:
                        p.append(text(bx - 8, ty, caption, text_anchor="end",
                                      **{"class": "r-bar-text"}))
            p.append(path(f"M {MARGIN} {top + height:.1f} H {WIDTH - MARGIN}",
                          stroke="#e1e5e9", fill="none", **{"class": "grid-rule"}))

        used = [s for s in STATUS_ORDER
                if any(i["status"] == s for v in by_track.values() for i in v)]
        lx, ly = float(MARGIN), bottom + 26
        for status in used:
            p.append(rect(lx, ly - 9, 11, 11, rx=3, fill=STATUS_COLORS[status],
                          **{"class": "legend-swatch"}))
            p.append(text(lx + 17, ly, status, **{"class": "r-axis"}))
            lx += 30 + text_width(status, 11)
        if params.get("milestones"):
            p.append(path(f"M {lx + 5:.1f} {ly - 9:.1f} l 5 5 l -5 5 l -5 -5 Z",
                          fill=MILESTONE, **{"class": "legend-ms"}))
            p.append(text(lx + 17, ly, "milestone", **{"class": "r-axis"}))

        return svg_document("".join(p), width=WIDTH, height=height_total,
                            class_name="diagram roadmap")
