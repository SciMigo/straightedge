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


# =================================================================== additions
#
# Everything below covers parameters added after the first release. The first
# group pins the promise they were added under: a plan that sets none of them
# gets, byte for byte, the scene that release wrote — so it renders the frames
# it always rendered.

import hashlib  # noqa: E402

from straightedge.cli import _read_beat_seconds  # noqa: E402
from straightedge.errors import InputFileError  # noqa: E402
from straightedge.probability import (Cue, cue_seconds, cue_time, expected_steps,  # noqa: E402
                                      renewal_blocks, renewal_escape, showcase_of_length,
                                      walking_seconds)
from straightedge.probability_scene import random_walk_scene  # noqa: E402

#: sha256 of ``random_walk_scene`` for four plans, as the first release wrote
#: them. If one of these changes, an existing plan now renders differently: make
#: the new behaviour opt-in instead, or say so in the changelog and update the
#: hash on purpose.
LEGACY_SCENES = [
    ({}, "6214930d66a3676ff585bfa33f78c6aaa0753d40ffc0afa89a9fb3f62b5afe75"),
    ({"phases": ["walk", "absorb"]},
     "6b4bb001de6e60262a07f69233b4110240290419637ccd1b5a0a7619272fbaeb"),
    ({"n": 6, "start": 3, "seed": 3, "runs": 120, "step_seconds": [1.0, 3.0],
      "phases": ["walk", "ends", "absorb", "tally"], "absorb_at": 0.1, "low_label": "3 below",
      "high_label": "3 above", "title": "How many steps?",
      "captions": {"walk": "fair coin", "tally": "<i>k</i><sup>2</sup>"}},
     "2baa616036ff1002941345d030c58c750510db44d05f4d28d70c09bb37fc5145"),
    ({"p": 0.6, "exit": "top", "phases": "walk, steps, absorb, tally", "runs": 30},
     "ff95eb5db387d6678e0e9b69a443d5780da3d1f57b11e3361c7cd0ec4578baeb"),
]


@pytest.mark.parametrize("params,digest", LEGACY_SCENES)
def test_a_plan_using_no_new_parameter_gets_the_first_release_scene(params, digest):
    src = random_walk_scene(coerce_model(params))
    assert hashlib.sha256(src.encode()).hexdigest() == digest


def test_defaults_leave_every_new_feature_out_of_the_scene():
    code = _scene({})
    for marker in ("cue_seconds", "renewal_blocks", "showcase_of_length", "CARDS =",
                   "place_row", "STEP_TICK", "X_TARGET", "BIG ="):
        assert marker not in code


# ---------------------------------------------------------------------- cues

STARTS, SPANS = [0.0, 10.0, 25.0], [10.0, 15.0, 20.0]


def test_a_measured_sentence_start_is_used():
    beats = {"b02.s3": 7.5}
    assert cue_seconds(STARTS, SPANS, beats, 1, 3, 0.0, None, 4) == 17.5


def test_an_unmeasured_sentence_falls_back_to_an_even_split():
    assert cue_seconds(STARTS, SPANS, {}, 1, 3, 0.0, None, 4) == 10.0 + 15.0 * 2 / 4


def test_at_is_a_fraction_of_the_phase_and_offset_shifts_it():
    assert cue_seconds(STARTS, SPANS, {}, 2, None, -1.0, 0.5, 1) == 25.0 + 10.0 - 1.0


def test_cues_are_clamped_to_the_scene():
    assert cue_seconds(STARTS, SPANS, {}, 0, None, -5.0, None, 1) == 0.0
    assert cue_seconds(STARTS, SPANS, {}, 2, None, 25.0, 1.0, 1) == 45.0


@pytest.mark.parametrize("raw,param", [
    ({"phase": "dance"}, "labels_until"),
    ({"phase": "walk", "sentence": 0}, "labels_until"),
    ({"phase": "walk", "sentence": 1, "at": 0.5}, "labels_until"),
    ({"phase": "walk", "at": 1.5}, "labels_until"),
    ({"phase": "walk", "offset": 99}, "labels_until"),
    ({"phase": "walk", "when": 3}, "labels_until"),
    (7, "labels_until"),
])
def test_bad_cues_are_refused_with_the_parameter(raw, param):
    with pytest.raises(ProbabilityError) as err:
        coerce_model({"labels_until": {"ends": raw}})
    assert err.value.param == param


