#!/usr/bin/env python3
"""Print one version's section of the changelog, for a release body.

`publish.yml` uploads to PyPI on a version tag and, until now, stopped there —
so the Releases page skipped 0.3.0, 0.3.1 and 0.3.2 while all three were tagged
and on the index. The page read as though the project had gone from 0.2.0 to
0.4.0, which is a worse impression than no page at all.

The extraction lives here rather than as a `sed` in the workflow because a
release body is the one artifact nobody proofreads before it is public, and a
shell one-liner that silently emits an empty string would produce an empty
release and a green build. This is testable, and it refuses rather than emits
nothing.

    python tools/changelog_section.py 0.4.0
    python tools/changelog_section.py v0.4.0 --check

Pure standard library, so the workflow needs no setup step to run it.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CHANGELOG = REPO / "CHANGELOG.md"

#: `## [0.4.0] - 2026-08-21`, and the unreleased heading that must never ship.
_HEADING = re.compile(r"^## \[(?P<version>[^\]]+)\](?:\s*-\s*(?P<date>\S+))?\s*$")


def sections(text: str) -> dict[str, str]:
    """Every version heading in the file, mapped to its body."""
    found: dict[str, str] = {}
    current: str | None = None
    body: list[str] = []
    for line in text.splitlines():
        match = _HEADING.match(line)
        if match:
            if current is not None:
                found[current] = "\n".join(body).strip()
            current = match.group("version")
            body = []
        elif current is not None:
            body.append(line)
    if current is not None:
        found[current] = "\n".join(body).strip()
    return found


def section_for(version: str, text: str | None = None) -> str:
    """The body for ``version``, or raise saying what the file does hold.

    A tag with no changelog entry is a release someone forgot to write up, and
    guessing — falling back to the commit log, or to nothing — would publish
    that omission rather than report it.
    """
    version = version.lstrip("v")
    found = sections(CHANGELOG.read_text(encoding="utf-8") if text is None else text)
    if version not in found:
        raise SystemExit(
            f"CHANGELOG.md has no section for {version!r}. "
            f"It has: {', '.join(sorted(found)) or '(none)'}")
    body = found[version]
    if not body.strip():
        raise SystemExit(f"the {version!r} section of CHANGELOG.md is empty")
    return body


def is_prerelease(version: str) -> bool:
    """``0.5.0rc1`` and ``1.0.0b2`` are prereleases; ``0.4.0`` is not."""
    return not re.fullmatch(r"\d+(\.\d+)*", version.lstrip("v"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("version", help="e.g. 0.4.0 or v0.4.0")
    parser.add_argument("--check", action="store_true",
                        help="say whether a section exists, print nothing")
    args = parser.parse_args(argv)

    body = section_for(args.version)
    if args.check:
        print(f"ok: {args.version} has {len(body.splitlines())} lines of notes")
        return 0
    sys.stdout.write(body + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
