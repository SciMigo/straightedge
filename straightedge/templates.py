from __future__ import annotations

import math
from textwrap import dedent

from .aspect import LANDSCAPE, frame_config_source
from .calculus import ConceptCalculus
from .conics import CONE_HALF_ANGLE_TAN, CONE_TAN_MAX, CONE_TAN_MIN, ConceptConic
from .expr import to_latex_expr, to_numpy_expr, validate_expression
from .fonts import DEFAULT_CJK_FONT
from .labels import DEFAULT_LANGUAGE, translate
from .linalg import (
    IDENTITY,
    VIEWS,
    ConceptLinAlg,
    check_view,
    coerce_grid,
    coerce_matrix,
    coerce_vectors,
    determinant,
    eigenpairs,
    fmt,
    shape,
    span_dimension,
    steps_for,
)
from .models import AnimationPlan, Topic
from .topics import scene_builder, scene_for
from .style import TEXTBOOK, Style
from .solids3d import (
    Concept3D,
    SOLID_HELPERS_SRC,
    SolidSpec,
    cube_section_code,
    section_points_latex,
    solid_construction_code,
    solid_title_zh,
    solid_volume_latex,
    three_views_code,
    vertex_name_latex,
)
from .trig import (
    Concept as ConceptTrig,
    TrigSpec,
    amplitude_latex,
    midline_latex,
    period_latex,
    period_value,
    pi_axis_ticks,
    trig_func_zh,
    trig_title_latex,
)

# Every template defines this scene class; renderer.render_scene targets it.
SCENE_CLASS_NAME = "GeneratedScene"


def qc_tail_source(sidecar_path: str) -> str:
    """Source that dumps the finished scene's extents for the caller to check.

    **Why the scene has to do this at all.** ``qc.check`` reads a *built* scene,
    and rendering happens in a Manim subprocess — the parent that asked for the
    render never holds the object. Somebody has to carry the measurements back
    across that boundary, and only code running inside the render can take them.

    **Why it wraps ``construct`` rather than overriding ``tear_down``.** Manim's
    ``Scene.render`` calls ``self.remove(*self.mobjects)`` between the two, so a
    ``tear_down`` hook measures an empty scene and reports every render as
    ``empty`` — the check firing on its own blind spot. Wrapping is also why
    this is emitted at module scope after the class: appending a statement to
    ``construct`` would depend on how each builder's body happens to end.

    **Why it measures and does not judge.** The checks stay in
    :mod:`straightedge.qc`, in the parent. What crosses the process boundary is
    numbers, so a finding can be re-derived, re-tuned, or reported differently
    without re-rendering anything.

    **Why every failure here is swallowed.** This runs after a render that has
    already cost about ten minutes of a core. Nothing a measurement pass can
    discover about itself is worth destroying that, and the import is lazy for
    the same reason: the emitted scene must still render on a host with Manim
    and no ``straightedge`` — which is exactly the render container's situation.
    """
    return dedent(
        f'''
        def _qc_dump(scene):
            """Record what was drawn. Never raises; see qc_tail_source."""
            try:
                import json
                from straightedge.qc import boxes_from_scene, frame_from_scene

                width, height = frame_from_scene(scene)
                payload = {{
                    "frame": [width, height],
                    "boxes": [
                        {{"label": b.label, "x0": b.x0, "x1": b.x1,
                          "y0": b.y0, "y1": b.y1, "kind": b.kind,
                          "path": [[list(p) for p in line] for line in b.path]}}
                        for b in boxes_from_scene(scene)
                    ],
                }}
                with open({sidecar_path!r}, "w", encoding="utf-8") as handle:
                    json.dump(payload, handle)
            except Exception:
                pass


        def _qc_wrap(cls):
            inner = cls.construct

            def construct(self):
                inner(self)
                _qc_dump(self)

            cls.construct = construct
            return cls


        _qc_wrap({SCENE_CLASS_NAME})
        '''
    ).strip()


def scene_code_for(
    plan: AnimationPlan,
    font: str = DEFAULT_CJK_FONT,
    beat_seconds: dict[str, float] | None = None,
    aspect: str = LANDSCAPE,
    language: str = DEFAULT_LANGUAGE,
    qc_sidecar: str | None = None,
    style: Style = TEXTBOOK,
) -> str:
    """Python source for one scene.

    ``beat_seconds`` maps a beat key to the measured length of its narration
    clip. When supplied, a converted builder spends exactly that long on the
    matching step, so the animation follows the voice instead of a duration
    somebody guessed. When omitted — the CLI, a silent render, a builder that
    has not been converted — every step keeps the timing it already had.

    ``aspect`` sets the frame the scene composes into. Pixels are the renderer's
    half of the job; see :mod:`straightedge.aspect` for why both are needed.

    ``language`` rewrites the on-screen labels. Applied to the finished source
    rather than inside each builder, so labels substituted in from ``solids3d``
    and ``trig`` are covered too; see :mod:`straightedge.labels`.

    ``qc_sidecar`` names a file the finished scene writes its extents to, for
    the caller to check once the render subprocess has exited. Off by default:
    the emitted scene otherwise depends on nothing but Manim, and that is worth
    keeping for hosts that render without this package installed.

    ``style`` picks the palette. It is **resolved here and baked into the emitted
    source as hex literals** — the generated scene must render on a host with
    Manim and no ``straightedge`` (see :func:`qc_tail_source`), so it cannot
    import a theme. The default is :data:`~straightedge.style.TEXTBOOK`, whose
    values are Manim's own constants, which is what these builders drew with
    before the palette was named; passing it changes no pixel.
    """
    # Unknown topics fall back to the geometry scene, as they always have.
    # `topics.verify` makes that a genuine fallback rather than a silent
    # gap: a registered topic without a scene builder fails at import.
    body = (scene_builder(plan.topic) or _geometry_scene)(plan)
    code = _preamble(font, beat_seconds, aspect, style) + "\n\n\n" + body
    if qc_sidecar is not None:
        code += "\n\n\n" + qc_tail_source(qc_sidecar)
    return translate(code, language)


def _palette_source(style: Style) -> str:
    """The chosen theme, as colour constants the emitted scene can use directly.

    Named with a ``C_`` prefix rather than shadowing Manim's own colour
    constants: the scene does ``from manim import *``, and rebinding those would
    leave a reader unable to tell a themed colour from a Manim default. The role
    names are the ones in :mod:`straightedge.style`, so the generated source says
    what a colour is *for* — a warning rather than a particular red — which is
    what makes it re-themable without re-reading every builder.

    **Wrapped in ``ManimColor``, not left as bare strings.** Manim accepts a hex
    string almost everywhere, which makes the exception easy to miss:
    ``interpolate_color`` calls a method on its first argument, so a string
    raises ``AttributeError: 'str' object has no attribute 'interpolate'`` — and
    raises it *during* the render, long after the source looked fine. The Riemann
    builder gradients its rectangles that way. Constructing the colours here
    removes the class of failure instead of fixing the one caller that found it.
    """
    tokens = ("fg", "muted", "dim", "rule", "ink", "well",
              "flow", "hold", "deep", "done", "warn", "aux", "warm")
    lines = "\n        ".join(
        f'C_{name.upper()} = ManimColor("{getattr(style, name)}")'
        for name in tokens
    )
    return (f"# Palette: {style.name}. Resolved from straightedge.style at\n"
            f"        # generation time, so this scene needs only Manim to render.\n"
            f"        {lines}")


def _preamble(
    font: str,
    beat_seconds: dict[str, float] | None = None,
    aspect: str = LANDSCAPE,
    style: Style = TEXTBOOK,
) -> str:
    # Imports + a CJK-aware Text wrapper shared by every scene, so 中文 labels
    # render with a real font instead of tofu boxes. Solid-geometry helpers
    # follow so 3D scenes can call ``make_cube`` / ``label_vertices`` etc.
    beats = dict(beat_seconds or {})
    # The frame is written at module scope so it lands before the Scene is
    # constructed. Without it Manim derives frame width from the default 8-unit
    # height and the output's pixel ratio — 4.5 units across for a 9:16 cut, so
    # a scene authored for landscape draws off both sides of its own picture.
    # Emitted for landscape too, where the values are Manim's own defaults: a
    # scene that states its frame cannot disagree with the one QC measures.
    # Re-indented to match the literal below: ``dedent`` strips the *common*
    # leading whitespace, so one flush-left continuation line would leave the
    # whole preamble indented.
    frame_config = frame_config_source(aspect).replace("\n", "\n        ")
    palette = _palette_source(style)
    base = dedent(
        f'''
        from manim import *

        {frame_config}


        CJK_FONT = "{font}"


        {palette}


        # The theme has to reach the things no builder names a colour for. A
        # light palette otherwise renders dark marks on Manim's black default —
        # worse than no theme at all, because it looks like a bug in the scene
        # rather than a missing wire. Set once, at module scope, before any
        # mobject is constructed:
        #   * the background, which nothing else sets;
        #   * the default text colour, which every unstyled label inherits;
        #   * axes, whose lines default to white;
        #   * DecimalNumber, which is what an axis draws its tick labels with and
        #     is neither a Text nor a MathTex — miss it and a light theme loses
        #     every number on both axes while everything else looks right.
        config.background_color = C_INK
        Text.set_default(color=C_FG)
        MathTex.set_default(color=C_FG)
        Tex.set_default(color=C_FG)
        DecimalNumber.set_default(color=C_FG)
        Axes.set_default(axis_config={{"color": C_FG}})


        # The bottom of the frame belongs to captions. A formula sitting on the
        # edge and a sentence above it occupy roughly 1.5 units together, and a
        # plot reaching into that band puts its tick row through the text —
        # which is exactly what shipped in derivative_tangent and
        # riemann_integral, in both languages, until QC could see a real render.
        # Both numbers live here so a builder cannot drift from the budget by
        # itself, and so fixing the budget fixes every plot that uses it.
        PLOT_Y_LENGTH = 4.3
        PLOT_SHIFT = UP * 0.5


        def _t(text, **kwargs):
            """A label that is guaranteed to fit inside the frame.

            Positions and font sizes across these scenes were tuned against
            Chinese, which is far denser than the languages it gets translated
            into — one 20-character caption becomes 66 in English — so a layout
            that fits comfortably in one language runs off both edges in
            another. The same happens to any long label in a 9-unit-wide
            vertical cut. Shrinking to fit keeps the text on screen; it is the
            fallback, not the plan, so translations are still written short.
            """
            kwargs.setdefault("font", CJK_FONT)
            mob = Text(text, **kwargs)
            limit = config.frame_width * 0.92
            if mob.width > limit > 0:
                mob.scale(limit / mob.width)
            return mob


        BEAT_SECONDS = {beats!r}


        def _beat(scene, key, *anims, run_time=None, reveal=None):
            """Spend this beat's narration length, then hold.

            With no measured length the step keeps whatever timing it was
            written with, so an unconverted builder and a silent render behave
            exactly as before. That fallback is what lets builders be converted
            one at a time instead of all at once.
            """
            span = BEAT_SECONDS.get(key)
            if span is None:
                if anims:
                    scene.play(*anims, **({{"run_time": run_time}} if run_time else {{}}))
                return
            if not anims:
                scene.wait(span)
                return
            used = min(reveal or run_time or 1.4, max(span - 0.2, 0.2))
            scene.play(*anims, run_time=used)
            rest = span - used
            if rest > 0.02:
                scene.wait(rest)


        def _beat_stretch(scene, key, *anims, run_time=None, tail=0.0):
            """Spread the animation across the whole beat.

            For a sweep the motion *is* the content, so it should occupy the
            sentence describing it rather than finishing early and leaving a
            frozen frame.
            """
            span = BEAT_SECONDS.get(key)
            if span is None:
                if anims:
                    scene.play(*anims, **({{"run_time": run_time}} if run_time else {{}}))
                return
            scene.play(*anims, run_time=max(span - tail, 0.3), rate_func=linear)
            if tail > 0.02:
                scene.wait(tail)
        '''
    ).strip()
    return base + "\n\n\n" + SOLID_HELPERS_SRC


@scene_for(Topic.GEOMETRY)
def _geometry_scene(plan: AnimationPlan) -> str:
    return dedent(
        '''
        class GeneratedScene(Scene):
            def construct(self):
                title = _t("几何关系演示", font_size=40).to_edge(UP)
                a = np.array([-3, -1.4, 0])
                b = np.array([2.8, -1.4, 0])
                c = np.array([-0.6, 1.7, 0])
                triangle = Polygon(a, b, c, color=C_FLOW)
                labels = VGroup(
                    _t("A", font_size=28).next_to(a, DOWN),
                    _t("B", font_size=28).next_to(b, DOWN),
                    _t("C", font_size=28).next_to(c, UP),
                )
                angle = Angle(Line(a, c), Line(a, b), radius=0.55, color=C_HOLD)
                side = Line(a, b, color=C_DONE, stroke_width=8)
                conclusion = _t("通过标注边和角，观察几何关系", font_size=30).to_edge(DOWN)

                self.play(Write(title))
                self.play(Create(triangle), FadeIn(labels))
                self.play(Create(angle), Create(side))
                self.play(Write(conclusion))
                self.wait(1)
        '''
    ).strip()


@scene_for(Topic.TRIG)
def _trig_scene(plan: AnimationPlan) -> str:
    builder = _TRIG_CONCEPT_BUILDERS.get(plan.concept, _trig_basic_scene)
    return builder(plan)


def _trig_basic_scene(plan: AnimationPlan) -> str:
    return dedent(
        '''
        class GeneratedScene(Scene):
            def construct(self):
                title = _t("正弦函数的周期与振幅", font_size=38).to_edge(UP)
                axes = Axes(
                    x_range=[-0.5, TAU + 0.8, PI / 2],
                    y_range=[-1.5, 1.5, 1],
                    x_length=9,
                    y_length=4,
                    tips=False,
                ).shift(DOWN * 0.2)
                curve = axes.plot(lambda x: np.sin(x), x_range=[0, TAU], color=C_FLOW)
                amp_line = Line(axes.c2p(PI / 2, 0), axes.c2p(PI / 2, 1), color=C_HOLD)
                period_line = Line(axes.c2p(0, -1.2), axes.c2p(TAU, -1.2), color=C_DONE)
                amp_label = _t("振幅 = 1", font_size=28, color=C_HOLD).next_to(amp_line, RIGHT)
                period_label = _t("周期 = 2π", font_size=28, color=C_DONE).next_to(period_line, DOWN)

                self.play(Write(title), Create(axes))
                self.play(Create(curve), run_time=2)
                self.play(Create(amp_line), Write(amp_label))
                self.play(Create(period_line), Write(period_label))
                self.wait(1)
        '''
    ).strip()


