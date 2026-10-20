"""Manim scene for ``probability/random_walk_exits``, from a checked model.

Layout. Position runs up a vertical number line from ``0`` to ``N``; time runs
to the right. The two ends are drawn as barriers across the whole plot — ruin
in the warning colour, the top in the done colour — so a walk is a path that
wanders right until it touches one of them. That is the standard picture of
gambler's ruin, and it shows what a bare token on a line cannot: *how long* the
walk wandered, and that it stopped.

Timing. One ``ValueTracker`` holds scene time. Every visual is a function of it
and of the beat boundaries, and each beat is a single ``_beat_stretch`` of that
clock across the beat, so the clock is the scene time exactly and nothing drifts.
The showcase walk is chosen *inside the scene* from the measured beat lengths
(see :mod:`straightedge.probability` for why), using the verbatim source of the
walk functions, so this file and the checks run the same code. Moments inside a
beat — a caption card, the last tally walk, a renewal block — are cues, resolved
by the verbatim source of :func:`~straightedge.probability.cue_seconds` for the
same reason.

**Optional parts are emitted only when asked for.** Each feature added after
the first release writes its code into the scene only when its parameter is
set, so a plan that sets none of them gets the scene source — and so the frames
— it always got. ``tests/test_probability_walk.py`` pins that.
"""
from __future__ import annotations

import inspect
from textwrap import dedent, indent

from . import probability as P
from .models import AnimationPlan, Topic
from .topics import scene_for


@scene_for(Topic.PROBABILITY)
def probability_scene(plan: AnimationPlan) -> str:
    """The scene body for a probability plan. Refuses before drawing."""
    concept = plan.concept or P.ConceptProbability.RANDOM_WALK_EXITS
    if concept != P.ConceptProbability.RANDOM_WALK_EXITS:
        return _refusal_scene(f"unknown probability concept {concept!r}")
    try:
        model = P.coerce_model(plan.parameters)
        P.walk_claims(model)
    except P.ProbabilityError as exc:
        return _refusal_scene(str(exc))
    return random_walk_scene(model)


