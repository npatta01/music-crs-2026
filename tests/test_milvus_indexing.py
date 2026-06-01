import pytest

from mcrs.milvus.indexing import (
    DEFAULT_BM25_ANALYZER_PARAMS,
    BM25_COMPAT_CORPUS_FIELDS,
    BM25_COMPAT_SPARSE_FIELD,
    BM25_COMPAT_TEXT_FIELD,
    BM25_EXPERIMENTAL_FIELDS,
    BM25_WITH_TAG_LIST_CORPUS_FIELDS,
    BM25_WITH_TAG_LIST_SPARSE_FIELD,
    BM25_WITH_TAG_LIST_TEXT_FIELD,
    EMBEDDING_FIELDS,
    build_track_collection_plan,
    build_track_document,
    build_vector_index_plan,
    has_embedding_field_name,
    milvus_safe_field_name,
    render_bm25_text_fields,
    wait_for_collection_indexes,
)


def test_milvus_safe_field_name_normalizes_embedding_columns():
    assert milvus_safe_field_name("metadata-qwen3_embedding_0.6b") == "metadata_qwen3_embedding_0_6b"
    assert milvus_safe_field_name("audio-laion_clap") == "audio_laion_clap"


def test_build_track_collection_plan_infers_metadata_and_vector_schema():
    metadata_rows = [
        {
            "track_id": "track-1",
            "track_name": ["A Song"],
            "artist_name": ["An Artist"],
            "album_name": ["An Album"],
            "tag_list": ["calm", "ambient"],
            "popularity": 39.0,
            "release_date": "2006-12-06",
            "duration": 300920,
            "ISRC": ["TCABY1497179"],
            "artist_id": ["artist-1"],
            "album_id": ["album-1"],
        },
        {
            "track_id": "track-2",
            "track_name": ["Second Song"],
            "artist_name": ["Duo", "Featured"],
            "album_name": ["Compilation"],
            "tag_list": ["upbeat"],
            "popularity": 12.5,
            "release_date": "2019-07-01",
            "duration": 180000,
            "ISRC": [],
            "artist_id": ["artist-2", "artist-3"],
            "album_id": ["album-2"],
        },
    ]
    embedding_rows = [
        {
            "track_id": "track-1",
            "audio-laion_clap": [0.1, 0.2, 0.3],
            "image-siglip2": [0.4, 0.5],
            "cf-bpr": [0.6, 0.7],
            "attributes-qwen3_embedding_0.6b": [0.8, 0.9, 1.0, 1.1],
            "lyrics-qwen3_embedding_0.6b": [1.2, 1.3, 1.4, 1.5],
            "metadata-qwen3_embedding_0.6b": [1.6, 1.7, 1.8, 1.9],
        },
        {
            "track_id": "track-2",
            "audio-laion_clap": [],
            "image-siglip2": [0.0, 0.1],
            "cf-bpr": [0.2, 0.3],
            "attributes-qwen3_embedding_0.6b": [0.4, 0.5, 0.6, 0.7],
            "lyrics-qwen3_embedding_0.6b": [],
            "metadata-qwen3_embedding_0.6b": [0.8, 0.9, 1.0, 1.1],
        },
    ]

    plan = build_track_collection_plan(metadata_rows, embedding_rows)
    field_specs = {field.name: field for field in plan.fields}

    assert field_specs["track_id"].is_primary is True
    assert field_specs["track_id"].datatype_name == "VARCHAR"
    assert field_specs["track_name"].datatype_name == "ARRAY"
    assert field_specs["track_name"].element_type_name == "VARCHAR"
    assert field_specs["track_name"].max_capacity == 1
    assert field_specs["artist_name"].max_capacity == 2
    assert field_specs["popularity"].datatype_name == "DOUBLE"
    assert field_specs["duration"].datatype_name == "INT64"
    assert field_specs["release_date"].max_length == len("2019-07-01")
    assert field_specs["audio_laion_clap"].dim == 3
    assert field_specs["audio_laion_clap"].nullable is False
    assert field_specs["has_audio_laion_clap"].datatype_name == "BOOL"
    assert field_specs["has_audio_laion_clap"].nullable is False
    assert field_specs["metadata_qwen3_embedding_0_6b"].dim == 4
    assert field_specs[BM25_COMPAT_TEXT_FIELD].datatype_name == "VARCHAR"
    assert field_specs[BM25_COMPAT_TEXT_FIELD].analyzer_params == DEFAULT_BM25_ANALYZER_PARAMS
    assert field_specs[BM25_COMPAT_SPARSE_FIELD].datatype_name == "SPARSE_FLOAT_VECTOR"
    assert field_specs[BM25_WITH_TAG_LIST_TEXT_FIELD].datatype_name == "VARCHAR"
    assert field_specs[BM25_WITH_TAG_LIST_TEXT_FIELD].analyzer_params == DEFAULT_BM25_ANALYZER_PARAMS
    assert field_specs[BM25_WITH_TAG_LIST_SPARSE_FIELD].datatype_name == "SPARSE_FLOAT_VECTOR"
    assert field_specs["track_name_text"].datatype_name == "VARCHAR"
    assert field_specs["track_name_text"].analyzer_params == DEFAULT_BM25_ANALYZER_PARAMS
    assert field_specs["track_name_sparse"].datatype_name == "SPARSE_FLOAT_VECTOR"
    assert field_specs["release_date_text"].datatype_name == "VARCHAR"
    assert field_specs["release_date_sparse"].datatype_name == "SPARSE_FLOAT_VECTOR"
    assert field_specs["release_year_text"].datatype_name == "VARCHAR"
    assert field_specs["release_year_sparse"].datatype_name == "SPARSE_FLOAT_VECTOR"
    assert field_specs["release_decade_text"].datatype_name == "VARCHAR"
    assert field_specs["release_decade_sparse"].datatype_name == "SPARSE_FLOAT_VECTOR"
    assert field_specs["tag_list_text"].datatype_name == "VARCHAR"
    assert field_specs["tag_list_sparse"].datatype_name == "SPARSE_FLOAT_VECTOR"
    assert set(plan.vector_field_names) == {milvus_safe_field_name(name) for name in EMBEDDING_FIELDS}
    assert set(plan.bm25_field_names) == {
        BM25_COMPAT_TEXT_FIELD,
        BM25_WITH_TAG_LIST_TEXT_FIELD,
        "track_name_text",
        "artist_name_text",
        "album_name_text",
        "release_date_text",
        "release_year_text",
        "release_decade_text",
        "tag_list_text",
    }


