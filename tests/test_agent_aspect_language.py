"""The agent path honours ``--aspect`` and ``--language`` too.

Both flags are global on the CLI, so they are advertised for all six commands.
They used to reach only the three deterministic ones: the agent path wrote its
scene through a different writer and rendered it through a different executor,
and neither had been told. The result was the quiet kind of wrong — a render
that succeeds, prints a path, and hands back a landscape Chinese video to a
caller who asked for a vertical English one.

The LLM half cannot be covered by a translation catalog, because a model invents
labels the catalog has never seen. So the two halves are split deliberately:
the *prompt* is what produces good English, and the catalog is the safety net
for labels copied verbatim out of the Chinese spec. Both are tested here.
"""

from __future__ import annotations

import json
import subprocess

import pytest

from straightedge.agent import orchestrator
from straightedge.agent.executor import (
    CapturedRenderResult, render_scene_captured, write_code_scene,
)
from straightedge.agent.orchestrator import run_agent_render, run_agent_scaffold
from straightedge.agent.prompts import writer_user_prompt
from straightedge.agent.repair import repair_code_with_llm
from straightedge.agent.reviewer import review_code_with_llm
from straightedge.agent.schemas import AnimationSpec
from straightedge.agent.writer import write_code_with_llm
from straightedge.aspect import LANDSCAPE, VERTICAL
from straightedge.templates import SCENE_CLASS_NAME


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def chat(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        if not self.responses:
            raise AssertionError("FakeClient has no response queued")
        return self.responses.pop(0)

    def last_user_prompt(self) -> str:
        return self.calls[-1][0][-1]["content"]


def _plan_json():
    return json.dumps({
        "language": "zh",
        "topic": "conic",
        "concept": "ellipse_foci",
        "title_zh": "椭圆",
        "objective_zh": "焦点",
    })


def _spec():
    return AnimationSpec(
        language="zh", topic="conic", concept="ellipse_foci",
        title_zh="椭圆", objective_zh="焦点",
    )


def _model_code(label: str = "测试") -> str:
    return f'''
from manim import *

CJK_FONT = "STSong"


def _t(text, **kwargs):
    kwargs.setdefault("font", CJK_FONT)
    return Text(text, **kwargs)


class GeneratedScene(Scene):
    def construct(self):
        self.play(Write(_t("{label}")))
        self.wait(1)
'''.strip()


# ------------------------------------------------------- the frame guarantee

class TestWrittenSceneDeclaresItsFrame:
    """A prompt is a request; this is the enforcement.

    A model that drops the frame lines yields a scene composed for a 4.5-unit
    frame with every label off both sides — and nothing downstream notices,
    because the file renders fine and only *looks* wrong.
    """

    def test_a_vertical_scene_gains_the_frame_it_was_missing(self, tmp_path):
        path = write_code_scene(_model_code(), tmp_path, aspect=VERTICAL)
        written = path.read_text(encoding="utf-8")
        assert "config.frame_width = 9.0" in written
        assert "config.frame_height = 16.0" in written

    def test_the_frame_lands_after_the_import_that_defines_config(self, tmp_path):
        """``config`` arrives with ``from manim import *``. Injected above it,
        the scene raises NameError before it draws anything.
        """
        written = write_code_scene(_model_code(), tmp_path, aspect=VERTICAL).read_text(
            encoding="utf-8")
        lines = [line.strip() for line in written.splitlines()]
        assert lines.index("config.frame_width = 9.0") > lines.index("from manim import *")

    def test_the_written_scene_still_compiles(self, tmp_path):
        written = write_code_scene(_model_code(), tmp_path, aspect=VERTICAL).read_text(
            encoding="utf-8")
        compile(written, "scene.py", "exec")

    def test_a_models_own_declaration_is_not_duplicated(self, tmp_path):
        """Two assignments would be harmless but dishonest — the second wins,
        and a reader could not tell which frame the scene was authored for.
        """
        code = _model_code().replace(
            "from manim import *",
            "from manim import *\n\nconfig.frame_width = 9.0\nconfig.frame_height = 16.0")
        written = write_code_scene(code, tmp_path, aspect=VERTICAL).read_text(encoding="utf-8")
        assert written.count("config.frame_width") == 1

    def test_landscape_code_is_left_exactly_as_reviewed(self, tmp_path):
        """The values would be Manim's own defaults, so the edit would change
        nothing — and this code has already cleared safety and review.
        """
        code = _model_code()
        written = write_code_scene(code, tmp_path, aspect=LANDSCAPE).read_text(encoding="utf-8")
        assert written == code + "\n"


# ------------------------------------------------------------ the pixel half

class TestCapturedRenderCarriesTheAspect:

    def _run(self, monkeypatch, tmp_path, aspect):
        captured = {}

        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd
            return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

        monkeypatch.setattr("straightedge.agent.executor.subprocess.run", fake_run)
        result = render_scene_captured(
            tmp_path / "scene.py", media_dir=tmp_path / "media", aspect=aspect)
        return captured["cmd"], result

    def test_a_vertical_render_asks_for_vertical_pixels(self, monkeypatch, tmp_path):
        cmd, _ = self._run(monkeypatch, tmp_path, VERTICAL)
        assert "-r" in cmd
        assert cmd[cmd.index("-r") + 1] == "480,854"

    def test_landscape_does_not_override_the_quality_flag(self, monkeypatch, tmp_path):
        cmd, _ = self._run(monkeypatch, tmp_path, LANDSCAPE)
        assert "-r" not in cmd
        assert "-ql" in cmd

    def test_the_vertical_output_is_looked_for_where_manim_writes_it(
            self, monkeypatch, tmp_path):
        """Filed under the pixel *height*, which for a rotated frame is the
        landscape width. Looking in ``480p15`` reports a good render as a
        failure — and the repair loop then feeds a clean scene back to the model
        as something to fix.
        """
        expected = (tmp_path / "media" / "videos" / "scene" / "854p15"
                    / f"{SCENE_CLASS_NAME}.mp4")
        expected.parent.mkdir(parents=True)
        expected.touch()
        _, result = self._run(monkeypatch, tmp_path, VERTICAL)
        assert result.output_path == expected


# ---------------------------------------------------------------- the prompt

class TestWriterPromptStatesShapeAndLanguage:
    """The model is handed a spec whose labels are Chinese in every case, so
    without an instruction it writes Chinese into the frame regardless of who
    the video is for.
    """

    def test_english_is_asked_for_explicitly(self):
        prompt = writer_user_prompt(_spec(), "STSong", LANDSCAPE, "en")
        assert "English" in prompt

    def test_chinese_is_asked_for_explicitly(self):
        prompt = writer_user_prompt(_spec(), "STSong", LANDSCAPE, "zh")
        assert "Chinese" in prompt
        assert "English" not in prompt

    def test_a_vertical_prompt_states_the_narrow_frame(self):
        prompt = writer_user_prompt(_spec(), "STSong", VERTICAL, "en")
        assert "9 units wide" in prompt
        assert "config.frame_width = 9.0" in prompt

    def test_the_dictated_preamble_matches_the_one_templates_emit(self):
        """These are two copies of the same preamble and this one had already
        fallen behind: it dictated a ``_t`` without the shrink-to-fit the
        templates gained, so LLM scenes kept drawing long labels off the edge
        after template scenes had stopped.
        """
        prompt = writer_user_prompt(_spec(), "STSong", LANDSCAPE, "en")
        assert "limit = config.frame_width * 0.92" in prompt
        assert "mob.scale(limit / mob.width)" in prompt


# ------------------------------------------------------- the catalog backstop

class TestModelOutputIsTranslated:

    def test_a_label_copied_from_the_spec_is_still_translated(self):
        """The model ignored the instruction and pasted the Chinese label
        through. The catalog knows this one precisely because it came from the
        spec rather than from the model's imagination.
        """
        client = FakeClient([_model_code("长轴")])
        code = write_code_with_llm(client, _spec(), font="STSong", language="en")
        assert '"major axis"' in code
        assert "长轴" not in code

    def test_asking_for_chinese_leaves_the_model_output_alone(self):
        client = FakeClient([_model_code("长轴")])
        code = write_code_with_llm(client, _spec(), font="STSong", language="zh")
        assert "长轴" in code

    def test_a_repair_cannot_silently_switch_the_language_back(self):
        """The repair prompt re-hands the model the Chinese spec, so a rewrite
        that touches a label tends to restore the Chinese the writer had already
        translated away — mid-render, in one scene.
        """
        client = FakeClient([_model_code("长轴")])
        code = repair_code_with_llm(client, _spec(), "old", "boom", "en")
        assert '"major axis"' in code

    def test_review_is_told_the_requested_shape_and_language(self):
        client = FakeClient([json.dumps({"approved": True, "issues": []})])
        review_code_with_llm(
            client, _spec(), _model_code("major axis"),
            aspect=VERTICAL, language="en")
        prompt = client.last_user_prompt()
        assert "9:16 vertical" in prompt
        assert "Requested labels:" in prompt
        assert "English" in prompt

    def test_repair_is_told_the_requested_shape_and_language(self):
        client = FakeClient([_model_code("major axis")])
        repair_code_with_llm(
            client, _spec(), "old", "boom", "en", aspect=VERTICAL)
        prompt = client.last_user_prompt()
        assert "9:16 vertical" in prompt
        assert "Requested labels:" in prompt
        assert "English" in prompt


# ------------------------------------------------------------ end to end

class TestOrchestratorPassesThemDown:

    def test_scaffold_writes_a_vertical_english_scene(self, tmp_path):
        client = FakeClient([
            _plan_json(),
            _model_code("长轴"),
            json.dumps({"approved": True, "issues": []}),
        ])
        result = run_agent_scaffold(
            "画一个椭圆", tmp_path, client=client, font="STSong",
            aspect=VERTICAL, language="en")
        written = result.scene_path.read_text(encoding="utf-8")
        assert "config.frame_width = 9.0" in written
        assert '"major axis"' in written

    def test_a_label_with_no_translation_is_reported_not_dropped(self, tmp_path):
        """A wrong-language caption is a reportable defect; a blank one looks
        like a render bug and loses the text entirely.
        """
        client = FakeClient([
            _plan_json(),
            _model_code("模型自己编的标签"),
            json.dumps({"approved": True, "issues": []}),
        ])
        result = run_agent_scaffold(
            "画一个椭圆", tmp_path, client=client, font="STSong", language="en")
        assert result.untranslated_labels == ("模型自己编的标签",)
        assert "模型自己编的标签" in result.scene_path.read_text(encoding="utf-8")

    def test_a_same_language_render_reports_nothing_missing(self, tmp_path):
        client = FakeClient([
            _plan_json(),
            _model_code("模型自己编的标签"),
            json.dumps({"approved": True, "issues": []}),
        ])
        result = run_agent_scaffold(
            "画一个椭圆", tmp_path, client=client, font="STSong", language="zh")
        assert result.untranslated_labels == ()

    def test_the_fallback_keeps_the_shape_and_language_that_were_asked_for(
            self, monkeypatch, tmp_path):
        """The worst available outcome is a fallback that reverts to landscape
        Chinese: the render succeeds, nothing reports a problem, and the caller
        gets a video in the wrong shape and language for its channel.
        """
        seen = []

        def fake_render(scene_path, quality="l", media_dir=None, aspect=LANDSCAPE):
            seen.append(aspect)
            return CapturedRenderResult(1, None, "render failed")

        monkeypatch.setattr(orchestrator, "render_scene_captured", fake_render)
        client = FakeClient([
            _plan_json(),
            _model_code(),
            json.dumps({"approved": True, "issues": []}),
            _model_code(),          # repair after the render failure
        ])

        result = run_agent_render(
            "画一个椭圆，显示焦点和长轴", tmp_path, tmp_path / "media",
            client=client, font="STSong", max_attempts=1,
            aspect=VERTICAL, language="en")

        assert result.fallback_used is True
        assert seen == [VERTICAL, VERTICAL]     # the LLM attempt and the fallback
        written = result.scene_path.read_text(encoding="utf-8")
        assert "config.frame_width = 9.0" in written
        assert "长轴" not in written


@pytest.mark.parametrize("aspect", [LANDSCAPE, VERTICAL])
def test_the_fallback_scene_is_valid_python_either_way(monkeypatch, tmp_path, aspect):
    monkeypatch.setattr(
        orchestrator, "render_scene_captured",
        lambda *a, **kw: CapturedRenderResult(1, None, "no manim"))
    client = FakeClient([
        _plan_json(), _model_code(),
        json.dumps({"approved": True, "issues": []}), _model_code(),
    ])
    result = run_agent_render(
        "画一个椭圆", tmp_path, tmp_path / "media", client=client,
        font="STSong", max_attempts=1, aspect=aspect, language="en")
    compile(result.scene_path.read_text(encoding="utf-8"), "scene.py", "exec")
