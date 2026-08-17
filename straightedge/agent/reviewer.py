from __future__ import annotations

import json

from straightedge.aspect import LANDSCAPE
from straightedge.labels import DEFAULT_LANGUAGE

from .llm import OpenAICompatibleClient
from .prompts import REVIEWER_SYSTEM, reviewer_user_prompt
from .schemas import AnimationSpec, CodeReview


def review_code_with_llm(
    client: OpenAICompatibleClient,
    spec: AnimationSpec,
    code: str,
    *,
    aspect: str = LANDSCAPE,
    language: str = DEFAULT_LANGUAGE,
) -> CodeReview:
    content = client.chat(
        [
            {"role": "system", "content": REVIEWER_SYSTEM},
            {
                "role": "user",
                "content": reviewer_user_prompt(spec, code, aspect, language),
            },
        ],
        temperature=0.0,
        response_format={"type": "json_object"},
    )
    return CodeReview.from_dict(json.loads(content))


def review_to_text(review: CodeReview) -> str:
    if review.approved:
        return "Approved."
    if not review.issues:
        return "Reviewer did not approve the code."
    return "\n".join(
        f"- {issue.severity}: {issue.message} {issue.suggestion}".strip()
        for issue in review.issues
    )
