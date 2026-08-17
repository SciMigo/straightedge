"""Work Breakdown Structure (工作分解结构 / WBS) tree diagram.

A top-down tree of labelled boxes — the standard way a project is decomposed
into deliverables and work packages. Pure structural layout (subtree-width
packing), so it is crisp and correct at any size.

image_hint usage::

    {"type": "wbs", "params": {"title": "项目工作分解结构", "root": {
        "name": "建设项目", "children": [
            {"name": "设计", "children": [{"name": "方案设计"}, {"name": "施工图"}]},
            {"name": "施工", "children": [{"name": "基础"}, {"name": "主体"}]},
            {"name": "验收"}]}}}

A flat ``nodes`` list (``{"id","name","parent"}``) is also accepted and folded
into a tree.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..registry import register
from ..renderer import rect, style, svg_document, text

BOX_W = 132
BOX_H = 46
HGAP = 22
VGAP = 64
MARGIN = 24
TITLE_H = 36

_CSS = """
.wbs-box{fill:#eef2f7;stroke:#94a3b8;stroke-width:1.4}
.wbs-box.root{fill:#2f7d72;stroke:#2f7d72}
.wbs-label{font:14px 'Noto Sans SC',sans-serif;fill:#1f2937}
.wbs-label.root{fill:#ffffff;font-weight:600}
.wbs-edge{stroke:#94a3b8;stroke-width:1.4;fill:none}
.wbs-title{font:600 18px 'Noto Sans SC',sans-serif;fill:#0f172a}
"""


def _tree_from_flat(nodes: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    by_id: Dict[str, Dict[str, Any]] = {}
    for n in nodes:
        nid = str(n.get("id") or n.get("name") or "").strip()
        if nid:
            by_id[nid] = {"name": str(n.get("name") or nid), "children": [], "_parent": n.get("parent")}
    root = None
    for nid, node in by_id.items():
        parent = node.pop("_parent", None)
        if parent and str(parent) in by_id:
            by_id[str(parent)]["children"].append(node)
        else:
            root = root or node
    return root


@register("wbs")
class WbsTemplate:
    def render(self, params: Dict[str, Any]) -> str:
        params = params or {}
        root = params.get("root")
        if not root and params.get("nodes"):
            root = _tree_from_flat(params["nodes"])
        if not isinstance(root, dict):
            return svg_document("", width=200, height=80, class_name="diagram wbs")
        title = str(params.get("title") or "").strip()

        # Two-pass: first compute positions, then draw (so edges can connect).
        positions: Dict[int, tuple] = {}
        cursor = [0.0]
        max_depth = [0]

        def layout(node: Dict[str, Any], depth: int) -> float:
            max_depth[0] = max(max_depth[0], depth)
            children = [c for c in (node.get("children") or []) if isinstance(c, dict)]
            if not children:
                cx = MARGIN + cursor[0] * (BOX_W + HGAP) + BOX_W / 2
                cursor[0] += 1
            else:
                centers = [layout(c, depth + 1) for c in children]
                cx = (centers[0] + centers[-1]) / 2
            y = MARGIN + TITLE_H + depth * (BOX_H + VGAP)
            positions[id(node)] = (cx, y)
            return cx

        layout(root, 0)

        n_leaves = max(1, int(round(cursor[0])))
        width = int(MARGIN * 2 + n_leaves * BOX_W + (n_leaves - 1) * HGAP)
        height = int(MARGIN * 2 + TITLE_H + (max_depth[0] + 1) * BOX_H + max_depth[0] * VGAP)

        parts: List[str] = ['<defs>' + style(_CSS) + '</defs>']
        if title:
            parts.append(text(MARGIN, MARGIN + 16, title, **{"class": "wbs-title"}))

        def draw(node: Dict[str, Any], depth: int) -> None:
            cx, y = positions[id(node)]
            children = [c for c in (node.get("children") or []) if isinstance(c, dict)]
            for c in children:
                ccx, cy = positions[id(c)]
                midy = (y + BOX_H + cy) / 2
                parts.append(
                    f'<path d="M{cx},{y+BOX_H} V{midy} H{ccx} V{cy}" class="wbs-edge"/>'
                )
            is_root = depth == 0
            cls = "wbs-box root" if is_root else "wbs-box"
            lcls = "wbs-label root" if is_root else "wbs-label"
            parts.append(rect(cx - BOX_W / 2, y, BOX_W, BOX_H, rx=6, **{"class": cls}))
            parts.append(text(cx, y + BOX_H / 2 + 5, str(node.get("name") or "")[:10],
                              text_anchor="middle", **{"class": lcls}))
            for c in children:
                draw(c, depth + 1)

        draw(root, 0)
        return svg_document("".join(parts), width=width, height=height,
                            class_name="diagram wbs")
