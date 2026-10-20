"""Probability: a token on a line that walks until it falls off one end.

This is the topic module for ``Topic.PROBABILITY`` in the animation lane. Its
first concept is the picture behind gambler's ruin, first-step analysis and every
"expected time to absorption" interview question: a random walk on
``0, 1, …, N`` that starts at ``i``, steps up with probability ``p`` and down
with ``q = 1 - p``, and stops the moment it reaches ``0`` or ``N``.

**The walk is real, and the same walk every render.** Paths come from
:func:`walk_path` with a seed, so a lecture and its re-render show the same
path, and every claim about that path — it starts at ``i``, every step is ±1, it
stays strictly inside until its last step, it ends on an absorbing end, the
tally counts what was drawn — is checked by :func:`walk_claims` before a frame is
drawn. Nothing is drawn by hand to look random.

**Why the path is chosen at render time.** A narrated walk has to hit its end on
the sentence that says the game stops, and that sentence's length is only known
once it has been spoken. So the scene carries the *source* of the three walk
functions below (via :func:`inspect.getsource`, so there is one copy of the
logic, not two that can drift) and picks the path with the measured beat lengths
in hand: the first seed, counting up from ``seed``, whose walk takes a number of
steps that puts each step between ``step_seconds`` bounds and wanders at least a
little. Deterministic given the narration; testable here with any timing.

**Phases.** Each phase is one beat, so a slide's narration turns map onto them
one to one:

``walk``    the token starts moving along the line (always first);
``ends``    the two ends are labelled — broke at ``0``, everything at ``N``;
``steps``   the up/down probabilities are marked on the token;
``absorb``  the walk reaches an end and freezes (required);
``renewal`` the finished walk is cut into blocks at each return to a set of
            *renewal states* and the blocks are counted off one at a time — the
            picture of a first-step / renewal argument ("from one away, each
            pair of flips escapes with chance 1/4 or puts you back");
``tally``   many walks replay from the same start and a statistic of them is
            tracked: which end each reached (the ruin frequency), the running
            mean of their lengths, or a histogram of their lengths.

A lecture that wants fewer beats names fewer phases; ``walk`` and ``absorb`` are
the minimum, because a walk that is never seen to stop shows nothing about
absorption.

**Sentences inside a phase.** A phase is one beat, but a long beat is several
sentences, and a visual event often belongs to one of them — the takeaway card
enters *with* the takeaway, the tally finishes *before* its result is read out.
Anything here that happens at a moment takes a **cue**: a phase name (its
start), or ``{"phase": ..., "sentence": k, "offset": s}`` (``s`` seconds after
the ``k``-th sentence of that phase starts), or ``{"phase": ..., "at": f}``
(fraction ``f`` of the phase). Sentence starts arrive with the beat lengths as
``"bNN.sK"`` keys; see ``docs/narration-timing.md``. Unmeasured, a sentence cue
falls back to an even split of its phase, so a silent render still runs.

**Defaults draw what they always drew.** Every parameter below added after the
first release defaults to the picture that release made.
"""
from __future__ import annotations

import random
import re
from dataclasses import dataclass
from typing import Any

from .models import Topic
from .topics import topic


class ConceptProbability:
    """Sub-topic identifiers under ``Topic.PROBABILITY``."""

    RANDOM_WALK_EXITS = "probability/random_walk_exits"


class ProbabilityError(ValueError):
    """The parameters cannot honestly produce the requested picture.

    ``param`` names the offending parameter and ``witness`` the value that shows
    why, so a refusal is something a caller can fix rather than a shrug.
    """

    def __init__(self, message: str, witness: Any = None, *, param: str | None = None) -> None:
        super().__init__(message)
        self.witness = witness
        self.param = param


#: Words that route a prompt here. Chinese first, as the router is.
RANDOM_WALK_KEYWORDS = ("随机游走", "赌徒破产", "吸收壁", "吸收态", "破产概率",
                        "random walk", "gambler's ruin", "gamblers ruin",
                        "absorbing barrier", "ruin probability")


@topic(Topic.PROBABILITY, keywords=RANDOM_WALK_KEYWORDS, priority=15)
class Probability:
    """Random processes whose outcome is decided by where they stop."""

    concepts = ConceptProbability


PHASES = ("walk", "ends", "steps", "absorb", "renewal", "tally")
#: The phases a plan gets when it names none — the original five. ``renewal``
#: is opt-in: it only makes sense when the narration argues from returns.
DEFAULT_PHASES = ("walk", "ends", "steps", "absorb", "tally")

#: Beat lengths used when no narration has been measured — a silent render, the
#: CLI, a preview. Close to what one spoken sentence per phase takes.
DEFAULT_SPANS = {"walk": 9.0, "ends": 11.0, "steps": 10.0, "absorb": 10.0, "renewal": 20.0,
                 "tally": 12.0}

#: Where in the ``absorb`` beat the walk reaches its end. Early enough that the
#: freeze is on screen while the sentence about stopping is still being said.
ABSORB_AT = 0.45

MIN_N, MAX_N = 3, 20            # tick labels stay legible up to 20 positions
MAX_RUNS = 120                  # replayed walks the tally can draw and count
MIN_TALLY_RUNS = 10             # fewer and the share is noise, not a frequency
MIN_P, MAX_P = 0.05, 0.95       # beyond these one end is effectively unreachable
MIN_TURNS = 4                   # a showcase walk must visibly change direction
PATH_CAP = 4000                 # steps before a walk is treated as runaway
SEED_TRIES = 20000
TALLY_SEED_STRIDE = 104729      # tally seeds live far from showcase seeds
MAX_CUE_OFFSET = 30.0           # seconds a cue may sit away from its sentence

TALLY_STATS = ("end", "mean", "histogram")
TALLY_EASES = ("linear", "slow_start")
LAYOUTS = ("classic", "adaptive")
AXIS_LABEL_KEYS = ("low", "high", "start")
FADE_KEYS = ("ends", "axis", "title")
RENEWAL_TEXT_KEYS = ("level", "count", "out", "average")
RENEWAL_CUE_KEYS = ("first", "blocks", "done")
#: Optional renewal moments, drawn only when cued.
RENEWAL_OPTIONAL_CUES = ("average",)