def test_build_track_document_preserves_metadata_and_zero_fills_missing_vectors():
    metadata_row = {
        "track_id": "track-1",
        "track_name": ["A Song"],
        "artist_name": ["An Artist"],
        "album_name": ["An Album"],
        "tag_list": ["calm", "ambient"],
        "popularity": 39.0,
        "release_date": "2006-12-06",
        "duration": 300920,
        "ISRC": ["TCABY1497179"],
        "artist_id": ["artist-1"],
        "album_id": ["album-1"],
    }
    embedding_row = {
        "track_id": "track-1",
        "audio-laion_clap": [],
        "image-siglip2": [0.4, 0.5],
        "cf-bpr": [0.6, 0.7],
        "attributes-qwen3_embedding_0.6b": [0.8, 0.9, 1.0, 1.1],
        "lyrics-qwen3_embedding_0.6b": [],
        "metadata-qwen3_embedding_0.6b": [1.6, 1.7, 1.8, 1.9],
    }

    plan = build_track_collection_plan(
        metadata_rows=[metadata_row],
        embedding_rows=[
            {
                "track_id": "seed",
                "audio-laion_clap": [0.1, 0.2],
                "image-siglip2": [0.3, 0.4],
                "cf-bpr": [0.5, 0.6],
                "attributes-qwen3_embedding_0.6b": [0.7, 0.8, 0.9, 1.0],
                "lyrics-qwen3_embedding_0.6b": [1.1, 1.2, 1.3, 1.4],
                "metadata-qwen3_embedding_0.6b": [1.5, 1.6, 1.7, 1.8],
            }
        ],
    )
    doc = build_track_document(metadata_row, embedding_row, vector_dims=plan.vector_dims)

    assert doc["track_id"] == "track-1"
    assert doc["track_name"] == ["A Song"]
    assert doc["audio_laion_clap"] == [0.0, 0.0]
    assert doc["lyrics_qwen3_embedding_0_6b"] == [0.0, 0.0, 0.0, 0.0]
    assert doc["metadata_qwen3_embedding_0_6b"] == [1.6, 1.7, 1.8, 1.9]
    assert doc["has_audio_laion_clap"] is False
    assert doc["has_lyrics_qwen3_embedding_0_6b"] is False
    assert doc["has_metadata_qwen3_embedding_0_6b"] is True
    assert doc[BM25_COMPAT_TEXT_FIELD] == (
        "track_name: A Song\n"
        "artist_name: An Artist\n"
        "album_name: An Album\n"
        "release_date: 2006-12-06\n"
    )
    assert doc[BM25_WITH_TAG_LIST_TEXT_FIELD] == (
        "track_name: A Song\n"
        "artist_name: An Artist\n"
        "album_name: An Album\n"
        "release_date: 2006-12-06\n"
        "tag_list: calm, ambient\n"
    )
    assert doc["track_name_text"] == "track_name: A Song\n"
    assert doc["artist_name_text"] == "artist_name: An Artist\n"
    assert doc["release_year_text"] == "2006"
    assert doc["release_decade_text"] == "2000s"
    assert doc["tag_list_text"] == "tag_list: calm, ambient\n"


