# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project aims to
follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-08-17

A minor rather than a patch release: the public API grew by seven names and a
CLI flag, and nothing was removed or changed. Code written against 0.1.0 keeps
working — `style` is the last parameter of `scene_code_for` and defaults to
`textbook`, which is tested against Manim's own palette, so existing renders are
unchanged unless a theme is asked for.

### Added
- A style layer (`straightedge.style`) naming colours, stroke widths, and fill
  opacities by **visual role** rather than by what they happen to depict, so one
  scene can be drawn more than one way. Three themes ship: `textbook` (Manim's
  own palette, the default), `paper` (light, for print and slides), and
  `dataflow` (the dark look the `examples/` scenes use). Select one with
  `--style` on the CLI, or `theme("paper")` from Python.
- `examples/tensor_parallel`: tensor parallelism given the same treatment as the
  other dataflow examples — simulated, asserted, and only then animated.
- [`docs/styling.md`](https://github.com/SciMigo/straightedge/blob/main/docs/styling.md),
  covering the token vocabulary and why generated scenes resolve a theme at
  generation time while hand-written scenes import it.

### Changed
- The package summary no longer scopes the project to lectures. It now reads
  "Generate deterministic, machine-checkable SVG diagrams and Manim animations
  from structured data, templates, or a prompt", matching the wording used in
  the README and on the gallery — three descriptions of the same library made it
  harder to place, for readers and for search alike. Package metadata is
  immutable once published, so 0.1.0 keeps the old wording on PyPI.

## [0.1.0] - 2026-08-17

The first public release. Everything below is new relative to the project's
private history as `math-voice`.

### Added
- Natural-language and named-template rendering of math figures — animated
  (Manim → MP4) and static (Python → SVG) — from one library.
- `list_templates()` and the `list-templates` command: enumerate every template
  across both lanes, with how each is invoked and the parameters it reads.
- `--template` (and the MCP `template` argument): render any shipped animation by
  name, in any language, with no keyword routing and no LLM.
- Automated visual QC (`qc.py`): checks the built scene for empty, clipped,
  off-frame, and overlapping content. Findings carry the defect's coordinates.
- Preconditions (`preconditions.py`): refuse a plan that would draw the wrong
  thing before spending a render.
- `estimate(plan, quality)`: a render-time budget before the render.
- `AnimationPlan.match`: whether a request reached a specific builder or a
  generic fallback.
- Structured CLI output (`--json`) and typed errors (`errors.py`) that carry a
  `code` and a `remedy`.
- An MCP server (`straightedge.mcp_server`, `straightedge[mcp]`) exposing
  `list_templates`, `plan`, `validate`, and `render` as tools.
- `SKILL.md` and `examples/agent_loop.py`: the agent workflow, documented and
  runnable.

### Security
- The agent lane runs generated code behind an AST allowlist (`agent/safety.py`);
  the figure lane evaluates expressions behind a strict allowlist (`expr.py`).
  See [`SECURITY.md`](SECURITY.md).