def test_the_scene_resolves_cues_with_the_checked_function():
    code = _scene({"labels_until": {"ends": {"phase": "absorb", "sentence": 2}}})
    assert inspect.getsource(cue_seconds) in code


def test_the_cli_accepts_sentence_starts_including_zero(tmp_path):
    f = tmp_path / "beats.json"
    f.write_text('{"b01": 4.0, "b01.s1": 0, "b01.s2": 1.9}')
    assert _read_beat_seconds(f) == {"b01": 4.0, "b01.s1": 0.0, "b01.s2": 1.9}
    f.write_text('{"b01": 4.0, "b01.s2": -1}')
    with pytest.raises(InputFileError):
        _read_beat_seconds(f)
    f.write_text('{"b01": 0}')
    with pytest.raises(InputFileError):
        _read_beat_seconds(f)


# --------------------------------------------------------- absorb on a sentence

V1 = {"n": 6, "start": 3, "seed": 3, "runs": 120, "step_seconds": [0.6, 3.0],
      "phases": ["walk", "ends", "absorb", "renewal", "tally"]}
V1_BEATS = {"b01": 10.0, "b02": 8.0, "b03": 4.0, "b04": 24.0, "b05": 20.0,
            "b03.s1": 0.8, "b04.s1": 0.0, "b04.s2": 5.0, "b04.s3": 11.0,
            "b05.s1": 0.0, "b05.s2": 4.0, "b05.s3": 12.0}


def test_absorb_at_a_sentence_puts_the_hit_there():
    m = coerce_model(dict(V1, absorb_at={"sentence": 1, "offset": 0.3}))
    spans = P.spans_for(m, V1_BEATS)
    assert walking_seconds(m, spans, V1_BEATS) == pytest.approx(18.0 + 0.8 + 0.3)


def test_absorb_at_a_cue_past_its_phase_is_refused():
    m = coerce_model(dict(V1, absorb_at={"sentence": 1, "offset": 3.0}))
    with pytest.raises(ProbabilityError) as err:
        walk_claims(m, V1_BEATS)
    assert err.value.param == "absorb_at"


def test_absorb_at_must_name_the_absorb_phase():
    with pytest.raises(ProbabilityError) as err:
        coerce_model(dict(V1, absorb_at={"phase": "walk", "at": 0.5}))
    assert err.value.param == "absorb_at"


# ------------------------------------------------------- a walk of known length


def test_showcase_steps_fixes_the_walk_whatever_the_timing():
    m = coerce_model(dict(V1, showcase_steps=21))
    short = walk_claims(m, dict(V1_BEATS, b01=4.0))
    long = walk_claims(m, dict(V1_BEATS, b01=30.0))
    assert short["steps"] == long["steps"] == 21
    assert short["path"] == long["path"]


def test_showcase_of_length_is_a_true_walk_of_that_length():
    seed, path, _ok = showcase_of_length(3, 6, 0.5, 3, "any", 21, 20.0, 0.5, 2.0)
    assert len(path) - 1 == 21 and path_violations(path, 3, 6) == []
    assert path == walk_path(3, 6, 0.5, seed)


@pytest.mark.parametrize("steps", [2, 20, 1])
def test_impossible_lengths_are_refused_before_searching(steps):
    """From the middle of 0..6 every exit takes an odd number of steps, at least 3."""
    with pytest.raises(ProbabilityError) as err:
        coerce_model(dict(V1, showcase_steps=steps))
    assert err.value.param == "showcase_steps"


def test_a_length_no_seed_reaches_is_refused_by_the_claims():
    with pytest.raises(ProbabilityError) as err:
        walk_claims(coerce_model(dict(V1, showcase_steps=199)), V1_BEATS)
    assert err.value.param == "showcase_steps"


def test_the_scene_draws_the_walk_of_stated_length():
    code = _scene(dict(V1, showcase_steps=21), beats=V1_BEATS)
    helpers = code[code.index("def walk_path("):code.index("class GeneratedScene")]
    ns: dict = {}
    exec("import random\n" + helpers, ns)
    _seed, path, _ok = ns["showcase_of_length"](3, 6, 0.5, 3, "any", 21, 20.0, 0.6, 3.0)
    facts = walk_claims(coerce_model(dict(V1, showcase_steps=21)), V1_BEATS)
    assert path == facts["path"]


