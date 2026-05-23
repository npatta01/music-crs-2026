from __future__ import annotations

import pytest


class FakeRetriever:
    def __init__(self):
        self.calls = []

    def retrieve(self, query: str, topk: int):
        self.calls.append(("retrieve", query, topk))
        return [f"{query}-track"]

    def retrieve_batch(self, queries: list[str], topk: int):
        self.calls.append(("retrieve_batch", list(queries), topk))
        return [[f"{query}-track"] for query in queries]


class FakeEmbedder:
    def __init__(self):
        self.calls = []

    def embed_batch(self, texts: list[str]):
        self.calls.append(list(texts))
        return [[float(len(text))] for text in texts]


def test_retrieval_service_delegates_retrieval_and_embedding():
    from mcrs.retrieval_services.service import RetrievalService

    retriever = FakeRetriever()
    embedder = FakeEmbedder()
    service = RetrievalService(retriever=retriever, embedding_client=embedder)

    assert service.retrieve("dark synthwave", topk=2) == ["dark synthwave-track"]
    assert service.retrieve_batch(["dark", "ambient"], topk=3) == [
        ["dark-track"],
        ["ambient-track"],
    ]
    assert service.embed_batch(["a", "abcd"]) == [[1.0], [4.0]]
    assert retriever.calls == [
        ("retrieve", "dark synthwave", 2),
        ("retrieve_batch", ["dark", "ambient"], 3),
    ]
    assert embedder.calls == [["a", "abcd"]]


def test_retrieval_service_requires_embedder_for_embedding_calls():
    from mcrs.retrieval_services.service import RetrievalService

    service = RetrievalService(retriever=FakeRetriever())

    with pytest.raises(RuntimeError, match="No embedding client configured"):
        service.embed_batch(["a"])
