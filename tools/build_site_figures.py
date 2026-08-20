#!/usr/bin/env python3
"""Render the site's SVG figures from declared inputs, and check they are current.

``build_site_assets.py`` exists because every MP4 on the site had been made by
hand and nothing could reproduce it. The SVGs under ``site/assets/svg/`` have
exactly the same problem and were never covered: a template can change, the
landing page keeps showing output the library no longer produces, and the only
way to notice is to re-render by hand and compare.

Each entry below names the exact hint that made its file, so the mapping stops
living in someone's memory. Unlike the video script this one writes into
``site/assets/svg/`` directly — an SVG is a few kilobytes of text that diffs
usefully in review, which is the opposite of the case for a binary.

    python tools/build_site_figures.py            # write every declared figure
    python tools/build_site_figures.py --check    # fail if any is stale
    python tools/build_site_figures.py --list

**On the eight figures this does not declare.** ``architecture``, ``gantt``,
``heatmap``, ``binary-tree``, ``linked-list``, ``riemann-sum``, ``unit-circle``
and ``flow-diagram`` predate this script and their inputs were not recorded.
They are deliberately *not* guessed at: a guess that renders something plausible
would replace the site's artwork with a different figure and report success. As
each one's parameters are recovered it should be added here and its file
regenerated in a reviewable commit — until then ``--check`` can only speak for
what is declared, and it says so rather than implying it covers the directory.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

OUT = REPO / "site" / "assets" / "svg"

#: The vesica, drawn far enough to prove the thing it is famous for: two circles,
#: the axis through their crossings, and the base — which together produce the
#: midpoint without anyone naming it.
VESICA_STEPS = [
    "A = 0, 0",
    "B = 1, 0",
    "( A B )",
    "( B A )",
    "[ C D ]",
    "[ A B ]",
]

@dataclass(frozen=True)
class Figure:
    name: str
    hint: Dict[str, Any]
    alt: str


FIGURES: tuple[Figure, ...] = (
    Figure(
        "construction-vesica",
        {"type": "construction",
         "params": {
             "title": "Vesica piscis — the perpendicular bisector, proved",
             "steps": VESICA_STEPS,
             "claims": [
                 {"claim": "perpendicular", "of": ["[ C D ]", "[ A B ]"]},
                 {"claim": "midpoint", "of": ["G", "A", "B"]},
                 {"claim": "congruent", "of": [["A", "B"], ["A", "C"], ["B", "C"]]},
             ]}},
        "Two overlapping circles, the vertical line through their intersections, "
        "and the base line through their centres, with every point labelled",
    ),
    Figure(
        "construction-steps",
        {"type": "construction",
         "params": {"title": "Every point but two was found, not placed",
                    "steps": VESICA_STEPS[:4],
                    "width": 420}},
        "The first four steps of the vesica: two given points and two circles, "
        "with the two intersection points they produce",
    ),
)


def render(figure: Figure) -> str:
    """The SVG for one figure, refusing anything blank or unverified.

    A figure whose claims fail renders empty, and an empty file on the landing
    page is worse than a missing one — it is a blank rectangle that looks like a
    styling bug rather than a false assertion. So the blank is caught here.
    """
    from straightedge.diagrams import render_diagram
    from straightedge.diagrams.registry import count_data_marks

    svg = render_diagram(figure.hint)
    if not svg or count_data_marks(svg) == 0:
        raise SystemExit(
            f"{figure.name}: rendered nothing. If it carries claims, one of them "
            f"is false — run verify_construction on the same steps for the reason.")
    return svg


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true",
                        help="exit non-zero if any declared figure is stale")
    parser.add_argument("--list", action="store_true", help="name the figures")
    parser.add_argument("names", nargs="*", help="only these (default: all)")
    args = parser.parse_args(argv)

    chosen = [f for f in FIGURES if not args.names or f.name in args.names]
    if args.list:
        for figure in FIGURES:
            print(f"{figure.name:24s} {figure.hint['type']}")
        return 0
    if not chosen:
        print(f"no such figure; known: {', '.join(f.name for f in FIGURES)}",
              file=sys.stderr)
        return 2

    stale: list[str] = []
    for figure in chosen:
        svg = render(figure)
        path = OUT / f"{figure.name}.svg"
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current == svg:
            print(f"  ok      {figure.name}")
            continue
        if args.check:
            stale.append(figure.name)
            print(f"  STALE   {figure.name}")
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(svg, encoding="utf-8")
        # Encoded length, not character count — the same distinction the
        # `draw` tool got wrong: the title carries an em dash.
        print(f"  written {figure.name}  ({len(svg.encode('utf-8'))} bytes)")

    if stale:
        print(f"\n{len(stale)} figure(s) differ from what the library now draws: "
              f"{', '.join(stale)}.\nRun this script without --check and review "
              f"the diff.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
