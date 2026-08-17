"""Generated scenes carry a themed palette, baked in rather than imported.

The emitted scene has to keep a property that predates this feature: it renders
on a host with Manim and **no straightedge** (see ``templates.qc_tail_source``).
So a theme cannot be an import — it is resolved at generation time and written
into the source as hex literals. These tests pin that, and pin the two ways the
port could silently rot:

* a builder that goes back to a bare ``YELLOW`` still renders, looks fine, and
  quietly stops following the theme — nothing at runtime can notice;
* the default drifting off ``TEXTBOOK`` would restyle every existing render.
"""

from __future__ import annotations

import ast
import re

import pytest

from straightedge.catalog import CANONICAL_PROMPTS
from straightedge.models import AnimationPlan
from straightedge.style import DATAFLOW, PAPER, TEXTBOOK, THEMES
from straightedge.templates import scene_code_for

CONCEPTS = sorted(CANONICAL_PROMPTS)

#: Manim colour names no builder should mention any more. Each one still
#: *resolves* in the emitted scene — ``from manim import *`` supplies it — which
#: is exactly why a test has to look: the failure is invisible at runtime.
BARE_MANIM_COLOURS = re.compile(
    r"\b(BLACK|WHITE|GRAY|GREY|GREY_[A-E]|GRAY_[A-E]|BLUE|BLUE_[A-E]|GREEN|"
    r"GREEN_[A-E]|YELLOW|YELLOW_[A-E]|RED|RED_[A-E]|ORANGE|TEAL|TEAL_[A-E]|"
    r"GOLD|PURPLE|MAROON|PINK)\b"
)

#: The role tokens the palette block defines.
ROLE_TOKENS = ("C_FG", "C_MUTED", "C_DIM", "C_RULE", "C_INK", "C_WELL",
               "C_FLOW", "C_HOLD", "C_DEEP", "C_DONE", "C_WARN", "C_AUX",
               "C_WARM")


def _plan(concept: str) -> AnimationPlan:
    return AnimationPlan(topic=concept.split("/")[0], title_zh="t",
                         objective_zh="o", english_prompt="p", concept=concept)


def _palette_of(source: str) -> dict[str, str]:
    """The ``C_NAME = ManimColor("#hex")`` assignments the preamble emitted."""
    return dict(re.findall(r'^(C_[A-Z_]+) = ManimColor\("(#[0-9a-fA-F]{6})"\)$',
                           source, re.MULTILINE))


# --- the palette is present, complete, and used -----------------------------


@pytest.mark.parametrize("concept", CONCEPTS)
def test_every_concept_emits_a_complete_palette(concept):
    palette = _palette_of(scene_code_for(_plan(concept)))
    missing = [t for t in ROLE_TOKENS if t not in palette]
    assert not missing, f"{concept} is missing {missing}"


@pytest.mark.parametrize("concept", CONCEPTS)
def test_no_builder_reaches_for_a_bare_manim_colour(concept):
    """The regression that cannot be caught at runtime."""
    source = scene_code_for(_plan(concept))
    # Strip the palette block itself: its values are hex strings, and its
    # comment is allowed to name what it replaced.
    body = "\n".join(line for line in source.splitlines()
                     if not line.strip().startswith("C_"))
    found = sorted(set(BARE_MANIM_COLOURS.findall(body)))
    assert not found, (
        f"{concept} draws with {found} instead of a C_* role token, so it will "
        f"ignore the chosen style"
    )


@pytest.mark.parametrize("concept", CONCEPTS)
def test_the_generated_scene_is_valid_python(concept):
    ast.parse(scene_code_for(_plan(concept)))


@pytest.mark.parametrize("concept", CONCEPTS)
def test_the_generated_scene_does_not_import_straightedge(concept):
    """The render host may not have this package. A baked palette is why it can.

    ``qc_sidecar`` is the one opt-in that breaks this, and it is off by default.

    Checked against the parsed tree rather than the text: the palette block's own
    comment says where the colours came from, and a substring search would call
    that a dependency.
    """
    tree = ast.parse(scene_code_for(_plan(concept)))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert "straightedge" not in imported, (
        f"{concept} imports straightedge, so it cannot render on a host that "
        f"only has Manim"
    )


# --- the default changes nothing --------------------------------------------


def test_the_default_style_is_textbook():
    """Manim's own palette — what these builders drew with before the port."""
    palette = _palette_of(scene_code_for(_plan("calculus/riemann_integral")))
    assert palette["C_HOLD"] == TEXTBOOK.hold
    assert palette["C_DONE"] == TEXTBOOK.done
    assert palette["C_FLOW"] == TEXTBOOK.flow
    assert palette["C_WARN"] == TEXTBOOK.warn


def test_the_default_matches_manims_constants():
    """Belt and braces: the emitted hexes are Manim's, so no pixel moved."""
    colour = pytest.importorskip("manim.utils.color")
    palette = _palette_of(scene_code_for(_plan("calculus/riemann_integral")))
    for token, constant in (("C_HOLD", "YELLOW"), ("C_DONE", "GREEN"),
                            ("C_FLOW", "BLUE"), ("C_WARN", "RED"),
                            ("C_DIM", "GREY"), ("C_MUTED", "GREY_B"),
                            ("C_FG", "WHITE"), ("C_AUX", "GREEN_B"),
                            ("C_WARM", "ORANGE")):
        assert palette[token].upper() == getattr(colour, constant).to_hex().upper()


# --- and a different style actually lands -----------------------------------


