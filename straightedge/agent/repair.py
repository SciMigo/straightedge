from __future__ import annotations

from straightedge.aspect import LANDSCAPE
from straightedge.labels import DEFAULT_LANGUAGE, translate

from .llm import OpenAICompatibleClient
from .prompts import REPAIR_SYSTEM, repair_user_prompt
from .schemas import AnimationSpec
from .writer import _strip_code_fence


def repair_code_with_llm(
    client: OpenAICompatibleClient,
    spec: AnimationSpec,
    code: str,
    failure: str,
    language: str = DEFAULT_LANGUAGE,
    *,
    aspect: str = LANDSCAPE,
) -> str:
    """A corrected scene, with its labels still in the requested language.

    The repair prompt hands the model the spec, whose labels are Chinese, so a
    rewrite that touches a label tends to restore the Chinese the writer had
    already translated away. Re-applying the catalog costs nothing and stops a
    render from changing language partway through a repair loop.
    """
    return translate(
        _strip_code_fence(
            client.chat(
                [
                    {"role": "system", "content": REPAIR_SYSTEM},
                    {
                        "role": "user",
                        "content": repair_user_prompt(
                            spec, code, failure, aspect, language),
                    },
                ],
                temperature=0.1,
            )
        ),
        language,
    )
