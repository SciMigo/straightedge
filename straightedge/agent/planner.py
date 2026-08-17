from __future__ import annotations

import json

from .llm import OpenAICompatibleClient
from .prompts import PLANNER_SYSTEM, PLANNER_USER_TEMPLATE
from .schemas import AnimationSpec


def plan_with_llm(client: OpenAICompatibleClient, request_zh: str) -> AnimationSpec:
    content = client.chat(
        [
            {"role": "system", "content": PLANNER_SYSTEM},
            {"role": "user", "content": PLANNER_USER_TEMPLATE.format(request=request_zh)},
        ],
        temperature=0.1,
        response_format={"type": "json_object"},
    )
    data = json.loads(content)
    return AnimationSpec.from_dict(data, source_request_zh=request_zh)
