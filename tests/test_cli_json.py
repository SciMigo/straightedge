"""``--json``: one parseable object per command, success or failure.

Everything the CLI prints as prose an agent has to scrape; ``--json`` gives it a
single object instead, and — the part that matters for recovery — on failure the
object carries a stable ``code`` and the ``remedy`` to try, not a sentence on
stderr that is free to change.

These assert the *shape* an agent depends on: `ok`, `command`, and on failure a
typed error with a code and remedy. They deliberately do not pin prose.
"""

from __future__ import annotations

import json

import pytest

from straightedge import cli


def _run_json(capsys, argv):
    code = cli.main(argv)
    out = capsys.readouterr().out
    return code, json.loads(out)


class TestSuccessEnvelope:
    def test_plan_emits_one_object(self, capsys):
        code, obj = _run_json(capsys, ["plan", "画 y=x^2 的导数", "--json"])
        assert code == 0
        assert obj["ok"] is True
        assert obj["command"] == "plan"
        assert obj["plan"]["concept"]

    def test_list_templates_emits_the_catalog(self, capsys):
        code, obj = _run_json(capsys, ["list-templates", "--json"])
        assert code == 0 and obj["ok"] is True
        assert isinstance(obj["templates"], list) and obj["templates"]

    def test_scaffold_reports_the_scene_path(self, capsys, tmp_path):
        code, obj = _run_json(
            capsys, ["scaffold", "画 y=x^2 的导数", "--json",
                     "--output-dir", str(tmp_path)])
        assert code == 0 and obj["ok"] is True
        assert obj["scene"].endswith(".py")
        assert "untranslated_labels" in obj

    def test_stdout_is_only_the_object(self, capsys, tmp_path):
        """No stray prose on stdout — the whole point is one parseable thing.

        Warnings still go to stderr; stdout must be exactly the JSON object.
        """
        cli.main(["scaffold", "画 y=x^2 的导数", "--json",
                  "--output-dir", str(tmp_path)])
        out = capsys.readouterr().out
        json.loads(out)                       # the entire stdout parses as one object

    def test_manim_chatter_is_kept_off_stdout(self, capsys, monkeypatch, tmp_path):
        """A render subprocess prints progress; under --json it must go to stderr.

        This is the failure a mocked render cannot catch — real Manim inherits
        stdout and would corrupt the one object. The CLI passes stderr as the
        render's stdout target under --json, so assert it does.
        """
        seen = {}

        class Result:
            returncode = 0
            output_path = tmp_path / "v.mp4"

        def fake_render(*args, stdout=None, **kwargs):
            seen["stdout"] = stdout
            return Result()

        monkeypatch.setattr(cli, "render_scene", fake_render)
        import sys
        cli.main(["render", "画 y=x^2", "--json", "--skip-font-check",
                  "--output-dir", str(tmp_path)])
        assert seen["stdout"] is sys.stderr, "Manim output must not reach stdout"
        json.loads(capsys.readouterr().out)   # stdout still one clean object


class TestErrorEnvelope:
    def test_a_blocking_precondition_is_a_typed_error(self, capsys, monkeypatch):
        from straightedge.preconditions import Violation

        monkeypatch.setattr(cli, "validate", lambda plan: [
            Violation("trig/graph_transform", "trig_spec.omega",
                      "omega=0 draws a flat line")])
        code, obj = _run_json(
            capsys, ["render", "画 y=sin(x)", "--json", "--skip-font-check"])
        assert code == 1
        assert obj["ok"] is False
        assert obj["error"]["code"] == "blocking_precondition"
        assert obj["error"]["remedy"], "an error must name what to try instead"
        assert obj["error"]["details"]["violations"]

    def test_force_turns_the_same_plan_into_a_render_attempt(self, capsys,
                                                             monkeypatch, tmp_path):
        """The remedy the error names actually works: --force gets past the gate."""
        from straightedge.preconditions import Violation

        monkeypatch.setattr(cli, "validate", lambda plan: [
            Violation("trig/graph_transform", "trig_spec.omega", "omega=0")])

        class Result:
            returncode = 0
            output_path = tmp_path / "video.mp4"

        monkeypatch.setattr(cli, "render_scene", lambda *a, **k: Result())
        code, obj = _run_json(
            capsys, ["render", "画 y=sin(x)", "--json", "--force",
                     "--skip-font-check", "--output-dir", str(tmp_path)])
        assert code == 0 and obj["ok"] is True
        assert obj["command"] == "render"

    def test_a_bad_beats_file_reports_its_code_and_remedy(self, capsys, tmp_path):
        code, obj = _run_json(
            capsys, ["render", "画 y=x^2", "--json", "--skip-font-check",
                     "--beat-seconds", str(tmp_path / "missing.json")])
        assert code == 1 and obj["ok"] is False
        assert obj["error"]["code"] == "bad_input_file"
        assert obj["error"]["remedy"]

    def test_a_render_failure_carries_the_returncode(self, capsys, monkeypatch,
                                                     tmp_path):
        class Result:
            returncode = 1
            output_path = None

        monkeypatch.setattr(cli, "render_scene", lambda *a, **k: Result())
        code, obj = _run_json(
            capsys, ["render", "画 y=x^2", "--json", "--skip-font-check",
                     "--output-dir", str(tmp_path)])
        assert code == 1 and obj["error"]["code"] == "render_failed"
        assert obj["error"]["details"]["returncode"] == 1


class TestHumanOutputUnchanged:
    """Without --json, every command prints exactly what it printed before."""

    def test_plan_still_prints_the_bare_json_object(self, capsys):
        cli.main(["plan", "画 y=x^2 的导数"])
        obj = json.loads(capsys.readouterr().out)
        assert "ok" not in obj, "the legacy plan output is the plan, not an envelope"
        assert obj["concept"]

    def test_scaffold_still_prints_the_path(self, capsys, tmp_path):
        cli.main(["scaffold", "画 y=x^2 的导数", "--output-dir", str(tmp_path)])
        out = capsys.readouterr().out.strip()
        assert out.endswith(".py") and out.count("\n") == 0

    def test_a_blocking_precondition_still_goes_to_stderr(self, capsys, monkeypatch):
        from straightedge.preconditions import Violation

        monkeypatch.setattr(cli, "validate", lambda plan: [
            Violation("c", "p", "boom")])
        code = cli.main(["render", "画 y=sin(x)", "--skip-font-check"])
        err = capsys.readouterr().err
        assert code == 1
        assert "--force" in err, "the human still gets the remedy on stderr"
