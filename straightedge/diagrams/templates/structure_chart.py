"""General-purpose structure / concept chart (结构图 / 思维导图 / 知识结构).

The everyday teaching visual: a single concept at the top branching into N
labelled aspects — "项目融资的四个特点", "细胞的三种结构", "议论文的三要素".
Basic-education and lecture audiences strongly prefer this over a flat bullet
list (a recurring request from teachers). Pure structural layout — crisp and
correct at any size.

Unlike :mod:`wbs` (project Work-Breakdown framing, 10-char labels), each branch
here is a CARD that holds a bold **term** plus an optional one-line description
and a few short sub-points, so it can carry real explanatory content.

image_hint usage::

    {"type": "structure_chart", "params": {
        "title": "项目融资的四个特点",
        "root": "项目融资",
        "children": [
            {"term": "有限追索", "desc": "贷款人主要依赖项目自身现金流偿债"},
            {"term": "风险分担", "desc": "参与各方按能力分担项目风险"},
            {"term": "表外融资", "desc": "不增加发起人资产负债表负债"},
            {"term": "结构复杂", "desc": "涉及多方合同与担保安排"}]}}}

``children`` accepts aliases: each item may use ``term`` / ``name`` / ``label`` /
``text`` for the title, ``desc`` / ``description`` / ``detail`` for the line, and
``points`` / ``subitems`` for short sub-bullets. A bare string child is treated
as a term-only card.
"""
from __future__ import annotations

from typing import Any, Dict, List

from ..registry import register
from ..renderer import rect, style, svg_document, text

MARGIN = 24
TITLE_H = 34
ROOT_W = 188
ROOT_H = 50
GAP_BELOW_ROOT = 52      # vertical space between root and the cards row
CARD_W = 196
CARD_GAP = 26
CARD_PAD = 14
TERM_LH = 23             # line height for the term
DESC_LH = 19             # line height for description / points
ACCENT_BAR = 6           # coloured top strip on each card

DEFAULT_ACCENT = "#2f7d72"   # science teal


def _css(accent: str) -> str:
    """Build the diagram stylesheet around a single accent color.

    Only the root node fill/stroke and each card's top accent bar are themed;
    text and card borders stay neutral so any accent reads cleanly.
    """
    return f"""
.sc-title{{font:600 19px 'Noto Sans SC',sans-serif;fill:#0f172a}}
.sc-root{{fill:{accent};stroke:{accent}}}
.sc-root-label{{font:600 17px 'Noto Sans SC',sans-serif;fill:#ffffff}}
.sc-card{{fill:#ffffff;stroke:#d8dee6;stroke-width:1.3}}
.sc-bar{{fill:{accent}}}
.sc-term{{font:600 16px 'Noto Sans SC',sans-serif;fill:#1f2937}}
.sc-desc{{font:13px 'Noto Sans SC',sans-serif;fill:#5b6573}}
.sc-point{{font:13px 'Noto Sans SC',sans-serif;fill:#5b6573}}
.sc-edge{{stroke:#94a3b8;stroke-width:1.4;fill:none}}
"""


def _wrap(s: str, max_chars: int) -> List[str]:
    """Wrap text to lines of at most ``max_chars`` display units.

    Latin text (contains spaces) wraps on word boundaries; CJK text wraps by
    character count. Empty input yields no lines.
    """
    s = str(s or "").strip()
    if not s:
        return []
    if " " in s:  # Latin-ish: wrap on words
        lines: List[str] = []
        cur = ""
        for word in s.split():
            cand = (cur + " " + word).strip()
            if len(cand) > max_chars and cur:
                lines.append(cur)
                cur = word
            else:
                cur = cand
        if cur:
            lines.append(cur)
        return lines
    # CJK: hard wrap by character count
    return [s[i:i + max_chars] for i in range(0, len(s), max_chars)] or [s]


