"""Side-by-side comparison diagram (对比图).

For the "A vs B" contrasts that recur in every course — 权责发生制 vs 收付实现制,
借 vs 贷, 固定成本 vs 变动成本, 总账 vs 明细账. Two (or three) labelled columns,
each a card with a colored header and a short list of points, so the difference
is read at a glance instead of buried in prose.

image_hint usage::

    {"type": "comparison", "params": {
        "title": "两种会计确认基础",
        "columns": [
            {"label": "权责发生制",
             "points": ["以权责归属期确认收入费用", "更能反映经营成果", "企业会计准则采用"]},
            {"label": "收付实现制",
             "points": ["以款项收付确认", "核算简单", "多用于行政事业单位"]}]}}

``columns`` accepts aliases ``sides`` / ``items``; each column may use ``label`` /
``name`` / ``title`` for the header, ``points`` / ``items`` / ``subitems`` for the
list, and an optional ``desc`` shown under the header.
"""
from __future__ import annotations

from typing import Any, Dict, List

from ..registry import register
from ..renderer import group, rect, style, svg_document, text, wrap_units

MARGIN = 24
TITLE_H = 34
HEAD_H = 44
COL_W = 250
COL_GAP = 28
LINE_H = 26
PAD = 16
DESC_H = 24
DEFAULT_ACCENT = "#2f7d72"
# palette so adjacent columns are visually distinct
_PALETTE = ["#2f7d72", "#b45309", "#3b5bdb"]


def _wrap(s: str, max_units: float) -> List[str]:
    """Wrap a point onto at most three lines, on word boundaries for Latin."""
    return wrap_units(str(s or "").strip(), max_units, max_lines=3)


def _side_pair_columns(params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Accept the per-side shapes models reach for instead of ``columns``.

    Asked for an A-vs-B comparison, an LLM very often emits
    ``{"left_label": ..., "left_items": [...], "right_label": ..., ...}``
    instead of a ``columns`` list. That shape produced no columns at all, and
    the template answered with an empty 200x80 document — a blank white card on
    the slide, with nothing logged. Normalize it rather than lose the diagram.

    It just as often nests the side instead of prefixing it —
    ``{"left": {"label": ..., "items": [...]}}`` — which is what a live kepu
    short actually produced on two slides, each rendering blank while carrying
    perfectly good content. A bare string is treated as the label and a bare
    list as the points, since both appear too.
    """

    out: List[Dict[str, Any]] = []
    for side in ("left", "right", "middle", "center"):
        label = str(params.get(f"{side}_label") or "").strip()
        desc = str(params.get(f"{side}_desc") or "").strip()
        pts = params.get(f"{side}_items") or params.get(f"{side}_points") or []

        nested = params.get(side)
        if isinstance(nested, dict):
            label = label or str(
                nested.get("label") or nested.get("name") or nested.get("title") or ""
            ).strip()
            desc = desc or str(
                nested.get("desc") or nested.get("description") or ""
            ).strip()
            pts = pts or nested.get("items") or nested.get("points") \
                or nested.get("subitems") or []
        elif isinstance(nested, list):
            pts = pts or nested
        elif isinstance(nested, str) and nested.strip():
            label = label or nested.strip()

        points = [str(p).strip() for p in pts if str(p).strip()]
        if label or points:
            out.append({"label": label or "—", "desc": desc, "points": points})
    return out[:3]


def _normalize_columns(params: Dict[str, Any]) -> List[Dict[str, Any]]:
    cols = params.get("columns") or params.get("sides") or params.get("items")
    if not isinstance(cols, list):
        return _side_pair_columns(params)
    out: List[Dict[str, Any]] = []
    for c in cols:
        if not isinstance(c, dict):
            if isinstance(c, str) and c.strip():
                out.append({"label": c.strip(), "desc": "", "points": []})
            continue
        label = str(c.get("label") or c.get("name") or c.get("title") or "").strip()
        desc = str(c.get("desc") or c.get("description") or "").strip()
        pts = c.get("points") or c.get("items") or c.get("subitems") or []
        points = [str(p).strip() for p in pts if str(p).strip()]
        if label or points:
            out.append({"label": label or "—", "desc": desc, "points": points})
    return out[:3]


@register("comparison")
class ComparisonTemplate:
    def render(self, params: Dict[str, Any]) -> str:
        params = params or {}
        cols = _normalize_columns(params)
        if not cols:
            return svg_document("", width=200, height=80,
                                class_name="diagram comparison")

        title = str(params.get("title") or "").strip()
        top0 = MARGIN + (TITLE_H if title else 0)

        # each point wraps to <=2 lines; size the body to the tallest column
        wrapped: List[List[List[str]]] = []
        for c in cols:
            wrapped.append([_wrap(p, 15) for p in c["points"]])
        max_lines = max((sum(len(w) for w in col) for col in wrapped), default=1)
        has_desc = any(c["desc"] for c in cols)
        body_h = max_lines * LINE_H + PAD * 2 + (DESC_H if has_desc else 0)
        col_h = HEAD_H + body_h

        n = len(cols)
        width = MARGIN * 2 + n * COL_W + (n - 1) * COL_GAP
        height = top0 + col_h + MARGIN

        parts: List[str] = [style(self._css())]
        if title:
            parts.append(text(width / 2, MARGIN + 18, title,
                              **{"class": "cmp-title", "text-anchor": "middle"}))
        for i, (c, wp) in enumerate(zip(cols, wrapped)):
            x = MARGIN + i * (COL_W + COL_GAP)
            accent = _PALETTE[i % len(_PALETTE)]
            parts.append(self._column(c, wp, x, top0, col_h, accent, has_desc))
        return svg_document("\n".join(parts), width=width, height=height,
                            class_name="diagram comparison")

    def _column(self, c: Dict[str, Any], wrapped: List[List[str]], x: float,
                y: float, col_h: float, accent: str, has_desc: bool) -> str:
        inner: List[str] = [
            rect(x, y, COL_W, col_h, rx=12, **{"class": "cmp-card"}),
            rect(x, y, COL_W, HEAD_H, rx=12, fill=accent, **{"class": "cmp-head"}),
            # square off the header's bottom corners
            rect(x, y + HEAD_H - 12, COL_W, 12, fill=accent),
            text(x + COL_W / 2, y + 28, c["label"],
                 **{"class": "cmp-head-label", "text-anchor": "middle"}),
        ]
        ty = y + HEAD_H + PAD + 6
        if has_desc:
            if c["desc"]:
                inner.append(text(x + COL_W / 2, ty, c["desc"][:22],
                                  **{"class": "cmp-desc", "text-anchor": "middle"}))
            ty += DESC_H
        for lines in wrapped:
            first = True
            for ln in lines:
                bullet = "• " if first else "　"
                inner.append(text(x + PAD, ty, bullet + ln,
                                  **{"class": "cmp-point"}))
                ty += LINE_H
                first = False
        return group("\n".join(inner))

    def _css(self) -> str:
        return """
.cmp-title{font:600 19px 'Noto Sans SC',sans-serif;fill:#0f172a}
.cmp-card{fill:#ffffff;stroke:#e2e8f0;stroke-width:1.3}
.cmp-head-label{font:600 17px 'Noto Sans SC',sans-serif;fill:#ffffff}
.cmp-desc{font:13px 'Noto Sans SC',sans-serif;fill:#64748b}
.cmp-point{font:15px 'Noto Sans SC',sans-serif;fill:#1f2937}
"""