def _unit_circle_to_sine_scene(plan: AnimationPlan) -> str:
    return dedent(
        r'''
        class GeneratedScene(Scene):
            def construct(self):
                title = _t("单位圆生成正弦函数", font_size=38).to_edge(UP)

                circle_origin = LEFT * 4.0 + DOWN * 0.15
                radius = 1.35
                circle = Circle(radius=radius, color=C_FLOW).move_to(circle_origin)
                circle_axes = VGroup(
                    Line(circle_origin + LEFT * 1.65, circle_origin + RIGHT * 1.65, color=C_DIM, stroke_width=2),
                    Line(circle_origin + DOWN * 1.65, circle_origin + UP * 1.65, color=C_DIM, stroke_width=2),
                )
                circle_label = _t("单位圆", font_size=26).next_to(circle, DOWN, buff=0.28)

                graph_axes = Axes(
                    x_range=[0, TAU, PI / 2],
                    y_range=[-1.35, 1.35, 1],
                    x_length=6.4,
                    y_length=3.2,
                    tips=False,
                ).shift(RIGHT * 1.6 + DOWN * 0.15)
                x_labels = VGroup(
                    MathTex(r"\frac{\pi}{2}", font_size=22).next_to(graph_axes.c2p(PI / 2, 0), DOWN, buff=0.12),
                    MathTex(r"\pi", font_size=22).next_to(graph_axes.c2p(PI, 0), DOWN, buff=0.12),
                    MathTex(r"\frac{3\pi}{2}", font_size=22).next_to(graph_axes.c2p(3 * PI / 2, 0), DOWN, buff=0.12),
                    MathTex(r"2\pi", font_size=22).next_to(graph_axes.c2p(TAU, 0), DOWN, buff=0.12),
                )
                y_labels = VGroup(
                    MathTex("1", font_size=22).next_to(graph_axes.c2p(0, 1), LEFT, buff=0.12),
                    MathTex("-1", font_size=22).next_to(graph_axes.c2p(0, -1), LEFT, buff=0.12),
                )

                full_curve = graph_axes.plot(
                    lambda x: np.sin(x),
                    x_range=[0, TAU, 0.02],
                    color=C_DIM,
                    stroke_width=2,
                    stroke_opacity=0.35,
                )

                theta = ValueTracker(0.001)

                def circle_point():
                    t = theta.get_value()
                    return circle_origin + radius * np.array([np.cos(t), np.sin(t), 0])

                moving_radius = always_redraw(
                    lambda: Line(circle_origin, circle_point(), color=C_HOLD, stroke_width=5)
                )
                moving_dot = always_redraw(lambda: Dot(circle_point(), color=C_WARN, radius=0.07))
                angle_arc = always_redraw(
                    lambda: Arc(
                        radius=0.38,
                        start_angle=0,
                        angle=theta.get_value(),
                        arc_center=circle_origin,
                        color=C_HOLD,
                    )
                )
                theta_label = MathTex(r"\theta", font_size=26, color=C_HOLD).move_to(
                    circle_origin + RIGHT * 0.58 + UP * 0.22
                )

                sine_dot = always_redraw(
                    lambda: Dot(
                        graph_axes.c2p(theta.get_value(), np.sin(theta.get_value())),
                        color=C_WARN,
                        radius=0.06,
                    )
                )
                sine_trace = TracedPath(
                    sine_dot.get_center,
                    stroke_color=C_FLOW,
                    stroke_width=5,
                    dissipating_time=None,
                )
                transfer_line = always_redraw(
                    lambda: DashedLine(
                        circle_point(),
                        graph_axes.c2p(theta.get_value(), np.sin(theta.get_value())),
                        color=C_HOLD,
                        stroke_width=2,
                        dash_length=0.12,
                    )
                )
                height_line = always_redraw(
                    lambda: Line(
                        circle_origin + RIGHT * 1.75,
                        circle_origin + RIGHT * 1.75 + UP * radius * np.sin(theta.get_value()),
                        color=C_DONE,
                        stroke_width=4,
                    )
                )
                height_label = MathTex(r"\sin\theta", font_size=26, color=C_DONE).next_to(
                    circle_origin + RIGHT * 1.75 + UP * radius * 0.75,
                    RIGHT,
                    buff=0.1,
                )

                period_line = Line(
                    graph_axes.c2p(0, -1.18),
                    graph_axes.c2p(TAU, -1.18),
                    color=C_DONE,
                    stroke_width=4,
                )
                period_brace = Brace(period_line, direction=DOWN, color=C_DONE)
                period_label = MathTex(r"T = 2\pi", font_size=28, color=C_DONE).next_to(
                    period_brace,
                    DOWN,
                    buff=0.05,
                )

                graph_title = MathTex(r"y = \sin x", font_size=32, color=C_FLOW).next_to(
                    graph_axes,
                    UP,
                    buff=0.2,
                )
                conclusion = _t("单位圆上一点的纵坐标，沿角度展开就是正弦曲线", font_size=28).to_edge(DOWN)

                _beat(self, "b01", Write(title))
                _beat(self, "b02", Create(circle_axes), Create(circle), Write(circle_label))
                _beat(self, "b03", Create(graph_axes), FadeIn(x_labels), FadeIn(y_labels), Write(graph_title))
                _beat(self, "b04", Create(full_curve))
                self.add(sine_trace)
                _beat(
                    self, "b05",
                    Create(moving_radius),
                    FadeIn(moving_dot),
                    FadeIn(sine_dot),
                    Create(angle_arc),
                    Write(theta_label),
                    Create(height_line),
                    Write(height_label),
                )
                self.add(transfer_line)
                # A full turn around the circle drawing the sine wave — the
                # motion is the content, so it spans its whole sentence.
                _beat_stretch(self, "b06", theta.animate.set_value(TAU), run_time=6)
                _beat(self, "b07", Create(period_line), GrowFromCenter(period_brace), Write(period_label))
                _beat(self, "b08", Write(conclusion))
                self.wait(1)
        '''
    ).strip()


def _trig_transform_scene(plan: AnimationPlan) -> str:
    spec_dict = plan.parameters.get("trig_spec") or {
        "func": "sin", "A": 1.0, "omega": 1.0, "phi": 0.0, "k": 0.0,
    }
    func = spec_dict.get("func", "sin")
    if func not in ("sin", "cos", "tan"):
        func = "sin"
    A = float(spec_dict.get("A", 1.0)) or 1.0
    omega = float(spec_dict.get("omega", 1.0)) or 1.0
    phi = float(spec_dict.get("phi", 0.0))
    k = float(spec_dict.get("k", 0.0))
    spec = TrigSpec(func=func, A=A, omega=omega, phi=phi, k=k)

    T = period_value(spec)
    x_min, x_max = -0.3 * T, 2.3 * T
    if func == "tan":
        y_amp = max(abs(k) + 4, 4.0)
    else:
        y_amp = 1.5 * max(abs(A), 1.0)
    y_min, y_max = k - y_amp, k + y_amp

    if func == "sin":
        x_peak = (math.pi / 2 - phi) / omega
        x_period_start = -phi / omega
    elif func == "cos":
        x_peak = -phi / omega
        x_period_start = (-math.pi / 2 - phi) / omega
    else:
        x_peak = None
        x_period_start = -phi / omega

    # Shift the period span into the visible x window so the brace stays on-screen.
    while x_period_start + T > x_max:
        x_period_start -= T
    while x_period_start < x_min:
        x_period_start += T
    if x_peak is not None:
        while x_peak > x_max:
            x_peak -= T
        while x_peak < x_min:
            x_peak += T

    has_amp = func != "tan" and abs(A) > 1e-12
    period_y = y_min + 0.4

    base_np = {"sin": "np.sin(x)", "cos": "np.cos(x)", "tan": "np.tan(x)"}[func]
    target_np = (
        f"({_fmt_f(A)}) * np.{func}(({_fmt_f(omega)}) * x + ({_fmt_f(phi)})) + ({_fmt_f(k)})"
    )
    y_clamp = max(2 * y_amp, 4.0)

    # Asymptote positions for tan. Telling Manim about discontinuities lets it
    # break the curve cleanly instead of treating each one as a wild jump --
    # NaN-clamping on its own makes axes.plot produce an invisible VMobject
    # because Create() can't interpolate across the gaps.
    base_disc = _tan_asymptotes(1.0, 0.0, x_min, x_max) if func == "tan" else []
    target_disc = _tan_asymptotes(omega, phi, x_min, x_max) if func == "tan" else []
    base_disc_literal = "[" + ", ".join(_fmt_f(d) for d in base_disc) + "]"
    target_disc_literal = "[" + ", ".join(_fmt_f(d) for d in target_disc) + "]"

    # Tan has asymptotes — morphing a base curve riddled with spikes into a
    # target with different spikes produces visually chaotic intermediate
    # frames. Skip the morph and draw the target directly instead.
    # Beat keys are numbered here rather than written into the template,
    # because how many steps this scene has depends on the spec: tan skips the
    # morph, and only some specs draw an amplitude brace. Numbering them in the
    # template would misalign every later step whenever either varies.
    _step = 2  # title, then the tick labels

    if func == "tan":
        _step += 1
        play_curve = '_beat(self, "b%02d", Create(target), run_time=2.5)' % _step
    else:
        play_curve = (
            '_beat(self, "b%02d", Create(base), run_time=1.5)\n' % (_step + 1)
            + '_beat(self, "b%02d", ReplacementTransform(base, target), run_time=2)'
            % (_step + 2)
        )
        _step += 2

    play_midline = (
        '_beat(self, "b%02d", Create(midline), Write(midline_label))' % (_step + 1)
    )
    play_period = (
        '_beat(self, "b%02d", Create(period_line), GrowFromCenter(period_brace), '
        'Write(period_label))' % (_step + 2)
    )

    amp_block = "amp_line = amp_brace = amp_label = None"
    play_amp = ""
    if has_amp:
        amp_block = dedent(
            r'''
            amp_line = Line(
                axes.c2p(__AMP_X__, __AMP_BOTTOM_Y__),
                axes.c2p(__AMP_X__, __AMP_TOP_Y__),
                color=C_WARN, stroke_width=4,
            )
            amp_brace = Brace(amp_line, direction=RIGHT, color=C_WARN)
            amp_label = MathTex(r"__AMP_LATEX__", font_size=26, color=C_WARN).next_to(amp_brace, RIGHT, buff=0.05)
            '''
        ).strip()
        play_amp = (
            '_beat(self, "b%02d", Create(amp_line), GrowFromCenter(amp_brace), '
            'Write(amp_label))' % (_step + 3)
        )

    body = dedent(
        r'''
        class GeneratedScene(Scene):
            def construct(self):
                title = MathTex(r"__TITLE__", font_size=36).to_edge(UP)

                x_min, x_max = __X_MIN__, __X_MAX__
                y_min, y_max = __Y_MIN__, __Y_MAX__
                k_val = __K__
                T = __T__

                axes = Axes(
                    x_range=[x_min, x_max, T / 2],
                    y_range=[y_min, y_max, max(1, round((y_max - y_min) / 6))],
                    x_length=10, y_length=4.5,
                    tips=False,
                ).shift(DOWN * 0.3)

                # π-aware x-tick labels (textbook style, e.g. \\frac{\\pi}{3})
                # and integer y-tick labels — auto add_coordinates() would emit
                # decimal x-labels at irrational positions and they'd overlap.
                x_tick_labels = VGroup()
                for tick_x, tick_latex in __X_TICKS__:
                    if tick_latex == "0":
                        continue
                    lbl = MathTex(tick_latex, font_size=22).next_to(
                        axes.c2p(tick_x, 0), DOWN, buff=0.12,
                    )
                    x_tick_labels.add(lbl)
                y_tick_labels = VGroup()
                for tick_y in __Y_TICKS__:
                    if tick_y == 0:
                        continue
                    lbl = MathTex(str(tick_y), font_size=22).next_to(
                        axes.c2p(0, tick_y), LEFT, buff=0.12,
                    )
                    y_tick_labels.add(lbl)
                origin_label = MathTex("O", font_size=22).next_to(
                    axes.c2p(0, 0), DL, buff=0.1,
                )

                clamp = __Y_CLAMP__

                def _clip(y):
                    # Bound off-screen samples to a finite value so the path
                    # never picks up NaN (Create() can't traverse NaN gaps,
                    # which would leave the curve invisible after animation).
                    if not np.isfinite(y):
                        return float(np.sign(y or 1.0)) * clamp + k_val
                    if y - k_val > clamp:
                        return k_val + clamp
                    if k_val - y > clamp:
                        return k_val - clamp
                    return y

                def base_f(x):
                    try:
                        return _clip(__BASE_NP__)
                    except Exception:
                        return k_val

                def target_f(x):
                    try:
                        return _clip(__TARGET_NP__)
                    except Exception:
                        return k_val

                base = axes.plot(
                    base_f, x_range=[x_min, x_max, 0.02], color=C_DIM,
                    use_smoothing=False, discontinuities=__BASE_DISC__, dt=0.005,
                )
                target = axes.plot(
                    target_f, x_range=[x_min, x_max, 0.02], color=C_FLOW,
                    use_smoothing=False, discontinuities=__TARGET_DISC__, dt=0.005,
                )

                midline = DashedLine(
                    axes.c2p(x_min, k_val), axes.c2p(x_max, k_val),
                    color=C_HOLD, stroke_width=2,
                )
                midline_label = MathTex(r"__MIDLINE__", font_size=26, color=C_HOLD).next_to(midline.get_end(), RIGHT, buff=0.1)

                period_line = Line(
                    axes.c2p(__PERIOD_X__, __PERIOD_Y__),
                    axes.c2p(__PERIOD_END_X__, __PERIOD_Y__),
                    color=C_DONE, stroke_width=4,
                )
                period_brace = Brace(period_line, direction=DOWN, color=C_DONE)
                period_label = MathTex(r"__PERIOD__", font_size=26, color=C_DONE).next_to(period_brace, DOWN, buff=0.05)

                __AMP_BLOCK__

                _beat(self, "b01", Write(title), Create(axes))
                _beat(self, "b02", FadeIn(x_tick_labels), FadeIn(y_tick_labels), FadeIn(origin_label))
                __PLAY_CURVE__
                __PLAY_MIDLINE__
                __PLAY_PERIOD__
                __PLAY_AMP__
                self.wait(1)
        '''
    ).strip()

    x_ticks_literal = "[" + ", ".join(
        f"({_fmt_f(xv)}, r'{lbl}')" for xv, lbl in pi_axis_ticks(T, x_min, x_max)
    ) + "]"
    y_tick_values = list(range(int(math.ceil(y_min)), int(math.floor(y_max)) + 1))
    y_ticks_literal = "[" + ", ".join(str(y) for y in y_tick_values) + "]"

    return (
        body
        .replace("__AMP_BLOCK__", _reindent(amp_block, 8))
        .replace("__PLAY_CURVE__", _reindent(play_curve, 8))
        .replace("__PLAY_MIDLINE__", _reindent(play_midline, 8))
        .replace("__PLAY_PERIOD__", _reindent(play_period, 8))
        .replace("__PLAY_AMP__", _reindent(play_amp, 8))
        .replace("__TITLE__", trig_title_latex(spec))
        .replace("__X_MIN__", _fmt_f(x_min))
        .replace("__X_MAX__", _fmt_f(x_max))
        .replace("__Y_MIN__", _fmt_f(y_min))
        .replace("__Y_MAX__", _fmt_f(y_max))
        .replace("__K__", _fmt_f(k))
        .replace("__T__", _fmt_f(T))
        .replace("__X_TICKS__", x_ticks_literal)
        .replace("__Y_TICKS__", y_ticks_literal)
        .replace("__BASE_NP__", base_np)
        .replace("__TARGET_NP__", target_np)
        .replace("__MIDLINE__", midline_latex(spec))
        .replace("__PERIOD_X__", _fmt_f(x_period_start))
        .replace("__PERIOD_END_X__", _fmt_f(x_period_start + T))
        .replace("__PERIOD_Y__", _fmt_f(period_y))
        .replace("__PERIOD__", period_latex(spec))
        .replace("__Y_CLAMP__", _fmt_f(y_clamp))
        .replace("__BASE_DISC__", base_disc_literal)
        .replace("__TARGET_DISC__", target_disc_literal)
        .replace("__AMP_X__", _fmt_f(x_peak if x_peak is not None else 0.0))
        .replace("__AMP_BOTTOM_Y__", _fmt_f(k))
        .replace("__AMP_TOP_Y__", _fmt_f(k + abs(A)))
        .replace("__AMP_LATEX__", amplitude_latex(spec) if has_amp else "A")
    )


def _tan_asymptotes(omega: float, phi: float, x_min: float, x_max: float) -> list[float]:
    """Positions of ``tan(omega·x + phi)`` asymptotes inside ``[x_min, x_max]``.

    ``omega·x + phi = π/2 + π·n`` solves to ``x = (π/2 + π·n - phi) / omega``.
    Returned sorted; used as Manim's ``discontinuities`` so the plotter
    breaks the curve into clean sub-paths instead of skidding across the gap.
    """
    if abs(omega) < 1e-12:
        return []
    n_lo = math.floor(((x_min * omega + phi) - math.pi / 2) / math.pi) - 1
    n_hi = math.ceil(((x_max * omega + phi) - math.pi / 2) / math.pi) + 1
    out: list[float] = []
    for n in range(n_lo, n_hi + 1):
        x = (math.pi / 2 + math.pi * n - phi) / omega
        if x_min < x < x_max:
            out.append(x)
    return sorted(out)


