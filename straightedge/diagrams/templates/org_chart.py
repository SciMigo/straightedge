"""Organisational chart (组织结构图) — reporting lines, in the shape orgs are read in.

Distinct from :mod:`wbs`, which packs a tree by subtree width. That is correct
for a work breakdown, whose leaves are few and short, and unusable for an
organisation, whose leaves are people: width there grows with the *leaf count*,
so a 157-person org renders 18,528px wide at a 51:1 aspect, and a 297-person one
37,008px at 102:1. Nothing can read that and nothing can print it.

The convention this follows instead is the one org charts have used since they
were drawn on paper: the level under the top sits in a horizontal row, and
everything below it stacks in a vertical, indented column under its manager. The
same 157 people come out 1,704x1,146 — about 1.5:1, and the aspect stays there as
the org grows, because depth adds rows rather than width.

Three things a work-breakdown tree has no way to say, all of them conventions
with settled meanings:

* a node is a **person and a role**, two fields, not one label;
* a **dotted line** is a real reporting relationship — secondary, matrix or
  temporary oversight — drawn dashed, and distinct from the solid line of
  primary authority;
* an **assistant** hangs off the side of the spine below the person it assists
  and above that person's own reports, which is neither a child nor a sibling.

image_hint usage::

    {"type": "org_chart", "params": {
        "title": "SciMigo engineering",
        "root": {"name": "Ada Lovelace", "title": "CEO", "children": [
            {"name": "Grace Hopper", "title": "VP Engineering", "children": [
                {"name": "Ken Thompson", "title": "Staff Engineer"},
                {"name": "", "title": "Senior Engineer", "status": "vacant"}]},
            {"name": "Radia Perlman", "title": "VP Infrastructure"}]},
        "assistants": [{"name": "Chief of Staff", "assists": "Ada Lovelace"}],
        "dotted": [{"from": "Ken Thompson", "to": "Radia Perlman",
                    "label": "security"}]}}

A flat ``people`` list is also accepted --- ``{"id", "name", "title",
"reports_to", "status"}`` --- and folded into the same tree, which is the shape
an HR export arrives in.

``status`` is one of ``filled`` (the default), ``vacant`` and ``interim``; only
``vacant`` and ``interim`` are drawn differently, and both are called out in the
legend rather than left to be guessed.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from ..registry import register
from ..renderer import fit_text, path, rect, style, svg_document, text, text_width

MAX_WIDTH = 1160
MARGIN = 28
HEADER_H = 62

#: A column is at least this wide and grows to fill the canvas. It used to be
#: the fixed width, which left a third of the page blank while five labels were
#: trimmed for want of the room sitting beside them — the layout was bounded by
#: a constant rather than by the space it actually had.
CARD_W = 206
#: …and no wider, so a single unit does not become one 1,100px-wide card.
CARD_W_MAX = 392
#: An assistant row needs room for a name and a role. The canvas is widened to
#: hold it rather than the row being squeezed into whatever is left: a chart with
#: one unit sized itself to the card alone, leaving 34px beside it, and "Chief of
#: Staff" came out as a bare ellipsis.
ASSISTANT_W = 260
CARD_H = 56          # a manager card: name over role
ROW_H = 36           # a stacked report row
COL_GAP = 22
BANK_GAP = 34        # between wrapped rows of columns
INDENT = 18
SPINE_DROP = 34      # root -> bus -> level-1 cards
STACK_TOP_GAP = 14

NAME_PX = 13.5
ROLE_PX = 11.5
TITLE_PX = 19

ACCENT = "#2f7d72"
INK = "#0f172a"
MUTED = "#64748b"
RULE = "#94a3b8"
VACANT = "#b45309"
DOTTED = "#7c6f9e"

_CSS = f"""
.oc-title{{font-size:{TITLE_PX}px;font-weight:600;fill:{INK}}}
.oc-card{{fill:#eef2f7;stroke:{RULE};stroke-width:1.4}}
.oc-card.root{{fill:{ACCENT};stroke:{ACCENT}}}
.oc-card.vacant{{fill:#fdf6ec;stroke:{VACANT};stroke-width:1.4;stroke-dasharray:5 3}}
.oc-row{{fill:#f8fafc;stroke:#cbd5e1;stroke-width:1}}
.oc-row.vacant{{fill:#fdf6ec;stroke:{VACANT};stroke-dasharray:5 3}}
.oc-row.interim{{fill:#f5f3fa;stroke:{DOTTED};stroke-dasharray:2 3}}
.oc-card.interim{{fill:#f5f3fa;stroke:{DOTTED};stroke-width:1.4;stroke-dasharray:2 3}}
.oc-name{{font-size:{NAME_PX}px;font-weight:600;fill:{INK}}}
.oc-name.root{{fill:#ffffff}}
.oc-role{{font-size:{ROLE_PX}px;fill:{MUTED}}}
.oc-role.root{{fill:#d7ece7}}
.oc-role.vacant{{fill:{VACANT};font-style:italic}}
.oc-edge{{stroke:{RULE};stroke-width:1.4;fill:none}}
.oc-dotted{{stroke:{DOTTED};stroke-width:1.4;fill:none;stroke-dasharray:4 3}}
.oc-dotted-label{{font-size:10.5px;fill:{DOTTED}}}
.oc-legend{{font-size:11px;fill:{MUTED}}}
text{{font-family:'Noto Sans SC',Helvetica,Arial,sans-serif}}
"""

_NAME_KEYS = ("name", "label", "person", "who")
_ROLE_KEYS = ("title", "role", "position", "job")
_VACANT = {"vacant", "open", "tbh", "to be hired", "unfilled"}
_INTERIM = {"interim", "acting", "temporary", "temp"}


def _field(item: Dict[str, Any], keys: Tuple[str, ...]) -> str:
    for k in keys:
        v = item.get(k)
        if v:
            return str(v).strip()
    return ""


def _status(raw: Any) -> str:
    s = str(raw or "").strip().lower()
    if s in _VACANT:
        return "vacant"
    if s in _INTERIM:
        return "interim"
    return "filled"


def _node(raw: Any) -> Optional[Dict[str, Any]]:
    """Normalise one person into ``{name, role, status, children}``."""
    if isinstance(raw, str):
        raw = {"name": raw}
    if not isinstance(raw, dict):
        return None
    name = _field(raw, _NAME_KEYS)
    role = _field(raw, _ROLE_KEYS)
    status = _status(raw.get("status"))
    if not name and not role:
        return None
    if not name:
        # A vacancy is a role with nobody in it; say so rather than draw a blank.
        name = "Vacant" if status == "vacant" else role
        if status == "filled":
            role = ""
        elif name == "Vacant":
            status = "vacant"
    kids = raw.get("children") or raw.get("reports") or raw.get("directs") or []
    children = [n for n in (_node(k) for k in kids) if n] if isinstance(kids, list) else []
    return {"name": name, "role": role, "status": status, "children": children}


def _from_flat(people: List[Any]) -> Optional[Dict[str, Any]]:
    """Fold a flat ``{id, name, title, reports_to}`` export into a tree.

    Cycles and unknown parents are the normal state of a real export, so both
    are survived rather than raised on: an unreachable person is attached to the
    root instead of being dropped, because a person missing from an org chart is
    a worse failure than one drawn in the wrong place.
    """
    rows: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    for raw in people:
        if not isinstance(raw, dict):
            continue
        node = _node(raw)
        if node is None:
            continue
        key = str(raw.get("id") or node["name"])
        node["_parent"] = str(raw.get("reports_to") or raw.get("parent")
                              or raw.get("manager") or "")
        rows[key] = node
        order.append(key)
    if not rows:
        return None

    for key in order:
        rows[key]["children"] = []
    roots: List[str] = []
    for key in order:
        parent = rows[key].pop("_parent", "")
        # Walk up to detect a cycle before attaching, so a mutual-report pair
        # cannot make the layout recurse forever.
        seen, cur, cyclic = {key}, parent, False
        while cur in rows:
            if cur in seen:
                cyclic = True
                break
            seen.add(cur)
            cur = str(rows[cur].get("_parent") or "") if "_parent" in rows[cur] else ""
        if parent and parent in rows and parent != key and not cyclic:
            rows[parent]["children"].append(rows[key])
        else:
            roots.append(key)
    if len(roots) == 1:
        return rows[roots[0]]
    return {"name": "Organisation", "role": "", "status": "filled",
            "children": [rows[k] for k in roots]}


def _flatten(node: Dict[str, Any], depth: int = 0) -> List[Tuple[Dict[str, Any], int]]:
    """Depth-first list of a subtree, carrying indent depth."""
    out = [(node, depth)]
    for child in node["children"]:
        out.extend(_flatten(child, depth + 1))
    return out


def column_width(columns: int, width: int = MAX_WIDTH) -> float:
    """How wide each column may be, given how many share the row.

    Fills the canvas rather than leaving it: with three units on a 1,160px page
    there is room for 370px a column, and pinning them to 206 trimmed names that
    would otherwise have fitted whole.
    """
    columns = max(1, columns)
    usable = width - 2 * MARGIN - (columns - 1) * COL_GAP
    return max(CARD_W, min(CARD_W_MAX, usable / columns))


def columns_per_bank(count: int, width: int = MAX_WIDTH) -> int:
    """How many columns fit across, so width is bounded however wide the org is.

    Returning at least one keeps a single very wide card from producing a
    zero-column layout and a division by zero downstream.
    """
    usable = width - 2 * MARGIN + COL_GAP
    return max(1, min(count, int(usable // (CARD_W + COL_GAP)) or 1))


@register("org_chart")
class OrgChartTemplate:
    def render(self, params: Dict[str, Any]) -> str:
        params = params or {}
        root = _node(params.get("root")) if params.get("root") else None
        if root is None:
            people = params.get("people") or params.get("employees") or []
            root = _from_flat(people) if isinstance(people, list) else None
        if root is None:
            return svg_document("", width=200, height=80,
                                class_name="diagram org-chart")

        title = str(params.get("title") or "").strip()
        units = root["children"]
        # Everything under a unit is stacked; the unit itself heads the column.
        stacks = [_flatten(u)[1:] for u in units]

        assistants = [a for a in (params.get("assistants") or []) if isinstance(a, dict)]
        assistant_h = ROW_H if assistants else 0

        per_bank = columns_per_bank(len(units) or 1)
        banks: List[List[int]] = [list(range(i, min(i + per_bank, len(units))))
                                  for i in range(0, len(units), per_bank)] or [[]]

        index = {}
        for node, _ in _flatten(root):
            index.setdefault(node["name"], node)


        top = HEADER_H if title else MARGIN
        root_y = top
        bus_y = root_y + CARD_H + SPINE_DROP / 2 + assistant_h
        bank_top = bus_y + SPINE_DROP / 2

        bank_heights = []
        for bank in banks:
            tallest = max((len(stacks[i]) for i in bank), default=0)
            bank_heights.append(CARD_H + STACK_TOP_GAP + tallest * ROW_H)

        widest = max((len(bank) for bank in banks), default=1)
        card_w = column_width(widest)
        # An assistant hangs to the right of the spine, so the canvas has to be
        # wide enough for the root card *and* that row. Solving
        # `centre + card_w/2 + 26 + assistant + MARGIN <= width` for width gives
        # the second term below; without it a one-unit chart sized itself to the
        # card and left the assistant 34px to render a name in.
        assistant_w = float(min(card_w, ASSISTANT_W)) if assistants else 0.0
        if len(units) > 1:
            width = MAX_WIDTH
        else:
            needed = card_w + 2 * MARGIN + 120
            if assistants:
                needed = max(needed, card_w + 52 + 2 * assistant_w + 2 * MARGIN)
            width = max(420, int(needed + 0.5))
        height = int(bank_top + sum(bank_heights) + BANK_GAP * max(0, len(banks) - 1)
                     + MARGIN + 30)

        p: List[str] = ["<defs>" + style(_CSS) + "</defs>"]
        p.append(rect(0, 0, width, height, fill="#ffffff", **{"class": "grid-paper"}))
        if title:
            p.append(text(MARGIN, 40, fit_text(title, width - 2 * MARGIN, TITLE_PX, bold=True),
                          **{"class": "oc-title"}))

        centre = width / 2
        p.extend(self._card(root, centre - card_w / 2, root_y, card_w, root=True))

        # Assistants: on a side line below the principal, above their reports.
        for i, raw in enumerate(assistants):
            node = _node(raw)
            if node is None:
                continue
            ay = root_y + CARD_H + 8 + i * ROW_H
            ax = centre + card_w / 2 + 26
            p.append(path(f"M {centre:.1f} {ay + ROW_H / 2:.1f} H {ax:.1f}",
                          **{"class": "oc-edge"}))
            p.extend(self._row(node, ax, ay,
                               min(assistant_w, width - MARGIN - ax)))

        placed: Dict[str, Tuple[float, float]] = {}
        y = bank_top
        for bank_i, bank in enumerate(banks):
            span = len(bank) * card_w + (len(bank) - 1) * COL_GAP
            x0 = (width - span) / 2
            if bank:
                p.append(path(f"M {centre:.1f} {bus_y - SPINE_DROP / 2:.1f} "
                              f"V {y - STACK_TOP_GAP / 2:.1f}", **{"class": "oc-edge"}))
                left = x0 + card_w / 2
                right = x0 + span - card_w / 2
                p.append(path(f"M {left:.1f} {y - STACK_TOP_GAP / 2:.1f} "
                              f"H {right:.1f}", **{"class": "oc-edge"}))
            for slot, unit_i in enumerate(bank):
                cx = x0 + slot * (card_w + COL_GAP)
                unit = units[unit_i]
                p.append(path(f"M {cx + card_w / 2:.1f} {y - STACK_TOP_GAP / 2:.1f} "
                              f"V {y:.1f}", **{"class": "oc-edge"}))
                p.extend(self._card(unit, cx, y, card_w, root=False))
                # The *top* edge, not the centre. A dotted line drawn to the
                # centre crosses the card's own name on the way in, so it
                # obscures the person it is pointing at; arcing above and
                # meeting the edge leaves both labels clear.
                placed[unit["name"]] = (cx + card_w / 2, y)
                ry = y + CARD_H + STACK_TOP_GAP
                for node, depth in stacks[unit_i]:
                    ix = cx + (depth - 1) * INDENT
                    w = card_w - (depth - 1) * INDENT
                    p.append(path(f"M {ix - 8:.1f} {ry - 4:.1f} V {ry + ROW_H / 2:.1f} "
                                  f"H {ix:.1f}", **{"class": "oc-edge"}))
                    p.extend(self._row(node, ix, ry, w))
                    placed[node["name"]] = (ix + w / 2, ry)
                    ry += ROW_H
            y += bank_heights[bank_i] + BANK_GAP

        p.extend(self._dotted(params.get("dotted") or params.get("dotted_lines") or [],
                              placed))
        p.extend(self._legend(root, assistants, params, width, height))
        return svg_document("".join(p), width=int(width), height=height,
                            class_name="diagram org-chart")

    # -- pieces ----------------------------------------------------------
    def _card(self, node: Dict[str, Any], x: float, y: float, width: float,
              root: bool) -> List[str]:
        status = node["status"]
        vacant = status == "vacant"
        cls = ("oc-card root" if root else
               "oc-card" + (f" {status}" if status in ("vacant", "interim") else ""))
        out = [rect(x, y, width, CARD_H, rx=7, **{"class": cls})]
        pad = 12
        name = fit_text(node["name"], width - 2 * pad, NAME_PX, bold=True)
        out.append(text(x + width / 2, y + 23, name, text_anchor="middle",
                        **{"class": "oc-name root" if root else "oc-name"}))
        role = node["role"] or ("Vacant" if vacant else "")
        if role:
            rcls = "oc-role root" if root else ("oc-role vacant" if vacant else "oc-role")
            out.append(text(x + width / 2, y + 41,
                            fit_text(role, width - 2 * pad, ROLE_PX),
                            text_anchor="middle", **{"class": rcls}))
        return out

    def _row(self, node: Dict[str, Any], x: float, y: float, w: float) -> List[str]:
        status = node["status"]
        cls = "oc-row" + (f" {status}" if status in ("vacant", "interim") else "")
        out = [rect(x, y, w, ROW_H - 6, rx=5, **{"class": cls})]
        pad, gap = 9, 8
        name = node["name"]
        role = node["role"] or ("Vacant" if status == "vacant" else "")
        inner = w - 2 * pad

        # The role's space is reserved *before* the name is placed, and the name
        # is then fitted into what is left. Placing the name first and giving the
        # role the remainder let a name whose width was under-measured put the
        # two on top of each other, which is what "Ken Thompson" over "Staff
        # Engine…" was. Now the two fields cannot overlap even if the estimate is
        # wrong, because neither is allowed into the other's budget.
        role_w = 0.0
        if role:
            want = text_width(role, ROLE_PX, safe=True)
            role_w = min(want, max(0.0, inner * 0.40))
            if role_w < 22:                     # too little to say anything
                role_w = 0.0
        name_budget = inner - (role_w + gap if role_w else 0.0)
        out.append(text(x + pad, y + 16,
                        fit_text(name, name_budget, NAME_PX, bold=True),
                        **{"class": "oc-name"}))
        if role_w:
            rcls = "oc-role vacant" if status == "vacant" else "oc-role"
            out.append(text(x + w - pad, y + 16,
                            fit_text(role, role_w, ROLE_PX),
                            text_anchor="end", **{"class": rcls}))
        return out

    def _dotted(self, raw: Any, placed: Dict[str, Tuple[float, float]]) -> List[str]:
        out: List[str] = []
        if not isinstance(raw, list):
            return out
        for link in raw:
            if not isinstance(link, dict):
                continue
            a = placed.get(str(link.get("from") or ""))
            b = placed.get(str(link.get("to") or ""))
            if not a or not b or a == b:
                continue
            # A quadratic passes at half its control offset, so the control
            # point is solved for the apex we actually want rather than guessed
            # at: apex = (start + 2·control + end)/4. Bowing by a fixed multiple
            # put the control 156px above the cards to raise the curve by 63,
            # and left the label floating over the root card labelling nothing.
            clearance = 26.0
            apex_y = min(a[1], b[1]) - clearance
            mx = (a[0] + b[0]) / 2
            my = (4 * apex_y - a[1] - b[1]) / 2
            out.append(path(f"M {a[0]:.1f} {a[1]:.1f} Q {mx:.1f} {my:.1f} "
                            f"{b[0]:.1f} {b[1]:.1f}", **{"class": "oc-dotted"}))
            label = str(link.get("label") or "")
            if label:
                # On the curve it names, not above where the curve might have
                # gone: the apex is where the two are closest to each other.
                out.append(text(mx, apex_y - 5, label, text_anchor="middle",
                                **{"class": "oc-dotted-label"}))
        return out

    def _legend(self, root: Dict[str, Any], assistants: List[Any],
                params: Dict[str, Any], width: int, height: int) -> List[str]:
        """Name every convention the chart uses. A dashed line with no legend is
        a line the reader has to guess at, which is the failure the sources on
        dotted-line reporting are unanimous about."""
        nodes = [n for n, _ in _flatten(root)]
        entries: List[Tuple[str, str]] = []
        if any(n["status"] == "vacant" for n in nodes):
            entries.append(("vacant", "vacant / to be hired"))
        if any(n["status"] == "interim" for n in nodes):
            entries.append(("interim", "interim"))
        if params.get("dotted") or params.get("dotted_lines"):
            entries.append(("dotted", "secondary (dotted-line) reporting"))
        if assistants:
            entries.append(("assistant", "assistant / chief of staff"))
        if not entries:
            return []
        out: List[str] = []
        x, y = float(MARGIN), height - 18
        for kind, label in entries:
            if kind == "dotted":
                out.append(path(f"M {x:.1f} {y - 4:.1f} H {x + 18:.1f}",
                                **{"class": "oc-dotted"}))
            elif kind == "assistant":
                out.append(path(f"M {x:.1f} {y - 4:.1f} H {x + 18:.1f}",
                                **{"class": "oc-edge"}))
            else:
                cls = "oc-row vacant" if kind == "vacant" else "oc-row"
                out.append(rect(x, y - 10, 18, 11, rx=3, **{"class": cls}))
            out.append(text(x + 24, y, label, **{"class": "oc-legend"}))
            x += 34 + text_width(label, 11, safe=True)
        return out
