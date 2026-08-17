"""The flags, at the boundary where a user actually types them.

Everything below is about a flag reaching the thing it names. That sounds too
obvious to test, and it is exactly what went wrong: ``--aspect`` and
``--language`` were declared globally, printed in ``--help`` for all six
commands, and read by three of them. Nothing failed — the renders just came out
in the wrong shape and the wrong language, which no test and no exit code could
see.
"""

from __future__ import annotations

import json

import pytest

from straightedge import cli
from straightedge.aspect import VERTICAL
from straightedge.errors import InputFileError


# --------------------------------------------------------- measured timings

class TestBeatSecondsFile:
    """The map is supplied, not measured: the durations come from whatever
    produced the audio, and this project does not synthesise it.
    """

    def _write(self, tmp_path, payload):
        path = tmp_path / "beats.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_absent_means_keep_the_authored_timing(self):
        assert cli._read_beat_seconds(None) is None

    def test_a_valid_map_is_read_as_floats(self, tmp_path):
        path = self._write(tmp_path, {"b01": 2, "b02": 3.5})
        assert cli._read_beat_seconds(path) == {"b01": 2.0, "b02": 3.5}

    def test_a_partial_map_is_valid(self, tmp_path):
        """Keys absent from the map keep the timing the builder was written
        with, which is what lets scenes be converted one at a time.
        """
        assert cli._read_beat_seconds(self._write(tmp_path, {"b07": 6.8})) == {"b07": 6.8}

    @pytest.mark.parametrize("payload", [[1, 2], "3.0", 4])
    def test_a_non_object_payload_is_rejected(self, tmp_path, payload):
        with pytest.raises(InputFileError, match="JSON object"):
            cli._read_beat_seconds(self._write(tmp_path, payload))

    def test_a_non_numeric_duration_is_rejected(self, tmp_path):
        with pytest.raises(InputFileError, match="number of seconds"):
            cli._read_beat_seconds(self._write(tmp_path, {"b01": "3.2s"}))

    def test_a_boolean_is_not_a_duration(self, tmp_path):
        """``True`` is an ``int`` in Python and would silently mean one second."""
        with pytest.raises(InputFileError, match="number of seconds"):
            cli._read_beat_seconds(self._write(tmp_path, {"b01": True}))

    @pytest.mark.parametrize("value", [0, -1.5])
    def test_a_non_positive_duration_is_rejected(self, tmp_path, value):
        with pytest.raises(InputFileError, match="positive"):
            cli._read_beat_seconds(self._write(tmp_path, {"b01": value}))

    def test_malformed_json_names_the_file(self, tmp_path):
        path = tmp_path / "beats.json"
        path.write_text("{not json", encoding="utf-8")
        with pytest.raises(InputFileError, match="not valid JSON"):
            cli._read_beat_seconds(path)

    def test_a_missing_file_is_reported_rather_than_ignored(self, tmp_path):
        """Silently rendering with default timings would look like success."""
        with pytest.raises(InputFileError, match="Cannot read"):
            cli._read_beat_seconds(tmp_path / "nope.json")


def test_measured_timings_reach_the_scene_the_cli_writes(tmp_path, capsys):
    """The whole point of the flag: ``write_scene`` is the only writer, so this
    is the only route a measured narration has into a render.
    """
    beats = tmp_path / "beats.json"
    beats.write_text(json.dumps({"b01": 4.25}), encoding="utf-8")

    code = cli.main([
        "scaffold", "画一个椭圆，显示焦点和长轴",
        "--output-dir", str(tmp_path / "out"),
        "--beat-seconds", str(beats),
    ])

    assert code == 0
    assert "4.25" in (tmp_path / "out" / "scene.py").read_text(encoding="utf-8")


def test_a_bad_beats_file_fails_before_anything_is_rendered(tmp_path, capsys):
    beats = tmp_path / "beats.json"
    beats.write_text("[]", encoding="utf-8")

    code = cli.main([
        "scaffold", "画一个椭圆",
        "--output-dir", str(tmp_path / "out"),
        "--beat-seconds", str(beats),
    ])

    assert code == 1
    assert "JSON object" in capsys.readouterr().err


# ------------------------------------------------------------ shape and words

def test_the_scaffold_command_writes_the_aspect_it_was_given(tmp_path):
    cli.main([
        "scaffold", "画一个椭圆，显示焦点和长轴",
        "--output-dir", str(tmp_path), "--aspect", VERTICAL,
    ])
    assert "config.frame_width = 9.0" in (tmp_path / "scene.py").read_text(encoding="utf-8")


def test_an_untranslated_label_is_named_on_stderr(tmp_path, capsys, monkeypatch):
    """Warned about, never blanked: a visible Chinese caption on an English cut
    is a catalog fix, where an empty one looks like a render bug.
    """
    monkeypatch.setattr(cli, "untranslated", lambda code, language: ["未翻译的标签"])
    cli.main(["scaffold", "画一个椭圆", "--output-dir", str(tmp_path), "--language", "en"])
    err = capsys.readouterr().err
    assert "未翻译的标签" in err
    assert "no en translation" in err


# ------------------------------------------------------------- the font gate

class TestAgentRenderFontPreflight:
    """The agent path enforced a CJK font unconditionally while the
    deterministic path had already learned not to. An English render has no CJK
    glyphs left to draw, so the check was refusing renders a host could serve.
    """

    @pytest.fixture
    def broken_font(self, monkeypatch):
        monkeypatch.setattr(cli, "font_status", lambda font: ("error", "no CJK font"))

    @pytest.fixture
    def spy_render(self, monkeypatch):
        calls = []

        class Result:
            output_path = None
            fallback_used = False
            logs = ""
            untranslated_labels = ()
            violations = ()

        def fake(*args, **kwargs):
            calls.append(kwargs)
            return Result()

        monkeypatch.setattr(cli, "run_agent_render", fake)
        return calls

    def test_an_english_render_proceeds_without_a_cjk_font(
            self, tmp_path, broken_font, spy_render):
        cli.main(["agent-render", "画一个椭圆", "--output-dir", str(tmp_path),
                  "--language", "en"])
        assert len(spy_render) == 1, "the render must not be refused"

    def test_a_chinese_render_still_refuses(self, tmp_path, broken_font, spy_render):
        code = cli.main(["agent-render", "画一个椭圆", "--output-dir", str(tmp_path),
                         "--language", "zh"])
        assert code == 1
        assert spy_render == [], "nothing should have been rendered"

    def test_the_flags_reach_the_agent(self, tmp_path, spy_render, monkeypatch):
        monkeypatch.setattr(cli, "font_status", lambda font: ("ok", ""))
        cli.main(["agent-render", "画一个椭圆", "--output-dir", str(tmp_path),
                  "--aspect", VERTICAL, "--language", "en"])
        assert spy_render[0]["aspect"] == VERTICAL
        assert spy_render[0]["language"] == "en"


def test_the_agent_scaffold_command_passes_them_too(tmp_path, monkeypatch):
    calls = []

    class Result:
        scene_path = "scene.py"
        validated = True
        untranslated_labels = ()

        class spec:
            topic = "conic"
            concept = "ellipse_foci"

    def fake(*args, **kwargs):
        calls.append(kwargs)
        return Result()

    monkeypatch.setattr(cli, "run_agent_scaffold", fake)
    cli.main(["agent-scaffold", "画一个椭圆", "--output-dir", str(tmp_path),
              "--aspect", VERTICAL, "--language", "en"])

    assert calls[0]["aspect"] == VERTICAL
    assert calls[0]["language"] == "en"
