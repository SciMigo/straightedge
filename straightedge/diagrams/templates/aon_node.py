"""Activity-on-Node (单代号) node-representation teaching diagram.

Draws the 单代号 work node. Two modes:

* simple (``annotated`` false / omitted) — the basic node box with three stacked
  cells: 工作代号 / 工作名称 / 持续时间 (图6.16).
* annotated (``annotated`` true) — the six-parameter标注 layout (图6.17): a left
  label column (代号 / 名称 / D) beside a 2×3 parameter grid::

      工作代号 | ES | EF
      工作名称 | TF | FF
        D     | LS | LF

  With two nodes, a ``lag`` arrow (时间间隔 LAG) is drawn between them.

Use for 单代号 concept slides; for a full computed schedule use ``project_network``.

image_hint usage::

    {"type": "aon_node", "params": {
        "title": "单代号：时间参数的标注",
        "annotated": true, "lag": "LAG(i,j)",
        "nodes": [
          {"code": "i", "name": "工作 i", "duration": "Dᵢ",
           "es": "ESᵢ", "ef": "EFᵢ", "ls": "LSᵢ", "lf": "LFᵢ", "tf": "TFᵢ", "ff": "FFᵢ"},
          {"code": "j", "name": "工作 j", "duration": "Dⱼ",
           "es": "ESⱼ", "ef": "EFⱼ", "ls": "LSⱼ", "lf": "LFⱼ", "tf": "TFⱼ", "ff": "FFⱼ"}]}}
"""
from __future__ import annotations

from typing import Any, Dict, List

from ..registry import register
from ..renderer import defs, line, rect, style, svg_document, text

MARGIN = 30
TITLE_H = 36
SIMPLE_W, BOX_H = 132, 99
LABEL_W, PCOL = 88, 64           # annotated: label column + each param column
ANNOT_W = LABEL_W + 2 * PCOL     # 88 + 128 = 216
GAP = 96                          # horizontal gap between two nodes (for LAG arrow)

_CSS = """
.aon-box{stroke:#475569;stroke-width:2;fill:#ffffff}
.aon-cell{stroke:#cbd5e1;stroke-width:1;fill:none}
.aon-code{font:700 18px 'Noto Sans SC',sans-serif;fill:#1f2937}
.aon-name{font:14px 'Noto Sans SC',sans-serif;fill:#334155}
.aon-dur{font:14px 'Noto Sans SC',sans-serif;fill:#2563eb}
.aon-val{font:13px 'Noto Sans SC',sans-serif;fill:#475569}
.aon-hd{font:11px 'Noto Sans SC',sans-serif;fill:#94a3b8}
.aon-edge{stroke:#475569;stroke-width:2;fill:none}
.aon-lag{font:13px 'Noto Sans SC',sans-serif;fill:#b45309}
.aon-title{font:600 18px 'Noto Sans SC',sans-serif;fill:#0f172a}
"""

_ARROW = (
    '<marker id="aon-tip" markerWidth="10" markerHeight="10" refX="8" refY="4.5" '
    'orient="auto"><path d="M0,0 L9,4.5 L0,9 Z" fill="#475569"/></marker>'
)


def _c(cx: float, cy: float, s: str, cls: str) -> str:
    return text(cx, cy + 4, str(s), text_anchor="middle", **{"class": cls})


def _title_width(title: str, px: int = 18) -> float:
    """Rough pixel width of a CJK/ASCII title at the given font size."""
    w = 0.0
    for ch in title:
        w += px if ord(ch) > 0x2E80 else px * 0.55
    return w


def _simple_box(x: float, y: float, n: Dict[str, Any]) -> str:
    h3 = BOX_H / 3
    p = [rect(x, y, SIMPLE_W, BOX_H, rx=6, **{"class": "aon-box"})]
    p.append(line(x, y + h3, x + SIMPLE_W, y + h3, **{"class": "aon-cell"}))
    p.append(line(x, y + 2 * h3, x + SIMPLE_W, y + 2 * h3, **{"class": "aon-cell"}))
    cx = x + SIMPLE_W / 2
    p.append(_c(cx, y + h3 / 2, n.get("code", ""), "aon-code"))
    p.append(_c(cx, y + h3 + h3 / 2, n.get("name", ""), "aon-name"))
    p.append(_c(cx, y + 2 * h3 + h3 / 2, n.get("duration", ""), "aon-dur"))
    return "".join(p)


