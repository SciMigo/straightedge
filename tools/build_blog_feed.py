#!/usr/bin/env python3
"""Generate the blog's Atom feed from the published posts.

Read out of the posts rather than maintained beside them. A feed is exactly the
kind of file that rots: it duplicates every title, date and summary already in
the HTML, nothing renders it during review, and the first time anyone notices it
is stale is when a subscriber gets a post that does not exist. Deriving it means
the duplication cannot drift.

Each post supplies its own entry:

* ``<h1>``                      → the title
* ``<time datetime="...">``     → the date, from the dateline
* ``<meta name="description">`` → the summary

A post missing any of them is reported rather than skipped, because a post
silently absent from the feed is the failure this script exists to prevent.

    python tools/build_blog_feed.py            # writes site/posts/feed.xml
    python tools/build_blog_feed.py --check    # non-zero if it is out of date
"""

from __future__ import annotations

import argparse
import html
import sys
from html.parser import HTMLParser
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
POSTS = REPO / "site" / "posts"
FEED = POSTS / "feed.xml"
BASE = "https://scimigo.github.io/straightedge"

TITLE = "Straightedge blog"
SUBTITLE = "Mechanisms simulated, asserted, and animated from the simulation."


class _PostReader(HTMLParser):
    """Pulls a post's title, date and summary out of its markup.

    A parser rather than three regexes, because both things a regex got wrong
    here are things a parser gets right for free. Entity references are decoded
    once — ``A &amp; B`` is the text ``A & B``, and re-escaping the raw source
    on the way into XML produced ``A &amp;amp; B``. And inline markup inside the
    headline is dropped rather than carried: a title reading ``<code>AB</code>``
    would otherwise reach a feed reader as literal ``&lt;code&gt;`` text.

    Attribute values arrive decoded too, which is the same fix for the summary.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title: str | None = None
        self.date: str | None = None
        self.summary: str | None = None
        self._title_parts: list[str] = []
        self._in_title = False

    def handle_starttag(self, tag: str, attrs) -> None:
        values = dict(attrs)
        if tag == "h1" and self.title is None:
            self._in_title = True
        elif (tag == "meta" and values.get("name") == "description"
              and self.summary is None):
            self.summary = values.get("content")
        elif tag == "time" and self.date is None and values.get("datetime"):
            self.date = values["datetime"]

    def handle_endtag(self, tag: str) -> None:
        # Only the first h1 is the title; a later one closes nothing.
        if tag == "h1" and self._in_title:
            self._in_title = False
            self.title = " ".join("".join(self._title_parts).split())

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title_parts.append(data)


def read_post(path: Path) -> dict:
    reader = _PostReader()
    reader.feed(path.read_text(encoding="utf-8"))

    missing = [name for name in ("title", "date", "summary")
               if not getattr(reader, name)]
    if missing:
        raise SystemExit(
            f"{path.name}: no {', '.join(missing)} — every post needs an <h1>, a "
            "<time> in its dateline, and a description meta tag")
    return {
        "file": path.name,
        "title": reader.title,
        "date": reader.date,
        "summary": reader.summary,
    }


def collect() -> list[dict]:
    posts = [read_post(p) for p in sorted(POSTS.glob("*.html"))
             if p.name != "index.html"]
    # Newest first, and by filename within a day so the order is stable rather
    # than dependent on the filesystem.
    posts.sort(key=lambda e: (e["date"], e["file"]), reverse=True)
    return posts


def render(posts: list[dict]) -> str:
    entries = "\n".join(
        f"""  <entry>
    <title>{html.escape(post['title'])}</title>
    <link href="{BASE}/posts/{post['file']}"/>
    <id>{BASE}/posts/{post['file']}</id>
    <updated>{post['date']}T00:00:00Z</updated>
    <summary>{html.escape(post['summary'])}</summary>
  </entry>""" for post in posts)

    return f"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>{TITLE}</title>
  <subtitle>{SUBTITLE}</subtitle>
  <link href="{BASE}/posts/feed.xml" rel="self"/>
  <link href="{BASE}/posts/"/>
  <id>{BASE}/posts/</id>
  <updated>{posts[0]['date']}T00:00:00Z</updated>
  <author><name>SciMigo</name></author>
{entries}
</feed>
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="exit non-zero if feed.xml is not what this would write")
    args = parser.parse_args(argv)

    posts = collect()
    if not posts:
        raise SystemExit(f"no posts found under {POSTS}")
    feed = render(posts)

    if args.check:
        current = FEED.read_text(encoding="utf-8") if FEED.exists() else ""
        if current != feed:
            print("feed.xml is out of date; run tools/build_blog_feed.py",
                  file=sys.stderr)
            return 1
        print(f"feed.xml is current ({len(posts)} posts)")
        return 0

    FEED.write_text(feed, encoding="utf-8")
    print(f"wrote {FEED.relative_to(REPO)} ({len(posts)} posts)")
    for post in posts:
        print(f"  {post['date']}  {post['title']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
