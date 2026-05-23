from __future__ import annotations


def test_modal_lancedb_retrieval_module_delegates_to_client(monkeypatch):
    calls = {}

    class FakeClient:
        def __init__(self, app_name: str, class_name: str):
            calls["init"] = (app_name, class_name)

        def query(self, query: str, topk: int, retrieval_config=None):
            calls["query"] = (query, topk, retrieval_config)
            return ["track-1"]

        def query_batch(self, queries: list[str], topk: int, retrieval_config=None):
            calls["query_batch"] = (queries, topk, retrieval_config)
            return [["track-1"], ["track-2"]]

    monkeypatch.setattr("mcrs.retrieval_modules.modal_lancedb.LanceDbModalClient", FakeClient)

    from mcrs.retrieval_modules.modal_lancedb import MODAL_LANCEDB_MODEL

    model = MODAL_LANCEDB_MODEL(
        dataset_name="unused",
        split_types=["all_tracks"],
        corpus_types=[],
        retrieval_config={
            "app_name": "music-crs",
            "class_name": "ModalRetrievalService",
            "searches": [
                {
                    "name": "metadata_dense",
                    "kind": "dense_vector",
                    "vector_field": "metadata_qwen3_embedding_0_6b",
                    "topk": 1000,
                }
            ],
        },
    )

    assert model.text_to_item_retrieval("dark", topk=20) == ["track-1"]
    assert model.batch_text_to_item_retrieval(["dark", "ambient"], topk=10) == [
        ["track-1"],
        ["track-2"],
    ]
    assert calls["init"] == ("music-crs", "ModalRetrievalService")
    assert calls["query"] == (
        "dark",
        20,
        {
            "searches": [
                {
                    "name": "metadata_dense",
                    "kind": "dense_vector",
                    "vector_field": "metadata_qwen3_embedding_0_6b",
                    "topk": 1000,
                }
            ]
        },
    )
    assert calls["query_batch"] == (
        ["dark", "ambient"],
        10,
        {
            "searches": [
                {
                    "name": "metadata_dense",
                    "kind": "dense_vector",
                    "vector_field": "metadata_qwen3_embedding_0_6b",
                    "topk": 1000,
                }
            ]
        },
    )
