import json
from pathlib import Path

import pytest

from mcrs.lancedb.indexing import (
    BM25S_TOKENIZED_FTS_INDEX_OPTIONS,
    BM25_WITH_TAG_LIST_BM25S_TOKENIZED_TEXT_FIELD,
    DEFAULT_LANCEDB_TABLE_NAME,
    LANCEDB_FTS_TEXT_FIELDS,
    build_track_lancedb_table,
    build_track_record,
)
from mcrs.milvus.indexing import (
    BM25_COMPAT_TEXT_FIELD,
    BM25_WITH_TAG_LIST_TEXT_FIELD,
    EMBEDDING_FIELDS,
    build_track_collection_plan,
    has_embedding_field_name,
    milvus_safe_field_name,
)


def test_build_track_record_preserves_bm25_with_tag_list_text_and_vectors():
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
        "attributes-qwen3_embedding_0.6b": [0.8, 0.9],
        "lyrics-qwen3_embedding_0.6b": [],
        "metadata-qwen3_embedding_0.6b": [1.6, 1.7],
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

    record = build_track_record(metadata_row, embedding_row, vector_dims=plan.vector_dims)

    assert DEFAULT_LANCEDB_TABLE_NAME == "music_track_catalog"
    assert record["track_id"] == "track-1"
    assert record[BM25_WITH_TAG_LIST_TEXT_FIELD] == (
        "track_name: A Song\n"
        "artist_name: An Artist\n"
        "album_name: An Album\n"
        "release_date: 2006-12-06\n"
        "tag_list: calm, ambient\n"
    )
    assert record[BM25_WITH_TAG_LIST_BM25S_TOKENIZED_TEXT_FIELD] == (
        "track_name song artist_name artist album_name album release_date 2006 12 06 tag_list calm ambient"
    )
    assert record["audio_laion_clap"] == [0.0, 0.0]
    assert record["metadata_qwen3_embedding_0_6b"] == [1.6, 1.7]
    assert record["has_audio_laion_clap"] is False
    assert record["has_metadata_qwen3_embedding_0_6b"] is True


def test_build_track_record_supports_metadata_only_rows():
    metadata_row = {
        "track_id": "track-2",
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

    record = build_track_record(metadata_row, embedding_row=None, vector_dims=plan.vector_dims)

    for raw_name in EMBEDDING_FIELDS:
        field_name = milvus_safe_field_name(raw_name)
        assert record[field_name] == [0.0] * plan.vector_dims[field_name]
        assert record[has_embedding_field_name(field_name)] is False


def test_lancedb_fts_fields_include_taglist_compat_and_per_field_text():
    assert BM25_COMPAT_TEXT_FIELD in LANCEDB_FTS_TEXT_FIELDS
    assert BM25_WITH_TAG_LIST_TEXT_FIELD in LANCEDB_FTS_TEXT_FIELDS
    assert BM25_WITH_TAG_LIST_BM25S_TOKENIZED_TEXT_FIELD in LANCEDB_FTS_TEXT_FIELDS
    assert "track_name_text" in LANCEDB_FTS_TEXT_FIELDS
    assert "artist_name_text" in LANCEDB_FTS_TEXT_FIELDS
    assert "album_name_text" in LANCEDB_FTS_TEXT_FIELDS
    assert "release_date_text" in LANCEDB_FTS_TEXT_FIELDS
    assert "tag_list_text" in LANCEDB_FTS_TEXT_FIELDS


def test_bm25s_tokenized_fts_index_options_preserve_pre_tokenized_terms():
    assert BM25S_TOKENIZED_FTS_INDEX_OPTIONS == {
        "base_tokenizer": "whitespace",
        "lower_case": False,
        "stem": False,
        "remove_stop_words": False,
        "ascii_folding": False,
    }


def test_build_lancedb_script_includes_embeddings_by_default():
    from scripts.build_lancedb_index import build_parser

    parser = build_parser()

    assert parser.parse_args([]).include_embeddings is True
    assert parser.parse_args(["--include-embeddings"]).include_embeddings is True
    assert parser.parse_args(["--metadata-only"]).include_embeddings is False


def test_build_track_lancedb_table_defaults_to_embedding_columns(monkeypatch, tmp_path):
    metadata_row = {
        "track_id": "track-1",
        "track_name": ["A Song"],
        "artist_name": ["An Artist"],
        "album_name": ["An Album"],
        "tag_list": ["calm"],
        "popularity": 39.0,
        "release_date": "2006-12-06",
        "duration": 300920,
        "ISRC": [],
        "artist_id": [],
        "album_id": [],
    }
    embedding_row = {
        "track_id": "track-1",
        "audio-laion_clap": [0.1, 0.2],
        "image-siglip2": [0.3, 0.4],
        "cf-bpr": [0.5, 0.6],
        "attributes-qwen3_embedding_0.6b": [0.7, 0.8],
        "lyrics-qwen3_embedding_0.6b": [0.9, 1.0],
        "metadata-qwen3_embedding_0.6b": [1.1, 1.2],
    }

    class FakeTable:
        def __init__(self, rows):
            if hasattr(rows, "to_pylist"):
                rows = rows.to_pylist()
            self.rows = list(rows)
            self.fts_indexes = []
            self.optimized = False

        def add(self, rows):
            if hasattr(rows, "to_pylist"):
                rows = rows.to_pylist()
            self.rows.extend(rows)

        def create_fts_index(self, text_field, replace=True, **kwargs):
            self.fts_indexes.append((text_field, replace, kwargs))

        def optimize(self):
            self.optimized = True

    class FakeDb:
        def __init__(self):
            self.table = None

        def create_table(self, table_name, data, mode):
            assert table_name == DEFAULT_LANCEDB_TABLE_NAME
            assert mode == "overwrite"
            self.table = FakeTable(data)
            return self.table

    fake_db = FakeDb()
    load_calls = {"embeddings": 0}
    monkeypatch.setattr(
        "mcrs.lancedb.indexing.load_track_metadata_rows",
        lambda *args, **kwargs: [metadata_row],
    )

    def fake_load_embeddings(*args, **kwargs):
        load_calls["embeddings"] += 1
        return [embedding_row]

    monkeypatch.setattr("mcrs.lancedb.indexing.load_track_embedding_rows", fake_load_embeddings)
    monkeypatch.setattr("mcrs.lancedb.indexing.connect_lancedb", lambda _: fake_db)

    summary = build_track_lancedb_table(db_uri=str(tmp_path / "lancedb"), drop_existing=True)

    assert summary.include_embeddings is True
    assert summary.inserted_rows == 1
    assert load_calls["embeddings"] == 1
    assert fake_db.table is not None
    assert fake_db.table.optimized is True
    row = fake_db.table.rows[0]
    assert row["audio_laion_clap"] == pytest.approx([0.1, 0.2])
    assert row["metadata_qwen3_embedding_0_6b"] == pytest.approx([1.1, 1.2])
    assert row["has_audio_laion_clap"] is True


def test_lancedb_indexing_notebook_delegates_to_checked_in_entrypoints():
    notebook_path = Path("notebooks/05_lancedb_indexing.ipynb")
    notebook = json.loads(notebook_path.read_text())
    source = "\n".join("".join(cell.get("source", [])) for cell in notebook["cells"])

    assert "scripts/build_lancedb_index.py" in source
    assert "modal/app.py::upload_lancedb_index" in source
    assert "scripts/smoke_lancedb_modal_query.py" in source
    assert "--metadata-only" in source
    assert "build_track_lancedb_table" not in source
