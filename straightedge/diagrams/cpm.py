"""Critical Path Method (CPM) engine for project-management diagrams.

Shared by the ``project_network`` (Activity-on-Node) and ``gantt`` templates.
Given a list of activities with durations and immediate predecessors, it runs
the forward + backward pass and returns each activity's ES/EF/LS/LF, total
float, and whether it is on the critical path — plus a topological order and a
layout level (longest-path depth) for drawing.

This is the whole reason we render PM diagrams from structured data rather than
asking an image model: the schedule has a *unique correct answer*, and we want
the figure to teach it exactly (and highlight the critical path), not approximate
it. See memory ``freeform-html-slides-and-diagrams``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Sequence


@dataclass
class Activity:
    id: str
    duration: float
    predecessors: List[str] = field(default_factory=list)
    name: str = ""

    # filled by compute_cpm
    es: float = 0.0
    ef: float = 0.0
    ls: float = 0.0
    lf: float = 0.0
    total_float: float = 0.0
    critical: bool = False
    level: int = 0


@dataclass
class CpmResult:
    activities: Dict[str, Activity]
    order: List[str]            # topological order
    project_duration: float
    critical_path: List[str]    # ids on the critical path, in topo order
    levels: Dict[str, int]      # id -> longest-path depth (x layout rank)


def _coerce_activities(raw: Sequence[Any]) -> Dict[str, Activity]:
    acts: Dict[str, Activity] = {}
    for item in raw or []:
        if isinstance(item, Mapping):
            m = item
        elif hasattr(item, "__dict__"):
            m = vars(item)
        else:
            continue
        aid = str(m.get("id") or m.get("name") or "").strip()
        if not aid:
            continue
        preds_raw = m.get("predecessors") or m.get("preds") or m.get("depends_on") or []
        if isinstance(preds_raw, str):
            # tolerate "B、C" / "B,C" / "B C"
            preds = [p for p in _split_preds(preds_raw)]
        else:
            preds = [str(p).strip() for p in preds_raw if str(p).strip()]
        try:
            dur = float(m.get("duration", m.get("dur", 0)) or 0)
        except (TypeError, ValueError):
            dur = 0.0
        acts[aid] = Activity(id=aid, duration=dur, predecessors=preds,
                             name=str(m.get("name") or "").strip())
    # Drop predecessor references that don't exist (robustness).
    for a in acts.values():
        a.predecessors = [p for p in a.predecessors if p in acts]
    return acts


def _split_preds(s: str) -> List[str]:
    out: List[str] = []
    token = ""
    for ch in s:
        if ch in ",，、; 　":
            if token.strip():
                out.append(token.strip())
            token = ""
        else:
            token += ch
    if token.strip():
        out.append(token.strip())
    return out


def _topo_order(acts: Dict[str, Activity]) -> List[str]:
    """Kahn's algorithm. Raises ValueError on a cycle."""
    indeg = {aid: 0 for aid in acts}
    succ: Dict[str, List[str]] = {aid: [] for aid in acts}
    for a in acts.values():
        for p in a.predecessors:
            indeg[a.id] += 1
            succ[p].append(a.id)
    queue = sorted([aid for aid, d in indeg.items() if d == 0])
    order: List[str] = []
    while queue:
        n = queue.pop(0)
        order.append(n)
        for s in sorted(succ[n]):
            indeg[s] -= 1
            if indeg[s] == 0:
                queue.append(s)
    if len(order) != len(acts):
        raise ValueError("activity graph has a cycle")
    return order


def compute_cpm(raw_activities: Sequence[Any]) -> CpmResult:
    """Run the CPM forward + backward pass over the activities."""
    acts = _coerce_activities(raw_activities)
    if not acts:
        return CpmResult({}, [], 0.0, [], {})

    order = _topo_order(acts)
    succ: Dict[str, List[str]] = {aid: [] for aid in acts}
    for a in acts.values():
        for p in a.predecessors:
            succ[p].append(a.id)

    # Forward pass + layout level.
    for aid in order:
        a = acts[aid]
        if a.predecessors:
            a.es = max(acts[p].ef for p in a.predecessors)
            a.level = max(acts[p].level for p in a.predecessors) + 1
        else:
            a.es = 0.0
            a.level = 0
        a.ef = a.es + a.duration

    project_duration = max((a.ef for a in acts.values()), default=0.0)

    # Backward pass.
    for aid in reversed(order):
        a = acts[aid]
        if succ[aid]:
            a.lf = min(acts[s].ls for s in succ[aid])
        else:
            a.lf = project_duration
        a.ls = a.lf - a.duration
        a.total_float = a.ls - a.es
        a.critical = abs(a.total_float) < 1e-9

    critical_path = [aid for aid in order if acts[aid].critical]
    levels = {aid: acts[aid].level for aid in acts}
    return CpmResult(acts, order, project_duration, critical_path, levels)
