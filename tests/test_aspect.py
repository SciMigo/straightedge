"""Vertical renders: the frame, the pixels, and where the file lands.

Three facts here were established by rendering, not by reading docs, and each
one silently produces a wrong or missing video when guessed at:

* the output directory is named for the pixel *height*, so a 9:16 cut is filed
  under the landscape width;
* the frame must be set in the scene as well as on the command line;
* ``-r`` overrides the shape the quality flag implies but not its frame rate.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from straightedge.aspect import (
    ASPECTS, LANDSCAPE, VERTICAL, FRAME_UNITS, frame_config_source, frame_for,
    is_vertical, normalize, output_dir_name, resolution_for, with_frame_config,
)
from straightedge.calculus import ConceptCalculus
from straightedge.models import AnimationPlan, Topic
from straightedge.renderer import expected_output, manim_command, write_scene
from straightedge.templates import scene_code_for


def _plan():
    return AnimationPlan(
        topic=Topic.CALCULUS, title_zh="标题", objective_zh="目标",
        english_prompt="prompt", concept=ConceptCalculus.RIEMANN_INTEGRAL,
        parameters={"expression": "x**2"},
    )


class TestNormalize:

    def test_the_two_supported_aspects_pass_through(self):
        assert normalize("16:9") == LANDSCAPE
        assert normalize("9:16") == VERTICAL

    @pytest.mark.parametrize("value", [None, "", "  ", "4:3", "nonsense"])
    def test_anything_else_is_landscape_rather_than_an_error(self, value):
        """The aspect arrives from a payload that already validated it, so a
        second rejection here turns a typo into a crash deep in the renderer.
        """
        assert normalize(value) == LANDSCAPE

    def test_every_listed_aspect_has_a_frame(self):
        assert set(ASPECTS) == set(FRAME_UNITS)


class TestFrame:

    def test_vertical_is_taller_than_it_is_wide(self):
        width, height = frame_for(VERTICAL)
        assert height > width

    def test_landscape_keeps_manims_own_default(self):
        """Changing it would silently reframe every scene ever authored."""
        assert frame_for(LANDSCAPE) == (14.222222222222221, 8.0)

    def test_vertical_is_not_the_landscape_frame_transposed(self):
        """16 units tall is the point: a vertical cut has room to stack.

        Transposing landscape would give 8 wide by 14.2 tall, which is both a
        wrong aspect and a frame no scene is authored against.
        """
        assert frame_for(VERTICAL) == (9.0, 16.0)

    def test_is_vertical_agrees_with_the_frame(self):
        assert is_vertical(VERTICAL) is True
        assert is_vertical(LANDSCAPE) is False


class TestResolution:

    def test_vertical_swaps_the_pixels(self):
        assert resolution_for("h", LANDSCAPE) == (1920, 1080, 60)
        assert resolution_for("h", VERTICAL) == (1080, 1920, 60)

    def test_the_frame_rate_is_not_affected_by_aspect(self):
        """``-r`` overrides the shape the quality flag implies, not its fps."""
        for quality in ("l", "m", "h", "p", "k"):
            landscape = resolution_for(quality, LANDSCAPE)
            vertical = resolution_for(quality, VERTICAL)
            assert landscape[2] == vertical[2]

    def test_an_unknown_quality_is_none_rather_than_a_raise(self):
        assert resolution_for("ultra") is None


class TestOutputDirectory:

    def test_a_vertical_cut_is_filed_under_the_landscape_width(self):
        """Verified against Manim CE 0.20 by rendering: ``-ql -r 480,854``
        writes to ``854p15``. Assuming the quality flag names the folder makes a
        successful vertical render look like a failed one.
        """
        assert output_dir_name("l", VERTICAL) == "854p15"
        assert output_dir_name("l", LANDSCAPE) == "480p15"

    def test_landscape_names_are_manims_familiar_ones(self):
        assert output_dir_name("h") == "1080p60"
        assert output_dir_name("m") == "720p30"

    def test_an_unknown_quality_echoes_back(self):
        """Long-standing behaviour of ``expected_output``; a flag this table has
        not caught up with should still resolve to whatever Manim wrote.
        """
        assert output_dir_name("custom") == "custom"

    def test_expected_output_follows_the_aspect(self, tmp_path):
        scene = tmp_path / "scene.py"
        vertical = expected_output(scene, "l", tmp_path / "media", VERTICAL)
        landscape = expected_output(scene, "l", tmp_path / "media", LANDSCAPE)
        assert vertical.parent.name == "854p15"
        assert landscape.parent.name == "480p15"

    def test_expected_output_defaults_to_landscape(self, tmp_path):
        assert expected_output(Path("s.py"), "l", tmp_path).parent.name == "480p15"


class TestCommand:

    def test_vertical_asks_for_its_pixels_explicitly(self):
        argv = manim_command(Path("s.py"), "h", Path("media"), VERTICAL)
        assert "-r" in argv
        assert argv[argv.index("-r") + 1] == "1080,1920"

    def test_the_quality_flag_survives_the_override(self):
        """It still carries the frame rate; dropping it drops that too."""
        argv = manim_command(Path("s.py"), "h", Path("media"), VERTICAL)
        assert "-qh" in argv

    def test_landscape_adds_no_resolution_flag(self):
        """Unchanged argv for every existing caller."""
        assert "-r" not in manim_command(Path("s.py"), "h", Path("media"))


class TestSceneCarriesTheFrame:
    """The half a command-line flag cannot do.

    Pixels alone leave Manim deriving frame width from the default 8-unit
    height and the output ratio — 4.5 units across for 9:16 — so a scene
    authored for landscape draws off both sides of its own picture.
    """

    def test_a_vertical_scene_states_its_frame(self):
        source = scene_code_for(_plan(), aspect=VERTICAL)
        assert "config.frame_width = 9.0" in source
        assert "config.frame_height = 16.0" in source

    def test_a_landscape_scene_states_it_too(self):
        """Stated rather than left implicit, so the scene and QC cannot disagree."""
        source = scene_code_for(_plan())
        assert "config.frame_height = 8.0" in source

    def test_the_frame_is_set_before_the_scene_class(self):
        """Module scope, so it lands before the Scene is constructed."""
        source = scene_code_for(_plan(), aspect=VERTICAL)
        assert source.index("config.frame_width") < source.index("class GeneratedScene")

    def test_write_scene_carries_the_aspect_to_the_file(self, tmp_path):
        source = write_scene(_plan(), tmp_path, aspect=VERTICAL).read_text(encoding="utf-8")
        assert "config.frame_width = 9.0" in source


class TestFrameConfigSource:
    """One definition of the two lines a scene states its frame with.

    Both the template preamble and the LLM writer prompt need them, and the
    prompt's hand-copied version had already drifted — a frame declaration that
    disagrees with the renderer is worse than a missing one, because the scene
    then composes against numbers nothing is using.
    """

    def test_it_states_the_frame_for_the_aspect(self):
        assert "config.frame_width = 9.0" in frame_config_source(VERTICAL)
        assert "config.frame_height = 16.0" in frame_config_source(VERTICAL)

    def test_it_is_executable_python(self):
        compile(frame_config_source(LANDSCAPE), "<preamble>", "exec")

    def test_the_generated_preamble_uses_it_verbatim(self):
        """Otherwise the two drift again, quietly, in the same direction."""
        assert frame_config_source(VERTICAL) in scene_code_for(_plan(), aspect=VERTICAL)


class TestWithFrameConfig:

    SOURCE = "from manim import *\n\n\nclass GeneratedScene(Scene):\n    pass\n"

    def test_a_vertical_scene_missing_its_frame_gets_one(self):
        assert "config.frame_width = 9.0" in with_frame_config(self.SOURCE, VERTICAL)

    def test_the_result_is_still_valid_python(self):
        compile(with_frame_config(self.SOURCE, VERTICAL), "<scene>", "exec")

    def test_landscape_is_left_untouched(self):
        """Manim's own defaults, so the injection would change nothing — and for
        model-authored code the edit would diverge from what review approved.
        """
        assert with_frame_config(self.SOURCE, LANDSCAPE) == self.SOURCE

    def test_an_existing_declaration_is_respected(self):
        already = "from manim import *\nconfig.frame_width = 5.0\nconfig.frame_height = 9.0\n"
        assert with_frame_config(already, VERTICAL) == already

    def test_a_half_declaration_is_not_treated_as_a_declaration(self):
        """Width alone leaves the height at the landscape default, which is the
        broken state the injection exists to fix.
        """
        half = "from manim import *\nconfig.frame_width = 9.0\n"
        assert "config.frame_height" in with_frame_config(half, VERTICAL)

    def test_it_lands_below_the_import_that_defines_config(self):
        lines = with_frame_config(self.SOURCE, VERTICAL).splitlines()
        assert lines.index("config.frame_width = 9.0") > lines.index("from manim import *")

    def test_code_with_no_manim_import_still_gets_the_frame(self):
        """Not valid Manim, but the safety checker — not this — is what rejects
        it. Dropping the frame here would be a second, silent failure.
        """
        assert "config.frame_width" in with_frame_config("x = 1\n", VERTICAL)


class TestChosenFrameRate:
    """1080p30, which no quality letter can express.

    `-qh` bundles 1080p with 60fps. For a narrated proof the extra frames buy
    nothing anybody watching can see, and they are 45% of the render: measured
    2026-08-08 on one real scene, 306s at 60fps against 168s at 30fps.
    """

    def test_the_rate_overrides_what_the_quality_letter_implies(self):
        assert resolution_for("h") == (1920, 1080, 60)
        assert resolution_for("h", LANDSCAPE, 30) == (1920, 1080, 30)

    def test_the_resolution_is_untouched_by_the_rate(self):
        """Only the frame rate changes; 1080p30 is still 1080p."""
        width, height, _ = resolution_for("h", LANDSCAPE, 30)
        assert (width, height) == (1920, 1080)

    def test_a_vertical_cut_keeps_its_shape_and_takes_the_rate(self):
        assert resolution_for("h", VERTICAL, 30) == (1080, 1920, 30)

    def test_the_directory_is_named_for_the_rate_that_was_asked_for(self):
        assert output_dir_name("h", LANDSCAPE, 30) == "1080p30"
        assert output_dir_name("h", VERTICAL, 30) == "1920p30"

    def test_the_command_states_the_rate(self):
        argv = manim_command(Path("s.py"), "h", Path("media"), LANDSCAPE, 30)
        assert argv[argv.index("--fps") + 1] == "30"

    def test_an_unstated_rate_stays_off_the_command_line(self):
        """So the default render is byte-identical to what shipped before."""
        assert "--fps" not in manim_command(Path("s.py"), "h", Path("media"))

    @pytest.mark.parametrize("quality", ["l", "m", "h"])
    @pytest.mark.parametrize("aspect", [LANDSCAPE, VERTICAL])
    @pytest.mark.parametrize("fps", [None, 24, 30, 60])
    def test_the_command_and_the_expected_path_cannot_disagree(
        self, tmp_path, quality, aspect, fps
    ):
        """The one invariant that matters, across every combination.

        Manim files output under `{pixel_height}p{fps}`. If the argv says one
        rate and the resolver looks under another, the render succeeds and is
        reported as a failure, because nothing wrote to the directory being
        searched. Two functions have to agree about a name neither of them
        owns, which is exactly the pairing that rots.
        """
        argv = manim_command(tmp_path / "s.py", quality, tmp_path, aspect, fps)
        path = expected_output(tmp_path / "s.py", quality, tmp_path, aspect, fps)

        stated = int(argv[argv.index("--fps") + 1]) if "--fps" in argv else None
        _, pixel_height, effective = resolution_for(quality, aspect, fps)
        assert path.parent.name == f"{pixel_height}p{effective}"
        assert stated in (None, effective)
