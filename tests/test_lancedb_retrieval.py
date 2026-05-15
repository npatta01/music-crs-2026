import pytest

from mcrs.milvus.indexing import BM25_WITH_TAG_LIST_CORPUS_FIELDS


class FakeQuery:
    def __init__(self, hits):
        self.hits = hits
        self.limit_value = None
        self.selected = None

    def limit(self, value):
        self.limit_value = value
        return self

    def select(self, fields):
        self.selected = fields
        return self

    def to_list(self):
        return self.hits[: self.limit_value]


class FakeTable:
    def __init__(self, hits_by_field, all_track_ids=None):
        self.hits_by_field = hits_by_field
        self.all_track_ids = all_track_ids
        self.search_calls = []

    def search(self, query, **kwargs):
        self.search_calls.append({"query": query, **kwargs})
        field = kwargs.get("fts_columns")
        if field is None and hasattr(query, "queries") and query.queries:
            field = query.queries[0][1].column
        return FakeQuery(self.hits_by_field[field])

    def to_arrow(self):
        if self.all_track_ids is None:
            raise AttributeError("No fake catalog rows configured")

        class FakeArrow:
            def __init__(self, track_ids):
                self.track_ids = track_ids

            def select(self, fields):
                assert fields == ["track_id"]
                return self

            def to_pylist(self):
                return [{"track_id": track_id} for track_id in self.track_ids]

        return FakeArrow(self.all_track_ids)


class FakeDb:
    def __init__(self, table):
        self.table = table
        self.opened = []

    def open_table(self, name):
        self.opened.append(name)
        return self.table


def test_lancedb_fts_compat_searches_taglist_text_field(monkeypatch):
    from mcrs.retrieval_modules.lancedb import LANCEDB_MODEL

    table = FakeTable(
        {
            "bm25_with_tag_list_text": [
                {"track_id": "track-1", "_score": 3.0},
                {"track_id": "track-2", "_score": 2.0},
            ]
        }
    )
    fake_db = FakeDb(table)
    monkeypatch.setattr("mcrs.retrieval_modules.lancedb.connect_lancedb", lambda _: fake_db)

    model = LANCEDB_MODEL(
        dataset_name="tracks",
        split_types=["all_tracks"],
        corpus_types=["track_name"],
        retrieval_config={
            "db_uri": "./cache/lancedb",
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
        },
    )

    assert model.text_to_item_retrieval("late night shoegaze", topk=20) == ["track-1", "track-2"]
    assert fake_db.opened == ["music_track_catalog"]
    assert table.search_calls == [
        {
            "query": "late night shoegaze",
            "query_type": "fts",
            "fts_columns": "bm25_with_tag_list_text",
        }
    ]


def test_lancedb_bm25s_compat_uses_tokenized_field_and_query_term_boosts(monkeypatch):
    from lancedb.query import BooleanQuery

    from mcrs.retrieval_modules.lancedb import LANCEDB_MODEL

    table = FakeTable(
        {
            "bm25_with_tag_list_bm25s_tokens_text": [
                {"track_id": "track-1", "_score": 3.0},
                {"track_id": "track-2", "_score": 2.0},
            ]
        }
    )
    fake_db = FakeDb(table)
    monkeypatch.setattr("mcrs.retrieval_modules.lancedb.connect_lancedb", lambda _: fake_db)

    model = LANCEDB_MODEL(
        dataset_name="tracks",
        split_types=["all_tracks"],
        corpus_types=["track_name"],
        retrieval_config={
            "db_uri": "./cache/lancedb",
            "table_name": "music_track_catalog",
            "searches": [
                {
                    "name": "bm25s_with_tag_list",
                    "kind": "fts_bm25s_compat",
                    "corpus_fields": list(BM25_WITH_TAG_LIST_CORPUS_FIELDS),
                    "weight": 1.0,
                    "topk": 1000,
                }
            ],
            "fusion": {"method": "weighted_rrf"},
        },
    )

    assert model.text_to_item_retrieval(
        "track_name: Blue Song\ntrack_name: Red Song\nlate night shoegaze and the",
        topk=20,
    ) == ["track-1", "track-2"]

    call = table.search_calls[0]
    assert call["query_type"] == "fts"
    assert "fts_columns" not in call
    assert isinstance(call["query"], BooleanQuery)
    boosts_by_term = {query.query: query.boost for _, query in call["query"].queries}
    assert boosts_by_term == {
        "track_name": 2.0,
        "blue": 1.0,
        "song": 2.0,
        "red": 1.0,
        "late": 1.0,
        "night": 1.0,
        "shoegaze": 1.0,
    }
    assert {query.column for _, query in call["query"].queries} == {
        "bm25_with_tag_list_bm25s_tokens_text"
    }


