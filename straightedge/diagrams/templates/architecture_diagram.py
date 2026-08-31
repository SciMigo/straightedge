"""Architecture diagram template for system design lectures."""

from __future__ import annotations

import math
from collections import deque
from html import escape
from typing import Any, Dict, List, Optional, Tuple

from ..registry import register
from ..renderer import (
    defs,
    fit_lines,
    line,
    path,
    rect,
    style,
    svg_document,
    text,
    titled_group,
)

# Component fill colours by kind/type
_FILL = {
    "service": "#E3F2FD",
    "service_cluster": "#E3F2FD",
    "worker": "#E3F2FD",
    "database": "#E8F5E9",
    "datastore": "#E8F5E9",
    "cache": "#FFF8E1",
    "queue": "#F3E5F5",
    "bus": "#F3E5F5",
    "client": "#F5F5F5",
    "external": "#F5F5F5",
}

_STROKE = {
    "cache": "#FFC107",
}

_DEFAULT_FILL = "#F5F5F5"
_DEFAULT_STROKE = "#546E7A"

_BOX_W = 140
_BOX_H = 44
_BOX_RX = 8
_CYLINDER_H = 50
_CYLINDER_RX = 35
_CYLINDER_RY = 8

# Layout constants
_PADDING = 60
#: One line of the bottom note stack, at the 10px note size, plus the gap that
#: keeps the last baseline off the canvas edge — a baseline sitting exactly on
#: it still hangs the descenders over.
_NOTE_LINE = 14
_NOTE_PAD = 6
#: Component label size, and the step between its two lines.
_LABEL_PX = 12
_LABEL_LINE = 13
_LAYER_GAP_H = 180  # horizontal gap between layers (left-to-right)
_LAYER_GAP_V = 100  # vertical gap between layers (top-to-bottom)
_NODE_GAP_H = 60  # gap between nodes in same layer (left-to-right)
_NODE_GAP_V = 70  # gap between nodes in same layer (top-to-bottom)