def _fmt_f(value: float) -> str:
    """A Python float literal safe to interpolate into the generated source."""
    if value == int(value):
        return f"{int(value)}.0"
    return repr(float(value))


def _reindent(block: str, spaces: int) -> str:
    """Re-indent a multi-line replacement so every line lands at the same column."""
    prefix = " " * spaces
    return ("\n" + prefix).join(block.splitlines()) if block else ""


def _escape_text(value: str) -> str:
    """Make caller text safe to write into the generated source.

    Anything substituted into a scene lands inside a Python string literal, so
    a title containing a quote, a backslash or a newline would close that
    literal early and the scene would fail to compile. Titles come from users
    now that they are not hardcoded, and an apostrophe is not an exotic input:
    "Euler's identity" would have been a syntax error.
    """
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", " ")
        .strip()
    )


_TRIG_CONCEPT_BUILDERS = {
    ConceptTrig.GRAPH_TRANSFORM: _trig_transform_scene,
    ConceptTrig.UNIT_CIRCLE_TO_SINE: _unit_circle_to_sine_scene,
}


@scene_for(Topic.CONIC)
def _conic_scene(plan: AnimationPlan) -> str:
    builder = _CONIC_CONCEPT_BUILDERS.get(plan.concept, _ellipse_static_scene)
    return builder(plan)


def _ellipse_foci_scene(plan: AnimationPlan) -> str:
    return dedent(
        r'''
        class GeneratedScene(Scene):
            def construct(self):
                title = _t("椭圆的焦点距离和", font_size=38).to_edge(UP)

                center = DOWN * 0.1
                a = 3.0
                b = 1.75
                c = np.sqrt(a * a - b * b)
                ellipse = Ellipse(width=2 * a, height=2 * b, color=C_FLOW, stroke_width=5).move_to(center)
                major_axis = Line(center + LEFT * a, center + RIGHT * a, color=C_DONE, stroke_width=5)
                f1_pos = center + LEFT * c
                f2_pos = center + RIGHT * c
                f1 = Dot(f1_pos, color=C_HOLD, radius=0.08)
                f2 = Dot(f2_pos, color=C_HOLD, radius=0.08)
                f1_label = _t("F1", font_size=26, color=C_HOLD).next_to(f1, DOWN, buff=0.12)
                f2_label = _t("F2", font_size=26, color=C_HOLD).next_to(f2, DOWN, buff=0.12)
                axis_label = MathTex(r"2a", font_size=30, color=C_DONE).next_to(major_axis, DOWN, buff=0.18)

                t = ValueTracker(0.35)

                def point_coords():
                    angle = t.get_value()
                    return center + np.array([a * np.cos(angle), b * np.sin(angle), 0])

                moving_point = always_redraw(lambda: Dot(point_coords(), color=C_WARN, radius=0.075))
                point_label = always_redraw(
                    lambda: _t("P", font_size=26, color=C_WARN).next_to(moving_point, UR, buff=0.08)
                )
                pf1 = always_redraw(lambda: Line(point_coords(), f1_pos, color=C_HOLD, stroke_width=5))
                pf2 = always_redraw(lambda: Line(point_coords(), f2_pos, color=C_WARM, stroke_width=5))
                # A legend under the title, not parked in the frame corner. The
                # corner is where the conclusion lives once the frame is narrow,
                # so `to_corner(DL)` collided with it in a 9:16 cut and merely
                # looked stranded in a 16:9 one.
                pf1_label = MathTex(r"PF_1", font_size=30, color=C_HOLD)
                pf2_label = MathTex(r"PF_2", font_size=30, color=C_WARM)
                legend = VGroup(pf1_label, pf2_label).arrange(RIGHT, buff=0.45)
                legend.next_to(title, DOWN, buff=0.25)
                invariant = MathTex(r"PF_1 + PF_2 = 2a", font_size=38).to_edge(DOWN)
                conclusion = _t(
                    "椭圆：到两个焦点的距离和为常数的点的轨迹",
                    font_size=28,
                ).next_to(invariant, UP, buff=0.18)

                sample_points = VGroup(*[
                    Dot(center + np.array([a * np.cos(angle), b * np.sin(angle), 0]), color=C_FLOW, radius=0.035)
                    for angle in (0, PI / 3, 2 * PI / 3, PI, 4 * PI / 3, 5 * PI / 3)
                ])

                _beat(self, "b01", Write(title))
                _beat(self, "b02", Create(ellipse), Create(major_axis), Write(axis_label))
                _beat(self, "b03", FadeIn(f1, f2), Write(f1_label), Write(f2_label))
                _beat(self, "b04", FadeIn(sample_points))
                _beat(self, "b05", FadeIn(moving_point), Write(point_label))
                _beat(self, "b06", Create(pf1), Create(pf2), Write(legend))
                # The sweep is the argument, not decoration around it: P has to
                # travel for as long as the narrator is saying the sum holds, so
                # this one stretches rather than finishing early and freezing.
                # `rate_func` rides on the animation so a constant-speed trace
                # survives the unmeasured path too, where `play` is called
                # without one.
                _beat_stretch(
                    self, "b07",
                    t.animate(rate_func=linear).set_value(2 * PI + 0.35),
                    run_time=5.5,
                )
                _beat(self, "b08", Write(invariant), Write(conclusion), FadeOut(legend))
                self.wait(1)
        '''
    ).strip()


def _ellipse_static_scene(plan: AnimationPlan) -> str:
    return dedent(
        '''
        class GeneratedScene(Scene):
            def construct(self):
                title = _t("椭圆的焦点与长轴", font_size=38).to_edge(UP)
                ellipse = Ellipse(width=6, height=3, color=C_FLOW)
                major_axis = Line(LEFT * 3, RIGHT * 3, color=C_DONE, stroke_width=6)
                f1 = Dot(LEFT * 1.8, color=C_HOLD)
                f2 = Dot(RIGHT * 1.8, color=C_HOLD)
                labels = VGroup(
                    _t("F1", font_size=26).next_to(f1, DOWN),
                    _t("F2", font_size=26).next_to(f2, DOWN),
                    _t("长轴", font_size=28, color=C_DONE).next_to(major_axis, DOWN),
                )
                p = Dot(ellipse.point_at_angle(PI / 3), color=C_WARN)
                segments = VGroup(Line(p.get_center(), f1.get_center()), Line(p.get_center(), f2.get_center()))
                relation = _t("椭圆上任意点到两个焦点的距离和不变", font_size=30).to_edge(DOWN)

                self.play(Write(title))
                self.play(Create(ellipse), Create(major_axis))
                self.play(FadeIn(f1, f2), Write(labels))
                self.play(FadeIn(p), Create(segments))
                self.play(Write(relation))
                self.wait(1)
        '''
    ).strip()


def _parabola_focus_directrix_scene(plan: AnimationPlan) -> str:
    return dedent(
        r'''
        class GeneratedScene(Scene):
            def construct(self):
                title = _t("抛物线的焦点与准线", font_size=38).to_edge(UP)
                axes = Axes(
                    x_range=[-1.4, 5.4, 1],
                    y_range=[-3.2, 3.2, 1],
                    x_length=8.2,
                    y_length=5.2,
                    tips=False,
                ).shift(RIGHT * 0.45 + DOWN * 0.15)

                p_val = 1.0
                focus = axes.c2p(p_val, 0)
                directrix_x = -p_val
                parabola = axes.plot_parametric_curve(
                    lambda t: [(t * t) / (4 * p_val), t, 0],
                    t_range=[-2.9, 2.9, 0.02],
                    color=C_FLOW,
                    stroke_width=5,
                )
                directrix = DashedLine(
                    axes.c2p(directrix_x, -3.0),
                    axes.c2p(directrix_x, 3.0),
                    color=C_DONE,
                    stroke_width=4,
                    dash_length=0.16,
                )
                focus_dot = Dot(focus, color=C_HOLD, radius=0.08)
                focus_label = _t("焦点 F", font_size=26, color=C_HOLD).next_to(focus_dot, UR, buff=0.12)
                directrix_label = _t("准线", font_size=26, color=C_DONE).next_to(directrix, LEFT, buff=0.16)

                y_tracker = ValueTracker(-2.35)

                def point_coords():
                    y = y_tracker.get_value()
                    x = (y * y) / (4 * p_val)
                    return axes.c2p(x, y)

                def foot_coords():
                    y = y_tracker.get_value()
                    return axes.c2p(directrix_x, y)

                moving_point = always_redraw(lambda: Dot(point_coords(), color=C_WARN, radius=0.075))
                point_label = always_redraw(
                    lambda: _t("P", font_size=26, color=C_WARN).next_to(moving_point, RIGHT, buff=0.1)
                )
                focus_segment = always_redraw(
                    lambda: Line(point_coords(), focus, color=C_HOLD, stroke_width=5)
                )
                directrix_segment = always_redraw(
                    lambda: Line(point_coords(), foot_coords(), color=C_DONE, stroke_width=5)
                )
                foot_dot = always_redraw(lambda: Dot(foot_coords(), color=C_DONE, radius=0.055))
                right_angle = always_redraw(
                    lambda: RightAngle(
                        Line(foot_coords(), foot_coords() + UP * 0.5),
                        Line(foot_coords(), point_coords()),
                        length=0.18,
                        color=C_DONE,
                        quadrant=(-1, 1),
                    )
                )

                equality = _t("PF = d(P, 准线)", font_size=34).to_edge(DOWN)
                conclusion = _t("抛物线：到焦点和到准线距离相等的点的轨迹", font_size=28).next_to(
                    equality,
                    UP,
                    buff=0.18,
                )
                # Stacked above the conclusion rather than lifted a fixed amount
                # off the corner. The legend used to sit at a hand-tuned height
                # that cleared the Chinese caption and not the English one, which
                # is three times longer and reaches back into the corner: one
                # collision, in one language, from a number that only ever
                # described the language it was tuned in.
                focus_distance_label = MathTex(r"PF", font_size=30, color=C_HOLD)
                focus_distance_label.next_to(conclusion, UP, buff=0.3).to_edge(LEFT)
                directrix_distance_label = _t(
                    "d(P, 准线)",
                    font_size=30,
                    color=C_DONE,
                ).next_to(focus_distance_label, RIGHT, buff=0.5)

                self.play(Write(title), Create(axes))
                self.play(Create(parabola), Create(directrix))
                self.play(FadeIn(focus_dot), Write(focus_label), Write(directrix_label))
                self.play(FadeIn(moving_point), Write(point_label))
                self.play(
                    Create(focus_segment),
                    Create(directrix_segment),
                    FadeIn(foot_dot),
                    Create(right_angle),
                )
                self.play(Write(focus_distance_label), Write(directrix_distance_label))
                self.play(y_tracker.animate.set_value(2.35), run_time=4.5, rate_func=smooth)
                self.play(Write(equality), Write(conclusion))
                self.wait(1)
        '''
    ).strip()


