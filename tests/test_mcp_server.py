"""The MCP server: granular tools, failures as data, isolated renders.

The logic worth testing lives in the tool bodies, which are free of the SDK —
so most of this runs without the ``mcp`` extra installed. The handful that need
a real server (schema inference, the tool set) are gated on the SDK, because a
CI without the optional dependency should still exercise everything else.

The design claims under test: the tools are separate (an agent checks cheaply
before it renders), failures come back as ``{ok: false, error: {...}}`` rather
than exceptions, and each render is isolated so concurrent calls cannot collide.
"""

from __future__ import annotations

import pytest

from straightedge import mcp_server
from straightedge.errors import PreconditionError, StraightedgeError


class TestFailuresComeBackAsData:
    def test_a_straightedge_error_becomes_an_error_object(self):
        def boom():
            raise PreconditionError("no", remedy="try --force",
                                    details={"violations": ["v"]})
        result = mcp_server._guarded(boom)
        assert result["ok"] is False
        assert result["error"]["code"] == "blocking_precondition"
        assert result["error"]["remedy"] == "try --force"
        assert result["error"]["details"]["violations"] == ["v"]

    def test_a_bug_is_not_swallowed(self):
        """Only expected failures are data; a real bug must still surface."""
        def bug():
            raise KeyError("this is a bug, not a handled failure")
        with pytest.raises(KeyError):
            mcp_server._guarded(bug)


class TestPlanIsCheapAndComplete:
    def test_plan_returns_the_plan_and_violations(self):
        result = mcp_server._plan_payload("画 y=x^2 的导数")
        assert result["ok"] is True
        assert result["plan"]["concept"] == "calculus/derivative_tangent"
        assert "violations" in result["plan"]


class TestRenderGuardsBeforeSpending:
    def test_a_blocking_precondition_refuses_without_rendering(self, monkeypatch):
        """The whole point of separate tools: stop before the expensive step.

        render must not reach render_scene when a blocking precondition holds and
        force is off — the refusal has to be free.
        """
        from straightedge.preconditions import Violation

        monkeypatch.setattr(mcp_server, "_validate",
                            lambda plan: [Violation("c", "p", "boom")])
        called = []
        monkeypatch.setattr(mcp_server, "render_scene",
                            lambda *a, **k: called.append(1))

        result = mcp_server._guarded(lambda: mcp_server._render("画 y=sin(x)", "en", "l", force=False))
        assert result["ok"] is False
        assert result["error"]["code"] == "blocking_precondition"
        assert not called, "render_scene must not run when the plan is refused"

    def test_force_gets_past_the_refusal(self, monkeypatch, tmp_path):
        from straightedge.preconditions import Violation

        monkeypatch.setattr(mcp_server, "_validate",
                            lambda plan: [Violation("c", "p", "boom")])

        class Result:
            returncode = 0
            output_path = tmp_path / "GeneratedScene.mp4"

        def fake_render(scene, **kwargs):
            Result.output_path.write_bytes(b"mp4")
            return Result()

        monkeypatch.setattr(mcp_server, "render_scene", fake_render)
        monkeypatch.setattr(mcp_server, "check_sidecar", lambda p: [])

        result = mcp_server._guarded(lambda: mcp_server._render("画 y=sin(x)", "en", "l", force=True))
        assert result["ok"] is True
        assert result["output"].endswith(".mp4")

    def test_manim_stdout_is_routed_off_the_protocol_channel(self, monkeypatch,
                                                             tmp_path):
        """Stdio transport owns stdout; Manim must not print there.

        The failure a mock hides and a real render reveals — so assert the server
        hands render_scene a non-stdout target, which is the guard.
        """
        import sys
        from straightedge.preconditions import Violation

        monkeypatch.setattr(mcp_server, "_validate", lambda plan: [])
        seen = {}

        class Result:
            returncode = 0
            output_path = tmp_path / "GeneratedScene.mp4"

        def fake_render(scene, *, stdout=None, **kwargs):
            seen["stdout"] = stdout
            Result.output_path.write_bytes(b"mp4")
            return Result()

        monkeypatch.setattr(mcp_server, "render_scene", fake_render)
        monkeypatch.setattr(mcp_server, "check_sidecar", lambda p: [])
        mcp_server._render("画一个椭圆", "en", "l", force=False)
        assert seen["stdout"] is sys.stderr