def test_build_track_document_supports_metadata_only_rows():
    metadata_row = {
        "track_id": "track-3",
        "track_name": ["Metadata Only"],
        "artist_name": ["Unknown"],
        "album_name": ["Loose Ends"],
        "tag_list": [],
        "popularity": 0.0,
        "release_date": "2026-01-01",
        "duration": 123456,
        "ISRC": [],
        "artist_id": [],
        "album_id": [],
    }

    plan = build_track_collection_plan(
        metadata_rows=[metadata_row],
        embedding_rows=[
            {
                "track_id": "seed",
                "audio-laion_clap": [0.1, 0.2],
                "image-siglip2": [0.3, 0.4],
                "cf-bpr": [0.5, 0.6],
                "attributes-qwen3_embedding_0.6b": [0.7, 0.8],
                "lyrics-qwen3_embedding_0.6b": [0.9, 1.0],
                "metadata-qwen3_embedding_0.6b": [1.1, 1.2],
            }
        ],
    )
    doc = build_track_document(metadata_row, embedding_row=None, vector_dims=plan.vector_dims)

    assert doc["track_id"] == "track-3"
    for raw_name in EMBEDDING_FIELDS:
        field_name = milvus_safe_field_name(raw_name)
        assert doc[field_name] == [0.0] * plan.vector_dims[field_name]
        assert doc[has_embedding_field_name(field_name)] is False


def test_render_bm25_text_fields_matches_default_formatter_shape():
    metadata_row = {
        "track_name": ["Song A", "Song A (Live)"],
        "artist_name": ["Artist A", "Artist B"],
        "album_name": ["Album X"],
        "tag_list": ["indie", "energetic"],
        "release_date": "2020-01-02",
    }

    bm25_fields = render_bm25_text_fields(metadata_row)

    assert bm25_fields[BM25_COMPAT_TEXT_FIELD] == (
        "track_name: Song A, Song A (Live)\n"
        "artist_name: Artist A, Artist B\n"
        "album_name: Album X\n"
        "release_date: 2020-01-02\n"
    )
    assert bm25_fields[BM25_WITH_TAG_LIST_TEXT_FIELD] == (
        "track_name: Song A, Song A (Live)\n"
        "artist_name: Artist A, Artist B\n"
        "album_name: Album X\n"
        "release_date: 2020-01-02\n"
        "tag_list: indie, energetic\n"
    )
    assert bm25_fields["track_name_text"] == "track_name: Song A, Song A (Live)\n"
    assert bm25_fields["artist_name_text"] == "artist_name: Artist A, Artist B\n"
    assert bm25_fields["album_name_text"] == "album_name: Album X\n"
    assert bm25_fields["release_date_text"] == "release_date: 2020-01-02\n"
    assert bm25_fields["release_year_text"] == "2020"
    assert bm25_fields["release_decade_text"] == "2020s"
    assert bm25_fields["tag_list_text"] == "tag_list: indie, energetic\n"