def _cone_slice_scene(plan: AnimationPlan) -> str:
    """The sweep circle → ellipse → parabola → hyperbola, plus the degenerates.

    **Beat map — what each beat shows.** Narration is written per beat and
    synthesized separately, so beat *n* is spoken over exactly this:

    ====  ===================================  ==========================
    beat  animation                            caption
    ====  ===================================  ==========================
    b01   cone, axis, apex, generator, alpha   (none yet)
    b02   plane enters level, theta = 90       perpendicular to axis
    b03   tilt to m = 0.55                     slightly tilted: ellipse
    b04   tilt until theta = alpha             parallel to a slant line
    b05   tilt to m = 2.3                      steeper: both nappes
    b06   plane descends onto the apex         through the apex: a point
    b07   tilt at the apex                     one line, then two crossed
    b08   hold                                 one cone, four curves
    ====  ===================================  ==========================

    That table is the contract a narration has to be written against.
    Written blind, a planner produces a textbook-correct explanation in its
    own order and then says "hyperbola" over b06, which is the apex
    collapsing to a point. That shipped once.

    The whole scene rests on one substitution. Putting the cutting plane
    ``z = h + m·x`` into the double cone ``x² + y² = (z·T)²`` leaves

        y² = (T²m² − 1)·x² + 2T²mh·x + T²h²

    so the sign of the leading coefficient *is* the classification, and the
    degenerate cases are not special-cased — they are what the same expression
    gives when ``h = 0``. That is also the lesson of the video, so the code and
    the explanation are the same object.
    """
    # Clamped, not refused — a video beats a traceback. The matching
    # precondition reports the substitution so it is never silent.
    tan_half = plan.parameters.get("half_angle_tan", CONE_HALF_ANGLE_TAN)
    try:
        tan_half = float(tan_half)
    except (TypeError, ValueError):
        tan_half = CONE_HALF_ANGLE_TAN
    if not CONE_TAN_MIN < tan_half < CONE_TAN_MAX:
        tan_half = CONE_HALF_ANGLE_TAN

    return dedent(
        r'''
        CONE_T = __TAN__
        CONE_Z = 2.0
        CONE_R = CONE_Z * CONE_T
        # The plane is parallel to a slant line at exactly this tilt, which is
        # the parabola. Derived rather than written down: a hardcoded slope
        # stops being the parabola the moment the cone's angle is changed.
        PARABOLA_SLOPE = 1.0 / CONE_T


        def _section_branches(h, m, samples=360):
            """Points where the plane z = h + m*x meets the double cone.

            One quadratic decides everything: y² = a·x² + b·x + c. a < 0 closes
            the curve (ellipse), a == 0 opens it once (parabola), a > 0 splits
            it in two (hyperbola, one branch per nappe). With h = 0 the same
            expression collapses to the degenerate cases — a point, one line,
            then two crossed lines — with no separate code path.
            """
            t2 = CONE_T * CONE_T
            a = t2 * m * m - 1.0
            b = 2.0 * t2 * m * h
            c = t2 * h * h
            runs, current = [], []
            for x in np.linspace(-CONE_R, CONE_R, samples):
                z = h + m * x
                r = a * x * x + b * x + c
                # The tolerance matters at the parabola, where a is zero only up
                # to floating point: an exact test drops the entire section for
                # one frame and the curve blinks out at the moment it is named.
                if r >= -1e-9 and abs(z) <= CONE_Z:
                    current.append((x, np.sqrt(max(r, 0.0)), z))
                elif current:
                    runs.append(current)
                    current = []
            if current:
                runs.append(current)

            branches = []
            for run in runs:
                if len(run) < 2:
                    continue
                # The +y and -y halves are drawn as separate strokes. Joining
                # them into one path looks identical wherever the section closes
                # itself (both halves meet at y = 0), but where the run instead
                # ends against the cone's rim the join draws a chord straight
                # across the opening — which renders a parabola as a closed loop.
                branches.append([np.array([x, y, z]) for x, y, z in run])
                branches.append([np.array([x, -y, z]) for x, y, z in run])
            return branches


        def _section_mobject(h, m):
            group = VGroup()
            for pts in _section_branches(h, m):
                curve = VMobject(color=C_HOLD, stroke_width=6)
                curve.set_points_as_corners(pts)
                group.add(curve)
            return group


        class GeneratedScene(ThreeDScene):
            def construct(self):
                # Authored in English, and taken from the plan. Both are
                # departures from the rest of this module, which hardcodes a
                # Chinese title and translates it at render time -- which is why
                # a caller who set `title` got "Where the Conics Come From"
                # instead, the English of a string they never wrote.
                # Vertical text is inset well clear of the frame edge. TikTok
                # and Reels draw their own UI over the top and bottom of the
                # picture -- caption, handle, buttons -- and `to_edge` puts a
                # label exactly where that furniture lands. The insets match the
                # ones the drama lane already ships (overlay at y=210 of 1920,
                # subtitle at y=H-300), converted into frame units.
                _VERTICAL_TOP_INSET, _VERTICAL_BOTTOM_INSET = 1.75, 2.55
                title = _t("__TITLE__", font_size=38).to_edge(UP)
                if config.frame_height > config.frame_width:
                    title.shift(DOWN * _VERTICAL_TOP_INSET)
                self.add_fixed_in_frame_mobjects(title)

                # Every caption is built and pinned to the frame up front, then
                # cross-faded. `Transform` between two Text mobjects maps glyph
                # to glyph, so captions of different lengths lose characters and
                # the surplus drifts off — and in a ThreeDScene the morph target
                # is not pinned, so the debris ends up floating in world space.
                #
                # Written short on purpose. `_t` shrinks a label that would
                # overrun the frame, and these were Chinese: a 20-character
                # caption becomes about 66 in English, so translated text was
                # arriving pre-shrunk into a layout tuned for a denser script.
                # Authoring them at English length is what makes the shrink the
                # fallback it was meant to be rather than the normal case.
                captions = VGroup(*[
                    _t(line, font_size=28).to_edge(DOWN) for line in (
                        "Perpendicular to the axis: a circle",
                        "Tilted slightly: an ellipse",
                        "Parallel to a slant line: a parabola",
                        "Steeper — cutting both cones: a hyperbola",
                        "Through the apex: the section shrinks to a point",
                        "Tilt further: one line, then two crossed lines",
                        "One cone, four curves — the angle decides",
                    )
                ])
                if config.frame_height > config.frame_width:
                    captions.shift(UP * _VERTICAL_BOTTOM_INSET)
                for line in captions:
                    self.add_fixed_in_frame_mobjects(line)
                    line.set_opacity(0.0)

                def swap(index):
                    """Cut to this caption. Instant, and outside the beat.

                    Not a cross-fade: `_beat_stretch` spreads every animation it
                    is handed across the whole beat, so a fade handed to it is
                    still half-finished seconds later — two captions sit on top
                    of each other for most of the sweep. A hard cut on the beat
                    boundary is also what the narration is doing.
                    """
                    captions[index - 1].set_opacity(0.0)
                    captions[index].set_opacity(1.0)

                cone = Surface(
                    lambda u, v: np.array(
                        [u * CONE_T * np.cos(v), u * CONE_T * np.sin(v), u]),
                    u_range=[-CONE_Z, CONE_Z],
                    v_range=[0, TAU],
                    resolution=(12, 48),
                ).set_opacity(0.30).set_color(C_FLOW)
                axis = DashedLine(
                    np.array([0.0, 0.0, -CONE_Z - 0.35]),
                    np.array([0.0, 0.0, CONE_Z + 0.35]),
                    color=C_MUTED,
                    stroke_width=2,
                )
                apex = Dot3D(ORIGIN, color=C_FG, radius=0.07)

                height = ValueTracker(1.0)
                slope = ValueTracker(0.0)

                def plane_sheet():
                    m = slope.get_value()
                    # Shrink the x-extent as the tilt grows so the sheet's size
                    # in space stays put. Left fixed, a slope of 2.3 stretches
                    # the plane to four times the cone's height and the picture
                    # becomes a green rectangle with a cone somewhere behind it.
                    half = 1.9 / np.sqrt(1.0 + m * m)
                    return Surface(
                        lambda u, v: np.array([u, v, height.get_value() + m * u]),
                        u_range=[-half, half],
                        v_range=[-1.9, 1.9],
                        resolution=(2, 2),
                    ).set_opacity(0.32).set_color(C_DONE)

                plane = always_redraw(plane_sheet)
                section = always_redraw(
                    lambda: _section_mobject(height.get_value(), slope.get_value()))

                # --- the angle criterion, drawn rather than only narrated ----
                # The classification is theta against alpha, and this scene used
                # to show neither: narration compared two angles over a picture
                # with no angle in it, no slant line and no label. Everything
                # below lives in the y = 0 plane, where the axis is z and the
                # generator is x = T*z, so both angles are honest sections of the
                # same solid rather than an inset diagram beside it.
                #
                # theta is drawn on a line through the apex *parallel to* the
                # cutting plane, not on the plane itself: the plane sits at
                # height h and its angle is a property of its direction, so
                # measuring it at the apex is what puts both angles at the same
                # vertex and makes them comparable. It also buys the payoff --
                # at the parabola that line lies exactly along the generator,
                # and theta = alpha stops being a claim and becomes something
                # you watch happen.
                ALPHA = float(np.arctan(CONE_T))
                # Widely separated radii, because the two arcs must read as
                # two things *converging* at the parabola. At 0.78 and 1.12
                # they sat almost on top of each other, so theta meeting
                # alpha -- the whole point of the video -- looked like
                # clutter rather than a coincidence.
                A_R, T_R = 0.58, 1.34

                def _axis_arc(to_axis_angle, radius, color):
                    """Arc from the +z axis toward +x, swept in the y = 0 plane."""
                    return ParametricFunction(
                        lambda t: np.array(
                            [radius * np.sin(t), 0.0, radius * np.cos(t)]),
                        t_range=[0.0, max(float(to_axis_angle), 1e-3), 0.02],
                        color=color, stroke_width=5,
                    )

                def _label_at(angle, radius, out=0.30):
                    """Sit the label on the arc's bisector, just outside it."""
                    half = float(angle) * 0.5
                    return np.array([(radius + out) * np.sin(half), 0.0,
                                     (radius + out) * np.cos(half)])

                # arctan2, not arctan(1/m): at m = 0 the plane is level and the
                # angle is exactly 90 degrees, which 1/m cannot express.
                def _theta():
                    return float(np.arctan2(1.0, slope.get_value()))

                generator = Line(ORIGIN, np.array([CONE_R, 0.0, CONE_Z]),
                                 color=C_HOLD, stroke_width=5)
                alpha_arc = _axis_arc(ALPHA, A_R, C_HOLD)
                tilt_line = always_redraw(lambda: DashedLine(
                    -1.6 * np.array([np.sin(_theta()), 0.0, np.cos(_theta())]),
                    1.6 * np.array([np.sin(_theta()), 0.0, np.cos(_theta())]),
                    color=C_AUX, stroke_width=4, dash_length=0.11))
                theta_arc = always_redraw(lambda: _axis_arc(_theta(), T_R, C_AUX))

                # Built once and moved by an updater, never rebuilt. A label
                # returned fresh from `always_redraw` is a different mobject
                # every frame, so the one registered for fixed orientation is
                # discarded immediately and the replacements render edge-on in
                # the y = 0 plane -- which is what turned theta into a squiggle.
                alpha_label = MathTex(r"\alpha", font_size=44, color=C_HOLD)
                alpha_label.move_to(_label_at(ALPHA, A_R))
                theta_label = MathTex(r"\theta", font_size=44, color=C_AUX)
                theta_label.move_to(_label_at(_theta(), T_R))
                theta_label.add_updater(
                    lambda mob: mob.move_to(_label_at(_theta(), T_R)))
                # `add_fixed_orientation_mobjects` calls `self.add` internally,
                # so registering puts both labels on screen *immediately* --
                # before the title finishes writing, floating in empty space
                # next to a half-drawn cone, with theta naming a plane that does
                # not exist yet. `FadeIn` later is then a no-op on something
                # already added and already opaque. Register for billboarding,
                # hide, and let each beat fade its own label up.
                for label in (alpha_label, theta_label):
                    self.add_fixed_orientation_mobjects(label)
                    label.set_opacity(0.0)

                # A vertical cut is not the landscape one in a taller box. The
                # frame goes from 8 units tall to 16, so the same solid occupies
                # half the height and the cone ends up floating in the middle of
                # a mostly empty screen -- on a phone, most of the picture is
                # black. Zoom restores the apparent size; 1.55 is what fits the
                # widest moment (the plane at its shallowest spans about 3.8
                # units) inside the 9-unit width with margin to spare.
                _VERTICAL = config.frame_height > config.frame_width
                self.set_camera_orientation(
                    phi=68 * DEGREES, theta=-52 * DEGREES,
                    zoom=1.55 if _VERTICAL else 1.0,
                )
                _beat(self, "b01", Write(title), Create(cone), Create(axis), FadeIn(apex),
                      Create(generator), Create(alpha_arc),
                      alpha_label.animate.set_opacity(1.0))
                captions[0].set_opacity(1.0)
                _beat(self, "b02", FadeIn(plane), Create(section),
                      Create(tilt_line), Create(theta_arc),
                      theta_label.animate.set_opacity(1.0))
                swap(1)
                _beat_stretch(
                    self, "b03",
                    slope.animate(rate_func=linear).set_value(0.55),
                )
                swap(2)
                _beat_stretch(
                    self, "b04",
                    slope.animate(rate_func=linear).set_value(PARABOLA_SLOPE),
                )
                swap(3)
                _beat_stretch(
                    self, "b05",
                    slope.animate(rate_func=linear).set_value(2.3),
                )
                swap(4)
                _beat_stretch(
                    self, "b06",
                    slope.animate(rate_func=linear).set_value(0.55),
                    height.animate(rate_func=linear).set_value(0.0),
                )
                swap(5)
                _beat_stretch(
                    self, "b07",
                    slope.animate(rate_func=linear).set_value(2.3),
                )
                swap(6)
                _beat(self, "b08")
                self.wait(1)
        '''
    ).strip().replace("__TAN__", repr(tan_half)).replace(
        # The plan's own title, when it set one. Escaped rather than
        # interpolated raw: a title carrying a quote or a backslash would
        # otherwise end the string literal it is being written into, and the
        # scene would fail to compile on a caller's punctuation.
        "__TITLE__", _escape_text(plan.title_zh or "Where the Conics Come From"))


_CONIC_CONCEPT_BUILDERS = {
    ConceptConic.ELLIPSE_FOCI: _ellipse_foci_scene,
    ConceptConic.PARABOLA_FOCUS_DIRECTRIX: _parabola_focus_directrix_scene,
    ConceptConic.CONE_SLICE: _cone_slice_scene,
}


@scene_for(Topic.THREE_D)
def _three_d_scene(plan: AnimationPlan) -> str:
    builder = _THREE_D_CONCEPT_BUILDERS.get(plan.concept, _sphere_section_scene)
    return builder(plan)


def _sphere_section_scene(plan: AnimationPlan) -> str:
    return dedent(
        '''
        class GeneratedScene(ThreeDScene):
            def construct(self):
                title = _t("三维几何中的截面", font_size=38).to_edge(UP)
                self.add_fixed_in_frame_mobjects(title)
                axes = ThreeDAxes(x_length=5, y_length=5, z_length=4)
                sphere = Sphere(radius=1.5, resolution=(24, 48)).set_opacity(0.35).set_color(C_FLOW)
                plane = Surface(
                    lambda u, v: axes.c2p(u, v, 0.55),
                    u_range=[-1.8, 1.8],
                    v_range=[-1.8, 1.8],
                    resolution=(2, 2),
                ).set_opacity(0.45).set_color(C_DONE)
                label = _t("平面截球得到圆形截面", font_size=28).to_edge(DOWN)
                self.add_fixed_in_frame_mobjects(label)

                self.set_camera_orientation(phi=65 * DEGREES, theta=-45 * DEGREES)
                self.play(Write(title), Create(axes))
                self.play(FadeIn(sphere), FadeIn(plane))
                self.play(Write(label))
                self.begin_ambient_camera_rotation(rate=0.25)
                self.wait(4)
                self.stop_ambient_camera_rotation()
        '''
    ).strip()


def _solid_overview_scene(plan: AnimationPlan) -> str:
    spec_dict = plan.parameters.get("solid_spec") or {"kind": "cube", "params": {"side": 2.0}, "name": "ABCD-A1B1C1D1"}
    spec = SolidSpec(kind=spec_dict["kind"], params=spec_dict["params"], name=spec_dict["name"])
    title_zh = solid_title_zh(spec)
    name_latex = vertex_name_latex(spec.name, spec.kind)
    formula_latex = solid_volume_latex(spec)
    solid_call = solid_construction_code(spec)
    body = dedent(
        r'''
        class GeneratedScene(ThreeDScene):
            def construct(self):
                title = VGroup(
                    _t("__TITLE_ZH__", font_size=36),
                    MathTex(r"__NAME_LATEX__", font_size=36),
                ).arrange(RIGHT, buff=0.2).to_edge(UP)
                self.add_fixed_in_frame_mobjects(title)

                formula = MathTex(r"__FORMULA__", font_size=36).to_edge(DOWN)
                self.add_fixed_in_frame_mobjects(formula)

                axes = ThreeDAxes(x_length=5, y_length=5, z_length=4)
                solid, verts = __SOLID_CALL__
                labels = label_vertices(verts)
                for label in labels:
                    self.add_fixed_orientation_mobjects(label)

                self.set_camera_orientation(phi=70 * DEGREES, theta=-50 * DEGREES)
                self.play(Write(title), Create(axes))
                self.play(Create(solid))
                self.play(FadeIn(labels))
                self.play(Write(formula))
                self.begin_ambient_camera_rotation(rate=0.2)
                self.wait(4)
                self.stop_ambient_camera_rotation()
        '''
    ).strip()
    return (
        body
        .replace("__TITLE_ZH__", title_zh)
        .replace("__NAME_LATEX__", name_latex)
        .replace("__FORMULA__", formula_latex)
        .replace("__SOLID_CALL__", solid_call)
    )


def _cube_section_scene(plan: AnimationPlan) -> str:
    spec_dict = plan.parameters.get("solid_spec") or {
        "kind": "cube",
        "params": {"side": 2.0},
        "name": "ABCD-A1B1C1D1",
    }
    spec = SolidSpec(kind=spec_dict["kind"], params=spec_dict["params"], name=spec_dict["name"])
    points = plan.parameters.get("section_points") or ["D", "A1", "C1"]
    name_latex = vertex_name_latex(spec.name, spec.kind)
    points_latex = section_points_latex(points)
    solid_call = solid_construction_code(spec)
    section_call = cube_section_code(points)
    body = dedent(
        r'''
        class GeneratedScene(ThreeDScene):
            def construct(self):
                title = VGroup(
                    _t("正方体", font_size=34),
                    MathTex(r"__NAME_LATEX__", font_size=34),
                    _t("的截面", font_size=34),
                ).arrange(RIGHT, buff=0.2).to_edge(UP)
                self.add_fixed_in_frame_mobjects(title)

                caption = VGroup(
                    _t("过", font_size=28),
                    MathTex(r"__POINTS_LATEX__", font_size=28),
                    _t("的截面", font_size=28),
                ).arrange(RIGHT, buff=0.15).to_edge(DOWN)
                self.add_fixed_in_frame_mobjects(caption)

                axes = ThreeDAxes(x_length=5, y_length=5, z_length=4)
                solid, verts = __SOLID_CALL__
                labels = label_vertices(verts)
                for label in labels:
                    self.add_fixed_orientation_mobjects(label)

                section = __SECTION_CALL__
                highlight_names = __POINT_NAMES__
                highlights = VGroup(*[
                    Dot3D(point=verts[n], color=C_WARN, radius=0.07)
                    for n in highlight_names if n in verts
                ])

                self.set_camera_orientation(phi=70 * DEGREES, theta=-50 * DEGREES)
                self.play(Write(title), Create(axes))
                self.play(Create(solid))
                self.play(FadeIn(labels))
                self.play(FadeIn(highlights))
                if section is not None:
                    self.play(Create(section))
                self.play(Write(caption))
                self.begin_ambient_camera_rotation(rate=0.2)
                self.wait(4)
                self.stop_ambient_camera_rotation()
        '''
    ).strip()
    point_names_literal = "[" + ", ".join(f'"{n}"' for n in _validated_points(points)) + "]"
    return (
        body
        .replace("__NAME_LATEX__", name_latex)
        .replace("__POINTS_LATEX__", points_latex)
        .replace("__SOLID_CALL__", solid_call)
        .replace("__SECTION_CALL__", section_call)
        .replace("__POINT_NAMES__", point_names_literal)
    )


def _validated_points(points):
    import re as _re

    safe = [n for n in points if isinstance(n, str) and _re.fullmatch(r"[A-Z]\d?", n)]
    return safe if len(safe) >= 3 else ["D", "A1", "C1"]