def _normalise_components(params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Accept ``components`` or ``elements`` key."""
    raw = params.get("components") or params.get("elements") or []
    if not isinstance(raw, list):
        return []
    out: List[Dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        comp = dict(item)
        # Normalise kind → type
        if "kind" in comp and "type" not in comp:
            comp["type"] = comp.pop("kind")
        out.append(comp)
    return out


def _normalise_connections(params: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw = params.get("connections", [])
    if not isinstance(raw, list):
        return []
    return [c for c in raw if isinstance(c, dict)]


def _normalise_annotations(params: Dict[str, Any]) -> List[Dict[str, str]]:
    raw = params.get("annotations") or params.get("notes") or []
    if not isinstance(raw, list):
        return []
    out: List[Dict[str, str]] = []
    for item in raw:
        if isinstance(item, str):
            out.append({"text": item, "near": ""})
        elif isinstance(item, dict):
            out.append({
                "text": str(item.get("text", "")),
                "near": str(item.get("near", "")),
            })
    return out


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

def _build_adjacency(
    node_ids: List[str],
    connections: List[Dict[str, Any]],
) -> Dict[str, List[str]]:
    adj: Dict[str, List[str]] = {nid: [] for nid in node_ids}
    for conn in connections:
        src = str(conn.get("from", ""))
        tgt = str(conn.get("to", ""))
        if src in adj and tgt in adj:
            adj[src].append(tgt)
    return adj


def _find_roots(
    node_ids: List[str],
    connections: List[Dict[str, Any]],
) -> List[str]:
    """Return nodes with no incoming edges, preserving order."""
    has_incoming = set()
    id_set = set(node_ids)
    for conn in connections:
        tgt = str(conn.get("to", ""))
        if tgt in id_set:
            has_incoming.add(tgt)
    roots = [nid for nid in node_ids if nid not in has_incoming]
    return roots if roots else node_ids[:1]


def _hierarchical_layout(
    node_ids: List[str],
    connections: List[Dict[str, Any]],
    direction: str,
) -> Tuple[Dict[str, Tuple[float, float]], int, int]:
    """BFS layered layout.  Returns (positions, svg_width, svg_height)."""
    if not node_ids:
        return {}, 200, 200

    adj = _build_adjacency(node_ids, connections)
    roots = _find_roots(node_ids, connections)

    levels: Dict[str, int] = {}
    q: deque[str] = deque()
    for r in roots:
        if r not in levels:
            levels[r] = 0
            q.append(r)

    while q:
        cur = q.popleft()
        for nbr in adj.get(cur, []):
            if nbr not in levels:
                levels[nbr] = levels[cur] + 1
                q.append(nbr)

    # Assign unreachable nodes to an extra layer
    max_level = max(levels.values(), default=0)
    for nid in node_ids:
        if nid not in levels:
            max_level += 1
            levels[nid] = max_level

    # Group by level
    grouped: Dict[int, List[str]] = {}
    for nid, lvl in levels.items():
        grouped.setdefault(lvl, []).append(nid)

    # Preserve original order within each layer
    id_order = {nid: i for i, nid in enumerate(node_ids)}
    for lvl in grouped:
        grouped[lvl].sort(key=lambda n: id_order.get(n, 0))

    num_layers = max(grouped.keys()) + 1
    max_per_layer = max(len(v) for v in grouped.values())

    ltr = direction == "left-to-right"

    if ltr:
        svg_w = _PADDING * 2 + (num_layers - 1) * _LAYER_GAP_H + _BOX_W
        svg_h = _PADDING * 2 + (max_per_layer - 1) * _NODE_GAP_V + _BOX_H
        svg_h = max(svg_h, 300)
    else:
        svg_w = _PADDING * 2 + (max_per_layer - 1) * _NODE_GAP_H + _BOX_W
        svg_w = max(svg_w, 400)
        svg_h = _PADDING * 2 + (num_layers - 1) * _LAYER_GAP_V + _CYLINDER_H

    positions: Dict[str, Tuple[float, float]] = {}
    for lvl, members in grouped.items():
        count = len(members)
        for idx, nid in enumerate(members):
            if ltr:
                x = _PADDING + lvl * _LAYER_GAP_H
                total_h = (count - 1) * _NODE_GAP_V
                start_y = (svg_h - total_h) / 2
                y = start_y + idx * _NODE_GAP_V
            else:
                total_w = (count - 1) * _NODE_GAP_H
                start_x = (svg_w - total_w) / 2
                x = start_x + idx * _NODE_GAP_H
                y = _PADDING + lvl * _LAYER_GAP_V
            positions[nid] = (x, y)

    return positions, svg_w, svg_h


# ---------------------------------------------------------------------------
# SVG shape helpers
# ---------------------------------------------------------------------------

def _cylinder_path(x: float, y: float, w: float, h: float, ry: float) -> str:
    """SVG path for a cylinder shape (database icon)."""
    # Top ellipse, sides, bottom ellipse
    rx = w / 2
    cx = x + rx
    top_y = y + ry
    bot_y = y + h - ry
    d = (
        f"M {x} {top_y} "
        f"A {rx} {ry} 0 1 1 {x + w} {top_y} "
        f"L {x + w} {bot_y} "
        f"A {rx} {ry} 0 1 1 {x} {bot_y} "
        f"Z "
        # Top ellipse visible arc (drawn on top)
        f"M {x} {top_y} "
        f"A {rx} {ry} 0 1 0 {x + w} {top_y}"
    )
    return d


def _render_component(
    comp: Dict[str, Any],
    cx: float,
    cy: float,
) -> Tuple[str, Tuple[float, float]]:
    """Render a single component and return (svg_fragment, center_point)."""
    kind = str(comp.get("type", "service")).lower()
    label = str(comp.get("label", comp.get("id", "")))
    fill = _FILL.get(kind, _DEFAULT_FILL)
    stroke = _STROKE.get(kind, _DEFAULT_STROKE)

    elements: List[str] = []
    center: Tuple[float, float]

    is_db = kind in ("database", "datastore")
    is_cache = kind == "cache"

    if is_db:
        w, h, ry = _BOX_W, _CYLINDER_H, _CYLINDER_RY
        x0 = cx
        y0 = cy
        d = _cylinder_path(x0, y0, w, h, ry)
        elements.append(path(d, fill=fill, stroke=stroke, stroke_width="1.4"))
        center = (x0 + w / 2, y0 + h / 2)
        elements.extend(_label_lines(label, center[0], center[1] + 5))
    else:
        w, h = _BOX_W, _BOX_H
        extra: Dict[str, Any] = {}
        if is_cache:
            extra["stroke_dasharray"] = "6,3"
        elements.append(rect(
            cx, cy, w, h,
            rx=_BOX_RX, ry=_BOX_RX,
            fill=fill, stroke=stroke,
            stroke_width="1.4",
            **extra,
        ))
        center = (cx + w / 2, cy + h / 2)
        elements.extend(_label_lines(label, center[0], center[1] + 4))

    # One group per component, named by its title. Emitted as siblings of the
    # shapes, seven titles were children of the root `<svg>` — every one naming
    # the whole document, and all but the first ignored.
    return titled_group(label, elements), center


# ---------------------------------------------------------------------------
# Connection rendering
# ---------------------------------------------------------------------------

def _arrow_marker() -> str:
    return (
        '<marker id="arch-arrow" markerWidth="10" markerHeight="7" '
        'refX="9" refY="3.5" orient="auto">'
        '<polygon points="0 0, 10 3.5, 0 7" fill="#546E7A"/>'
        '</marker>'
    )


def _edge_anchor(
    center: Tuple[float, float],
    target: Tuple[float, float],
    kind: str,
) -> Tuple[float, float]:
    """Compute the anchor point on the component boundary closest to *target*."""
    cx, cy = center
    tx, ty = target
    dx = tx - cx
    dy = ty - cy

    is_db = kind in ("database", "datastore")
    half_w = _BOX_W / 2
    half_h = (_CYLINDER_H if is_db else _BOX_H) / 2

    if dx == 0 and dy == 0:
        return (cx + half_w, cy)

    # Scale to box boundary
    sx = abs(half_w / dx) if dx != 0 else float("inf")
    sy = abs(half_h / dy) if dy != 0 else float("inf")
    s = min(sx, sy)
    return (cx + dx * s, cy + dy * s)


def _label_lines(label: str, cx: float, cy: float) -> List[str]:
    """The component label, wrapped to fit the box it is drawn in.

    Drawn raw, a label wider than the 140px box simply overhung it: "Gateway
    (WebSocket/MQTT)" measured 186px and reached 46px into the space either
    side, far enough to collide with the label on the connection leaving it.
    Two lines fit comfortably in 44px of box, so wrap rather than truncate --
    the text is the diagram's content, and there is room for it.
    """
    lines = fit_lines(label, _BOX_W - 12, _LABEL_PX)
    top = cy - _LABEL_LINE * (len(lines) - 1) / 2
    return [text(cx, top + _LABEL_LINE * i, part,
                 text_anchor="middle",
                 font_size=f"{_LABEL_PX}px",
                 font_family="sans-serif",
                 fill="#333")
            for i, part in enumerate(lines)]


def _render_connection(
    conn: Dict[str, Any],
    centers: Dict[str, Tuple[float, float]],
    kinds: Dict[str, str],
) -> str:
    src = str(conn.get("from", ""))
    tgt = str(conn.get("to", ""))
    label = conn.get("label")

    if src not in centers or tgt not in centers:
        return ""

    sc = centers[src]
    tc = centers[tgt]

    p1 = _edge_anchor(sc, tc, kinds.get(src, "service"))
    p2 = _edge_anchor(tc, sc, kinds.get(tgt, "service"))

    elements: List[str] = []
    elements.append(line(
        p1[0], p1[1], p2[0], p2[1],
        stroke="#546E7A",
        stroke_width="1.6",
        marker_end="url(#arch-arrow)",
    ))

    if label:
        mid_x = (p1[0] + p2[0]) / 2
        mid_y = (p1[1] + p2[1]) / 2 - 8
        elements.append(text(
            mid_x, mid_y, str(label),
            text_anchor="middle",
            font_size="10px",
            font_family="sans-serif",
            fill="#666",
        ))

    return "\n".join(elements)


# ---------------------------------------------------------------------------
# Template
# ---------------------------------------------------------------------------

@register("architecture_diagram")
class ArchitectureDiagramTemplate:
    """Render a system architecture diagram with typed components and connections."""

    def render(self, params: Dict[str, Any]) -> str:
        components = _normalise_components(params)
        connections = _normalise_connections(params)
        annotations = _normalise_annotations(params)
        caption = params.get("caption") or params.get("title") or ""
        direction = str(params.get("layout", "left-to-right"))
        if direction not in ("left-to-right", "top-to-bottom"):
            direction = "left-to-right"

        if not components:
            return ""

        node_ids = [str(c["id"]) for c in components if "id" in c]
        positions, svg_w, svg_h = _hierarchical_layout(
            node_ids, connections, direction,
        )

        # An annotation with no `near`, or one naming a component that is not
        # here, has nowhere to point. Those go in a stack along the bottom, and
        # the stack needs room: every one of them used to be placed at the same
        # single spot, so two notes were drawn one on top of the other and the
        # reader saw neither.
        anchored = set(node_ids)
        loose = [a for a in annotations
                 if not (a.get("near") and str(a["near"]) in anchored)
                 and a.get("text")]
        # Wrapped before the height is reserved, so a note that needs two lines
        # gets two. It used to get one and an ellipsis, with the trimmed half
        # kept nowhere at all — on a narrow diagram the note the caller supplied
        # was simply not in the document. Whatever the lines cannot hold is
        # still the group's accessible name.
        note_room = svg_w - _PADDING * 2
        notes = [(str(a["text"]), fit_lines(str(a["text"]), note_room, 10))
                 for a in loose]
        # One number for the stack's height, used both to reserve it here and
        # to place it later — two independent copies of this sum drifted apart
        # is exactly the out-of-frame failure the reservation exists to prevent.
        notes_h = _NOTE_LINE * sum(len(lines) for _, lines in notes)
        notes_h += _NOTE_PAD if loose else 0
        svg_h += notes_h

        # Reserve space for caption
        if caption:
            svg_h += 30

        elements: List[str] = []
        elements.append(style(_STYLES))
        elements.append(defs(_arrow_marker()))

        # Map id → kind and id → center for connection rendering
        kind_map: Dict[str, str] = {}
        center_map: Dict[str, Tuple[float, float]] = {}

        # Render components
        for comp in components:
            cid = str(comp.get("id", ""))
            if cid not in positions:
                continue
            kind = str(comp.get("type", "service")).lower()
            kind_map[cid] = kind
            cx, cy = positions[cid]
            svg_frag, center = _render_component(comp, cx, cy)
            center_map[cid] = center
            elements.append(svg_frag)

        # Render connections (on top of components for visibility)
        for conn in connections:
            elements.append(_render_connection(conn, center_map, kind_map))

        # Annotations that point at something, drawn where they point — with
        # the same care the loose stack gets. Drawn raw they had every defect
        # the stack was rewritten to fix: unwrapped and unmeasured, so a long
        # note overhung the frame with no <title> holding the lost text, and
        # every note on one component was placed at the same single spot, so
        # two of them overlapped by 100% and the reader saw neither.
        anchored_lines_placed: Dict[str, int] = {}
        for ann in annotations:
            ann_text = ann.get("text", "")
            near_id = ann.get("near", "")
            if not ann_text or not (near_id and near_id in center_map):
                continue
            ax, ay = center_map[near_id]
            ay += (_CYLINDER_H if kind_map.get(near_id) in ("database", "datastore") else _BOX_H) / 2 + 16
            start = anchored_lines_placed.get(near_id, 0)
            lines = fit_lines(ann_text, _BOX_W, 10)
            drawn = [text(
                ax, ay + _NOTE_LINE * (start + i), part,
                text_anchor="middle",
                font_size="10px",
                font_style="italic",
                font_family="sans-serif",
                fill="#888",
            ) for i, part in enumerate(lines)]
            anchored_lines_placed[near_id] = start + len(lines)
            elements.append(titled_group(ann_text, drawn))

        # The rest go in a stack along the bottom, left-aligned. Centring a
        # 300px note on the left margin put most of it off the canvas, and every
        # one used to be placed at the same single spot, drawn over each other.
        note_top = svg_h - (30 if caption else 0) - notes_h
        placed = 0
        for full, lines in notes:
            drawn = [text(_PADDING, note_top + _NOTE_LINE * (placed + i) + _NOTE_LINE,
                          part,
                          text_anchor="start",
                          font_size="10px",
                          font_style="italic",
                          font_family="sans-serif",
                          fill="#888")
                     for i, part in enumerate(lines)]
            placed += len(lines)
            elements.append(titled_group(full, drawn))

        # Caption
        if caption:
            elements.append(text(
                svg_w / 2, svg_h - 10, str(caption),
                text_anchor="middle",
                font_size="13px",
                font_family="sans-serif",
                fill="#333",
            ))

        return svg_document("\n".join(elements), svg_w, svg_h)


_STYLES = """
.diagram-label { font-size: 12px; font-family: sans-serif; fill: #333; }
"""