#: Fields each tally readout may use, and the text it shows by default. The
#: ``end`` defaults are the strings the first release drew.
TALLY_TEXT_FIELDS = {"zero": ("count", "runs"), "top": ("count", "runs"),
                     "count": ("k", "runs"), "stat": ("k", "runs", "mean", "median")}
TALLY_TEXT_DEFAULTS = {"zero": "reached 0   {count} of {runs}",
                       "top": "reached N   {count} of {runs}",
                       "count": "walks  {k} of {runs}",
                       "stat": "average  {mean:.2f} steps"}
RENEWAL_TEXT_FIELDS = {"level": (), "count": ("k", "blocks"), "out": ("k", "blocks"),
                       "average": ("mean",)}
RENEWAL_TEXT_DEFAULTS = {"level": "", "count": "block {k}: back again",
                         "out": "block {k}: out", "average": "average {mean:g}"}


@dataclass(frozen=True)
class Cue:
    """A moment in the scene, named by phase and, optionally, by sentence.

    ``sentence`` counts from 1 within the phase; ``offset`` is seconds after the
    sentence (or phase) starts and may be negative; ``at`` is a fraction of the
    phase and excludes ``sentence``. Resolved by :func:`cue_seconds`.
    """

    phase: str
    sentence: int | None = None
    offset: float = 0.0
    at: float | None = None

    def as_args(self, phases: tuple) -> tuple:
        """``(index, sentence, offset, at)`` — what the scene's resolver takes."""
        return (phases.index(self.phase), self.sentence, self.offset, self.at)


@dataclass(frozen=True)
class Card:
    """One caption card. ``build`` keeps the cards before it on screen."""

    text: str
    cue: Cue
    build: bool = False
    until: Cue | None = None


@dataclass(frozen=True)
class WalkModel:
    n: int = 10
    start: int = 4
    p: float = 0.5
    seed: int = 7
    exit: str = "any"                     # "any" | "zero" | "top"
    runs: int = 40
    phases: tuple = DEFAULT_PHASES
    low_label: str = "broke"
    high_label: str = "everything in play"
    title: str = ""
    step_seconds: tuple = (0.45, 0.9)
    #: Fraction of the ``absorb`` beat at which the walk reaches its end. Set it
    #: to where the sentence says so: early for "it reaches an end and freezes,
    #: and here is why", late for a sentence that builds up to the stop.
    absorb_at: float = ABSORB_AT
    #: Optional caption per phase, drawn along the bottom while that phase runs.
    #: Pango markup — ``<i>``, ``<b>``, ``<sub>``, ``<sup>`` — so notation like
    #: R<sub>i</sub> reads as notation without needing LaTeX on the render host.
    captions: tuple = ()
    #: Replaces the position labels: ``low`` (default ``0``), ``high``
    #: (``N = n``) and ``start`` (``i``). A puzzle about distance from the start
    #: wants ``−3 / +3 / start``; the default is gambler's-ruin notation.
    axis_labels: tuple = ()
    #: ``(which, Cue)`` pairs: fade the end labels (``ends``), the position
    #: labels (``axis``) or the title out at that cue. Default: they stay.
    labels_until: tuple = ()
    #: Ask for a showcase walk of exactly this many steps, so the narration can
    #: say how long it is before anything is rendered. ``None``: chosen by pace.
    showcase_steps: int | None = None
    #: ``classic`` is the first release's frame. ``adaptive`` re-lays a 9:16
    #: frame: a taller plot, a larger title wrapped to two lines, readouts in the
    #: band above the plot and larger captions below it. Landscape is unchanged.
    layout: str = "classic"
    #: Positions a renewal block ends on. Default: one step either side of start.
    renewal_states: tuple = ()
    #: ``(key, Cue)`` for ``first`` (the approach is marked), ``blocks`` (the
    #: first block is counted) and ``done`` (the last one is); and, only if
    #: cued, ``average`` — a line at the exact expected length on the walk's
    #: own time axis, so "this one took 21, the average is 9" is one picture.
    renewal_cues: tuple = ()
    #: ``(key, text)`` for ``level`` (label on each renewal line), ``count`` and
    #: ``out`` (the counter while blocks return, and on the block that escapes).
    renewal_text: tuple = ()
    tally_stat: str = "end"
    #: A dashed line at this many steps on the fan, for ``mean``/``histogram``.
    tally_target: float | None = None
    tally_target_label: str = ""
    tally_from: Cue | None = None
    #: When the last walk lands. Default: 2.2 s before the phase ends.
    tally_until: Cue | None = None
    tally_ease: str = "linear"
    tally_text: tuple = ()
    #: Label for a step-count axis under the tally fan; empty draws none.
    step_axis: str = ""

    @property
    def beats(self) -> int:
        return len(self.phases)

    def text_for(self, table: tuple, defaults: dict, key: str) -> str:
        return dict(table).get(key, defaults[key])

    def renewal_set(self) -> tuple:
        if self.renewal_states:
            return tuple(self.renewal_states)
        return tuple(x for x in (self.start - 1, self.start + 1) if 0 < x < self.n)


# ------------------------------------------------------------ embedded logic
#
# The three functions below are copied verbatim into the generated scene with
# inspect.getsource. They may use only `random` and builtins.


def walk_path(start, n, p, seed, cap=4000):
    """Positions from ``start`` until the walk reaches 0 or ``n``, inclusive.

    ``None`` if it has not been absorbed within ``cap`` steps, which for the
    bounded ``p`` and ``n`` this module allows does not happen in practice but
    must not hang a render if it ever did.
    """
    rng = random.Random(seed)
    pos = start
    path = [pos]
    while 0 < pos < n:
        pos += 1 if rng.random() < p else -1
        path.append(pos)
        if len(path) > cap:
            return None
    return path


