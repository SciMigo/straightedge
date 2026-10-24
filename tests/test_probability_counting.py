"""probability/outcome_grid and probability/arrangement_gaps: every number computed, never typed."""
from __future__ import annotations

import inspect
import re
from fractions import Fraction
from math import comb

import pytest

from straightedge import build_plan, list_templates, plan_from_template, scene_code_for, validate
from straightedge import probability_counting as C
from straightedge.probability import ProbabilityError

GRID = "probability/outcome_grid"
GAPS = "probability/arrangement_gaps"
BEATS = {"b01": 7.0, "b02": 8.0, "b03": 6.0, "b04": 7.0}
ENGINE_BEAT_RE = r'_beat\w*\(\s*self,\s*"(b\d+)"'


def _scene(template, params, beats=BEATS):
    return scene_code_for(plan_from_template(template, params), beat_seconds=beats)


def _helpers(code, first):
    """Run the scene's embedded helper functions (from ``def first(`` to the scene class)."""
    ns: dict = {}
    exec("import random\nfrom bisect import bisect_right\n"
         + code[code.index(f"def {first}("):code.index("class GeneratedScene")], ns)
    return ns


# ================================================================ outcome grid


def test_default_grid_is_seven_against_six():
    facts = C.grid_claims(C.coerce_outcome_grid({}))
    assert facts["total"] == 36 and facts["counts"] == [6, 5] and facts["n_all"] == 11
    assert facts["p_first"] == ["6/11", "5/11"]
    assert facts["p_single"] == ["1/6", "5/36"]
    assert facts["p_neither"] == "25/36"


def test_p_first_is_the_race_probability():
    """P(A before B) for independent rolls = P(A) / (P(A) + P(B)), checked by the series."""
    m = C.coerce_outcome_grid({"events": [{"stat": "sum", "values": [8]},
                                          {"stat": "sum", "values": [12]}]})
    facts = C.grid_claims(m)
    assert facts["p_first"] == ["5/6", "1/6"]
    a, b = (Fraction(n, 36) for n in facts["counts"])
    series = sum((1 - a - b) ** k * a for k in range(2000))
    assert abs(series - Fraction(facts["p_first"][0])) < Fraction(1, 10 ** 40)


@pytest.mark.parametrize("stat,values,count", [
    ("sum", [7], 6), ("sum", [2, 12], 2), ("absdiff", [0], 6), ("max", [6], 11),
    ("min", [1], 11), ("product", [12], 4), ("first", [3], 6), ("second", [1, 2], 12),
    ("difference", [1], 5),
])
def test_event_cells_count_the_rolls(stat, values, count):
    cells = C.event_cells((6, 6), [(stat, tuple(values))])[0]
    assert len(cells) == count
    assert all(C.grid_stat(stat, r + 1, c + 1) in values for r, c in cells)


def test_faces_need_not_be_six():
    facts = C.grid_claims(C.coerce_outcome_grid(
        {"faces": [4, 8], "events": [{"stat": "sum", "values": [5]}]}))
    assert facts["total"] == 32 and facts["counts"] == [4]


@pytest.mark.parametrize("params,param", [
    ({"faces": [1, 6]}, "faces"),
    ({"faces": [6, 11]}, "faces"),
    ({"events": [{"stat": "sum", "values": [13]}]}, "events"),
    ({"events": [{"stat": "sum", "values": [7]}, {"stat": "first", "values": [1]}]}, "events"),
    ({"events": [{"stat": "mean", "values": [3]}]}, "events"),
    ({"events": [{"stat": "sum", "values": [7], "colour": "pink"}]}, "events"),
    ({"events": [{"stat": "sum", "values": [k]} for k in (2, 3, 4, 5)]}, "events"),
    ({"captions": {"grid": ["answer {nope}"]}}, "captions"),
    ({"captions": {"tally": ["x"]}}, "captions"),
    ({"result_text": "P = {p9}"}, "result_text"),
    ({"phases": ["events", "grid"]}, "phases"),
    ({"phases": ["grid", "condition"]}, "phases"),
    ({"phases": ["grid", "events"], "result_text": "x"}, "result_text"),
    ({"cues": {"event1": {"phase": "grid", "sentence": 1}}}, "cues"),
    ({"cues": {"event3": "events"}}, "cues"),
    ({"safe_area": "phone"}, "safe_area"),
])
def test_grid_refusals_name_the_parameter(params, param):
    with pytest.raises(ProbabilityError) as err:
        C.grid_claims(C.coerce_outcome_grid(params))
    assert err.value.param == param


def test_overlapping_events_are_refused_with_the_shared_roll():
    with pytest.raises(ProbabilityError, match="share the roll"):
        C.coerce_outcome_grid({"events": [{"stat": "sum", "values": [4]},
                                          {"stat": "absdiff", "values": [0]}]})


