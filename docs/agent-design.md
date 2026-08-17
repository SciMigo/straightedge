# LLM Manim Agent Design

`straightedge` keeps deterministic templates for reliable classroom clips, but
advanced prompts need an agentic path:

```text
Chinese teacher request
-> LLM planner -> structured AnimationSpec JSON
-> LLM writer -> Manim GeneratedScene code
-> local AST safety check
-> LLM reviewer -> approval or issues
-> Manim render with captured logs
-> LLM repairer -> patched code
-> retry, then deterministic fallback if enabled
```

## CLI

```bash
python3 -m straightedge.cli agent-plan "展示 sin(x) 的泰勒展开"
python3 -m straightedge.cli agent-scaffold "展示 sin(x) 的泰勒展开"
python3 -m straightedge.cli agent-render "展示 sin(x) 的泰勒展开" --max-attempts 3
```

Agent commands use an OpenAI-compatible chat-completions API:

```bash
export OPENAI_API_KEY=...
export STRAIGHTEDGE_AGENT_MODEL=gpt-4.1-mini
# optional for compatible providers:
export OPENAI_BASE_URL=https://api.openai.com/v1
export STRAIGHTEDGE_LLM_TIMEOUT=300
```

## Guardrails

The generated scene is checked before review/render:

- must parse as Python;
- must define exactly one `GeneratedScene`;
- may only import exactly `manim`, `math`, and `numpy.linalg` (Manim's public
  namespace already exposes NumPy as `np`);
- rejects direct imports and obvious calls involving filesystem, shell, network,
  `eval`, `exec`, `open`, and dunder attribute access.

The generated code still runs as Python during Manim rendering. Manim's own
public namespace includes helpers that can access the host, and static AST
checks cannot prove arbitrary Python safe, so these checks are guardrails, not
filesystem or process isolation. Run untrusted code only in an isolated
environment.

## Fallback

`agent-render` defaults to deterministic fallback after repair attempts are
exhausted. Use `--no-fallback` when you want failures surfaced instead.

The deterministic path is still useful for demos and regression safety. The LLM
agent should be used for unsupported or more creative concepts.
