"""Shared, dependency-free colour themes for SVG diagram families.

Themes describe semantic roles, not renderer-specific CSS.  A roadmap can use
``warning`` for an at-risk bar while a unit circle uses it for the angle arc;
the meaning stays stable even though the geometry does not.

Each template that accepts a theme owns a *family* — see :func:`family` — a
mapping from theme name to palette whose ``professional`` entry is that
template's own pre-theme colours, declared from the constants it always drew
with.  The renderer then reads ``theme.<role>`` unconditionally.  There is no
``if theme.name == "professional"`` ladder for a new colour to fall out of
step with, and "the default is byte-identical to the pre-theme renderer" is a
fact about data that a test can check rather than a claim in a changelog.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from typing import Any, Dict, Mapping

logger = logging.getLogger(__name__)

DEFAULT_DIAGRAM_THEME = "professional"

#: The roles a renderer uses to tell categories apart — a roadmap's five
#: statuses, a unit circle's sin/cos/tan. Every palette keeps these pairwise
#: distinguishable; the test measures it.
CATEGORICAL_ROLES = ("primary", "secondary", "success", "warning", "danger", "accent")


@dataclass(frozen=True)
class DiagramTheme:
    name: str
    #: The paper. Empty when the figure draws no background of its own — the
    #: pre-theme math and data-structure figures are transparent — so a
    #: renderer asks ``if theme.background`` rather than ``if professional``.
    background: str
    surface: str
    surface_alt: str
    text: str
    muted: str
    rule: str
    grid: str
    primary: str
    secondary: str
    success: str
    warning: str
    danger: str
    accent: str
    on_primary: str
    primary_soft: str
    secondary_soft: str
    success_soft: str
    warning_soft: str
    danger_soft: str
    radius: int
    #: The ink connectors and arrows are drawn in, and its lighter companion.
    #: They default to ``text`` and ``muted``; a family whose pre-theme
    #: renderer drew lines in a different dark than its labels states so here.
    ink: str = ""
    ink_soft: str = ""

    def __post_init__(self) -> None:
        if not self.ink:
            object.__setattr__(self, "ink", self.text)
        if not self.ink_soft:
            object.__setattr__(self, "ink_soft", self.muted)

    def variant(self, **overrides: Any) -> "DiagramTheme":
        """This palette with some roles replaced.

        How a family states its professional colours: start from the shared
        professional palette and name only the roles its renderer drew
        differently. ``ink``/``ink_soft`` re-derive unless overridden.
        """
        for role in ("ink", "ink_soft"):
            if role not in overrides:
                overrides[role] = ""
        return replace(self, **overrides)


DIAGRAM_THEMES = {
    "professional": DiagramTheme(
        "professional", "#fbfaf7", "#eef2f7", "#f8fafc", "#17202a", "#68717a",
        "#94a3b8", "#e1e5e9", "#2f7d72", "#4c78a8", "#2a9d8f", "#d97706",
        "#e76f51", "#7c6f9e", "#ffffff", "#d7ece7", "#e8eef7", "#dff4ea",
        "#fdf6ec", "#f8d7da", 7,
    ),
    "presentation": DiagramTheme(
        "presentation", "#f7f9fc", "#e8eef8", "#ffffff", "#111827", "#4b5563",
        "#7b8ba5", "#d9e0eb", "#1d4ed8", "#5b21b6", "#087a62", "#b45309",
        "#b42318", "#7c3aed", "#ffffff", "#dbeafe", "#ede9fe", "#d8f3e8",
        "#fff0c2", "#fee4e2", 9,
    ),
    "friendly": DiagramTheme(
        "friendly", "#fffdf7", "#e7f5f1", "#f7fbfa", "#203047", "#5d6878",
        "#86a8a0", "#dce9e5", "#147d6f", "#3974b8", "#3a9d3a", "#a65f00",
        "#b43a50", "#8055a5", "#ffffff", "#d8f3eb", "#e1edfa", "#d9f3e9",
        "#fff0c2", "#f9dce2", 10,
    ),
    "classroom": DiagramTheme(
        "classroom", "#fffdf5", "#edf4fb", "#fff8df", "#203047", "#5d6878",
        "#7b8b9c", "#dce5ec", "#2563a8", "#7040a0", "#087a62", "#b05d00",
        "#b83b31", "#b3005b", "#ffffff", "#deecff", "#eee2fa", "#d8f3e8",
        "#fff0c2", "#f8d9d6", 8,
    ),
    "playful": DiagramTheme(
        "playful", "#fff9f2", "#f5e8ff", "#fff1d6", "#32233c", "#6d5a72",
        "#9f80a5", "#eaddea", "#6d28a8", "#087aaa", "#07805c", "#b85b00",
        "#b82770", "#9f2cb3", "#ffffff", "#eadcff", "#dcedff", "#d8f5e7",
        "#ffedba", "#f9d8e8", 12,
    ),
    "pastel": DiagramTheme(
        "pastel", "#fffafd", "#f8e7ff", "#fff0f6", "#382b3f", "#746579",
        "#aa91ae", "#e8dce9", "#8e73ba", "#6a9fd8", "#4c9b82", "#a66c20",
        "#b45f78", "#d98c3a", "#17101b", "#e8ddf5", "#e2e9ff", "#d9f3e9",
        "#fff0cf", "#f7dce5", 10,
    ),
    "dark": DiagramTheme(
        "dark", "#10151f", "#202938", "#17202c", "#f8fafc", "#c4cfdd",
        "#94a3b8", "#344154", "#60a5fa", "#c084fc", "#4ade80", "#fbbf24",
        "#fb7185", "#2dd4bf", "#0b1020", "#1e3a5f", "#3d2861", "#173d2a",
        "#4b3612", "#4c1d2a", 8,
    ),
    "high-contrast": DiagramTheme(
        "high-contrast", "#ffffff", "#ffffff", "#f1f1f1", "#000000", "#303030",
        "#000000", "#767676", "#003f88", "#6a1b7b", "#006b54", "#8a5200",
        "#9b1c1c", "#b3005b", "#ffffff", "#e4efff", "#eee2f3", "#e2f3ed",
        "#fff0c7", "#f8dddd", 2,
    ),
    # Print-friendly is white paper, no soft washes, and dark inks that stay
    # apart on a photocopier — not five greys. A roadmap tells its statuses
    # apart by bar colour alone, and greys a few percent apart do not survive
    # toner; these are distinct hues that also differ in lightness.
    "print-friendly": DiagramTheme(
        "print-friendly", "#ffffff", "#eeeeee", "#f8f8f8", "#111111", "#4a4a4a",
        "#777777", "#c8c8c8", "#1f4e79", "#5c5c5c", "#2e6b3a", "#8a5a00",
        "#9b1c1c", "#5b3a8a", "#ffffff", "#eeeeee", "#e5e5e5", "#dddddd",
        "#f3f3f3", "#d5d5d5", 1,
    ),
}


def family(professional: DiagramTheme, *names: str) -> Dict[str, DiagramTheme]:
    """A template's themes: its own professional palette, then shared ones.

    The catalog publishes the keys as the ``theme`` parameter's enum, so what
    a template accepts and what it advertises are the same object.
    """
    themes = {DEFAULT_DIAGRAM_THEME: professional}
    for name in names:
        themes[name] = DIAGRAM_THEMES[name]
    return themes


def resolve_theme(value: Any, themes: Mapping[str, DiagramTheme]) -> DiagramTheme:
    """The named theme, or the family's professional default.

    A name the family does not offer draws the default, so an optional figure
    never aborts a document build — but it is logged, the way
    :func:`render_diagram` logs a figure with no data: an agent that learned
    ``dark`` from one family and sent it to another should be able to find out
    why its roadmap came back light.
    """
    if isinstance(value, str) and value in themes:
        return themes[value]
    if value is not None:
        logger.warning(
            "Diagram theme %r is not offered by this family (%s) — drawing %s",
            value, ", ".join(themes), DEFAULT_DIAGRAM_THEME,
        )
    return themes[DEFAULT_DIAGRAM_THEME]


def luminance(hex_colour: str) -> float:
    """WCAG relative luminance of a ``#rrggbb`` or ``#rgb`` colour."""
    def channel(value: float) -> float:
        return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4

    digits = hex_colour.lstrip("#")
    if len(digits) == 3:
        digits = "".join(d * 2 for d in digits)
    r, g, b = (channel(int(digits[i:i + 2], 16) / 255) for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    """WCAG contrast ratio between two colours, 1 to 21."""
    bright, dark = sorted((luminance(a), luminance(b)), reverse=True)
    return (bright + 0.05) / (dark + 0.05)


def readable_on(background: str, *inks: str) -> str:
    """Whichever of ``inks`` contrasts most with ``background``.

    For text drawn over a saturated role colour, where neither the body ink
    nor ``on_primary`` is right for every palette: a dark theme's amber wants
    dark text, a light theme's amber wants light text, and the professional
    default drew its body ink and must keep doing so.
    """
    return max(inks, key=lambda ink: contrast(ink, background))
