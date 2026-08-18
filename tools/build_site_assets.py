#!/usr/bin/env python3
"""Render the site's demo assets, and publish them to R2.

Every MP4, poster and GIF under ``site/assets/`` was produced by hand, and
nothing in the repository could reproduce any of them. That is fine until a
scene builder changes: the video on the landing page then shows output the
library no longer produces, and there is no way to tell without rendering it
again by hand and comparing frames. This script is that missing step.

The scenes below are declared, not discovered, because a demo reel is a curated
thing — ``list_templates()`` says what *can* be drawn, and only some of it is
worth putting on a landing page. What matters is that each entry names the
exact input that produced its file, so the mapping stops living in someone's
memory.

**Binaries go to R2, not into git.** ``site/assets/`` is already 3.3M against a
5.1M ``.git``; another few MP4s is the wrong direction for a source repository.
Rendered files land in a staging directory and are uploaded to the public
``scimigo-cdn`` bucket under the ``straightedge/`` prefix, and the page
references them by their public URL.

    # credentials live in ~/.bashrc, not in this repo
    python tools/build_site_assets.py --list
    python tools/build_site_assets.py linear-map matmul-outer
    python tools/build_site_assets.py linear-map --upload

Rendering needs the ``render`` extra (Manim) and ``ffmpeg`` on PATH; uploading
needs ``aws`` and the five ``R2_*`` variables. Each is checked before any work
is done, so a missing tool costs a second rather than a five-minute render.

A note on that bucket: it is fronted by a public ``r2.dev`` host, so everything
under it answers an unauthenticated GET. For demo videos that is the point. It
is *not* suitable for anything user-supplied — see the same bucket's
``user-uploads/`` prefix, which holds copyrighted material and should not be
there.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

#: Where rendered files are staged. Deliberately outside ``site/`` so a render
#: cannot accidentally be committed; ``site/assets/`` holds only what predates
#: this script.
STAGING = REPO / "build" / "site-assets"

#: Key prefix inside the bucket. Nothing else in ``scimigo-cdn`` uses it.
R2_PREFIX = "straightedge/assets"

#: Matches what the existing assets already are: 854x480 at 15fps is Manim's
#: ``-ql``, and the posters are 640x360 JPEGs cut from the video itself.
QUALITY = "l"
POSTER_WIDTH = 640
POSTER_AT = 0.60          # fraction of the way through, where a scene is built


@dataclass(frozen=True)
class Scene:
    """One demo asset, and the exact input that produces it."""

    slug: str
    kicker: str
    title: str
    #: A catalog template id, rendered through the planner.
    template: str | None = None
    params: dict = field(default_factory=dict)
    #: Or a standalone example: (directory under examples/, scene class).
    example: tuple[str, str] | None = None
    #: Second of the finished video to cut the poster from. ``None`` uses
    #: :data:`POSTER_AT` of the duration, which is wrong for a scene that ends
    #: on a title card and right for most others.
    poster_at: float | None = None
    gif: bool = False


SCENES: list[Scene] = [
    # --- new in this change -------------------------------------------------
    Scene("linear-map", "Linear algebra · eigenvectors",
          "The directions that do not turn",
          template="linear_algebra/linear_map",
          # [[2,1],[1,2]] rather than a shear: both eigendirections come out
          # off-axis (45 and -45 degrees), so neither dashed line hides under
          # the plane's own axis the way the x-axis eigenvector of [[3,1],[0,2]]
          # does. lambda=1 also gives the stronger picture — a direction that
          # does not move at all, beside one stretched by three.
          params={"matrix": [[2, 1], [1, 2]], "vectors": [[1, 0], [0, 1]],
                  "labels": ["u", "v"], "show_eigenvectors": True,
                  "show_determinant": True}),
    Scene("matmul-outer", "Linear algebra · the product, read four ways",
          "AB as a sum of rank-1 terms",
          template="linear_algebra/matmul_views",
          params={"a": [[1, 2], [3, 4]], "b": [[0, 1], [1, 1]], "view": "outer"}),

    # --- already on the site, declared here so they are reproducible --------
    # These files predate this script and are not re-rendered unless asked for
    # by name with --force; the entries exist so the mapping from asset to
    # input is written down rather than remembered.
    Scene("derivative-tangent", "Calculus · tangent as a limit",
          "Secant becomes tangent",
          template="calculus/derivative_tangent", gif=True),
    Scene("riemann-integral", "Calculus · area by refinement",
          "Rectangles become the integral",
          template="calculus/riemann_integral", gif=True),
    Scene("ellipse-foci", "Conics · the focal property",
          "Two foci, one constant sum",
          template="conic/ellipse_foci", gif=True),
    Scene("unit-circle-sine", "Trigonometry · where the wave comes from",
          "The circle unrolled",
          template="trig/unit_circle_to_sine", gif=True),
    Scene("systolic-array", "Dataflow · weight-stationary matrix unit",
          "Why the input skew exists",
          example=("systolic_array", "SystolicArray")),
    Scene("pipeline-schedules", "Dataflow · GPipe against 1F1B",
          "The same bubble, four times the memory",
          example=("pipeline_schedules", "PipelineSchedules")),
    Scene("ring-allreduce", "Dataflow · reduce-scatter then all-gather",
          "Bytes per rank stay flat",
          example=("ring_allreduce", "RingAllReduce")),
]

BY_SLUG = {s.slug: s for s in SCENES}


# --------------------------------------------------------------- prerequisites


def require(*tools: str) -> None:
    """Fail before a five-minute render rather than after it."""
    missing = [t for t in tools if shutil.which(t) is None]
    if missing:
        sys.exit(f"not on PATH: {', '.join(missing)}")


def r2_env() -> dict:
    """The five R2 variables, or exit saying which are missing.

    Read from the environment only. They live in ``~/.bashrc`` on the machine
    that publishes; putting them in this repository would publish them.
    """
    names = ("R2_ENDPOINT_URL", "R2_BUCKET", "R2_PUBLIC_BASE_URL",
             "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY")
    values = {n: os.environ.get(n) for n in names}
    missing = [n for n, v in values.items() if not v]
    if missing:
        sys.exit("missing R2 configuration: " + ", ".join(missing)
                 + "\n  set -a; source ~/.bashrc; set +a")
    return values


# ------------------------------------------------------------------ rendering


def render(scene: Scene, work: Path) -> Path:
    """Render one scene to an MP4 in ``work``. Returns the path."""
    if scene.example:
        return _render_example(scene, work)
    return _render_template(scene, work)


def _render_template(scene: Scene, work: Path) -> Path:
    from straightedge import plan_from_template
    from straightedge.preconditions import blocking, validate
    from straightedge.renderer import render_scene, write_scene

    plan = plan_from_template(scene.template, scene.params)

    # The library's own gate, applied to its own demo reel. A landing page
    # asset that trips a blocking precondition is exactly the confidently-wrong
    # output the project exists to refuse, and shipping one on the front page
    # would be the worst place to do it.
    violations = blocking(validate(plan))
    if violations:
        sys.exit(f"{scene.slug}: refused by preconditions\n  "
                 + "\n  ".join(str(v) for v in violations))

    scene_path = write_scene(plan, work, name=scene.slug)
    result = render_scene(scene_path, quality=QUALITY, media_dir=work / "media",
                          stdout=sys.stderr)
    if result.returncode != 0 or result.output_path is None:
        sys.exit(f"{scene.slug}: manim exited {result.returncode}")
    return result.output_path


def _render_example(scene: Scene, work: Path) -> Path:
    """Standalone example scenes render themselves; they take no plan."""
    directory, class_name = scene.example
    source = REPO / "examples" / directory / "scene.py"
    if not source.exists():
        sys.exit(f"{scene.slug}: no example at {source}")

    media = work / "media"
    subprocess.run(
        [sys.executable, "-m", "manim", f"-q{QUALITY}", "--media_dir", str(media),
         "--disable_caching", str(source), class_name],
        check=True, cwd=source.parent, stdout=sys.stderr)

    found = list(media.rglob(f"{class_name}.mp4"))
    if not found:
        sys.exit(f"{scene.slug}: manim wrote no {class_name}.mp4 under {media}")
    return found[0]


# -------------------------------------------------------------- stills and gifs


def duration(mp4: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nk=1:nw=1", str(mp4)],
        check=True, capture_output=True, text=True)
    return float(out.stdout.strip())


def poster(mp4: Path, out: Path, at: float | None) -> Path:
    """One frame, scaled to the width the existing posters use.

    Taken from the finished video rather than rendered separately, so the still
    is guaranteed to be a frame the viewer will actually see.
    """
    seconds = at if at is not None else duration(mp4) * POSTER_AT
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{seconds:.3f}", "-i", str(mp4),
         "-frames:v", "1", "-vf", f"scale={POSTER_WIDTH}:-2", "-q:v", "3", str(out)],
        check=True)
    return out


def gif(mp4: Path, out: Path) -> Path:
    """A palette-generated GIF, which is the difference between 300K and 3M."""
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        palette = Path(tmp) / "palette.png"
        chain = "fps=10,scale=480:-2:flags=lanczos"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp4),
                        "-vf", f"{chain},palettegen", str(palette)], check=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp4),
                        "-i", str(palette), "-lavfi", f"{chain} [x]; [x][1:v] paletteuse",
                        str(out)], check=True)
    return out


# ------------------------------------------------------------------- publishing


def upload(paths: list[Path], env: dict, *, dry_run: bool = False) -> dict[Path, str]:
    """Put each file under ``straightedge/assets/<kind>/`` and return its URL.

    Content types are set explicitly. R2 serves what it is told, and an MP4
    stored as ``application/octet-stream`` downloads instead of playing —
    a failure that only shows up in a browser, never in the upload.
    """
    types = {".mp4": "video/mp4", ".jpg": "image/jpeg", ".gif": "image/gif"}
    urls: dict[Path, str] = {}
    for path in paths:
        kind = {".mp4": "mp4", ".jpg": "posters", ".gif": "gif"}[path.suffix]
        key = f"{R2_PREFIX}/{kind}/{path.name}"
        url = f"{env['R2_PUBLIC_BASE_URL'].rstrip('/')}/{key}"
        urls[path] = url
        if dry_run:
            print(f"  would upload {path.name} -> {url}")
            continue
        subprocess.run(
            ["aws", "s3", "cp", str(path), f"s3://{env['R2_BUCKET']}/{key}",
             "--endpoint-url", env["R2_ENDPOINT_URL"],
             "--content-type", types[path.suffix],
             # A demo asset is immutable: a changed scene gets re-uploaded under
             # the same key, so a long max-age with no revalidation would pin the
             # old video in caches for a year.
             "--cache-control", "public, max-age=3600"],
            check=True,
            env={**os.environ,
                 "AWS_ACCESS_KEY_ID": env["R2_ACCESS_KEY_ID"],
                 "AWS_SECRET_ACCESS_KEY": env["R2_SECRET_ACCESS_KEY"],
                 "AWS_DEFAULT_REGION": "auto"},
            stdout=subprocess.DEVNULL)
        print(f"  uploaded {path.name} -> {url}")
    return urls


# ------------------------------------------------------------------------- main


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("slugs", nargs="*", help="scenes to build (default: none — pass --list)")
    p.add_argument("--list", action="store_true", help="show every declared scene and exit")
    p.add_argument("--all", action="store_true", help="build every declared scene")
    p.add_argument("--upload", action="store_true", help="publish to R2 when done")
    p.add_argument("--dry-run", action="store_true", help="with --upload, print URLs only")
    p.add_argument("--out", type=Path, default=STAGING, help=f"staging dir (default {STAGING})")
    p.add_argument("--json", action="store_true", help="emit the manifest as JSON")
    args = p.parse_args(argv)

    if args.list:
        for s in SCENES:
            source = s.template or f"examples/{s.example[0]}:{s.example[1]}"
            print(f"{s.slug:20} {source}")
        return 0

    slugs = [s.slug for s in SCENES] if args.all else args.slugs
    if not slugs:
        p.error("name at least one scene, or pass --all or --list")
    unknown = [s for s in slugs if s not in BY_SLUG]
    if unknown:
        p.error(f"unknown scene(s): {', '.join(unknown)}")

    require("ffmpeg", "ffprobe")
    env = r2_env() if args.upload else {}
    if args.upload:
        require("aws")

    manifest = {}
    args.out.mkdir(parents=True, exist_ok=True)
    for slug in slugs:
        scene = BY_SLUG[slug]
        print(f"[{slug}] rendering…", file=sys.stderr)
        with tempfile.TemporaryDirectory() as tmp:
            rendered = render(scene, Path(tmp))
            mp4 = args.out / f"{slug}.mp4"
            shutil.copy2(rendered, mp4)

        built = [mp4, poster(mp4, args.out / f"{slug}.jpg", scene.poster_at)]
        if scene.gif:
            built.append(gif(mp4, args.out / f"{slug}.gif"))

        entry = {"kicker": scene.kicker, "title": scene.title,
                 "files": {f.suffix.lstrip("."): str(f) for f in built}}
        if args.upload:
            urls = upload(built, env, dry_run=args.dry_run)
            entry["urls"] = {f.suffix.lstrip("."): urls[f] for f in built}
        manifest[slug] = entry

    if args.json:
        print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
