"""Probability by counting: an outcome grid, and markers cutting a shuffle into gaps.

Two concepts under ``Topic.PROBABILITY``, both for the kind of question that is
answered by *counting equally likely cases* rather than by a process in time:

``probability/outcome_grid``
    Two independent fair dice (any face counts, 2..10 each) as an ``a × b`` grid
    of equally likely outcomes. Events are sets of cells — "the sum is 7",
    "doubles", "the larger die is at least 5" — highlighted in their own colour
    and counted. A ``condition`` phase fades every cell outside the events, which
    is the picture of conditioning: once only those cells can end the game, the
    chance of each is its share of them. That is how "roll until a 7 or a 6:
    which comes first?" becomes 6 cells against 5, so 6/11.

``probability/arrangement_gaps``
    A seeded shuffle of ``total`` items of which ``markers`` are special (the
    aces of a deck). The markers cut the other items into ``markers + 1`` gaps.
    Every non-marker is equally likely to land in each gap, so each gap holds
    ``(total - markers) / (markers + 1)`` on average; the position of the k-th
    marker is k gaps plus k markers. The scene deals one real shuffle, counts its
    gaps, then replays ``runs`` shuffles and shows each gap's running average
    settle on the exact value.

**Every number is computed here, never taken from the caller.** Cell counts,
the conditional probabilities, the gap sizes of the dealt shuffle, the running
averages and the exact expectation all come from the parameters, over
``Fraction`` where they are exact. Caption text may name them as ``str.format``
fields (``{n1}``, ``{p1}``, ``{mean_gap}``…), which are filled in from the
computed facts; a field that does not exist is refused before a render.

**The shuffles are real, and the same every render.** :func:`deal` is seeded,
the showcase deal is the first seed whose gaps are all at least ``min_gap``
(so their counts stay legible; the choice is reported in the facts), and the
running averages are over genuine seeded shuffles. The scene carries the source
of the functions below (:func:`inspect.getsource`), so it draws exactly what
:func:`grid_claims` / :func:`gap_claims` checked.

**Phases, cues and caption cards** work as in ``probability/random_walk_exits``
(see :mod:`straightedge.probability` and ``docs/narration-timing.md``): one beat
per phase, and a moment inside a phase is a cue — a phase name, ``{"phase",
"sentence", "offset"}``, or ``{"phase", "at"}``.

**Safe area.** ``safe_area: "shorts"`` (the default in 9:16) keeps every mark
out of the bottom fifth and the right-hand eighth of a vertical frame, where a
short-video player draws its own buttons and caption. ``"frame"`` uses the whole
frame.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from fractions import Fraction
from typing import Any

from .probability import (
    Card,
    ConceptProbability,
    Cue,
    ProbabilityError,
    _as_float,
    _as_int,
    _check_markup,
    _coerce_cards,
    _plain_label,
    coerce_cue,
    cue_seconds,
)


#: The concept ids live on the topic's one concept class; this alias keeps the
#: module readable on its own.
ConceptCounting = ConceptProbability


SAFE_AREAS = ("shorts", "frame")
#: Colour tokens an event may take. They name the scene palette, not hex values,
#: so a theme re-colours them.
EVENT_COLOURS = ("done", "warn", "hold", "flow", "aux", "warm")
MAX_TITLE = 90


# ================================================================ shared


def _phases(raw: Any, known: tuple, default: tuple, first: str) -> tuple:
    if raw is None:
        return default
    if isinstance(raw, str):
        raw = [x.strip() for x in raw.split(",") if x.strip()]
    phases = tuple(str(x).strip().lower() for x in raw)
    unknown = [x for x in phases if x not in known]
    if unknown:
        raise ProbabilityError(f"unknown phase(s) {unknown}; known: {list(known)}", unknown,
                               param="phases")
    if len(set(phases)) != len(phases):
        raise ProbabilityError("a phase may appear only once", list(phases), param="phases")
    if not phases or phases[0] != first:
        raise ProbabilityError(f"phases must begin with '{first}'", list(phases), param="phases")
    order = [known.index(x) for x in phases]
    if order != sorted(order):
        raise ProbabilityError(f"phases must keep the order {list(known)}", list(phases),
                               param="phases")
    return phases


def _title(raw: Any) -> str:
    text = str(raw or "")
    if len(text) > MAX_TITLE or "\n" in text:
        raise ProbabilityError(f"title must be one line of at most {MAX_TITLE} characters "
                               "(the scene wraps it)", text, param="title")
    return text


class _Missing(dict):
    def __missing__(self, key):
        raise KeyError(key)


def _fill(text: str, fields: dict, name: str) -> str:
    """``text`` with ``{field}`` filled from computed facts; unknown fields refused."""
    try:
        return str(text).format_map(_Missing(fields))
    except KeyError as exc:
        raise ProbabilityError(f"{name}: {{{exc.args[0]}}} is not a computed field; "
                               f"known: {sorted(fields)}", text, param=name) from None
    except (IndexError, ValueError) as exc:
        raise ProbabilityError(f"{name}: {text!r} is not a valid format string ({exc})", text,
                               param=name) from None


def _captions(raw: Any, phases: tuple, fields: dict) -> tuple:
    """``(phase, (Card, ...))`` in phase order, text filled from ``fields``."""
    if not raw:
        return ()
    if not isinstance(raw, dict):
        raise ProbabilityError("captions must map a phase name to its cards", raw, param="captions")
    out = []
    for phase, items in raw.items():
        if phase not in phases:
            raise ProbabilityError(f"caption for '{phase}', which is not one of the phases "
                                   f"{list(phases)}", phase, param="captions")
        if isinstance(items, str):
            items = [items]
        filled = []
        for item in items:
            if isinstance(item, str):
                item = {"text": item}
            if isinstance(item, dict) and "text" in item:
                item = dict(item, text=_fill(item["text"], fields, "captions"))
            filled.append(item)
        out.append((phase, _coerce_cards(filled, phase, phases)))
    order = {ph: k for k, ph in enumerate(phases)}
    return tuple(sorted(out, key=lambda pair: order[pair[0]]))


def _text(raw: Any, default: str, fields: dict, name: str) -> str:
    return _check_markup(_fill(default if raw is None else raw, fields, name))


def _safe_area(raw: Any) -> str:
    value = str(raw or "shorts").strip().lower()
    if value not in SAFE_AREAS:
        raise ProbabilityError(f"safe_area must be one of {list(SAFE_AREAS)}", value,
                               param="safe_area")
    return value


def spans_for(phases: tuple, defaults: dict, beat_seconds: dict | None = None) -> list[float]:
    beats = dict(beat_seconds or {})
    return [float(beats.get(f"b{i + 1:02d}", defaults[ph])) for i, ph in enumerate(phases)]


def phase_starts(spans: list[float]) -> list[float]:
    out, acc = [], 0.0
    for span in spans:
        out.append(acc)
        acc += span
    return out


def _all_cues(m) -> list[Cue]:
    cues = [c for _k, c in m.cues]
    for _phase, cards in m.captions:
        for card in cards:
            cues.append(card.cue)
            if card.until is not None:
                cues.append(card.until)
    return cues


def sentence_counts(m) -> dict[int, int]:
    """Per phase index, the highest sentence any cue names (for unmeasured beats)."""
    counts: dict[int, int] = {}
    for c in _all_cues(m):
        if c.sentence is not None:
            i = m.phases.index(c.phase)
            counts[i] = max(counts.get(i, 1), c.sentence)
    return counts


def cue_time(m, spans: list[float], beat_seconds: dict | None, cue: Cue) -> float:
    i, sentence, offset, at = cue.as_args(m.phases)
    return cue_seconds(phase_starts(spans), spans, dict(beat_seconds or {}), i, sentence, offset,
                       at, sentence_counts(m).get(i, 1))


def _cues(raw: Any, phases: tuple, known: dict) -> tuple:
    """``(key, Cue)`` pairs for the named moments a template understands.

    ``known`` maps each key to the phase it belongs in; a cue for a phase the
    plan does not show is refused, as is one placed in another phase.
    """
    if not raw:
        return ()
    if not isinstance(raw, dict):
        raise ProbabilityError(f"cues must map {sorted(known)} to cues", raw, param="cues")
    out = []
    for key, value in raw.items():
        if key not in known:
            raise ProbabilityError(f"cues: unknown key {key!r}; known: {sorted(known)}", key,
                                   param="cues")
        phase = known[key]
        if phase not in phases:
            raise ProbabilityError(f"cues['{key}'] needs the '{phase}' phase", key, param="cues")
        cue = coerce_cue(value, phases, "cues", phase=phase)
        if cue.phase != phase:
            raise ProbabilityError(f"cues['{key}'] must be a moment in the '{phase}' phase",
                                   value, param="cues")
        out.append((key, cue))
    return tuple(out)


def _ratio(f: Fraction) -> str:
    return str(f.numerator) if f.denominator == 1 else f"{f.numerator}/{f.denominator}"


def _decimal(f: Fraction, places: int) -> str:
    """``f`` to ``places`` decimals, trailing zeros dropped (10.60 → 10.6)."""
    text = f"{float(f):.{places}f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


# ================================================================ outcome grid


GRID_PHASES = ("grid", "events", "condition", "result")
GRID_DEFAULT_PHASES = GRID_PHASES
GRID_DEFAULT_SPANS = {"grid": 7.0, "events": 8.0, "condition": 6.0, "result": 7.0}
GRID_CUE_PHASES = {"grid_until": "grid", "condition": "condition", "result": "result",
                   **{f"event{k}": "events" for k in (1, 2, 3)}}
#: The statistic of a roll ``(a, b)`` an event tests. ``a`` is the row die.
GRID_STATS = ("sum", "difference", "absdiff", "product", "max", "min", "first", "second")
CELL_TEXTS = ("sum", "pair", "none")
MAX_EVENTS = 3
MIN_FACES, MAX_FACES = 2, 10


def grid_stat(stat, a, b):
    """The statistic ``stat`` of the roll ``(a, b)``. Embedded verbatim in the scene."""
    if stat == "sum":
        return a + b
    if stat == "difference":
        return a - b
    if stat == "absdiff":
        return abs(a - b)
    if stat == "product":
        return a * b
    if stat == "max":
        return max(a, b)
    if stat == "min":
        return min(a, b)
    if stat == "first":
        return a
    return b


def event_cells(faces, events):
    """Per event, the cells ``(row, col)`` (0-based) whose roll is in the event."""
    out = []
    for stat, values in events:
        wanted = set(values)
        out.append([(r, c) for r in range(faces[0]) for c in range(faces[1])
                    if grid_stat(stat, r + 1, c + 1) in wanted])
    return out


@dataclass(frozen=True)
class GridEvent:
    stat: str
    values: tuple
    label: str
    colour: str


@dataclass(frozen=True)
class GridModel:
    faces: tuple = (6, 6)
    events: tuple = ()
    phases: tuple = GRID_DEFAULT_PHASES
    cell_text: str = "sum"
    title: str = ""
    row_label: str = ""
    col_label: str = ""
    captions: tuple = ()
    cues: tuple = ()
    condition_text: str = ""
    result_text: str = ""
    safe_area: str = "shorts"
    fields: tuple = ()

    @property
    def beats(self) -> int:
        return len(self.phases)


def _grid_events(raw: Any, faces: tuple) -> list[tuple]:
    if raw is None:
        raw = [{"stat": "sum", "values": [7]}, {"stat": "sum", "values": [6]}]
    if not isinstance(raw, (list, tuple)) or not raw:
        raise ProbabilityError("events must be a non-empty list of {stat, values}", raw,
                               param="events")
    if len(raw) > MAX_EVENTS:
        raise ProbabilityError(f"at most {MAX_EVENTS} events stay distinguishable", len(raw),
                               param="events")
    out = []
    for k, ev in enumerate(raw):
        if not isinstance(ev, dict):
            raise ProbabilityError(f"events[{k}] must be a mapping", ev, param="events")
        bad = set(ev) - {"stat", "values", "label", "colour", "color"}
        if bad:
            raise ProbabilityError(f"events[{k}]: unknown key(s) {sorted(bad)}", ev, param="events")
        stat = str(ev.get("stat", "sum")).strip().lower()
        if stat not in GRID_STATS:
            raise ProbabilityError(f"events[{k}].stat must be one of {list(GRID_STATS)}", stat,
                                   param="events")
        values = ev.get("values")
        if isinstance(values, (int, float)) and not isinstance(values, bool):
            values = [values]
        if not isinstance(values, (list, tuple)) or not values:
            raise ProbabilityError(f"events[{k}].values must be a non-empty list", values,
                                   param="events")
        values = tuple(_as_int(v, "events") for v in values)
        out.append((stat, values, ev))
    return out


def coerce_outcome_grid(params: dict | None) -> GridModel:
    """Validate parameters into a :class:`GridModel`, refusing with the culprit."""
    params = dict(params or {})
    faces = params.get("faces", (6, 6))
    if isinstance(faces, (int, float)) and not isinstance(faces, bool):
        faces = (faces, faces)
    try:
        faces = (_as_int(faces[0], "faces"), _as_int(faces[1], "faces"))
    except (TypeError, IndexError, KeyError):
        raise ProbabilityError("faces must be a pair (rows, columns)", faces, param="faces") from None
    if not all(MIN_FACES <= f <= MAX_FACES for f in faces):
        raise ProbabilityError(f"each die must have {MIN_FACES}..{MAX_FACES} faces so every cell "
                               "stays legible", faces, param="faces")
    phases = _phases(params.get("phases"), GRID_PHASES, GRID_DEFAULT_PHASES, "grid")
    if any(p in phases for p in ("condition", "result")) and "events" not in phases:
        raise ProbabilityError("'condition' and 'result' need the 'events' phase", list(phases),
                               param="phases")
    raw_events = _grid_events(params.get("events"), faces)
    cells = event_cells(faces, [(s, v) for s, v, _ in raw_events])
    for k, found in enumerate(cells):
        if not found:
            raise ProbabilityError(f"events[{k}] contains no outcome of a {faces[0]}×{faces[1]} "
                                   "roll; there is nothing to highlight", raw_events[k][1],
                                   param="events")
    seen: dict = {}
    for k, found in enumerate(cells):
        for cell in found:
            if cell in seen:
                raise ProbabilityError(
                    f"events[{seen[cell]}] and events[{k}] share the roll {cell[0] + 1}, "
                    f"{cell[1] + 1}; overlapping events have no single colour and no 'which "
                    "comes first'", cell, param="events")
            seen[cell] = k
    fields = grid_fields(faces, cells)
    events = []
    for k, (stat, values, ev) in enumerate(raw_events):
        colour = str(ev.get("colour", ev.get("color", EVENT_COLOURS[k]))).strip().lower()
        if colour not in EVENT_COLOURS:
            raise ProbabilityError(f"events[{k}].colour must be one of {list(EVENT_COLOURS)}",
                                   colour, param="events")
        default = f"{stat} {'/'.join(str(v) for v in values)}: {{n{k + 1}}}"
        label = _plain_label(_text(ev.get("label"), default, fields, "events"), "events")
        events.append(GridEvent(stat, values, label, colour))
    cell_text = str(params.get("cell_text", "sum")).strip().lower()
    if cell_text not in CELL_TEXTS:
        raise ProbabilityError(f"cell_text must be one of {list(CELL_TEXTS)}", cell_text,
                               param="cell_text")
    if "condition" not in phases and params.get("condition_text"):
        raise ProbabilityError("condition_text needs the 'condition' phase", "condition_text",
                               param="condition_text")
    if "result" not in phases and params.get("result_text"):
        raise ProbabilityError("result_text needs the 'result' phase", "result_text",
                               param="result_text")
    condition_text = _text(params.get("condition_text"), "{n_all} of {total} rolls matter",
                           fields, "condition_text") if "condition" in phases else ""
    default_result = ("{n1} / ({n1} + {n2}) = <b>{p1}</b>" if len(events) == 2
                      else "{n1} / {n_all} = <b>{p1}</b>")
    result_text = _text(params.get("result_text"), default_result,
                        fields, "result_text") if "result" in phases else ""
    return GridModel(
        faces=faces, events=tuple(events), phases=phases, cell_text=cell_text,
        title=_title(params.get("title")),
        row_label=_plain_label(params.get("row_label", ""), "row_label"),
        col_label=_plain_label(params.get("col_label", ""), "col_label"),
        captions=_captions(params.get("captions"), phases, fields),
        cues=_cues(params.get("cues"), phases,
                   {k: v for k, v in GRID_CUE_PHASES.items()
                    if not (k.startswith("event") and int(k[5:]) > len(events))}),
        condition_text=condition_text, result_text=result_text,
        safe_area=_safe_area(params.get("safe_area")),
        fields=tuple(sorted(fields.items())),
    )


def grid_fields(faces: tuple, cells: list) -> dict:
    """Every number a grid caption may name, computed exactly."""
    total = faces[0] * faces[1]
    counts = [len(c) for c in cells]
    n_all = sum(counts)
    fields: dict[str, Any] = {"total": total, "n_all": n_all, "rows": faces[0], "cols": faces[1],
                              "rest": total - n_all}
    for k, n in enumerate(counts, start=1):
        race = Fraction(n, n_all)
        fields[f"n{k}"] = n
        fields[f"p{k}"] = _ratio(race)                       # P(event k comes first)
        fields[f"p{k}_decimal"] = _decimal(race, 3)
        fields[f"q{k}"] = _ratio(Fraction(n, total))          # P(event k on one roll), reduced
        fields[f"q{k}_raw"] = f"{n}/{total}"                  # the same, as counted
    return fields


def grid_claims(m: GridModel, beat_seconds: dict | None = None) -> dict:
    """The facts the grid shows, and a check that its moments are in order."""
    cells = event_cells(m.faces, [(e.stat, e.values) for e in m.events])
    total = m.faces[0] * m.faces[1]
    counts = [len(c) for c in cells]
    n_all = sum(counts)
    spans = spans_for(m.phases, GRID_DEFAULT_SPANS, beat_seconds)
    times = grid_times(m, spans, beat_seconds)
    starts = phase_starts(spans)
    if "events" in m.phases:
        i = m.phases.index("events")
        t0, t1 = starts[i], starts[i] + spans[i]
        ev = times["events"]
        if ev != sorted(ev) or not all(t0 <= t <= t1 for t in ev):
            raise ProbabilityError(f"event cues must be in order inside the events phase "
                                   f"({t0:.2f}s..{t1:.2f}s); got {[round(t, 2) for t in ev]}",
                                   ev, param="cues")
    return {
        "spans": spans,
        "total": total,
        "cells": [[list(c) for c in found] for found in cells],
        "counts": counts,
        "n_all": n_all,
        "p_single": [str(Fraction(n, total)) for n in counts],
        "p_first": [str(Fraction(n, n_all)) for n in counts],
        "p_neither": str(Fraction(total - n_all, total)),
        "times": times,
        "fields": dict(m.fields),
    }


def grid_times(m: GridModel, spans: list[float], beat_seconds: dict | None) -> dict:
    """Scene times of the grid's moments (defaults where no cue is given)."""
    starts = phase_starts(spans)
    cues = dict(m.cues)

    def at(key, phase, frac):
        if key in cues:
            return cue_time(m, spans, beat_seconds, cues[key])
        i = m.phases.index(phase)
        return starts[i] + frac * spans[i]

    out: dict[str, Any] = {"grid_until": at("grid_until", "grid", 0.55)}
    if "events" in m.phases:
        n = len(m.events)
        out["events"] = [at(f"event{k + 1}", "events", 0.08 + 0.84 * k / max(n, 1))
                         for k in range(n)]
    if "condition" in m.phases:
        out["condition"] = at("condition", "condition", 0.05)
    if "result" in m.phases:
        out["result"] = at("result", "result", 0.05)
    return out


