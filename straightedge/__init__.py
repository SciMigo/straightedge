"""Natural language to Manim math animations, with automated visual QC.

The names below are the supported surface. Everything is importable without
Manim installed — the core declares no runtime dependencies, so a host that only
needs to *validate* a plan (see :mod:`straightedge.preconditions`) can carry the
package without the ``render`` extra. Only :func:`render_scene` shells out to
Manim, and only :mod:`straightedge.stt` needs the ``stt`` extra.

Three checks run at three different moments, and they catch different things:

``preconditions.validate``
    Before anything is drawn. Does the plan describe the animation that was
    actually requested? Catches silent substitution, where a builder repairs bad
    input and renders the wrong thing beautifully.
``qc.check``
    After the scene is built. Does it *look* right — anything empty, clipped,
    off-frame, or printed on top of something else?
``labels.untranslated``
    After generation. Did every on-screen label survive translation?
"""

#: The one place the version is written. ``pyproject.toml`` declares its version
#: dynamically from this attribute rather than restating it, so the packaged
#: metadata and anything reading it at runtime — the MCP server advertises it to
#: clients — cannot drift apart. Kept a plain literal because setuptools reads it
#: statically, without importing the package at build time.
__version__ = "0.3.2"

from .aspect import ASPECTS, LANDSCAPE, VERTICAL
from .catalog import Template, list_templates
from .errors import (
    DependencyError, FontError, InputFileError, PreconditionError, RenderError,
    RequestError, StraightedgeError, UnknownTemplateError,
)
from .estimate import Estimate, estimate
from .expr import parse_function, to_latex_expr, to_numpy_expr
from .labels import DEFAULT_LANGUAGE, LANGUAGES, translate, untranslated
from .models import AnimationPlan, Topic
from .planner import build_plan, plan_from_template
from .preconditions import Violation, blocking, validate
from .qc import Box, Finding, boxes_from_scene, check, frame_from_scene, worst_severity
from .renderer import RenderResult, render_scene, write_scene
from .style import (
    DATAFLOW, PAPER, TEXTBOOK, THEME_NAMES, THEMES, Style, theme,
)
from .templates import SCENE_CLASS_NAME, scene_code_for
from .topics import TopicSpec, all_ids as topic_ids, spec as topic_spec, verify as _topics_verify

# Every topic module, and both builder modules, have now been imported, so every
# registration that is going to happen has happened. Checking here rather than
# lazily means a half-registered topic cannot reach a caller at all — the four
# ways one used to fail silently are described in `straightedge.topics`.
_topics_verify()

__all__ = [
    "__version__",
    # Discovery
    "list_templates",
    "Template",
    # Topics — what the animation lane can be asked about, and how each is
    # declared. `topic_ids()` replaces the old `Topic.ALL`.
    "topic_ids",
    "topic_spec",
    "TopicSpec",
    # Errors — typed, with a remedy; catch StraightedgeError for all of them
    "StraightedgeError",
    "RequestError",
    "InputFileError",
    "PreconditionError",
    "FontError",
    "RenderError",
    "DependencyError",
    "UnknownTemplateError",
    # Plan
    "AnimationPlan",
    "Topic",
    "build_plan",
    "plan_from_template",
    # Cost — roughly how long a render takes, before spending it
    "estimate",
    "Estimate",
    # Expressions
    "parse_function",
    "to_latex_expr",
    "to_numpy_expr",
    # Scene generation and rendering
    "SCENE_CLASS_NAME",
    "scene_code_for",
    "write_scene",
    "render_scene",
    "RenderResult",
    # Checks
    "validate",
    "blocking",
    "Violation",
    "check",
    "boxes_from_scene",
    "frame_from_scene",
    "worst_severity",
    "Box",
    "Finding",
    # Style — named visual roles, so one scene can be drawn more than one way
    "Style",
    "theme",
    "THEMES",
    "THEME_NAMES",
    "DATAFLOW",
    "TEXTBOOK",
    "PAPER",
    # Frame and language
    "ASPECTS",
    "LANDSCAPE",
    "VERTICAL",
    "LANGUAGES",
    "DEFAULT_LANGUAGE",
    "translate",
    "untranslated",
]
