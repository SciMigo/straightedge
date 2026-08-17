"""General-purpose process / block-flow diagram (流程图 / 框图).

The everyday teaching visual for a *sequence*: ordered steps drawn as boxes
connected by arrows — "会计循环：填制凭证 → 登记账簿 → 对账结账 → 编制报表",
"项目投资运作流程", "资金运动过程". Teachers reach for this constantly, and the
diagram registry had hierarchies (:mod:`structure_chart`, :mod:`wbs`) and layered
system diagrams (:mod:`architecture_diagram`) but no clean linear flow.

Horizontal by default, snake-wrapping to a new row when there are many steps so
labels stay large; ``orientation: "vertical"`` stacks top-to-bottom instead.

image_hint usage::

    {"type": "flow_diagram", "params": {
        "title": "会计核算流程",
        "steps": [
            {"label": "填制凭证", "desc": "审核原始凭证"},
            {"label": "登记账簿"},
            {"label": "对账结账"},
            {"label": "编制报表"}]}}

``steps`` accepts aliases: each item may use ``label`` / ``name`` / ``text`` /
``term`` for the box title and ``desc`` / ``description`` / ``detail`` for the
line under it; a bare string is a label-only box.
"""
from __future__ import annotations

from typing import Any, Dict, List

from ..registry import register
from ..renderer import group, path, rect, style, svg_document, text, wrap_units

MARGIN = 24
TITLE_H = 34
BOX_W = 166
BOX_H = 60          # minimum box height; grown to fit content (see render)
H_GAP = 46          # horizontal arrow gap between boxes
V_GAP = 40          # vertical arrow gap between rows / stacked boxes
LABEL_LH = 22
DESC_LH = 17
BOX_PAD = 10        # vertical padding inside a box
LABEL_MAX_LINES = 2
DESC_MAX_LINES = 3
DESC_WRAP = 12
ACCENT_BAR = 6
DEFAULT_ACCENT = "#2f7d72"
MAX_COLS = 4        # boxes per row before snake-wrapping (horizontal mode)
TITLE_FONT_PX = 19  # keep in sync with .fd-title in _css()


def _text_width(s: str, font_px: float) -> float:
    """Approximate rendered width of ``s``, counting CJK as full-width.

    Used to size the canvas so a title is never clipped. Latin glyphs in a
    semi-bold sans average a little over half an em; CJK is square.
    """
    if not s:
        return 0.0
    return sum(font_px if ord(ch) > 0x2E7F else font_px * 0.56 for ch in s)