def _three_views_scene(plan: AnimationPlan) -> str:
    spec_dict = plan.parameters.get("solid_spec") or {
        "kind": "cube",
        "params": {"side": 2.0},
        "name": "ABCD-A1B1C1D1",
    }
    spec = SolidSpec(kind=spec_dict["kind"], params=spec_dict["params"], name=spec_dict["name"])
    title_zh = solid_title_zh(spec)
    name_latex = vertex_name_latex(spec.name, spec.kind)
    views_call = three_views_code(spec)
    body = dedent(
        r'''
        class GeneratedScene(Scene):
            def construct(self):
                title = VGroup(
                    _t("__TITLE_ZH__", font_size=34),
                    MathTex(r"__NAME_LATEX__", font_size=34),
                    _t("的三视图", font_size=34),
                ).arrange(RIGHT, buff=0.2).to_edge(UP)

                front, side, top = __VIEWS_CALL__

                # Scale each view uniformly so the widest fits the screen
                # while still showing proportions between views faithfully.
                max_extent = max(
                    front.width, front.height,
                    side.width, side.height,
                    top.width, top.height,
                )
                view_scale = min(1.0, 2.4 / max_extent) if max_extent > 0 else 1.0
                for v in (front, side, top):
                    v.scale(view_scale)

                # Textbook layout: 正视图 upper-left, 侧视图 upper-right,
                # 俯视图 lower-left. align so corresponding edges share a line.
                front.move_to(LEFT * 3.0 + UP * 1.4)
                side.next_to(front, RIGHT, buff=1.6, aligned_edge=UP)
                top.next_to(front, DOWN, buff=1.6, aligned_edge=LEFT)

                front_label = _t("正视图", font_size=26).next_to(front, DOWN, buff=0.18)
                side_label  = _t("侧视图", font_size=26).next_to(side,  DOWN, buff=0.18)
                top_label   = _t("俯视图", font_size=26).next_to(top,   DOWN, buff=0.18)

                # 长对正 — vertical dashed line from front's right edge down
                # through top's right edge (both share the same x-extent).
                guide_x = front.get_right()[0] + 0.05
                length_guide = DashedLine(
                    np.array([guide_x, front.get_top()[1], 0.0]),
                    np.array([guide_x, top.get_bottom()[1], 0.0]),
                    color=C_DIM, stroke_width=2, dash_length=0.12,
                )
                length_label = _t("长对正", font_size=22, color=C_DIM).next_to(
                    length_guide, RIGHT, buff=0.08,
                )

                # 高平齐 — horizontal dashed line linking front and side tops.
                guide_y = front.get_top()[1] + 0.18
                height_guide = DashedLine(
                    np.array([front.get_left()[0], guide_y, 0.0]),
                    np.array([side.get_right()[0], guide_y, 0.0]),
                    color=C_DIM, stroke_width=2, dash_length=0.12,
                )
                height_label = _t("高平齐", font_size=22, color=C_DIM).next_to(
                    height_guide, UP, buff=0.05,
                )

                self.play(Write(title))
                self.play(Create(front), Write(front_label))
                self.play(Create(side),  Write(side_label))
                self.play(Create(top),   Write(top_label))
                self.play(Create(length_guide), Write(length_label))
                self.play(Create(height_guide), Write(height_label))
                self.wait(1.5)
        '''
    ).strip()
    return (
        body
        .replace("__TITLE_ZH__", title_zh)
        .replace("__NAME_LATEX__", name_latex)
        .replace("__VIEWS_CALL__", views_call)
    )


_THREE_D_CONCEPT_BUILDERS = {
    Concept3D.SOLID_OVERVIEW: _solid_overview_scene,
    Concept3D.SPHERE_SECTION: _sphere_section_scene,
    Concept3D.CUBE_SECTION: _cube_section_scene,
    Concept3D.THREE_VIEWS: _three_views_scene,
}


@scene_for(Topic.CALCULUS)
def _calculus_scene(plan: AnimationPlan) -> str:
    builder = _CALCULUS_CONCEPT_BUILDERS.get(plan.concept, _derivative_tangent_scene)
    return builder(plan)


def _calculus_expr(plan: AnimationPlan, fallback: str) -> tuple[str, str, str]:
    raw = plan.parameters.get("expression") or fallback
    if not validate_expression(raw):
        raw = fallback
    return raw, to_numpy_expr(raw), to_latex_expr(raw)


_TAYLOR_VARIANTS = {
    "sin": {
        "title": "sin(x) 的泰勒展开",
        "target_fn": "np.sin(x)",
        "target_label": r"y=\sin x",
        "final": r"\sin x=x-\frac{x^3}{3!}+\frac{x^5}{5!}-\frac{x^7}{7!}+\cdots",
        "terms": [
            ("x", r"P_1(x)=x", "只保留一阶项：在 0 附近像一条切线"),
            ("x - x**3 / 6", r"P_3(x)=x-\frac{x^3}{3!}", "加入三次项：弯曲方向开始匹配"),
            ("x - x**3 / 6 + x**5 / 120", r"P_5(x)=x-\frac{x^3}{3!}+\frac{x^5}{5!}", "加入五次项：贴合范围继续扩大"),
            (
                "x - x**3 / 6 + x**5 / 120 - x**7 / 5040",
                r"P_7(x)=x-\frac{x^3}{3!}+\frac{x^5}{5!}-\frac{x^7}{7!}",
                "加入七次项：多项式逐步逼近 sin(x)",
            ),
        ],
    },
    "cos": {
        "title": "cos(x) 的泰勒展开",
        "target_fn": "np.cos(x)",
        "target_label": r"y=\cos x",
        "final": r"\cos x=1-\frac{x^2}{2!}+\frac{x^4}{4!}-\frac{x^6}{6!}+\cdots",
        "terms": [
            ("1", r"P_0(x)=1", "只保留常数项：在 0 附近是一条水平线"),
            ("1 - x**2 / 2", r"P_2(x)=1-\frac{x^2}{2!}", "加入二次项：开口方向开始匹配"),
            ("1 - x**2 / 2 + x**4 / 24", r"P_4(x)=1-\frac{x^2}{2!}+\frac{x^4}{4!}", "加入四次项：贴合范围继续扩大"),
            (
                "1 - x**2 / 2 + x**4 / 24 - x**6 / 720",
                r"P_6(x)=1-\frac{x^2}{2!}+\frac{x^4}{4!}-\frac{x^6}{6!}",
                "加入六次项：多项式逐步逼近 cos(x)",
            ),
        ],
    },
}


def _taylor_terms_source(terms: list[tuple[str, str, str]]) -> str:
    """Render the ``approximations`` list literal with a stable 16-space indent."""
    lines = ["approximations = ["]
    for expr, latex, note in terms:
        lines.append("                    (")
        lines.append(f"                        lambda x: {expr},")
        lines.append(f'                        r"{latex}",')
        lines.append(f'                        "{note}",')
        lines.append("                    ),")
    lines.append("                ]")
    return "\n".join(lines)


def _taylor_series_scene(plan: AnimationPlan) -> str:
    function = plan.parameters.get("function") or "sin"
    variant = _TAYLOR_VARIANTS.get(function, _TAYLOR_VARIANTS["sin"])
    body = dedent(
        r'''
        class GeneratedScene(Scene):
            def construct(self):
                title = _t("__TITLE__", font_size=38).to_edge(UP)
                # Sized to the shared caption budget; see PLOT_Y_LENGTH. The
                # approximations are clamped just inside y_range, so a plot
                # reaching into the caption band takes the clamped tails with it
                # and draws a flat line straight through the conclusion.
                axes = Axes(
                    x_range=[-2 * PI, 2 * PI, PI / 2],
                    y_range=[-2.2, 2.2, 1],
                    x_length=10.5,
                    y_length=PLOT_Y_LENGTH,
                    tips=False,
                ).shift(PLOT_SHIFT)

                x_labels = VGroup(
                    MathTex(r"-2\pi", font_size=22).next_to(axes.c2p(-2 * PI, 0), DOWN, buff=0.1),
                    MathTex(r"-\pi", font_size=22).next_to(axes.c2p(-PI, 0), DOWN, buff=0.1),
                    MathTex(r"\pi", font_size=22).next_to(axes.c2p(PI, 0), DOWN, buff=0.1),
                    MathTex(r"2\pi", font_size=22).next_to(axes.c2p(2 * PI, 0), DOWN, buff=0.1),
                )
                target = axes.plot(lambda x: __TARGET_FN__, x_range=[-2 * PI, 2 * PI, 0.02], color=C_FLOW, stroke_width=6)
                # Hung below the title rather than above the axes. Anchored to
                # the plot it rose with it when the axes moved onto the shared
                # caption budget, and ran into the English title — which is wide
                # enough to reach x=2.6 where the Chinese one is not. Anchoring
                # to the thing it must stay clear of is what makes that hold in
                # either language.
                target_label = MathTex(r"__TARGET_LABEL__", font_size=32, color=C_FLOW).next_to(title, DOWN, buff=0.12).shift(RIGHT * 2.6)

                def clamp(y):
                    if not np.isfinite(y):
                        return np.nan
                    return max(min(y, 2.1), -2.1)

                __APPROXIMATIONS__

                approx_curves = [
                    axes.plot(
                        lambda x, fn=fn: clamp(fn(x)),
                        x_range=[-2 * PI, 2 * PI, 0.02],
                        color=C_HOLD,
                        stroke_width=5,
                        use_smoothing=False,
                    )
                    for fn, _, _ in approximations
                ]
                formula = MathTex(approximations[0][1], font_size=34, color=C_HOLD).to_corner(DL).shift(UP * 0.75)
                note = _t(approximations[0][2], font_size=28, color=C_HOLD).to_edge(DOWN)
                neighborhood = NumberLine(
                    x_range=[-1.2, 1.2, 0.6],
                    length=2.7,
                    color=C_DONE,
                    include_ticks=False,
                ).move_to(axes.c2p(0, -1.65))
                neighborhood_label = _t("先在 0 附近最准确", font_size=24, color=C_DONE).next_to(neighborhood, DOWN, buff=0.08)

                _beat(self, "b01", Write(title), Create(axes), FadeIn(x_labels))
                _beat(self, "b02", Create(target), Write(target_label), run_time=2)
                _beat(self, "b03", Create(neighborhood), Write(neighborhood_label))
                _beat(self, "b04", Create(approx_curves[0]), Write(formula), Write(note), run_time=1.6)

                current_curve = approx_curves[0]
                current_formula = formula
                current_note = note
                for i in range(1, len(approximations)):
                    new_formula = MathTex(approximations[i][1], font_size=34, color=C_HOLD).to_corner(DL).shift(UP * 0.75)
                    new_note = _t(approximations[i][2], font_size=28, color=C_HOLD).to_edge(DOWN)
                    # One beat per added order: the narration steps through the
                    # polynomials one at a time, so the picture does too. A run
                    # whose narration is shorter than the term list simply falls
                    # back to the written run_time for the extra terms.
                    _beat(
                        self, "b%02d" % (4 + i),
                        ReplacementTransform(current_curve, approx_curves[i]),
                        ReplacementTransform(current_formula, new_formula),
                        ReplacementTransform(current_note, new_note),
                        run_time=2,
                    )
                    current_curve = approx_curves[i]
                    current_formula = new_formula
                    current_note = new_note

                final_formula = MathTex(
                    r"__FINAL_FORMULA__",
                    font_size=34,
                    color=C_DONE,
                ).to_edge(DOWN)
                conclusion = _t("更多项会把逼近范围继续向外推开", font_size=28, color=C_DONE).next_to(final_formula, UP, buff=0.15)
                _beat(
                    self, "b%02d" % (4 + len(approximations)),
                    # The neighbourhood label goes with the note. It explains the
                    # early frames and is superseded by the conclusion, which
                    # lands on the same spot — leaving it drew the two sentences
                    # on top of each other in the final frame of every render.
                    FadeOut(current_note), FadeOut(neighborhood_label),
                    Write(conclusion),
                    ReplacementTransform(current_formula, final_formula),
                )
                self.wait(1)
        '''
    ).strip()
    return (
        body.replace("__TITLE__", variant["title"])
        .replace("__TARGET_FN__", variant["target_fn"])
        .replace("__TARGET_LABEL__", variant["target_label"])
        .replace("__APPROXIMATIONS__", _taylor_terms_source(variant["terms"]))
        .replace("__FINAL_FORMULA__", variant["final"])
    )


def _derivative_tangent_scene(plan: AnimationPlan) -> str:
    _raw, numpy_expr, latex = _calculus_expr(plan, "x ** 2")
    body = dedent(
        r'''
        class GeneratedScene(Scene):
            def construct(self):
                def f(x):
                    return __PLOT_EXPR__

                def safe_f(x):
                    try:
                        y = float(f(x))
                    except Exception:
                        return np.nan
                    if not np.isfinite(y) or abs(y) > 1e4:
                        return np.nan
                    return y

                def slope_at(x0):
                    eps = 1e-3
                    y1 = safe_f(x0 - eps)
                    y2 = safe_f(x0 + eps)
                    if not (np.isfinite(y1) and np.isfinite(y2)):
                        return 0.0
                    return (y2 - y1) / (2 * eps)

                x_min, x_max = -3.2, 3.2
                y_values = [safe_f(x) for x in np.linspace(x_min, x_max, 400)]
                visible = [y for y in y_values if np.isfinite(y) and abs(y) <= 12]
                y_min, y_max = (min(visible), max(visible)) if visible else (-2, 6)
                pad = max(1.0, 0.22 * (y_max - y_min))
                y_min, y_max = max(y_min - pad, -8), min(y_max + pad, 8)
                if y_max - y_min < 2:
                    y_min, y_max = y_min - 1, y_max + 1

                title = VGroup(
                    _t("导数：", font_size=34),
                    MathTex(r"y = __LATEX__", font_size=34),
                    _t(" 的切线斜率", font_size=34),
                ).arrange(RIGHT, buff=0.12).to_edge(UP)
                # Sized to the shared caption budget; see PLOT_Y_LENGTH.
                axes = Axes(
                    x_range=[x_min, x_max, 1],
                    y_range=[y_min, y_max, 1],
                    x_length=9.4,
                    y_length=PLOT_Y_LENGTH,
                    tips=False,
                ).shift(PLOT_SHIFT).add_coordinates()
                curve = axes.plot(safe_f, x_range=[x_min, x_max, 0.02], color=C_FLOW, use_smoothing=False)

                x0 = 1.0
                h = ValueTracker(1.45)

                def point_at(xv):
                    yv = safe_f(xv)
                    if not np.isfinite(yv):
                        yv = 0
                    return axes.c2p(xv, yv)

                p_dot = Dot(point_at(x0), color=C_HOLD, radius=0.075)
                p_label = _t("x", font_size=24, color=C_HOLD).next_to(p_dot, DOWN, buff=0.1)
                q_dot = always_redraw(lambda: Dot(point_at(x0 + h.get_value()), color=C_WARN, radius=0.07))
                q_label = always_redraw(lambda: _t("x+h", font_size=24, color=C_WARN).next_to(q_dot, UP, buff=0.1))
                secant = always_redraw(
                    lambda: Line(point_at(x0), point_at(x0 + h.get_value()), color=C_HOLD, stroke_width=6).set_length(4.2)
                )
                tangent = Line(
                    axes.c2p(x0 - 1.7, safe_f(x0) - 1.7 * slope_at(x0)),
                    axes.c2p(x0 + 1.7, safe_f(x0) + 1.7 * slope_at(x0)),
                    color=C_DONE,
                    stroke_width=6,
                )
                secant_label = MathTex(r"\frac{\Delta y}{\Delta x}", font_size=34, color=C_HOLD).to_corner(DL).shift(UP * 0.55)
                derivative_label = MathTex(r"\frac{dy}{dx}=f'(x)", font_size=38, color=C_DONE).to_edge(DOWN)
                conclusion = _t("两点靠近时，割线斜率逼近切线斜率", font_size=28).next_to(derivative_label, UP, buff=0.18)

                _beat(self, "b01", Write(title), Create(axes))
                _beat(self, "b02", Create(curve), run_time=2)
                _beat(self, "b03", FadeIn(p_dot), Write(p_label), FadeIn(q_dot), Write(q_label))
                _beat(self, "b04", Create(secant), Write(secant_label))
                # The secant sliding onto the tangent *is* the explanation, so it
                # spreads across its whole sentence instead of finishing early.
                _beat_stretch(self, "b05", h.animate.set_value(0.22), run_time=4)
                _beat(self, "b06", ReplacementTransform(secant.copy(), tangent), Write(derivative_label), Write(conclusion))
                self.wait(1)
        '''
    ).strip()
    return body.replace("__PLOT_EXPR__", numpy_expr).replace("__LATEX__", latex)