def test_bm25_compat_corpus_fields_are_the_benchmark_fields():
    assert BM25_COMPAT_CORPUS_FIELDS == (
        "track_name",
        "artist_name",
        "album_name",
        "release_date",
    )
    assert BM25_WITH_TAG_LIST_CORPUS_FIELDS == (
        "track_name",
        "artist_name",
        "album_name",
        "release_date",
        "tag_list",
    )
    assert BM25_EXPERIMENTAL_FIELDS == (
        "track_name",
        "artist_name",
        "album_name",
        "release_date",
        "release_year",
        "release_decade",
        "tag_list",
    )


def test_build_vector_index_plan_supports_exact_dense_and_bm25_sparse_indexes():
    metadata_rows = [
        {
            "track_id": "track-1",
            "track_name": ["A Song"],
            "artist_name": ["An Artist"],
            "album_name": ["An Album"],
            "tag_list": ["calm"],
            "popularity": 1.0,
            "release_date": "2000-01-01",
            "duration": 123,
            "ISRC": [],
            "artist_id": [],
            "album_id": [],
        }
    ]
    embedding_rows = [
        {
            "track_id": "track-1",
            "audio-laion_clap": [0.1, 0.2],
            "image-siglip2": [0.3, 0.4],
            "cf-bpr": [0.5, 0.6],
            "attributes-qwen3_embedding_0.6b": [0.7, 0.8],
            "lyrics-qwen3_embedding_0.6b": [0.9, 1.0],
            "metadata-qwen3_embedding_0.6b": [1.1, 1.2],
        }
    ]
    plan = build_track_collection_plan(metadata_rows, embedding_rows)

    dense_indexes = build_vector_index_plan(plan, dense_index_type="FLAT")
    sparse_indexes = {item["field_name"]: item for item in dense_indexes if item["field_name"].endswith("_sparse")}
    flat_indexes = {item["field_name"]: item for item in dense_indexes if item["field_name"] in plan.vector_field_names}

    assert flat_indexes["audio_laion_clap"]["index_type"] == "FLAT"
    assert flat_indexes["audio_laion_clap"]["metric_type"] == "COSINE"
    assert flat_indexes["audio_laion_clap"]["params"] == {}
    assert sparse_indexes[BM25_COMPAT_SPARSE_FIELD]["index_type"] == "SPARSE_INVERTED_INDEX"
    assert sparse_indexes[BM25_COMPAT_SPARSE_FIELD]["metric_type"] == "BM25"
    assert sparse_indexes[BM25_WITH_TAG_LIST_SPARSE_FIELD]["metric_type"] == "BM25"
    assert sparse_indexes["tag_list_sparse"]["metric_type"] == "BM25"


def test_wait_for_collection_indexes_polls_until_finished(monkeypatch):
    class FakeClient:
        def __init__(self):
            self.describe_calls = 0

        def list_indexes(self, collection_name):
            assert collection_name == "music_track_catalog"
            return ["dense_idx", "sparse_idx"]

        def describe_index(self, collection_name, index_name):
            assert collection_name == "music_track_catalog"
            self.describe_calls += 1
            if self.describe_calls <= 2:
                return {
                    "index_name": index_name,
                    "state": "InProgress",
                    "pending_index_rows": 5,
                }
            return {
                "index_name": index_name,
                "state": "Finished",
                "pending_index_rows": 0,
            }

    sleep_calls = []
    monkeypatch.setattr("mcrs.milvus.indexing.time.sleep", lambda _: sleep_calls.append("slept"))

    client = FakeClient()
    wait_for_collection_indexes(
        client=client,
        collection_name="music_track_catalog",
        timeout=1.0,
        poll_interval=0.0,
    )

    assert client.describe_calls >= 4
    assert sleep_calls == ["slept"]
