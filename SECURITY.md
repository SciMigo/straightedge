# Security Policy

## Why this file matters here

Straightedge executes generated code. The agent lane (`agent-*` commands, the
LLM writer/reviewer/repair loop) runs Python that a model wrote, and the figure
lane evaluates caller-supplied math expressions. Both are guarded — `agent/
safety.py` is an AST allowlist over the generated scene, and `expr.py` is a
strict allowlist over expressions — but a sandbox escape in either is a real
vulnerability, not a bug. This project therefore needs a disclosure channel more
than a typical library does.

## Reporting a vulnerability

**Do not open a public issue for a security problem.** Report it privately
through GitHub's ["Report a vulnerability"](https://github.com/SciMigo/straightedge/security/advisories/new)
form (Security → Advisories), which opens a private advisory only maintainers
can see.

Please include:

- what the flaw is and where (file and, if you have it, line),
- a minimal reproduction — for a sandbox escape, the input that escapes,
- what an attacker gains.

A demonstrated escape is far more actionable than a described one; a runnable
payload gets prioritized.

## What is in scope

- **Sandbox escape in the agent lane** — generated code reaching `open`, `exec`,
  `subprocess`, the network, or the filesystem despite `agent/safety.py`.
- **Expression-evaluation escape** — a `--params`/plan expression executing
  arbitrary code past `expr.py`'s allowlist.
- **Injection into emitted output** — a parameter reaching raw scene source or
  SVG unescaped.

## What is not

- Manim, LaTeX, or other dependencies — report those upstream.
- Denial of service from a deliberately expensive but legitimate render.
- Anything requiring the attacker to already control the host the render runs on.

## Handling

We aim to acknowledge a report within a few days and to fix a confirmed
vulnerability before the advisory is made public, crediting the reporter unless
they prefer otherwise.