def test_lancedb_pads_short_fts_results_from_catalog_order(monkeypatch):
    from mcrs.retrieval_modules.lancedb import LANCEDB_MODEL

    table = FakeTable(
        {
            "bm25_with_tag_list_text": [
                {"track_id": "track-2", "_score": 3.0},
            ]
        },
        all_track_ids=["track-1", "track-2", "track-3"],
    )
    fake_db = FakeDb(table)
    monkeypatch.setattr("mcrs.retrieval_modules.lancedb.connect_lancedb", lambda _: fake_db)

    model = LANCEDB_MODEL(
        dataset_name="tracks",
        split_types=["all_tracks"],
        corpus_types=["track_name"],
        retrieval_config={
            "db_uri": "./cache/lancedb",
            "table_name": "music_track_catalog",
            "searches": [
                {
                    "name": "bm25_with_tag_list",
                    "kind": "fts_compat",
                    "corpus_fields": list(BM25_WITH_TAG_LIST_CORPUS_FIELDS),
                    "weight": 1.0,
                    "topk": 3,
                }
            ],
            "fusion": {"method": "weighted_rrf"},
        },
    )

    assert model.text_to_item_retrieval("rare query", topk=3) == ["track-2", "track-1", "track-3"]


def test_lancedb_multi_field_fts_uses_weighted_rrf(monkeypatch):
    from mcrs.retrieval_modules.lancedb import LANCEDB_MODEL

    table = FakeTable(
        {
            "track_name_text": [
                {"track_id": "track-a", "_score": 10.0},
                {"track_id": "track-b", "_score": 9.0},
            ],
            "tag_list_text": [
                {"track_id": "track-c", "_score": 10.0},
                {"track_id": "track-a", "_score": 9.0},
            ],
        }
    )
    fake_db = FakeDb(table)
    monkeypatch.setattr("mcrs.retrieval_modules.lancedb.connect_lancedb", lambda _: fake_db)

    model = LANCEDB_MODEL(
        dataset_name="tracks",
        split_types=["all_tracks"],
        corpus_types=["track_name"],
        retrieval_config={
            "db_uri": "./cache/lancedb",
            "table_name": "music_track_catalog",
            "searches": [
                {
                    "name": "field_fts",
                    "kind": "fts_fields",
                    "weight": 1.0,
                    "fields": [
                        {"name": "track_name", "weight": 0.2},
                        {"name": "tag_list", "weight": 0.8},
                    ],
                    "topk": 1000,
                }
            ],
            "fusion": {"method": "weighted_rrf"},
        },
    )

    assert model.text_to_item_retrieval("ambient calm", topk=3) == ["track-a", "track-c", "track-b"]
    assert [call["fts_columns"] for call in table.search_calls] == ["track_name_text", "tag_list_text"]


def test_lancedb_retriever_rejects_non_cpu_device():
    from mcrs.retrieval_modules.lancedb import LANCEDB_MODEL

    with pytest.raises(ValueError, match="CPU-only"):
        LANCEDB_MODEL(
            dataset_name="tracks",
            split_types=["all_tracks"],
            corpus_types=["track_name"],
            retrieval_config={
                "db_uri": "./cache/lancedb",
                "table_name": "music_track_catalog",
                "device": "cuda",
                "searches": [
                    {
                        "name": "bm25_with_tag_list",
                        "kind": "fts_compat",
                        "corpus_fields": list(BM25_WITH_TAG_LIST_CORPUS_FIELDS),
                        "topk": 1000,
                    }
                ],
                "fusion": {"method": "weighted_rrf"},
            },
        )
