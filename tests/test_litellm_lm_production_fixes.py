from __future__ import annotations

import sys
from types import SimpleNamespace


def test_build_messages_normalizes_music_role():
    from mcrs.lm_modules.litellm_chat import _build_messages
    history = [
        {"role": "user", "content": "hi"},
        {"role": "music", "content": "title: X | artist: Y"},
        {"role": "assistant", "content": "here you go"},
    ]
    msgs = _build_messages("SYS", history, {"title": "Z"})
    roles = [m["role"] for m in msgs]
    assert "music" not in roles
    assert all(r in {"system", "user", "assistant"} for r in roles)
    # the music turn's content is preserved, just re-roled to assistant
    assert any(m["content"].startswith("title: X") and m["role"] == "assistant" for m in msgs)


def test_batch_response_generation_uses_self_max_tokens_by_default(monkeypatch):
    sent = []

    def fake_batch_completion(**kwargs):
        sent.append(kwargs)
        return [SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))])]

    monkeypatch.setitem(sys.modules, "litellm",
                        SimpleNamespace(batch_completion=fake_batch_completion))
    from mcrs.lm_modules.litellm_chat import LITELLM_LM
    lm = LITELLM_LM(model_name="openrouter/x/y", api_key="k", max_tokens=222)
    out = lm.batch_response_generation(["SYS"], [[{"role": "user", "content": "hi"}]], [{"t": 1}])
    assert out == ["ok"]
    # default (no cap passed) must fall back to self.max_tokens, NOT 64
    assert sent[0]["max_tokens"] == 222


def test_batch_response_generation_retries_per_item_failure(monkeypatch):
    # litellm.batch_completion puts a bare exception object in the results
    # list on a per-item failure instead of raising (observed empirically:
    # one blank response out of 80 real cache-backed Blind-B sessions, with
    # an identical rerun recovering the correct cached content). A single
    # retry via plain litellm.completion should recover it.
    def fake_batch_completion(**kwargs):
        return [
            SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="fine"))]),
            RuntimeError("transient cache read glitch"),
        ]

    def fake_completion(**kwargs):
        assert kwargs["messages"][-1]["content"].startswith("Recommend the following track")
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="recovered"))])

    monkeypatch.setitem(
        sys.modules, "litellm",
        SimpleNamespace(batch_completion=fake_batch_completion, completion=fake_completion),
    )
    from mcrs.lm_modules.litellm_chat import LITELLM_LM
    lm = LITELLM_LM(model_name="openrouter/x/y", api_key="k")
    out = lm.batch_response_generation(
        ["SYS", "SYS"],
        [[{"role": "user", "content": "hi"}], [{"role": "user", "content": "hi"}]],
        [{"t": 1}, {"t": 2}],
    )
    assert out == ["fine", "recovered"]


def test_batch_response_generation_blank_only_if_retry_also_fails(monkeypatch):
    def fake_batch_completion(**kwargs):
        return [RuntimeError("first failure")]

    def fake_completion(**kwargs):
        raise RuntimeError("retry also fails")

    monkeypatch.setitem(
        sys.modules, "litellm",
        SimpleNamespace(batch_completion=fake_batch_completion, completion=fake_completion),
    )
    from mcrs.lm_modules.litellm_chat import LITELLM_LM
    lm = LITELLM_LM(model_name="openrouter/x/y", api_key="k")
    out = lm.batch_response_generation(["SYS"], [[{"role": "user", "content": "hi"}]], [{"t": 1}])
    assert out == [""]