def choose_showcase(start, n, p, seed, exit_side, walking_seconds, lo, hi,
                    min_turns=4, tries=20000, cap=4000):
    """``(seed_used, path, in_range)`` for the walk to narrate over.

    The first seed from ``seed`` upward whose walk ends on the requested side,
    changes direction at least ``min_turns`` times, and takes a step count that
    makes each step last between ``lo`` and ``hi`` seconds when the walk fills
    ``walking_seconds``. If none does, the valid walk whose pace is nearest the
    middle of the range, with ``in_range`` False — still a true walk, just paced
    outside the preferred band.
    """
    target = walking_seconds / ((lo + hi) / 2.0)
    best = None
    for k in range(tries):
        path = walk_path(start, n, p, seed + k, cap)
        if path is None:
            continue
        if exit_side == "zero" and path[-1] != 0:
            continue
        if exit_side == "top" and path[-1] != n:
            continue
        turns = sum(1 for a, b, c in zip(path, path[1:], path[2:]) if (b - a) != (c - b))
        if turns < min_turns:
            continue
        steps = len(path) - 1
        per = walking_seconds / steps
        if lo <= per <= hi:
            return seed + k, path, True
        score = abs(steps - target)
        if best is None or score < best[0]:
            best = (score, seed + k, path)
    if best is None:
        return None, None, False
    return best[1], best[2], False


def showcase_of_length(start, n, p, seed, exit_side, steps, walking_seconds, lo, hi,
                       min_turns=4, tries=20000, cap=4000):
    """``(seed_used, path, in_range)`` for a showcase walk of exactly ``steps`` steps.

    The first seed from ``seed`` upward whose walk ends on the requested side,
    changes direction at least ``min_turns`` times, and is that long. The choice
    does not depend on the narration's timing, so a script can state the walk's
    length before anything is rendered; ``in_range`` reports whether filling
    ``walking_seconds`` paces it inside ``lo``..``hi``. ``(None, None, False)``
    if no seed within ``tries`` has that length.
    """
    for k in range(tries):
        path = walk_path(start, n, p, seed + k, cap)
        if path is None or len(path) - 1 != steps:
            continue
        if exit_side == "zero" and path[-1] != 0:
            continue
        if exit_side == "top" and path[-1] != n:
            continue
        turns = sum(1 for a, b, c in zip(path, path[1:], path[2:]) if (b - a) != (c - b))
        if turns < min_turns:
            continue
        return seed + k, path, lo <= walking_seconds / steps <= hi
    return None, None, False


def tally_paths(start, n, p, seed, runs, stride=104729, cap=4000):
    """``runs`` independent walks from ``start``, for the frequency count."""
    out = []
    k = 0
    while len(out) < runs and k < runs * 4 + 16:
        path = walk_path(start, n, p, seed * 31 + stride + k, cap)
        k += 1
        if path is not None:
            out.append(path)
    return out


def cue_seconds(starts, spans, beats, index, sentence=None, offset=0.0, at=None, count=1):
    """Scene time of a cue: phase ``index``, its ``sentence``-th sentence, plus ``offset``.

    ``beats`` is the beat map; a sentence start is its ``"bNN.sK"`` entry, in
    seconds from the beat's start. Unmeasured, sentence ``k`` of ``count`` falls
    at ``(k - 1) / count`` of the phase, so a silent render still lays out.
    ``at`` is a fraction of the phase instead. Clamped to the scene.
    """
    t = starts[index]
    if at is not None:
        t += at * spans[index]
    elif sentence is not None:
        key = "b%02d.s%d" % (index + 1, sentence)
        if key in beats:
            t += float(beats[key])
        else:
            t += spans[index] * (sentence - 1) / max(count, 1)
    t += offset
    return min(max(t, 0.0), starts[-1] + spans[-1])


def renewal_blocks(path, states):
    """``(first, ends)``: where a walk first enters ``states``, and where each block ends.

    A block runs from one visit to ``states`` to the next, and the last one ends
    where the walk is absorbed. ``first`` is ``None`` if the walk is absorbed
    without ever visiting them, which leaves nothing to count.
    """
    marks = set(states)
    first = None
    for k, x in enumerate(path[:-1]):
        if x in marks:
            first = k
            break
    if first is None:
        return None, []
    ends = [k for k in range(first + 1, len(path) - 1) if path[k] in marks]
    ends.append(len(path) - 1)
    return first, ends


# ------------------------------------------------------------------ model


def _as_int(value: Any, name: str) -> int:
    if isinstance(value, bool):
        raise ProbabilityError(f"{name} must be an integer, got {value!r}", value, param=name)
    try:
        as_float = float(value)
    except (TypeError, ValueError):
        raise ProbabilityError(f"{name} must be an integer, got {value!r}", value, param=name) from None
    if as_float != int(as_float):
        raise ProbabilityError(f"{name} must be a whole number, got {value!r}", value, param=name)
    return int(as_float)


