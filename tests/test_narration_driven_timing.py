"""Scenes follow the voice when told how long it is, and are unchanged when not.

The contract in one sentence: a measured narration length decides how long its
step runs, and a step with no measurement keeps exactly the timing it was
written with. The second half is what lets builders be converted one at a time.
"""

from __future__ import annotations

import ast

import pytest

from straightedge.calculus import ConceptCalculus
from straightedge.conics import ConceptConic
from straightedge.trig import Concept as ConceptTrig
from straightedge.models import AnimationPlan, Topic
from straightedge.templates import scene_code_for


def _plan(concept=ConceptCalculus.RIEMANN_INTEGRAL, **parameters):
    return AnimationPlan(
        topic=Topic.CALCULUS, title_zh="标题", objective_zh="目标",
        english_prompt="prompt", concept=concept,
        parameters=parameters or {"expression": "x**2"},
    )


def _beats(n=6):
    return {f"b{i:02d}": 2.0 + i for i in range(1, n + 1)}


def _exec_preamble(code: str) -> dict:
    """Execute just the beat map and its two helpers.

    Narrower than running the whole preamble on purpose: the rest of it is
    Manim-dependent (``SOLID_HELPERS_SRC`` names colour constants at module
    scope) and stubbing that would mostly test the stubs. The helpers are
    ordinary functions, and what they ask of a scene is the entire contract — so
    those are what get run, on a host without the render extra, which is where
    they are most likely to be run.
    """
    wanted = {"_beat", "_beat_stretch"}
    body = []
    for node in ast.parse(code).body:
        if isinstance(node, ast.FunctionDef) and node.name in wanted:
            body.append(node)
        elif isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "BEAT_SECONDS" for t in node.targets
        ):
            body.append(node)
    assert len(body) == 3, f"expected BEAT_SECONDS and both helpers, got {len(body)}"

    # One namespace for globals and locals: with two, BEAT_SECONDS lands in
    # locals while the helper bodies resolve it as a global, and every call
    # raises NameError.
    namespace: dict = {"__builtins__": __builtins__, "linear": object()}
    exec(compile(ast.Module(body=body, type_ignores=[]), "<helpers>", "exec"), namespace)
    return namespace


class RecordingScene:
    """Captures what the helpers ask a scene to do."""

    def __init__(self):
        self.calls: list[tuple] = []

    def play(self, *anims, **kwargs):
        self.calls.append(("play", kwargs.get("run_time")))

    def wait(self, seconds):
        self.calls.append(("wait", seconds))

    def total(self):
        return sum(t for _, t in self.calls if t)


# ------------------------------------------------------------------ codegen

class TestGeneratedCode:

    def test_measured_durations_reach_the_scene(self):
        code = scene_code_for(_plan(), beat_seconds={"b01": 3.5})
        assert "BEAT_SECONDS = {'b01': 3.5}" in code

    def test_omitting_durations_leaves_an_empty_map(self):
        assert "BEAT_SECONDS = {}" in scene_code_for(_plan())

    @pytest.mark.parametrize("beats", [None, {"b01": 4.0}])
    def test_the_scene_parses_either_way(self, beats):
        ast.parse(scene_code_for(_plan(), beat_seconds=beats))

    def test_a_converted_builder_uses_the_helpers(self):
        code = scene_code_for(_plan())
        assert '_beat(self, "b01"' in code
        assert '_beat_stretch(self, "b04"' in code, "the sweep should occupy its sentence"


# ---------------------------------------------------------- converted scenes

def _conic_plan():
    return AnimationPlan(
        topic=Topic.CONIC, title_zh="椭圆", objective_zh="焦点",
        english_prompt="ellipse", concept=ConceptConic.ELLIPSE_FOCI,
    )


