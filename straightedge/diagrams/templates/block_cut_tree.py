"""Block-cut forest derived from the shared low-link analysis."""

from __future__ import annotations

from typing import Any, Dict, List

from ...graphs import GraphError, coerce_graph, connectivity_analysis
from ...qc import Finding
from ..registry import DIAGRAM_REGISTRY, register


@register("block_cut_tree")
class BlockCutTreeTemplate:
    """Compute and draw blocks joined through articulation vertices."""

    checks = ["undirected simple graph", "Tarjan low-link values", "block membership",
              "articulation incidence"]

    def refusal_findings(self, params: Dict[str, Any]) -> List[Finding]:
        try: connectivity_analysis(coerce_graph(params))
        except GraphError as exc:
            return [Finding("block_cut_refused", "error", str(exc))]
        return []

    def render(self, params: Dict[str, Any]) -> str:
        params.get("nodes", []); params.get("edges", []); params.get("directed", False)
        title = params.get("title", "Block-cut forest"); caption = params.get("caption")
        width = int(params.get("width", 720)); height = int(params.get("height", 420))
        if self.refusal_findings(params): return ""
        analysis = connectivity_analysis(coerce_graph(params))
        blocks = list(analysis.blocks); cuts = list(analysis.articulations)
        nodes = []
        membership = {}
        for i, block in enumerate(blocks):
            y = (i + 1) / (len(blocks) + 1)
            block_id = f"B{i + 1}"
            nodes.append({"id": block_id, "label": block_id, "x": 0.25, "y": y})
            membership[block_id] = "{" + ",".join(block) + "}"
        for i, cut in enumerate(cuts):
            y = (i + 1) / (len(cuts) + 1)
            nodes.append({"id": f"A:{cut}", "label": cut, "x": 0.75, "y": y})
        edges = [{"from": f"B{i + 1}", "to": f"A:{cut}"}
                 for i, block in enumerate(blocks) for cut in cuts if cut in block]
        return DIAGRAM_REGISTRY["graph"].render({
            "nodes": nodes, "edges": edges, "layout": "custom", "width": width, "height": height,
            "highlights": {"nodes": {f"A:{cut}": "articulation" for cut in cuts}},
            "distance_labels": membership,
            "caption": str(caption) if caption is not None else
                       f"{title} · {len(blocks)} block(s); {len(cuts)} articulation vertex/vertices",
        })