def _annot_box(x: float, y: float, n: Dict[str, Any]) -> str:
    h3 = BOX_H / 3
    p = [rect(x, y, ANNOT_W, BOX_H, rx=6, **{"class": "aon-box"})]
    # internal grid
    p.append(line(x + LABEL_W, y, x + LABEL_W, y + BOX_H, **{"class": "aon-cell"}))
    p.append(line(x + LABEL_W + PCOL, y, x + LABEL_W + PCOL, y + BOX_H, **{"class": "aon-cell"}))
    for r in (1, 2):
        p.append(line(x, y + r * h3, x + ANNOT_W, y + r * h3, **{"class": "aon-cell"}))
    lx = x + LABEL_W / 2
    p.append(_c(lx, y + h3 / 2, n.get("code", ""), "aon-code"))
    p.append(_c(lx, y + h3 + h3 / 2, n.get("name", ""), "aon-name"))
    p.append(_c(lx, y + 2 * h3 + h3 / 2, n.get("duration", ""), "aon-dur"))
    # right 2x3 params: ES EF / TF FF / LS LF
    grid = [("es", "ef"), ("tf", "ff"), ("ls", "lf")]
    hdr = [("ES", "EF"), ("TF", "FF"), ("LS", "LF")]
    for ri, ((ka, kb), (ha, hb)) in enumerate(zip(grid, hdr)):
        c1 = x + LABEL_W + PCOL / 2
        c2 = x + LABEL_W + PCOL + PCOL / 2
        ry = y + ri * h3
        p.append(text(c1, ry + 13, ha, text_anchor="middle", **{"class": "aon-hd"}))
        p.append(text(c2, ry + 13, hb, text_anchor="middle", **{"class": "aon-hd"}))
        p.append(_c(c1, ry + h3 / 2 + 8, n.get(ka, ""), "aon-val"))
        p.append(_c(c2, ry + h3 / 2 + 8, n.get(kb, ""), "aon-val"))
    return "".join(p)


@register("aon_node")
class AonNodeTemplate:
    def render(self, params: Dict[str, Any]) -> str:
        params = params or {}
        title = str(params.get("title") or "").strip()
        annotated = bool(params.get("annotated"))
        nodes = params.get("nodes") or []
        lag = str(params.get("lag") or "").strip()
        if not nodes:
            return svg_document("", width=200, height=80, class_name="diagram aon-node")

        bw = ANNOT_W if annotated else SIMPLE_W
        y = MARGIN + TITLE_H
        diagram_w = MARGIN * 2 + len(nodes) * bw + (len(nodes) - 1) * GAP
        title_w = (MARGIN * 2 + _title_width(title)) if title else 0
        width = int(max(diagram_w, title_w))
        height = int(y + BOX_H + MARGIN)

        parts: List[str] = [defs(_ARROW + style(_CSS))]
        if title:
            parts.append(text(MARGIN, MARGIN + 16, title, **{"class": "aon-title"}))

        xs: List[float] = []
        for i, n in enumerate(nodes):
            x = MARGIN + i * (bw + GAP)
            xs.append(x)
            parts.append(_annot_box(x, y, n) if annotated else _simple_box(x, y, n))

        # connecting arrows + LAG label between consecutive nodes
        for i in range(len(nodes) - 1):
            x1 = xs[i] + bw
            x2 = xs[i + 1]
            cy = y + BOX_H / 2
            parts.append(line(x1 + 4, cy, x2 - 6, cy, **{"class": "aon-edge",
                                                          "marker-end": "url(#aon-tip)"}))
            if lag:
                parts.append(text((x1 + x2) / 2, cy - 9, lag, text_anchor="middle",
                                  **{"class": "aon-lag"}))
        return svg_document("".join(parts), width=width, height=height,
                            class_name="diagram aon-node")
