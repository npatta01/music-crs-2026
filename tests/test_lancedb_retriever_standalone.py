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


class FakeTableWithSchema(FakeTable):
    def __init__(self, column_names):
        super().__init__()
        self.schema = type("FakeSchema", (), {"names": list(column_names)})()


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


class ChannelAwareFakeTable:
    """A FakeTable that returns hits per FTS column.

    Two modes:
    - Legacy `fts_columns=...` string-query path: returns `_hits_by_column[column]`.
    - New BooleanQuery + MatchQuery path: iterates the BooleanQuery's clauses,
      unions hits across all referenced columns, with score = sum(per-hit-score *
      match.boost). Mimics what tantivy would do for a multi-field Boolean query.
    """

    def __init__(self, hits_by_column):
        self.search_calls = []
        self._hits_by_column = hits_by_column

    def search(self, query, **kwargs):
        from lancedb.query import BooleanQuery

        self.search_calls.append({"query": query, **kwargs})

        if isinstance(query, BooleanQuery):
            scores: dict[str, float] = {}
            first_seen: dict[str, int] = {}
            order = 0
            for _occur, match in query.queries:
                column = match.column
                boost = float(match.boost)
                for hit in self._hits_by_column.get(column, []):
                    tid = hit.get("track_id")
                    score = float(hit.get("_score", 0.0)) * boost
                    if tid not in first_seen:
                        first_seen[tid] = order
                        order += 1
                    scores[tid] = scores.get(tid, 0.0) + score
            ranked = sorted(scores, key=lambda t: (-scores[t], first_seen[t]))
            fused_hits = [{"track_id": tid, "_score": scores[tid]} for tid in ranked]
            return FakeQuery(fused_hits)

        # Legacy single-column path
        column = kwargs.get("fts_columns")
        hits = self._hits_by_column.get(column, [])
        return FakeQuery(list(hits))


# --- FieldQuery dataclass validation ---


def test_field_query_rejects_empty_field():
    import pytest

    from mcrs.retrieval_modules.base import FieldQuery

    with pytest.raises(ValueError, match="non-empty string"):
        FieldQuery(field="", query="anything")


def test_field_query_rejects_non_positive_boost():
    import pytest

    from mcrs.retrieval_modules.base import FieldQuery

    with pytest.raises(ValueError, match="must be positive"):
        FieldQuery(field="artist_name", query="Morphine", boost=0.0)


# --- supported_*_fields introspection ---


def test_supported_text_and_vector_fields_exposed(monkeypatch):
    from mcrs.lancedb.retriever import LanceDbRetriever
    from mcrs.milvus.indexing import BM25_EXPERIMENTAL_FIELDS

    table = FakeTable()
    fake_db = FakeDb(table)
    monkeypatch.setattr("mcrs.lancedb.retriever.connect_lancedb", lambda _: fake_db)

    retriever = LanceDbRetriever.from_retrieval_config(_retrieval_config())

    assert retriever.supported_text_fields == frozenset(BM25_EXPERIMENTAL_FIELDS)
    assert "metadata_qwen3_embedding_0_6b" in retriever.supported_vector_fields
    assert "metadata_qwen3_embedding_4b" in retriever.supported_vector_fields
    assert "attributes_qwen3_embedding_4b" in retriever.supported_vector_fields
    assert "metadata_qwen3_embedding_8b" in retriever.supported_vector_fields
    assert "attributes_qwen3_embedding_8b" in retriever.supported_vector_fields


def test_supported_text_fields_reflect_table_schema(monkeypatch):
    from mcrs.lancedb.retriever import LanceDbRetriever

    table = FakeTableWithSchema(
        [
            "track_id",
            "track_name_text",
            "artist_name_text",
            "album_name_text",
            "tag_list_text",
        ]
    )
    fake_db = FakeDb(table)
    monkeypatch.setattr("mcrs.lancedb.retriever.connect_lancedb", lambda _: fake_db)

    retriever = LanceDbRetriever.from_retrieval_config(_retrieval_config())

    assert "tag_list" in retriever.supported_text_fields
    assert "release_year" not in retriever.supported_text_fields
    assert "release_decade" not in retriever.supported_text_fields
    assert retriever.supported_vector_fields == frozenset()