def _beat_calls(code: str) -> list[tuple[str, str]]:
    """``(helper, beat key)`` for every timed step, in source order.

    Parsed rather than grepped. A generated call may wrap across lines, so
    substring matching silently fails to find a step that is present — and it
    equally finds one that is only mentioned in a comment.
    """
    found: list[tuple[int, str, str]] = []
    for node in ast.walk(ast.parse(code)):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        if node.func.id not in {"_beat", "_beat_stretch"}:
            continue
        if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
            found.append((node.lineno, node.func.id, node.args[1].value))
    return [(helper, key) for _, helper, key in sorted(found)]


def _without_comments(code: str) -> str:
    """Source as the interpreter sees it — comments dropped.

    A rationale comment naming the thing it replaced would otherwise satisfy an
    assertion that the thing is gone.
    """
    return ast.unparse(ast.parse(code))


class TestEllipseFociIsConverted:
    """The first conic on the shorts path, so the first one that has to follow
    the voice rather than its own hardcoded run times.
    """

    def test_every_step_is_on_the_timeline(self):
        """No step left with a hardcoded run time — that is what conversion means."""
        keys = [key for _, key in _beat_calls(scene_code_for(_conic_plan()))]
        assert keys == [f"b{i:02d}" for i in range(1, 9)]

    def test_the_sweep_stretches_rather_than_finishing_early(self):
        """P must still be travelling while the narrator says the sum holds.
        A plain `_beat` would race the trace and hold a frozen frame.
        """
        calls = dict((key, helper) for helper, key in _beat_calls(scene_code_for(_conic_plan())))
        assert calls["b07"] == "_beat_stretch"

    def test_only_the_sweep_stretches(self):
        """Stretching a reveal spreads a two-second `Write` over its whole beat,
        which reads as the text being drawn in slow motion.
        """
        stretched = [key for helper, key in _beat_calls(scene_code_for(_conic_plan()))
                     if helper == "_beat_stretch"]
        assert stretched == ["b07"]

    def test_the_trace_is_linear_on_the_unmeasured_path_too(self):
        """`_beat_stretch` forces `rate_func=linear` only when it has a measured
        length; its fallback calls `play` without one. Carrying the rate func on
        the animation keeps a constant-speed locus in both branches — an eased
        trace visibly slows at the ends, which reads as the point hesitating.
        """
        assert "t.animate(rate_func=linear)" in _without_comments(scene_code_for(_conic_plan()))

    def test_the_distance_labels_are_not_parked_in_a_frame_corner(self):
        """`to_corner(DL)` put them where the conclusion lives once the frame is
        narrow: they collided in 9:16 and looked stranded in 16:9.
        """
        code = _without_comments(scene_code_for(_conic_plan()))
        assert "to_corner(DL)" not in code
        assert "legend.next_to(title, DOWN" in code

    def test_the_legend_is_cleared_before_the_conclusion_lands(self):
        assert "FadeOut(legend)" in _without_comments(scene_code_for(_conic_plan()))

    @pytest.mark.parametrize("beats", [None, {f"b{i:02d}": 2.0 for i in range(1, 9)}])
    def test_the_scene_parses_either_way(self, beats):
        ast.parse(scene_code_for(_conic_plan(), beat_seconds=beats))

    def test_the_scene_runs_as_long_as_its_narration(self):
        """Replays the builder's own beat sequence against the real helpers."""
        beats = {f"b{i:02d}": 1.0 + i for i in range(1, 9)}
        ns = _exec_preamble(scene_code_for(_conic_plan(), beat_seconds=beats))
        scene = RecordingScene()
        for index in range(1, 9):
            key = f"b{index:02d}"
            if key == "b07":
                ns["_beat_stretch"](scene, key, object(), run_time=5.5)
            else:
                ns["_beat"](scene, key, object())
        assert scene.total() == pytest.approx(sum(beats.values()))


# ------------------------------------------------------------------ helpers

