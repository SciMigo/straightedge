"""The blog's Atom feed, and the two ways it could go out wrong.

``--check`` existed and nothing ran it, so a post could be written, merged and
deployed while the feed still described the one before it — the exact rot the
generator was written to prevent, reintroduced one level up. These tests are the
enforcement: they run in the same matrix as everything else, so the check cannot
be green in review and absent from CI.

The `pages` workflow deploys ``site/`` as it stands rather than building
anything, which is why the committed feed has to be correct rather than merely
producible.
"""

from __future__ import annotations

import importlib.util
import sys
import xml.dom.minidom
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parent.parent / "tools" / "build_blog_feed.py"


@pytest.fixture(scope="module")
def feed_tool():
    spec = importlib.util.spec_from_file_location("build_blog_feed", _PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# ------------------------------------------------------------------ freshness


def test_the_committed_feed_is_current(feed_tool):
    """Fails when a post is added, retitled or redated without regenerating.

    This is `--check`, run where CI will see it. `pages.yml` uploads `site/`
    verbatim, so a stale file here is a stale file served to subscribers.
    """
    expected = feed_tool.render(feed_tool.collect())
    assert feed_tool.FEED.read_text(encoding="utf-8") == expected, (
        "site/posts/feed.xml is out of date — run tools/build_blog_feed.py")


def test_every_post_reaches_the_feed(feed_tool):
    """A post silently absent is the failure the generator exists to prevent."""
    on_disk = {p.name for p in feed_tool.POSTS.glob("*.html")} - {"index.html"}
    assert {post["file"] for post in feed_tool.collect()} == on_disk


def test_the_feed_is_valid_xml(feed_tool):
    xml.dom.minidom.parseString(feed_tool.FEED.read_text(encoding="utf-8"))


def test_entries_are_newest_first(feed_tool):
    dates = [post["date"] for post in feed_tool.collect()]
    assert dates == sorted(dates, reverse=True)


# -------------------------------------------------------------------- escaping


def _post(tmp_path: Path, *, title: str, summary: str,
          date: str = "2026-01-01") -> Path:
    path = tmp_path / "post.html"
    path.write_text(
        f'<meta name="description" content="{summary}">\n'
        f"<h1>{title}</h1>\n"
        f'<time datetime="{date}">1 Jan 2026</time>\n',
        encoding="utf-8")
    return path


def test_entities_are_decoded_before_they_are_escaped(feed_tool, tmp_path):
    """`A &amp; B` is the text `A & B`; escaping the source gave `A &amp;amp; B`."""
    post = feed_tool.read_post(
        _post(tmp_path, title="A &amp; B", summary="Tea &amp; toast"))
    assert post["title"] == "A & B"
    assert post["summary"] == "Tea & toast"

    rendered = feed_tool.render([post])
    assert "<title>A &amp; B</title>" in rendered
    assert "&amp;amp;" not in rendered


def test_markup_inside_a_headline_does_not_reach_the_feed(feed_tool, tmp_path):
    """A title of `<code>AB</code>` would arrive as literal `&lt;code&gt;`."""
    post = feed_tool.read_post(
        _post(tmp_path, title="Reading <code>AB</code> four ways",
              summary="Plain"))
    assert post["title"] == "Reading AB four ways"
    assert "&lt;code&gt;" not in feed_tool.render([post])


def test_a_quoted_summary_survives_the_round_trip(feed_tool, tmp_path):
    post = feed_tool.read_post(
        _post(tmp_path, title="Plain", summary="A &quot;quoted&quot; phrase"))
    assert post["summary"] == 'A "quoted" phrase'
    assert "&amp;quot;" not in feed_tool.render([post])


def test_whitespace_in_a_headline_is_normalised(feed_tool, tmp_path):
    """Headlines are wrapped across lines in the source; feeds want one line."""
    post = feed_tool.read_post(
        _post(tmp_path, title="A title\n          split over lines",
              summary="Plain"))
    assert post["title"] == "A title split over lines"


# --------------------------------------------------------------- completeness


@pytest.mark.parametrize("missing", ["title", "date", "summary"])
def test_a_post_missing_a_field_is_reported_not_skipped(feed_tool, tmp_path,
                                                        missing):
    path = tmp_path / "post.html"
    parts = {
        "summary": '<meta name="description" content="Plain">',
        "title": "<h1>A title</h1>",
        "date": '<time datetime="2026-01-01">1 Jan 2026</time>',
    }
    del parts[missing]
    path.write_text("\n".join(parts.values()), encoding="utf-8")

    with pytest.raises(SystemExit, match=missing):
        feed_tool.read_post(path)
