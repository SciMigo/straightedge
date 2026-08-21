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

import pathlib
import sys

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
        # These mock render_scene, so the host runtime is irrelevant here.
        monkeypatch.setattr(mcp_server, "_missing_render_runtime", lambda: [])

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

        # These mock render_scene, so the host runtime is irrelevant here.
        monkeypatch.setattr(mcp_server, "_missing_render_runtime", lambda: [])

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

    def test_it_exposes_the_granular_tools(self):
        """One per question an agent asks, and the set is asserted exactly.

        An exact set is the point: a tool added without a thought for the shape
        of the whole fails here rather than quietly widening the surface.

        `render` is in the set only where it can run. Everything else needs
        nothing but the standard library, which is why the rest is unconditional.
        """
        import asyncio
        server = self._server()
        names = {t.name for t in asyncio.run(server.list_tools())}
        expected = {"list_templates", "draw", "verify_construction",
                    "plan", "validate"}
        if not mcp_server._missing_render_runtime():
            expected.add("render")
        assert names == expected

    def test_render_is_the_only_tool_with_a_force_switch(self):
        """A tool set an agent can read: the expensive one is the one you force."""
        import asyncio
        server = self._server()
        tools = {t.name: t for t in asyncio.run(server.list_tools())}
        if "render" not in tools:
            pytest.skip("this host cannot render; the tool is not offered")
        assert "force" in tools["render"].input_schema["properties"]
        assert "force" not in tools["plan"].input_schema.get("properties", {})


class TestRenderIsOfferedOnlyWhereItRuns:
    """A tool that cannot work is worse than a tool that is not there.

    The animation lane needs Manim, ffmpeg, LaTeX and dvisvgm; pip installs one
    of them. Advertised regardless, `render` was a tool an agent picks because
    it is listed, waits on, and gets a dependency error from. The guard that
    raises that error already existed -- it fired after the caller had
    committed, which is the wrong end of the call.
    """

    def _names(self, monkeypatch, missing):
        import asyncio
        pytest.importorskip("mcp")
        monkeypatch.setattr(mcp_server, "_missing_render_runtime", lambda: missing)
        return {t.name for t in asyncio.run(mcp_server.build_server().list_tools())}

    def test_it_is_absent_when_the_runtime_is(self, monkeypatch):
        names = self._names(monkeypatch, ["manim", "ffmpeg"])
        assert "render" not in names

    def test_it_is_there_when_the_runtime_is(self, monkeypatch):
        assert "render" in self._names(monkeypatch, [])

    def test_the_figure_lane_never_depends_on_it(self, monkeypatch):
        """`draw` is pure standard library, and `plan` and `validate` only
        decide things. None of them should vanish with the renderer."""
        names = self._names(monkeypatch, ["manim", "ffmpeg", "a LaTeX distribution"])
        assert {"list_templates", "draw", "verify_construction",
                "plan", "validate"} <= names

    def test_the_absence_is_explained_rather_than_silent(self, monkeypatch):
        """An agent reading five tools and no renderer should not have to
        work out why, or conclude the lane does not exist."""
        monkeypatch.setattr(mcp_server, "_missing_render_runtime",
                            lambda: ["manim", "ffmpeg"])
        note = mcp_server._lane_note()
        assert "manim" in note and "ffmpeg" in note
        assert "draw" in note, "it should say what still works"

    def test_nothing_is_said_when_everything_is_present(self, monkeypatch):
        monkeypatch.setattr(mcp_server, "_missing_render_runtime", lambda: [])
        assert mcp_server._lane_note() == ""

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


