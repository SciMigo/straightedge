"""Sequence diagram: parties as lifelines, messages in time order down the page.

The registry could draw a chain of steps (:mod:`flow_diagram`) and boxes joined
by arrows (:mod:`architecture_diagram`), but not *who sends what to whom, in
what order*. That is the shape of every protocol explanation — a Worker sends a
Command, the Service records an Event, a timer fires while nobody is running —
and without it such figures were hand-drawn SVG or ASCII art with two "Worker"
columns standing in for "later". Here time runs down the page, so one lifeline
per party is enough, and a ``gap`` row can break the lifelines of parties that
are absent while the others carry on: the picture of a process dying while the
service keeps its clock.

The labels are the content — event numbers, sequence numbers, command names —
so they are drawn exactly, and the input is checked before anything is drawn:
a message to an undeclared party, or event numbers that do not increase down
the page, is refused with the row that breaks it (see :meth:`refusal_findings`)
rather than drawn as a plausible wrong protocol.

image_hint usage::

    {"type": "sequence_diagram", "params": {
        "participants": [
            {"id": "worker", "label": "Worker"},
            {"id": "svc", "label": "Temporal Service"}],
        "rows": [
            {"from": "worker", "to": "svc", "label": "StartTimer(20 s)", "event": 11},
            {"gap": "20 s pass", "breaks": ["worker"]},
            {"self": "svc", "label": "TimerFired", "event": 12},
            {"from": "svc", "to": "worker", "label": "Workflow Task", "event": 13,
             "style": "dashed"}]}}

Row kinds, one per item in ``rows`` (alias ``steps`` / ``messages``):

* message — ``from``, ``to``, ``label``; optional ``style`` (``"solid"`` or
  ``"dashed"``, for a reply or an asynchronous delivery), ``tone``, ``event``.
* self message — ``self`` (a participant id) and ``label``, or ``from`` equal
  to ``to``. Drawn as a loop on that lifeline.
* note — ``note`` text, ``over`` one participant id or a list of them.
* gap — ``gap`` text for the time that passes; ``breaks`` lists participants
  whose lifelines are interrupted across it.

``event`` is an optional number shown in the left gutter, for protocols whose
steps are numbered (an event history, a packet trace); ``event_label`` heads that
column, so a reader is told what the numbers count. ``tone`` is one of the
theme's categorical roles: ``primary``, ``secondary``, ``success``, ``warning``,
``danger``, ``accent``. A participant is a dict with ``id``, ``label`` and an
optional ``sub`` line, or a bare string used as both id and label.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from ...qc import Finding
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
    text_width,
    title as svg_title,
    titled_group,
)
from ..themes import DIAGRAM_THEMES, DiagramTheme, family, resolve_theme

MARGIN = 24
TITLE_FONT = 17
TITLE_H = 36
GUTTER_W = 40          # the event-number column, drawn only when a row has one
HEAD_FONT = 15
SUB_FONT = 12
HEAD_PAD_X = 16
HEAD_MIN_W = 120
HEAD_H = 44
HEAD_SUB_H = 62
LABEL_FONT = 13
LABEL_LH = 17
LABEL_MAX_W = 420      # a message label wraps past this, to at most two lines
NOTE_FONT = 13
NOTE_LH = 18
NOTE_MAX_W = 300
NOTE_PAD = 8
GAP_FONT = 13
EVENT_FONT = 12
COL_MIN = 170          # smallest distance between two lifelines
ARROW_PAD = 16         # clear space between a label and the lifelines it spans
LOOP_W = 30
LOOP_DROP = 18
ROW_TOP = 18           # between the header boxes and the first row
MSG_H = 40
SELF_H = 52
GAP_H = 44
TAIL = 16              # lifelines run this far past the last row

TONES = ("primary", "secondary", "success", "warning", "danger", "accent")

#: Pre-theme there was no sequence diagram, so the professional palette is the
#: shared one unchanged; ``dark`` exists for pages whose other figures are dark.
THEMES = family(DIAGRAM_THEMES["professional"], "dark", "high-contrast", "print-friendly")


def _participants(raw: Any) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for item in raw if isinstance(raw, list) else []:
        if isinstance(item, str) and item.strip():
            out.append({"id": item.strip(), "label": item.strip(), "sub": ""})
        elif isinstance(item, dict):
            pid = str(item.get("id") or item.get("name") or item.get("label") or "").strip()
            if pid:
                out.append({"id": pid,
                            "label": str(item.get("label") or item.get("name") or pid).strip(),
                            "sub": str(item.get("sub") or item.get("desc") or "").strip()})
    return out


def _as_ids(value: Any) -> List[str]:
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    return [str(value).strip()] if value is not None and str(value).strip() else []


def _rows(raw: Any) -> List[Dict[str, Any]]:
    """Normalise each row to one of four kinds; drop what is none of them."""
    out: List[Dict[str, Any]] = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        event = item.get("event")
        tone = str(item.get("tone") or "").strip()
        base = {"event": event, "tone": tone if tone in TONES else ""}
        if "gap" in item:
            out.append({**base, "kind": "gap", "label": str(item.get("gap") or "").strip(),
                        "breaks": _as_ids(item.get("breaks"))})
        elif "note" in item:
            out.append({**base, "kind": "note", "label": str(item.get("note") or "").strip(),
                        "over": _as_ids(item.get("over"))})
        elif "self" in item or ("from" in item and item.get("from") == item.get("to")):
            out.append({**base, "kind": "self",
                        "at": str(item.get("self") or item.get("from") or "").strip(),
                        "label": str(item.get("label") or "").strip()})
        elif "from" in item or "to" in item:
            out.append({**base, "kind": "message",
                        "from": str(item.get("from") or "").strip(),
                        "to": str(item.get("to") or "").strip(),
                        "label": str(item.get("label") or "").strip(),
                        "dashed": str(item.get("style") or "").strip().lower() == "dashed"})
    return out


def _referenced(row: Dict[str, Any]) -> List[str]:
    kind = row["kind"]
    if kind == "message":
        return [row["from"], row["to"]]
    if kind == "self":
        return [row["at"]]
    if kind == "note":
        return row["over"]
    return row["breaks"]


def _findings(params: Dict[str, Any]) -> List[Finding]:
    participants = _participants(params.get("participants") or params.get("actors")
                                 or params.get("lifelines"))
    rows = _rows(params.get("rows") or params.get("steps") or params.get("messages"))
    findings: List[Finding] = []
    if not participants:
        return [Finding("sequence_input", "error", "no participants to draw lifelines for")]
    if not rows:
        return [Finding("sequence_input", "error", "no rows: nothing happens between the parties")]
    seen: set[str] = set()
    for p in participants:
        if p["id"] in seen:
            findings.append(Finding("sequence_input", "error",
                                    f"participant id {p['id']!r} is declared twice", label=p["id"]))
        seen.add(p["id"])
    last_event: Optional[float] = None
    for index, row in enumerate(rows):
        where = f"row {index + 1} ({row['label'] or row['kind']})"
        for pid in _referenced(row):
            if pid not in seen:
                findings.append(Finding("sequence_input", "error",
                                        f"{where} names {pid!r}, which is not a declared participant",
                                        label=pid))
        if row["kind"] == "note" and not row["over"]:
            findings.append(Finding("sequence_input", "error", f"{where} is a note over nobody"))
        if row["event"] is not None:
            try:
                event = float(row["event"])
            except (TypeError, ValueError):
                findings.append(Finding("sequence_input", "error",
                                        f"{where} has event {row['event']!r}, which is not a number",
                                        label=str(row["event"])))
                continue
            # Numbered steps are the order the diagram claims; drawing 12 above 11
            # is a protocol that did not happen.
            if last_event is not None and event <= last_event:
                findings.append(Finding("sequence_input", "error",
                                        f"{where} has event {row['event']}, not after the "
                                        f"{last_event:g} above it", label=str(row["event"])))
            last_event = event
    return findings


def _event_text(value: Any) -> str:
    number = float(value)
    return str(int(number)) if number.is_integer() else f"{number:g}"


@register("sequence_diagram")
class SequenceDiagramTemplate:
    """Lifelines for each party; messages, notes and gaps in time order."""

    motion = "none"
    themes = THEMES
    checks = ["every row names declared participants", "event numbers increase down the page",
              "labels fit between the lifelines they span"]

    def refusal_findings(self, params: Dict[str, Any]) -> List[Finding]:
        return _findings(params or {})

    def render(self, params: Dict[str, Any]) -> str:
        params = params or {}
        participants = _participants(params.get("participants", []) or params.get("actors", [])
                                     or params.get("lifelines", []))
        rows = _rows(params.get("rows", []) or params.get("steps", []) or params.get("messages", []))
        title = str(params.get("title", "") or "").strip()
        event_label = str(params.get("event_label", "") or "").strip()
        theme = resolve_theme(params.get("theme", "professional"), THEMES)
        if _findings(params):
            return ""

        n = len(participants)
        col = {p["id"]: i for i, p in enumerate(participants)}
        has_sub = any(p["sub"] for p in participants)
        head_h = HEAD_SUB_H if has_sub else HEAD_H
        gutter = GUTTER_W if any(r["event"] is not None for r in rows) else 0
        if gutter and event_label:
            gutter = max(gutter, text_width(event_label, SUB_FONT, safe=True) + 16)

        head_w = [max(HEAD_MIN_W,
                      text_width(p["label"], HEAD_FONT, bold=True, safe=True) + 2 * HEAD_PAD_X,
                      text_width(p["sub"], SUB_FONT, safe=True) + 2 * HEAD_PAD_X)
                  for p in participants]

        # Wrap every label once, then size the columns so each fits where it sits.
        for row in rows:
            if row["kind"] in ("message", "self"):
                row["lines"] = fit_lines(row["label"], LABEL_MAX_W, LABEL_FONT, 2) if row["label"] else []
                row["w"] = max((text_width(s, LABEL_FONT, safe=True) for s in row["lines"]), default=0)
            elif row["kind"] == "note":
                row["lines"] = fit_lines(row["label"], NOTE_MAX_W, NOTE_FONT, 3)
                row["w"] = max((text_width(s, NOTE_FONT, safe=True) for s in row["lines"]), default=0)
            else:
                row["lines"] = [row["label"]] if row["label"] else []
                row["w"] = text_width(row["label"], GAP_FONT, safe=True)

        spacing = [max(COL_MIN, (head_w[i] + head_w[i + 1]) / 2 + 24) for i in range(n - 1)]
        left_need = head_w[0] / 2
        right_need = head_w[-1] / 2

        def need_between(a: int, b: int, width: float) -> None:
            """Grow the gaps between columns a < b until ``width`` fits across them."""
            short = width - sum(spacing[a:b])
            if short > 0:
                for k in range(a, b):
                    spacing[k] += short / (b - a)

        spans: List[Tuple[int, int, float]] = []
        for row in rows:
            if row["kind"] == "message":
                a, b = sorted((col[row["from"]], col[row["to"]]))
                spans.append((a, b, row["w"] + 2 * ARROW_PAD))
            elif row["kind"] == "self":
                i = col[row["at"]]
                reach = LOOP_W + 8 + row["w"] + 12
                if i < n - 1:
                    spans.append((i, i + 1, reach + 12))
                else:
                    right_need = max(right_need, reach)
            elif row["kind"] in ("note", "gap") and (row.get("over") or row.get("breaks")):
                ids = row.get("over") or row.get("breaks")
                a, b = min(col[i] for i in ids), max(col[i] for i in ids)
                chip = row["w"] + 2 * NOTE_PAD
                if a == b:
                    if a > 0:
                        spans.append((a - 1, a, chip / 2 + head_w[a - 1] / 2 + 8))
                    else:
                        left_need = max(left_need, chip / 2)
                    if a < n - 1:
                        spans.append((a, a + 1, chip / 2 + head_w[a + 1] / 2 + 8))
                    else:
                        right_need = max(right_need, chip / 2)
                else:
                    spans.append((a, b, chip - 2 * 20))
        for a, b, width in sorted(spans, key=lambda s: s[1] - s[0]):
            need_between(a, b, width)

        x0 = MARGIN + gutter + left_need
        xs = [x0 + sum(spacing[:i]) for i in range(n)]
        diagram_left, diagram_right = xs[0] - left_need, xs[-1] + right_need
        content_w = diagram_right + MARGIN
        if title:
            content_w = max(content_w, text_width(title, TITLE_FONT, bold=True, safe=True) + 2 * MARGIN)
        width = content_w

        top = MARGIN + (TITLE_H if title else 0)
        y = top + head_h + ROW_TOP
        placed: List[Tuple[Dict[str, Any], float, float]] = []   # row, y_top, height
        for row in rows:
            if row["kind"] == "message":
                h = MSG_H + (len(row["lines"]) - 1) * LABEL_LH
            elif row["kind"] == "self":
                h = SELF_H + max(0, len(row["lines"]) - 1) * LABEL_LH
            elif row["kind"] == "note":
                h = len(row["lines"]) * NOTE_LH + 2 * NOTE_PAD + 14
            else:
                h = GAP_H
            placed.append((row, y, h))
            y += h
        bottom = y + TAIL
        height = bottom + MARGIN

        parts: List[str] = [style(self._css(theme)),
                            defs(self._markers(theme))]
        parts.append(rect(0, 0, width, height, **{"class": "sq-background"}))
        if title:
            parts.append(text(width / 2, MARGIN + 20, title,
                              **{"class": "sq-title", "text-anchor": "middle"}))

        # Lifelines first, interrupted across the gaps that break them.
        lifeline_top = top + head_h
        for p, x in zip(participants, xs):
            cuts = [(ry, ry + rh) for row, ry, rh in placed
                    if row["kind"] == "gap" and p["id"] in row["breaks"]]
            start = lifeline_top
            for c0, c1 in cuts:
                parts.append(line(x, start, x, c0 + 6, **{"class": "sq-lifeline"}))
                parts.append(path(f"M{x - 7},{c0 + 10} L{x + 7},{c0 + 4}", **{"class": "sq-break"}))
                parts.append(path(f"M{x - 7},{c1 - 4} L{x + 7},{c1 - 10}", **{"class": "sq-break"}))
                start = c1 - 6
            parts.append(line(x, start, x, bottom, **{"class": "sq-lifeline"}))

        if gutter and event_label:
            parts.append(text(MARGIN + gutter - 12, top + head_h / 2 + 4, event_label,
                              **{"class": "sq-event-head", "text-anchor": "end"}))

        for p, x, w in zip(participants, xs, head_w):
            box = [rect(x - w / 2, top, w, head_h, rx=theme.radius, **{"class": "sq-head"}),
                   text(x, top + (24 if p["sub"] else 27), p["label"],
                        **{"class": "sq-head-label", "text-anchor": "middle"})]
            if p["sub"]:
                box.append(text(x, top + 45, p["sub"], **{"class": "sq-head-sub", "text-anchor": "middle"}))
            parts.append(titled_group(p["label"] + (f" ({p['sub']})" if p["sub"] else ""), box))

        for row, ry, rh in placed:
            parts.append(self._row(row, ry, rh, xs, col, gutter, theme))

        return svg_document("\n".join(parts), width=round(width), height=round(height),
                            class_name="diagram sequence-diagram")

    # -- pieces ----------------------------------------------------------

    def _row(self, row: Dict[str, Any], y: float, h: float, xs: List[float],
             col: Dict[str, int], gutter: float, theme: DiagramTheme) -> str:
        tone = row["tone"]
        tone_class = f" sq-tone-{tone}" if tone else ""
        out: List[str] = []
        kind = row["kind"]
        if kind == "message":
            xa, xb = xs[col[row["from"]]], xs[col[row["to"]]]
            ay = y + h - 10
            direction = 1 if xb > xa else -1
            label_y = ay - 8 - (len(row["lines"]) - 1) * LABEL_LH
            cls = "sq-arrow sq-dashed" if row["dashed"] else "sq-arrow"
            out.append(line(xa, ay, xb - direction * 2, ay,
                            **{"class": cls + tone_class, "marker-end": f"url(#{self._marker_id(tone)})"}))
            mid = (xa + xb) / 2
            for i, s in enumerate(row["lines"]):
                out.append(text(mid, label_y + i * LABEL_LH, s,
                                **{"class": "sq-label" + tone_class, "text-anchor": "middle"}))
            anchor_y = ay
        elif kind == "self":
            x = xs[col[row["at"]]]
            ly = y + 14
            out.append(path(f"M{x},{ly} h{LOOP_W} v{LOOP_DROP} h{-LOOP_W + 3}",
                            **{"class": "sq-arrow" + tone_class,
                               "marker-end": f"url(#{self._marker_id(tone)})"}))
            for i, s in enumerate(row["lines"]):
                out.append(text(x + LOOP_W + 8, ly + LOOP_DROP / 2 + 5 + i * LABEL_LH, s,
                                **{"class": "sq-label" + tone_class}))
            anchor_y = ly + LOOP_DROP / 2 + 5
        elif kind == "note":
            ids = row["over"]
            a, b = min(col[i] for i in ids), max(col[i] for i in ids)
            chip_w = row["w"] + 2 * NOTE_PAD
            if a != b:
                chip_w = max(chip_w, xs[b] - xs[a] + 40)
            cx = (xs[a] + xs[b]) / 2
            chip_h = len(row["lines"]) * NOTE_LH + 2 * NOTE_PAD
            cy = y + 7
            out.append(rect(cx - chip_w / 2, cy, chip_w, chip_h, rx=4, **{"class": "sq-note" + tone_class}))
            for i, s in enumerate(row["lines"]):
                out.append(text(cx, cy + NOTE_PAD + 13 + i * NOTE_LH, s,
                                **{"class": "sq-note-text", "text-anchor": "middle"}))
            anchor_y = cy + NOTE_PAD + 13
        else:
            ids = row["breaks"]
            if ids:
                a, b = min(col[i] for i in ids), max(col[i] for i in ids)
                cx = (xs[a] + xs[b]) / 2
            else:
                cx = (xs[0] + xs[-1]) / 2
            if row["label"]:
                out.append(text(cx, y + h / 2 + 5, row["label"],
                                **{"class": "sq-gap" + tone_class, "text-anchor": "middle"}))
            anchor_y = y + h / 2 + 5
        if row["event"] is not None and gutter:
            out.append(text(MARGIN + gutter - 12, anchor_y + 4, _event_text(row["event"]),
                            **{"class": "sq-event", "text-anchor": "end"}))
        name = row["label"] or kind
        return "<g>" + svg_title(name) + "".join(out) + "</g>"

    @staticmethod
    def _marker_id(tone: str) -> str:
        return f"sq-arrow-{tone or 'ink'}"

    def _markers(self, theme: DiagramTheme) -> str:
        colours = {"ink": theme.ink, **{t: getattr(theme, t) for t in TONES}}
        return "".join(
            f'<marker id="sq-arrow-{name}" markerWidth="10" markerHeight="10" refX="8" refY="4" '
            f'orient="auto" markerUnits="userSpaceOnUse"><path d="M0,0 L8,4 L0,8 Z" fill="{c}"/></marker>'
            for name, c in colours.items())

    @staticmethod
    def _css(theme: DiagramTheme) -> str:
        tones = "".join(
            f".sq-arrow.sq-tone-{t}{{stroke:{getattr(theme, t)}}}"
            f".sq-label.sq-tone-{t},.sq-gap.sq-tone-{t}{{fill:{getattr(theme, t)}}}"
            f".sq-note.sq-tone-{t}{{stroke:{getattr(theme, t)}}}"
            for t in TONES)
        return (
            f".sq-background{{fill:{theme.background or theme.surface_alt}}}"
            f".sq-title{{font:600 {TITLE_FONT}px sans-serif;fill:{theme.text}}}"
            f".sq-head{{fill:{theme.surface};stroke:{theme.rule};stroke-width:1.2}}"
            f".sq-head-label{{font:600 {HEAD_FONT}px sans-serif;fill:{theme.text}}}"
            f".sq-head-sub{{font:{SUB_FONT}px sans-serif;fill:{theme.muted}}}"
            f".sq-lifeline{{stroke:{theme.rule};stroke-width:1.2;stroke-dasharray:5 4;fill:none}}"
            f".sq-break{{stroke:{theme.muted};stroke-width:1.6;fill:none}}"
            f".sq-arrow{{stroke:{theme.ink};stroke-width:1.6;fill:none}}"
            f".sq-dashed{{stroke-dasharray:6 4}}"
            f".sq-label{{font:{LABEL_FONT}px sans-serif;fill:{theme.text}}}"
            f".sq-note{{fill:{theme.warning_soft};stroke:{theme.warning};stroke-width:1}}"
            f".sq-note-text{{font:{NOTE_FONT}px sans-serif;fill:{theme.text}}}"
            f".sq-gap{{font:italic {GAP_FONT}px sans-serif;fill:{theme.muted}}}"
            f".sq-event{{font:600 {EVENT_FONT}px sans-serif;fill:{theme.accent}}}"
            f".sq-event-head{{font:{SUB_FONT}px sans-serif;fill:{theme.muted}}}"
            + tones
        )