def coerce_model(params: dict | None) -> WalkModel:
    """Validate parameters into a :class:`WalkModel`, refusing with the culprit."""
    params = dict(params or {})
    d = WalkModel()
    n = _as_int(params.get("n", d.n), "n")
    if not MIN_N <= n <= MAX_N:
        raise ProbabilityError(f"n must be between {MIN_N} and {MAX_N} so every position "
                               f"gets a legible tick, got {n}", n, param="n")
    start = _as_int(params.get("start", d.start), "start")
    if not 0 < start < n:
        raise ProbabilityError(f"start must be strictly between 0 and n={n}; a walk "
                               f"that starts on an end has already stopped", start, param="start")
    try:
        p = float(params.get("p", d.p))
    except (TypeError, ValueError):
        raise ProbabilityError(f"p must be a number, got {params.get('p')!r}", params.get("p"), param="p") from None
    if not MIN_P <= p <= MAX_P:
        raise ProbabilityError(f"p must be between {MIN_P} and {MAX_P}; beyond that one end "
                               f"is practically never reached and the picture would say "
                               f"otherwise", p, param="p")
    seed = _as_int(params.get("seed", d.seed), "seed")
    exit_side = str(params.get("exit", d.exit)).strip().lower()
    if exit_side not in ("any", "zero", "top"):
        raise ProbabilityError("exit must be 'any', 'zero' or 'top'", exit_side, param="exit")
    phases = params.get("phases", d.phases)
    if isinstance(phases, str):
        phases = [x.strip() for x in phases.split(",") if x.strip()]
    phases = tuple(str(x).strip().lower() for x in phases)
    _check_phases(phases)
    runs = _as_int(params.get("runs", d.runs), "runs")
    if "tally" in phases:
        if not MIN_TALLY_RUNS <= runs <= MAX_RUNS:
            raise ProbabilityError(f"runs must be between {MIN_TALLY_RUNS} and {MAX_RUNS} "
                                   f"when the tally phase is shown, got {runs}", runs, param="runs")
    step = params.get("step_seconds", d.step_seconds)
    try:
        lo, hi = float(step[0]), float(step[1])
    except (TypeError, ValueError, IndexError, KeyError):
        raise ProbabilityError("step_seconds must be a pair (lo, hi)", step, param="step_seconds") from None
    if not 0.15 <= lo < hi <= 3.0:
        raise ProbabilityError("step_seconds must satisfy 0.15 <= lo < hi <= 3.0", step,
                               param="step_seconds")
    raw_absorb = params.get("absorb_at", d.absorb_at)
    if isinstance(raw_absorb, dict):
        # A cue: the walk is absorbed on a sentence, wherever it falls. The
        # "before the beat ends" rule is checked against real spans in walk_claims.
        absorb_at = coerce_cue(raw_absorb, phases, "absorb_at", phase="absorb")
        if absorb_at.phase != "absorb":
            raise ProbabilityError("absorb_at must be a moment in the absorb phase", raw_absorb,
                                   param="absorb_at")
    else:
        try:
            absorb_at = float(raw_absorb)
        except (TypeError, ValueError):
            raise ProbabilityError("absorb_at must be a number or a cue", raw_absorb,
                                   param="absorb_at") from None
    if isinstance(absorb_at, float) and not 0.1 <= absorb_at <= 0.85:
        raise ProbabilityError("absorb_at must be between 0.1 and 0.85 of the absorb beat, so the "
                               "freeze is on screen before the beat ends", absorb_at, param="absorb_at")
    captions = _coerce_captions(params.get("captions"), phases)
    extra = _coerce_extensions(params, phases, n, start, runs)
    return WalkModel(
        n=n, start=start, p=p, seed=seed, exit=exit_side, runs=runs, phases=phases,
        absorb_at=absorb_at, captions=captions,
        low_label=str(params.get("low_label", d.low_label)),
        high_label=str(params.get("high_label", d.high_label)),
        title=str(params.get("title", d.title)),
        step_seconds=(lo, hi),
        **extra,
    )


