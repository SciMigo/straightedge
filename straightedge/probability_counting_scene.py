"""Manim scenes for ``probability/outcome_grid`` and ``probability/arrangement_gaps``.

Both follow the random-walk scene's timing model: one ``ValueTracker`` holds
scene time, every mark is a function of it, and each beat is one
``_beat_stretch`` of that clock across the beat, so the picture follows the
measured narration and nothing drifts. Mobjects are built once and only their
colour and opacity change per frame (text is never re-laid out mid-scene except
for the running-average readouts, which are cached per value).

The numbers drawn are computed by :mod:`straightedge.probability_counting`. The
functions that produce them (:func:`~straightedge.probability_counting.event_cells`,
:func:`~straightedge.probability_counting.deal`, …) are copied into the scene
verbatim with :func:`inspect.getsource`, so the scene and the checks run one
copy of the logic.

**Layout boxes.** Each scene computes a safe box (``SX0..SX1`` × ``SY0..SY1``)
from the frame and ``safe_area``. In a 9:16 frame with ``safe_area: "shorts"``
that box leaves out the bottom 21% and the right 14% of the frame, where a
short-video player draws its controls and caption; nothing — title, figure,
readouts or captions — is placed outside it.
"""
from __future__ import annotations

import inspect
from textwrap import dedent, indent

from . import probability_counting as C
from .probability import cue_seconds


def _src(*fns) -> str:
    return "\n\n".join(inspect.getsource(fn) for fn in fns)


def _block(src: str, depth: int = 8) -> str:
    return indent(dedent(src).strip("\n"), " " * depth) + "\n"


def _cards_literal(m) -> dict:
    return {ph: [(c.text, c.cue.as_args(m.phases), c.build,
                  c.until.as_args(m.phases) if c.until else None) for c in cards]
            for ph, cards in m.captions}


def _common(m, defaults: dict) -> str:
    """Clock, phases, cue resolver, safe box, title wrapper and caption cards."""
    span_exprs = ", ".join(
        f'BEAT_SECONDS.get("b{i + 1:02d}", {defaults[ph]!r})' for i, ph in enumerate(m.phases))
    return _block(f'''
        PHASES = {tuple(m.phases)!r}
        SPANS = [{span_exprs}]
        STARTS, ENDS, acc = [], [], 0.0
        for span in SPANS:
            STARTS.append(acc)
            acc += span
            ENDS.append(acc)
        SENTENCE_COUNTS = {C.sentence_counts(m)!r}

        def cue_t(args):
            if args is None:
                return None
            return cue_seconds(STARTS, SPANS, BEAT_SECONDS, *args,
                               count=SENTENCE_COUNTS.get(args[0], 1))

        clk = ValueTracker(0.0)

        def fade(t0, dur=0.5):
            if t0 is None:
                return 0.0
            return min(max((clk.get_value() - t0) / dur, 0.0), 1.0)

        W, H = config.frame_width, config.frame_height
        vertical = H > W
        SHORTS = {m.safe_area == "shorts"!r} and vertical
        if SHORTS:
            # A short-video player covers the bottom fifth (caption, channel,
            # buttons) and a column on the right (like, comment, share).
            SX0, SX1 = -W / 2 + 0.35, W / 2 - 0.14 * W
            SY0, SY1 = -H / 2 + 0.21 * H, H / 2 - 0.06 * H
        else:
            SX0, SX1 = -W / 2 + 0.3, W / 2 - 0.3
            SY0, SY1 = -H / 2 + 0.3, H / 2 - 0.3
        SW, CX = SX1 - SX0, (SX0 + SX1) / 2.0
        BIG = 1.3 if vertical else 1.0

        def wrapped(text, size, width, **kw):
            """Text broken into lines no wider than ``width``, greedy by word."""
            words, lines = text.split(), []
            for word in words:
                trial = (lines[-1] + " " + word) if lines else word
                if lines and Text(trial, font=CJK_FONT, font_size=size).width <= width:
                    lines[-1] = trial
                else:
                    lines.append(word)
            mob = Text("\\n".join(lines) or " ", font=CJK_FONT, font_size=size, line_spacing=0.85,
                       **kw)
            if mob.width > width:
                mob.scale(width / mob.width)
            return mob

        TITLE = {m.title!r}
        title = None
        if TITLE:
            title = wrapped(TITLE, 36 * BIG, SW)
            title.move_to(np.array([CX, SY1 - title.height / 2.0, 0.0]))
            self.add(title)
        TOP = (title.get_bottom()[1] - 0.3) if title is not None else SY1
    ''')


