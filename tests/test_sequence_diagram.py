"""The sequence_diagram template: lifelines, time order, and refusing a wrong protocol.

The figure's claims are positional — this message comes after that one, this
party is absent across that gap, this label belongs between those two parties —
so the tests read positions back out of the SVG rather than looking for strings.
"""
from __future__ import annotations

import re
from xml.etree import ElementTree as ET

import pytest

import straightedge.diagrams.templates  # noqa: F401  (triggers @register)
from straightedge.diagrams.legibility import check_figure
from straightedge.diagrams.registry import (
    DIAGRAM_REGISTRY,
    count_data_marks,
    refusal_findings,
    render_diagram,
)
from straightedge.diagrams.renderer import text_width
from straightedge.diagrams.templates.sequence_diagram import LABEL_FONT

NS = "{http://www.w3.org/2000/svg}"

TIMER = {
    "participants": [{"id": "code", "label": "Workflow code"},
                     {"id": "sdk", "label": "SDK event loop", "sub": "in the Worker"},
                     {"id": "svc", "label": "Temporal Service"}],
    "rows": [
        {"from": "code", "to": "sdk", "label": "asyncio.sleep(20)"},
        {"note": "seq 1 · pending[1] = resolve", "over": "sdk"},
        {"from": "sdk", "to": "svc", "label": "StartTimer(seq 1, 20 s)", "event": 11},
        {"gap": "20 s on the Service's clock", "breaks": ["code", "sdk"]},
        {"self": "svc", "label": "TimerFired", "event": 12},
        {"from": "svc", "to": "sdk", "label": "fire_timer(seq 1)", "event": 13, "style": "dashed"},
        {"from": "sdk", "to": "code", "label": "the await returns"},
    ],
}


def _svg(params=None, **extra):
    return render_diagram({"type": "sequence_diagram", "params": {**(params or TIMER), **extra}})


def _texts(svg):
    root = ET.fromstring(svg)
    return [(el.text or "", float(el.get("x")), float(el.get("y")), el.get("class") or "")
            for el in root.iter(f"{NS}text")]


def _lifelines(svg):
    root = ET.fromstring(svg)
    return [(float(el.get("x1")), float(el.get("y1")), float(el.get("y2")))
            for el in root.iter(f"{NS}line") if "sq-lifeline" in (el.get("class") or "")]


def test_registered():
    assert "sequence_diagram" in DIAGRAM_REGISTRY


def test_draws_every_participant_label_and_event_number():
    svg = _svg()
    drawn = {t for t, *_ in _texts(svg)}
    for expected in ("Workflow code", "SDK event loop", "in the Worker", "Temporal Service",
                     "StartTimer(seq 1, 20 s)", "TimerFired", "fire_timer(seq 1)",
                     "seq 1 · pending[1] = resolve", "20 s on the Service's clock",
                     "11", "12", "13"):
        assert expected in drawn, expected
    assert count_data_marks(svg) > 0


def test_rows_run_down_the_page_in_the_order_given():
    y = {t: ty for t, _, ty, _ in _texts(_svg())}
    order = ["asyncio.sleep(20)", "seq 1 · pending[1] = resolve", "StartTimer(seq 1, 20 s)",
             "20 s on the Service's clock", "TimerFired", "fire_timer(seq 1)", "the await returns"]
    assert [y[label] for label in order] == sorted(y[label] for label in order)


def test_event_numbers_sit_on_their_rows():
    y = {t: ty for t, _, ty, _ in _texts(_svg())}
    assert abs(y["11"] - y["StartTimer(seq 1, 20 s)"]) < 20
    assert abs(y["12"] - y["TimerFired"]) < 20


def test_a_gap_breaks_only_the_lifelines_it_names():
    """The Worker's two lifelines stop across the gap; the Service's does not."""
    segments = {}
    for x, _, _ in _lifelines(_svg()):
        segments[x] = segments.get(x, 0) + 1
    code_x, sdk_x, svc_x = sorted(segments)
    assert segments[code_x] == 2 and segments[sdk_x] == 2
    assert segments[svc_x] == 1


def test_a_gap_label_never_crosses_a_lifeline_that_carries_on():
    """Breaks on both sides of a continuing lifeline: the label must not sit on it."""
    params = {"participants": ["worker1", "service", "worker2"],
              "rows": [{"from": "worker1", "to": "service", "label": "StartTimer"},
                       {"gap": "kill -9 Worker 1; the timer keeps running",
                        "breaks": ["worker1", "worker2"]},
                       {"self": "service", "label": "TimerFired"}]}
    svg = _svg(params)
    segments = {}
    for x, _, _ in _lifelines(svg):
        segments[x] = segments.get(x, 0) + 1
    continuing = [x for x, count in segments.items() if count == 1]
    assert len(continuing) == 1
    [gap] = [t for t in _texts(svg) if t[3].startswith("sq-gap")]
    half = text_width(gap[0], LABEL_FONT, safe=True) / 2
    assert not (gap[1] - half <= continuing[0] <= gap[1] + half)


