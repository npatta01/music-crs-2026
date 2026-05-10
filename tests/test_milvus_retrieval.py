import pytest

from mcrs.milvus.indexing import BM25_COMPAT_CORPUS_FIELDS, BM25_WITH_TAG_LIST_CORPUS_FIELDS


def _dense_encoder_config():
    return {
        "model_name": "Qwen/Qwen3-Embedding-0.6B",
        "pooling": "last_token",
        "query_template": (
            "Instruct: Given a music recommendation conversation, retrieve relevant track metadata "
            "passages that match the listener request and prior music preferences.\nQuery:{query}"
        ),
        "max_length": 512,
        "padding_side": "left",
        "torch_dtype": "bfloat16",
    }


def test_milvus_retriever_rejects_empty_searches():
    from mcrs.retrieval_modules.milvus import MILVUS_MODEL

    with pytest.raises(ValueError, match="searches"):
        MILVUS_MODEL(
            dataset_name="tracks",
            split_types=["all_tracks"],
            corpus_types=["track_name"],
            retrieval_config={
                "uri": "http://localhost:19530",
                "db_name": "default",
                "collection_name": "music_track_catalog",
                "searches": [],
                "fusion": {"method": "weighted"},
            },
        )


def test_milvus_retriever_rejects_duplicate_bm25_fields():
    from mcrs.retrieval_modules.milvus import MILVUS_MODEL

    with pytest.raises(ValueError, match="Duplicate BM25 field"):
        MILVUS_MODEL(
            dataset_name="tracks",
            split_types=["all_tracks"],
            corpus_types=["track_name"],
            retrieval_config={
                "uri": "http://localhost:19530",
                "db_name": "default",
                "collection_name": "music_track_catalog",
                "searches": [
                    {
                        "name": "dup_sparse",
                        "kind": "bm25_fields",
                        "fields": [
                            {"name": "track_name", "weight": 0.5},
                            {"name": "track_name", "weight": 0.5},
                        ],
                        "topk": 100,
                    }
                ],
                "fusion": {"method": "weighted"},
            },
        )


def test_milvus_retriever_rejects_dense_search_without_query_encoder():
    from mcrs.retrieval_modules.milvus import MILVUS_MODEL

    with pytest.raises(ValueError, match="query_encoder"):
        MILVUS_MODEL(
            dataset_name="tracks",
            split_types=["all_tracks"],
            corpus_types=["track_name"],
            retrieval_config={
                "uri": "http://localhost:19530",
                "db_name": "default",
                "collection_name": "music_track_catalog",
                "searches": [
                    {
                        "name": "dense_missing_encoder",
                        "kind": "dense",
                        "vector_field": "metadata_qwen3_embedding_0_6b",
                        "topk": 100,
                    }
                ],
                "fusion": {"method": "weighted"},
            },
        )


def test_bm25_compat_search_uses_default_sparse_field(monkeypatch):
    from mcrs.retrieval_modules.milvus import MILVUS_MODEL

    class FakeClient:
        def __init__(self):
            self.search_calls = []

        def search(self, **kwargs):
            self.search_calls.append(kwargs)
            return [[{"track_id": "track-1"}, {"track_id": "track-2"}]]

    fake_client = FakeClient()
    monkeypatch.setattr("mcrs.retrieval_modules.milvus.connect_milvus", lambda **_: fake_client)
    model = MILVUS_MODEL(
        dataset_name="tracks",
        split_types=["all_tracks"],
        corpus_types=["track_name"],
        retrieval_config={
            "uri": "http://localhost:19530",
            "db_name": "default",
            "collection_name": "music_track_catalog",
            "searches": [
                {
                    "name": "benchmark_bm25",
                    "kind": "bm25_compat",
                    "corpus_fields": list(BM25_COMPAT_CORPUS_FIELDS),
                    "weight": 1.0,
                    "topk": 1000,
                }
            ],
            "fusion": {"method": "weighted"},
        },
    )

    assert model.text_to_item_retrieval("dark rock", topk=4) == ["track-1", "track-2"]
    call = fake_client.search_calls[0]
    assert call["anns_field"] == "bm25_compat_sparse"
    assert call["data"] == ["dark rock"]
    assert call["search_params"]["metric_type"] == "BM25"
    assert call["limit"] == 1000


def test_bm25_compat_search_supports_with_tag_list_profile(monkeypatch):
    from mcrs.retrieval_modules.milvus import MILVUS_MODEL

    class FakeClient:
        def __init__(self):
            self.search_calls = []

        def search(self, **kwargs):
            self.search_calls.append(kwargs)
            return [[{"track_id": "track-3"}]]

    fake_client = FakeClient()
    monkeypatch.setattr("mcrs.retrieval_modules.milvus.connect_milvus", lambda **_: fake_client)
    model = MILVUS_MODEL(
        dataset_name="tracks",
        split_types=["all_tracks"],
        corpus_types=["track_name"],
        retrieval_config={
            "uri": "http://localhost:19530",
            "db_name": "default",
            "collection_name": "music_track_catalog",
            "searches": [
                {
                    "name": "bm25_with_tag_list",
                    "kind": "bm25_compat",
                    "corpus_fields": list(BM25_WITH_TAG_LIST_CORPUS_FIELDS),
                    "weight": 1.0,
                    "topk": 1000,
                }
            ],
            "fusion": {"method": "weighted"},
        },
    )

    assert model.text_to_item_retrieval("late-night shoegaze", topk=4) == ["track-3"]
    call = fake_client.search_calls[0]
    assert call["anns_field"] == "bm25_with_tag_list_sparse"
    assert call["data"] == ["late-night shoegaze"]
    assert call["search_params"]["metric_type"] == "BM25"
    assert call["limit"] == 1000