# ================================================================ arrangement gaps


GAP_PHASES = ("deal", "gaps", "average", "focus")
GAP_DEFAULT_PHASES = GAP_PHASES
GAP_DEFAULT_SPANS = {"deal": 8.0, "gaps": 6.0, "average": 10.0, "focus": 8.0}
#: ``average_from`` the bars appear at this deal's gaps; ``target`` the dashed
#: line at the exact mean; ``shuffle_from``..``average_until`` the replayed
#: shuffles run; ``focus`` the wait is outlined; ``focus_sum`` the markers are
#: added on top and the sum is written out.
GAP_CUE_PHASES = {"deal_until": "deal", "gaps_from": "gaps", "gaps_until": "gaps",
                  "average_from": "average", "target": "average", "shuffle_from": "average",
                  "average_until": "average", "focus": "focus", "focus_sum": "focus"}
MIN_TOTAL, MAX_TOTAL = 4, 60        # a row of 60 is ~14 px a card at 1080 wide
MAX_MARKERS = 8
MIN_RUNS, MAX_RUNS = 100, 200000
DEAL_TRIES = 100000


def deal(total, markers, seed):
    """One seeded shuffle: a list of ``total`` flags, True where a marker landed."""
    order = [k < markers for k in range(total)]
    random.Random(seed).shuffle(order)
    return order