# --------------------------------------------------------------- renewal


def test_renewal_blocks_cut_at_each_return():
    #        start 3 -> 2 (first visit) -> 1 -> 2 -> 3 -> 4 -> 5 -> 6
    path = [3, 2, 1, 2, 3, 4, 5, 6]
    first, ends = renewal_blocks(path, (2, 4))
    assert first == 1 and ends == [3, 5, 7]


def test_a_walk_that_never_returns_has_no_blocks():
    assert renewal_blocks([3, 4, 5, 6], (2,)) == (None, [])


def test_from_one_away_a_pair_of_flips_escapes_one_time_in_four():
    assert str(renewal_escape(2, (2, 4), 6, 0.5)) == "1/4"
    assert str(renewal_escape(4, (2, 4), 6, 0.5)) == "1/4"


def test_renewal_escape_for_an_asymmetric_walk():
    # From 1 on 0..4 with renewal at {1}: down at once (q), or up to 2 and then
    # to 4 before 1 — gambler's ruin from 1 on 0..3 with r = q/p.
    p, r = 0.6, 0.4 / 0.6
    reach_top = (1 - r) / (1 - r ** 3)
    assert float(renewal_escape(1, (1,), 4, p)) == pytest.approx(0.4 + p * reach_top)


def test_expected_steps_is_i_times_j_for_a_fair_walk():
    for n in range(3, 12):
        for i in range(1, n):
            assert expected_steps(i, n, 0.5) == i * (n - i)


def test_renewal_facts_count_the_drawn_walk():
    facts = walk_claims(coerce_model(dict(V1, showcase_steps=21)), V1_BEATS)
    assert facts["renewal_first_steps"] == 1
    assert facts["renewal_blocks"] == 10 and set(facts["renewal_block_steps"]) == {2}
    assert facts["renewal_escape_exact"] == {2: "1/4", 4: "1/4"}
    assert facts["expected_steps"] == 9.0


@pytest.mark.parametrize("params,param", [
    ({"phases": ["walk", "renewal", "absorb"]}, "phases"),
    ({"renewal_states": [0, 2]}, "renewal_states"),
    ({"renewal_states": [2, 2]}, "renewal_states"),
    ({"renewal_states": "2"}, "renewal_states"),
    ({"renewal_cues": {"middle": "renewal"}}, "renewal_cues"),
    ({"renewal_text": {"count": "block {nope}"}}, "renewal_text"),
])
def test_renewal_refusals_name_the_parameter(params, param):
    with pytest.raises(ProbabilityError) as err:
        coerce_model(dict(V1, **params))
    assert err.value.param == param


def test_renewal_parameters_need_the_phase():
    with pytest.raises(ProbabilityError) as err:
        coerce_model({"renewal_states": [3]})
    assert err.value.param == "renewal_states"


def test_renewal_cues_out_of_order_are_refused():
    m = coerce_model(dict(V1, renewal_cues={"blocks": {"sentence": 3}, "done": {"sentence": 2}}))
    with pytest.raises(ProbabilityError) as err:
        walk_claims(m, V1_BEATS)
    assert err.value.param == "renewal_cues"


def test_renewal_states_the_walk_never_visits_are_refused():
    """Refused exactly when the drawn walk is absorbed without visiting them."""
    refused = accepted = 0
    for seed in range(40):
        m = coerce_model(dict(V1, seed=seed, exit="zero", renewal_states=[5]))
        path = walk_claims(coerce_model(dict(V1, seed=seed, exit="zero")), V1_BEATS)["path"]
        if 5 in path[:-1]:
            walk_claims(m, V1_BEATS)
            accepted += 1
        else:
            with pytest.raises(ProbabilityError) as err:
                walk_claims(m, V1_BEATS)
            assert err.value.param == "renewal_states"
            refused += 1
    assert refused and accepted