def _normalize_steps(raw: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out: List[Dict[str, Any]] = []
    for item in raw:
        if isinstance(item, str):
            label, desc = item.strip(), ""
        elif isinstance(item, dict):
            label = str(item.get("label") or item.get("name") or item.get("text")
                        or item.get("term") or "").strip()
            desc = str(item.get("desc") or item.get("description")
                       or item.get("detail") or "").strip()
        else:
            continue
        if label:
            out.append({"label": label, "desc": desc})
    return out


def _wrap(s: str, max_chars: int, max_lines: int = 2) -> List[str]:
    """Wrap a step label; see ``renderer.wrap_units`` for the algorithm."""
    return wrap_units(s, max_chars, max_lines=max_lines)


def _arrow_marker(accent: str) -> str:
    return (f'<marker id="flow-arrow" markerWidth="9" markerHeight="9" '
            f'refX="7" refY="3" orient="auto" markerUnits="userSpaceOnUse">'
            f'<path d="M0,0 L7,3 L0,6 Z" fill="{accent}"/></marker>')


@register("flow_diagram")
class FlowDiagramTemplate:
    def render(self, params: Dict[str, Any]) -> str:
        params = params or {}
        steps = _normalize_steps(params.get("steps") or params.get("nodes")
                                 or params.get("items"))
        if not steps:
            return svg_document("", width=200, height=80,
                                class_name="diagram flow-diagram")

        accent = (str(params.get("accent") or params.get("color")
                      or DEFAULT_ACCENT).strip() or DEFAULT_ACCENT)
        title = str(params.get("title") or "").strip()
        orientation = str(params.get("orientation") or "horizontal").strip().lower()
        vertical = orientation.startswith("v")

        n = len(steps)
        cols = 1 if vertical else min(n, MAX_COLS)
        rows = -(-n // cols)  # ceil

        # Pre-wrap each box's text and size ONE uniform box height to the tallest
        # box's content, so a long label+description never overflows a fixed box.
        wrapped = [(_wrap(s["label"], 8, LABEL_MAX_LINES),
                    _wrap(s["desc"], DESC_WRAP, DESC_MAX_LINES) if s["desc"] else [])
                   for s in steps]
        box_h = max(
            [BOX_H] + [ACCENT_BAR + len(ll) * LABEL_LH + len(dl) * DESC_LH + 2 * BOX_PAD
                       for ll, dl in wrapped])

        # Canvas must fit the widest of {box grid, title}. A vertical flow is
        # only one box wide (214px), so a normal-length title used to overflow
        # the viewBox and render visibly clipped ("w the heat actually happ").
        grid_w = cols * BOX_W + (cols - 1) * H_GAP
        width = MARGIN * 2 + max(grid_w, _text_width(title, TITLE_FONT_PX))

        # Box positions in a snake (boustrophedon) layout, centred when the
        # title (not the grid) is what set the canvas width.
        top0 = MARGIN + (TITLE_H if title else 0)
        x0 = (width - grid_w) / 2
        positions: List[Dict[str, float]] = []
        for i in range(n):
            r = i // cols
            c_in_row = i % cols
            # snake: even rows L→R, odd rows R→L
            c = c_in_row if r % 2 == 0 else (cols - 1 - c_in_row)
            x = x0 + c * (BOX_W + H_GAP)
            y = top0 + r * (box_h + V_GAP)
            positions.append({"x": x, "y": y, "row": r, "col": c})

        height = top0 + rows * box_h + (rows - 1) * V_GAP + MARGIN

        parts: List[str] = [style(self._css(accent)),
                            f'<defs>{_arrow_marker(accent)}</defs>']
        if title:
            parts.append(text(width / 2, MARGIN + 18, title,
                              **{"class": "fd-title", "text-anchor": "middle"}))

        # Connectors first (under the boxes).
        for i in range(n - 1):
            parts.append(self._connector(positions[i], positions[i + 1], box_h))

        # Boxes.
        for (ll, dl), pos in zip(wrapped, positions):
            parts.append(self._box(ll, dl, pos["x"], pos["y"], box_h))

        return svg_document("\n".join(parts), width=width, height=height,
                            class_name="diagram flow-diagram")

    # -- pieces ----------------------------------------------------------

    def _box(self, label_lines: List[str], desc_lines: List[str],
             x: float, y: float, box_h: float) -> str:
        inner: List[str] = [
            rect(x, y, BOX_W, box_h, rx=8, **{"class": "fd-box"}),
            rect(x, y, BOX_W, ACCENT_BAR, rx=3, **{"class": "fd-bar"}),
        ]
        block_h = len(label_lines) * LABEL_LH + len(desc_lines) * DESC_LH
        ty = y + ACCENT_BAR + (box_h - ACCENT_BAR - block_h) / 2 + LABEL_LH - 6
        for ln in label_lines:
            inner.append(text(x + BOX_W / 2, ty, ln,
                              **{"class": "fd-label", "text-anchor": "middle"}))
            ty += LABEL_LH
        for ln in desc_lines:
            inner.append(text(x + BOX_W / 2, ty, ln,
                              **{"class": "fd-desc", "text-anchor": "middle"}))
            ty += DESC_LH
        return group("\n".join(inner))

    def _connector(self, a: Dict[str, float], b: Dict[str, float],
                   box_h: float) -> str:
        # Same row → horizontal arrow between the facing edges.
        if a["row"] == b["row"]:
            if b["x"] > a["x"]:  # L→R
                x1, x2 = a["x"] + BOX_W, b["x"]
            else:                # R→L (snake)
                x1, x2 = a["x"], b["x"] + BOX_W
            ym = a["y"] + box_h / 2
            return path(f"M{x1},{ym} L{x2},{ym}", **{
                "class": "fd-edge", "marker-end": "url(#flow-arrow)"})
        # Row turn → drop straight down from the box that ends the row.
        xm = a["x"] + BOX_W / 2
        y1, y2 = a["y"] + box_h, b["y"]
        return path(f"M{xm},{y1} L{xm},{y2}", **{
            "class": "fd-edge", "marker-end": "url(#flow-arrow)"})

    def _css(self, accent: str) -> str:
        return f"""
.fd-title{{font:600 19px 'Noto Sans SC',sans-serif;fill:#0f172a}}
.fd-box{{fill:#ffffff;stroke:#d8dee6;stroke-width:1.4}}
.fd-bar{{fill:{accent}}}
.fd-label{{font:600 16px 'Noto Sans SC',sans-serif;fill:#1f2937}}
.fd-desc{{font:13px 'Noto Sans SC',sans-serif;fill:#5b6573}}
.fd-edge{{stroke:{accent};stroke-width:2;fill:none}}
"""