def gap_sizes(order):
    """How many non-markers sit before the first marker, between each pair, and after the last."""
    sizes = [0]
    for is_marker in order:
        if is_marker:
            sizes.append(0)
        else:
            sizes[-1] += 1
    return sizes


def choose_deal(total, markers, seed, min_gap, tries=100000, max_gap=None):
    """``(seed_used, order)``: the first seed from ``seed`` whose gaps all lie in
    ``min_gap..max_gap`` (``max_gap`` None: no upper bound)."""
    for k in range(tries):
        order = deal(total, markers, seed + k)
        sizes = gap_sizes(order)
        if min(sizes) >= min_gap and (max_gap is None or max(sizes) <= max_gap):
            return seed + k, order
    return None, None


def running_means(total, markers, seed, runs, first):
    """Running mean of every gap over ``runs`` seeded shuffles, the first being ``first``.

    Returns ``(checkpoints, means)``: ``means[j]`` is the list of gap averages
    after ``checkpoints[j]`` shuffles. Checkpoints are dense early and sparse
    late, so the scene can draw any moment without storing every shuffle.
    """
    gaps = markers + 1
    sums = [0] * gaps
    rng = random.Random(seed * 7919 + 15485863)
    order = [k < markers for k in range(total)]
    checkpoints, means = [], []
    marks = set(range(1, min(runs, 200) + 1))
    x = 200
    while x < runs:                 # then about 2% apart: ~350 checkpoints for 10^5 runs
        x = int(x * 1.02) + 1
        marks.add(min(x, runs))
    marks.add(runs)
    for r in range(1, runs + 1):
        if r == 1:
            current = list(first)
        else:
            rng.shuffle(order)
            current = order
        for g, size in enumerate(gap_sizes(current)):
            sums[g] += size
        if r in marks:
            checkpoints.append(r)
            means.append([s / r for s in sums])
    return checkpoints, means