def test_a_label_fits_between_the_lifelines_it_spans():
    long_label = "Command ScheduleActivityTask(call_llm, prompt, key) with a retry policy"
    params = {"participants": ["A", "B"],
              "rows": [{"from": "A", "to": "B", "label": long_label}]}
    svg = _svg(params)
    xs = sorted({x for x, _, _ in _lifelines(svg)})
    lines = [t for t in _texts(svg) if t[3].startswith("sq-label")]
    assert len(lines) == 2                 # past LABEL_MAX_W it wraps rather than overflows
    for value, x, _, _ in lines:
        half = text_width(value, LABEL_FONT, safe=True) / 2
        assert xs[0] <= x - half and x + half <= xs[1], value


def test_a_self_message_on_the_last_lifeline_stays_on_the_canvas():
    params = {"participants": ["client", "server"],
              "rows": [{"self": "server", "label": "a long self-message label on the edge"}]}
    svg = _svg(params)
    width = float(ET.fromstring(svg).get("width"))
    [label] = [t for t in _texts(svg) if t[0].startswith("a long")]
    assert label[1] + text_width(label[0], LABEL_FONT, safe=True) <= width


def test_bare_string_participants_and_aliases():
    svg = render_diagram({"type": "sequence_diagram", "params": {
        "actors": ["client", "server"],
        "messages": [{"from": "client", "to": "server", "label": "GET /"},
                     {"from": "server", "to": "server", "label": "render"},
                     {"from": "server", "to": "client", "label": "200 OK", "style": "dashed"}]}})
    drawn = {t for t, *_ in _texts(svg)}
    assert {"client", "server", "GET /", "render", "200 OK"} <= drawn
    assert "sq-dashed" in svg


class TestRefusals:
    """A protocol the rows contradict is refused with the row, not drawn."""

    @pytest.mark.parametrize("params,needle", [
        ({"participants": ["A"], "rows": [{"from": "A", "to": "B", "label": "x"}]}, "'B'"),
        ({"participants": ["A", "B"], "rows": [
            {"from": "A", "to": "B", "label": "x", "event": 12},
            {"from": "B", "to": "A", "label": "y", "event": 11}]}, "not after"),
        ({"participants": ["A", "A"], "rows": [{"self": "A", "label": "x"}]}, "declared twice"),
        ({"participants": ["A"], "rows": [{"note": "n", "over": []}]}, "over nobody"),
        ({"participants": ["A"], "rows": [{"gap": "later", "breaks": ["Z"]}]}, "'Z'"),
        ({"participants": ["A"], "rows": [{"self": "A", "label": "x", "event": "eleven"}]}, "not a number"),
        ({"participants": [], "rows": [{"self": "A", "label": "x"}]}, "no participants"),
        ({"participants": ["A"], "rows": []}, "no rows"),
    ])
    def test_refused_with_a_reason_and_drawn_as_nothing(self, params, needle):
        findings = refusal_findings("sequence_diagram", params)
        assert findings and all(f.severity == "error" for f in findings)
        assert any(needle in f.message for f in findings), [f.message for f in findings]
        assert _svg(params) == ""

    def test_a_valid_protocol_has_no_findings(self):
        assert refusal_findings("sequence_diagram", TIMER) == []


class TestThemes:
    def test_every_theme_renders_and_changes_only_colour_and_corners(self):
        template = DIAGRAM_REGISTRY["sequence_diagram"]
        renders = {name: _svg(theme=name) for name in template.themes}
        assert len(set(renders.values())) == len(renders)
        # Colour lives in <style> and <defs>; corner radius is the theme's too.
        geometry = {name: re.sub(r'<style>.*?</style>|<defs>.*?</defs>| rx="[^"]*"', "", svg, flags=re.S)
                    for name, svg in renders.items()}
        assert len(set(geometry.values())) == 1

    def test_dark_draws_dark_paper(self):
        assert ".sq-background{fill:#10151f}" in _svg(theme="dark")


def test_the_example_figure_carries_no_legibility_error():
    errors = [f for f in check_figure(_svg()) if f.severity == "error"]
    assert not errors, [(f.check, f.label, f.message) for f in errors]
