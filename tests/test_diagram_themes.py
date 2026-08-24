"""The SVG theme contract shared by representative visual families."""
from __future__ import annotations

import re
from xml.etree import ElementTree as ET

import pytest

from straightedge import list_templates
from straightedge.diagrams import render_diagram
from straightedge.diagrams.themes import (
    DATA_STRUCTURE_THEMES,
    DIAGRAM_THEMES,
    MATH_THEMES,
    ORG_CHART_THEMES,
    ROADMAP_THEMES,
    TEMPLATE_THEME_NAMES,
)


CASES = {
    "roadmap": {
        "title": "Launch",
        "start_date": "2026-01-01",
        "end_date": "2026-03-31",
        "tracks": [{"id": "build", "label": "Build"}],
        "items": [{"id": "api", "title": "API", "track": "build",
                   "start_date": "2026-01-01", "end_date": "2026-02-15",
                   "status": "active"}],
    },
    "org_chart": {"title": "Team", "root": {"name": "Ada", "title": "GM",
                                                           "children": [{"name": "Grace",
                                                                         "title": "Engineering"}]}},
    "unit_circle": {"angle": 45, "show_tan": True},
    "linked_list": {"nodes": [{"id": "a", "value": 1},
                                {"id": "b", "value": 2}],
                    "highlights": {"a": "current"}},
}


@pytest.mark.parametrize("template,themes", [
    ("roadmap", ROADMAP_THEMES),
    ("org_chart", ORG_CHART_THEMES),
    ("unit_circle", MATH_THEMES),
    ("linked_list", DATA_STRUCTURE_THEMES),
])
def test_every_advertised_theme_renders_valid_distinct_svg(template, themes):
    renders = []
    for theme in themes:
        svg = render_diagram({"type": template,
                              "params": {**CASES[template], "theme": theme}})
        ET.fromstring(svg)
        assert svg.count("<svg") == 1
        renders.append(svg)
    assert len(set(renders)) == len(themes)


@pytest.mark.parametrize("template", CASES)
def test_professional_is_the_byte_identical_default(template):
    bare = render_diagram({"type": template, "params": CASES[template]})
    explicit = render_diagram({"type": template,
                               "params": {**CASES[template], "theme": "professional"}})
    unknown = render_diagram({"type": template,
                              "params": {**CASES[template], "theme": "not-a-theme"}})
    assert bare == explicit == unknown


def test_catalog_publishes_family_specific_theme_enums():
    by_id = {template.id: template for template in list_templates()}
    for template, themes in TEMPLATE_THEME_NAMES.items():
        parameter = next(p for p in by_id[template].parameters if p["name"] == "theme")
        assert parameter == {"name": "theme", "type": "string",
                             "default": "professional", "enum": list(themes)}


def _rgb(hex_colour: str) -> tuple[float, float, float]:
    return tuple(int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5))


def _luminance(hex_colour: str) -> float:
    def channel(value: float) -> float:
        return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(value) for value in _rgb(hex_colour))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(a: str, b: str) -> float:
    bright, dark = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (bright + 0.05) / (dark + 0.05)


def test_every_palette_keeps_body_and_filled_text_readable():
    for theme in DIAGRAM_THEMES.values():
        assert _contrast(theme.text, theme.background) >= 4.5, theme.name
        assert _contrast(theme.on_primary, theme.primary) >= 4.5, theme.name