@dataclass(frozen=True)
class GapModel:
    total: int = 52
    markers: int = 4
    seed: int = 1
    min_gap: int = 2
    #: Upper bound on every gap of the showcase deal, so one long gap does not
    #: squash the bar chart. ``None``: no bound.
    max_gap: int | None = None
    runs: int = 20000
    focus: int = 1
    phases: tuple = GAP_DEFAULT_PHASES
    title: str = ""
    marker_label: str = "A"
    gap_label: str = "gap {k}"
    counter_text: str = ""
    target_text: str = ""
    focus_text: str = ""
    captions: tuple = ()
    cues: tuple = ()
    ease: str = "slow_start"
    safe_area: str = "shorts"
    fields: tuple = ()

    @property
    def beats(self) -> int:
        return len(self.phases)


def gap_fields(total: int, markers: int, focus: int) -> dict:
    """Every number a gaps caption may name, computed exactly."""
    other = total - markers
    gaps = markers + 1
    mean_gap = Fraction(other, gaps)
    answer = focus * (mean_gap + 1)
    return {
        "total": total, "markers": markers, "other": other, "gaps": gaps, "focus": focus,
        "mean_gap": _ratio(mean_gap), "mean_gap_decimal": _decimal(mean_gap, 3),
        "answer": _ratio(answer), "answer_decimal": _decimal(answer, 3),
        "focus_gaps": _decimal(focus * mean_gap, 3),
    }


