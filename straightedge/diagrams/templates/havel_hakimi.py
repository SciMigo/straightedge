"""Checked Havel–Hakimi reductions, with an optional graph realization."""

from __future__ import annotations

from typing import Any, Dict, List

from ...graphs import GraphError, havel_hakimi_steps
from ...qc import Finding
from ..registry import DIAGRAM_REGISTRY, register


MAX_STEPS = 12


def _steps(params: Dict[str, Any]):
    return havel_hakimi_steps(params.get("sequence"), bool(params.get("realize", False)))


def _findings(params: Dict[str, Any]) -> List[Finding]:
    try:
        steps = _steps(params)
    except GraphError as exc:
        witness = exc.witness
        label = None
        if isinstance(witness, (list, tuple)):
            label = "(" + ", ".join(str(value) for value in witness) + ")"
        elif witness is not None:
            label = str(witness)
        return [Finding("havel_hakimi_sequence", "error", str(exc), label=label)]
    if len(steps) > MAX_STEPS:
        return [Finding("havel_hakimi_size", "error",
                        f"the trace takes {len(steps)} panels; at most {MAX_STEPS} fit")]
    return []


def frames(params: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for step in _steps(params):
        if "graph_edges" in step.extras:
            visible = set(step.extras["visible_edges"])
            edges = [{"from": u, "to": v} for u, v in step.extras["graph_edges"]
                     if (min(u, v), max(u, v)) in visible]
            visual = {"type": "graph", "params": {
                "nodes": [{"id": vertex} for vertex in step.extras["graph_nodes"]],
                "edges": edges,
                "highlights": {
                    "nodes": step.node_states,
                    "edges": [list(edge) for edge in visible],
                },
                "caption": step.caption,
            }}
        else:
            visual = {"type": "array_state", "params": {
                "values": step.extras.get("values", []),
                "highlights": step.extras.get("highlights", {}),
            }}
        out.append({"label": step.label, "visual": visual})
    return out


@register("havel_hakimi")
class HavelHakimiTemplate:
    """Reduce a degree sequence and, when requested, realize its graph."""

    motion = "optional"
    checks = ["nonnegative degrees below n", "even degree sum",
              "nonnegative Havel–Hakimi reductions", "readable panel count"]

    def refusal_findings(self, params: Dict[str, Any]) -> List[Finding]:
        return _findings(params)

    def render(self, params: Dict[str, Any]) -> str:
        params.get("sequence")
        params.get("realize", False)
        animate = bool(params.get("animate", False))
        params.get("duration_s", 1.2)
        params.get("loop", True)
        params.get("columns", 3)
        params.get("title")
        if self.refusal_findings(params):
            return ""
        trace = frames(params)
        title = str(params.get("title", "Havel–Hakimi"))
        if animate:
            return DIAGRAM_REGISTRY["animated_trace"].render({
                "title": title, "frames": trace,
                "duration_s": float(params.get("duration_s", 1.2)),
                "loop": bool(params.get("loop", True)),
            })
        return DIAGRAM_REGISTRY["algorithm_trace"].render({
            "title": title, "steps": trace,
            "columns": int(params.get("columns", 3)), "show_step_numbers": True,
        })
