"""Shared, dependency-free colour themes for SVG diagram families.

Themes describe semantic roles, not renderer-specific CSS.  A roadmap can use
``warning`` for an at-risk bar while a unit circle uses it for the angle arc;
the meaning stays stable even though the geometry does not.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


DEFAULT_DIAGRAM_THEME = "professional"

ROADMAP_THEMES = (
    "professional", "presentation", "pastel", "high-contrast", "print-friendly",
)
ORG_CHART_THEMES = (
    "professional", "friendly", "pastel", "high-contrast", "print-friendly",
)
MATH_THEMES = (
    "professional", "classroom", "dark", "high-contrast", "print-friendly",
)
DATA_STRUCTURE_THEMES = (
    "professional", "classroom", "playful", "dark", "high-contrast",
)

# Used by the catalog to publish an enum instead of making an agent guess which
# global themes happen to make sense for a particular visual family.
TEMPLATE_THEME_NAMES = {
    "roadmap": ROADMAP_THEMES,
    "org_chart": ORG_CHART_THEMES,
    "unit_circle": MATH_THEMES,
    "linked_list": DATA_STRUCTURE_THEMES,
}


@dataclass(frozen=True)
class DiagramTheme:
    name: str
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
        "#86a8a0", "#dce9e5", "#147d6f", "#3974b8", "#16805d", "#a65f00",
        "#b43a50", "#8055a5", "#ffffff", "#d8f3eb", "#e1edfa", "#d9f3e9",
        "#fff0c2", "#f9dce2", 10,
    ),
    "classroom": DiagramTheme(
        "classroom", "#fffdf5", "#edf4fb", "#fff8df", "#203047", "#5d6878",
        "#7b8b9c", "#dce5ec", "#2563a8", "#7040a0", "#087a62", "#b05d00",
        "#b83b31", "#7040a0", "#ffffff", "#deecff", "#eee2fa", "#d8f3e8",
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
        "#aa91ae", "#e8dce9", "#8e73ba", "#748bc7", "#4c9b82", "#a66c20",
        "#b45f78", "#9a72a7", "#17101b", "#e8ddf5", "#e2e9ff", "#d9f3e9",
        "#fff0cf", "#f7dce5", 10,
    ),
    "dark": DiagramTheme(
        "dark", "#10151f", "#202938", "#17202c", "#f8fafc", "#c4cfdd",
        "#94a3b8", "#344154", "#60a5fa", "#c084fc", "#4ade80", "#fbbf24",
        "#fb7185", "#c084fc", "#0b1020", "#1e3a5f", "#3d2861", "#173d2a",
        "#4b3612", "#4c1d2a", 8,
    ),
    "high-contrast": DiagramTheme(
        "high-contrast", "#ffffff", "#ffffff", "#f1f1f1", "#000000", "#303030",
        "#000000", "#767676", "#003f88", "#6a1b7b", "#006b54", "#8a5200",
        "#9b1c1c", "#5b1885", "#ffffff", "#e4efff", "#eee2f3", "#e2f3ed",
        "#fff0c7", "#f8dddd", 2,
    ),
    "print-friendly": DiagramTheme(
        "print-friendly", "#ffffff", "#eeeeee", "#f8f8f8", "#111111", "#4a4a4a",
        "#777777", "#c8c8c8", "#202020", "#444444", "#333333", "#555555",
        "#111111", "#666666", "#ffffff", "#eeeeee", "#e5e5e5", "#dddddd",
        "#f3f3f3", "#d5d5d5", 1,
    ),
}


def resolve_theme(value: Any, supported: Iterable[str]) -> DiagramTheme:
    """Resolve a supported theme, falling back deterministically to the default."""
    names = tuple(supported)
    name = value if isinstance(value, str) and value in names else DEFAULT_DIAGRAM_THEME
    return DIAGRAM_THEMES[name]