def _captions(m) -> str:
    return _block(f'''
        # Caption cards in the band [CAP_BOTTOM, CAP_TOP], centred on CAP_X. A
        # card with build=True stacks under the ones before it; a stack leaves
        # when the next one enters, at its own `until`, or at its phase's end
        # (the last phase holds).
        CARDS = {_cards_literal(m)!r}

        def card_stacks(phase, cards):
            i = PHASES.index(phase)
            stacks = []
            for text, cue, build, until in cards:
                if not build:
                    stacks.append([])
                stacks[-1].append((text, cue_t(cue), cue_t(until)))
            last = i == len(PHASES) - 1
            out = []
            for s, stack in enumerate(stacks):
                mobs = [MarkupText(text, font=CJK_FONT, font_size=32 * BIG) for text, _, _ in stack]
                group = VGroup(*mobs).arrange(DOWN, buff=0.16)
                if group.width > CAP_W:
                    group.scale(CAP_W / group.width)
                room = CAP_TOP - CAP_BOTTOM
                if group.height > room:
                    group.scale(room / group.height)
                group.move_to(np.array([CAP_X, (CAP_TOP + CAP_BOTTOM) / 2.0, 0.0]))
                t_out = stacks[s + 1][0][1] if s + 1 < len(stacks) else (None if last else ENDS[i])
                untils = [u for _, _, u in stack if u is not None]
                if untils:
                    t_out = min(untils)
                for mob, (_text, t_in, _u) in zip(mobs, stack):
                    mob.add_updater(lambda mb, t_in=t_in, t_out=t_out: mb.set_opacity(
                        fade(t_in, 0.35) * (1.0 if t_out is None else 1.0 - fade(t_out - 0.3, 0.3))))
                    out.append(mob)
            return out

        for phase, cards in CARDS.items():
            self.add(*card_stacks(phase, cards))
    ''')


def _beats(m) -> str:
    return "\n".join(
        f'        _beat_stretch(self, "b{i + 1:02d}", clk.animate.set_value(ENDS[{i}]), '
        f'run_time=SPANS[{i}])' for i in range(m.beats)) + "\n"


def _assemble(helpers: str, body: str, m) -> str:
    return ("import math\nimport random\nfrom bisect import bisect_right\n\n\n" + helpers.strip()
            + "\n\n\nclass GeneratedScene(Scene):\n    def construct(self):\n" + body + _beats(m))


# ================================================================ outcome grid