def coerce_arrangement_gaps(params: dict | None) -> GapModel:
    """Validate parameters into a :class:`GapModel`, refusing with the culprit."""
    params = dict(params or {})
    d = GapModel()
    total = _as_int(params.get("total", d.total), "total")
    if not MIN_TOTAL <= total <= MAX_TOTAL:
        raise ProbabilityError(f"total must be {MIN_TOTAL}..{MAX_TOTAL} so the row of items "
                               "stays legible", total, param="total")
    markers = _as_int(params.get("markers", d.markers), "markers")
    if not 1 <= markers <= min(MAX_MARKERS, total - 1):
        raise ProbabilityError(f"markers must be 1..{min(MAX_MARKERS, total - 1)}: at least one "
                               "marker and at least one other item", markers, param="markers")
    seed = _as_int(params.get("seed", d.seed), "seed")
    min_gap = _as_int(params.get("min_gap", d.min_gap), "min_gap")
    if min_gap < 0 or min_gap * (markers + 1) > total - markers:
        raise ProbabilityError(f"min_gap={min_gap} is impossible: {markers + 1} gaps of at least "
                               f"{min_gap} need {min_gap * (markers + 1)} items, there are "
                               f"{total - markers}", min_gap, param="min_gap")
    max_gap = params.get("max_gap")
    if max_gap is not None:
        max_gap = _as_int(max_gap, "max_gap")
        if max_gap < max(min_gap, 0) or max_gap * (markers + 1) < total - markers:
            raise ProbabilityError(f"max_gap={max_gap} is impossible: {markers + 1} gaps of at "
                                   f"most {max_gap} hold fewer than the {total - markers} items "
                                   "(or it is below min_gap)", max_gap, param="max_gap")
    runs = _as_int(params.get("runs", d.runs), "runs")
    phases = _phases(params.get("phases"), GAP_PHASES, GAP_DEFAULT_PHASES, "deal")
    if "average" in phases and not MIN_RUNS <= runs <= MAX_RUNS:
        raise ProbabilityError(f"runs must be {MIN_RUNS}..{MAX_RUNS}", runs, param="runs")
    focus = _as_int(params.get("focus", d.focus), "focus")
    if not 1 <= focus <= markers:
        raise ProbabilityError(f"focus is which marker to wait for, 1..{markers}", focus,
                               param="focus")
    ease = str(params.get("ease", d.ease)).strip().lower()
    if ease not in ("linear", "slow_start"):
        raise ProbabilityError("ease must be 'linear' or 'slow_start'", ease, param="ease")
    fields = gap_fields(total, markers, focus)
    gap_label = str(params.get("gap_label", d.gap_label))
    try:
        _plain_label(gap_label.format(k=markers + 1), "gap_label")
    except (KeyError, IndexError, ValueError):
        raise ProbabilityError("gap_label may use only {k}", gap_label, param="gap_label") from None
    for key, phase in (("counter_text", "average"), ("target_text", "average"),
                       ("focus_text", "focus")):
        if phase not in phases and params.get(key):
            raise ProbabilityError(f"{key} needs the '{phase}' phase", key, param=key)
    counter = str(params.get("counter_text", "after {k} shuffles"))
    try:
        counter.format(k="1,000")
    except (KeyError, IndexError, ValueError):
        raise ProbabilityError("counter_text may use only {k}", counter,
                               param="counter_text") from None
    return GapModel(
        total=total, markers=markers, seed=seed, min_gap=min_gap, max_gap=max_gap, runs=runs,
        focus=focus,
        phases=phases, title=_title(params.get("title")),
        marker_label=_plain_label(params.get("marker_label", d.marker_label), "marker_label"),
        gap_label=gap_label, counter_text=_check_markup(counter),
        target_text=_text(params.get("target_text"), "{mean_gap_decimal}", fields, "target_text"),
        focus_text=_text(params.get("focus_text"), "{focus_gaps} + {focus} = <b>{answer_decimal}</b>",
                         fields, "focus_text"),
        captions=_captions(params.get("captions"), phases, fields),
        cues=_cues(params.get("cues"), phases, GAP_CUE_PHASES),
        ease=ease, safe_area=_safe_area(params.get("safe_area")),
        fields=tuple(sorted(fields.items())),
    )


