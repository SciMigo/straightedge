from __future__ import annotations

from straightedge.aspect import LANDSCAPE
from straightedge.labels import DEFAULT_LANGUAGE, translate

from .llm import OpenAICompatibleClient
from .prompts import WRITER_SYSTEM, writer_user_prompt
from .schemas import AnimationSpec


def write_code_with_llm(
    client: OpenAICompatibleClient,
    spec: AnimationSpec,
    *,
    font: str,
    aspect: str = LANDSCAPE,
    language: str = DEFAULT_LANGUAGE,
) -> str:
    """Model-authored scene source for ``spec``.

    ``language`` is asked for in the prompt *and* applied to the result. The
    prompt is what produces good English — a translation catalog cannot invent a
    phrase it has never seen. The pass afterwards is the safety net for the
    labels the model copied verbatim out of the Chinese spec instead of
    translating, which are exactly the ones the catalog does know.
    """
    code = _strip_code_fence(
        client.chat(
            [
                {"role": "system", "content": WRITER_SYSTEM},
                {"role": "user", "content": writer_user_prompt(spec, font, aspect, language)},
            ],
            temperature=0.2,
        )
    )
    return translate(code, language)


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()