def _q(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _cue(m: P.WalkModel, cue: P.Cue | None) -> str:
    return "None" if cue is None else repr(cue.as_args(m.phases))


def _block(src: str, depth: int = 8) -> str:
    """A code block written flush-left, re-indented to ``depth`` spaces."""
    return indent(dedent(src).strip("\n"), " " * depth) + "\n"


# --------------------------------------------------------------- sections
#
# Each returns source indented for ``construct`` (8 spaces), ending in "\n".


def _labels(m: P.WalkModel, adaptive: bool, fades: dict) -> str:
    axis = dict(m.axis_labels)

    def label(key: str, anchor: str, default: str) -> str:
        if key not in axis:
            return default
        text = axis[key]
        size = 34 if len(text) <= 3 else 28
        size_expr = f"{size} * BIG" if adaptive else f"{size}"
        colour = ", color=C_FLOW" if key == "start" else ""
        slant = ", slant=ITALIC" if (len(text) == 1 and text.isalpha()) else ""
        return (f'_t("{_q(text)}", font_size={size_expr}{colour}{slant}).next_to(\n'
                f'    {anchor}, LEFT, buff=0.12)')

    lab0 = label("low", "np.array([X0 - 0.12, Y0, 0.0])",
                 '_t("0", font_size=34).next_to(np.array([X0 - 0.12, Y0, 0.0]), LEFT, buff=0.12)')
    lab_n = label("high", "np.array([X0 - 0.12, Y1, 0.0])",
                  '_t("N = %d" % N, font_size=34).next_to(np.array([X0 - 0.12, Y1, 0.0]), LEFT, buff=0.12)')
    lab_i = label("start", "np.array([X0 - 0.12, ypos(START), 0.0])",
                  '_t("i", font_size=34, color=C_FLOW, slant=ITALIC).next_to(\n'
                  '    np.array([X0 - 0.12, ypos(START), 0.0]), LEFT, buff=0.12)')
    end_size = "32 * BIG" if adaptive else "32"
    lines = [
        "axis = Line([X0, Y0, 0.0], [X0, Y1, 0.0], color=C_MUTED, stroke_width=3)",
        "ticks = VGroup(*[Line([X0 - 0.09, ypos(k), 0.0], [X0 + 0.09, ypos(k), 0.0],",
        "                      color=C_MUTED, stroke_width=2) for k in range(N + 1)])",
        "lab0 = " + lab0,
        "labN = " + lab_n,
        "labi = " + lab_i,
        "",
        f"high = _t(HIGH_LABEL, font_size={end_size}, color=C_DONE).next_to(",
        "    np.array([X0 + 0.25, Y1, 0.0]), UR, buff=0.12)",
        f"low = _t(LOW_LABEL, font_size={end_size}, color=C_WARN).next_to(",
        "    np.array([X0 + 0.25, Y0, 0.0]), DR, buff=0.12)",
    ]
    src = _block("\n".join(lines))
    if adaptive:
        src += _block('''
            # A narrow frame leaves little margin left of the axis: shrink a label
            # into it rather than let it run off the edge.
            for _lab in (lab0, labN, labi):
                if _lab.get_left()[0] < -W / 2 + 0.08:
                    _lab.scale((_lab.get_right()[0] + W / 2 - 0.08) / _lab.width, about_edge=RIGHT)
        ''')
    ends_out = fades.get("ends")
    step_axis = bool(m.step_axis) and "tally" in m.phases
    if ends_out is None and not step_axis:
        src += _block('''
            high.add_updater(lambda mob: mob.set_opacity(fade(T_ENDS)))
            low.add_updater(lambda mob: mob.set_opacity(fade(T_ENDS)))
        ''')
    else:
        # A step axis is drawn under the bottom barrier, where the low label sits,
        # so it takes the end labels down when the tally starts at the latest.
        out_expr = f"cue_t({_cue(m, ends_out)})" if ends_out is not None else "T_TALLY"
        if ends_out is not None and step_axis:
            out_expr = f"min({out_expr}, T_TALLY)"
        src += _block(f'''
            T_ENDS_OUT = {out_expr}
            high.add_updater(lambda mob: mob.set_opacity(fade(T_ENDS) * (1.0 - fade(T_ENDS_OUT, 0.6))))
            low.add_updater(lambda mob: mob.set_opacity(fade(T_ENDS) * (1.0 - fade(T_ENDS_OUT, 0.6))))
        ''')
    if "axis" in fades:
        src += _block(f'''
            T_AXIS_OUT = cue_t({_cue(m, fades["axis"])})
            for _lab in (lab0, labN, labi):
                _lab.add_updater(lambda mob: mob.set_opacity(1.0 - fade(T_AXIS_OUT, 0.6)))
        ''')
    return src


def _captions(m: P.WalkModel, adaptive: bool) -> str:
    size = "34 * BIG" if adaptive else "34"
    src = _block(f'''
        def caption_mob(phase, markup):
            mob = MarkupText(markup, font=CJK_FONT, font_size={size})
            if mob.width > W * 0.92:
                mob.scale(W * 0.92 / mob.width)
            mob.to_edge(DOWN, buff=0.3)
            t0 = STARTS[PHASES.index(phase)]
            t1 = ENDS[PHASES.index(phase)]
            # In with its phase, out with it (except the last, which holds).
            last = PHASES.index(phase) == len(PHASES) - 1
            mob.add_updater(lambda m, t0=t0, t1=t1, last=last: m.set_opacity(
                fade(t0) * (1.0 if last else 1.0 - fade(t1 - 0.4, 0.4))))
            return mob

        for phase, markup in CAPTIONS.items():
            self.add(caption_mob(phase, markup))
    ''')
    cards = {ph: c for ph, c in m.captions if not isinstance(c, str)}
    if not cards:
        return src
    literal = {
        ph: [(c.text, c.cue.as_args(m.phases), c.build,
              c.until.as_args(m.phases) if c.until else None) for c in phase_cards]
        for ph, phase_cards in cards.items()
    }
    return src + _block(f'''
        # Caption cards: each enters on its own cue. A card with build=True joins
        # the stack above it instead of replacing it, so an argument can be
        # written up line by line; a stack leaves when the next one enters, at its
        # own `until`, or at its phase's end (the last phase holds).
        CARDS = {literal!r}

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
                mobs = [MarkupText(text, font=CJK_FONT, font_size={size}) for text, _, _ in stack]
                group = VGroup(*mobs).arrange(DOWN, buff=0.16)
                if group.width > W * 0.92:
                    group.scale(W * 0.92 / group.width)
                group.to_edge(DOWN, buff=0.3)
                # A stack stays in the band under the plot and its step numbers.
                # That band holds two lines in 16:9 and four or more in an
                # adaptive 9:16; past that it shrinks, so write fewer lines.
                room = (Y0 - 0.5) - group.get_bottom()[1]
                if len(mobs) > 1 and group.height > room > 0:
                    group.scale(room / group.height, about_edge=DOWN)
                t_out = stacks[s + 1][0][1] if s + 1 < len(stacks) else (None if last else ENDS[i])
                untils = [u for _, _, u in stack if u is not None]
                if untils:
                    t_out = min(untils)
                for mob, (_text, t_in, _u) in zip(mobs, stack):
                    mob.add_updater(lambda mb, t_in=t_in, t_out=t_out: mb.set_opacity(
                        fade(t_in) * (1.0 if t_out is None else 1.0 - fade(t_out - 0.4, 0.4))))
                    out.append(mob)
            return out

        for phase, cards in CARDS.items():
            self.add(*card_stacks(phase, cards))
    ''')


def _title(m: P.WalkModel, adaptive: bool, fades: dict) -> str:
    if not adaptive and "title" not in fades:
        return _block('''
            if TITLE:
                self.add(_t(TITLE, font_size=34).to_edge(UP, buff=0.3))
        ''')
    if not m.title:
        return ""
    if adaptive:
        src = _block('''
            def title_mob():
                size = 34 * (1.35 if vertical else 1.0)
                mob = Text(TITLE, font=CJK_FONT, font_size=size)
                words = TITLE.split()
                if vertical and mob.width > W * 0.92 and len(words) > 1:
                    # Two balanced lines rather than one line shrunk to fit.
                    cut = min(range(1, len(words)), key=lambda k: abs(
                        len(" ".join(words[:k])) - len(" ".join(words[k:]))))
                    mob = Text(" ".join(words[:cut]) + "\\n" + " ".join(words[cut:]),
                               font=CJK_FONT, font_size=size, line_spacing=0.8)
                if mob.width > W * 0.92:
                    mob.scale(W * 0.92 / mob.width)
                return mob.to_edge(UP, buff=0.3 if not vertical else 0.45)

            title = title_mob()
        ''')
    else:
        src = _block('''
            title = _t(TITLE, font_size=34).to_edge(UP, buff=0.3)
        ''')
    if "title" in fades:
        src += _block(f'''
            T_TITLE_OUT = cue_t({_cue(m, fades["title"])})
            title.add_updater(lambda mob: mob.set_opacity(1.0 - fade(T_TITLE_OUT, 0.6)))
        ''')
    return src + _block("self.add(title)")


def _rows(adaptive: bool) -> str:
    vertical_rows = '''
            if vertical:
                mob.move_to(np.array([0.0, Y1 + (1.65 if upper else 0.95), 0.0]))
                return mob
    ''' if adaptive else ""
    return _block(f'''
        # Readout rows. The first release drew them in the plot's right-hand
        # corners; an adaptive 9:16 frame centres them in the band above the plot,
        # where nothing else is drawn.
        def place_row(mob, upper, drop=0.0):{vertical_rows}
            if upper:
                mob.next_to(np.array([X1, Y1, 0.0]), UL, buff=0.12)
            else:
                mob.next_to(np.array([X1, Y0 - drop, 0.0]), DL, buff=0.12)
            return mob
    ''')


def _renewal(m: P.WalkModel, adaptive: bool) -> str:
    cues = dict(m.renewal_cues)
    default = {"first": P.Cue("renewal", at=0.10), "blocks": P.Cue("renewal", at=0.25),
               "done": P.Cue("renewal", at=0.75)}
    first, blocks, done = (_cue(m, cues.get(k, default[k])) for k in P.RENEWAL_CUE_KEYS)
    average = cues.get("average")
    text = {k: m.text_for(m.renewal_text, P.RENEWAL_TEXT_DEFAULTS, k) for k in P.RENEWAL_TEXT_KEYS}
    big = "BIG" if adaptive else "1.0"
    return _block(f'''
        # Renewal: the finished walk is cut at each return to the renewal states
        # and the blocks are counted off one by one, so the argument "from here,
        # each block either escapes or puts you back" is drawn on a real walk.
        # Returned blocks settle grey, the block that escapes takes its end's
        # colour, and a dot marks each return.
        R_STATES = {tuple(m.renewal_set())!r}
        R_FIRST, R_ENDS = renewal_blocks(PATH, R_STATES)
        R_BOUNDS = list(zip([R_FIRST] + R_ENDS[:-1], R_ENDS))
        T_RFIRST, T_RBLOCKS, T_RDONE = cue_t({first}), cue_t({blocks}), cue_t({done})
        R_TEXT = {text!r}
        RBIG = {big}

        def block_time(k):
            if len(R_BOUNDS) == 1:
                return T_RBLOCKS
            return T_RBLOCKS + k * (T_RDONE - T_RBLOCKS) / (len(R_BOUNDS) - 1)

        def counted():
            t = clk.get_value()
            return sum(1 for k in range(len(R_BOUNDS)) if t >= block_time(k))

        def path_point(j):
            return np.array([X0 + DX * j, ypos(PATH[j]), 0.0])

        def polyline(i0, i1, col, width, opacity):
            mob = VMobject(stroke_color=col, stroke_width=width, stroke_opacity=opacity)
            mob.set_points_as_corners([path_point(j) for j in range(i0, i1 + 1)])
            return mob

        def renewal_marks():
            t = clk.get_value()
            out = VGroup()
            if t < T_RFIRST:
                return out
            a = dimmed()
            if R_FIRST > 0:
                out.add(polyline(0, R_FIRST, C_FLOW, 7, 0.95 * a * fade(T_RFIRST, 0.4)))
            for k, (i0, i1) in enumerate(R_BOUNDS):
                tk = block_time(k)
                if t < tk:
                    break
                last = k == len(R_BOUNDS) - 1
                fresh = 1.0 - fade(tk + 0.5, 0.6)
                col = exit_colour() if last else interpolate_color(C_MUTED, C_HOLD, fresh)
                out.add(polyline(i0, i1, col, 6 + 3 * fresh, 0.95 * a))
                if not last:
                    out.add(Dot(path_point(i1), radius=0.08, color=C_HOLD).set_opacity(a))
            return out

        NUM_CACHE = {{}}

        def block_numbers():
            a = dimmed() * (1.0 - fade(T_TALLY, 0.6))
            out = VGroup()
            for k in range(counted()):
                if k not in NUM_CACHE:
                    i0, i1 = R_BOUNDS[k]
                    last = k == len(R_BOUNDS) - 1
                    NUM_CACHE[k] = _t(str(k + 1), font_size=24 * RBIG,
                                      color=exit_colour() if last else C_MUTED).move_to(
                        np.array([X0 + DX * (i0 + i1) / 2.0, Y0 - 0.3, 0.0]))
                out.add(NUM_CACHE[k].copy().set_opacity(a))
            return out

        def level_lines():
            a = 0.6 * fade(T_RFIRST, 0.6) * dimmed()
            out = VGroup()
            if a <= 0.0:
                return out
            for r in R_STATES:
                out.add(DashedLine([X0, ypos(r), 0.0], [X1, ypos(r), 0.0], color=C_HOLD,
                                   stroke_width=2.5, dash_length=0.12).set_opacity(a))
            return out

        # Labelled beside the position axis, where the walk never goes.
        level_labels = VGroup()
        if R_TEXT["level"]:
            for r in R_STATES:
                lab = _t(R_TEXT["level"], font_size=24 * RBIG, color=C_HOLD).next_to(
                    np.array([X0 - 0.12, ypos(r), 0.0]), LEFT, buff=0.12)
                margin = -W / 2 + 0.08
                if lab.get_left()[0] < margin:   # a narrow frame: shrink into the margin
                    lab.scale((lab.get_right()[0] - margin) / lab.width, about_edge=RIGHT)
                level_labels.add(lab)
            level_labels.add_updater(lambda mob: mob.set_opacity(
                fade(T_RFIRST, 0.6) * (1.0 - fade(T_TALLY, 0.6))))

        RCOUNT_CACHE = {{}}

        def renewal_row():
            k = counted()
            if k == 0:
                return VGroup()
            if k not in RCOUNT_CACHE:
                key = "out" if k == len(R_BOUNDS) else "count"
                mob = _t(R_TEXT[key].format(k=k, blocks=len(R_BOUNDS)), font_size=34 * RBIG,
                         color=exit_colour() if key == "out" else C_HOLD)
                RCOUNT_CACHE[k] = place_row(mob, not (vertical and RBIG > 1))
            return RCOUNT_CACHE[k].copy().set_opacity(1.0 - fade(T_TALLY, 0.6))

        self.add(always_redraw(level_lines), level_labels, always_redraw(renewal_marks),
                 always_redraw(block_numbers), always_redraw(renewal_row))
    ''') + (_renewal_average(m, average, text["average"]) if average is not None else "")


def _renewal_average(m: P.WalkModel, cue: P.Cue, label: str) -> str:
    mean = float(P.expected_steps(m.start, m.n, m.p))
    return _block(f'''
        # The exact expected length, on the showcase walk's own time axis.
        E_T = {mean!r}
        T_RAVG = cue_t({_cue(m, cue)})
        X_AVG = X0 + DX * E_T
        avg_line = DashedLine([X_AVG, Y0, 0.0], [X_AVG, Y1, 0.0], color=C_HOLD, stroke_width=4,
                              dash_length=0.12)
        avg_label = _t("{_q(label.format(mean=round(mean, 2)))}", font_size=30 * RBIG,
                       color=C_HOLD).next_to(np.array([X_AVG, Y1 - 0.3 * UNIT, 0.0]), RIGHT, buff=0.12)
        for _mob in (avg_line, avg_label):
            _mob.add_updater(lambda mob: mob.set_opacity(fade(T_RAVG, 0.6) * (1.0 - fade(T_TALLY, 0.6))))
        self.add(avg_line, avg_label)
    ''')


def _tally(m: P.WalkModel, adaptive: bool) -> str:
    stat = m.tally_stat
    legacy = stat == "end" and not m.tally_text and not adaptive
    custom_window = m.tally_from is not None or m.tally_until is not None or m.tally_ease != "linear"
    head = ['if TALLY:',
            '    LONGEST = max(len(r) - 1 for r in TALLY)',
            '    TDX = (X1 - X0) / max(LONGEST, 1)',
            '    IT = PHASES.index("tally")']
    if custom_window:
        tf = f"cue_t({_cue(m, m.tally_from)})" if m.tally_from else "T_TALLY + 0.8"
        tu = (f"cue_t({_cue(m, m.tally_until)})" if m.tally_until
              else "T_TALLY + 0.8 + max(SPANS[IT] - 2.2, 1.0)")
        ease = "u * u" if m.tally_ease == "slow_start" else "u"
        head += [f'    TF, TU = {tf}, {tu}', '    DRAW = max(TU - TF, 0.5)']
        shown = ['    def shown():',
                 '        u = min(max((clk.get_value() - TF) / DRAW, 0.0), 1.0)',
                 f'        return int(({ease}) * len(TALLY) + 1e-9)']
    else:
        head += ['    DRAW = max(SPANS[IT] - 2.2, 1.0)']
        shown = ['    def shown():',
                 '        u = (clk.get_value() - T_TALLY - 0.8) / DRAW',
                 '        return int(min(max(u, 0.0), 1.0) * len(TALLY) + 1e-9)']
    if not legacy:
        head += [f'    BIG_ROW = {"BIG" if adaptive else "1.0"}']
    head += ['    SHAPES = []',
             '    for r in TALLY:',
             '        v = VMobject(stroke_color=C_DONE if r[-1] == N else C_WARN,',
             '                     stroke_width=2, stroke_opacity=0.4)',
             '        v.set_points_as_corners([np.array([X0 + TDX * j, ypos(x), 0.0])',
             '                                 for j, x in enumerate(r)])',
             '        SHAPES.append(v)',
             '']
    head += shown
    head += ['',
             '    def fan():',
             '        return VGroup(*SHAPES[:shown()])',
             '',
             '    def count(top):',
             '        return sum(1 for r in TALLY[:shown()] if (r[-1] == N) == top)',
             '']
    src = _block("\n".join(head)) + "\n"
    ttext = {k: m.text_for(m.tally_text, P.TALLY_TEXT_DEFAULTS, k) for k in P.TALLY_TEXT_DEFAULTS}
    if legacy:
        rows = '''
            # One Text per count value, built on first use. An Integer next to
            # static text keeps the layout it was arranged with at 0, so a
            # two-digit count runs into "of 40"; and it draws its digits in a
            # different face from every other label. At most RUNS+1 values
            # per row, so the cache is small and each frame reuses them.
            ROW_CACHE = {}

            def row(top):
                key = (top, count(top))
                if key not in ROW_CACHE:
                    label = "reached N" if top else "reached 0"
                    mob = _t("%s   %d of %d" % (label, key[1], len(TALLY)), font_size=34,
                             color=C_DONE if top else C_WARN)
                    if top:
                        mob.next_to(np.array([X1, Y1, 0.0]), UL, buff=0.12)
                    else:
                        mob.next_to(np.array([X1, Y0, 0.0]), DL, buff=0.12)
                    ROW_CACHE[key] = mob
                return ROW_CACHE[key].copy().set_opacity(fade(T_TALLY, 0.8))
        '''
    elif stat == "end":
        rows = f'''
            ROW_CACHE = {{}}
            TALLY_TEXT = {ttext!r}

            def row(top):
                key = (top, count(top))
                if key not in ROW_CACHE:
                    fmt = TALLY_TEXT["top" if top else "zero"]
                    mob = _t(fmt.format(count=key[1], runs=len(TALLY)), font_size=34 * BIG_ROW,
                             color=C_DONE if top else C_WARN)
                    ROW_CACHE[key] = place_row(mob, top)
                return ROW_CACHE[key].copy().set_opacity(fade(T_TALLY, 0.8))
        '''
    else:
        drop = "0.5" if m.step_axis else "0.0"
        rows = f'''
            # A running statistic of the walks drawn so far, cached per count like
            # the end tally: at most RUNS+1 values per row.
            ROW_CACHE = {{}}
            TALLY_TEXT = {ttext!r}
            STEPS_OF = [len(r) - 1 for r in TALLY]

            def row(top):
                k = shown()
                key = (top, k)
                if key not in ROW_CACHE:
                    if top:
                        mob = _t(TALLY_TEXT["count"].format(k=k, runs=len(TALLY)),
                                 font_size=30 * BIG_ROW, color=C_MUTED)
                    else:
                        seen = sorted(STEPS_OF[:k])
                        if k:
                            text = TALLY_TEXT["stat"].format(k=k, runs=len(TALLY),
                                                             mean=sum(seen) / k, median=seen[k // 2])
                        else:
                            text = TALLY_TEXT["stat"].split("{{")[0].rstrip() + "  -"
                        big = BIG_ROW * (1.2 if vertical and BIG_ROW > 1 else 1.0)
                        mob = _t(text, font_size=36 * big, color=C_HOLD)
                    ROW_CACHE[key] = place_row(mob, top, drop={drop})
                return ROW_CACHE[key].copy().set_opacity(fade(T_TALLY, 0.8))
        '''
    src += _block(rows, 12) + "\n"
    if m.tally_target is not None:
        src += _block(f'''
            X_TARGET = X0 + TDX * {m.tally_target!r}
            target_line = DashedLine([X_TARGET, Y0, 0.0], [X_TARGET, Y1, 0.0], color=C_HOLD,
                                     stroke_width=4, dash_length=0.12)
            target_label = _t("{_q(m.tally_target_label)}", font_size=34, color=C_HOLD).next_to(
                np.array([X_TARGET, Y1 - 0.25 * UNIT, 0.0]), RIGHT, buff=0.12)
            target_line.add_updater(lambda mob: mob.set_opacity(fade(T_TALLY + 0.8, 0.8)))
            target_label.add_updater(lambda mob: mob.set_opacity(fade(T_TALLY + 0.8, 0.8)))
            self.add(target_line, target_label)
        ''', 12) + "\n"
    if stat == "histogram":
        src += _block('''
            # Where the walks ended in time: one bar per length, under the fan and
            # on the fan's step scale, so a bar stands where its walks stopped.
            HIST_MAX = max(STEPS_OF.count(s) for s in set(STEPS_OF))
            HIST_H = 0.55 * (Y1 - Y0)

            def histogram():
                counts = {}
                for s in STEPS_OF[:shown()]:
                    counts[s] = counts.get(s, 0) + 1
                out = VGroup()
                for s, c in counts.items():
                    h = HIST_H * c / HIST_MAX
                    out.add(Rectangle(width=TDX * 0.9, height=h, stroke_width=0, fill_color=C_HOLD,
                                      fill_opacity=0.75 * fade(T_TALLY, 0.8)).move_to(
                        np.array([X0 + TDX * s, Y0 + h / 2.0, 0.0])))
                return out

            self.add(always_redraw(histogram))
        ''', 12) + "\n"
    if m.step_axis:
        src += _block(f'''
            # Step counts under the fan, on the fan's own scale, so a length the
            # narration names can be read off the picture.
            STEP_TICK = next(s for s in (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000)
                             if LONGEST / s <= 8)
            step_label = _t("{_q(m.step_axis)}", font_size=24 * BIG_ROW, color=C_MUTED).next_to(
                np.array([X1, Y0 - 0.32, 0.0]), LEFT, buff=0.0)
            step_axis = VGroup(step_label)
            for s in range(0, LONGEST + 1, STEP_TICK):
                x = X0 + TDX * s
                number = _t(str(s), font_size=24 * BIG_ROW, color=C_MUTED).move_to(
                    np.array([x, Y0 - 0.32, 0.0]))
                if number.get_right()[0] > step_label.get_left()[0] - 0.15:
                    break
                step_axis.add(Line([x, Y0, 0.0], [x, Y0 - 0.1, 0.0], color=C_MUTED, stroke_width=2))
                step_axis.add(number)
            step_axis.add_updater(lambda mob: mob.set_opacity(fade(T_TALLY + 0.8, 0.8)))
            self.add(step_axis)
        ''', 12) + "\n"
    src += _block('''
        self.add(always_redraw(fan), always_redraw(lambda: row(True)),
                 always_redraw(lambda: row(False)))
    ''', 12)
    return src


def random_walk_scene(m: P.WalkModel) -> str:
    adaptive = m.layout == "adaptive"
    fades = dict(m.labels_until)
    uses_cues = bool(P.all_cues(m)) or "renewal" in m.phases
    fns = [P.walk_path, P.choose_showcase, P.tally_paths]
    if m.showcase_steps is not None:
        fns.append(P.showcase_of_length)
    if uses_cues:
        fns.append(P.cue_seconds)
    if "renewal" in m.phases:
        fns.append(P.renewal_blocks)
    helpers = "\n\n".join(inspect.getsource(fn) for fn in fns)
    span_exprs = ", ".join(
        f'BEAT_SECONDS.get("b{i + 1:02d}", {P.DEFAULT_SPANS[ph]!r})' for i, ph in enumerate(m.phases)
    )
    beat_calls = "\n".join(
        f'        _beat_stretch(self, "b{i + 1:02d}", clk.animate.set_value(ENDS[{i}]), run_time=SPANS[{i}])'
        for i in range(m.beats)
    )
    legacy_captions = {ph: c for ph, c in m.captions if isinstance(c, str)}
    if m.showcase_steps is None:
        showcase = _block(f'''
            _seed, PATH, _in_range = choose_showcase(START, N, P_UP, SEED, EXIT, WALKING, LO, HI,
                                                     min_turns={P.MIN_TURNS}, tries={P.SEED_TRIES},
                                                     cap={P.PATH_CAP})
        ''')
    else:
        showcase = _block(f'''
            # A walk of a stated length, so the narration can say how long it is.
            _seed, PATH, _in_range = showcase_of_length(START, N, P_UP, SEED, EXIT, {m.showcase_steps!r},
                                                        WALKING, LO, HI, min_turns={P.MIN_TURNS},
                                                        tries={P.SEED_TRIES}, cap={P.PATH_CAP})
        ''')
    absorb_cue = isinstance(m.absorb_at, P.Cue)

    cues = ""
    if uses_cues:
        cues = _block(f'''
            SENTENCE_COUNTS = {P.sentence_counts(m)!r}

            def cue_t(args):
                if args is None:
                    return None
                return cue_seconds(STARTS, SPANS, BEAT_SECONDS, *args,
                                   count=SENTENCE_COUNTS.get(args[0], 1))
        ''')
    walking = (_block(f"WALKING = cue_t({_cue(m, m.absorb_at)})") if absorb_cue
               else _block("WALKING = sum(SPANS[:IA]) + ABSORB_AT * SPANS[IA]"))
    if adaptive:
        frame = _block('''
            X0, X1 = -0.36 * W, 0.44 * W
            # Adaptive: in 9:16 the plot takes half the height, the title two
            # lines, readouts the band above the plot and captions the band below.
            Y0, Y1 = (-0.31 * H, 0.24 * H) if vertical else (-0.26 * H, 0.31 * H)
            BIG = 1.2 if vertical else 1.0
        ''')
    else:
        frame = _block('''
            X0, X1 = -0.36 * W, 0.44 * W
            # Raised off centre: the bottom band belongs to captions (see the preamble).
            Y0, Y1 = (-0.20 * H, 0.24 * H) if vertical else (-0.26 * H, 0.31 * H)
        ''')
    needs_rows = adaptive or "renewal" in m.phases or m.tally_stat != "end" or bool(m.tally_text)
    rows = _rows(adaptive) if needs_rows else ""
    trail_dim = " * (1.0 - 0.6 * fade(T_RFIRST, 0.5))" if "renewal" in m.phases else ""
    renewal_pre = _block("T_RFIRST = cue_t(%s)" % _cue(m, dict(m.renewal_cues).get(
        "first", P.Cue("renewal", at=0.10)))) if "renewal" in m.phases else ""

    body = dedent(f'''
        class GeneratedScene(Scene):
            def construct(self):
                N, START, P_UP, SEED = {m.n!r}, {m.start!r}, {m.p!r}, {m.seed!r}
                EXIT, RUNS = {m.exit!r}, {m.runs!r}
                PHASES = {tuple(m.phases)!r}
                LO, HI = {m.step_seconds[0]!r}, {m.step_seconds[1]!r}
                ABSORB_AT = {(None if absorb_cue else m.absorb_at)!r}
                CAPTIONS = {legacy_captions!r}
                LOW_LABEL, HIGH_LABEL, TITLE = "{_q(m.low_label)}", "{_q(m.high_label)}", "{_q(m.title)}"

                SPANS = [{span_exprs}]
                STARTS, ENDS, acc = [], [], 0.0
                for span in SPANS:
                    STARTS.append(acc)
                    acc += span
                    ENDS.append(acc)
                IA = PHASES.index("absorb")
        @@CUES@@@@WALKING@@@@SHOWCASE@@
                T = len(PATH) - 1
                END_IS_TOP = PATH[-1] == N
                TALLY = tally_paths(START, N, P_UP, SEED, RUNS, stride={P.TALLY_SEED_STRIDE},
                                    cap={P.PATH_CAP}) if "tally" in PHASES else []

                def phase_start(name):
                    return STARTS[PHASES.index(name)] if name in PHASES else None

                T_ENDS, T_STEPS, T_TALLY = phase_start("ends"), phase_start("steps"), phase_start("tally")
        @@RPRE@@

                # Sized for a side column, not a full frame: on a lecture_dark slide the
                # video sits in a ~620px column, where font_size 28 measured ~10px tall.
                # Labels are 42-54 and strokes doubled for that reason.
                W, H = config.frame_width, config.frame_height
                vertical = H > W
        @@FRAME@@        UNIT = (Y1 - Y0) / N

                def ypos(k):
                    return Y0 + UNIT * k

                clk = ValueTracker(0.0)

                def fade(t0, dur=0.6):
                    if t0 is None:
                        return 0.0
                    return min(max((clk.get_value() - t0) / dur, 0.0), 1.0)

                def walk_fraction():
                    return min(max(clk.get_value() / WALKING, 0.0), 1.0)

                DX = (X1 - X0) / max(T, 1)

                def head():
                    s = walk_fraction() * T
                    k = min(int(s), T)
                    if k >= T:
                        return np.array([X0 + DX * T, ypos(PATH[T]), 0.0])
                    frac = s - k
                    a, b = PATH[k], PATH[k + 1]
                    return np.array([X0 + DX * s, ypos(a + (b - a) * frac), 0.0])

                def dimmed():
                    return 1.0 - 0.92 * fade(T_TALLY, 0.8)

                def trail():
                    s = walk_fraction() * T
                    k = min(int(s), T)
                    pts = [np.array([X0 + DX * j, ypos(PATH[j]), 0.0]) for j in range(k + 1)]
                    if k < T:
                        pts.append(head())
                    mob = VMobject(stroke_color=C_FLOW, stroke_width=6, stroke_opacity=0.95 * dimmed(){trail_dim})
                    if len(pts) >= 2:
                        mob.set_points_as_corners(pts)
                    return mob

                def absorbed():
                    return clk.get_value() >= WALKING

                def exit_colour():
                    return C_DONE if END_IS_TOP else C_WARN

                def token():
                    col = exit_colour() if absorbed() else C_FLOW
                    return Dot(head(), radius=0.14, color=col).set_opacity(dimmed())

                def axis_marker():
                    y = head()[1]
                    col = exit_colour() if absorbed() else C_FLOW
                    return Dot(np.array([X0, y, 0.0]), radius=0.09, color=col).set_opacity(dimmed())

                def pulse():
                    u = clk.get_value() - WALKING
                    if u < 0 or u > 1.2:
                        return VGroup()
                    u /= 1.2
                    return Circle(radius=0.14 + 0.6 * u, color=exit_colour(), stroke_width=5,
                                  stroke_opacity=1.0 - u).move_to(head())

                def barrier(y, colour, is_top):
                    def build():
                        hit = absorbed() and END_IS_TOP == is_top
                        width = 8 if hit and T_TALLY is None else (8 if hit and clk.get_value() < T_TALLY else 4)
                        return Line([X0, y, 0.0], [X1, y, 0.0], color=colour, stroke_width=width)
                    return always_redraw(build)

                def step_arrows():
                    a = fade(T_STEPS) * (1.0 - fade(WALKING - 0.4, 0.4))
                    if a <= 0.0:
                        return VGroup()
                    h = head() + np.array([0.32, 0.0, 0.0])
                    up = Arrow(h, h + np.array([0.0, UNIT, 0.0]), buff=0.0, color=C_DONE,
                               stroke_width=4, max_tip_length_to_length_ratio=0.35)
                    down = Arrow(h, h - np.array([0.0, UNIT, 0.0]), buff=0.0, color=C_WARN,
                                 stroke_width=4, max_tip_length_to_length_ratio=0.35)
                    return VGroup(up, down).set_opacity(a)

                p_label = _t("p", font_size=38, color=C_DONE, slant=ITALIC)
                q_label = _t("q", font_size=38, color=C_WARN, slant=ITALIC)
                p_label.add_updater(lambda mob: mob.move_to(head() + np.array([0.62, 0.5 * UNIT, 0.0]))
                                    .set_opacity(fade(T_STEPS) * (1.0 - fade(WALKING - 0.4, 0.4))))
                q_label.add_updater(lambda mob: mob.move_to(head() + np.array([0.62, -0.5 * UNIT, 0.0]))
                                    .set_opacity(fade(T_STEPS) * (1.0 - fade(WALKING - 0.4, 0.4))))

        @@ROWS@@@@LABELS@@

        @@CAPTIONS@@

                self.add(axis, ticks, lab0, labN, labi)
                self.add(barrier(Y0, C_WARN, False), barrier(Y1, C_DONE, True))
                self.add(high, low)
        @@TITLE@@

        @@TALLY@@

                self.add(always_redraw(trail), always_redraw(axis_marker), always_redraw(token),
                         always_redraw(pulse), always_redraw(step_arrows), p_label, q_label)
        @@RENEWAL@@''').strip("\n")
    sections = {
        "@@CUES@@": cues, "@@WALKING@@": walking, "@@SHOWCASE@@": showcase, "@@FRAME@@": frame, "@@ROWS@@": rows,
        "@@RPRE@@": renewal_pre, "@@LABELS@@": _labels(m, adaptive, fades),
        "@@CAPTIONS@@": _captions(m, adaptive), "@@TITLE@@": _title(m, adaptive, fades),
        "@@TALLY@@": _tally(m, adaptive),
        "@@RENEWAL@@": _renewal(m, adaptive) if "renewal" in m.phases else "",
    }
    for marker, src in sections.items():
        body = body.replace(marker + "\n", src).replace(marker, src)
    return ("import math\nimport random\n\n\n" + helpers.strip() + "\n\n\n" + body.rstrip() + "\n"
            + beat_calls + "\n")


def _refusal_scene(reason: str) -> str:
    """A scene that states the refusal, for a caller that skipped the check."""
    return "\n".join([
        "class GeneratedScene(Scene):",
        "    def construct(self):",
        '        title = _t("Nothing to draw", font_size=34).to_edge(UP)',
        '        reason = _t("%s", font_size=22)' % _q(reason),
        "        self.play(Write(title), FadeIn(reason))",
        "        self.wait(2)",
    ])
