from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LLMConfig:
    model: str
    api_key: str
    base_url: str = "https://api.openai.com/v1"
    # Reasoning models and compatible gateways can take well over a minute to
    # produce their first token. Callers can still lower this per environment.
    timeout: float = 300.0


class LLMError(RuntimeError):
    pass


class OpenAICompatibleClient:
    """Tiny standard-library client for OpenAI-compatible chat completions."""

    def __init__(self, config: LLMConfig):
        self.config = config

    @classmethod
    def from_env(cls, model: str | None = None) -> "OpenAICompatibleClient":
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise LLMError("OPENAI_API_KEY is not set; agent mode needs an LLM API key.")
        return cls(
            LLMConfig(
                model=model or os.environ.get("STRAIGHTEDGE_AGENT_MODEL") or "gpt-4.1-mini",
                api_key=api_key,
                base_url=os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1",
                timeout=float(os.environ.get("STRAIGHTEDGE_LLM_TIMEOUT") or "300"),
            )
        )

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
        response_format: dict[str, str] | None = None,
    ) -> str:
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "temperature": temperature,
        }
        if response_format is not None:
            payload["response_format"] = response_format

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.config.base_url.rstrip("/") + "/chat/completions",
            data=data,
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise LLMError(f"LLM API HTTP {exc.code}: {detail}") from exc
        except OSError as exc:
            raise LLMError(f"LLM API request failed: {exc}") from exc

        try:
            return str(body["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"Unexpected LLM API response: {body!r}") from exc
