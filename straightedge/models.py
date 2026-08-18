from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


class Topic:
    """Canonical topic identifiers — the single source of truth for routing.

    Plain string constants (not an Enum) so the values stay JSON-friendly and
    compare/hash as ordinary strings on Python 3.10+.

    Names only. What a topic *does* — its keywords, its tie-break priority, its
    concepts, its plan and scene builders — is declared with
    :func:`straightedge.topics.topic` in the module that owns the topic, and
    :func:`straightedge.topics.verify` raises at import if a name here has no
    such declaration. Use :func:`straightedge.topics.all_ids` for the set of
    topics that actually exist; a constant here is a spelling, not a promise.
    """

    GEOMETRY = "geometry"
    TRIG = "trig"
    CONIC = "conic"
    THREE_D = "3d"
    FUNCTION = "function"
    CALCULUS = "calculus"
    LINEAR_ALGEBRA = "linear_algebra"


@dataclass(frozen=True)
class AnimationPlan:
    topic: str
    title_zh: str
    objective_zh: str
    english_prompt: str
    concept: str | None = None
    elements: list[str] = field(default_factory=list)
    narration_zh: list[str] = field(default_factory=list)
    parameters: dict[str, Any] = field(default_factory=dict)

    @property
    def match(self) -> str:
        """Whether the request reached a specific builder or a topic fallback.

        The planner never refuses — an unmatched request routes to the topic's
        generic scene rather than erroring. That is the right behaviour (a video
        beats a traceback), but it means "draw the Pythagorean theorem" quietly
        becomes a stock triangle, and a caller that cannot see the frame has no
        way to know it did not get what it asked for.

        ``"concept"`` means a specific builder matched; ``"topic-fallback"`` means
        it did not, and the result is a generic stand-in for the topic. An agent
        should treat a fallback as "I do not have this" rather than present the
        generic scene as the thing that was requested.
        """
        return "concept" if self.concept else "topic-fallback"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