class TestTheGatedTestsActuallyRun:
    """The declaration, not the environment.

    `test_it_exposes_the_granular_tools` is guarded by `importorskip("mcp")` and
    CI installs `.[dev]`. When that extra did not carry the SDK the guard turned
    the check into a permanent skip, and a stale assertion outlived a tool being
    added while every build stayed green.

    This reads `pyproject.toml` rather than asking whether `mcp` imports, because
    an import check passes in any environment where someone installed it by hand
    — which is exactly how the missing declaration was verified as present and
    written up as fixed. What has to be true is that the *declared* test extra
    installs the SDK, and only the file says that.
    """

    @staticmethod
    def _dev_extra() -> str:
        root = pathlib.Path(__file__).resolve().parent.parent
        for line in (root / "pyproject.toml").read_text().splitlines():
            if line.startswith("dev = "):
                return line
        raise AssertionError("no dev extra declared in pyproject.toml")

    def test_the_dev_extra_installs_the_sdk_the_gated_tests_need(self):
        assert "mcp" in self._dev_extra(), (
            "tests/test_mcp_server.py guards on importorskip('mcp'); without the "
            "SDK in the dev extra those checks silently never run in CI")


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
            # Reachability, not output: a template given no parameters may
            # legitimately have nothing to draw, and that now comes back as
            # blank_figure. What must never happen is unknown_template.
            out = mcp_server._guarded(lambda n=name: mcp_server._draw_payload(n, {}))
            assert out["ok"] or out["error"]["code"] == "blank_figure", name

    def test_an_empty_figure_is_a_failure_not_a_quiet_flag(self):
        """Chrome with no data reads exactly like a successful render, so the
        tool must not answer `ok: true` — it can already tell from its own mark
        count that nothing landed."""
        out = mcp_server._guarded(
            lambda: mcp_server._draw_payload("org_chart", {"nothing": "usable"}))

        assert out["ok"] is False
        assert out["error"]["code"] == "blank_figure"
        assert out["error"]["details"]["type"] == "org_chart"

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

    def test_bytes_are_bytes_not_characters(self):
        """CJK labels made `len(svg)` under-report the payload by 44 bytes.

        A field named `bytes` that counts code points is worse than no field: a
        caller sizing a buffer or a quota from it is wrong by exactly the amount
        of non-ASCII in the figure.
        """
        result = mcp_server._draw_payload("org_chart", {"root": {
            "name": "艾达·洛夫莱斯", "title": "首席执行官",
            "children": [{"name": "格蕾丝·霍珀", "title": "工程副总裁"}]}})
        assert result["bytes"] == len(result["svg"].encode("utf-8"))
        assert result["characters"] == len(result["svg"])
        assert result["bytes"] > result["characters"], "no multi-byte glyph in the fixture"

    def test_bytes_and_characters_agree_on_ascii(self):
        result = mcp_server._draw_payload("org_chart", {"root": {
            "name": "Ada Lovelace", "title": "CEO"}})
        assert result["bytes"] == result["characters"]

    def test_drawing_needs_no_manim(self):
        """The figure lane is stdlib; this is what makes `draw` milliseconds."""
        import sys
        assert "manim" not in sys.modules
        assert mcp_server._draw_payload("unit_circle", {"angle": 30})["ok"]


class TestABlankFigureIsAFailure:
    """A template handed a value it cannot read draws its frame and no data.

    That is the one failure that looks exactly like success, and the tool can
    tell from its own mark count — so it must not answer `ok: true`.
    """

    def test_a_figure_with_no_marks_comes_back_as_an_error(self):
        out = mcp_server._guarded(
            lambda: mcp_server._draw_payload("unit_circle", {"angle": "pi/4"}))

        assert out["ok"] is False
        assert out["error"]["code"] == "blank_figure"

    def test_the_failure_carries_the_shapes_the_caller_got_wrong(self):
        """An agent asked for the unit circle at "pi/4"; nothing in the response
        said `angle` is a number of degrees, so it could not correct itself."""
        out = mcp_server._guarded(
            lambda: mcp_server._draw_payload("unit_circle", {"angle": "pi/4"}))
        details = out["error"]["details"]
        angle = [p for p in details["parameters"] if p["name"] == "angle"][0]

        assert angle["type"] == "number"
        assert angle["default"] == 45
        assert details["given"] == ["angle"]
        assert out["error"]["remedy"]

    def test_a_figure_that_draws_still_succeeds(self):
        out = mcp_server._draw_payload("unit_circle", {"angle": 45})

        assert out["ok"] is True and out["blank"] is False
        assert out["data_marks"] > 0 and out["bytes"] > 0