def test_supported_vector_fields_reflect_table_schema(monkeypatch):
    from mcrs.lancedb.retriever import LanceDbRetriever

    table = FakeTableWithSchema(
        [
            "track_id",
            "track_name_text",
            "metadata_qwen3_embedding_0_6b",
            "has_metadata_qwen3_embedding_0_6b",
            "attributes_qwen3_embedding_0_6b",
            "has_attributes_qwen3_embedding_0_6b",
        ]
    )
    fake_db = FakeDb(table)
    monkeypatch.setattr("mcrs.lancedb.retriever.connect_lancedb", lambda _: fake_db)

    retriever = LanceDbRetriever.from_retrieval_config(_retrieval_config())

    assert "metadata_qwen3_embedding_0_6b" in retriever.supported_vector_fields
    assert "attributes_qwen3_embedding_0_6b" in retriever.supported_vector_fields
    assert "metadata_qwen3_embedding_8b" not in retriever.supported_vector_fields


def test_lancedb_retriever_satisfies_retriever_protocol(monkeypatch):
    from mcrs.lancedb.retriever import LanceDbRetriever
    from mcrs.retrieval_modules.base import Retriever

    table = FakeTable()
    fake_db = FakeDb(table)
    monkeypatch.setattr("mcrs.lancedb.retriever.connect_lancedb", lambda _: fake_db)

    retriever = LanceDbRetriever.from_retrieval_config(_retrieval_config())

    assert isinstance(retriever, Retriever)  # runtime_checkable Protocol


# --- search(): single-clause path ---


def test_search_single_clause_issues_one_boolean_query(monkeypatch):
    """Single clause goes through the BooleanQuery path (one MatchQuery, boost=1)."""
    from lancedb.query import BooleanQuery

    from mcrs.lancedb.retriever import LanceDbRetriever
    from mcrs.milvus.indexing import bm25_text_field_name
    from mcrs.retrieval_modules.base import FieldQuery

    artist_col = bm25_text_field_name("artist_name")
    table = ChannelAwareFakeTable({
        artist_col: [
            {"track_id": "morphine-1", "_score": 5.0},
            {"track_id": "morphine-2", "_score": 3.0},
        ],
    })
    fake_db = FakeDb(table)
    monkeypatch.setattr("mcrs.lancedb.retriever.connect_lancedb", lambda _: fake_db)

    retriever = LanceDbRetriever.from_retrieval_config(_retrieval_config())

    result = retriever.search(
        [FieldQuery(field="artist_name", query="Morphine")],
        topk=10,
    )

    # Single backend call with a BooleanQuery wrapping one MatchQuery
    assert len(table.search_calls) == 1
    call = table.search_calls[0]
    assert isinstance(call["query"], BooleanQuery)
    assert len(call["query"].queries) == 1
    _, mq = call["query"].queries[0]
    assert mq.column == artist_col
    assert mq.query == "Morphine"
    assert mq.boost == 1.0
    # Single clause => raw FTS scores pass through (× boost 1.0)
    assert result == [("morphine-1", 5.0), ("morphine-2", 3.0)]


def test_search_skips_blank_clauses(monkeypatch):
    from mcrs.lancedb.retriever import LanceDbRetriever
    from mcrs.retrieval_modules.base import FieldQuery

    table = FakeTable()
    fake_db = FakeDb(table)
    monkeypatch.setattr("mcrs.lancedb.retriever.connect_lancedb", lambda _: fake_db)

    retriever = LanceDbRetriever.from_retrieval_config(_retrieval_config())

    # Only the non-empty clause should actually issue a backend call.
    result = retriever.search(
        [
            FieldQuery(field="artist_name", query="Morphine"),
            FieldQuery(field="tag_list", query="   "),
            FieldQuery(field="album_name", query=""),
        ],
        topk=10,
    )

    assert result == [("track-1", 2.0), ("track-2", 1.0)]
    assert len(table.search_calls) == 1