def test_the_renewal_scene_compiles_and_keeps_one_beat_per_phase():
    code = _scene(dict(V1, showcase_steps=21, renewal_text={"level": "one away"}), beats=V1_BEATS)
    compile(code, "scene", "exec")
    assert sorted(set(re.findall(ENGINE_BEAT_RE, code))) == ["b01", "b02", "b03", "b04", "b05"]
    assert inspect.getsource(renewal_blocks) in code


# ------------------------------------------------------------------ tally


def test_mean_tally_reports_what_it_draws():
    facts = walk_claims(coerce_model(dict(V1, tally_stat="mean", tally_target=9)), V1_BEATS)
    steps = facts["tally_steps"]
    assert len(steps) == 120 and facts["tally_mean"] == sum(steps) / 120
    assert all(s % 2 == 1 for s in steps), "from the middle every exit is odd"


def test_tally_until_moves_when_the_last_walk_lands():
    m = coerce_model(dict(V1, tally_until={"sentence": 3, "offset": -0.5}))
    facts = walk_claims(m, V1_BEATS)
    tally_start = 10.0 + 8.0 + 4.0 + 24.0
    assert facts["tally_done_seconds"] == pytest.approx(tally_start + 12.0 - 0.5)


def test_a_tally_window_outside_its_phase_is_refused():
    m = coerce_model(dict(V1, tally_until={"phase": "renewal", "at": 0.5}))
    with pytest.raises(ProbabilityError) as err:
        walk_claims(m, V1_BEATS)
    assert err.value.param == "tally_until"


@pytest.mark.parametrize("params,param", [
    ({"tally_stat": "mode"}, "tally_stat"),
    ({"tally_target": 9}, "tally_target"),                      # needs mean/histogram
    ({"tally_stat": "mean", "tally_target": -1}, "tally_target"),
    ({"tally_ease": "bounce"}, "tally_ease"),
    ({"tally_text": {"stat": "{mean:.2f} of {total}"}}, "tally_text"),
    ({"tally_text": {"average": "x"}}, "tally_text"),
    ({"step_axis": "x" * 50}, "step_axis"),
])
def test_tally_refusals_name_the_parameter(params, param):
    with pytest.raises(ProbabilityError) as err:
        coerce_model(dict(V1, **params))
    assert err.value.param == param


def test_tally_parameters_need_the_tally():
    with pytest.raises(ProbabilityError) as err:
        coerce_model({"phases": ["walk", "absorb"], "step_axis": "steps"})
    assert err.value.param == "step_axis"


@pytest.mark.parametrize("stat", ["mean", "histogram"])
def test_statistic_tallies_compile(stat):
    code = _scene(dict(V1, tally_stat=stat, tally_target=9, step_axis="steps",
                       tally_until={"sentence": 2}, tally_ease="slow_start"), beats=V1_BEATS)
    compile(code, "scene", "exec")
    assert "STEPS_OF" in code and "X_TARGET" in code and "STEP_TICK" in code


def test_end_tally_text_can_be_rewritten():
    code = _scene({"tally_text": {"zero": "fell to 0: {count}"}})
    compile(code, "scene", "exec")
    assert "fell to 0: {count}" in code


# ------------------------------------------------------------- labels, cards


def test_axis_labels_replace_the_defaults():
    code = _scene({"axis_labels": {"low": "−3", "high": "+3", "start": "start"}})
    compile(code, "scene", "exec")
    assert '"−3"' in code and '"+3"' in code and '"start"' in code
    assert '"N = %d" % N' not in code


def test_axis_labels_refuse_unknown_keys():
    with pytest.raises(ProbabilityError) as err:
        coerce_model({"axis_labels": {"middle": "x"}})
    assert err.value.param == "axis_labels"


def test_labels_until_fades_the_end_labels():
    code = _scene({"labels_until": {"ends": "tally", "title": "tally"}, "title": "T"})
    compile(code, "scene", "exec")
    assert "T_ENDS_OUT" in code and "T_TITLE_OUT" in code


def test_a_step_axis_takes_the_end_labels_down_with_the_tally():
    """The low label sits where the step numbers go."""
    code = _scene(dict(V1, tally_stat="mean", step_axis="steps"), beats=V1_BEATS)
    assert "T_ENDS_OUT = T_TALLY" in code


