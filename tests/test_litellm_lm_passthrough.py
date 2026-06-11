from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest


def _install_fake_litellm(monkeypatch):
    calls = []

    def fake_completion(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
            id="c1",
        )

    monkeypatch.setitem(sys.modules, "litellm", SimpleNamespace(completion=fake_completion))
    return calls


def test_completion_kwargs_merge_through(monkeypatch):
    calls = _install_fake_litellm(monkeypatch)
    from mcrs.lm_modules.litellm_chat import LITELLM_LM

    lm = LITELLM_LM(
        model_name="openrouter/qwen/qwen3-8b",
        api_key="or-test",
        temperature=0.0,
        max_tokens=64,
        completion_kwargs={"extra_body": {"reasoning": {"enabled": False}}},
    )
    out = lm.response_generation("sys", [{"role": "user", "content": "hi"}], {"title": "X"})
    assert out == "ok"
    sent = calls[0]
    assert sent["model"] == "openrouter/qwen/qwen3-8b"
    assert sent["extra_body"] == {"reasoning": {"enabled": False}}
    assert sent["max_tokens"] == 64


def test_api_base_omitted_when_unset(monkeypatch):
    monkeypatch.delenv("LITELLM_PROXY_BASE", raising=False)
    calls = _install_fake_litellm(monkeypatch)
    from mcrs.lm_modules.litellm_chat import LITELLM_LM

    lm = LITELLM_LM(model_name="openrouter/google/gemma-3-4b-it", api_key="or-test")
    lm.response_generation("sys", [], {"title": "X"})
    assert "api_base" not in calls[0]


def test_api_base_forwarded_when_proxy_env_set(monkeypatch):
    monkeypatch.setenv("LITELLM_PROXY_BASE", "http://localhost:4000")
    calls = _install_fake_litellm(monkeypatch)
    from mcrs.lm_modules.litellm_chat import LITELLM_LM

    lm = LITELLM_LM(model_name="proxy/model", api_key="k")
    lm.response_generation("sys", [], {"title": "X"})
    assert calls[0]["api_base"] == "http://localhost:4000"
