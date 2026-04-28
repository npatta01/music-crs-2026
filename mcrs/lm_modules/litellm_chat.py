"""LiteLLM-backed chat LM for response generation."""

import os
from typing import Any


def _format_recommend_item(recommend_item: Any) -> str:
    if isinstance(recommend_item, dict):
        return ", ".join(f"{k}: {v}" for k, v in recommend_item.items() if v is not None)
    return str(recommend_item)


def _build_messages(sys_prompt: str, chat_history: list, recommend_item: Any) -> list[dict]:
    item_text = _format_recommend_item(recommend_item)
    messages = [{"role": "system", "content": sys_prompt}]
    messages.extend(chat_history)
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
        **_unused,
    ):
        self.model_name = model_name
        self.api_base = api_base or os.environ.get("LITELLM_PROXY_BASE", "http://0.0.0.0:4000")
        self.api_key = api_key or os.environ.get("LITELLM_PROXY_KEY", "sk-anything")
        self.temperature = temperature
        self.max_tokens = max_tokens

    def _completion_kwargs(self, max_new_tokens: int | None) -> dict:
        return {
            "model": self.model_name,
            "api_base": self.api_base,
            "api_key": self.api_key,
            "temperature": self.temperature,
            "max_tokens": int(max_new_tokens) if max_new_tokens is not None else self.max_tokens,
        }

    def response_generation(
        self,
        sys_prompt: str,
        chat_history: list,
        recommend_item: Any,
        max_new_tokens: int = 512,
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
        max_new_tokens: int = 64,
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