@pytest.mark.parametrize("style", sorted(THEMES.values(), key=lambda s: s.name))
def test_a_chosen_style_reaches_the_emitted_source(style):
    source = scene_code_for(_plan("calculus/riemann_integral"), style=style)
    palette = _palette_of(source)
    assert f"# Palette: {style.name}." in source
    for token in ("flow", "hold", "done", "warn", "aux", "warm", "dim"):
        assert palette[f"C_{token.upper()}"] == getattr(style, token)


def test_switching_style_changes_only_the_palette():
    """A theme swap must not perturb geometry, timing, or labels."""
    plan = _plan("trig/unit_circle_to_sine")
    a = scene_code_for(plan, style=TEXTBOOK).splitlines()
    b = scene_code_for(plan, style=PAPER).splitlines()
    assert len(a) == len(b)
    differing = [(x, y) for x, y in zip(a, b) if x != y]
    for x, y in differing:
        assert x.strip().startswith("C_") or "Palette:" in x, (
            f"a style swap changed a non-palette line:\n  {x}\n  {y}"
        )
    assert differing, "PAPER and TEXTBOOK should not emit an identical palette"


@pytest.mark.parametrize("concept", CONCEPTS)
def test_a_dark_and_a_light_theme_both_generate(concept):
    """Every builder, every theme — the combination is what ships."""
    for style in (DATAFLOW, PAPER):
        ast.parse(scene_code_for(_plan(concept), style=style))


# --- the style is reachable from outside Python -------------------------------


def test_write_scene_threads_the_style(tmp_path):
    """``write_scene`` is the only writer, so a style missing here is unreachable."""
    from straightedge.renderer import write_scene

    path = write_scene(_plan("calculus/riemann_integral"), tmp_path, style=PAPER)
    palette = _palette_of(path.read_text(encoding="utf-8"))
    assert palette["C_INK"] == PAPER.ink
    assert palette["C_FLOW"] == PAPER.flow


def test_write_scene_defaults_to_textbook(tmp_path):
    from straightedge.renderer import write_scene

    path = write_scene(_plan("calculus/riemann_integral"), tmp_path)
    assert _palette_of(path.read_text(encoding="utf-8"))["C_FLOW"] == TEXTBOOK.flow


def test_the_cli_scaffolds_in_a_chosen_style(tmp_path, monkeypatch):
    """A feature only reachable from Python is a feature most callers lack."""
    from straightedge.cli import main

    out = tmp_path / "paper"
    code = main(["scaffold", "riemann sum of x squared",
                 "--output-dir", str(out), "--style", "paper"])
    assert code == 0
    palette = _palette_of((out / "scene.py").read_text(encoding="utf-8"))
    assert palette["C_INK"] == PAPER.ink, "--style paper did not reach the scene"


def test_the_cli_rejects_an_unknown_style(tmp_path, capsys):
    """argparse should refuse before any work happens, and list the choices."""
    from straightedge.cli import main

    with pytest.raises(SystemExit):
        main(["scaffold", "riemann sum", "--output-dir", str(tmp_path),
              "--style", "neon"])
    assert "paper" in capsys.readouterr().err


# --- the theme reaches what no builder names a colour for --------------------


@pytest.mark.parametrize("concept", CONCEPTS)
def test_the_background_and_default_text_colour_are_set(concept):
    """Without these a light theme is a trap, not a feature.

    Manim's background is black and its unstyled text is white regardless of any
    palette, so a scene that themes only the marks it names renders dark-on-dark
    for ``paper`` — and looks like a broken builder rather than a missing wire.
    """
    source = scene_code_for(_plan(concept), style=PAPER)
    assert "config.background_color = C_INK" in source
    for cls in ("Text", "MathTex", "Tex", "DecimalNumber"):
        assert f"{cls}.set_default(color=C_FG)" in source, (
            f"{cls} keeps Manim's white default, so {concept} loses it on a "
            f"light background"
        )


def test_the_palette_is_constructed_not_left_as_strings():
    """``interpolate_color`` calls a method on its argument, so a str raises.

    It raises *inside* the render, after minutes of work, and only in the
    builders that gradient something — which is why this is pinned rather than
    left to the smoke test that happened to catch it.
    """
    source = scene_code_for(_plan("calculus/riemann_integral"))
    assert 'C_FLOW = ManimColor("' in source
    assert not re.search(r'^C_[A-Z_]+ = "#', source, re.MULTILINE), (
        "a bare hex string in the palette will break interpolate_color"
    )


def test_the_palette_lands_before_anything_uses_it():
    """Module scope, above the class — a colour used at class-body time needs it."""
    source = scene_code_for(_plan("calculus/riemann_integral"))
    assert source.index("C_FLOW = ManimColor(") < source.index("class GeneratedScene")


# --- the 3D helpers are themed too ------------------------------------------


def test_the_solid_helpers_follow_the_theme():
    """These live in solids3d and are appended after the palette block.

    They were the half of the port easiest to miss: a 3D scene would have
    rendered fine with unthemed blue faces and nothing would have complained.
    """
    from straightedge.solids3d import SOLID_HELPERS_SRC

    assert not BARE_MANIM_COLOURS.findall(SOLID_HELPERS_SRC), (
        "the emitted 3D helpers still hardcode a Manim colour"
    )
    assert "C_FLOW" in SOLID_HELPERS_SRC, "the solid faces should take a role token"

    # And every token they use must be defined *above* them in the emitted
    # module, or the helper's default argument raises NameError at import.
    source = scene_code_for(_plan("3d/cube_section"), style=PAPER)
    palette = _palette_of(source)
    first_helper = source.index("def _subscriptify")
    for token in sorted(set(re.findall(r"\bC_[A-Z_]+\b", SOLID_HELPERS_SRC))):
        assert token in palette, f"{token} is used by a helper but never defined"
        assert source.index(f"{token} = ManimColor(") < first_helper, (
            f"{token} is defined after the helper that uses it"
        )