class TestBeatHelper:

    def _helpers(self, beats):
        return _exec_preamble(scene_code_for(_plan(), beat_seconds=beats))

    def test_a_beat_lasts_exactly_its_narration(self):
        ns = self._helpers({"b01": 5.0})
        scene = RecordingScene()
        ns["_beat"](scene, "b01", object())
        assert scene.total() == pytest.approx(5.0)

    def test_the_reveal_finishes_early_and_the_rest_is_held(self):
        """Narration should play over a settled frame, not a still-moving one."""
        ns = self._helpers({"b01": 5.0})
        scene = RecordingScene()
        ns["_beat"](scene, "b01", object(), reveal=1.4)
        assert scene.calls[0] == ("play", 1.4)
        assert scene.calls[1] == ("wait", pytest.approx(3.6))

    def test_an_unmeasured_beat_keeps_its_written_timing(self):
        """The property that lets builders convert one at a time."""
        ns = self._helpers({})
        scene = RecordingScene()
        ns["_beat"](scene, "b02", object(), run_time=2)
        assert scene.calls == [("play", 2)]

    def test_an_unmeasured_beat_with_no_written_timing_is_left_alone(self):
        ns = self._helpers({})
        scene = RecordingScene()
        ns["_beat"](scene, "b01", object())
        assert scene.calls == [("play", None)]

    def test_a_beat_with_no_animation_simply_holds(self):
        ns = self._helpers({"b09": 2.5})
        scene = RecordingScene()
        ns["_beat"](scene, "b09")
        assert scene.calls == [("wait", 2.5)]

    def test_a_short_beat_is_not_stretched_into_a_negative_hold(self):
        """A one-second clip must not ask for a 1.4s reveal and a -0.4s wait."""
        ns = self._helpers({"b01": 1.0})
        scene = RecordingScene()
        ns["_beat"](scene, "b01", object(), reveal=1.4)
        assert all(t is None or t >= 0 for _, t in scene.calls)
        assert scene.total() == pytest.approx(1.0)


class TestStretchHelper:

    def _helpers(self, beats):
        return _exec_preamble(scene_code_for(_plan(), beat_seconds=beats))

    def test_a_sweep_occupies_its_whole_sentence(self):
        ns = self._helpers({"b04": 6.0})
        scene = RecordingScene()
        ns["_beat_stretch"](scene, "b04", object())
        assert scene.calls == [("play", pytest.approx(6.0))]

    def test_a_tail_holds_the_final_state(self):
        ns = self._helpers({"b04": 6.0})
        scene = RecordingScene()
        ns["_beat_stretch"](scene, "b04", object(), tail=1.5)
        assert scene.calls[0] == ("play", pytest.approx(4.5))
        assert scene.calls[1] == ("wait", pytest.approx(1.5))
        assert scene.total() == pytest.approx(6.0)

    def test_an_unmeasured_sweep_keeps_its_written_timing(self):
        ns = self._helpers({})
        scene = RecordingScene()
        ns["_beat_stretch"](scene, "b04", object(), run_time=2.5)
        assert scene.calls == [("play", 2.5)]


# ------------------------------------------------------------ the whole act

def test_a_converted_scene_runs_as_long_as_its_narration():
    """The property the lane depends on: video length follows the voice."""
    beats = _beats()
    ns = _exec_preamble(scene_code_for(_plan(), beat_seconds=beats))
    scene = RecordingScene()
    ns["_beat"](scene, "b01", object())
    ns["_beat"](scene, "b02", object(), run_time=2)
    ns["_beat"](scene, "b03", object())
    ns["_beat_stretch"](scene, "b04", object())
    ns["_beat"](scene, "b05", object())
    ns["_beat"](scene, "b06", object())
    assert scene.total() == pytest.approx(sum(beats.values()))


# --------------------------------------------------------- reaching the file

