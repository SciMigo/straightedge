# Contributing

Thanks for looking. Straightedge renders math and technical figures from a
request or a template, and checks that the result is legible — so the bar for a
change is not just "does it run" but "does it draw the right thing, and can you
see when it doesn't."

## Setup

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e '.[render,dev]'      # add ,mcp for the server, ,stt for audio
pytest -q                            # the fast suite: no Manim needed for most of it
```

The core (`build_plan`, `validate`, `list_templates`, the checks) imports without
Manim. Only rendering needs the `render` extra.

## The rule the code follows

Two properties are the reason this project exists; keep them true.

- **It checks its own output.** `qc.py` inspects the built scene for defects a
  human would catch by opening the frame. A new scene builder is not done until a
  render of it comes back clean under QC — `tools/qc_sweep.py` renders every
  builder and reports the findings.
- **It admits what it cannot do.** The planner never crashes on an unmatched
  request; it falls back to a generic scene and says so (`match ==
  "topic-fallback"`). Do not paper over a gap — surface it.

## Tests

- Every change needs a test. A bug fix needs a test that fails before it.
- The visual checks are unit-testable without Manim — `check()` takes plain
  `Box` values. Prefer that to a live render where you can.
- The `smoke` marker runs a real Manim render per builder; it is slow and
  excluded by default (`pytest -m smoke` to opt in). Run it if you touched a
  scene builder or the renderer.
- Assert on structured fields (`finding.severity`, `finding.box`, error `code`),
  not on prose — the wording changes.

## Style

- Docstrings explain *why*, naming the specific defect that motivated the code.
  See `qc.py` for the standard; it is the house style and worth matching.
- Match the surrounding code's density and idiom.

## Adding a template

A new animation concept is a scene builder plus a precondition check plus a plan
route; a new figure is a `@register`ed template in `straightedge.diagrams`.
Either way, add it to the catalog's reach (`list_templates` should enumerate it)
and give it a test. `docs/agent-interface.md` explains why enumeration matters.

## Security

Straightedge executes generated code and evaluates expressions. If you find a way
past `agent/safety.py` or `expr.py`, **do not open a public issue** — see
[`SECURITY.md`](SECURITY.md).

## Pull requests

Explain what the change is and why in the description — the same *why* the
docstrings carry. Keep a PR to one idea. CI must pass.
