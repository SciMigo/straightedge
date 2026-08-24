"""The SVG theme contract shared by representative visual families.

A theme changes colours, not facts. The two things this suite holds a
template to: `professional` is the renderer it always was, measured against
the literals it always drew with rather than against itself; and every other
theme keeps the roles a reader tells categories apart by actually apart.
"""
from __future__ import annotations

import itertools
import logging
import math
import re
from xml.etree import ElementTree as ET

import pytest

from straightedge import list_templates
from straightedge.diagrams import DIAGRAM_REGISTRY, render_diagram
from straightedge.diagrams.registry import count_data_marks
from straightedge.diagrams.themes import (
    CATEGORICAL_ROLES,
    DIAGRAM_THEMES,
    DiagramTheme,
    contrast,
    readable_on,
    resolve_theme,
)

THEMED = ("roadmap", "org_chart", "unit_circle", "linked_list")

CASES = {
    "roadmap": {
        "title": "Launch",
        "start_date": "2026-01-01",
        "end_date": "2026-03-31",
        "tracks": [{"id": "build", "label": "Build"}],
        "milestones": [{"date": "2026-02-01", "label": "Beta"}],
        "items": [{"id": "api", "title": "API", "track": "build",
                   "start_date": "2026-01-01", "end_date": "2026-02-15",
                   "status": "active"},
                  {"id": "ui", "title": "UI", "track": "build",
                   "start_date": "2026-02-01", "end_date": "2026-03-01",
                   "status": "planned", "depends_on": ["api"]}],
    },
    "org_chart": {"title": "Team", "root": {"name": "Ada", "title": "GM", "children": [
        {"name": "Grace", "title": "Engineering"},
        {"name": "", "title": "Backend", "status": "vacant"},
        {"name": "Mo", "title": "Ops", "status": "interim"}]}},
    "unit_circle": {"angle": 45, "show_tan": True},
    "linked_list": {"nodes": [{"id": "a", "value": 1}, {"id": "b", "value": 2},
                              {"id": "c", "value": 3}],
                    "highlights": {"a": "current", "b": "comparison", "c": "visited"},
                    "pointers": [{"node": "a", "label": "head"}],
                    "caption": "Two pointers", "type": "doubly"},
}

#: What each pre-theme renderer drew with, harvested from the templates as
#: they stood before `theme` existed. The professional render must still
#: contain every one of these — and none of the shared palette's substitutes,
#: which is how a role quietly replacing a literal shows up.
LEGACY_LITERALS = {
    "roadmap": {"#4c78a8", "#2a9d8f", "#d97706", 'fill="#9aa4ad" class="r-dep-head"',
                'fill="#f4f2ec"', 'rx="6"', 'stroke="#e1e5e9"'},
    "org_chart": {"#0f172a", "#64748b", "#2f7d72", "#7c6f9e", "#b45309", "#cbd5e1",
                  "#f5f3fa", 'fill="#ffffff" class="grid-paper"'},
    "unit_circle": {"#4CAF50", "#2E7D32", "#FF9800", "#f44336", "#2196F3", "#9C27B0",
                    "stroke: #333", "fill: #666", "stroke: #999"},
    "linked_list": {"#212529", "#6c757d", "stroke: #343a40", 'stroke="#343a40"',
                    'stroke="#333"', 'stroke="#666"', 'fill="#333"', "#fff3cd",
                    "#d1ecf1", "#FF9800", "#f8f9fa", "#2196F3"},
}
SHARED_SUBSTITUTES = {
    "org_chart": {"#17202a", "#68717a", "#fbfaf7"},
    "unit_circle": {"#17202a", "#68717a", "#94a3b8"},
    "linked_list": {"#17202a", "#68717a", "#94a3b8"},
}


def _render(template: str, **extra) -> str:
    return render_diagram({"type": template, "params": {**CASES[template], **extra}})


def _families() -> dict[str, dict[str, DiagramTheme]]:
    return {name: DIAGRAM_REGISTRY[name].themes for name in THEMED}


class TestProfessionalIsThePreThemeRenderer:
    @pytest.mark.parametrize("template", THEMED)
    def test_the_default_still_draws_with_its_own_literals(self, template):
        svg = _render(template)
        missing = [lit for lit in LEGACY_LITERALS[template] if lit not in svg]
        assert not missing, f"{template} no longer draws {missing}"
        leaked = [hx for hx in SHARED_SUBSTITUTES.get(template, ()) if hx in svg]
        assert not leaked, f"{template} took {leaked} from the shared palette"

    @pytest.mark.parametrize("template", THEMED)
    def test_bare_explicit_and_unknown_all_draw_the_default(self, template):
        bare = _render(template)
        assert bare == _render(template, theme="professional")
        assert bare == _render(template, theme="not-a-theme")

    def test_a_professional_palette_reads_the_theme_with_no_name_checks(self):
        """One `if theme.name == "professional"` is a literal waiting to drift
        from its role; the fix was to give each family its own palette."""
        import importlib
        import inspect

        for name in THEMED:
            module = importlib.import_module(type(DIAGRAM_REGISTRY[name]).__module__)
            assert 'theme.name == "professional"' not in inspect.getsource(module), name


