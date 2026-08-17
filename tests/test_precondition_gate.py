"""The CLI's refusal to spend a render on a plan that will draw the wrong thing.

:mod:`straightedge.preconditions` has been able to predict this class of defect
for a while; until now nothing called it outside the tests, so every prediction
was made and discarded. These tests are about the call, not the checks — that a
blocking violation stops the render, that a warning does not, and that a human
who has read the reason can still overrule it.

The violations are injected rather than provoked through a real request. Which
concepts currently trip which check is the subject of ``test_preconditions``;
tying the gate's tests to that would make them fail whenever a builder learned
to handle input it used to reject, which is the opposite of the signal wanted
here.
"""

from __future__ import annotations

import json

import pytest

from straightedge import cli
from straightedge.preconditions import Violation


BLOCKING = Violation("trig/graph_transform", "trig_spec.omega",
                     "omega=0 draws a flat line, not a wave")
WARNING = Violation("trig/graph_transform", "trig_spec.phi",
                    "phase is outside one period", severity="warn")


@pytest.fixture
def spy_render(monkeypatch):
    """Record whether the render was reached at all."""
    calls = []

    class Result:
        returncode = 0
        output_path = "video.mp4"

    def fake(*args, **kwargs):
        calls.append(kwargs)
        return Result()

    monkeypatch.setattr(cli, "render_scene", fake)
    return calls


def _violations(monkeypatch, *violations):
    monkeypatch.setattr(cli, "validate", lambda plan: list(violations))


class TestTheGate:

    def test_a_blocking_violation_stops_the_render(
            self, tmp_path, monkeypatch, spy_render, capsys):
        _violations(monkeypatch, BLOCKING)
        code = cli.main(["render", "画 y=sin(x)", "--output-dir", str(tmp_path),
                         "--skip-font-check"])
        assert code == 1
        assert not spy_render, "the render must not be reached"
        assert "omega=0" in capsys.readouterr().err, "say which check refused"

    def test_force_overrules_it(self, tmp_path, monkeypatch, spy_render, capsys):
        """A human who has read the reason is the better judge.

        The prediction is still printed — overruling a check is not a reason to
        stop reporting it.
        """
        _violations(monkeypatch, BLOCKING)
        code = cli.main(["render", "画 y=sin(x)", "--output-dir", str(tmp_path),
                         "--skip-font-check", "--force"])
        assert code == 0
        assert spy_render, "--force must reach the render"
        assert "omega=0" in capsys.readouterr().err

    def test_a_warning_reports_but_does_not_stop(
            self, tmp_path, monkeypatch, spy_render, capsys):
        _violations(monkeypatch, WARNING)
        code = cli.main(["render", "画 y=sin(x)", "--output-dir", str(tmp_path),
                         "--skip-font-check"])
        assert code == 0
        assert spy_render, "a warning is not a refusal"
        assert "outside one period" in capsys.readouterr().err

    def test_a_clean_plan_says_nothing(
            self, tmp_path, monkeypatch, spy_render, capsys):
        _violations(monkeypatch)
        code = cli.main(["render", "画 y=sin(x)", "--output-dir", str(tmp_path),
                         "--skip-font-check"])
        assert code == 0
        assert spy_render
        assert "[error]" not in capsys.readouterr().err

    def test_scaffold_is_gated_too(self, tmp_path, monkeypatch, capsys):
        """Scaffolding costs nothing, but it is the file a caller renders next.

        Writing a scene we have already predicted is wrong just moves the ten
        minutes somewhere this check cannot see them.
        """
        _violations(monkeypatch, BLOCKING)
        code = cli.main(["scaffold", "画 y=sin(x)", "--output-dir", str(tmp_path)])
        assert code == 1
        assert not list(tmp_path.glob("*.py")), "no scene should be written"


class TestPlanReporting:
    """``plan`` predicts rather than refuses — it is the command you run to find
    out, so it prints the violations and still returns the plan.
    """

    def test_violations_ride_along_with_the_plan(self, monkeypatch, capsys):
        _violations(monkeypatch, BLOCKING, WARNING)
        assert cli.main(["plan", "画 y=sin(x)"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert len(payload["violations"]) == 2
        assert "omega=0" in payload["violations"][0]

    def test_a_clean_plan_reports_an_empty_list(self, monkeypatch, capsys):
        """Present and empty, not absent: a caller parsing this should not have
        to distinguish "no violations" from "an older build that never checked".
        """
        _violations(monkeypatch)
        assert cli.main(["plan", "画 y=sin(x)"]) == 0
        assert json.loads(capsys.readouterr().out)["violations"] == []