def _riemann_integral_scene(plan: AnimationPlan) -> str:
    _raw, numpy_expr, latex = _calculus_expr(plan, "0.25 * x ** 2 + 0.5")
    body = dedent(
        r'''
        class GeneratedScene(Scene):
            def construct(self):
                def f(x):
                    return __PLOT_EXPR__

                def safe_f(x):
                    try:
                        y = float(f(x))
                    except Exception:
                        return 0.0
                    if not np.isfinite(y) or abs(y) > 20:
                        return 0.0
                    return y

                def rectangles(n):
                    group = VGroup()
                    a, b = -2.0, 2.2
                    dx = (b - a) / n
                    for i in range(n):
                        x0 = a + i * dx
                        x1 = x0 + dx
                        xm = x0 + dx / 2
                        y = safe_f(xm)
                        color = interpolate_color(C_FLOW, C_DONE, i / max(n - 1, 1))
                        rect = Polygon(
                            axes.c2p(x0, 0),
                            axes.c2p(x1, 0),
                            axes.c2p(x1, y),
                            axes.c2p(x0, y),
                            color=color,
                            fill_color=color,
                            fill_opacity=0.48,
                            stroke_width=1.2,
                        )
                        group.add(rect)
                    return group

                title = VGroup(
                    _t("定积分：", font_size=34),
                    MathTex(r"y = __LATEX__", font_size=34),
                    _t(" 下的面积", font_size=34),
                ).arrange(RIGHT, buff=0.12).to_edge(UP)
                # Sized to the shared caption budget; see PLOT_Y_LENGTH.
                axes = Axes(
                    x_range=[-2.8, 2.8, 1],
                    y_range=[-0.8, 4.2, 1],
                    x_length=9.2,
                    y_length=PLOT_Y_LENGTH,
                    tips=False,
                ).shift(PLOT_SHIFT).add_coordinates()
                curve = axes.plot(safe_f, x_range=[-2.3, 2.35, 0.02], color=C_FLOW, use_smoothing=False)
                coarse = rectangles(6)
                fine = rectangles(24)
                brace_line = Line(axes.c2p(-2.0, -0.35), axes.c2p(2.2, -0.35), color=C_DONE)
                brace = Brace(brace_line, direction=DOWN, color=C_DONE)
                # Beside the brace, not under it. The brace already hangs below
                # the plot, so a label under *that* lands in the caption band —
                # it used to overlap the integral, and once the plot was raised
                # it overlapped the conclusion instead. The brace spans the
                # rectangles and stops well short of the right edge, so there is
                # room next to it and none beneath.
                dx_label = MathTex(r"\Delta x \to 0", font_size=32, color=C_DONE).next_to(brace, RIGHT, buff=0.15)
                sum_label = MathTex(r"\sum f(x_i)\Delta x", font_size=34, color=C_HOLD).to_corner(DL).shift(UP * 0.6)
                integral_label = MathTex(r"\int_a^b f(x)\,dx", font_size=40, color=C_DONE).to_edge(DOWN)
                conclusion = _t("矩形越细，总面积越接近曲线下方的面积", font_size=28).next_to(integral_label, UP, buff=0.18)

                # One beat per narrated step. With measured narration these run
                # exactly as long as the voice describing them; without it they
                # keep the timings they were written with.
                _beat(self, "b01", Write(title), Create(axes))
                _beat(self, "b02", Create(curve), run_time=2)
                _beat(self, "b03", FadeIn(coarse), Write(sum_label))
                # The refinement is the argument, so it spreads across its whole
                # sentence rather than finishing early over a held frame.
                _beat_stretch(self, "b04", Transform(coarse, fine), run_time=2.5)
                _beat(self, "b05", Create(brace_line), GrowFromCenter(brace), Write(dx_label))
                _beat(self, "b06", Write(integral_label), Write(conclusion))
                self.wait(1)
        '''
    ).strip()
    return body.replace("__PLOT_EXPR__", numpy_expr).replace("__LATEX__", latex)


def _ftc_accumulation_scene(plan: AnimationPlan) -> str:
    _raw, numpy_expr, latex = _calculus_expr(plan, "0.3 * x ** 2 + 0.4")
    body = dedent(
        r'''
        class GeneratedScene(Scene):
            def construct(self):
                def f(x):
                    return __PLOT_EXPR__

                def safe_f(x):
                    try:
                        y = float(f(x))
                    except Exception:
                        return 0.0
                    if not np.isfinite(y) or abs(y) > 20:
                        return 0.0
                    return y

                # Precompute the cumulative area once, then look up F(x) by
                # interpolation. always_redraw calls accum() twice per frame, so
                # re-integrating from scratch each time would be needlessly slow.
                accum_a = -1.8
                accum_grid = np.linspace(accum_a, 2.4, 400)
                accum_f = np.array([safe_f(v) for v in accum_grid])
                accum_table = np.concatenate((
                    [0.0],
                    np.cumsum((accum_f[1:] + accum_f[:-1]) / 2 * np.diff(accum_grid)),
                ))

                def accum(x):
                    if x <= accum_a:
                        return 0.0
                    return float(np.interp(x, accum_grid, accum_table))

                title = _t("微积分基本定理", font_size=38).to_edge(UP)
                left_axes = Axes(
                    x_range=[-2.2, 2.4, 1],
                    y_range=[-0.5, 3.5, 1],
                    x_length=5.0,
                    y_length=3.6,
                    tips=False,
                ).shift(LEFT * 3.05 + DOWN * 0.25)
                right_axes = Axes(
                    x_range=[-2.2, 2.4, 1],
                    y_range=[-0.5, 7.0, 2],
                    x_length=5.0,
                    y_length=3.6,
                    tips=False,
                ).shift(RIGHT * 3.05 + DOWN * 0.25)
                f_curve = left_axes.plot(safe_f, x_range=[-2.0, 2.25, 0.02], color=C_FLOW, use_smoothing=False)
                f_title = VGroup(
                    MathTex(r"f(x)=", font_size=28),
                    MathTex(r"__LATEX__", font_size=28),
                ).arrange(RIGHT, buff=0.06).next_to(left_axes, UP, buff=0.22)
                F_title = MathTex(r"F(x)=\int_a^x f(t)\,dt", font_size=30, color=C_DONE).next_to(right_axes, UP, buff=0.22)

                x_tracker = ValueTracker(-1.8)
                area = always_redraw(
                    lambda: left_axes.get_area(
                        f_curve,
                        x_range=[-1.8, x_tracker.get_value()],
                        color=C_DONE,
                        opacity=0.45,
                    )
                )
                vertical = always_redraw(
                    lambda: Line(
                        left_axes.c2p(x_tracker.get_value(), 0),
                        left_axes.c2p(x_tracker.get_value(), safe_f(x_tracker.get_value())),
                        color=C_HOLD,
                        stroke_width=5,
                    )
                )
                moving_dot = always_redraw(
                    lambda: Dot(
                        right_axes.c2p(x_tracker.get_value(), accum(x_tracker.get_value())),
                        color=C_WARN,
                        radius=0.06,
                    )
                )
                F_trace = TracedPath(moving_dot.get_center, stroke_color=C_DONE, stroke_width=5, dissipating_time=None)
                guide = always_redraw(
                    lambda: DashedLine(
                        left_axes.c2p(x_tracker.get_value(), safe_f(x_tracker.get_value())),
                        right_axes.c2p(x_tracker.get_value(), accum(x_tracker.get_value())),
                        color=C_HOLD,
                        stroke_width=2,
                        dash_length=0.12,
                    )
                )
                equation = MathTex(r"F'(x)=f(x)", font_size=42, color=C_DONE).to_edge(DOWN)
                conclusion = _t("面积函数的瞬时变化率，等于当前高度 f(x)", font_size=28).next_to(equation, UP, buff=0.16)

                _beat(self, "b01", Write(title))
                _beat(self, "b02", Create(left_axes), Create(right_axes), Write(f_title), Write(F_title))
                _beat(self, "b03", Create(f_curve))
                self.add(F_trace)
                _beat(self, "b04", FadeIn(area), Create(vertical), FadeIn(moving_dot), Create(guide))
                # The sweep is the whole point of this concept: the upper limit
                # moving is what draws the accumulation curve, so it fills its
                # sentence rather than finishing early under a frozen frame.
                _beat_stretch(self, "b05", x_tracker.animate.set_value(2.15), run_time=5.5)
                _beat(self, "b06", Write(equation), Write(conclusion))
                self.wait(1)
        '''
    ).strip()
    return body.replace("__PLOT_EXPR__", numpy_expr).replace("__LATEX__", latex)