def test_sparse_field_weighted_search_uses_hybrid_search(monkeypatch):
    from mcrs.retrieval_modules.milvus import MILVUS_MODEL

    class FakeClient:
        def __init__(self):
            self.hybrid_calls = []

        def hybrid_search(self, **kwargs):
            self.hybrid_calls.append(kwargs)
            return [[{"track_id": "track-9"}]]

    fake_client = FakeClient()
    monkeypatch.setattr("mcrs.retrieval_modules.milvus.connect_milvus", lambda **_: fake_client)

    model = MILVUS_MODEL(
        dataset_name="tracks",
        split_types=["all_tracks"],
        corpus_types=["track_name"],
        retrieval_config={
            "uri": "http://localhost:19530",
            "db_name": "default",
            "collection_name": "music_track_catalog",
            "searches": [
                {
                    "name": "tag_heavy_sparse",
                    "kind": "bm25_fields",
                    "fields": [
                        {"name": "track_name", "weight": 0.3},
                        {"name": "tag_list", "weight": 0.7},
                    ],
                    "topk": 1000,
                }
            ],
            "fusion": {"method": "weighted"},
        },
    )

    assert model.text_to_item_retrieval("moody synthwave", topk=20) == ["track-9"]
    call = fake_client.hybrid_calls[0]
    assert [req.anns_field for req in call["reqs"]] == ["track_name_sparse", "tag_list_sparse"]
    assert [req.limit for req in call["reqs"]] == [1000, 1000]
    assert call["limit"] == 20
    assert call["ranker"].dict()["params"]["weights"] == [0.3, 0.7]


def test_dense_search_uses_query_encoder_and_presence_filter(monkeypatch):
    from mcrs.retrieval_modules.milvus import MILVUS_MODEL

    class FakeEncoder:
        def encode(self, query):
            assert query == "late night ambient"
            return [0.1, 0.2, 0.3]

    class FakeClient:
        def __init__(self):
            self.search_calls = []

        def search(self, **kwargs):
            self.search_calls.append(kwargs)
            return [[{"track_id": "track-42"}]]

    fake_client = FakeClient()
    monkeypatch.setattr("mcrs.retrieval_modules.milvus.connect_milvus", lambda **_: fake_client)
    monkeypatch.setattr(
        "mcrs.retrieval_modules.milvus._DenseQueryEncoder.from_config",
        lambda *args, **kwargs: FakeEncoder(),
    )

    model = MILVUS_MODEL(
        dataset_name="tracks",
        split_types=["all_tracks"],
        corpus_types=["track_name"],
        retrieval_config={
            "uri": "http://localhost:19530",
            "db_name": "default",
            "collection_name": "music_track_catalog",
            "searches": [
                {
                    "name": "metadata_dense",
                    "kind": "dense",
                    "vector_field": "metadata_qwen3_embedding_0_6b",
                    "weight": 1.0,
                    "topk": 1000,
                    "query_encoder": _dense_encoder_config(),
                }
            ],
            "fusion": {"method": "weighted"},
        },
    )

    assert model.text_to_item_retrieval("late night ambient", topk=20) == ["track-42"]
    call = fake_client.search_calls[0]
    assert call["anns_field"] == "metadata_qwen3_embedding_0_6b"
    assert call["data"] == [[0.1, 0.2, 0.3]]
    assert call["filter"] == "has_metadata_qwen3_embedding_0_6b == true"
    assert call["search_params"]["metric_type"] == "COSINE"


def test_multi_search_hybrid_multiplies_search_and_field_weights(monkeypatch):
    from mcrs.retrieval_modules.milvus import MILVUS_MODEL

    class FakeEncoder:
        def encode(self, query):
            return [0.4, 0.5]

    class FakeClient:
        def __init__(self):
            self.hybrid_calls = []

        def hybrid_search(self, **kwargs):
            self.hybrid_calls.append(kwargs)
            return [[{"track_id": "track-77"}]]

    fake_client = FakeClient()
    monkeypatch.setattr("mcrs.retrieval_modules.milvus.connect_milvus", lambda **_: fake_client)
    monkeypatch.setattr(
        "mcrs.retrieval_modules.milvus._DenseQueryEncoder.from_config",
        lambda *args, **kwargs: FakeEncoder(),
    )

    model = MILVUS_MODEL(
        dataset_name="tracks",
        split_types=["all_tracks"],
        corpus_types=["track_name"],
        retrieval_config={
            "uri": "http://localhost:19530",
            "db_name": "default",
            "collection_name": "music_track_catalog",
            "searches": [
                {
                    "name": "sparse_tags",
                    "kind": "bm25_fields",
                    "weight": 0.6,
                    "fields": [
                        {"name": "track_name", "weight": 0.25},
                        {"name": "tag_list", "weight": 0.75},
                    ],
                    "topk": 1000,
                },
                {
                    "name": "dense_metadata",
                    "kind": "dense",
                    "vector_field": "metadata_qwen3_embedding_0_6b",
                    "weight": 0.4,
                    "topk": 1000,
                    "query_encoder": _dense_encoder_config(),
                },
            ],
            "fusion": {"method": "weighted"},
        },
    )

    assert model.text_to_item_retrieval("dream pop", topk=20) == ["track-77"]
    call = fake_client.hybrid_calls[0]
    assert [req.anns_field for req in call["reqs"]] == [
        "track_name_sparse",
        "tag_list_sparse",
        "metadata_qwen3_embedding_0_6b",
    ]
    assert call["ranker"].dict()["params"]["weights"] == [0.15, 0.45, 0.4]
