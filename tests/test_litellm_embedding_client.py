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


def test_litellm_embedding_client_applies_query_instruct_to_cached_request(monkeypatch):
    calls = []

    def fake_embedding(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(data=[{"embedding": [3.0, 4.0]}])

    monkeypatch.setitem(sys.modules, "litellm", SimpleNamespace(embedding=fake_embedding))

    from mcrs.embeddings.litellm_client import LiteLLMEmbeddingClient

    instruct = (
        "Instruct: Given a music recommendation conversation, retrieve relevant "
        "track metadata passages.\nQuery: "
    )
    client = LiteLLMEmbeddingClient(
        model_name="openai/Qwen/Qwen3-Embedding-4B",
        api_base="https://vllm.example/v1",
        api_key="vllm-key",
        encoding_format="float",
        cache={"ttl": 86400},
        query_instruct=instruct,
        extra_params={"timeout": 600},
    )

    assert client.embed_one("conversation state text") == [3.0, 4.0]
    assert calls == [
        {
            "model": "openai/Qwen/Qwen3-Embedding-4B",
            "input": [instruct + "conversation state text"],
            "api_base": "https://vllm.example/v1",
            "api_key": "vllm-key",
            "encoding_format": "float",
            "cache": {"ttl": 86400},
            "timeout": 600,
        }
    ]


def test_litellm_embedding_cache_wrap_persists_across_clients(tmp_path, monkeypatch):
    calls = []

    def fake_embedding(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            data=[{"embedding": [float(len(text)), 7.0]} for text in kwargs["input"]]
        )

    monkeypatch.setitem(sys.modules, "litellm", SimpleNamespace(embedding=fake_embedding))

    from mcrs.embeddings.litellm_client import LiteLLMEmbeddingClient, cache_wrap

    first = cache_wrap(
        LiteLLMEmbeddingClient(
            model_name="openai/Qwen/Qwen3-Embedding-8B",
            api_base="https://fake/v1",
            api_key="secret",
            encoding_format="float",
            query_instruct="Query: ",
        ),
        cache_dir=str(tmp_path),
        enabled=True,
    )
    assert first.embed_batch(["same text", "same text"]) == [[16.0, 7.0], [16.0, 7.0]]
    assert [call["input"] for call in calls] == [["Query: same text"]]

    second = cache_wrap(
        LiteLLMEmbeddingClient(
            model_name="openai/Qwen/Qwen3-Embedding-8B",
            api_base="https://fake/v1",
            api_key="rotated-secret",
            encoding_format="float",
            query_instruct="Query: ",
        ),
        cache_dir=str(tmp_path),
        enabled=True,
    )
    assert second.embed_batch(["same text"]) == [[16.0, 7.0]]
    assert [call["input"] for call in calls] == [["Query: same text"]]


def test_litellm_embedding_client_rejects_empty_batch_size():
    import pytest

    from mcrs.embeddings.litellm_client import LiteLLMEmbeddingClient

    with pytest.raises(ValueError, match="batch_size must be positive"):
        LiteLLMEmbeddingClient(model_name="openai/text-embedding-3-small", batch_size=0)