def test_search_empty_clause_list_returns_empty(monkeypatch):
    from mcrs.lancedb.retriever import LanceDbRetriever

    table = FakeTable()
    fake_db = FakeDb(table)
    monkeypatch.setattr("mcrs.lancedb.retriever.connect_lancedb", lambda _: fake_db)

    retriever = LanceDbRetriever.from_retrieval_config(_retrieval_config())

    assert retriever.search([], topk=10) == []
    assert table.search_calls == []


def test_search_rejects_unknown_field(monkeypatch):
    import pytest

    from mcrs.lancedb.retriever import LanceDbRetriever
    from mcrs.retrieval_modules.base import FieldQuery

    table = FakeTable()
    fake_db = FakeDb(table)
    monkeypatch.setattr("mcrs.lancedb.retriever.connect_lancedb", lambda _: fake_db)

    retriever = LanceDbRetriever.from_retrieval_config(_retrieval_config())

    with pytest.raises(ValueError, match="Unsupported BM25 field"):
        retriever.search(
            [FieldQuery(field="not_a_real_field", query="anything")],
            topk=10,
        )


# --- search(): multi-clause path with internal weighted RRF ---


def test_search_multi_clause_uses_one_boolean_query_with_match_per_clause(monkeypatch):
    """Multi-clause goes through ONE BooleanQuery call (Solr-style) with one
    MatchQuery per clause. tantivy then ranks across all fields in a single pass.
    """
    from lancedb.query import BooleanQuery

    from mcrs.lancedb.retriever import LanceDbRetriever
    from mcrs.milvus.indexing import bm25_text_field_name
    from mcrs.retrieval_modules.base import FieldQuery

    artist_col = bm25_text_field_name("artist_name")
    tag_col = bm25_text_field_name("tag_list")
    table = ChannelAwareFakeTable({
        artist_col: [
            {"track_id": "morphine-1", "_score": 5.0},
            {"track_id": "morphine-2", "_score": 3.0},
        ],
        tag_col: [
            {"track_id": "lounge-1", "_score": 2.5},
            {"track_id": "morphine-1", "_score": 1.5},  # overlap with artist channel
        ],
    })
    fake_db = FakeDb(table)
    monkeypatch.setattr("mcrs.lancedb.retriever.connect_lancedb", lambda _: fake_db)

    retriever = LanceDbRetriever.from_retrieval_config(_retrieval_config())

    result = retriever.search(
        [
            FieldQuery(field="artist_name", query="Morphine", boost=3.0),
            FieldQuery(field="tag_list", query="smoky lounge", boost=1.5),
        ],
        topk=10,
    )

    # ONE backend call with a BooleanQuery wrapping both MatchQueries
    assert len(table.search_calls) == 1
    bq = table.search_calls[0]["query"]
    assert isinstance(bq, BooleanQuery)
    assert len(bq.queries) == 2
    matches_by_col = {mq.column: mq for _, mq in bq.queries}
    assert matches_by_col[artist_col].query == "Morphine"
    assert matches_by_col[artist_col].boost == 3.0
    assert matches_by_col[tag_col].query == "smoky lounge"
    assert matches_by_col[tag_col].boost == 1.5

    # morphine-1 appears in BOTH clauses => highest score under boosted fusion
    assert result[0][0] == "morphine-1"
    assert set(tid for tid, _ in result) == {"morphine-1", "morphine-2", "lounge-1"}


