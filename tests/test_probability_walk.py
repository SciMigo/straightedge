"""probability/random_walk_exits: a real walk, the same walk every render."""
from __future__ import annotations

import inspect
import re

import pytest

from straightedge import build_plan, list_templates, plan_from_template, scene_code_for, validate
from straightedge import probability as P
from straightedge.probability import (ProbabilityError, WalkModel, choose_showcase, coerce_model,
                                      path_violations, ruin_probability, tally_paths, walk_claims,
                                      walk_path)

TEMPLATE = "probability/random_walk_exits"
BEATS = {"b01": 9.1, "b02": 13.0, "b03": 10.9, "b04": 12.0, "b05": 14.2}
ENGINE_BEAT_RE = r'_beat\w*\(\s*self,\s*"(b\d+)"'   # mini_lecture count_scene_beats


# ------------------------------------------------------------------ the walk


def test_walk_is_an_absorbed_unit_step_walk():
    for seed in range(200):
        path = walk_path(4, 10, 0.5, seed)
        assert path_violations(path, 4, 10) == []


def test_same_seed_same_walk():
    assert walk_path(4, 10, 0.5, 11) == walk_path(4, 10, 0.5, 11)


def test_a_runaway_walk_is_reported_not_hung():
    assert walk_path(50, 100, 0.5, 1, cap=5) is None


@pytest.mark.parametrize("bad,why", [
    ([4, 6, 5], "moves by 2"),
    ([4, 5, 10], "moves by 5"),
    ([3, 2, 1, 0, 1, 0], "touches an end"),
    ([4, 5, 6], "not absorbing"),
    ([5, 4, 3, 2, 1, 0], "starts at 5"),
])
def test_path_violations_name_the_fault(bad, why):
    assert any(why in v for v in path_violations(bad, 4, 10))


# ------------------------------------------------------------- showcase choice


@pytest.mark.parametrize("side,end", [("zero", 0), ("top", 10)])
def test_showcase_honours_the_requested_exit(side, end):
    _seed, path, _ok = choose_showcase(4, 10, 0.5, 7, side, 34.5, 0.45, 0.9)
    assert path[-1] == end


def test_showcase_pace_lands_in_the_requested_band():
    _seed, path, ok = choose_showcase(4, 10, 0.5, 7, "any", 34.5, 0.45, 0.9)
    per = 34.5 / (len(path) - 1)
    assert ok and 0.45 <= per <= 0.9


def test_showcase_wanders():
    _seed, path, _ok = choose_showcase(4, 10, 0.5, 7, "any", 34.5, 0.45, 0.9, min_turns=4)
    turns = sum(1 for a, b, c in zip(path, path[1:], path[2:]) if (b - a) != (c - b))
    assert turns >= 4


def test_impossible_pace_falls_back_to_a_true_walk():
    """A pace no walk can meet still yields a genuine walk, flagged out of band."""
    _seed, path, ok = choose_showcase(4, 10, 0.5, 7, "any", 0.5, 0.45, 0.9, tries=300)
    assert not ok
    assert path_violations(path, 4, 10) == []


def test_tally_frequency_approaches_the_ruin_probability():
    runs = tally_paths(4, 10, 0.5, 7, 120)
    share = sum(1 for r in runs if r[-1] == 0) / len(runs)
    assert abs(share - ruin_probability(4, 10, 0.5)) < 0.12


def test_ruin_probability_matches_the_closed_forms():
    assert ruin_probability(4, 10, 0.5) == pytest.approx(0.6)
    assert ruin_probability(100, 200, 0.51) == pytest.approx(0.017977, abs=1e-6)


# ------------------------------------------------------------------ the model


def test_defaults_are_drawable():
    facts = walk_claims(coerce_model({}))
    assert facts["tally_zero"] + facts["tally_top"] == 40
    assert facts["exit"] in ("zero", "top")


@pytest.mark.parametrize("params,param", [
    ({"start": 0}, "start"),
    ({"start": 10}, "start"),
    ({"n": 2}, "n"),
    ({"n": 21}, "n"),
    ({"p": 0.99}, "p"),
    ({"p": "a lot"}, "p"),
    ({"n": True}, "n"),
    ({"n": 7.5}, "n"),
    ({"exit": "sideways"}, "exit"),
    ({"runs": 3}, "runs"),
    ({"step_seconds": (0.9, 0.45)}, "step_seconds"),
    ({"phases": ["ends", "walk", "absorb"]}, "phases"),
    ({"phases": ["walk", "tally"]}, "phases"),
    ({"phases": ["walk", "absorb", "ends"]}, "phases"),
    ({"phases": ["walk", "tally", "absorb"]}, "phases"),
    ({"phases": ["walk", "walk", "absorb"]}, "phases"),
    ({"phases": ["walk", "absorb", "dance"]}, "phases"),
])
def test_refusals_name_the_parameter(params, param):
    with pytest.raises(ProbabilityError) as err:
        coerce_model(params)
    assert err.value.param == param


