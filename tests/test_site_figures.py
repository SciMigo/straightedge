"""The site's declared SVG figures, and whether they still match the library.

`tools/build_site_assets.py` exists because every MP4 on the site was made by
hand and nothing could reproduce it. The SVGs had the same problem and were not
covered: a template changes, the landing page keeps showing output the library
no longer produces, and nobody finds out.

This is the check that closes it for the figures whose inputs are declared. It
is the same shape as `tests/test_blog_feed.py`, which keeps the Atom feed honest
for the same reason — a file maintained beside the thing it describes is exactly
the file that rots, because nothing renders it during review.

The eight legacy figures are deliberately outside this: their parameters were
never recorded, and guessing at them would replace the site's artwork with
something plausible and report success.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from straightedge.diagrams.registry import count_data_marks
from tools.build_site_figures import FIGURES, OUT, render


@pytest.mark.parametrize("figure", FIGURES, ids=lambda f: f.name)
class TestEveryDeclaredFigure:
    def test_the_committed_file_is_what_the_library_now_draws(self, figure):
        path = OUT / f"{figure.name}.svg"
        assert path.exists(), (
            f"{figure.name}.svg is declared but missing — "
            f"run `python tools/build_site_figures.py`")
        assert path.read_text(encoding="utf-8") == render(figure), (
            f"{figure.name}.svg is stale: the library draws something else now. "
            f"Run `python tools/build_site_figures.py` and review the diff.")

    def test_it_is_a_figure_rather_than_an_empty_frame(self, figure):
        svg = (OUT / f"{figure.name}.svg").read_text(encoding="utf-8")
        assert count_data_marks(svg) > 0

    def test_it_is_well_formed_svg(self, figure):
        """It is served to browsers directly; a broken one shows as nothing."""
        root = ET.fromstring((OUT / f"{figure.name}.svg").read_text(encoding="utf-8"))
        assert root.tag == "{http://www.w3.org/2000/svg}svg"

    def test_it_carries_alt_text_for_the_page_to_use(self, figure):
        assert figure.alt.strip() and len(figure.alt) > 30

    def test_it_can_be_rasterised_outside_a_browser(self, figure):
        """No CSS custom properties: `var(--ink, …)` makes a figure unrenderable
        by every non-browser rasteriser, which is what the site's own build and
        any downstream consumer would use."""
        svg = (OUT / f"{figure.name}.svg").read_text(encoding="utf-8")
        assert "var(--" not in svg


class TestTheFiguresAreOnThePagesThatClaimThem:
    def test_the_landing_gallery_references_a_declared_figure(self):
        page = (OUT.parent.parent / "index.html").read_text(encoding="utf-8")
        assert "assets/svg/construction-vesica.svg" in page

    def test_every_declared_figure_is_on_some_page(self):
        site = OUT.parent.parent
        pages = "\n".join(p.read_text(encoding="utf-8")
                          for p in [site / "index.html", *sorted((site / "posts").glob("*.html"))])
        for figure in FIGURES:
            assert f"assets/svg/{figure.name}.svg" in pages, (
                f"{figure.name} is declared and built but appears on no page")


# ------------------------------------------------------- the landing-page counts


class TestTheLandingPageCounts:
    """The hero's numbers were typed once at the first release and never read
    again: the page said 35 templates while the registry held 54. A count that
    sits in prose beside the thing it counts is the feed problem again, so it is
    checked the same way — against the registry, and against the page itself."""

    INDEX = OUT.parent.parent / "index.html"

    @pytest.fixture(scope="class")
    def page(self):
        return self.INDEX.read_text(encoding="utf-8")

    def test_the_template_count_is_the_registry_size(self, page):
        from straightedge.diagrams import DIAGRAM_REGISTRY
        n = len(DIAGRAM_REGISTRY)
        assert f"<strong>{n}</strong><span>dependency-free SVG templates</span>" in page
        assert f"{n} dependency-free templates" in page, "og:description is stale"
        assert f"<p>{n} figure templates render from the standard library alone" in page

    def test_the_animation_count_is_the_number_of_videos_on_the_page(self, page):
        n = page.count("<video")
        assert f"<strong>{n}</strong><span>playable animation examples</span>" in page
