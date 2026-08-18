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
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
POSTS = REPO / "site" / "posts"
FEED = POSTS / "feed.xml"
BASE = "https://scimigo.github.io/straightedge"

TITLE = "Straightedge blog"
SUBTITLE = "Mechanisms simulated, asserted, and animated from the simulation."


def read_post(path: Path) -> dict:
    source = path.read_text(encoding="utf-8")
    fields = {
        "title": re.search(r"<h1>(.*?)</h1>", source, re.S),
        "date": re.search(r'<time datetime="([\d-]+)"', source),
        "summary": re.search(r'<meta name="description" content="(.*?)">', source),
    }
    missing = [name for name, match in fields.items() if match is None]
    if missing:
        raise SystemExit(
            f"{path.name}: no {', '.join(missing)} — every post needs an <h1>, a "
            "<time> in its dateline, and a description meta tag")
    return {
        "file": path.name,
        "title": " ".join(fields["title"].group(1).split()),
        "date": fields["date"].group(1),
        "summary": fields["summary"].group(1),
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
