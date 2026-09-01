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
    "( B A ) -> C D",       # named, so the line below cannot drift onto other points
    "[ C D ]",
    "[ A B ]",
    "< A B C >",            # the equilateral triangle the congruence claim is about
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
    # --- graph theory, computed (posts/graph-theory-computed.html) ----------
    # The same stock graph the animation lane draws by prompt, listed in the
    # order that keeps the circular layout crossing-free.
    Figure(
        "graph-kruskal-storyboard",
        {"type": "graph_algorithm",
         "params": {"algorithm": "kruskal", "animate": False, "columns": 4,
                    "title": "Kruskal's algorithm: accept or reject, edge by edge",
                    "nodes": [{"id": v} for v in "ACEDFB"],
                    "edges": [{"from": a, "to": b, "weight": w} for a, b, w in
                              [("A", "B", 4), ("A", "C", 2), ("B", "C", 5), ("B", "D", 10),
                               ("C", "E", 3), ("E", "D", 4), ("D", "F", 11)]]}},
        "Eight panels of Kruskal's algorithm on a six-vertex weighted graph; "
        "accepted edges thicken, the two cycle-closing edges are drawn dashed",
    ),
    Figure(
        "graph-coloring-animated",
        {"type": "graph_algorithm",
         "params": {"algorithm": "greedy_coloring", "animate": True,
                    "duration_s": 1.2, "loop": True,
                    "title": "Greedy colouring, computed frame by frame",
                    "nodes": [{"id": v} for v in "ABCDEF"],
                    "edges": [{"from": a, "to": b} for a, b in
                              [("A", "B"), ("B", "C"), ("C", "D"), ("D", "E"), ("E", "A"),
                               ("F", "A"), ("F", "B"), ("F", "C"), ("F", "D"), ("F", "E")]]}},
        "A wheel on six vertices greedily coloured one vertex per frame, "
        "cross-fading; the hub takes a fourth colour",
    ),
    Figure(
        "graph-max-flow-storyboard",
        {"type": "graph_algorithm",
         "params": {"algorithm": "max_flow", "animate": False, "columns": 3,
                    "directed": True, "graph_layout": "hierarchical",
                    "source": "s", "sink": "t",
                    "title": "Edmonds–Karp on a four-vertex network",
                    "nodes": [{"id": v} for v in "sabt"],
                    "edges": [{"from": a, "to": b, "capacity": c} for a, b, c in
                              [("s", "a", 3), ("s", "b", 2), ("a", "b", 1),
                               ("a", "t", 2), ("b", "t", 3)]]}},
        "Five panels: three augmenting paths with their bottlenecks, then the "
        "min cut whose capacity equals the flow value of 5",
    ),
    # --- graph theory, computed · 02 (posts/graph-course-algorithms.html) ---
    # The course's own instances, so the figures agree with its text.
    Figure(
        "graph-turan",
        {"type": "turan",
         "params": {"n": 7, "r": 3, "highlight_clique_free": True}},
        "The Turán graph T(7,3): parts of sizes 3, 2 and 2 drawn as three "
        "coloured columns with every cross-part edge; the caption states 16 "
        "edges and no K4",
    ),
    Figure(
        "graph-prufer-storyboard",
        {"type": "graph_algorithm",
         "params": {"algorithm": "prufer_encode", "animate": False, "columns": 3,
                    "expect": [3, 3, 4, 4],
                    "title": "Prüfer code: delete the smallest leaf, write down its neighbour",
                    "nodes": [{"id": str(i)} for i in range(1, 7)],
                    "edges": [{"from": a, "to": b} for a, b in
                              [("1", "3"), ("2", "3"), ("3", "4"), ("4", "5"), ("4", "6")]]}},
        "Five panels of Prüfer encoding on a six-vertex tree; each deleted leaf "
        "is highlighted with its edge dashed, and the code grows to (3, 3, 4, 4)",
    ),
    Figure(
        "graph-stable-matching-storyboard",
        {"type": "graph_algorithm",
         "params": {"algorithm": "stable_matching", "animate": False, "columns": 4,
                    "title": "Gale–Shapley: ten proposals to a stable matching",
                    "proposers": {"A": ["4", "3", "1", "2"], "B": ["3", "4", "2", "1"],
                                  "C": ["1", "2", "4", "3"], "D": ["1", "4", "3", "2"]},
                    "receivers": {"1": ["B", "A", "C", "D"], "2": ["A", "B", "D", "C"],
                                  "3": ["D", "A", "B", "C"], "4": ["C", "B", "A", "D"]}}},
        "Twelve panels of Gale–Shapley on four proposers and four receivers: "
        "each proposal, each held offer, each rejection drawn dashed, ending on "
        "the stable matching A–1, B–4, C–2, D–3 after ten proposals",
    ),
    Figure(
        "graph-havel-hakimi-storyboard",
        {"type": "havel_hakimi",
         "params": {"animate": False, "realize": True, "sequence": [3, 3, 2, 2, 2],
                    "title": "Havel–Hakimi: reduce the sequence, then build the graph back up"}},
        "Seven panels: the degree sequence (3,3,2,2,2) reduced to (0,0) with the "
        "decremented entries highlighted, then the graph realised one restored "
        "vertex at a time",
    ),
    Figure(
        "graph-floyd-warshall-storyboard",
        {"type": "floyd_warshall",
         "params": {"animate": False, "directed": True,
                    "title": "Floyd–Warshall: one table per intermediate vertex",
                    "nodes": [{"id": x} for x in "ABCD"],
                    "edges": [{"from": a, "to": b, "weight": w} for a, b, w in
                              [("A", "B", 3), ("B", "C", -2), ("A", "C", 5),
                               ("C", "D", 1), ("D", "B", 4), ("A", "D", 10)]]}},
        "Five distance tables for a four-vertex digraph with one negative edge, "
        "infinity rendered explicitly and every entry an intermediate vertex "
        "improves highlighted",
    ),
    Figure(
        "graph-hamiltonian-animated",
        {"type": "graph_algorithm",
         "params": {"algorithm": "hamiltonian_search", "animate": True,
                    "duration_s": 1.0, "loop": True, "start": "0", "expect": "cycle",
                    "title": "Backtracking for a Hamiltonian cycle of the octahedron",
                    "nodes": [{"id": str(i)} for i in range(6)],
                    "edges": [{"from": str(a), "to": str(b)}
                              for a in range(6) for b in range(a + 1, 6)
                              if {a, b} not in ({0, 1}, {2, 3}, {4, 5})]}},
        "Backtracking search on the octahedron as an animated SVG: the partial "
        "path grows, a dead end backtracks, and the found Hamiltonian cycle is "
        "the last frame",
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
