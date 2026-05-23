from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class LiteLLMChatClient:
    """Standalone LiteLLM chat client with no Modal dependency."""

    model_name: str
    api_base: str | None = None
    api_key: str | None = None
    temperature: float = 0.0
    max_tokens: int = 128
    extra_params: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.model_name.strip():
            raise ValueError("model_name must be a non-empty string")
        self.max_tokens = int(self.max_tokens)
        if self.max_tokens <= 0:
            raise ValueError("max_tokens must be positive")

    def build_request_kwargs(self, messages: list[dict[str, str]], cache: dict[str, Any] | None) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "temperature": float(self.temperature),
            "max_tokens": self.max_tokens,
        }
        if self.api_base:
            kwargs["api_base"] = self.api_base
        if self.api_key:
            kwargs["api_key"] = self.api_key
        if cache is not None:
            kwargs["cache"] = cache
        kwargs.update(self.extra_params)
        return kwargs

    def _kwargs(self, messages: list[dict[str, str]], cache: dict[str, Any] | None) -> dict[str, Any]:
        return self.build_request_kwargs(messages=messages, cache=cache)

    def chat(self, messages: list[dict[str, str]], cache: dict[str, Any] | None = None) -> str:
        import litellm

        response = litellm.completion(**self.build_request_kwargs(messages=messages, cache=cache))
        return response.choices[0].message.content or ""
