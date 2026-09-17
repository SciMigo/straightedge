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
``tally``   many walks replay from the same start and a count tracks which end
            each reached — the frequency whose limit *is* the ruin probability.

A lecture that wants fewer beats names fewer phases; ``walk`` and ``absorb`` are
the minimum, because a walk that is never seen to stop shows nothing about
absorption.
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


PHASES = ("walk", "ends", "steps", "absorb", "tally")
DEFAULT_PHASES = PHASES

#: Beat lengths used when no narration has been measured — a silent render, the
#: CLI, a preview. Close to what one spoken sentence per phase takes.
DEFAULT_SPANS = {"walk": 9.0, "ends": 11.0, "steps": 10.0, "absorb": 10.0, "tally": 12.0}

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

    @property
    def beats(self) -> int:
        return len(self.phases)


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
    try:
        absorb_at = float(params.get("absorb_at", d.absorb_at))
    except (TypeError, ValueError):
        raise ProbabilityError("absorb_at must be a number", params.get("absorb_at"),
                               param="absorb_at") from None
    if not 0.1 <= absorb_at <= 0.85:
        raise ProbabilityError("absorb_at must be between 0.1 and 0.85 of the absorb beat, so the "
                               "freeze is on screen before the beat ends", absorb_at, param="absorb_at")
    captions = _coerce_captions(params.get("captions"), phases)
    return WalkModel(
        n=n, start=start, p=p, seed=seed, exit=exit_side, runs=runs, phases=phases,
        absorb_at=absorb_at, captions=captions,
        low_label=str(params.get("low_label", d.low_label)),
        high_label=str(params.get("high_label", d.high_label)),
        title=str(params.get("title", d.title)),
        step_seconds=(lo, hi),
    )


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
        text = str(text)
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
        out.append((phase, text))
    order = {ph: k for k, ph in enumerate(phases)}
    return tuple(sorted(out, key=lambda pair: order[pair[0]]))


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
    if "tally" in phases and phases[-1] != "tally":
        raise ProbabilityError("'tally' must be the last phase", list(phases), param="phases")


def spans_for(m: WalkModel, beat_seconds: dict | None = None) -> list[float]:
    """Seconds per phase: measured when given (``b01``…), else the defaults."""
    beats = dict(beat_seconds or {})
    return [float(beats.get(f"b{i + 1:02d}", DEFAULT_SPANS[ph])) for i, ph in enumerate(m.phases)]


def walking_seconds(m: WalkModel, spans: list[float]) -> float:
    """Scene time from the first step to the moment the walk is absorbed."""
    a = m.phases.index("absorb")
    return sum(spans[:a]) + m.absorb_at * spans[a]


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
    walking = walking_seconds(m, spans)
    lo, hi = m.step_seconds
    seed_used, path, in_range = choose_showcase(
        m.start, m.n, m.p, m.seed, m.exit, walking, lo, hi,
        min_turns=MIN_TURNS, tries=SEED_TRIES, cap=PATH_CAP)
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
    }
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
        facts.update({"tally_zero": at_zero, "tally_top": m.runs - at_zero,
                      "tally_longest": max(len(r) - 1 for r in runs)})
    return facts


def ruin_probability(start: int, n: int, p: float) -> float:
    """Exact P(reach 0 before n) — for tests and summaries, never drawn as a claim."""
    q = 1.0 - p
    if abs(p - q) < 1e-12:
        return 1.0 - start / n
    r = q / p
    return (r ** start - r ** n) / (1.0 - r ** n)
