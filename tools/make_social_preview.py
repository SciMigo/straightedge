#!/usr/bin/env python3
"""Build the repository's social preview card.

GitHub renders a card whenever the repository URL is shared -- in a chat, on
Hacker News, in a tweet. Without one uploaded it generates a grey text card
carrying the description and the star count, which for this project is exactly
backwards: the argument for a diagram library is the diagrams, and the default
card shows none of them.

So the card is built from the repository's own figures. They are the claim.

`site/assets/social-preview.png` is committed, which the rule in
`build_site_assets.py` otherwise forbids -- binaries belong in R2, not in git.
Three reasons this one is an exception rather than a lapse: it is 66K against
that file's 3.3M of MP4s, it is singular rather than a set that grows with every
render, and GitHub's social-preview upload takes a *file* through the web UI,
so it has to be fetchable by whoever is doing the uploading.

Uploading is manual. The REST API exposes no endpoint for it:

    Settings -> General -> Social preview -> Edit -> Upload an image

Requires `rsvg-convert` (librsvg) and Pillow.

    python tools/make_social_preview.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
SVG_DIR = ROOT / "site" / "assets" / "svg"
OUT = ROOT / "site" / "assets" / "social-preview.png"

# GitHub's stated size. Cards are often displayed at half this, so the type is
# sized to survive that rather than to fill the canvas.
W, H = 1280, 640
MARGIN = 44

BG = (255, 255, 255)
INK = (25, 28, 33)
MUTED = (108, 117, 128)
# Taken from the figures themselves rather than invented, so the card and its
# contents are not two different palettes sitting next to each other.
ACCENT = (33, 150, 243)
RULE = (226, 230, 235)

FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")
SANS = FONT_DIR / "DejaVuSans.ttf"
SANS_BOLD = FONT_DIR / "DejaVuSans-Bold.ttf"
MONO = FONT_DIR / "DejaVuSansMono.ttf"

# The figures are drawn in dark strokes on transparency: they are meant for a
# light page, and would vanish on a dark card.
FIGURES = [
    ("unit-circle", 268, (742, 62)),
    ("riemann-sum", 196, (905, 372)),
]


def rasterise(name: str, height: int) -> Image.Image:
    """SVG -> PNG at a known height, via librsvg.

    Rasterising each figure separately rather than inlining them into one SVG
    avoids the CSS class collisions that would follow from merging several
    stylesheets that each assume they are alone in the document.
    """
    source = SVG_DIR / f"{name}.svg"
    if not source.exists():
        raise SystemExit(f"missing figure: {source}")
    png = subprocess.run(
        ["rsvg-convert", "-h", str(height), "-b", "white", str(source)],
        check=True,
        capture_output=True,
    ).stdout
    import io

    return Image.open(io.BytesIO(png)).convert("RGBA")


def build() -> Image.Image:
    card = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(card)

    for name, height, (x, y) in FIGURES:
        figure = rasterise(name, height)
        # Assert rather than eyeball: a figure whose aspect ratio changes would
        # otherwise silently run off the edge, and the failure is only visible
        # by opening the file.
        if x + figure.width > W - MARGIN:
            raise SystemExit(f"{name} overflows the right edge: {x + figure.width} > {W - MARGIN}")
        if y + figure.height > H - MARGIN:
            raise SystemExit(f"{name} overflows the bottom: {y + figure.height} > {H - MARGIN}")
        card.paste(figure, (x, y), figure)

    title = ImageFont.truetype(str(SANS_BOLD), 74)
    tag = ImageFont.truetype(str(SANS), 30)
    meta = ImageFont.truetype(str(MONO), 22)

    x = 84
    draw.text((x, 138), "Straightedge", font=title, fill=INK)
    draw.line([(x, 248), (x + 112, 248)], fill=ACCENT, width=7)
    draw.text((x, 288), "Deterministic, machine-checkable", font=tag, fill=INK)
    draw.text((x, 328), "SVG diagrams and Manim animations.", font=tag, fill=INK)
    draw.text((x, 386), "Generated from structure, not guessed.", font=tag, fill=MUTED)
    draw.line([(x, 462), (x + 548, 462)], fill=RULE, width=2)
    draw.text((x, 492), "pip install straightedge", font=meta, fill=ACCENT)
    draw.text((x, 530), "MIT  ·  Python 3.10+  ·  SciMigo/straightedge", font=meta, fill=MUTED)

    return card


def main() -> int:
    if not SANS.exists():
        raise SystemExit(f"missing font: {SANS} (apt install fonts-dejavu-core)")
    card = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    card.save(OUT, "PNG", optimize=True)
    print(f"{OUT.relative_to(ROOT)}  {card.size[0]}x{card.size[1]}  {OUT.stat().st_size // 1024}K")
    print("upload: Settings -> General -> Social preview -> Edit")
    return 0


if __name__ == "__main__":
    sys.exit(main())