class TestTheServer:
    """These need the SDK; skipped when the mcp extra is absent."""

    def _server(self):
        pytest.importorskip("mcp")
        return mcp_server.build_server()

    def test_it_exposes_the_four_granular_tools(self):
        import asyncio
        server = self._server()
        names = {t.name for t in asyncio.run(server.list_tools())}
        assert names == {"list_templates", "plan", "validate", "render"}

    def test_render_is_the_only_tool_with_a_force_switch(self):
        """A tool set an agent can read: the expensive one is the one you force."""
        import asyncio
        server = self._server()
        tools = {t.name: t for t in asyncio.run(server.list_tools())}
        assert "force" in tools["render"].input_schema["properties"]
        assert "force" not in tools["plan"].input_schema.get("properties", {})

    def test_missing_sdk_names_the_extra(self, monkeypatch):
        """If the SDK is absent, the error says which extra to install."""
        import builtins
        real_import = builtins.__import__

        def no_mcp(name, *args, **kwargs):
            if name.startswith("mcp"):
                raise ImportError("no mcp")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", no_mcp)
        with pytest.raises(StraightedgeError) as exc:
            mcp_server.build_server()
        assert "straightedge[mcp]" in (exc.value.remedy or "")


class TestTheFigureLaneIsReachable:
    """`list_templates` advertised both lanes; only one could be drawn.

    Every tool but `list_templates` reached the animation lane, so an agent saw
    the figure templates listed and had no way to draw any of them. Reported
    from a downstream plugin that had promised users those figures.
    """

    def test_a_figure_can_be_drawn(self):
        result = mcp_server._draw_payload("org_chart", {"root": {
            "name": "Ada Lovelace", "title": "CEO",
            "children": [{"name": "Grace Hopper", "title": "VP Engineering"}]}})
        assert result["ok"] and result["svg"].startswith("<svg")
        assert result["data_marks"] > 0 and result["blank"] is False

    def test_every_advertised_figure_template_is_drawable(self):
        """The listing and the draw tool read the same registry, so a template
        cannot be advertised by one and unreachable by the other."""
        from straightedge.diagrams import DIAGRAM_REGISTRY
        listed = {t["id"] for t in mcp_server.as_dicts() if t["lane"] == "figure"}
        assert listed == set(DIAGRAM_REGISTRY)
        for name in sorted(listed):
            assert mcp_server._draw_payload(name, {})["ok"]

    def test_an_empty_figure_is_reported_rather_than_hidden(self):
        """Chrome with no data reads exactly like a successful render."""
        result = mcp_server._draw_payload("org_chart", {"nothing": "usable"})
        assert result["ok"] and result["blank"] is True
        assert result["data_marks"] == 0 and result["bytes"] > 0

    def test_an_unknown_id_says_so_and_lists_the_real_ones(self):
        with pytest.raises(StraightedgeError) as excinfo:
            mcp_server._draw_payload("orgchart", {})
        error = excinfo.value
        assert error.code == "unknown_template"
        assert "org_chart" in error.details["known"]

    def test_a_missing_id_is_a_different_failure_from_a_wrong_one(self):
        """`no_request` sends an agent looking for a missing request; a typo is
        not that, and the two must not share a code."""
        with pytest.raises(StraightedgeError) as excinfo:
            mcp_server._draw_payload("", {})
        assert excinfo.value.code == "no_request"

    def test_drawing_needs_no_manim(self):
        """The figure lane is stdlib; this is what makes `draw` milliseconds."""
        import sys
        assert "manim" not in sys.modules
        assert mcp_server._draw_payload("unit_circle", {"angle": 30})["ok"]