def gap_times(m: GapModel, spans: list[float], beat_seconds: dict | None) -> dict:
    starts = phase_starts(spans)
    cues = dict(m.cues)

    def at(key, phase, frac):
        if key in cues:
            return cue_time(m, spans, beat_seconds, cues[key])
        i = m.phases.index(phase)
        return starts[i] + frac * spans[i]

    out = {"deal_until": at("deal_until", "deal", 0.6)}
    if "gaps" in m.phases:
        out["gaps_from"] = at("gaps_from", "gaps", 0.1)
        out["gaps_until"] = at("gaps_until", "gaps", 0.6)
    if "average" in m.phases:
        out["average_from"] = at("average_from", "average", 0.12)
        out["target"] = (cue_time(m, spans, beat_seconds, cues["target"]) if "target" in cues
                         else out["average_from"] + 0.9)
        out["shuffle_from"] = (cue_time(m, spans, beat_seconds, cues["shuffle_from"])
                               if "shuffle_from" in cues else out["target"])
        out["average_until"] = at("average_until", "average", 0.8)
    if "focus" in m.phases:
        out["focus"] = at("focus", "focus", 0.05)
        out["focus_sum"] = at("focus_sum", "focus", 0.4)
    return out


def exact_marker_position(total: int, markers: int, focus: int) -> Fraction:
    """E[position of the ``focus``-th marker], summed directly over its distribution.

    Independent of the gap argument: P(it is at position k) is
    C(k-1, focus-1) · C(total-k, markers-focus) / C(total, markers).
    """
    from math import comb

    denom = comb(total, markers)
    return sum(Fraction(k * comb(k - 1, focus - 1) * comb(total - k, markers - focus), denom)
               for k in range(1, total + 1))


