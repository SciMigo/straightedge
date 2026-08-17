"""Cyclic-process diagram (循环图) — a closed loop of steps.

For processes that *return to their start*: 会计循环 (填制凭证 → 登记账簿 → 试算平衡
→ 编制报表 → …回到凭证), 资金运动 (供应 → 生产 → 销售 → 供应), the cash-conversion
cycle. A :mod:`flow_diagram` draws an open left-to-right chain; this draws the
same steps arranged around a ring with clockwise arrows, which reads as "this
repeats" at a glance — a distinction teachers care about.

image_hint usage::

    {"type": "cycle_diagram", "params": {
        "title": "会计循环",
        "center": "会计\\n循环",
        "steps": [
            {"label": "填制凭证"}, {"label": "登记账簿"},
            {"label": "试算平衡"}, {"label": "编制报表"}]}}

``steps`` accepts the same aliases as :mod:`flow_diagram` (``label`` / ``name`` /
``text`` / ``term``, bare string = label-only). ``center`` (optional) labels the
hub; ``\\n`` forces a line break in it.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List

from ..registry import register
from ..renderer import circle, group, path, rect, style, svg_document, text

MARGIN = 28
TITLE_H = 34
NODE_W = 118
NODE_H = 48
RING_PAD = 30         # extra space so nodes don't touch the edge
DEFAULT_ACCENT = "#2f7d72"


def _normalize_steps(raw: Any) -> List[str]:
    if not isinstance(raw, list):
        return []
    out: List[str] = []
    for item in raw:
        if isinstance(item, str):
            label = item.strip()
        elif isinstance(item, dict):
            label = str(item.get("label") or item.get("name") or item.get("text")
                        or item.get("term") or "").strip()
        else:
            continue
        if label:
            out.append(label)
    return out


def _clip(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


@register("cycle_diagram")
class CycleDiagramTemplate:
    def render(self, params: Dict[str, Any]) -> str:
        params = params or {}
        steps = _normalize_steps(params.get("steps") or params.get("nodes")
                                 or params.get("items"))
        if len(steps) < 2:
            return svg_document("", width=200, height=80,
                                class_name="diagram cycle-diagram")

        accent = str(params.get("accent") or params.get("color")
                     or DEFAULT_ACCENT).strip() or DEFAULT_ACCENT
        title = str(params.get("title") or "").strip()
        center_label = str(params.get("center") or params.get("hub") or "").strip()

        n = len(steps)
        # Ring radius scales with node count so labels never overlap.
        radius = max(120, int(20 * n / math.pi + 70))
        top0 = MARGIN + (TITLE_H if title else 0)
        cx = MARGIN + radius + RING_PAD
        cy = top0 + radius + RING_PAD
        width = cx + radius + RING_PAD + MARGIN
        height = cy + radius + RING_PAD + MARGIN

        parts: List[str] = [style(self._css(accent)),
                            f'<defs>{self._marker(accent)}</defs>']
        if title:
            parts.append(text(width / 2, MARGIN + 18, title,
                              **{"class": "cy-title", "text-anchor": "middle"}))

        # node centers, clockwise from top (−90°)
        pts: List[Dict[str, float]] = []
        for i in range(n):
            ang = -math.pi / 2 + 2 * math.pi * i / n
            pts.append({"x": cx + radius * math.cos(ang),
                        "y": cy + radius * math.sin(ang), "ang": ang})

        # arc arrows between consecutive nodes (drawn under the nodes)
        for i in range(n):
            parts.append(self._arc(pts[i], pts[(i + 1) % n], cx, cy, radius))

        # optional hub
        if center_label:
            parts.append(circle(cx, cy, 46, **{"class": "cy-hub"}))
            lines = center_label.split("\\n") or [center_label]
            ly = cy - (len(lines) - 1) * 10 + 5
            for ln in lines:
                parts.append(text(cx, ly, _clip(ln, 6),
                                  **{"class": "cy-hub-label", "text-anchor": "middle"}))
                ly += 20

        # nodes
        for i, p in enumerate(pts):
            parts.append(self._node(steps[i], p["x"], p["y"], i + 1))

        return svg_document("\n".join(parts), width=width, height=height,
                            class_name="diagram cycle-diagram")

    def _node(self, label: str, x: float, y: float, num: int) -> str:
        rx0 = x - NODE_W / 2
        ry0 = y - NODE_H / 2
        return group(
            rect(rx0, ry0, NODE_W, NODE_H, rx=10, **{"class": "cy-node"})
            + rect(rx0, ry0, NODE_W, 5, rx=2, **{"class": "cy-bar"})
            + text(x, y + 6, _clip(label, 7),
                   **{"class": "cy-label", "text-anchor": "middle"})
        )

    def _arc(self, a: Dict[str, float], b: Dict[str, float],
             cx: float, cy: float, radius: float) -> str:
        # arc along a slightly larger ring so it sits outside the nodes
        r = radius + NODE_H / 2 + 8
        ax = cx + r * math.cos(a["ang"] + 0.28)
        ay = cy + r * math.sin(a["ang"] + 0.28)
        bx = cx + r * math.cos(b["ang"] - 0.28)
        by = cy + r * math.sin(b["ang"] - 0.28)
        return path(f"M{ax:.1f},{ay:.1f} A{r:.1f},{r:.1f} 0 0 1 {bx:.1f},{by:.1f}",
                    **{"class": "cy-edge", "marker-end": "url(#cy-arrow)"})

    def _marker(self, accent: str) -> str:
        return (f'<marker id="cy-arrow" markerWidth="9" markerHeight="9" '
                f'refX="6" refY="3" orient="auto" markerUnits="userSpaceOnUse">'
                f'<path d="M0,0 L7,3 L0,6 Z" fill="{accent}"/></marker>')

    def _css(self, accent: str) -> str:
        return f"""
.cy-title{{font:600 19px 'Noto Sans SC',sans-serif;fill:#0f172a}}
.cy-node{{fill:#ffffff;stroke:#d8dee6;stroke-width:1.4}}
.cy-bar{{fill:{accent}}}
.cy-label{{font:600 15px 'Noto Sans SC',sans-serif;fill:#1f2937}}
.cy-edge{{stroke:{accent};stroke-width:2;fill:none}}
.cy-hub{{fill:{accent};opacity:.12;stroke:{accent};stroke-width:1.4}}
.cy-hub-label{{font:600 15px 'Noto Sans SC',sans-serif;fill:{accent}}}
"""