def _as_float(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise ProbabilityError(f"{name} must be a number, got {value!r}", value, param=name)
    try:
        out = float(value)
    except (TypeError, ValueError):
        raise ProbabilityError(f"{name} must be a number, got {value!r}", value, param=name) from None
    if out != out or out in (float("inf"), float("-inf")):
        raise ProbabilityError(f"{name} must be finite, got {value!r}", value, param=name)
    return out


def coerce_cue(raw: Any, phases: tuple, name: str, *, phase: str | None = None) -> Cue:
    """A cue from a phase name or a ``{"phase", "sentence", "offset", "at"}`` mapping.

    ``phase`` is the phase to assume when the mapping names none — a caption
    card's own phase, the ``absorb`` phase for ``absorb_at``.
    """
    if isinstance(raw, str):
        raw = {"phase": raw}
    if not isinstance(raw, dict):
        raise ProbabilityError(f"{name} must be a phase name or a mapping with 'phase' and "
                               "'sentence' or 'at'", raw, param=name)
    unknown = set(raw) - {"phase", "sentence", "offset", "at"}
    if unknown:
        raise ProbabilityError(f"{name} has unknown key(s) {sorted(unknown)}", raw, param=name)
    ph = str(raw.get("phase", phase or "")).strip().lower()
    if ph not in phases:
        raise ProbabilityError(f"{name} names phase {ph!r}, which is not one of {list(phases)}",
                               raw, param=name)
    sentence = raw.get("sentence")
    if sentence is not None:
        sentence = _as_int(sentence, name)
        if sentence < 1:
            raise ProbabilityError(f"{name}: sentences count from 1", raw, param=name)
    at = raw.get("at")
    if at is not None:
        if sentence is not None:
            raise ProbabilityError(f"{name}: give 'sentence' or 'at', not both", raw, param=name)
        at = _as_float(at, name)
        if not 0.0 <= at <= 1.0:
            raise ProbabilityError(f"{name}: 'at' is a fraction of the phase, 0..1", raw, param=name)
    offset = _as_float(raw.get("offset", 0.0), name)
    if abs(offset) > MAX_CUE_OFFSET:
        raise ProbabilityError(f"{name}: offset must be within ±{MAX_CUE_OFFSET:g} s", raw, param=name)
    return Cue(ph, sentence, offset, at)


def _check_format(template: Any, fields: tuple, name: str) -> str:
    text = str(template)
    sample = {"k": 3, "runs": 40, "count": 7, "mean": 8.5, "median": 7, "blocks": 4}
    try:
        text.format(**{f: sample[f] for f in fields})
    except (KeyError, IndexError, ValueError) as exc:
        raise ProbabilityError(f"{name} may use only the fields {list(fields)} "
                               f"(str.format), and {text!r} fails with {exc!r}", text,
                               param=name) from None
    return text


def _text_table(raw: Any, fields: dict, name: str) -> tuple:
    if not raw:
        return ()
    if not isinstance(raw, dict):
        raise ProbabilityError(f"{name} must map a key to its text", raw, param=name)
    out = []
    for key, text in raw.items():
        if key not in fields:
            raise ProbabilityError(f"{name}: unknown key {key!r}; known: {list(fields)}",
                                   key, param=name)
        out.append((key, _check_format(text, fields[key], name)))
    return tuple(out)


def _plain_label(text: Any, name: str) -> str:
    text = str(text)
    if "\n" in text or len(text) > 40:
        raise ProbabilityError(f"{name} must be one short line (at most 40 characters)", text,
                               param=name)
    return text


def _coerce_extensions(params: dict, phases: tuple, n: int, start: int, runs: int) -> dict:
    """The parameters added after the first release. Each defaults to its old picture."""
    out: dict[str, Any] = {}

    raw = params.get("axis_labels")
    if raw:
        if not isinstance(raw, dict):
            raise ProbabilityError("axis_labels must map low/high/start to a label", raw,
                                   param="axis_labels")
        bad = set(raw) - set(AXIS_LABEL_KEYS)
        if bad:
            raise ProbabilityError(f"axis_labels: unknown key(s) {sorted(bad)}; known: "
                                   f"{list(AXIS_LABEL_KEYS)}", raw, param="axis_labels")
        out["axis_labels"] = tuple((k, _plain_label(raw[k], "axis_labels"))
                                   for k in AXIS_LABEL_KEYS if k in raw)

    raw = params.get("labels_until")
    if raw:
        if not isinstance(raw, dict):
            raise ProbabilityError("labels_until must map ends/axis/title to a cue", raw,
                                   param="labels_until")
        bad = set(raw) - set(FADE_KEYS)
        if bad:
            raise ProbabilityError(f"labels_until: unknown key(s) {sorted(bad)}; known: "
                                   f"{list(FADE_KEYS)}", raw, param="labels_until")
        out["labels_until"] = tuple((k, coerce_cue(raw[k], phases, "labels_until"))
                                    for k in FADE_KEYS if k in raw)

    if params.get("showcase_steps") is not None:
        steps = _as_int(params["showcase_steps"], "showcase_steps")
        nearest = min(start, n - start)
        if steps < nearest or (steps - nearest) % 2:
            raise ProbabilityError(
                f"showcase_steps={steps} is impossible: from {start} the nearest end is "
                f"{nearest} steps away and every walk to it has that parity", steps,
                param="showcase_steps")
        if steps > 200:
            raise ProbabilityError("showcase_steps above 200 would not be legible", steps,
                                   param="showcase_steps")
        out["showcase_steps"] = steps

    layout = str(params.get("layout", "classic")).strip().lower()
    if layout not in LAYOUTS:
        raise ProbabilityError(f"layout must be one of {list(LAYOUTS)}", layout, param="layout")
    out["layout"] = layout

    renewal_keys = ("renewal_states", "renewal_cues", "renewal_text")
    if "renewal" not in phases:
        given = [k for k in renewal_keys if params.get(k)]
        if given:
            raise ProbabilityError(f"{given[0]} needs the 'renewal' phase", given[0], param=given[0])
    else:
        raw = params.get("renewal_states")
        if raw:
            if isinstance(raw, (str, bytes)) or not hasattr(raw, "__iter__"):
                raise ProbabilityError("renewal_states must be a list of positions", raw,
                                       param="renewal_states")
            states = tuple(_as_int(x, "renewal_states") for x in raw)
            if not states or len(set(states)) != len(states):
                raise ProbabilityError("renewal_states must be distinct positions", raw,
                                       param="renewal_states")
            if any(not 0 < x < n for x in states):
                raise ProbabilityError(f"renewal_states must lie strictly inside 0..{n}: an end "
                                       "absorbs, so nothing returns from it", raw,
                                       param="renewal_states")
            out["renewal_states"] = states
        elif not tuple(x for x in (start - 1, start + 1) if 0 < x < n):
            raise ProbabilityError("no default renewal states", start, param="renewal_states")
        raw = params.get("renewal_cues")
        if raw:
            known = RENEWAL_CUE_KEYS + RENEWAL_OPTIONAL_CUES
            if not isinstance(raw, dict) or set(raw) - set(known):
                raise ProbabilityError(f"renewal_cues must map {list(known)} to cues",
                                       raw, param="renewal_cues")
            out["renewal_cues"] = tuple(
                (k, coerce_cue(raw[k], phases, "renewal_cues", phase="renewal"))
                for k in known if k in raw)
        out["renewal_text"] = _text_table(params.get("renewal_text"), RENEWAL_TEXT_FIELDS,
                                          "renewal_text")

    tally_keys = ("tally_target", "tally_from", "tally_until", "tally_text", "step_axis")
    stat = str(params.get("tally_stat", "end")).strip().lower()
    if stat not in TALLY_STATS:
        raise ProbabilityError(f"tally_stat must be one of {list(TALLY_STATS)}", stat,
                               param="tally_stat")
    ease = str(params.get("tally_ease", "linear")).strip().lower()
    if ease not in TALLY_EASES:
        raise ProbabilityError(f"tally_ease must be one of {list(TALLY_EASES)}", ease,
                               param="tally_ease")
    out["tally_stat"], out["tally_ease"] = stat, ease
    if "tally" not in phases:
        given = [k for k in tally_keys if params.get(k) not in (None, "", {})]
        if given:
            raise ProbabilityError(f"{given[0]} needs the 'tally' phase", given[0], param=given[0])
        return out
    target = params.get("tally_target")
    if target is not None:
        if stat == "end":
            raise ProbabilityError("tally_target marks a number of steps, so it needs "
                                   "tally_stat 'mean' or 'histogram'", target, param="tally_target")
        target = _as_float(target, "tally_target")
        if not 0 < target <= 4 * PATH_CAP:
            raise ProbabilityError("tally_target must be a positive number of steps", target,
                                   param="tally_target")
        out["tally_target"] = target
        out["tally_target_label"] = _plain_label(
            params.get("tally_target_label", "%g" % target), "tally_target_label")
    for key in ("tally_from", "tally_until"):
        if params.get(key) is not None:
            out[key] = coerce_cue(params[key], phases, key, phase="tally")
    fields = dict(TALLY_TEXT_FIELDS)
    out["tally_text"] = _text_table(params.get("tally_text"), fields, "tally_text")
    if params.get("step_axis"):
        out["step_axis"] = _plain_label(params["step_axis"], "step_axis")
    return out


_MARKUP_TAG = re.compile(r"</?(i|b|sub|sup)>")


def _coerce_captions(raw: Any, phases: tuple) -> tuple:
    """``(phase, markup)`` pairs, in phase order. Refuses markup Pango would choke on.

    Only the four tags are allowed, balanced, and a bare ``<`` or ``&`` is refused:
    Pango rejects malformed markup *at render time*, after the Manim process has
    been paid for, so the cheap place to catch it is here.
    """
    if not raw:
        return ()
    if not isinstance(raw, dict):
        raise ProbabilityError("captions must map a phase name to its caption", raw, param="captions")
    out = []
    for phase, text in raw.items():
        if phase not in phases:
            raise ProbabilityError(f"caption for '{phase}', which is not one of the phases {list(phases)}",
                                   phase, param="captions")
        if isinstance(text, (list, tuple)):
            out.append((phase, _coerce_cards(text, phase, phases)))
            continue
        out.append((phase, _check_markup(str(text))))
    order = {ph: k for k, ph in enumerate(phases)}
    return tuple(sorted(out, key=lambda pair: order[pair[0]]))


def _coerce_cards(raw: list | tuple, phase: str, phases: tuple) -> tuple:
    """A phase's sequence of cards, each entering on its own cue, in time order.

    A bare string is a card at the phase start. A mapping carries ``text`` and a
    cue (``sentence``/``offset`` or ``at``, within this phase unless it names
    another), plus ``build`` (stack under the cards before it instead of
    replacing them) and ``until`` (leave early).
    """
    if not raw:
        raise ProbabilityError(f"captions['{phase}'] is an empty list", raw, param="captions")
    cards = []
    for k, item in enumerate(raw):
        if isinstance(item, str):
            item = {"text": item}
        if not isinstance(item, dict) or "text" not in item:
            raise ProbabilityError(f"captions['{phase}'][{k}] must be a string or a mapping with "
                                   "'text'", item, param="captions")
        bad = set(item) - {"text", "sentence", "offset", "at", "build", "until"}
        if bad:
            raise ProbabilityError(f"captions['{phase}'][{k}]: unknown key(s) {sorted(bad)}",
                                   item, param="captions")
        cue = coerce_cue({x: item[x] for x in ("sentence", "offset", "at") if x in item} | {"phase": phase},
                         phases, "captions")
        until = coerce_cue(item["until"], phases, "captions", phase=phase) if item.get("until") else None
        build = bool(item.get("build", False))
        if build and k == 0:
            raise ProbabilityError(f"captions['{phase}'][0] cannot build on nothing", item,
                                   param="captions")
        cards.append(Card(_check_markup(str(item["text"])), cue, build, until))
    return tuple(cards)


def _check_markup(text: str) -> str:
    """Refuse markup Pango would choke on; see :func:`_coerce_captions`."""
    stripped = _MARKUP_TAG.sub("", text)
    if "<" in stripped or ">" in stripped:
        raise ProbabilityError("captions allow only <i>, <b>, <sub> and <sup> tags", text, param="captions")
    if re.search(r"&(?!amp;|lt;|gt;)", text):
        raise ProbabilityError("a bare & in a caption must be written &amp;", text, param="captions")
    stack = []
    for m in re.finditer(r"<(/?)(i|b|sub|sup)>", text):
        if not m.group(1):
            stack.append(m.group(2))
        elif not stack or stack.pop() != m.group(2):
            raise ProbabilityError("caption tags are not balanced", text, param="captions")
    if stack:
        raise ProbabilityError("caption tags are not balanced", text, param="captions")
    return text


def _check_phases(phases: tuple) -> None:
    unknown = [x for x in phases if x not in PHASES]
    if unknown:
        raise ProbabilityError(f"unknown phase(s) {unknown}; known: {list(PHASES)}", unknown,
                               param="phases")
    if len(set(phases)) != len(phases):
        raise ProbabilityError("a phase may appear only once", list(phases), param="phases")
    if not phases or phases[0] != "walk":
        raise ProbabilityError("phases must begin with 'walk': nothing else has a token to act on",
                               list(phases), param="phases")
    if "absorb" not in phases:
        raise ProbabilityError("phases must include 'absorb': a walk never seen to stop shows "
                               "nothing about absorbing ends", list(phases), param="phases")
    a = phases.index("absorb")
    for name in ("ends", "steps"):
        if name in phases and phases.index(name) > a:
            raise ProbabilityError(f"'{name}' must come before 'absorb', while the token still moves",
                                   list(phases), param="phases")
    if "renewal" in phases and phases.index("renewal") < a:
        raise ProbabilityError("'renewal' must come after 'absorb': it counts off a walk that "
                               "has finished", list(phases), param="phases")
    if "tally" in phases and phases[-1] != "tally":
        raise ProbabilityError("'tally' must be the last phase", list(phases), param="phases")


def spans_for(m: WalkModel, beat_seconds: dict | None = None) -> list[float]:
    """Seconds per phase: measured when given (``b01``…), else the defaults."""
    beats = dict(beat_seconds or {})
    return [float(beats.get(f"b{i + 1:02d}", DEFAULT_SPANS[ph])) for i, ph in enumerate(m.phases)]


def phase_starts(spans: list[float]) -> list[float]:
    out, acc = [], 0.0
    for span in spans:
        out.append(acc)
        acc += span
    return out


def all_cues(m: WalkModel) -> list[Cue]:
    """Every cue the model uses, for the unmeasured-sentence fallback."""
    cues = [c for _k, c in m.labels_until] + [c for _k, c in m.renewal_cues]
    cues += [c for c in (m.tally_from, m.tally_until) if c is not None]
    if isinstance(m.absorb_at, Cue):
        cues.append(m.absorb_at)
    for _phase, cards in m.captions:
        if isinstance(cards, tuple):
            for card in cards:
                cues.append(card.cue)
                if card.until is not None:
                    cues.append(card.until)
    return cues


def sentence_counts(m: WalkModel) -> dict[int, int]:
    """Per phase index, the highest sentence any cue refers to.

    Only used when a sentence start was not measured: sentence ``k`` of ``K``
    then falls at ``(k - 1) / K`` of its phase.
    """
    counts: dict[int, int] = {}
    for c in all_cues(m):
        if c.sentence is not None:
            i = m.phases.index(c.phase)
            counts[i] = max(counts.get(i, 1), c.sentence)
    return counts


def cue_time(m: WalkModel, spans: list[float], beat_seconds: dict | None, cue: Cue) -> float:
    """:func:`cue_seconds` for a model — the same arithmetic the scene runs."""
    i, sentence, offset, at = cue.as_args(m.phases)
    return cue_seconds(phase_starts(spans), spans, dict(beat_seconds or {}), i, sentence, offset,
                       at, sentence_counts(m).get(i, 1))


def walking_seconds(m: WalkModel, spans: list[float], beat_seconds: dict | None = None) -> float:
    """Scene time from the first step to the moment the walk is absorbed."""
    a = m.phases.index("absorb")
    if isinstance(m.absorb_at, Cue):
        return cue_time(m, spans, beat_seconds, m.absorb_at)
    return sum(spans[:a]) + m.absorb_at * spans[a]


def renewal_times(m: WalkModel, spans: list[float], beat_seconds: dict | None) -> tuple:
    """``(first, blocks, done)`` scene times for the renewal phase."""
    defaults = {"first": Cue("renewal", at=0.10), "blocks": Cue("renewal", at=0.25),
                "done": Cue("renewal", at=0.75)}
    defaults.update(dict(m.renewal_cues))
    return tuple(cue_time(m, spans, beat_seconds, defaults[k]) for k in RENEWAL_CUE_KEYS)


def tally_times(m: WalkModel, spans: list[float], beat_seconds: dict | None) -> tuple:
    """``(from, until)``: when the first replayed walk appears and when the last lands."""
    i = m.phases.index("tally")
    t0 = phase_starts(spans)[i]
    start = cue_time(m, spans, beat_seconds, m.tally_from) if m.tally_from else t0 + 0.8
    if m.tally_until:
        until = cue_time(m, spans, beat_seconds, m.tally_until)
    else:
        until = t0 + 0.8 + max(spans[i] - 2.2, 1.0)
    return start, until


# ------------------------------------------------------------------ claims


def path_violations(path: list[int] | None, start: int, n: int) -> list[str]:
    """Every way ``path`` fails to be an absorbed ±1 walk from ``start``."""
    if not path:
        return ["no path"]
    problems = []
    if path[0] != start:
        problems.append(f"starts at {path[0]}, not {start}")
    for k, (a, b) in enumerate(zip(path, path[1:])):
        if abs(b - a) != 1:
            problems.append(f"step {k + 1} moves by {b - a}")
            break
    if any(not 0 < x < n for x in path[:-1]):
        problems.append("touches an end before its last step")
    if path[-1] not in (0, n):
        problems.append(f"ends at {path[-1]}, which is not absorbing")
    return problems


def walk_claims(m: WalkModel, beat_seconds: dict | None = None) -> dict:
    """Check everything the picture asserts; return the facts it will show.

    Raises :class:`ProbabilityError` if a walk with the requested exit cannot be
    found, or if any drawn path is not a genuine absorbed walk. Pace outside the
    preferred band is reported, not refused — the walk is still true.
    """
    spans = spans_for(m, beat_seconds)
    walking = walking_seconds(m, spans, beat_seconds)
    a = m.phases.index("absorb")
    if isinstance(m.absorb_at, Cue):
        a_start = phase_starts(spans)[a]
        if not a_start < walking <= a_start + spans[a] - 0.3:
            raise ProbabilityError(
                f"absorb_at resolves to {walking:.2f}s, outside the absorb phase "
                f"({a_start:.2f}s..{a_start + spans[a]:.2f}s) or too close to its end for the "
                "freeze to be seen", walking, param="absorb_at")
    lo, hi = m.step_seconds
    if m.showcase_steps is not None:
        seed_used, path, in_range = showcase_of_length(
            m.start, m.n, m.p, m.seed, m.exit, m.showcase_steps, walking, lo, hi,
            min_turns=MIN_TURNS, tries=SEED_TRIES, cap=PATH_CAP)
    else:
        seed_used, path, in_range = choose_showcase(
            m.start, m.n, m.p, m.seed, m.exit, walking, lo, hi,
            min_turns=MIN_TURNS, tries=SEED_TRIES, cap=PATH_CAP)
    if path is None and m.showcase_steps is not None:
        raise ProbabilityError(
            f"no walk of exactly {m.showcase_steps} steps from {m.start} on 0..{m.n} with "
            f"p={m.p} ends at the '{m.exit}' end within {SEED_TRIES} seeds from {m.seed}",
            m.showcase_steps, param="showcase_steps")
    if path is None:
        raise ProbabilityError(
            f"no walk from {m.start} on 0..{m.n} with p={m.p} ends at the requested "
            f"'{m.exit}' end within {SEED_TRIES} seeds", m.exit, param="exit")
    bad = path_violations(path, m.start, m.n)
    if bad:  # pragma: no cover - walk_path cannot produce these; guards a future edit
        raise ProbabilityError(f"showcase walk is not a valid walk: {bad}", seed_used, param="seed")
    facts: dict[str, Any] = {
        "spans": spans,
        "walking_seconds": walking,
        "seed_used": seed_used,
        "steps": len(path) - 1,
        "exit": "zero" if path[-1] == 0 else "top",
        "seconds_per_step": walking / (len(path) - 1),
        "pace_in_range": in_range,
        "path": list(path),
        "expected_steps": float(expected_steps(m.start, m.n, m.p)),
    }
    for key, cue in m.labels_until:
        facts[f"{key}_labels_out_seconds"] = cue_time(m, spans, beat_seconds, cue)
    if "renewal" in m.phases:
        facts.update(_renewal_facts(m, path, spans, beat_seconds, walking))
    if "tally" in m.phases:
        runs = tally_paths(m.start, m.n, m.p, m.seed, m.runs, stride=TALLY_SEED_STRIDE, cap=PATH_CAP)
        if len(runs) != m.runs:
            raise ProbabilityError(f"only {len(runs)} of {m.runs} tally walks were absorbed within "
                                   f"{PATH_CAP} steps", len(runs), param="runs")
        for path_k in runs:
            bad = path_violations(path_k, m.start, m.n)
            if bad:  # pragma: no cover - as above
                raise ProbabilityError(f"tally walk invalid: {bad}", None, param="runs")
        at_zero = sum(1 for r in runs if r[-1] == 0)
        steps = [len(r) - 1 for r in runs]
        t_from, t_until = tally_times(m, spans, beat_seconds)
        i = m.phases.index("tally")
        t0 = phase_starts(spans)[i]
        if not t0 <= t_from < t_until <= t0 + spans[i]:
            raise ProbabilityError(
                f"the tally would run {t_from:.2f}s..{t_until:.2f}s, which is not an interval "
                f"inside its phase ({t0:.2f}s..{t0 + spans[i]:.2f}s)", (t_from, t_until),
                param="tally_until" if m.tally_until else "tally_from")
        facts.update({"tally_zero": at_zero, "tally_top": m.runs - at_zero,
                      "tally_longest": max(steps), "tally_steps": steps,
                      "tally_mean": sum(steps) / len(steps),
                      "tally_median": sorted(steps)[len(steps) // 2],
                      "tally_from_seconds": t_from, "tally_done_seconds": t_until})
    return facts


def _renewal_facts(m: WalkModel, path: list, spans: list, beat_seconds: dict | None,
                   walking: float) -> dict:
    states = m.renewal_set()
    first, ends = renewal_blocks(path, states)
    if first is None:
        raise ProbabilityError(
            f"the showcase walk is absorbed without visiting the renewal states {list(states)}, "
            "so there are no blocks to count", list(states), param="renewal_states")
    t_first, t_blocks, t_done = renewal_times(m, spans, beat_seconds)
    i = m.phases.index("renewal")
    r0 = phase_starts(spans)[i]
    if not (walking < t_first <= t_blocks <= t_done <= r0 + spans[i]) or (len(ends) > 1 and t_blocks == t_done):
        raise ProbabilityError(
            f"renewal cues must run first <= blocks < done inside the phase; got "
            f"{t_first:.2f}s, {t_blocks:.2f}s, {t_done:.2f}s in {r0:.2f}s..{r0 + spans[i]:.2f}s",
            (t_first, t_blocks, t_done), param="renewal_cues")
    average = dict(m.renewal_cues).get("average")
    t_average = cue_time(m, spans, beat_seconds, average) if average else None
    if t_average is not None and not t_done <= t_average <= r0 + spans[i]:
        raise ProbabilityError(f"the renewal 'average' cue ({t_average:.2f}s) must come after "
                               f"'done' ({t_done:.2f}s), inside the phase", t_average,
                               param="renewal_cues")
    lengths = [b - a for a, b in zip([first] + ends[:-1], ends)]
    escape = {x: renewal_escape(x, states, m.n, m.p) for x in states}
    return {
        "renewal_states": list(states),
        "renewal_first_steps": first,
        "renewal_blocks": len(ends),
        "renewal_block_steps": lengths,
        "renewal_escape": {x: float(v) for x, v in escape.items()},
        "renewal_escape_exact": {x: str(v) for x, v in escape.items()},
        "renewal_seconds": (t_first, t_blocks, t_done),
        "renewal_average_seconds": t_average,
    }


def _exact(p: float):
    from fractions import Fraction

    return Fraction(str(p))


def _solve(rows: list, rhs: list) -> list:
    """Gaussian elimination over Fractions; ``rows`` is square and non-singular here."""
    n = len(rows)
    a = [list(r) + [b] for r, b in zip(rows, rhs)]
    for c in range(n):
        pivot = next(r for r in range(c, n) if a[r][c] != 0)
        a[c], a[pivot] = a[pivot], a[c]
        for r in range(n):
            if r != c and a[r][c] != 0:
                f = a[r][c] / a[c][c]
                a[r] = [x - f * y for x, y in zip(a[r], a[c])]
    return [a[r][n] / a[r][r] for r in range(n)]


def expected_steps(start: int, n: int, p: float):
    """Exact E[steps to absorption] from ``start``, as a Fraction (``p`` read as a decimal)."""
    from fractions import Fraction

    pu = _exact(p)
    inner = list(range(1, n))
    idx = {x: k for k, x in enumerate(inner)}
    rows, rhs = [], []
    for x in inner:
        row = [Fraction(0)] * len(inner)
        row[idx[x]] = Fraction(1)
        for y, w in ((x + 1, pu), (x - 1, 1 - pu)):
            if y in idx:
                row[idx[y]] -= w
        rows.append(row)
        rhs.append(Fraction(1))
    return _solve(rows, rhs)[idx[start]]


def renewal_escape(x: int, states: tuple, n: int, p: float):
    """Exact chance that a block starting at ``x`` ends on an end, not back in ``states``."""
    from fractions import Fraction

    pu = _exact(p)
    marks = set(states)
    free = [y for y in range(1, n) if y not in marks]
    idx = {y: k for k, y in enumerate(free)}

    def value(y, h):
        if y in (0, n):
            return Fraction(1)
        if y in marks:
            return Fraction(0)
        return h[idx[y]]

    h = []
    if free:
        rows, rhs = [], []
        for y in free:
            row = [Fraction(0)] * len(free)
            row[idx[y]] = Fraction(1)
            b = Fraction(0)
            for z, w in ((y + 1, pu), (y - 1, 1 - pu)):
                if z in idx:
                    row[idx[z]] -= w
                elif z in (0, n):
                    b += w
            rows.append(row)
            rhs.append(b)
        h = _solve(rows, rhs)
    return pu * value(x + 1, h) + (1 - pu) * value(x - 1, h)


def ruin_probability(start: int, n: int, p: float) -> float:
    """Exact P(reach 0 before n) — for tests and summaries, never drawn as a claim."""
    q = 1.0 - p
    if abs(p - q) < 1e-12:
        return 1.0 - start / n
    r = q / p
    return (r ** start - r ** n) / (1.0 - r ** n)