def gap_claims(m: GapModel, beat_seconds: dict | None = None) -> dict:
    """Deal the showcase shuffle, run the averages, and check what will be drawn."""
    seed_used, order = choose_deal(m.total, m.markers, m.seed, m.min_gap, DEAL_TRIES, m.max_gap)
    if order is None:
        raise ProbabilityError(f"no shuffle within {DEAL_TRIES} seeds from {m.seed} has every gap "
                               f"in {m.min_gap}..{m.max_gap}", (m.min_gap, m.max_gap),
                               param="max_gap" if m.max_gap is not None else "min_gap")
    sizes = gap_sizes(order)
    assert sum(sizes) == m.total - m.markers and len(sizes) == m.markers + 1
    other = m.total - m.markers
    mean_gap = Fraction(other, m.markers + 1)
    answer = m.focus * (mean_gap + 1)
    exact = exact_marker_position(m.total, m.markers, m.focus)
    if exact != answer:  # pragma: no cover - a theorem; guards a future edit
        raise ProbabilityError(f"gap argument gives {answer}, direct sum gives {exact}", exact)
    spans = spans_for(m.phases, GAP_DEFAULT_SPANS, beat_seconds)
    times = gap_times(m, spans, beat_seconds)
    starts = phase_starts(spans)
    order_ok = [times["deal_until"]]
    for key in ("gaps_from", "gaps_until", "average_from", "target", "shuffle_from",
                "average_until", "focus", "focus_sum"):
        if key in times:
            order_ok.append(times[key])
    if order_ok != sorted(order_ok):
        raise ProbabilityError(f"gap cues must run in order; got "
                               f"{[round(t, 2) for t in order_ok]}", order_ok, param="cues")
    if not 0.0 < times["deal_until"] <= starts[0] + spans[0]:
        raise ProbabilityError("the deal must finish inside the deal phase", times["deal_until"],
                               param="cues")
    facts: dict[str, Any] = {
        "spans": spans, "times": times, "seed_used": seed_used,
        "order": order, "marker_positions": [k + 1 for k, x in enumerate(order) if x],
        "gap_sizes": sizes, "first_marker_at": order.index(True) + 1,
        "mean_gap": str(mean_gap), "answer": str(answer), "answer_float": float(answer),
        "fields": dict(m.fields),
    }
    if "average" in m.phases:
        checkpoints, means = running_means(m.total, m.markers, m.seed, m.runs, order)
        final = means[-1]
        facts.update({
            "runs": m.runs, "final_means": final,
            "max_deviation": max(abs(x - float(mean_gap)) for x in final),
            "checkpoints": len(checkpoints),
            "first_means": means[0],
        })
        assert checkpoints[-1] == m.runs and means[0] == [float(s) for s in sizes]
    return facts