def outcome_grid_scene(m: C.GridModel) -> str:
    times = {k: v for k, v in dict(m.cues).items()}
    cue = {k: (None if k not in times else times[k].as_args(m.phases)) for k in C.GRID_CUE_PHASES}
    events = [(e.stat, tuple(e.values), e.label, "C_" + e.colour.upper()) for e in m.events]
    defaults = {"grid_until": ("grid", 0.55), "condition": ("condition", 0.05),
                "result": ("result", 0.05)}
    body = _common(m, C.GRID_DEFAULT_SPANS)
    body += _block(f'''
        FACES = {tuple(m.faces)!r}
        EVENTS = {[(s, v) for s, v, _l, _c in events]!r}
        LABELS = {[label for _s, _v, label, _c in events]!r}
        COLOURS = [{", ".join(c for *_x, c in events)}]
        CELL_TEXT = {m.cell_text!r}
        ROW_LABEL, COL_LABEL = {m.row_label!r}, {m.col_label!r}
        CONDITION_TEXT, RESULT_TEXT = {m.condition_text!r}, {m.result_text!r}
        CELLS = event_cells(FACES, EVENTS)
        OWNER = {{}}
        for j, found in enumerate(CELLS):
            for cell in found:
                OWNER[tuple(cell)] = j

        def phase_at(name, frac, given):
            if given is not None:
                return cue_t(given)
            if name not in PHASES:
                return None
            i = PHASES.index(name)
            return STARTS[i] + frac * SPANS[i]

        T_GRID_UNTIL = phase_at("grid", {defaults["grid_until"][1]!r}, {cue["grid_until"]!r})
        EV_CUES = {[cue.get(f"event{k + 1}") for k in range(len(events))]!r}
        T_EV = [phase_at("events", 0.08 + 0.84 * k / max(len(EVENTS), 1), EV_CUES[k])
                for k in range(len(EVENTS))]
        T_COND = phase_at("condition", {defaults["condition"][1]!r}, {cue["condition"]!r})
        T_RES = phase_at("result", {defaults["result"][1]!r}, {cue["result"]!r})

        # ---- layout: readouts under the title, then the grid, then captions.
        R, Cc = FACES
        READ_H = (0.62 if EVENTS else 0.0) + (0.9 if (CONDITION_TEXT or RESULT_TEXT) else 0.0)
        if vertical:
            CAP_H = 1.3
            grid_top = TOP - READ_H * BIG - 0.05
            avail_h = grid_top - (SY0 + CAP_H + 0.25)
            S = min(SW / (Cc + 1 + (0.45 if ROW_LABEL else 0.0)), avail_h / (R + 1 + (0.45 if COL_LABEL else 0.0)))
            GX0 = CX - S * (Cc + 1) / 2.0
            READ_X, READ_W = CX, SW
            READ_TOP = TOP
            CAP_X, CAP_W, CAP_BOTTOM = CX, SW, SY0 + 0.05
            CAP_TOP = SY0 + CAP_H
        else:
            grid_top = TOP
            avail_h = grid_top - SY0
            S = avail_h / (R + 1 + (0.45 if COL_LABEL else 0.0))
            GX0 = SX0 + (0.45 * S if ROW_LABEL else 0.0)
            right = GX0 + S * (Cc + 1) + 0.5
            READ_X, READ_W = (right + SX1) / 2.0, SX1 - right
            READ_TOP = TOP
            CAP_X, CAP_W, CAP_BOTTOM = READ_X, READ_W, SY0 + 0.05
            CAP_TOP = SY0 + 2.2
        if COL_LABEL:
            grid_top -= 0.45 * S
        GY0 = grid_top

        def cell_centre(r, c):
            return np.array([GX0 + S * (c + 1.5), GY0 - S * (r + 1.5), 0.0])

        PIPS = {{1: [(0, 0)], 2: [(-1, 1), (1, -1)], 3: [(-1, 1), (0, 0), (1, -1)],
                4: [(-1, 1), (1, 1), (-1, -1), (1, -1)],
                5: [(-1, 1), (1, 1), (0, 0), (-1, -1), (1, -1)],
                6: [(-1, 1), (1, 1), (-1, 0), (1, 0), (-1, -1), (1, -1)]}}

        def die_face(value, centre):
            side = 0.74 * S
            box = RoundedRectangle(corner_radius=0.12 * side, width=side, height=side,
                                   stroke_color=C_FG, stroke_width=3, fill_color=C_WELL,
                                   fill_opacity=1.0).move_to(centre)
            if FACES[0] > 6 or FACES[1] > 6:
                return VGroup(box, _t(str(value), font_size=30 * BIG).move_to(centre))
            pips = VGroup(*[Dot(centre + np.array([dx * 0.26 * side, dy * 0.26 * side, 0.0]),
                                radius=0.075 * side, color=C_FG) for dx, dy in PIPS[value]])
            return VGroup(box, pips)

        headers = VGroup()
        for c in range(Cc):
            headers.add(die_face(c + 1, np.array([GX0 + S * (c + 1.5), GY0 - S * 0.5, 0.0])))
        for r in range(R):
            headers.add(die_face(r + 1, np.array([GX0 + S * 0.5, GY0 - S * (r + 1.5), 0.0])))
        if COL_LABEL:
            headers.add(_t(COL_LABEL, font_size=26 * BIG, color=C_MUTED).move_to(
                np.array([GX0 + S * (Cc + 2) / 2.0, GY0 + 0.25 * S, 0.0])))
        if ROW_LABEL:
            headers.add(_t(ROW_LABEL, font_size=26 * BIG, color=C_MUTED).rotate(PI / 2).move_to(
                np.array([GX0 - 0.25 * S, GY0 - S * (R + 2) / 2.0, 0.0])))
        headers.add_updater(lambda mob: mob.set_opacity(fade(0.0, 0.5)))
        self.add(headers)

        def cell_label(r, c):
            if CELL_TEXT == "sum":
                return str(r + c + 2)
            if CELL_TEXT == "pair":
                return "%d,%d" % (r + 1, c + 1)
            return ""

        N_CELLS = R * Cc
        T_G0 = STARTS[0] + 0.3
        squares, texts = [], []
        for r in range(R):
            for c in range(Cc):
                k = r * Cc + c
                t_in = T_G0 + (T_GRID_UNTIL - T_G0) * k / max(N_CELLS - 1, 1)
                j = OWNER.get((r, c))
                t_hi = None if j is None else T_EV[j] + 0.5 * (CELLS[j].index((r, c)) / max(len(CELLS[j]), 1))
                sq = Square(side_length=0.9 * S, stroke_color=C_MUTED, stroke_width=2,
                            fill_color=C_WELL, fill_opacity=1.0).move_to(cell_centre(r, c))
                txt = cell_label(r, c)
                lab = _t(txt, font_size=30 * BIG, color=C_FG) if txt else VMobject()
                if txt and lab.width > 0.78 * S:
                    lab.scale(0.78 * S / lab.width)
                lab.move_to(cell_centre(r, c))

                def sq_update(mob, t_in=t_in, j=j, t_hi=t_hi):
                    a = fade(t_in, 0.25)
                    lit = 0.0 if t_hi is None else fade(t_hi, 0.3)
                    gone = 0.0 if (j is not None or T_COND is None) else fade(T_COND, 0.8)
                    fill = C_WELL if j is None else interpolate_color(C_WELL, COLOURS[j], lit)
                    mob.set_fill(fill, opacity=a * (1.0 - 0.88 * gone))
                    mob.set_stroke(C_MUTED if j is None or lit < 0.5 else COLOURS[j],
                                   opacity=a * (1.0 - 0.88 * gone))

                def lab_update(mob, t_in=t_in, j=j, t_hi=t_hi):
                    a = fade(t_in, 0.25)
                    lit = 0.0 if t_hi is None else fade(t_hi, 0.3)
                    gone = 0.0 if (j is not None or T_COND is None) else fade(T_COND, 0.8)
                    mob.set_color(C_FG if lit < 0.5 else C_INK)
                    mob.set_opacity(a * (1.0 - 0.85 * gone))

                sq.add_updater(sq_update)
                lab.add_updater(lab_update)
                squares.append(sq)
                texts.append(lab)
        self.add(*squares, *texts)

        # ---- readouts: one row of event counts, then the condition / result line.
        rows = VGroup()
        ev_mobs = []
        for j, label in enumerate(LABELS):
            mob = _t(label, font_size=34 * BIG, color=COLOURS[j])
            ev_mobs.append(mob)
        if ev_mobs:
            ev_row = VGroup(*ev_mobs).arrange(RIGHT, buff=0.6)
            if ev_row.width > READ_W:
                ev_row.scale(READ_W / ev_row.width)
            ev_row.move_to(np.array([READ_X, READ_TOP - ev_row.height / 2.0, 0.0]))
            for j, mob in enumerate(ev_mobs):
                mob.add_updater(lambda mb, j=j: mb.set_opacity(fade(T_EV[j], 0.4)))
            self.add(*ev_mobs)
            line_top = ev_row.get_bottom()[1] - 0.25
        else:
            line_top = READ_TOP

        def line_mob(markup, size, t_in, t_out):
            mob = MarkupText(markup, font=CJK_FONT, font_size=size)
            if mob.width > READ_W:
                mob.scale(READ_W / mob.width)
            mob.move_to(np.array([READ_X, line_top - mob.height / 2.0, 0.0]))
            mob.add_updater(lambda mb: mb.set_opacity(
                fade(t_in, 0.4) * (1.0 if t_out is None else 1.0 - fade(t_out - 0.3, 0.3))))
            return mob

        if CONDITION_TEXT and T_COND is not None:
            self.add(line_mob(CONDITION_TEXT, 34 * BIG, T_COND, T_RES))
        if RESULT_TEXT and T_RES is not None:
            self.add(line_mob(RESULT_TEXT, 44 * BIG, T_RES, None))
    ''')
    body += _captions(m)
    helpers = _src(C.grid_stat, C.event_cells, cue_seconds)
    return _assemble(helpers, body, m)


