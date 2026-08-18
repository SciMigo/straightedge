# site/assets

What is still here, and why the rest is not.

`gif/` and `svg/` are in git. The GIFs are the images `README.md` embeds through
`raw.githubusercontent.com`, so they render on GitHub and PyPI; tying them to
anything but the repository would mean the project's own landing images break
if that host's public binding ever changes. They are 292K, which is not the
weight worth optimising.

`mp4/` and `posters/` are **not** in git. They were 2.8M against a 5.1M `.git`,
they are regenerated rather than edited, and nothing reads them except the two
HTML pages. They live in the public `scimigo-cdn` R2 bucket under
`straightedge/assets/`, and the pages reference them by URL:

    https://pub-ae0e951cb13d4628913ced2bc423d839.r2.dev/straightedge/assets/mp4/<slug>.mp4
    https://pub-ae0e951cb13d4628913ced2bc423d839.r2.dev/straightedge/assets/posters/<slug>.jpg

`tools/build_site_assets.py` renders and publishes them, and declares the exact
input behind every slug — including the seven that predate it. To change one:

    python tools/build_site_assets.py <slug> --upload

The bucket is fronted by a public `r2.dev` host, which is what makes this work
and is also why nothing user-supplied belongs under this prefix.
