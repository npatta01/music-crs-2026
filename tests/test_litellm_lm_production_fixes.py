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
