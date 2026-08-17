from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class AnimationSpec:
    language: str
    topic: str
    concept: str
    title_zh: str
    objective_zh: str
    math_objects: list[str] = field(default_factory=list)
    animation_steps: list[str] = field(default_factory=list)
    labels_zh: list[str] = field(default_factory=list)
    narration_zh: list[str] = field(default_factory=list)
    constraints: dict[str, Any] = field(default_factory=dict)
    source_request_zh: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any], source_request_zh: str = "") -> "AnimationSpec":
        return cls(
            language=str(data.get("language") or "zh"),
            topic=str(data.get("topic") or "unknown"),
            concept=str(data.get("concept") or "generated"),
            title_zh=str(data.get("title_zh") or "数学动画"),
            objective_zh=str(data.get("objective_zh") or ""),
            math_objects=_string_list(data.get("math_objects")),
            animation_steps=_string_list(data.get("animation_steps")),
            labels_zh=_string_list(data.get("labels_zh")),
            narration_zh=_string_list(data.get("narration_zh")),
            constraints=dict(data.get("constraints") or {}),
            source_request_zh=str(data.get("source_request_zh") or source_request_zh),
        )


@dataclass(frozen=True)
class ReviewIssue:
    severity: str
    message: str
    suggestion: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReviewIssue":
        return cls(
            severity=str(data.get("severity") or "medium"),
            message=str(data.get("message") or ""),
            suggestion=str(data.get("suggestion") or ""),
        )


@dataclass(frozen=True)
class CodeReview:
    approved: bool
    issues: list[ReviewIssue] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CodeReview":
        issues = [ReviewIssue.from_dict(item) for item in data.get("issues") or [] if isinstance(item, dict)]
        return cls(approved=bool(data.get("approved")), issues=issues)


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]
