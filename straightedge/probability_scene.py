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
walk functions, so this file and the checks run the same code.
"""
from __future__ import annotations

import inspect
from textwrap import dedent

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


def random_walk_scene(m: P.WalkModel) -> str:
    helpers = "\n\n".join(inspect.getsource(fn) for fn in (P.walk_path, P.choose_showcase, P.tally_paths))
    span_exprs = ", ".join(
        f'BEAT_SECONDS.get("b{i + 1:02d}", {P.DEFAULT_SPANS[ph]!r})' for i, ph in enumerate(m.phases)
    )
    beat_calls = "\n".join(
        f'        _beat_stretch(self, "b{i + 1:02d}", clk.animate.set_value(ENDS[{i}]), run_time=SPANS[{i}])'
        for i in range(m.beats)
    )
    body = dedent(f'''
        class GeneratedScene(Scene):
            def construct(self):
                N, START, P_UP, SEED = {m.n!r}, {m.start!r}, {m.p!r}, {m.seed!r}
                EXIT, RUNS = {m.exit!r}, {m.runs!r}
                PHASES = {tuple(m.phases)!r}
                LO, HI = {m.step_seconds[0]!r}, {m.step_seconds[1]!r}
                ABSORB_AT = {m.absorb_at!r}
                CAPTIONS = {dict(m.captions)!r}
                LOW_LABEL, HIGH_LABEL, TITLE = "{_q(m.low_label)}", "{_q(m.high_label)}", "{_q(m.title)}"

                SPANS = [{span_exprs}]
                STARTS, ENDS, acc = [], [], 0.0
                for span in SPANS:
                    STARTS.append(acc)
                    acc += span
                    ENDS.append(acc)
                IA = PHASES.index("absorb")
                WALKING = sum(SPANS[:IA]) + ABSORB_AT * SPANS[IA]
                _seed, PATH, _in_range = choose_showcase(START, N, P_UP, SEED, EXIT, WALKING, LO, HI,
                                                         min_turns={P.MIN_TURNS}, tries={P.SEED_TRIES},
                                                         cap={P.PATH_CAP})
                T = len(PATH) - 1
                END_IS_TOP = PATH[-1] == N
                TALLY = tally_paths(START, N, P_UP, SEED, RUNS, stride={P.TALLY_SEED_STRIDE},
                                    cap={P.PATH_CAP}) if "tally" in PHASES else []

                def phase_start(name):
                    return STARTS[PHASES.index(name)] if name in PHASES else None

                T_ENDS, T_STEPS, T_TALLY = phase_start("ends"), phase_start("steps"), phase_start("tally")

                # Sized for a side column, not a full frame: on a lecture_dark slide the
                # video sits in a ~620px column, where font_size 28 measured ~10px tall.
                # Labels are 42-54 and strokes doubled for that reason.
                W, H = config.frame_width, config.frame_height
                vertical = H > W
                X0, X1 = -0.36 * W, 0.44 * W
                # Raised off centre: the bottom band belongs to captions (see the preamble).
                Y0, Y1 = (-0.20 * H, 0.24 * H) if vertical else (-0.26 * H, 0.31 * H)
                UNIT = (Y1 - Y0) / N

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
                    mob = VMobject(stroke_color=C_FLOW, stroke_width=6, stroke_opacity=0.95 * dimmed())
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

                axis = Line([X0, Y0, 0.0], [X0, Y1, 0.0], color=C_MUTED, stroke_width=3)
                ticks = VGroup(*[Line([X0 - 0.09, ypos(k), 0.0], [X0 + 0.09, ypos(k), 0.0],
                                      color=C_MUTED, stroke_width=2) for k in range(N + 1)])
                lab0 = _t("0", font_size=34).next_to(np.array([X0 - 0.12, Y0, 0.0]), LEFT, buff=0.12)
                labN = _t("N = %d" % N, font_size=34).next_to(np.array([X0 - 0.12, Y1, 0.0]), LEFT, buff=0.12)
                labi = _t("i", font_size=34, color=C_FLOW, slant=ITALIC).next_to(
                    np.array([X0 - 0.12, ypos(START), 0.0]), LEFT, buff=0.12)

                high = _t(HIGH_LABEL, font_size=32, color=C_DONE).next_to(
                    np.array([X0 + 0.25, Y1, 0.0]), UR, buff=0.12)
                low = _t(LOW_LABEL, font_size=32, color=C_WARN).next_to(
                    np.array([X0 + 0.25, Y0, 0.0]), DR, buff=0.12)
                high.add_updater(lambda mob: mob.set_opacity(fade(T_ENDS)))
                low.add_updater(lambda mob: mob.set_opacity(fade(T_ENDS)))

                def caption_mob(phase, markup):
                    mob = MarkupText(markup, font=CJK_FONT, font_size=34)
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

                self.add(axis, ticks, lab0, labN, labi)
                self.add(barrier(Y0, C_WARN, False), barrier(Y1, C_DONE, True))
                self.add(high, low)
                if TITLE:
                    self.add(_t(TITLE, font_size=34).to_edge(UP, buff=0.3))

                if TALLY:
                    LONGEST = max(len(r) - 1 for r in TALLY)
                    TDX = (X1 - X0) / max(LONGEST, 1)
                    IT = PHASES.index("tally")
                    DRAW = max(SPANS[IT] - 2.2, 1.0)
                    SHAPES = []
                    for r in TALLY:
                        v = VMobject(stroke_color=C_DONE if r[-1] == N else C_WARN,
                                     stroke_width=2, stroke_opacity=0.4)
                        v.set_points_as_corners([np.array([X0 + TDX * j, ypos(x), 0.0])
                                                 for j, x in enumerate(r)])
                        SHAPES.append(v)

                    def shown():
                        u = (clk.get_value() - T_TALLY - 0.8) / DRAW
                        return int(min(max(u, 0.0), 1.0) * len(TALLY) + 1e-9)

                    def fan():
                        return VGroup(*SHAPES[:shown()])

                    def count(top):
                        return sum(1 for r in TALLY[:shown()] if (r[-1] == N) == top)

                    # One Text per count value, built on first use. An Integer next to
                    # static text keeps the layout it was arranged with at 0, so a
                    # two-digit count runs into "of 40"; and it draws its digits in a
                    # different face from every other label. At most RUNS+1 values
                    # per row, so the cache is small and each frame reuses them.
                    ROW_CACHE = {{}}

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

                    self.add(always_redraw(fan), always_redraw(lambda: row(True)),
                             always_redraw(lambda: row(False)))

                self.add(always_redraw(trail), always_redraw(axis_marker), always_redraw(token),
                         always_redraw(pulse), always_redraw(step_arrows), p_label, q_label)
        ''').strip("\n")
    return ("import math\nimport random\n\n\n" + helpers.strip() + "\n\n\n" + body + "\n" + beat_calls + "\n")


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