def test_search_multi_clause_higher_boost_dominates_ranking(monkeypatch):
    from mcrs.lancedb.retriever import LanceDbRetriever
    from mcrs.milvus.indexing import bm25_text_field_name
    from mcrs.retrieval_modules.base import FieldQuery

    artist_col = bm25_text_field_name("artist_name")
    tag_col = bm25_text_field_name("tag_list")
    # Each channel returns ONE distinct track at rank 1 so RRF rank is identical;
    # only the boost differentiates them.
    table = ChannelAwareFakeTable({
        artist_col: [{"track_id": "from-artist", "_score": 1.0}],
        tag_col:    [{"track_id": "from-tag",    "_score": 1.0}],
    })
    fake_db = FakeDb(table)
    monkeypatch.setattr("mcrs.lancedb.retriever.connect_lancedb", lambda _: fake_db)

    retriever = LanceDbRetriever.from_retrieval_config(_retrieval_config())

    result = retriever.search(
        [
            FieldQuery(field="artist_name", query="A", boost=10.0),  # higher boost
            FieldQuery(field="tag_list",    query="T", boost=1.0),
        ],
        topk=10,
    )
    # Higher-boost clause's track should rank first
    assert result[0][0] == "from-artist"
    assert result[1][0] == "from-tag"


# --- search_embedding: distance → similarity flip ---


def test_search_embedding_flips_cosine_distance_to_similarity(monkeypatch):
    from mcrs.lancedb.retriever import LanceDbRetriever

    table = FakeVectorTable()  # returns distances 0.01 and 0.03
    fake_db = FakeDb(table)
    monkeypatch.setattr("mcrs.lancedb.retriever.connect_lancedb", lambda _: fake_db)

    retriever = LanceDbRetriever.from_retrieval_config(_retrieval_config())

    result = retriever.search_embedding(
        query_vector=[0.1, 0.2, 0.3],
        vector_field="metadata_qwen3_embedding_0_6b",
        topk=2,
        distance_type="cosine",
    )

    # cosine: similarity = 1 - distance. Higher = more similar.
    assert result[0] == ("track-v1", 1.0 - 0.01)
    assert result[1] == ("track-v2", 1.0 - 0.03)
    assert result[0][1] > result[1][1]  # higher = better


def test_search_embedding_flips_l2_distance_to_similarity(monkeypatch):
    from mcrs.lancedb.retriever import LanceDbRetriever

    table = FakeVectorTable()
    fake_db = FakeDb(table)
    monkeypatch.setattr("mcrs.lancedb.retriever.connect_lancedb", lambda _: fake_db)

    retriever = LanceDbRetriever.from_retrieval_config(_retrieval_config())

    result = retriever.search_embedding(
        query_vector=[0.5],
        vector_field="metadata_qwen3_embedding_0_6b",
        topk=2,
        distance_type="l2",
    )

    # l2: similarity = 1 / (1 + distance). Still monotonic; higher = better.
    assert result[0] == ("track-v1", 1.0 / (1.0 + 0.01))
    assert result[1] == ("track-v2", 1.0 / (1.0 + 0.03))
    assert result[0][1] > result[1][1]


def test_search_embedding_converts_dot_distance_to_similarity(monkeypatch):
    from mcrs.lancedb.retriever import LanceDbRetriever

    table = FakeVectorTable()
    fake_db = FakeDb(table)
    monkeypatch.setattr("mcrs.lancedb.retriever.connect_lancedb", lambda _: fake_db)

    retriever = LanceDbRetriever.from_retrieval_config(_retrieval_config())

    result = retriever.search_embedding(
        query_vector=[0.5],
        vector_field="metadata_qwen3_embedding_0_6b",
        topk=2,
        distance_type="dot",
    )

    # LanceDB dot returns distance = 1 - dot_product. Convert back so higher
    # still means more similar, matching the Retriever Protocol contract.
    assert result[0] == ("track-v1", 1.0 - 0.01)
    assert result[1] == ("track-v2", 1.0 - 0.03)
    assert result[0][1] > result[1][1]


def test_dense_vector_search_rejects_unsupported_distance_type(monkeypatch):
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
            "distance_type": "ip",
            "weight": 1.0,
            "topk": 1000,
        }
    ]

    with pytest.raises(ValueError, match="Unsupported LanceDB distance type"):
        LanceDbRetriever.from_retrieval_config(config)


