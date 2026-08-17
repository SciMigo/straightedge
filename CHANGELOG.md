# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project aims to
follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