# ================================================================ arrangement gaps


def arrangement_gaps_scene(m: C.GapModel) -> str:
    cues = {k: v.as_args(m.phases) for k, v in dict(m.cues).items()}
    fields = dict(m.fields)
    body = _common(m, C.GAP_DEFAULT_SPANS)
    body += _block(f'''
        TOTAL, MARKERS, SEED, MIN_GAP, RUNS, FOCUS = {m.total!r}, {m.markers!r}, {m.seed!r}, {m.min_gap!r}, {m.runs!r}, {m.focus!r}
        MARKER_LABEL, GAP_LABEL, COUNTER_TEXT = {m.marker_label!r}, {m.gap_label!r}, {m.counter_text!r}
        TARGET_TEXT, FOCUS_TEXT = {m.target_text!r}, {m.focus_text!r}
        MEAN_GAP = {float(C.Fraction(m.total - m.markers, m.markers + 1))!r}
        EASE = {m.ease!r}
        _seed, ORDER = choose_deal(TOTAL, MARKERS, SEED, MIN_GAP, {C.DEAL_TRIES}, {m.max_gap!r})
        SIZES = gap_sizes(ORDER)
        GAPS = len(SIZES)
        if "average" in PHASES:
            CHECKS, MEANS = running_means(TOTAL, MARKERS, SEED, RUNS, ORDER)
        else:
            CHECKS, MEANS = [1], [[float(s) for s in SIZES]]

        CUES = {cues!r}

        def phase_at(key, name, frac):
            if key in CUES:
                return cue_t(CUES[key])
            if name not in PHASES:
                return None
            i = PHASES.index(name)
            return STARTS[i] + frac * SPANS[i]

        T_DEAL = phase_at("deal_until", "deal", 0.6)
        T_GF, T_GU = phase_at("gaps_from", "gaps", 0.1), phase_at("gaps_until", "gaps", 0.6)
        T_AF, T_AU = phase_at("average_from", "average", 0.12), phase_at("average_until", "average", 0.8)
        T_FOCUS, T_FSUM = phase_at("focus", "focus", 0.05), phase_at("focus_sum", "focus", 0.4)
        T_TARGET = None if T_AF is None else (cue_t(CUES["target"]) if "target" in CUES else T_AF + 0.9)
        T_SF = None if T_AF is None else (cue_t(CUES["shuffle_from"]) if "shuffle_from" in CUES
                                          else T_TARGET)

        # ---- the dealt row
        SLOT = SW / TOTAL
        ROW_Y = TOP - 0.55 - 0.42 * BIG
        CARD_H = 0.62 * BIG
        T_D0 = STARTS[0] + 0.3

        def slot_x(k):
            return SX0 + SLOT * (k + 0.5)

        cards = []
        for k, is_marker in enumerate(ORDER):
            t_in = T_D0 + (T_DEAL - T_D0) * k / max(TOTAL - 1, 1)
            h = CARD_H * (1.18 if is_marker else 1.0)
            card = RoundedRectangle(corner_radius=0.03, width=SLOT * 0.72, height=h,
                                    stroke_width=1.5, stroke_color=C_HOLD if is_marker else C_MUTED,
                                    fill_color=C_HOLD if is_marker else C_DIM, fill_opacity=1.0)
            card.move_to(np.array([slot_x(k), ROW_Y, 0.0]))
            card.add_updater(lambda mob, t_in=t_in: mob.set_opacity(fade(t_in, 0.2)))
            cards.append(card)
            if is_marker:
                lab = _t(MARKER_LABEL, font_size=30 * BIG, color=C_HOLD).next_to(card, UP, buff=0.08)
                lab.add_updater(lambda mob, t_in=t_in: mob.set_opacity(fade(t_in, 0.2)))
                cards.append(lab)
        self.add(*cards)

        # ---- the gaps of the dealt row: a bracket under each, with its count
        BOUNDS = []
        k = 0
        for g, size in enumerate(SIZES):
            BOUNDS.append((k, k + size - 1))
            k += size + 1
        BR_Y = ROW_Y - CARD_H * 0.5 - 0.14
        brackets = []
        if T_GF is not None:
            for g, (k0, k1) in enumerate(BOUNDS):
                t_in = T_GF + (T_GU - T_GF) * g / max(GAPS - 1, 1)
                if k1 >= k0:
                    x0, x1 = slot_x(k0) - SLOT * 0.4, slot_x(k1) + SLOT * 0.4
                else:                      # an empty gap: a tick between the markers
                    x0 = x1 = slot_x(k0) - SLOT * 0.5
                br = VMobject(stroke_color=C_FLOW, stroke_width=4)
                br.set_points_as_corners([np.array([x0, BR_Y + 0.08, 0.0]), np.array([x0, BR_Y, 0.0]),
                                          np.array([x1, BR_Y, 0.0]), np.array([x1, BR_Y + 0.08, 0.0])])
                num = _t(str(SIZES[g]), font_size=30 * BIG, color=C_FLOW).next_to(
                    np.array([(x0 + x1) / 2.0, BR_Y, 0.0]), DOWN, buff=0.08)
                for mob in (br, num):
                    mob.add_updater(lambda mb, t_in=t_in: mb.set_opacity(fade(t_in, 0.3)))
                brackets += [br, num]
            self.add(*brackets)
        NUM_BOTTOM = BR_Y - 0.5 * BIG

        # ---- the averages: one bar per gap, from this deal to the mean of RUNS deals
        if vertical:
            CAP_H = 1.3
            CAP_X, CAP_W, CAP_BOTTOM, CAP_TOP = CX, SW, SY0 + 0.05, SY0 + CAP_H
        else:
            CAP_X, CAP_W, CAP_BOTTOM, CAP_TOP = CX, SW, SY0 + 0.05, SY0 + 0.8
        COUNTER_Y = NUM_BOTTOM - 0.4 * BIG
        BASE = CAP_TOP + 0.25 + 0.45 * BIG          # gap names sit under the base
        CHART_TOP = COUNTER_Y - 0.4 * BIG - 0.5 * BIG   # room for the value labels
        SCALE_MAX = max(max(SIZES), MEAN_GAP + 1 + FOCUS) * 1.08
        UNIT = (CHART_TOP - BASE) / SCALE_MAX
        LEFT_PAD = 1.0 * BIG
        BX0 = SX0 + LEFT_PAD
        BW = (SX1 - BX0) / GAPS

        def ease(u):
            u = min(max(u, 0.0), 1.0)
            return u * u * u if EASE == "slow_start" else u

        def shuffles_now():
            if T_AF is None:
                return 1
            if clk.get_value() < T_SF:
                return 1
            u = (clk.get_value() - T_SF) / max(T_AU - T_SF, 0.5)
            return max(1, int(round(1 + ease(u) * (RUNS - 1))))

        def means_now():
            j = bisect_right(CHECKS, shuffles_now()) - 1
            return CHECKS[max(j, 0)], MEANS[max(j, 0)]

        def grow():
            return 0.0 if T_AF is None else fade(T_AF, 0.6)

        def bars():
            out = VGroup()
            g_in = grow()
            if g_in <= 0.0:
                return out
            _n, means = means_now()
            focus_a = fade(T_FOCUS, 0.5) if T_FOCUS is not None else 0.0
            for g, value in enumerate(means):
                h = max(value * UNIT * g_in, 0.001)
                col = C_FLOW
                if g < FOCUS and focus_a > 0:
                    col = interpolate_color(C_FLOW, C_DONE, focus_a)
                out.add(Rectangle(width=BW * 0.62, height=h, stroke_width=0, fill_color=col,
                                  fill_opacity=0.85).move_to(
                    np.array([BX0 + BW * (g + 0.5), BASE + h / 2.0, 0.0])))
            return out

        VAL_CACHE = {{}}

        def values():
            out = VGroup()
            g_in = grow()
            if g_in < 1.0:
                return out
            n, means = means_now()
            for g, value in enumerate(means):
                text = ("%d" % round(value)) if n == 1 else ("%.1f" % value)
                key = (g, text)
                if key not in VAL_CACHE:
                    VAL_CACHE[key] = _t(text, font_size=30 * BIG, color=C_FG).move_to(
                        np.array([BX0 + BW * (g + 0.5), 0.0, 0.0]))
                mob = VAL_CACHE[key].copy()
                # Over a focus bar the marker block sits on top: lift the value above it.
                lift = UNIT * fade(T_FSUM, 0.4) if (T_FSUM is not None and g < FOCUS) else 0.0
                mob.move_to(np.array([BX0 + BW * (g + 0.5), BASE + value * UNIT + lift + 0.32 * BIG, 0.0]))
                out.add(mob)
            return out

        if T_AF is not None:
            axis = Line([BX0, BASE, 0.0], [SX1, BASE, 0.0], color=C_MUTED, stroke_width=3)
            names = VGroup(*[_t(GAP_LABEL.format(k=g + 1), font_size=24 * BIG, color=C_MUTED).move_to(
                np.array([BX0 + BW * (g + 0.5), BASE - 0.3 * BIG, 0.0])) for g in range(GAPS)])
            if names.width > (SX1 - BX0):
                names.scale((SX1 - BX0) / names.width)
            for mob in (axis, names):
                mob.add_updater(lambda mb: mb.set_opacity(fade(T_AF, 0.5)))
            Y_T = BASE + MEAN_GAP * UNIT
            target = DashedLine([BX0 - 0.1, Y_T, 0.0], [SX1, Y_T, 0.0], color=C_HOLD,
                                stroke_width=4, dash_length=0.14)
            target_label = MarkupText(TARGET_TEXT, font=CJK_FONT, font_size=30 * BIG, color=C_HOLD)
            if target_label.width > LEFT_PAD - 0.15:
                target_label.scale((LEFT_PAD - 0.15) / target_label.width)
            target_label.move_to(np.array([SX0 + (LEFT_PAD - 0.1) / 2.0, Y_T, 0.0]))
            for mob in (target, target_label):
                mob.add_updater(lambda mb: mb.set_opacity(fade(T_TARGET, 0.6)))

            COUNT_CACHE = {{}}

            def counter():
                n = shuffles_now()
                a = fade(T_SF, 0.4) * (1.0 - (fade(T_FOCUS - 0.3, 0.3) if T_FOCUS is not None else 0.0))
                if n not in COUNT_CACHE:
                    word = "shuffle" if n == 1 else "shuffles"
                    text = COUNTER_TEXT.format(k="{{:,}}".format(n)).replace("shuffles", word)
                    COUNT_CACHE[n] = _t(text, font_size=32 * BIG, color=C_MUTED).move_to(
                        np.array([CX, COUNTER_Y, 0.0]))
                return COUNT_CACHE[n].copy().set_opacity(a)

            self.add(axis, names, target, target_label, always_redraw(bars), always_redraw(values),
                     always_redraw(counter))

        # ---- focus: the gaps before the FOCUS-th marker, plus the markers themselves
        if T_FOCUS is not None:
            plus = VGroup()
            for g in range(FOCUS):
                # The marker itself, one item tall, in the marker colour, on top of
                # the gap before it.
                block = Rectangle(width=BW * 0.62, height=UNIT * 1.0, stroke_width=0,
                                  fill_color=C_HOLD, fill_opacity=0.95).move_to(
                    np.array([BX0 + BW * (g + 0.5), BASE + (MEAN_GAP + 0.5) * UNIT, 0.0]))
                plus.add(block)
            plus.add_updater(lambda mob: mob.set_opacity(fade(T_FSUM, 0.4)))
            last = [k for k, x in enumerate(ORDER) if x][FOCUS - 1]
            lo = slot_x(0) - SLOT * 0.45
            hi = slot_x(last) + SLOT * 0.45
            span = RoundedRectangle(corner_radius=0.08, width=hi - lo, height=CARD_H * 1.45,
                                    stroke_color=C_DONE, stroke_width=5, fill_opacity=0.0).move_to(
                np.array([(lo + hi) / 2.0, ROW_Y, 0.0]))
            span.add_updater(lambda mob: mob.set_stroke(opacity=fade(T_FOCUS, 0.5)))
            sum_mob = MarkupText(FOCUS_TEXT, font=CJK_FONT, font_size=40 * BIG, color=C_DONE)
            if sum_mob.width > SW:
                sum_mob.scale(SW / sum_mob.width)
            sum_mob.move_to(np.array([CX, COUNTER_Y, 0.0]))
            sum_mob.add_updater(lambda mob: mob.set_opacity(fade(T_FSUM, 0.4)))
            self.add(span, plus, sum_mob)
    ''')
    body += _captions(m)
    helpers = _src(C.deal, C.gap_sizes, C.choose_deal, C.running_means, cue_seconds)
    del fields
    return _assemble(helpers, body, m)