def test_caption_cards_parse_in_order_with_their_cues():
    m = coerce_model(dict(V1, captions={"renewal": [
        "first", {"text": "second", "sentence": 2, "build": True},
        {"text": "third", "at": 0.8, "until": {"phase": "tally"}}]}))
    (_phase, cards), = m.captions
    assert [c.text for c in cards] == ["first", "second", "third"]
    assert cards[1].build and cards[1].cue == Cue("renewal", 2, 0.0, None)
    assert cards[2].until == Cue("tally")


@pytest.mark.parametrize("cards", [
    [],
    [{"text": "x", "build": True}],
    [{"words": "x"}],
    [{"text": "x", "colour": "red"}],
    [{"text": "<u>x</u>"}],
])
def test_bad_cards_are_refused(cards):
    with pytest.raises(ProbabilityError) as err:
        coerce_model(dict(V1, captions={"renewal": cards}))
    assert err.value.param == "captions"


def test_cards_and_plain_captions_mix_in_one_scene():
    code = _scene(dict(V1, captions={"walk": "plain", "tally": [{"text": "a", "sentence": 2}]}),
                  beats=V1_BEATS)
    compile(code, "scene", "exec")
    assert "CAPTIONS = {'walk': 'plain'}" in code and "CARDS = {'tally'" in code


# ------------------------------------------------------------------ layout


@pytest.mark.parametrize("aspect", ["16:9", "9:16"])
def test_the_adaptive_layout_compiles_in_both_aspects(aspect):
    plan = plan_from_template(TEMPLATE, dict(V1, layout="adaptive", title="A long title to wrap",
                                             tally_stat="mean", tally_target=9, step_axis="steps"))
    code = scene_code_for(plan, beat_seconds=V1_BEATS, aspect=aspect)
    compile(code, "scene", "exec")
    assert "BIG = 1.2 if vertical else 1.0" in code


def test_layout_refuses_unknown_names():
    with pytest.raises(ProbabilityError) as err:
        coerce_model({"layout": "wide"})
    assert err.value.param == "layout"


def test_the_python_and_scene_cue_resolvers_agree():
    m = coerce_model(dict(V1, tally_until={"sentence": 3, "offset": -0.5},
                          captions={"renewal": [{"text": "x", "sentence": 4}]}))
    spans = P.spans_for(m, V1_BEATS)
    code = _scene(dict(V1, tally_until={"sentence": 3, "offset": -0.5},
                       captions={"renewal": [{"text": "x", "sentence": 4}]}), beats=V1_BEATS)
    counts = eval(re.search(r"SENTENCE_COUNTS = (\{.*?\})", code).group(1))
    starts = P.phase_starts(spans)
    for cue in P.all_cues(m):
        i, s, o, a = cue.as_args(m.phases)
        assert cue_seconds(starts, spans, V1_BEATS, i, s, o, a, counts.get(i, 1)) == \
            cue_time(m, spans, V1_BEATS, cue)


def test_new_parameters_are_published_to_the_catalog():
    t = [x for x in list_templates() if x.id == TEMPLATE][0]
    assert {"tally_stat", "tally_target", "renewal_states", "showcase_steps", "layout",
            "axis_labels", "labels_until", "tally_until", "captions"} <= set(t.params)


def test_preconditions_reject_a_bad_new_parameter_at_submit_time():
    violations = validate(plan_from_template(TEMPLATE, {"tally_stat": "mode"}))
    assert violations and "tally_stat" in str(violations[0])


def test_the_average_marker_sits_at_the_exact_expected_length():
    params = dict(V1, showcase_steps=21, renewal_cues={"done": {"sentence": 2, "offset": 2.0},
                                                       "average": {"sentence": 3, "offset": 2.0}})
    facts = walk_claims(coerce_model(params), V1_BEATS)
    assert facts["renewal_average_seconds"] == pytest.approx(10 + 8 + 4 + 11.0 + 2.0)
    code = _scene(params, beats=V1_BEATS)
    compile(code, "scene", "exec")
    assert "E_T = 9.0" in code


def test_an_average_marker_before_the_count_finishes_is_refused():
    params = dict(V1, renewal_cues={"done": {"sentence": 3}, "average": {"sentence": 2}})
    with pytest.raises(ProbabilityError) as err:
        walk_claims(coerce_model(params), V1_BEATS)
    assert err.value.param == "renewal_cues"