class TestEveryThemeIsAFigure:
    @pytest.mark.parametrize("template", THEMED)
    def test_every_advertised_theme_renders_valid_distinct_svg(self, template):
        renders = []
        for theme in DIAGRAM_REGISTRY[template].themes:
            svg = _render(template, theme=theme)
            ET.fromstring(svg)
            assert svg.count("<svg") == 1
            renders.append(svg)
        assert len(set(renders)) == len(renders)

    @pytest.mark.parametrize("template", THEMED)
    def test_a_theme_changes_no_data_mark_count(self, template):
        """A background rectangle is chrome; it must not count as a mark, or a
        themed figure with nothing in it passes the blank check."""
        counts = {theme: count_data_marks(_render(template, theme=theme))
                  for theme in DIAGRAM_REGISTRY[template].themes}
        assert len(set(counts.values())) == 1, counts

    @pytest.mark.parametrize("template,params", [
        ("linked_list", {"nodes": []}),
        ("unit_circle", {"angle": "not an angle"}),
    ])
    def test_an_empty_themed_figure_is_still_blank(self, template, params):
        for theme in DIAGRAM_REGISTRY[template].themes:
            svg = render_diagram({"type": template, "params": {**params, "theme": theme}})
            assert count_data_marks(svg) == 0, theme

    def test_dependency_arrowheads_are_coloured_in_every_theme(self):
        """The arrowhead's colour local was shadowed by the dependency loop
        variable, so it was emitted as `fill="api"` — a bug the professional
        default shared."""
        for theme_name, theme in DIAGRAM_REGISTRY["roadmap"].themes.items():
            svg = _render("roadmap", theme=theme_name)
            heads = set(re.findall(r'fill="([^"]*)" class="r-dep-head"', svg))
            assert heads == {theme.rule}, (theme_name, heads)


class TestAnUnknownThemeIsNotSilent:
    def test_a_name_the_family_does_not_offer_is_logged(self, caplog):
        with caplog.at_level(logging.WARNING, logger="straightedge.diagrams.themes"):
            theme = resolve_theme("dark", DIAGRAM_REGISTRY["roadmap"].themes)
        assert theme.name == "professional"
        [record] = caplog.records
        assert "'dark'" in record.message and "professional" in record.message

    def test_a_missing_theme_is_the_default_and_says_nothing(self, caplog):
        with caplog.at_level(logging.WARNING, logger="straightedge.diagrams.themes"):
            assert resolve_theme(None, DIAGRAM_REGISTRY["roadmap"].themes).name == "professional"
        assert not caplog.records


class TestTheCatalogPublishesWhatTheTemplateAccepts:
    def test_theme_enums_come_from_the_template_family(self):
        by_id = {template.id: template for template in list_templates()}
        for name, themes in _families().items():
            parameter = next(p for p in by_id[name].parameters if p["name"] == "theme")
            assert parameter == {"name": "theme", "type": "string",
                                 "default": "professional", "enum": list(themes)}

    def test_no_other_template_advertises_a_theme(self):
        for template in list_templates():
            if template.lane == "figure" and template.id not in THEMED:
                assert all(p["name"] != "theme" for p in template.parameters), template.id


def _distance(a: str, b: str) -> float:
    return math.dist([int(a[i:i + 2], 16) for i in (1, 3, 5)],
                     [int(b[i:i + 2], 16) for i in (1, 3, 5)])


#: Pre-theme output that already fell short, kept because `professional` is
#: the old renderer by contract. Strict, like the legibility suite's list:
#: an entry that starts passing must be removed.
KNOWN_LOW_CONTRAST = {
    ("roadmap", "professional"): "white bar text on the active teal reads at 3.3:1",
}


class TestEveryPaletteKeepsItsRolesApart:
    def _every_theme(self):
        yield from (("shared", theme) for theme in DIAGRAM_THEMES.values())
        for name, themes in _families().items():
            yield name, themes["professional"]

    def test_body_text_reads_on_the_paper(self):
        for origin, theme in self._every_theme():
            paper = theme.background or "#ffffff"
            assert contrast(theme.text, paper) >= 4.5, (origin, theme.name)

    def test_filled_text_reads_on_primary(self):
        for origin, theme in self._every_theme():
            ratio = contrast(theme.on_primary, theme.primary)
            if (origin, theme.name) in KNOWN_LOW_CONTRAST:
                assert ratio < 4.5, f"{origin}/{theme.name} now passes; drop it from the list"
                continue
            assert ratio >= 4.5, (origin, theme.name, round(ratio, 2))

    def test_categorical_roles_are_pairwise_distinguishable(self):
        """A roadmap tells five statuses apart by bar colour alone, and a unit
        circle its sin/cos/tan by line colour. Two roles a few RGB units apart
        — classroom's secondary and accent were the same hex — draw one
        category as another."""
        for origin, theme in self._every_theme():
            for a, b in itertools.combinations(CATEGORICAL_ROLES, 2):
                apart = _distance(getattr(theme, a), getattr(theme, b))
                assert apart >= 40, (origin, theme.name, a, b, round(apart))

    def test_a_comparison_node_keeps_its_value_readable(self):
        """The node is filled with the saturated warning colour; the body ink
        does not read on a dark theme's amber, so the value is drawn in
        whichever ink does."""
        for theme_name, theme in DIAGRAM_REGISTRY["linked_list"].themes.items():
            ink = readable_on(theme.warning, theme.text, theme.on_primary)
            assert contrast(ink, theme.warning) >= 4.5, theme_name
            svg = render_diagram({"type": "linked_list", "params": {
                "nodes": [{"id": "a", "value": 1}], "highlights": {"a": "comparison"},
                "theme": theme_name}})
            value = re.search(r'<text[^>]*linked-node-value[^>]*>', svg).group(0)
            if ink == theme.text:
                assert "fill=" not in value, theme_name
            else:
                assert f'fill="{ink}"' in value, theme_name
