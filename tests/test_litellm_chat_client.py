from __future__ import annotations

import sys
from types import SimpleNamespace


def test_litellm_chat_client_calls_completion(monkeypatch):
    calls = []

    def fake_completion(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="cached gemma response")
                )
            ],
            id="chat-1",
        )

    monkeypatch.setitem(sys.modules, "litellm", SimpleNamespace(completion=fake_completion))

    from mcrs.lm_modules.litellm_client import LiteLLMChatClient

    client = LiteLLMChatClient(
        model_name="openrouter/google/gemma-3-4b-it",
        api_key="or-test",
        temperature=0.0,
        max_tokens=32,
    )

    output = client.chat(
        messages=[{"role": "user", "content": "Say hello."}],
        cache={"ttl": 3600},
    )

    assert output == "cached gemma response"
    assert calls == [
        {
            "model": "openrouter/google/gemma-3-4b-it",
            "messages": [{"role": "user", "content": "Say hello."}],
            "temperature": 0.0,
            "max_tokens": 32,
            "api_key": "or-test",
            "cache": {"ttl": 3600},
        }
    ]


def test_litellm_chat_client_builds_public_request_kwargs():
    from mcrs.lm_modules.litellm_client import LiteLLMChatClient

    client = LiteLLMChatClient(
        model_name="openrouter/google/gemma-3-4b-it",
        api_key="or-test",
        temperature=0.0,
        max_tokens=32,
    )

    assert client.build_request_kwargs(
        messages=[{"role": "user", "content": "Say hello."}],
        cache={"ttl": 3600},
    ) == {
        "model": "openrouter/google/gemma-3-4b-it",
        "messages": [{"role": "user", "content": "Say hello."}],
        "temperature": 0.0,
        "max_tokens": 32,
        "api_key": "or-test",
        "cache": {"ttl": 3600},
    }


def test_litellm_chat_client_rejects_empty_model_name():
    import pytest

    from mcrs.lm_modules.litellm_client import LiteLLMChatClient

    with pytest.raises(ValueError, match="model_name must be a non-empty string"):
        LiteLLMChatClient(model_name=" ")
