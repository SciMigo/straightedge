# AGENTS.md

Guidance for AI agents working in this repository.

## Project

`straightedge` renders a math or technical figure — animated (Manim → MP4) or
static (Python → SVG) — from a request or a named template, and checks the result
is legible before trusting it. See `README.md` for the pipeline and the docs
under `docs/` for the design of each lane.

## Tests

```bash
python -m pytest -q
```

`pyproject.toml` sets `pythonpath = ["."]`, so tests run from the repo root.
`pytest` is in the `dev` extra: `pip install '.[dev]'` (or `-r requirements.txt`
for the full render/STT/dev set).

Live Manim renders are marked `smoke` and excluded by default, because they need
LaTeX and ffmpeg and take minutes. Run them with `pytest -m smoke` when you have
touched a scene builder — they catch what `ast.parse` cannot: LaTeX compile
errors, primitive signature drift, missing glyphs.

## Invariants worth knowing before you edit

**The core has no runtime dependencies.** `dependencies = []` in
`pyproject.toml` is deliberate: the SVG lane is pure stdlib, so a caller who
only wants figures pays nothing for the video lane. Manim, Whisper and the MCP
SDK live behind extras and are imported lazily. Adding an unconditional import of
any of them at package level is a breaking change for every figure-only user.

**A visual can render successfully and still be wrong.** Three checks run at
three moments and catch different things — `preconditions` before anything is
drawn, `qc` on the built scene, `labels` on the emitted text. When you add a
capability, ask which of the three would catch its failure, and add the check if
the answer is none.

**The agent lane executes model-written Python.** `agent/safety.py` screens the
generated scene with an AST allowlist before it runs. That is defence in depth,
not a sandbox, and it is documented as such — do not describe it as a security
boundary, and do not widen the allowlist without saying what the new surface
lets a scene reach.

**Narration timing is a contract, not a convenience.** Builders wrap narrated
steps in `_beat` / `_beat_stretch` so a measured narration length can drive the
pacing. A step with no measurement must keep the timing it was written with;
that fallback is what allows builders to be converted one at a time. See
`docs/narration-timing.md`, and extend
`tests/test_narration_driven_timing.py` when you convert one.

**Examples are arguments, not decoration.** Everything under `examples/`
simulates the mechanism, asserts its central claim, and only then animates it —
so a scene whose claim stops being true fails to render rather than producing a
convincing picture of something false. A new example that draws its conclusion
instead of computing it does not belong there.