class TestTheAnimationLaneNamesWhatItNeeds:
    def test_a_host_without_the_runtime_says_which_part_is_missing(self, monkeypatch):
        """It failed deep in the pipeline with "Manim ran but did not produce the
        expected file", which sends a caller to their plan rather than their host."""
        monkeypatch.setattr(mcp_server, "_missing_render_runtime",
                            lambda: ["manim (pip install 'straightedge[render]')"])
        monkeypatch.setattr(mcp_server, "_plan_for", lambda *a, **k: object())
        monkeypatch.setattr(mcp_server, "_validate", lambda plan: [])
        out = mcp_server._guarded(
            lambda: mcp_server._render("", "en", "l", False, template="x"))

        assert out["ok"] is False
        assert out["error"]["code"] == "dependency_missing"
        assert "manim" in out["error"]["details"]["missing"][0]
        assert "draw" in out["error"]["remedy"]

    def test_the_check_is_per_component(self, monkeypatch):
        monkeypatch.setattr(mcp_server.shutil, "which", lambda _b: None)
        missing = mcp_server._missing_render_runtime()

        assert any("ffmpeg" in item for item in missing)
        assert any("LaTeX" in item for item in missing)

    def test_the_whole_latex_chain_is_checked_not_just_its_headline(self, monkeypatch):
        """Scenes use MathTex, so Manim goes LaTeX -> DVI -> SVG. A host with
        manim, ffmpeg and latex but no dvisvgm passed the guard and still failed
        deep in the render — the failure it exists to pre-empt."""
        monkeypatch.setitem(sys.modules, "manim", object())
        monkeypatch.setattr(mcp_server.shutil, "which",
                            lambda binary: None if binary == "dvisvgm" else "/usr/bin/" + binary)
        monkeypatch.setattr(mcp_server, "_tex_has", lambda _cls: True)

        assert mcp_server._missing_render_runtime() == [
            "dvisvgm (Manim's DVI to SVG step)"]

    def test_a_tex_install_missing_the_class_the_preamble_asks_for(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "manim", object())
        monkeypatch.setattr(mcp_server.shutil, "which", lambda binary: "/usr/bin/" + binary)
        monkeypatch.setattr(mcp_server, "_tex_has", lambda _cls: False)

        assert mcp_server._missing_render_runtime() == [
            "standalone.cls (texlive-latex-extra)"]

    def test_an_unanswerable_probe_is_not_reported_as_missing(self, monkeypatch):
        """kpsewhich absent means unknown, not absent. Reporting a guess sends a
        caller to install something they may already have."""
        monkeypatch.setitem(sys.modules, "manim", object())
        monkeypatch.setattr(
            mcp_server.shutil, "which",
            lambda binary: None if binary == "kpsewhich" else "/usr/bin/" + binary)

        assert mcp_server._missing_render_runtime() == []

    def test_a_probe_that_cannot_run_answers_unknown(self, monkeypatch):
        def boom(*_a, **_k):
            raise OSError("kpsewhich exploded")

        monkeypatch.setattr(mcp_server.subprocess, "run", boom)
        assert mcp_server._tex_has("standalone.cls") is True


class TestTemplatesDeclareTheirParameterShapes:
    def test_a_figure_template_reports_types_and_defaults(self):
        from straightedge.catalog import list_templates

        unit_circle = [t for t in list_templates() if t.id == "unit_circle"][0]
        by_name = {p["name"]: p for p in unit_circle.parameters}

        assert by_name["angle"] == {"name": "angle", "type": "number", "default": 45}
        assert by_name["show_tan"]["type"] == "boolean"

    def test_names_are_still_reported_beside_the_shapes(self):
        from straightedge.catalog import list_templates

        for template in list_templates():
            named = {p["name"] for p in template.parameters}
            assert set(template.params) <= named


