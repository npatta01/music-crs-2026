from __future__ import annotations

from mcrs.milvus.indexing import BM25_WITH_TAG_LIST_CORPUS_FIELDS


class FakeQuery:
    def __init__(self, hits):
        self.hits = hits
        self.limit_value = None

    def limit(self, value):
        self.limit_value = value
        return self

    def select(self, fields):
        assert fields == ["track_id", "_score"]
        return self

    def to_list(self):
        return self.hits[: self.limit_value]


class FakeVectorQuery:
    def __init__(self, hits):
        self.hits = hits
        self.limit_value = None
        self.selected = None
        self.distance_type_value = None
        self.where_filter = None

    def distance_type(self, value):
        self.distance_type_value = value
        return self

    def where(self, value):
        self.where_filter = value
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def select(self, fields):
        self.selected = fields
        return self

    def to_list(self):
        return self.hits[: self.limit_value]


class FakeTable:
    def __init__(self):
        self.search_calls = []

    def search(self, query, **kwargs):
        self.search_calls.append({"query": query, **kwargs})
        return FakeQuery([
            {"track_id": "track-1", "_score": 2.0},
            {"track_id": "track-2", "_score": 1.0},
        ])


class FakeVectorTable:
    def __init__(self):
        self.search_calls = []
        self.queries = []

    def search(self, query, **kwargs):
        query_builder = FakeVectorQuery([
            {"track_id": "track-v1", "_distance": 0.01},
            {"track_id": "track-v2", "_distance": 0.03},
        ])
        self.search_calls.append({"query": query, "query_builder": query_builder, **kwargs})
        return query_builder


class FakeDb:
    def __init__(self, table):
        self.table = table
        self.open_count = 0

    def open_table(self, table_name):
        assert table_name == "music_track_catalog"
        self.open_count += 1
        return self.table


def _retrieval_config():
    return {
        "db_uri": "/root/models/lancedb",
        "table_name": "music_track_catalog",
        "searches": [
            {
                "name": "bm25_with_tag_list",
                "kind": "fts_compat",
                "corpus_fields": list(BM25_WITH_TAG_LIST_CORPUS_FIELDS),
                "weight": 1.0,
                "topk": 1000,
            }
        ],
        "fusion": {"method": "weighted_rrf"},
        "device": "cpu",
    }


def test_standalone_lance_retriever_opens_table_once(monkeypatch):
    from mcrs.lancedb.retriever import LanceDbRetriever

    table = FakeTable()
    fake_db = FakeDb(table)
    monkeypatch.setattr("mcrs.lancedb.retriever.connect_lancedb", lambda _: fake_db)

    retriever = LanceDbRetriever.from_retrieval_config(_retrieval_config())

    assert retriever.retrieve("dark synthwave", topk=20) == ["track-1", "track-2"]
    assert retriever.retrieve("ambient", topk=20) == ["track-1", "track-2"]
    assert fake_db.open_count == 1
    assert len(table.search_calls) == 2


def test_standalone_lance_retriever_batch_retrieval(monkeypatch):
    from mcrs.lancedb.retriever import LanceDbRetriever

    table = FakeTable()
    fake_db = FakeDb(table)
    monkeypatch.setattr("mcrs.lancedb.retriever.connect_lancedb", lambda _: fake_db)

    retriever = LanceDbRetriever.from_retrieval_config(_retrieval_config())

    assert retriever.retrieve_batch(["one", "two"], topk=2) == [
        ["track-1", "track-2"],
        ["track-1", "track-2"],
    ]


def test_standalone_lance_retriever_dense_vector_searches_embedding_field(monkeypatch):
    from mcrs.lancedb.retriever import LanceDbRetriever

    class FakeEmbedder:
        def embed_batch(self, texts):
            assert texts == ["dreamy synth pads"]
            return [[0.1, 0.2, 0.3]]

    table = FakeVectorTable()
    fake_db = FakeDb(table)
    monkeypatch.setattr("mcrs.lancedb.retriever.connect_lancedb", lambda _: fake_db)

    config = _retrieval_config()
    config["searches"] = [
        {
            "name": "metadata_dense",
            "kind": "dense_vector",
            "vector_field": "metadata_qwen3_embedding_0_6b",
            "distance_type": "cosine",
            "weight": 1.0,
            "topk": 1000,
        }
    ]
    retriever = LanceDbRetriever.from_retrieval_config(config, embedding_client=FakeEmbedder())

    assert retriever.retrieve("dreamy synth pads", topk=2) == ["track-v1", "track-v2"]
    call = table.search_calls[0]
    assert call["query"] == [0.1, 0.2, 0.3]
    assert call["vector_column_name"] == "metadata_qwen3_embedding_0_6b"
    assert call["query_type"] == "vector"
    assert call["query_builder"].distance_type_value == "cosine"
    assert call["query_builder"].where_filter == "has_metadata_qwen3_embedding_0_6b = true"
    assert call["query_builder"].selected == ["track_id", "_distance"]


def test_standalone_lance_retriever_dense_vector_requires_embedding_client(monkeypatch):
    import pytest

    from mcrs.lancedb.retriever import LanceDbRetriever

    table = FakeVectorTable()
    fake_db = FakeDb(table)
    monkeypatch.setattr("mcrs.lancedb.retriever.connect_lancedb", lambda _: fake_db)

    config = _retrieval_config()
    config["searches"] = [
        {
            "name": "metadata_dense",
            "kind": "dense_vector",
            "vector_field": "metadata_qwen3_embedding_0_6b",
            "topk": 1000,
        }
    ]
    retriever = LanceDbRetriever.from_retrieval_config(config)

    with pytest.raises(RuntimeError, match="requires an embedding client"):
        retriever.retrieve("dreamy synth pads", topk=2)


def test_standalone_lance_retriever_rejects_unknown_dense_vector_field(monkeypatch):
    import pytest

    from mcrs.lancedb.retriever import LanceDbRetriever

    table = FakeVectorTable()
    fake_db = FakeDb(table)
    monkeypatch.setattr("mcrs.lancedb.retriever.connect_lancedb", lambda _: fake_db)

    config = _retrieval_config()
    config["searches"] = [
        {
            "name": "unsafe_dense",
            "kind": "dense_vector",
            "vector_field": "metadata_qwen3_embedding_0_6b = true OR true",
            "topk": 1000,
        }
    ]

    with pytest.raises(ValueError, match="Unsupported LanceDB vector field"):
        LanceDbRetriever.from_retrieval_config(config)