def test_search_embedding_rejects_unsupported_distance_type(monkeypatch):
    import pytest

    from mcrs.lancedb.retriever import LanceDbRetriever

    table = FakeVectorTable()
    fake_db = FakeDb(table)
    monkeypatch.setattr("mcrs.lancedb.retriever.connect_lancedb", lambda _: fake_db)

    retriever = LanceDbRetriever.from_retrieval_config(_retrieval_config())

    with pytest.raises(ValueError, match="Unsupported LanceDB distance type"):
        retriever.search_embedding(
            query_vector=[0.1],
            vector_field="metadata_qwen3_embedding_0_6b",
            topk=1,
            distance_type="inner_product",
        )


def test_search_embedding_rejects_unknown_vector_field(monkeypatch):
    import pytest

    from mcrs.lancedb.retriever import LanceDbRetriever

    table = FakeVectorTable()
    fake_db = FakeDb(table)
    monkeypatch.setattr("mcrs.lancedb.retriever.connect_lancedb", lambda _: fake_db)

    retriever = LanceDbRetriever.from_retrieval_config(_retrieval_config())

    with pytest.raises(ValueError, match="Unsupported LanceDB vector field"):
        retriever.search_embedding(
            query_vector=[0.1],
            vector_field="not_a_real_field",
            topk=1,
        )


def test_search_embedding_respects_filter_missing_false(monkeypatch):
    from mcrs.lancedb.retriever import LanceDbRetriever

    table = FakeVectorTable()
    fake_db = FakeDb(table)
    monkeypatch.setattr("mcrs.lancedb.retriever.connect_lancedb", lambda _: fake_db)

    retriever = LanceDbRetriever.from_retrieval_config(_retrieval_config())

    retriever.search_embedding(
        query_vector=[0.5],
        vector_field="metadata_qwen3_embedding_0_6b",
        topk=1,
        filter_missing=False,
    )

    call = table.search_calls[0]
    assert call["query_builder"].where_filter is None


# --- declarative-API guards (kept; searches is optional now) ---


def test_searches_optional_for_callers_using_only_protocol_api(monkeypatch):
    from mcrs.lancedb.retriever import LanceDbRetriever
    from mcrs.milvus.indexing import bm25_text_field_name
    from mcrs.retrieval_modules.base import FieldQuery

    table = ChannelAwareFakeTable({
        bm25_text_field_name("artist_name"): [{"track_id": "a-1", "_score": 1.0}],
    })
    fake_db = FakeDb(table)
    monkeypatch.setattr("mcrs.lancedb.retriever.connect_lancedb", lambda _: fake_db)

    config = _retrieval_config()
    del config["searches"]
    retriever = LanceDbRetriever.from_retrieval_config(config)

    result = retriever.search(
        [FieldQuery(field="artist_name", query="Morphine")],
        topk=5,
    )
    assert result == [("a-1", 1.0)]


def test_declarative_retrieval_without_searches_raises_clear_error(monkeypatch):
    import pytest

    from mcrs.lancedb.retriever import LanceDbRetriever

    table = FakeTable()
    fake_db = FakeDb(table)
    monkeypatch.setattr("mcrs.lancedb.retriever.connect_lancedb", lambda _: fake_db)

    config = _retrieval_config()
    del config["searches"]
    retriever = LanceDbRetriever.from_retrieval_config(config)

    with pytest.raises(RuntimeError, match="search_embedding|requires `searches`"):
        retriever.retrieve("anything", topk=10)


def test_searches_when_present_must_be_non_empty(monkeypatch):
    import pytest

    from mcrs.lancedb.retriever import LanceDbRetriever

    table = FakeTable()
    fake_db = FakeDb(table)
    monkeypatch.setattr("mcrs.lancedb.retriever.connect_lancedb", lambda _: fake_db)

    config = _retrieval_config()
    config["searches"] = []
    with pytest.raises(ValueError, match="must be a non-empty list"):
        LanceDbRetriever.from_retrieval_config(config)