def _normalize_children(raw: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        if isinstance(item, str):
            out.append({"term": item.strip(), "desc": "", "points": []})
            continue
        if not isinstance(item, dict):
            continue
        term = str(item.get("term") or item.get("name") or item.get("label")
                   or item.get("text") or "").strip()
        desc = str(item.get("desc") or item.get("description")
                   or item.get("detail") or "").strip()
        pts_raw = item.get("points") or item.get("subitems") or []
        points = [str(p).strip() for p in pts_raw if str(p).strip()] \
            if isinstance(pts_raw, list) else []
        if term or desc or points:
            out.append({"term": term, "desc": desc, "points": points})
    return out


@register("structure_chart")
class StructureChartTemplate:
    def render(self, params: Dict[str, Any]) -> str:
        params = params or {}
        children = _normalize_children(params.get("children") or params.get("nodes"))
        if not children:
            return svg_document("", width=200, height=80,
                                class_name="diagram structure-chart")

        accent = str(params.get("accent") or params.get("color")
                     or DEFAULT_ACCENT).strip() or DEFAULT_ACCENT
        root_label = str(params.get("root") or params.get("center")
                         or params.get("title") or "").strip()
        title = str(params.get("title") or "").strip()
        # Avoid showing the same text as both title and root.
        if title and title == root_label:
            title = ""

        term_cols = max(4, (CARD_W - 2 * CARD_PAD) // 16)
        body_cols = max(6, (CARD_W - 2 * CARD_PAD) // 13)

        # Pre-wrap each card and compute a shared card height (aligned bottoms).
        cards: List[Dict[str, Any]] = []
        max_body_h = 0
        for ch in children:
            term_lines = _wrap(ch["term"], term_cols)
            desc_lines = _wrap(ch["desc"], body_cols)
            point_lines: List[str] = []
            for p in ch["points"]:
                point_lines.extend(_wrap("· " + p, body_cols))
            body_h = (len(term_lines) * TERM_LH
                      + (len(desc_lines) + len(point_lines)) * DESC_LH)
            max_body_h = max(max_body_h, body_h)
            cards.append({"term_lines": term_lines, "desc_lines": desc_lines,
                          "point_lines": point_lines})
        card_h = ACCENT_BAR + CARD_PAD + max_body_h + CARD_PAD

        n = len(children)
        title_block = TITLE_H if title else 0
        width = int(MARGIN * 2 + n * CARD_W + (n - 1) * CARD_GAP)
        row_top = MARGIN + title_block + ROOT_H + GAP_BELOW_ROOT
        height = int(row_top + card_h + MARGIN)

        parts: List[str] = ['<defs>' + style(_css(accent)) + '</defs>']
        if title:
            parts.append(text(MARGIN, MARGIN + 17, title, **{"class": "sc-title"}))

        # Root node, centred over the cards row.
        root_cx = width / 2
        root_y = MARGIN + title_block
        parts.append(rect(root_cx - ROOT_W / 2, root_y, ROOT_W, ROOT_H, rx=8,
                          **{"class": "sc-root"}))
        for k, ln in enumerate(_wrap(root_label, 12)[:2]):
            parts.append(text(root_cx, root_y + ROOT_H / 2 + 6
                              - (len(_wrap(root_label, 12)[:2]) - 1) * 10 + k * 20,
                              ln, text_anchor="middle",
                              **{"class": "sc-root-label"}))

        # Cards + connectors.
        for idx, card in enumerate(cards):
            cx = MARGIN + idx * (CARD_W + CARD_GAP) + CARD_W / 2
            # elbow connector: root bottom -> mid -> card top
            midy = (root_y + ROOT_H + row_top) / 2
            parts.append(
                f'<path d="M{root_cx},{root_y + ROOT_H} V{midy} H{cx} V{row_top}" '
                f'class="sc-edge"/>'
            )
            parts.append(rect(cx - CARD_W / 2, row_top, CARD_W, card_h, rx=10,
                              **{"class": "sc-card"}))
            parts.append(rect(cx - CARD_W / 2, row_top, CARD_W, ACCENT_BAR,
                              rx=0, **{"class": "sc-bar"}))
            ty = row_top + ACCENT_BAR + CARD_PAD + 16
            for ln in card["term_lines"]:
                parts.append(text(cx, ty, ln, text_anchor="middle",
                                  **{"class": "sc-term"}))
                ty += TERM_LH
            for ln in card["desc_lines"]:
                parts.append(text(cx, ty, ln, text_anchor="middle",
                                  **{"class": "sc-desc"}))
                ty += DESC_LH
            for ln in card["point_lines"]:
                parts.append(text(cx - CARD_W / 2 + CARD_PAD, ty, ln,
                                  **{"class": "sc-point"}))
                ty += DESC_LH

        return svg_document("".join(parts), width=width, height=height,
                            class_name="diagram structure-chart")