def _tangent_shift_scene(plan: AnimationPlan) -> str:
    """A line, a curve lifted until it just touches, and the ratio that follows.

    **Beat map — what each beat shows.**

    ====  ======================================  =========================
    beat  animation                               caption
    ====  ======================================  =========================
    b01   the statement card, then the line      the line
    b02   curve enters unshifted, two crossings   two crossings
    b03   the span between them is marked         between them the line wins
    b04   the shift rises, crossings converge     lifting the curve
    b05   they merge; the touch point is named    one touch, and only one
          (with the working card alongside)
    b06   the pair fades, the ratio is drawn      the ratio itself
    b07   its maximum is marked at the answer     the maximum is exactly one
    ====  ======================================  =========================

    Two optional cards of LaTeX lines, each revealed a line per equal slice of
    its beat. ``problem`` holds the statement and any working that dead-ends;
    it fills b01 centre-screen and clears as the axes come in. ``working``
    holds the algebra that reads the answer off the tangency, and sits in the
    upper-left corner through b05 beside the touch it describes. Omit either
    and its beat behaves as it did before — a drawn line, a fading-in dot.

    **Why a shift rather than a re-plot.** The curve moves only up, so it is
    plotted once and translated by an updater. ``cone_slice`` rebuilds two
    mobjects every frame with ``always_redraw`` and costs five to seven minutes
    per sweep at 1080p60; a translation is a transform on points already
    computed, so the same motion is nearly free.

    Crossings are found by scanning and bisecting rather than solved, because
    ``curve(x) + a = line(x)`` has no general closed form — for the exam case
    it is ``e**x + a = x + 2``, which is exactly the transcendental equation
    the problem exists to avoid.
    """
    line_raw = str(plan.parameters.get("line") or "x + 2")
    curve_raw = str(plan.parameters.get("curve") or "e ** x")
    if not validate_expression(line_raw):
        line_raw = "x + 2"
    if not validate_expression(curve_raw):
        curve_raw = "e ** x"
    try:
        shift = float(plan.parameters.get("shift", 1.0))
    except (TypeError, ValueError):
        shift = 1.0
    if not (0.0 < shift <= 8.0):
        shift = 1.0

    # Optional cards of LaTeX lines, revealed one at a time across a beat.
    # Without them b01 and b05 have nothing to look at but a finished picture,
    # and a narrator reading out algebra the viewer never sees written.
    def _card(key, limit):
        raw = plan.parameters.get(key)
        if isinstance(raw, str):
            raw = [raw]
        return [
            step.strip()[:220]
            for step in (raw or ())
            if isinstance(step, str) and step.strip()
        ][:limit]

    problem_steps = _card("problem", 4)
    working_steps = _card("working", 5)

    body = dedent(
        r'''
        class GeneratedScene(Scene):
            def construct(self):
                SHIFT = __SHIFT__

                def line_f(x):
                    return __LINE_EXPR__

                def curve_f(x):
                    return __CURVE_EXPR__

                def safe(fn, x):
                    try:
                        y = float(fn(x))
                    except Exception:
                        return np.nan
                    return y if np.isfinite(y) and abs(y) < 1e4 else np.nan

                TOUCH_TOL = 5e-3

                def crossings(a, lo=-6.0, hi=4.0, n=900):
                    """Where curve + a meets the line, by scan then refinement.

                    Sign changes are bisected. Tangencies are not found that way
                    at all — the gap touches zero without changing sign — so
                    local extrema of the gap are refined too and kept when they
                    reach zero. That case is the entire point of the scene, and
                    the exact shift the scene animates to is the one where the
                    only contact is a tangency.
                    """
                    def gap(x):
                        c, l = safe(curve_f, x), safe(line_f, x)
                        return np.nan if (np.isnan(c) or np.isnan(l)) else c + a - l
                    xs = np.linspace(lo, hi, n)
                    gs = [gap(x) for x in xs]
                    found = []
                    for i in range(1, len(xs)):
                        p, g = gs[i - 1], gs[i]
                        if np.isnan(p) or np.isnan(g):
                            continue
                        if p == 0:
                            found.append(xs[i - 1])
                        elif p * g < 0:
                            a_, b_ = xs[i - 1], xs[i]
                            for _ in range(60):
                                m = 0.5 * (a_ + b_)
                                gm = gap(m)
                                if np.isnan(gm):
                                    break
                                if gap(a_) * gm <= 0:
                                    b_ = m
                                else:
                                    a_ = m
                            found.append(0.5 * (a_ + b_))
                    # Tangencies: refine every interior extremum of |gap| by
                    # golden section and keep the ones that reach zero.
                    inv = 0.6180339887498949
                    for i in range(1, len(xs) - 1):
                        p, g, nx = gs[i - 1], gs[i], gs[i + 1]
                        if np.isnan(p) or np.isnan(g) or np.isnan(nx):
                            continue
                        if not (abs(g) < abs(p) and abs(g) < abs(nx)):
                            continue
                        a_, b_ = xs[i - 1], xs[i + 1]
                        for _ in range(80):
                            c_, d_ = b_ - (b_ - a_) * inv, a_ + (b_ - a_) * inv
                            gc, gd = gap(c_), gap(d_)
                            if np.isnan(gc) or np.isnan(gd):
                                break
                            if abs(gc) < abs(gd):
                                b_ = d_
                            else:
                                a_ = c_
                        m = 0.5 * (a_ + b_)
                        gm = gap(m)
                        if np.isnan(gm) or abs(gm) > TOUCH_TOL:
                            continue
                        if all(abs(m - x) > 1e-3 for x in found):
                            found.append(m)
                    return sorted(found)

                X_MIN, X_MAX = -3.4, 2.6
                Y_MIN, Y_MAX = -1.0, 7.0
                axes = Axes(
                    x_range=[X_MIN, X_MAX, 1],
                    y_range=[Y_MIN, Y_MAX, 1],
                    x_length=9.2,
                    y_length=5.0,
                    tips=False,
                ).shift(UP * 0.35).add_coordinates()

                title = _t("__TITLE__", font_size=36).to_edge(UP)

                captions = VGroup(*[
                    _t(line, font_size=28).to_edge(DOWN) for line in (
                        "A straight line",
                        "and a curve that grows much faster",
                        "Between the crossings the line is higher",
                        "Lift the curve and they close in",
                        "One touch, and only one",
                        "So the ratio never passes 1",
                        "Maximum exactly 1 — that fixes a",
                    )
                ])
                for cap in captions:
                    cap.set_opacity(0.0)
                self.add(*captions)

                def show(i):
                    for j, cap in enumerate(captions):
                        cap.set_opacity(1.0 if j == i else 0.0)

                line_plot = axes.plot(lambda x: safe(line_f, x),
                                      x_range=[X_MIN, X_MAX, 0.02],
                                      color=C_HOLD, use_smoothing=False)
                # Plotted once at a = 0 and translated afterwards. The curve only
                # ever moves vertically, so re-plotting it per frame would buy
                # nothing and cost the whole render.
                curve_plot = axes.plot(lambda x: safe(curve_f, x),
                                       x_range=[X_MIN, X_MAX, 0.02],
                                       color=C_FLOW, use_smoothing=False)
                # One unit of `a` in screen space, measured off the axes rather
                # than assumed, and the curve's home position captured before
                # anything moves it. Both are needed by the updater below, so
                # they are bound first — a closure over a name defined later
                # happens to work and is a trap for the next edit.
                unit_up = axes.c2p(0, 1) - axes.c2p(0, 0)
                home = curve_plot.get_center()
                a_tracker = ValueTracker(0.0)
                curve_plot.add_updater(
                    lambda m: m.move_to(home + unit_up * a_tracker.get_value()))

                dots = VGroup(Dot(color=C_AUX, radius=0.075),
                              Dot(color=C_AUX, radius=0.075))

                def place_dots(mob):
                    a = a_tracker.get_value()
                    xs = crossings(a)
                    for i, dot in enumerate(mob):
                        if i < len(xs):
                            dot.move_to(axes.c2p(xs[i], safe(line_f, xs[i])))
                            dot.set_opacity(1.0)
                        else:
                            dot.set_opacity(0.0)

                place_dots(dots)
                dots.add_updater(place_dots)

                touch_x = 0.0
                xs0 = crossings(SHIFT)
                if xs0:
                    touch_x = float(np.mean(xs0))
                touch = Dot(axes.c2p(touch_x, safe(line_f, touch_x)),
                            color=C_WARN, radius=0.09)
                # Formatted here, not by a build-time helper: this source runs
                # standalone, so anything it names has to exist inside it.
                def _num(v):
                    return str(int(round(v))) if abs(v - round(v)) < 1e-6 else f"{v:.2f}"

                touch_label = MathTex(
                    r"(%s,\ %s)" % (_num(touch_x), _num(safe(line_f, touch_x))),
                    font_size=32, color=C_WARN,
                ).next_to(touch, RIGHT, buff=0.18)

                PROBLEM_STEPS = __PROBLEM_STEPS__
                WORKING_STEPS = __WORKING_STEPS__

                def build_card(steps, font_size, max_width):
                    card = VGroup(*[
                        MathTex(s, font_size=font_size) for s in steps
                    ]).arrange(DOWN, buff=0.5, aligned_edge=LEFT)
                    if card.width > max_width:
                        card.scale_to_fit_width(max_width)
                    return card

                def reveal_over(key, parts, pre=(), post=(),
                                pre_t=0.9, post_t=1.6):
                    """Write `parts` one per equal slice of beat `key`.

                    A card is only worth showing if the viewer gets time to
                    read it, and the beat is only worth its length if
                    something happens across it — so the two constraints are
                    the same one, and the narration's own measured length
                    sets the pace.
                    """
                    span = BEAT_SECONDS.get(key)
                    lead = pre_t if pre else 0.0
                    tail = post_t if post else 0.0
                    if pre:
                        self.play(*pre, run_time=lead)
                    if span is None:
                        for part in parts:
                            self.play(Write(part), run_time=1.0)
                    else:
                        budget = span - lead - tail
                        slice_t = max(budget / max(len(parts), 1), 0.6)
                        for part in parts:
                            reveal = min(1.2, slice_t * 0.5)
                            self.play(Write(part), run_time=reveal)
                            if slice_t - reveal > 0.02:
                                self.wait(slice_t - reveal)
                    if post:
                        self.play(*post, run_time=tail)

                self.play(Write(title), run_time=0.8)
                if PROBLEM_STEPS:
                    # The statement first, then the step that goes nowhere.
                    # Centred and large: nothing else is on screen yet, and
                    # the beat exists so the problem gets read.
                    card = build_card(PROBLEM_STEPS, 40, 11.0).move_to(ORIGIN)
                    # The first caption describes the line, so it arrives with
                    # the line rather than over the statement it does not
                    # describe — as an animation, since `show` is a set.
                    reveal_over("b01", card,
                                post=(FadeOut(card), Create(axes),
                                      Create(line_plot),
                                      captions[0].animate.set_opacity(1.0)))
                else:
                    self.play(Create(axes), run_time=0.8)
                    show(0)
                    _beat(self, "b01", Create(line_plot))
                show(1)
                _beat(self, "b02", Create(curve_plot), FadeIn(dots))
                show(2)
                _beat(self, "b03")
                show(3)
                _beat_stretch(self, "b04",
                              a_tracker.animate.set_value(SHIFT), run_time=3.0)
                show(4)
                dots.clear_updaters()
                if WORKING_STEPS:
                    # The tangency picture is the payoff, so it stays put and
                    # the algebra reading it off is written beside it — upper
                    # left, the one corner a rising curve never enters.
                    work = build_card(WORKING_STEPS, 34, 4.6)
                    work.to_corner(UL).shift(DOWN * 0.9)
                    reveal_over("b05", work,
                                pre=(FadeIn(touch), Write(touch_label)))
                    working_out = [FadeOut(work)]
                else:
                    _beat(self, "b05", FadeIn(touch), Write(touch_label))
                    working_out = []

                # The ratio, on its own axes: the same statement read back as
                # the function the question actually asked about.
                curve_plot.clear_updaters()
                ratio_axes = Axes(
                    x_range=[X_MIN, X_MAX, 1],
                    y_range=[-0.4, 1.4, 0.5],
                    x_length=9.2,
                    y_length=4.4,
                    tips=False,
                ).shift(UP * 0.35).add_coordinates()

                def ratio(x):
                    l, c = safe(line_f, x), safe(curve_f, x)
                    if np.isnan(l) or np.isnan(c):
                        return np.nan
                    d = c + SHIFT
                    return np.nan if abs(d) < 1e-9 else l / d

                # Started right of X_MIN on purpose: the ratio dives steeply
                # below its root and would draw a near-vertical stroke through
                # the caption, which reads as a rendering fault rather than as
                # the function going negative.
                ratio_plot = ratio_axes.plot(ratio, x_range=[X_MIN + 0.8, X_MAX, 0.02],
                                             color=C_HOLD, use_smoothing=False)
                peak = Dot(ratio_axes.c2p(touch_x, 1.0), color=C_WARN, radius=0.09)
                one_line = DashedLine(
                    ratio_axes.c2p(X_MIN + 0.8, 1.0), ratio_axes.c2p(X_MAX, 1.0),
                    color=C_MUTED, stroke_width=2, dash_length=0.12)

                show(5)
                _beat(self, "b06",
                      *working_out,
                      FadeOut(line_plot), FadeOut(curve_plot), FadeOut(dots),
                      FadeOut(touch), FadeOut(touch_label),
                      ReplacementTransform(axes, ratio_axes),
                      Create(ratio_plot), Create(one_line))
                show(6)
                _beat(self, "b07", FadeIn(peak))
                self.wait(1)
        '''
    ).strip()
    return (
        body.replace("__SHIFT__", repr(shift))
        .replace("__LINE_EXPR__", to_numpy_expr(line_raw))
        .replace("__CURVE_EXPR__", to_numpy_expr(curve_raw))
        .replace("__PROBLEM_STEPS__", repr(problem_steps))
        .replace("__WORKING_STEPS__", repr(working_steps))
        .replace("__TITLE__", _escape_text(
            plan.title_zh or "Lift the curve until it just touches"))
    )


_CALCULUS_CONCEPT_BUILDERS = {
    ConceptCalculus.TAYLOR_SERIES: _taylor_series_scene,
    ConceptCalculus.DERIVATIVE_TANGENT: _derivative_tangent_scene,
    ConceptCalculus.RIEMANN_INTEGRAL: _riemann_integral_scene,
    ConceptCalculus.FTC_ACCUMULATION: _ftc_accumulation_scene,
    ConceptCalculus.TANGENT_SHIFT: _tangent_shift_scene,
}


@scene_for(Topic.FUNCTION)
def _function_scene(plan: AnimationPlan) -> str:
    raw = plan.parameters.get("expression") or "x**2"
    if not validate_expression(raw):
        raw = "x**2"
    latex = to_latex_expr(raw)
    body = dedent(
        '''
        class GeneratedScene(Scene):
            def construct(self):
                def f(x):
                    return __PLOT_EXPR__

                def safe_f(x):
                    try:
                        y = float(f(x))
                    except Exception:
                        return np.nan
                    if not np.isfinite(y) or abs(y) > 1e6:
                        return np.nan
                    return y

                x_min, x_max = -6, 6
                samples = []
                for xv in np.linspace(x_min, x_max, 600):
                    yv = safe_f(xv)
                    if np.isfinite(yv):
                        samples.append((xv, yv))

                visible = [y for _, y in samples if abs(y) <= 50]
                if visible:
                    y_min, y_max = min(visible), max(visible)
                    pad = max(1.0, 0.2 * (y_max - y_min))
                    y_min, y_max = max(y_min - pad, -20), min(y_max + pad, 20)
                else:
                    y_min, y_max = -5, 5
                if y_max - y_min < 1:
                    y_min, y_max = y_min - 1, y_max + 1
                y_step = max(1, round((y_max - y_min) / 6))

                axes = Axes(
                    x_range=[x_min, x_max, 1],
                    y_range=[y_min, y_max, y_step],
                    x_length=10,
                    y_length=5.5,
                    tips=False,
                ).add_coordinates()
                curve = axes.plot(safe_f, x_range=[x_min, x_max, 0.02], color=C_FLOW, use_smoothing=False)
                title = VGroup(
                    _t("函数", font_size=34),
                    MathTex(r"y = __LATEX__", font_size=34),
                    _t("的图像", font_size=34),
                ).arrange(RIGHT, buff=0.15).to_edge(UP)

                markers = VGroup()
                y0 = safe_f(0.0)
                if np.isfinite(y0) and y_min <= y0 <= y_max:
                    markers.add(Dot(axes.c2p(0, y0), color=C_HOLD))

                roots = []
                for (xa, ya), (xb, yb) in zip(samples, samples[1:]):
                    if ya == 0:
                        root = xa
                    elif ya * yb < 0:
                        root = xa - ya * (xb - xa) / (yb - ya)
                    else:
                        continue
                    if all(abs(root - r) > 0.05 for r in roots):
                        roots.append(root)
                for root in roots[:8]:
                    markers.add(Dot(axes.c2p(root, 0), color=C_WARN))

                note = _t("红点：零点    黄点：y 轴截距", font_size=26).to_edge(DOWN)

                self.play(Write(title), Create(axes))
                self.play(Create(curve), run_time=2)
                if len(markers) > 0:
                    self.play(FadeIn(markers))
                self.play(Write(note))
                self.wait(1)
        '''
    ).strip()
    return body.replace("__PLOT_EXPR__", to_numpy_expr(raw)).replace("__LATEX__", latex)



def _fit_plane_reach(matrix, half_w: float, half_h: float,
                     base_x: float = 6.0, base_y: float = 4.0) -> tuple[float, float]:
    """Half-extents for a plane whose image under ``matrix`` fits the frame.

    The corner of a rectangle maps furthest, and for a linear map the extreme
    image coordinate is ``a*|m00| + b*|m01|`` horizontally (and the analogous
    sum vertically), so one scale factor on the base extents is enough. Never
    scales *up*: a small matrix should not blow the grid past the frame in the
    other direction.
    """
    (m00, m01), (m10, m11) = matrix
    span_x = base_x * abs(m00) + base_y * abs(m01)
    span_y = base_x * abs(m10) + base_y * abs(m11)
    t = 1.0
    if span_x > 0:
        t = min(t, half_w / span_x)
    if span_y > 0:
        t = min(t, half_h / span_y)
    # Below this the grid has too few lines to read as a grid at all.
    t = max(t, 0.18)
    return (round(base_x * t, 3), round(base_y * t, 3))


class _BeatKeys:
    """Sequential beat keys, numbered in the order the scene actually emits.

    Hardcoding ``b01``..``b09`` leaves gaps when a section is not requested — a
    scene with no span step jumped from b02 to b04 — and ``beat_seconds`` is
    matched by key, so every step after the gap would be handed the length of
    the wrong narration clip.
    """

    def __init__(self) -> None:
        self._n = 0

    def next(self) -> str:
        self._n += 1
        return '"b%02d"' % self._n