def test_caption_fields_are_filled_from_the_counts():
    m = C.coerce_outcome_grid({
        "captions": {"result": [{"text": "{n1} of {n_all}: <b>{p1}</b> ({q1_raw})", "sentence": 1}]},
        "condition_text": "{rest} rolls change nothing"})
    (phase, cards), = m.captions
    assert phase == "result" and cards[0].text == "6 of 11: <b>6/11</b> (6/36)"
    assert m.condition_text == "25 rolls change nothing"
    assert m.result_text == "6 / (6 + 5) = <b>6/11</b>"
    assert [e.label for e in m.events] == ["sum 7: 6", "sum 6: 5"]


def test_event_cues_must_run_in_order():
    with pytest.raises(ProbabilityError) as err:
        C.grid_claims(C.coerce_outcome_grid({"cues": {"event1": {"phase": "events", "at": 0.9},
                                                       "event2": {"phase": "events", "at": 0.1}}}))
    assert err.value.param == "cues"


def test_grid_scene_compiles_with_one_beat_per_phase():
    code = _scene(GRID, {})
    compile(code, "scene", "exec")
    assert sorted(set(re.findall(ENGINE_BEAT_RE, code))) == ["b01", "b02", "b03", "b04"]
    short = _scene(GRID, {"phases": ["grid", "events"]}, {"b01": 5.0, "b02": 5.0})
    assert sorted(set(re.findall(ENGINE_BEAT_RE, short))) == ["b01", "b02"]


def test_grid_scene_carries_the_checked_functions_and_draws_their_cells():
    params = {"events": [{"stat": "max", "values": [6]}, {"stat": "sum", "values": [2, 3]}]}
    code = _scene(GRID, params)
    for fn in (C.grid_stat, C.event_cells):
        assert inspect.getsource(fn) in code
    ns = _helpers(code, "grid_stat")
    facts = C.grid_claims(C.coerce_outcome_grid(params), BEATS)
    drawn = ns["event_cells"]((6, 6), [("max", (6,)), ("sum", (2, 3))])
    assert [[list(c) for c in found] for found in drawn] == facts["cells"]


def test_invalid_grid_renders_a_refusal():
    code = _scene(GRID, {"faces": [1, 1]})
    assert "Nothing to draw" in code and "event_cells" not in code


def test_shorts_safe_area_is_written_into_the_scene():
    code = _scene(GRID, {})
    assert "W / 2 - 0.14 * W" in code and "-H / 2 + 0.21 * H" in code
    assert "SHORTS = True and vertical" in code
    assert "SHORTS = False and vertical" in _scene(GRID, {"safe_area": "frame"})


# ================================================================ arrangement gaps


def test_deal_is_seeded_and_gap_sizes_partition_the_rest():
    a, b = C.deal(52, 4, 9), C.deal(52, 4, 9)
    assert a == b and sum(a) == 4 and len(a) == 52
    sizes = C.gap_sizes(a)
    assert len(sizes) == 5 and sum(sizes) == 48


def test_gap_sizes_of_a_known_order():
    order = [False, True, True, False, False, True]
    assert C.gap_sizes(order) == [1, 0, 2, 0]


def test_choose_deal_respects_both_bounds():
    seed, order = C.choose_deal(52, 4, 1, 3, max_gap=16)
    sizes = C.gap_sizes(order)
    assert min(sizes) >= 3 and max(sizes) <= 16 and order == C.deal(52, 4, seed)


@pytest.mark.parametrize("total,markers,focus", [(52, 4, 1), (52, 4, 2), (52, 4, 4),
                                                  (10, 3, 2), (20, 1, 1)])
def test_expected_position_two_ways(total, markers, focus):
    """The gap argument, k·((n-m)/(m+1) + 1), equals the direct sum over the distribution."""
    gap = Fraction(total - markers, markers + 1)
    assert C.exact_marker_position(total, markers, focus) == focus * (gap + 1)


def test_first_ace_is_fifty_three_fifths():
    facts = C.gap_claims(C.coerce_arrangement_gaps({"runs": 2000}))
    assert facts["answer"] == "53/5" and facts["mean_gap"] == "48/5"
    direct = sum(Fraction(k * comb(52 - k, 3), comb(52, 4)) for k in range(1, 53))
    assert direct == Fraction(53, 5)
    f = facts["fields"]
    assert (f["answer_decimal"], f["mean_gap_decimal"], f["other"], f["gaps"]) == ("10.6", "9.6", 48, 5)


def test_running_means_start_at_the_showcase_and_approach_the_mean():
    m = C.coerce_arrangement_gaps({"runs": 50000, "seed": 3})
    facts = C.gap_claims(m)
    assert facts["first_means"] == [float(s) for s in facts["gap_sizes"]]
    assert facts["max_deviation"] < 0.15                     # SE ≈ 0.04 per gap at 5·10^4


def test_running_mean_checkpoints_are_sparse_but_end_on_the_last_run():
    checks, means = C.running_means(52, 4, 1, 100000, C.deal(52, 4, 1))
    assert checks[0] == 1 and checks[-1] == 100000 and len(checks) < 1000
    assert len(means) == len(checks) and all(len(row) == 5 for row in means)


