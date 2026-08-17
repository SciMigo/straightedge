# A container for running Straightedge — and specifically for isolating the
# agent lane, which executes model-written Python.
#
# The AST allowlist in `agent/safety.py` is defence in depth, not a sandbox. The
# real boundary is this: build the image, then run the agent command with the
# network off and only an output directory mounted, so generated code that
# escapes the checks still cannot reach the network or the host filesystem.
#
#   docker build -t straightedge-render -f docker/Dockerfile .
#
#   # untrusted prompt or model — isolate it:
#   docker run --rm --network=none -v "$PWD/out:/out" \
#     -e OPENAI_API_KEY="$OPENAI_API_KEY" \
#     straightedge-render agent-render "…your prompt…" --output-dir /out
#
# The deterministic lanes (`render`, `--template`, figures) do not execute model
# output and do not need this; they run fine on the host.

FROM python:3.12-slim

# Manim's runtime: cairo/pango for rendering, ffmpeg for muxing, a curated TeX
# for the LaTeX the emitted preamble actually asks for (standalone, amsmath,
# amssymb, babel), and a CJK font so Chinese labels are not tofu boxes. Build
# tools are needed to compile pycairo/manimpango and are dropped after.
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential pkg-config \
      libcairo2-dev libpango1.0-dev libgl1 \
      ffmpeg \
      texlive-latex-base texlive-latex-extra texlive-fonts-recommended \
      texlive-binaries \
      fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

ENV PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY . .
# The render extra pulls Manim; the base package is pure stdlib.
RUN pip install ".[render]"

# Warm fontconfig so the first render inside a --network=none container does not
# stall building its cache.
RUN fc-cache -f >/dev/null 2>&1 || true

# Renders land wherever --output-dir points; mount a volume there.
ENTRYPOINT ["straightedge"]