class TestConstructionsCanBeCheckedBeforeTheyAreDrawn:
    """`draw` refuses a construction whose claim is false and returns a blank.

    A template returns a string and has nowhere to put findings, so the refusal
    arrives with no reason attached. `verify_construction` is where the reasons
    live — the same economics as `validate` before `render`, at a smaller scale.
    """

    VESICA = "A = 0, 0\nB = 1, 0\n( A B )\n( B A )\n[ C D ]\n[ A B ]\n"

    def test_a_true_claim_holds_and_would_draw(self):
        result = mcp_server._verify_payload(
            self.VESICA, [{"claim": "perpendicular", "of": ["[ C D ]", "[ A B ]"]}])
        assert result["ok"] and result["holds"] and result["would_draw"]
        assert result["findings"] == [] and result["worst"] is None

    def test_a_false_claim_says_so_and_says_draw_will_refuse(self):
        result = mcp_server._verify_payload(
            self.VESICA, [{"claim": "parallel", "of": ["[ C D ]", "[ A B ]"]}])
        assert not result["holds"] and result["worst"] == "error"
        assert result["would_draw"] is False

    def test_the_verdict_agrees_with_what_draw_actually_does(self):
        """`would_draw` is a claim about another tool; it has to be true."""
        for claim, expected in (("perpendicular", True), ("parallel", False)):
            claims = [{"claim": claim, "of": ["[ C D ]", "[ A B ]"]}]
            verdict = mcp_server._verify_payload(self.VESICA, claims)["would_draw"]
            out = mcp_server._guarded(lambda: mcp_server._draw_payload(
                "construction", {"steps": self.VESICA, "claims": claims}))
            assert verdict is expected and out["ok"] is expected

    def test_a_refusal_is_not_reported_as_a_parameter_mistake(self):
        """A construction blocked by a false claim has correct parameters.

        `draw` raises `blank_figure` for anything with no marks, and its remedy
        sends the caller to check parameter shapes — right for a template handed
        a value it cannot read, and wrong here, where the input is fine and the
        assertion is not. The refusal says which claim failed instead.
        """
        out = mcp_server._guarded(lambda: mcp_server._draw_payload(
            "construction", {"steps": self.VESICA, "claims": [
                {"claim": "parallel", "of": ["[ C D ]", "[ A B ]"]}]}))
        error = out["error"]
        assert error["code"] == "blank_figure"
        assert "refused" in error["message"]
        assert "parameter" not in error["remedy"].split("The parameters")[0]
        assert "verify_construction" in error["remedy"]
        [finding] = error["details"]["findings"]
        assert finding["check"] == "claim:parallel"

    def test_an_unreadable_parameter_still_reports_the_shapes(self):
        """The other branch must keep #9's behaviour intact."""
        out = mcp_server._guarded(lambda: mcp_server._draw_payload(
            "construction", {"steps": "this is not a construction"}))
        assert out["error"]["code"] == "blank_figure"
        assert "parameters" in out["error"]["details"]

    def test_a_notation_error_comes_back_as_a_finding_with_its_line(self):
        result = mcp_server._verify_payload("A = 0, 0\n[ A ", [])
        assert result["findings"][0]["check"] == "construction:notation"
        assert "line 2" in result["findings"][0]["message"]

    def test_no_steps_is_a_typed_refusal(self):
        with pytest.raises(StraightedgeError) as excinfo:
            mcp_server._verify_payload(None, [])
        assert excinfo.value.code == "no_request"

    def test_verifying_costs_no_drawing(self):
        """It returns findings, never an SVG — that is the point of it."""
        result = mcp_server._verify_payload(self.VESICA, [])
        assert "svg" not in result


class TestABrokenOptionalExtraDoesNotStopTheServer:
    """Manim is a stack of native libraries — cairo, pango, an ffmpeg binding —
    and any of them can fail to load with `OSError` or `RuntimeError` rather
    than `ImportError`.

    The probe caught only `ImportError`. While it ran inside `render` that was
    survivable: one tool failed. Running it at startup to decide whether to
    offer that tool made it fatal — a broken *optional* extra took down `draw`,
    `plan`, `validate` and every other pure-standard-library tool with it.
    """

    def _with_manim_raising(self, monkeypatch, exc):
        import builtins

        real = builtins.__import__

        def fake(name, *args, **kwargs):
            if name == "manim":
                raise exc
            return real(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake)

    @pytest.mark.parametrize("exc", [
        OSError("cannot load library 'libpangocairo-1.0.so.0'"),
        RuntimeError("cairo returned an unexpected status"),
        ImportError("No module named 'manim'"),
    ])
    def test_the_probe_reports_rather_than_raises(self, monkeypatch, exc):
        self._with_manim_raising(monkeypatch, exc)
        missing = mcp_server._missing_render_runtime()
        assert any("manim" in note for note in missing), missing

    def test_the_server_still_builds(self, monkeypatch):
        import asyncio

        pytest.importorskip("mcp")
        self._with_manim_raising(monkeypatch, OSError("libpango is missing"))
        names = {t.name for t in asyncio.run(mcp_server.build_server().list_tools())}
        assert {"list_templates", "draw", "verify_construction",
                "plan", "validate"} <= names
        assert "render" not in names

    def test_the_note_says_it_is_installed_but_unusable(self, monkeypatch):
        """"Install manim" is the wrong advice for a manim that is installed."""
        self._with_manim_raising(monkeypatch, OSError("libpango is missing"))
        note = next(n for n in mcp_server._missing_render_runtime() if "manim" in n)
        assert "installed" in note and "OSError" in note
