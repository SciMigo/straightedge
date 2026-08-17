import json
import subprocess
import sys

import pytest

from straightedge.agent.executor import render_scene_captured
from straightedge.agent.llm import OpenAICompatibleClient
from straightedge.agent.orchestrator import run_agent_plan, run_agent_scaffold
from straightedge.agent.safety import check_scene_code
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


def _safe_code():
    return '''
from manim import *

CJK_FONT = "STSong"

def _t(text, **kwargs):
    kwargs.setdefault("font", CJK_FONT)
    return Text(text, **kwargs)

class GeneratedScene(Scene):
    def construct(self):
        self.play(Write(_t("测试")))
        self.wait(1)
'''.strip()


def test_agent_plan_uses_json_spec():
    client = FakeClient([
        json.dumps({
            "language": "zh",
            "topic": "calculus",
            "concept": "taylor_series",
            "title_zh": "泰勒展开",
            "objective_zh": "展示逼近",
            "math_objects": ["axes"],
            "animation_steps": ["draw"],
            "labels_zh": ["标签"],
            "narration_zh": ["旁白"],
            "constraints": {"scene_class": "GeneratedScene"},
        })
    ])

    spec = run_agent_plan("展示泰勒展开", client=client)

    assert spec.topic == "calculus"
    assert spec.concept == "taylor_series"
    assert spec.source_request_zh == "展示泰勒展开"


def test_agent_scaffold_writes_reviewed_code(tmp_path):
    client = FakeClient([
        json.dumps({
            "language": "zh",
            "topic": "calculus",
            "concept": "generated",
            "title_zh": "测试",
            "objective_zh": "测试",
        }),
        _safe_code(),
        json.dumps({"approved": True, "issues": []}),
    ])

    result = run_agent_scaffold("画一个测试动画", tmp_path, client=client, font="STSong")

    assert result.scene_path == tmp_path / "scene.py"
    assert result.scene_path.exists()
    assert "class GeneratedScene" in result.scene_path.read_text(encoding="utf-8")
    assert result.validated is True


def test_agent_scaffold_reports_unvalidated_when_guardrails_never_clear(tmp_path):
    # Writer keeps emitting code that fails the safety check; after the repair
    # budget is exhausted the scene is still written but flagged unvalidated.
    unsafe = '''
from manim import *
import os

class GeneratedScene(Scene):
    def construct(self):
        self.wait(1)
'''.strip()
    client = FakeClient([
        json.dumps({
            "language": "zh",
            "topic": "calculus",
            "concept": "generated",
            "title_zh": "测试",
            "objective_zh": "测试",
        }),
        unsafe,  # initial writer output
        unsafe,  # repair attempt 1
        unsafe,  # repair attempt 2
    ])

    result = run_agent_scaffold(
        "画一个测试动画", tmp_path, client=client, font="STSong", max_attempts=2
    )

    assert result.validated is False
    assert result.scene_path.exists()


def test_safety_rejects_dangerous_code():
    result = check_scene_code(
        '''
from manim import *
import os

class GeneratedScene(Scene):
    def construct(self):
        open("x", "w")
'''
    )

    assert not result.ok
    assert any("Disallowed import" in error for error in result.errors)
    assert any("Disallowed call" in error for error in result.errors)


def test_safety_accepts_basic_scene_code():
    result = check_scene_code(_safe_code())
    assert result.ok
    assert result.errors == []


def test_safety_accepts_math_and_numpy_imports():
    result = check_scene_code(
        '''
from manim import *
import math
from numpy.linalg import norm

class GeneratedScene(Scene):
    def construct(self):
        point = np.array([math.cos(0), math.sin(0), 0])
        self.add(Dot(point * norm(point)))
'''
    )

    assert result.ok
    assert result.errors == []


@pytest.mark.parametrize(
    "unsafe_import",
    [
        "from manim.utils.commands import capture",
        "import manim.utils.file_ops as file_ops",
        "import numpy as np",
        "from numpy import save",
        "import numpy.ctypeslib",
    ],
)
def test_safety_rejects_shell_filesystem_and_broad_numpy_imports(unsafe_import):
    result = check_scene_code(
        f'''\
from manim import *
{unsafe_import}

class GeneratedScene(Scene):
    def construct(self):
        self.wait(1)
'''
    )

    assert not result.ok
    assert any("Disallowed import" in error for error in result.errors)


def _scene(body: str) -> str:
    return (
        "from manim import *\n"
        "class GeneratedScene(Scene):\n"
        "    def construct(self):\n"
        f"        {body}\n"
    )


@pytest.mark.parametrize("call", [
    # The verified hole: getattr reaches any builtin by a *string*, so the name
    # allowlist and the dunder-attribute rule are both bypassed by constructing
    # the name rather than writing it.
    "getattr(__builtins__, chr(111)+chr(112)+chr(101)+chr(110))('x','w')",
    "getattr(object, '__sub' + 'classes__')",
    "setattr(self, 'x', 1)",
    "delattr(self, 'x')",
])
def test_safety_rejects_the_getattr_family(call):
    """getattr/setattr/delattr are the door in the allowlist — reaching a name
    the checker would reject if it were written literally."""
    result = check_scene_code(_scene(call))
    assert not result.ok
    assert any("Disallowed call" in e for e in result.errors)


@pytest.mark.parametrize("expr", [
    "b = __builtins__",                          # the back door as a bare name
    "c = ().__class__",                          # the start of the usual escape
    "s = ().__class__.__bases__[0].__subclasses__()",
    "g = (lambda: 0).__globals__",
])
def test_safety_rejects_reaching_interpreter_internals(expr):
    """A dunder reached as a name or an attribute is out — the escape chain runs
    through ``__class__`` / ``__subclasses__`` / ``__globals__`` / ``__builtins__``,
    and none of those belong in a scene."""
    result = check_scene_code(_scene(expr))
    assert not result.ok
    assert any("dunder" in e for e in result.errors)


def test_safety_still_accepts_a_scene_using_underscored_helpers():
    """The rule is dunders, not single underscores — the emitted preamble uses
    ``_t`` and ``_beat``, which must stay allowed."""
    result = check_scene_code(_scene("_t('hi'); _beat(self, 'b01')"))
    assert result.ok, result.errors


def test_llm_client_allows_slow_reasoning_by_default(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("STRAIGHTEDGE_LLM_TIMEOUT", raising=False)

    client = OpenAICompatibleClient.from_env()

    assert client.config.timeout == 300.0


def test_llm_timeout_can_be_lowered(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("STRAIGHTEDGE_LLM_TIMEOUT", "45")

    client = OpenAICompatibleClient.from_env()

    assert client.config.timeout == 45.0


def test_captured_render_builds_command_and_logs(monkeypatch, tmp_path):
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(cmd, returncode=1, stdout="out", stderr="err")

    monkeypatch.setattr("straightedge.agent.executor.subprocess.run", fake_run)

    result = render_scene_captured(tmp_path / "scene.py", media_dir=tmp_path / "media")

    assert captured["cmd"][:3] == [sys.executable, "-m", "manim"]
    assert SCENE_CLASS_NAME in captured["cmd"]
    assert captured["kwargs"]["capture_output"] is True
    assert result.returncode == 1
    assert result.logs == "outerr"
