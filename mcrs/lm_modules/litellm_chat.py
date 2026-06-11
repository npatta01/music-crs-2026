"""LiteLLM-backed chat LM for response generation."""

import os
from typing import Any

_VALID_ROLES = {"system", "user", "assistant"}


def _normalize_role(role: str) -> str:
    """Map non-standard roles (e.g. 'music' from chat_history_parser) to 'assistant'
    so OpenAI-style chat APIs don't 422 on an unknown role."""
    return role if role in _VALID_ROLES else "assistant"


def _format_recommend_item(recommend_item: Any) -> str:
    if isinstance(recommend_item, dict):
        return ", ".join(f"{k}: {v}" for k, v in recommend_item.items() if v is not None)
    return str(recommend_item)


def _build_messages(sys_prompt: str, chat_history: list, recommend_item: Any) -> list[dict]:
    item_text = _format_recommend_item(recommend_item)
    messages = [{"role": "system", "content": sys_prompt}]
    messages.extend(
        {"role": _normalize_role(m["role"]), "content": m["content"]}
        for m in chat_history
    )
    messages.append(
        {
            "role": "user",
            "content": (
                "Recommend the following track and write a natural assistant response "
                f"that introduces it:\n{item_text}"
            ),
        }
    )
    return messages


class LITELLM_LM:
    def __init__(
        self,
        model_name: str,
        api_base: str | None = None,
        api_key: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 512,
        completion_kwargs: dict | None = None,
        **_unused,
    ):
        self.model_name = model_name
        # Only use a proxy base when explicitly configured (arg or env).
        # No hardcoded localhost fallback — lets direct openrouter/... calls
        # authenticate via OPENROUTER_API_KEY (issue #96 §4).
        self.api_base = api_base or os.environ.get("LITELLM_PROXY_BASE")
        self.api_key = api_key or os.environ.get("LITELLM_PROXY_KEY")
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.completion_kwargs = dict(completion_kwargs or {})

    def _completion_kwargs(self, max_new_tokens: int | None) -> dict:
        kwargs = {
            "model": self.model_name,
            "temperature": self.temperature,
            "max_tokens": int(max_new_tokens) if max_new_tokens is not None else self.max_tokens,
        }
        if self.api_base:
            kwargs["api_base"] = self.api_base
        if self.api_key:
            kwargs["api_key"] = self.api_key
        # User-supplied params (reasoning_effort, extra_body, top_p, ...) win,
        # but cannot clobber model/messages (messages set at call time).
        kwargs.update(self.completion_kwargs)
        # Strip protected keys that must not be overridden
        kwargs.pop("messages", None)
        kwargs.pop("model", None)
        # Restore model_name to prevent silent misrouting
        kwargs["model"] = self.model_name
        return kwargs

    def response_generation(
        self,
        sys_prompt: str,
        chat_history: list,
        recommend_item: Any,
        max_new_tokens: int | None = None,
        response_format=None,
    ) -> str:
        import litellm

        messages = _build_messages(sys_prompt, chat_history, recommend_item)
        kwargs = self._completion_kwargs(max_new_tokens)
        response = litellm.completion(messages=messages, **kwargs)
        return response.choices[0].message.content or ""

    def batch_response_generation(
        self,
        sys_prompts: list[str],
        chat_histories: list[list],
        recommend_items: list,
        max_new_tokens: int | None = None,
    ) -> list[str]:
        import litellm

        batch_messages = [
            _build_messages(sys_prompt, chat_history, recommend_item)
            for sys_prompt, chat_history, recommend_item in zip(
                sys_prompts, chat_histories, recommend_items
            )
        ]
        kwargs = self._completion_kwargs(max_new_tokens)
        responses = litellm.batch_completion(messages=batch_messages, **kwargs)
        outputs: list[str] = []
        for response in responses:
            try:
                outputs.append(response.choices[0].message.content or "")
            except Exception:
                outputs.append("")
        return outputs