def test_runs_are_not_checked_without_a_tally():
    assert coerce_model({"phases": ["walk", "absorb"], "runs": 0}).runs == 0


def test_phases_accept_a_comma_string():
    assert coerce_model({"phases": "walk, absorb"}).phases == ("walk", "absorb")


# ----------------------------------------------------------------- the scene


def _scene(params, beats=BEATS):
    return scene_code_for(plan_from_template(TEMPLATE, params), beat_seconds=beats)


def test_scene_compiles_and_has_one_beat_per_phase():
    code = _scene({})
    compile(code, "scene", "exec")
    assert sorted(set(re.findall(ENGINE_BEAT_RE, code))) == ["b01", "b02", "b03", "b04", "b05"]


def test_fewer_phases_fewer_beats():
    code = _scene({"phases": ["walk", "absorb"]}, beats={"b01": 8.0, "b02": 6.0})
    assert sorted(set(re.findall(ENGINE_BEAT_RE, code))) == ["b01", "b02"]
    assert "tally_paths(" in code          # helper present; no tally drawn
    assert '"tally" in PHASES' in code


def test_scene_carries_the_checked_walk_functions_verbatim():
    """One copy of the logic: the scene runs the source the checks ran."""
    code = _scene({})
    for fn in (walk_path, choose_showcase, tally_paths):
        assert inspect.getsource(fn) in code


def test_scene_picks_the_walk_the_checks_verified():
    """Run the scene's own helper code and compare with walk_claims."""
    code = _scene({})
    helpers = code[code.index("def walk_path("):code.index("class GeneratedScene")]
    ns: dict = {}
    exec("import random\n" + helpers, ns)
    m = coerce_model({})
    facts = walk_claims(m, BEATS)
    seed, path, _ok = ns["choose_showcase"](m.start, m.n, m.p, m.seed, m.exit,
                                            facts["walking_seconds"], *m.step_seconds,
                                            min_turns=P.MIN_TURNS, tries=P.SEED_TRIES,
                                            cap=P.PATH_CAP)
    assert seed == facts["seed_used"] and len(path) - 1 == facts["steps"]


def test_invalid_params_render_a_refusal_not_a_walk():
    code = _scene({"start": 0})
    assert "Nothing to draw" in code and "choose_showcase" not in code


def test_labels_are_escaped():
    compile(_scene({"high_label": 'say "all"', "low_label": "back\\slash"}), "scene", "exec")


# ------------------------------------------------------------------ catalog


def test_listed_with_its_parameter_names():
    t = [x for x in list_templates() if x.id == TEMPLATE][0]
    assert {"n", "start", "p", "phases", "runs", "exit"} <= set(t.params)


def test_a_chinese_prompt_routes_here():
    assert build_plan("画一个赌徒破产的随机游走").concept == TEMPLATE


def test_preconditions_reject_at_submit_time():
    violations = validate(plan_from_template(TEMPLATE, {"start": 10}))
    assert violations and "start" in str(violations[0])


def test_walk_model_beats():
    assert WalkModel().beats == 5


# ------------------------------------------------------- absorb_at, captions


def test_absorb_at_moves_the_moment_of_absorption():
    early = walk_claims(coerce_model({"absorb_at": 0.2}), BEATS)["walking_seconds"]
    late = walk_claims(coerce_model({"absorb_at": 0.8}), BEATS)["walking_seconds"]
    assert late - early == pytest.approx(0.6 * BEATS["b04"])


@pytest.mark.parametrize("value", [0.05, 0.95, "soon"])
def test_absorb_at_out_of_range_is_refused(value):
    with pytest.raises(ProbabilityError) as err:
        coerce_model({"absorb_at": value})
    assert err.value.param == "absorb_at"


def test_captions_are_kept_in_phase_order():
    m = coerce_model({"captions": {"tally": "<i>R</i><sub><i>i</i></sub> = share", "walk": "a walk"}})
    assert [ph for ph, _ in m.captions] == ["walk", "tally"]


@pytest.mark.parametrize("captions", [
    {"dance": "x"},
    {"walk": "<script>x</script>"},
    {"walk": "a < b"},
    {"walk": "salt & pepper"},
    {"walk": "<i>unclosed"},
    {"walk": "<i><b>crossed</i></b>"},
    ["walk", "x"],
])
def test_bad_captions_are_refused_before_a_render(captions):
    with pytest.raises(ProbabilityError) as err:
        coerce_model({"captions": captions})
    assert err.value.param == "captions"


def test_escaped_entities_are_allowed():
    assert coerce_model({"captions": {"walk": "salt &amp; pepper, a &lt; b"}}).captions


def test_captions_reach_the_scene():
    code = _scene({"captions": {"tally": "<i>R</i><sub><i>i</i></sub> = share"}})
    compile(code, "scene", "exec")
    assert "MarkupText" in code and "<sub>" in code