def _linear_algebra_scene(plan: AnimationPlan) -> str:
    """One scene, read five ways, depending on what the parameters ask for.

    The geometry is resolved here rather than in the emitted scene: eigenvectors
    and the determinant are computed from the matrix now, as constants, so the
    animation draws a result that was already checked instead of deriving one at
    render time. A matrix with no real eigenvalues simply gets no eigen-step —
    the alternative, drawing an "invariant" direction for a rotation, is the
    confidently-wrong output this library exists to avoid.
    """
    params = plan.parameters or {}
    matrix = coerce_matrix(params.get("matrix", IDENTITY))
    (m00, m01), (m10, m11) = matrix
    is_identity = matrix == IDENTITY

    # Shared with the precondition check rather than reimplemented, so what the
    # check reports dropped is exactly what this fails to draw.
    vectors = coerce_vectors(params.get("vectors"))
    if not vectors:
        # Something has to move for the map to be visible at all.
        vectors = [(1.0, 0.0), (0.0, 1.0)] if not is_identity else [(3.0, 1.0), (1.0, 2.0)]

    labels = [str(x) for x in (params.get("labels") or [])]

    want_eigen = bool(params.get("show_eigenvectors"))
    want_det = bool(params.get("show_determinant"))
    want_span = bool(params.get("show_span"))

    pairs = eigenpairs(matrix) if want_eigen else []
    det = determinant(matrix)
    span_dim = span_dimension(vectors) if want_span else 0

    title = params.get("title") or (
        "Eigenvectors" if pairs else
        "Span" if want_span else
        "Determinant" if want_det else
        "A linear map" if not is_identity else
        "Vectors"
    )

    lines = []
    lines.append("class GeneratedScene(Scene):")
    lines.append("    def construct(self):")
    lines.append("        M = [[%r, %r], [%r, %r]]" % (m00, m01, m10, m11))
    # Size the plane so its *image* under M fits the frame, not the plane
    # itself. A grid drawn to a fixed +/-6 and then stretched by a matrix with
    # a large eigenvalue runs many units past the edge — QC measured 11.8 — and
    # the transformed picture, the one the lesson is about, is the half that
    # leaves the screen. Solving for the image instead keeps the whole
    # animation inside the frame for any matrix, which is why this is computed
    # rather than tuned.
    half_w, half_h = 7.11, 4.0
    x_reach, y_reach = _fit_plane_reach(matrix, half_w, half_h)
    lines.append("        plane = NumberPlane(")
    lines.append("            x_range=[%r, %r, 1], y_range=[%r, %r, 1],"
                 % (-x_reach, x_reach, -y_reach, y_reach))
    lines.append("            background_line_style={\"stroke_color\": C_RULE, \"stroke_width\": 1,")
    lines.append("                                   \"stroke_opacity\": 0.5},")
    lines.append("        )")
    lines.append("        title = _t(%r, font_size=34).to_edge(UP)" % title)
    # The grid and any long dashed line run behind the title; a backdrop is what
    # keeps it legible without moving the plane off centre.
    lines.append("        title.add_background_rectangle(opacity=0.9)")
    beat = _BeatKeys()
    lines.append("        _beat(self, %s, Write(title), Create(plane))" % beat.next())

    # The vectors themselves.
    lines.append("        arrows = VGroup()")
    lines.append("        tags = VGroup()")
    for i, (vx, vy) in enumerate(vectors):
        colour = ["C_FLOW", "C_HOLD", "C_DONE", "C_AUX", "C_WARM"][i % 5]
        lines.append("        a%d = Arrow(plane.c2p(0, 0), plane.c2p(%r, %r), "
                     "buff=0, color=%s)" % (i, vx, vy, colour))
        lines.append("        arrows.add(a%d)" % i)
        if i < len(labels):
            # Offset along the vector's own normal, so a label clears its
            # arrowhead and the unit square instead of sitting under them.
            nx, ny = -vy, vx
            n = (nx * nx + ny * ny) ** 0.5 or 1.0
            lines.append("        tags.add(_t(%r, font_size=26, color=%s)"
                         ".move_to(plane.c2p(%r, %r)))"
                         % (labels[i], colour,
                            vx * 1.06 + nx / n * 0.42, vy * 1.06 + ny / n * 0.42))
            lines.append("        tags[-1].add_background_rectangle(opacity=0.85)")
    lines.append("        _beat(self, " + beat.next() + ", *[GrowArrow(a) for a in arrows], "
                 "*[Write(t) for t in tags])")

    # Span: a line for one dimension, the whole plane for two. Drawn from the
    # computed dimension, so two parallel vectors do not get a plane.
    if want_span:
        if span_dim <= 1:
            vx, vy = vectors[0]
            lines.append("        span = Line(plane.c2p(%r, %r), plane.c2p(%r, %r), "
                         "color=C_DEEP, stroke_width=6)"
                         % (-6 * vx, -6 * vy, 6 * vx, 6 * vy))
            note = "the span is a line: these vectors are parallel"
        else:
            lines.append("        span = Rectangle(width=12, height=8, color=C_DEEP, "
                         "fill_opacity=0.18, stroke_width=0)")
            note = "the span is the whole plane"
        lines.append("        span_note = _t(%r, font_size=24, color=C_DEEP)"
                     ".to_edge(DOWN)" % note)
        lines.append("        span_note.add_background_rectangle(opacity=0.85)")
        lines.append("        _beat(self, %s, FadeIn(span), Write(span_note))" % beat.next())

    # The unit square, and the area it becomes.
    if want_det:
        lines.append("        square = Polygon(plane.c2p(0, 0), plane.c2p(1, 0), "
                     "plane.c2p(1, 1), plane.c2p(0, 1), color=C_WARM, "
                     "fill_opacity=0.35, stroke_width=2)")
        lines.append("        _beat(self, %s, FadeIn(square))" % beat.next())

    # Eigen-directions, before the map, so the viewer can watch them hold still.
    # Kept short enough to stay inside the frame, and deliberately NOT included
    # in the transformed group below. An eigenline is invariant *as a set*, so
    # the honest picture is one that does not move; feeding it to ApplyMatrix
    # instead redraws the same line lambda times longer, which pushed it several
    # units outside the frame and told the viewer the direction had changed.
    _EIG_REACH = 3.0
    for j, (lam, (ex, ey)) in enumerate(pairs):
        lines.append("        eig%d = DashedLine(plane.c2p(%r, %r), plane.c2p(%r, %r), "
                     "color=C_WARN, stroke_width=4)"
                     % (j, -_EIG_REACH * ex, -_EIG_REACH * ey,
                        _EIG_REACH * ex, _EIG_REACH * ey))
        # Sit the label at the far end of its own line, pushed off the shaft, so
        # it lands clear of the arrows and the unit square rather than under
        # them. A backdrop keeps it readable where the grid runs behind.
        lines.append("        eiglab%d = MathTex(r\"\\lambda = %s\", font_size=30, "
                     "color=C_WARN).move_to(plane.c2p(%r, %r))"
                     % (j, ("%.2f" % lam).rstrip("0").rstrip("."),
                        _EIG_REACH * ex * 0.97 - ey * 0.78,
                        _EIG_REACH * ey * 0.97 + ex * 0.78))
        lines.append("        eiglab%d.add_background_rectangle(opacity=0.85)" % j)
        lines.append("        _beat(self, %s, Create(eig%d), Write(eiglab%d))"
                     % (beat.next(), j, j))

    # Apply the map. Everything drawn in plane coordinates moves together.
    if not is_identity:
        movers = ["plane", "arrows"]
        if want_det:
            movers.append("square")
        # `eig*` is absent on purpose — see _EIG_REACH above.
        lines.append("        moving = VGroup(%s)" % ", ".join(movers))
        lines.append("        _beat_stretch(self, " + beat.next() + ", "
                     "ApplyMatrix(M, moving), run_time=3)")
        if want_det:
            area = abs(det)
            lines.append("        area = _t(%r, font_size=28, color=C_WARM).to_edge(DOWN)"
                         % ("area x %s  (det = %s)"
                            % (("%.2f" % area).rstrip("0").rstrip("."),
                               ("%.2f" % det).rstrip("0").rstrip("."))))
            lines.append("        area.add_background_rectangle(opacity=0.85)")
            lines.append("        _beat(self, %s, Write(area))" % beat.next())
        if pairs:
            # Both captions sit at the bottom; the second must clear the
            # first or the determinant line is drawn over by this one.
            # A 0.15 gap put the two captions inside each other's backdrops, so
            # the upper one shipped half painted over. Clear the whole line.
            place = ".next_to(area, UP, buff=0.42)" if want_det else ".to_edge(DOWN)"
            lines.append("        held = _t(%r, font_size=24, color=C_WARN)%s"
                         % ("the dashed directions did not turn", place))
            lines.append("        held.add_background_rectangle(opacity=0.85)")
            lines.append("        _beat(self, %s, Write(held))" % beat.next())

    lines.append("        self.wait(1)")
    return "\n".join(lines)


#: Biggest a cell is allowed to get. Sized so a 2x2 — much the most common
#: lesson — fills a useful part of the frame rather than sitting as a small
#: block of black space; larger shapes shrink below it. At 0.62 the 2x2 block
#: spanned under a third of the width, which reads as a rendering mistake.
_MM_CELL_MAX = 1.0

#: The band the three grids may occupy, after the title at the top and the
#: running caption at the bottom have taken theirs. Narrower than the frame
#: because the A/B/AB tags hang off the outer edges, and shorter than it looks
#: like it could be: a caption placed with ``to_edge(DOWN)`` reaches y=-3.1, so
#: a band that used the full 8 units let the bottom row of the product sit
#: under the closing line. ``qc`` reported it as ``text_obscured`` at 4x4.
_MM_BAND = (12.0, 5.6)

#: Vertical centre of the block. Slightly low, because the title above it is
#: larger than the caption below.
_MM_CENTRE_Y = -0.1


def _matmul_layout(m: int, k: int, n: int) -> tuple[float, tuple, tuple, tuple]:
    """Cell size and the three top-left cell centres, solved from the shapes.

    The schoolbook arrangement puts B above the product and A to its left, so
    that product cell (i, j) sits at the intersection of A's row i and B's
    column j — which is what makes the entry reading legible as a crossing.
    That arrangement means the block is ``(k + n)`` cells wide and ``(k + m)``
    cells tall, and both grow with the *inner* dimension.

    Fixed offsets therefore cannot work, and did not: tuned against 2x2 they put
    B on top of the product at 4x4, which the library's own ``qc`` reported as
    six ``text_overlap`` errors. Solving for the cell size instead makes the
    layout correct for every shape this concept accepts rather than for the one
    it was tried against.
    """
    gap_cells = 0.9                      # the A|AB and B/AB separation, in cells
    cell = min(_MM_CELL_MAX,
               _MM_BAND[0] / (k + n + gap_cells),
               _MM_BAND[1] / (k + m + gap_cells))
    gap = gap_cells * cell
    stride = k * cell + gap              # B's rows plus the gap; A's cols plus it

    # Centre the whole block: solved rather than nudged, so no shape drifts off
    # one edge while another sits central.
    x = ((k + 1 - n) * cell + gap) / 2.0
    y = _MM_CENTRE_Y + ((k + m - 1) * cell + gap) / 2.0

    b_at = (x, y)
    out_at = (x, y - stride)
    a_at = (x - stride, y - stride)
    return cell, a_at, b_at, out_at


def _matmul_views_scene(plan: AnimationPlan) -> str:
    """A @ B, animated under one of four readings of the same product.

    The arithmetic is run here and the *result of running it* is what gets
    emitted — every cell value, every caption, every highlighted index is a
    computed constant. That is the rule ``examples/README.md`` states for the
    dataflow scenes, applied to a lesson: a scene that computes what it shows
    cannot drift from it, and a view whose own rule fails to reproduce ``A @ B``
    raises out of :func:`check_view` before a frame is drawn rather than
    teaching a procedure that does not work.

    Every text swap is a ``FadeTransform``, never a ``Transform``. The note in
    ``examples/README.md`` is the reason: ``Transform`` zips the two mobjects'
    glyph families, so ``"0" -> "16"`` raises rather than animating, and both
    the captions and the accumulating cells here change digit count constantly.
    Zero-padding is the fix that note recommends, but ``02`` in a matrix cell is
    a lie about the number, so the structure-agnostic transform is the right one.
    """
    params = plan.parameters or {}
    a = coerce_grid(params.get("a")) or ((1.0, 2.0), (3.0, 4.0))
    b = coerce_grid(params.get("b")) or ((0.0, 1.0), (1.0, 1.0))
    if shape(a)[1] != shape(b)[0]:
        # Non-conforming shapes have no product to animate. The precondition
        # check reports this; the builder still needs something to draw.
        b = tuple(tuple(1.0 if i == j else 0.0 for j in range(shape(a)[1]))
                  for i in range(shape(a)[1]))

    view = str(params.get("view") or "entry").lower()
    if view not in VIEWS:
        view = "entry"

    product = check_view(a, b, view)      # raises rather than emitting a lie
    steps = steps_for(a, b, view)
    (m, k), (_, n) = shape(a), shape(b)

    cell, a_at, b_at, out_at = _matmul_layout(m, k, n)
    # Type scales with the cell, or a 4x4's digits swim in their boxes while a
    # 2x2's overflow them. Clamped at both ends: below 15 it is unreadable at
    # the width a video gives it, above 34 it crowds the box's own stroke.
    font = max(15, min(34, int(round(34 * cell))))

    def literal(grid):
        return "[%s]" % ", ".join(
            "[%s]" % ", ".join(repr(fmt(v)) for v in row) for row in grid)

    L = []
    L.append("class GeneratedScene(Scene):")
    L.append("    def construct(self):")
    L.append("        cells = {}")
    L.append("")
    L.append("        def _grid(name, values, at, colour, shown):")
    L.append("            g = VGroup()")
    L.append("            for i, row in enumerate(values):")
    L.append("                for j, value in enumerate(row):")
    L.append("                    box = Rectangle(width=%r, height=%r, "
             "stroke_width=1.5, color=colour)" % (cell, cell))
    L.append("                    box.move_to([at[0] + j * %r, at[1] - i * %r, 0])"
             % (cell, cell))
    L.append("                    label = _t(value, font_size=%d, color=C_FG)"
             ".move_to(box.get_center())" % font)
    L.append("                    # The product's numbers exist from the start but")
    L.append("                    # stay invisible until the step that derives them.")
    L.append("                    if not shown:")
    L.append("                        label.set_opacity(0)")
    L.append("                    cells[(name, i, j)] = [box, label]")
    L.append("                    g.add(box, label)")
    L.append("            return g")
    L.append("")
    L.append("        def _put(name, i, j, value):")
    L.append("            \"\"\"Replace a cell's number, and keep `cells` pointing at it.")
    L.append("")
    L.append("            FadeTransform removes the source from the scene, so the")
    L.append("            entry must be rebound or the next step animates a mobject")
    L.append("            that is no longer drawn.")
    L.append("            \"\"\"")
    L.append("            box, old = cells[(name, i, j)]")
    L.append("            new = _t(value, font_size=%d, color=C_DONE)"
             ".move_to(box.get_center())" % font)
    L.append("            cells[(name, i, j)] = [box, new]")
    L.append("            return FadeTransform(old, new)")
    L.append("")
    # The outer reading *accumulates* into the product; the other three
    # partition it. That is the one structural difference between the views, and
    # it decides what the product grid starts as: an accumulating scene opens at
    # zero and counts up, so seeding it with the finished product would show the
    # answer for a frame before the first rank-1 term replaced it. A
    # partitioning scene seeds the real values and reveals them cell by cell,
    # because no later step revisits one.
    accumulating = view == "outer"
    opening = (tuple(tuple(0.0 for _ in range(n)) for _ in range(m))
               if accumulating else product)

    L.append("        A = _grid('A', %s, %r, C_FLOW, True)" % (literal(a), a_at))
    L.append("        B = _grid('B', %s, %r, C_HOLD, True)" % (literal(b), b_at))
    L.append("        P = _grid('P', %s, %r, C_DONE, %s)"
             % (literal(opening), out_at, accumulating))
    L.append("        A_tag = _t(\"A\", font_size=26, color=C_FLOW)"
             ".next_to(A, LEFT, buff=0.22)")
    L.append("        B_tag = _t(\"B\", font_size=26, color=C_HOLD)"
             ".next_to(B, LEFT, buff=0.22)")
    L.append("        P_tag = _t(\"AB\", font_size=26, color=C_DONE)"
             ".next_to(P, RIGHT, buff=0.22)")

    heading = {
        "entry": "AB entry by entry",
        "column": "AB one column at a time",
        "row": "AB one row at a time",
        "outer": "AB as a sum of rank-1 terms",
    }[view]
    L.append("        title = _t(%r, font_size=34).to_edge(UP)" % heading)
    L.append("        title.add_background_rectangle(opacity=0.9)")

    beat = _BeatKeys()
    L.append("        _beat(self, %s, Write(title), FadeIn(A), FadeIn(B), FadeIn(P),"
             " Write(A_tag), Write(B_tag), Write(P_tag))" % beat.next())

    running = [[0.0] * n for _ in range(m)]

    for index, step in enumerate(steps):
        reads = (["cells[('A', %d, %d)][0]" % (i, j) for i, j in step.a_cells]
                 + ["cells[('B', %d, %d)][0]" % (i, j) for i, j in step.b_cells])
        L.append("        read_%d = VGroup(%s)" % (index, ", ".join(reads)))
        L.append("        cap_%d = _t(%r, font_size=24, color=C_MUTED).to_edge(DOWN)"
                 % (index, step.caption))
        L.append("        cap_%d.add_background_rectangle(opacity=0.85)" % index)

        if accumulating:
            for i, row in enumerate(step.contribution):
                for j, value in enumerate(row):
                    running[i][j] += value
            writes = ["_put('P', %d, %d, %r)" % (i, j, fmt(running[i][j]))
                      for i in range(m) for j in range(n)]
        else:
            writes = ["cells[('P', %d, %d)][1].animate.set_opacity(1)" % (i, j)
                      for i, j in step.out_cells]

        swap = ("Write(cap_0)" if index == 0
                else "FadeTransform(cap_%d, cap_%d)" % (index - 1, index))
        L.append("        _beat(self, %s, %s, Indicate(read_%d, color=C_WARN), %s)"
                 % (beat.next(), swap, index, ", ".join(writes)))

    closing = {
        "entry": "each entry: one row of A meets one column of B",
        "column": "A acts on each column of B, one column at a time",
        "row": "each row of AB is a blend of the rows of B",
        "outer": "%d rank-1 terms, added — the reading that shards across devices" % k,
    }[view]
    L.append("        done = _t(%r, font_size=26, color=C_DEEP).to_edge(DOWN)" % closing)
    L.append("        done.add_background_rectangle(opacity=0.9)")
    L.append("        _beat(self, %s, FadeTransform(cap_%d, done))"
             % (beat.next(), len(steps) - 1))
    L.append("        self.wait(1)")
    return "\n".join(L)


#: Concept -> builder within the linear-algebra topic. Mirrors the calculus and
#: trig dispatchers; the topic's generic form is the single-map scene.
_LINALG_CONCEPT_BUILDERS = {
    ConceptLinAlg.LINEAR_MAP: _linear_algebra_scene,
    ConceptLinAlg.MATMUL_VIEWS: _matmul_views_scene,
}


@scene_for(Topic.LINEAR_ALGEBRA)
def _linalg_scene(plan: AnimationPlan) -> str:
    builder = _LINALG_CONCEPT_BUILDERS.get(plan.concept, _linear_algebra_scene)
    return builder(plan)



