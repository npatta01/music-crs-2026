from __future__ import annotations

import sys
from types import SimpleNamespace


def test_litellm_embedding_client_batches_requests(monkeypatch):
    calls = []

    def fake_embedding(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            data=[
                {"embedding": [float(index), float(index + 10)]}
                for index, _ in enumerate(kwargs["input"])
            ]
        )

    monkeypatch.setitem(sys.modules, "litellm", SimpleNamespace(embedding=fake_embedding))

    from mcrs.embeddings.litellm_client import LiteLLMEmbeddingClient

    client = LiteLLMEmbeddingClient(
        model_name="huggingface/together/intfloat/e5-base-v2",
        api_base="https://router.huggingface.co/v1",
        api_key="hf-test",
        batch_size=2,
        dimensions=128,
        cache={"ttl": 3600},
    )

    vectors = client.embed_batch(["first", "second", "third"])

    assert vectors == [[0.0, 10.0], [1.0, 11.0], [0.0, 10.0]]
    assert calls == [
        {
            "model": "huggingface/together/intfloat/e5-base-v2",
            "input": ["first", "second"],
            "api_base": "https://router.huggingface.co/v1",
            "api_key": "hf-test",
            "dimensions": 128,
            "cache": {"ttl": 3600},
        },
        {
            "model": "huggingface/together/intfloat/e5-base-v2",
            "input": ["third"],
            "api_base": "https://router.huggingface.co/v1",
            "api_key": "hf-test",
            "dimensions": 128,
            "cache": {"ttl": 3600},
        },
    ]


def test_litellm_embedding_client_can_embed_single_text_as_string(monkeypatch):
    calls = []

    def fake_embedding(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(data=[{"embedding": [1.0, 2.0]}])

    monkeypatch.setitem(sys.modules, "litellm", SimpleNamespace(embedding=fake_embedding))

    from mcrs.embeddings.litellm_client import LiteLLMEmbeddingClient

    client = LiteLLMEmbeddingClient(
        model_name="openrouter/openai/text-embedding-3-small",
        api_key="or-test",
        cache={"ttl": 3600},
    )

    assert client.embed_one("solo query") == [1.0, 2.0]
    assert calls == [
        {
            "model": "openrouter/openai/text-embedding-3-small",
            "input": ["solo query"],
            "api_key": "or-test",
            "cache": {"ttl": 3600},
        }
    ]


def test_litellm_embedding_client_builds_public_request_kwargs():
    from mcrs.embeddings.litellm_client import LiteLLMEmbeddingClient

    client = LiteLLMEmbeddingClient(
        model_name="openrouter/openai/text-embedding-3-small",
        api_key="or-test",
        cache={"ttl": 3600},
    )

    assert client.build_request_kwargs(["query"]) == {
        "model": "openrouter/openai/text-embedding-3-small",
        "input": ["query"],
        "api_key": "or-test",
        "cache": {"ttl": 3600},
    }


def test_litellm_embedding_client_rejects_empty_batch_size():
    import pytest

    from mcrs.embeddings.litellm_client import LiteLLMEmbeddingClient

    with pytest.raises(ValueError, match="batch_size must be positive"):
        LiteLLMEmbeddingClient(model_name="openai/text-embedding-3-small", batch_size=0)
