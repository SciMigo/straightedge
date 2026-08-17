"""Hash table visualization template for CS/data structure diagrams."""

from __future__ import annotations

from typing import Any, Dict, List, Sequence

from ..registry import register
from ..renderer import DEFAULT_STYLES, defs, line, rect, style, svg_document, text


STATE_COLORS = {
    "default": "#f8f9fa",
    "current": "#fff3cd",
    "visited": "#d1ecf1",
    "target": "#d4edda",
    "found": "#d4edda",
    "invalid": "#f8d7da",
    "rejected": "#f8d7da",
    "comparison": "#FF9800",
}


def _normalize_bucket_count(value: Any) -> int:
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str) and value.isdigit():
        bucket_count = int(value)
        if bucket_count > 0:
            return bucket_count
    return 8


def _normalize_entries(entries: Any, bucket_count: int) -> List[Dict[str, Any]]:
    if not isinstance(entries, list):
        return []
    normalized: List[Dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        bucket = entry.get("bucket")
        if not isinstance(bucket, int) or not (0 <= bucket < bucket_count):
            continue
        key = entry.get("key")
        value = entry.get("value")
        normalized.append({"bucket": bucket, "key": key, "value": value})
    return normalized


def _normalize_highlight_key(value: Any) -> List[str]:
    if isinstance(value, Sequence) and not isinstance(value, str):
        return [str(item) for item in value]
    if value is None:
        return []
    return [str(value)]


@register("hash_table")
class HashTableTemplate:
    """Render a hash table visualization with chaining buckets."""

    def render(self, params: Dict[str, Any]) -> str:
        bucket_count = _normalize_bucket_count(params.get("buckets"))
        entries = _normalize_entries(params.get("entries", []), bucket_count)
        collision_strategy = params.get("collision_strategy", "chaining")
        caption = params.get("caption")
        show_hash = bool(params.get("show_hash", False))

        highlights = params.get("highlights", {})
        if not isinstance(highlights, dict):
            highlights = {}
        highlight_bucket = highlights.get("bucket")
        if isinstance(highlight_bucket, str) and highlight_bucket.isdigit():
            highlight_bucket = int(highlight_bucket)
        if not isinstance(highlight_bucket, int):
            highlight_bucket = None
        highlight_keys = _normalize_highlight_key(highlights.get("key"))

        bucket_width = int(params.get("bucket_width", 80))
        entry_width = int(params.get("entry_width", 120))
        entry_height = int(params.get("entry_height", 34))
        row_gap = int(params.get("row_gap", 14))
        entry_gap = int(params.get("entry_gap", 26))
        column_gap = int(params.get("column_gap", 30))
        padding_x = 24
        top_margin = 40
        bottom_margin = 20 + (20 if caption else 0)

        entries_by_bucket: Dict[int, List[Dict[str, Any]]] = {idx: [] for idx in range(bucket_count)}
        for entry in entries:
            entries_by_bucket[entry["bucket"]].append(entry)

        max_chain_length = max((len(chain) for chain in entries_by_bucket.values()), default=0)
        if max_chain_length == 0:
            max_chain_length = 1

        svg_width = (
            padding_x * 2
            + bucket_width
            + column_gap
            + max_chain_length * entry_width
            + (max_chain_length - 1) * entry_gap
        )
        svg_height = top_margin + bucket_count * entry_height + (bucket_count - 1) * row_gap + bottom_margin

        elements: List[str] = []
        elements.append(style(DEFAULT_STYLES + self._extra_styles()))
        elements.append(defs(self._arrow_marker()))

        header_y = 24
        elements.append(
            text(
                padding_x + bucket_width / 2,
                header_y,
                "Bucket",
                **{"class": "hash-header", "text_anchor": "middle"},
            )
        )
        elements.append(
            text(
                padding_x + bucket_width + column_gap + entry_width / 2,
                header_y,
                "Entries",
                **{"class": "hash-header", "text_anchor": "middle"},
            )
        )

        start_x = padding_x + bucket_width + column_gap
        for idx in range(bucket_count):
            row_y = top_margin + idx * (entry_height + row_gap)
            bucket_class = "hash-bucket"
            if highlight_bucket == idx:
                bucket_class += " hash-bucket-highlight"

            elements.append(
                rect(
                    padding_x,
                    row_y,
                    bucket_width,
                    entry_height,
                    **{"class": bucket_class},
                )
            )
            elements.append(
                text(
                    padding_x + bucket_width / 2,
                    row_y + entry_height / 2 + 5,
                    str(idx),
                    **{"class": "hash-bucket-label", "text_anchor": "middle"},
                )
            )

            chain = entries_by_bucket.get(idx, [])
            if collision_strategy != "chaining":
                chain = chain[:1]

            if chain:
                for entry_index, entry in enumerate(chain):
                    entry_x = start_x + entry_index * (entry_width + entry_gap)
                    key = entry.get("key", "")
                    value = entry.get("value", "")
                    label = f"{key}:{value}"
                    entry_class = "hash-entry"
                    if str(key) in highlight_keys:
                        entry_class += " hash-entry-highlight"
                    elements.append(
                        rect(
                            entry_x,
                            row_y,
                            entry_width,
                            entry_height,
                            **{"class": entry_class},
                        )
                    )
                    elements.append(
                        text(
                            entry_x + entry_width / 2,
                            row_y + entry_height / 2 + 5,
                            label,
                            **{"class": "hash-entry-label", "text_anchor": "middle"},
                        )
                    )
                    if show_hash:
                        elements.append(
                            text(
                                entry_x + entry_width / 2,
                                row_y - 6,
                                f"h({key})={idx}",
                                **{"class": "hash-hash-label", "text_anchor": "middle"},
                            )
                        )
                    if entry_index < len(chain) - 1:
                        arrow_start = entry_x + entry_width
                        arrow_end = entry_x + entry_width + entry_gap
                        center_y = row_y + entry_height / 2
                        elements.append(
                            line(
                                arrow_start,
                                center_y,
                                arrow_end,
                                center_y,
                                stroke="#333",
                                stroke_width="2",
                                marker_end="url(#hash-arrow)",
                                **{"class": "hash-chain-arrow"},
                            )
                        )
            else:
                elements.append(
                    rect(
                        start_x,
                        row_y,
                        entry_width,
                        entry_height,
                        **{"class": "hash-entry hash-entry-empty"},
                    )
                )
                elements.append(
                    text(
                        start_x + entry_width / 2,
                        row_y + entry_height / 2 + 5,
                        "[ ]",
                        **{"class": "hash-entry-label", "text_anchor": "middle"},
                    )
                )

        if caption:
            elements.append(
                text(
                    svg_width / 2,
                    svg_height - 8,
                    str(caption),
                    **{"class": "hash-caption", "text_anchor": "middle"},
                )
            )

        return svg_document("\n".join(elements), svg_width, svg_height)

    @staticmethod
    def _arrow_marker() -> str:
        return (
            '<marker id="hash-arrow" viewBox="0 0 10 10" refX="10" refY="5" '
            'markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
            '<path d="M 0 0 L 10 5 L 0 10 z" fill="#333" />'
            '</marker>'
        )

    @staticmethod
    def _extra_styles() -> str:
        return """
.hash-header { font-size: 12px; font-family: sans-serif; fill: #333; font-weight: 600; }
.hash-bucket { fill: #f8f9fa; stroke: #343a40; stroke-width: 1.2; }
.hash-bucket-highlight { fill: #fff3cd; }
.hash-bucket-label { font-size: 12px; font-family: sans-serif; fill: #333; }
.hash-entry { fill: #f8f9fa; stroke: #343a40; stroke-width: 1.2; }
.hash-entry-empty { stroke-dasharray: 4 3; fill: #ffffff; }
.hash-entry-highlight { fill: #d4edda; }
.hash-entry-label { font-size: 12px; font-family: sans-serif; fill: #333; }
.hash-chain-arrow { stroke: #333; }
.hash-hash-label { font-size: 10px; font-family: sans-serif; fill: #666; }
.hash-caption { font-size: 12px; font-family: sans-serif; fill: #333; }
"""