class TestWriteSceneCarriesTheMeasurements:
    """``write_scene`` is the only writer, so it is the only way in.

    Every test above calls ``scene_code_for`` directly and passes whatever it
    likes. The renderer does not — it goes through ``write_scene``, which dropped
    the argument. The timing feature was fully implemented, fully tested, and
    unreachable by the one caller that actually renders.
    """

    def test_measurements_reach_the_written_scene(self, tmp_path):
        from straightedge.renderer import write_scene

        path = write_scene(_plan(), tmp_path, beat_seconds={"b01": 4.25})
        assert "4.25" in path.read_text(encoding="utf-8")

    def test_an_unmeasured_scene_still_writes_an_empty_map(self, tmp_path):
        """The fallback the preamble relies on: absent means 'keep your timing'."""
        from straightedge.renderer import write_scene

        source = write_scene(_plan(), tmp_path).read_text(encoding="utf-8")
        assert "BEAT_SECONDS = {}" in source


# ------------------------------------------------- every shipped concept obeys

class TestEveryReachableConceptSpendsItsNarration:
    """A builder that never calls ``_beat`` ignores the voice entirely.

    The per-builder fallback is deliberate — it is what lets builders be
    converted one at a time — but it is invisible: an unconverted builder
    renders cleanly, passes every geometric gate, and then has a full-length
    narration muxed over a short picture. The first real render of this lane
    produced 13s of animation under 69.5s of voice, and nothing reported it.

    So the fallback stays for builders nothing can reach, and this test pins the
    ones a job *can* reach. A new concept wired into the catalog without beat
    conversion fails here rather than in a delivered video.
    """

    CONCEPTS = [
        (Topic.CALCULUS, ConceptCalculus.DERIVATIVE_TANGENT, {"expression": "x ** 2"}),
        (Topic.CALCULUS, ConceptCalculus.RIEMANN_INTEGRAL, {"expression": "x ** 2"}),
        (Topic.CALCULUS, ConceptCalculus.FTC_ACCUMULATION, {"expression": "x ** 2"}),
        (Topic.CALCULUS, ConceptCalculus.TAYLOR_SERIES, {"function": "sin"}),
        (Topic.CONIC, ConceptConic.ELLIPSE_FOCI, {"conic": "ellipse"}),
        (Topic.TRIG, ConceptTrig.UNIT_CIRCLE_TO_SINE, {}),
        # Both spec shapes, because the tan branch skips the morph and so
        # numbers every later beat differently.
        (Topic.TRIG, ConceptTrig.GRAPH_TRANSFORM,
         {"trig_spec": {"func": "sin", "A": 2.0, "omega": 1.0, "phi": 0.0, "k": 0.0}}),
        (Topic.TRIG, ConceptTrig.GRAPH_TRANSFORM,
         {"trig_spec": {"func": "tan", "A": 1.0, "omega": 1.0, "phi": 0.0, "k": 0.0}}),
    ]

    @pytest.mark.parametrize("topic,concept,params", CONCEPTS)
    def test_the_builder_spends_beats(self, topic, concept, params):
        code = scene_code_for(AnimationPlan(
            topic=topic, title_zh="标题", objective_zh="目标",
            english_prompt="prompt", concept=concept, parameters=params,
        ))
        construct = code.split("def construct(self):", 1)[1]
        assert "_beat(" in construct or "_beat_stretch(" in construct, (
            f"{concept} never spends a beat, so its animation cannot follow "
            f"the narration"
        )

    @pytest.mark.parametrize("topic,concept,params", CONCEPTS)
    def test_no_raw_play_survives_in_the_body(self, topic, concept, params):
        """A single missed ``self.play`` is a step the voice cannot stretch.

        Checked on the construct body only: the preamble's helpers call
        ``scene.play`` by design, which is how a beat is spent at all.
        """
        code = scene_code_for(AnimationPlan(
            topic=topic, title_zh="标题", objective_zh="目标",
            english_prompt="prompt", concept=concept, parameters=params,
        ))
        construct = code.split("def construct(self):", 1)[1]
        assert "self.play(" not in construct, (
            f"{concept} still has an unconverted self.play; it will run on its "
            f"written timing while the narration continues past it"
        )