@pytest.mark.parametrize("params,param", [
    ({"total": 3}, "total"),
    ({"total": 61}, "total"),
    ({"markers": 0}, "markers"),
    ({"markers": 9}, "markers"),
    ({"min_gap": 10}, "min_gap"),
    ({"max_gap": 5}, "max_gap"),
    ({"runs": 10}, "runs"),
    ({"focus": 5}, "focus"),
    ({"ease": "fast"}, "ease"),
    ({"gap_label": "gap {g}"}, "gap_label"),
    ({"counter_text": "{n} shuffles"}, "counter_text"),
    ({"focus_text": "{answer_fraction}"}, "focus_text"),
    ({"phases": ["deal", "focus", "gaps"]}, "phases"),
    ({"phases": ["deal", "gaps"], "focus_text": "x"}, "focus_text"),
    ({"cues": {"gaps_from": {"phase": "gaps", "at": 0.9},
               "gaps_until": {"phase": "gaps", "at": 0.1}}}, "cues"),
    ({"cues": {"focus": {"phase": "deal", "at": 0.5}}}, "cues"),
])
def test_gap_refusals_name_the_parameter(params, param):
    with pytest.raises(ProbabilityError) as err:
        C.gap_claims(C.coerce_arrangement_gaps({"runs": 200, **params}))
    assert err.value.param == param


def test_gap_captions_take_computed_fields():
    m = C.coerce_arrangement_gaps({"captions": {"deal": ["answer {answer} = {answer_decimal}"]}})
    assert m.captions[0][1][0].text == "answer 53/5 = 10.6"
    assert m.focus_text == "9.6 + 1 = <b>10.6</b>" and m.target_text == "9.6"


def test_gap_scene_compiles_and_deals_what_the_claims_dealt():
    params = {"seed": 4, "min_gap": 2, "max_gap": 18, "runs": 500}
    code = _scene(GAPS, params)
    compile(code, "scene", "exec")
    assert sorted(set(re.findall(ENGINE_BEAT_RE, code))) == ["b01", "b02", "b03", "b04"]
    for fn in (C.deal, C.gap_sizes, C.choose_deal, C.running_means):
        assert inspect.getsource(fn) in code
    ns = _helpers(code, "deal")
    facts = C.gap_claims(C.coerce_arrangement_gaps(params), BEATS)
    seed, order = ns["choose_deal"](52, 4, 4, 2, C.DEAL_TRIES, 18)
    assert seed == facts["seed_used"] and order == facts["order"]


def test_fewer_gap_phases_fewer_beats():
    code = _scene(GAPS, {"phases": ["deal", "gaps"]}, {"b01": 6.0, "b02": 5.0})
    compile(code, "scene", "exec")
    assert sorted(set(re.findall(ENGINE_BEAT_RE, code))) == ["b01", "b02"]


def test_gap_cues_follow_sentences():
    beats = {"b01": 8.0, "b01.s2": 3.0, "b02": 4.0, "b03": 12.0, "b03.s2": 4.0, "b03.s3": 8.0,
             "b04": 8.0}
    m = C.coerce_arrangement_gaps({"runs": 200, "cues": {
        "target": {"phase": "average", "sentence": 2, "offset": 0.5},
        "shuffle_from": {"phase": "average", "sentence": 3}}})
    times = C.gap_claims(m, beats)["times"]
    assert times["target"] == pytest.approx(8.0 + 4.0 + 4.0 + 0.5)
    assert times["shuffle_from"] == pytest.approx(8.0 + 4.0 + 8.0)


# ================================================================ catalog and routing


@pytest.mark.parametrize("prompt,concept", [
    ("掷两个骰子，画出 36 种结果，比较点数和为 7 与为 6", GRID),
    ("roll two dice until a 7 or a 6", GRID),
    ("洗牌后一张张翻，第一张A平均在第几张", GAPS),
    ("draw from a shuffled deck until the first ace", GAPS),
    ("画一个赌徒破产的随机游走", "probability/random_walk_exits"),
])
def test_prompts_route_to_the_concept(prompt, concept):
    assert build_plan(prompt).concept == concept


def test_both_are_listed_with_their_parameters():
    listed = {t.id: t for t in list_templates()}
    assert {"faces", "events", "phases", "captions", "safe_area"} <= set(listed[GRID].params)
    assert {"total", "markers", "seed", "min_gap", "max_gap", "runs", "focus"} <= set(listed[GAPS].params)


def test_preconditions_reject_at_submit_time():
    v = validate(plan_from_template(GRID, {"events": [{"stat": "sum", "values": [1]}]}))
    assert v and "events" in str(v[0])
    v = validate(plan_from_template(GAPS, {"total": 100}))
    assert v and "total" in str(v[0])
    assert not validate(plan_from_template(GAPS, {}))
