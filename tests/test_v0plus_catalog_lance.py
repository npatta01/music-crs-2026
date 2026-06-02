"""LanceDbCatalog implements CompilerCatalog backed by a LanceDB table."""
from datetime import date

import pytest
import pyarrow as pa
import lancedb

from mcrs.conversation_state.schema import HardFilter
from mcrs.qu_modules.v0plus_catalog_lance import LanceDbCatalog


def _build_fixture_table(path):
    """Build a tiny in-memory LanceDB table that matches the production schema shape
    (just the columns LanceDbCatalog reads — no embeddings here, that's Task 5)."""
    db = lancedb.connect(str(path))
    rows = [
        {"track_id": "t-old",  "release_date": date(1985, 6, 12), "popularity": 0.1,
         "track_name": ["Old"],  "artist_name": ["Alice"], "artist_id": ["a1"],
         "album_name": ["A1"], "album_id": ["x1"], "tag_list": ["rock"]},
        {"track_id": "t-in",   "release_date": date(2010, 3, 8),  "popularity": 0.9,
         "track_name": ["In"],   "artist_name": ["Alice"], "artist_id": ["a1"],
         "album_name": ["A2"], "album_id": ["x2"], "tag_list": ["pop"]},
        {"track_id": "t-new",  "release_date": date(2020, 1, 1),  "popularity": 0.5,
         "track_name": ["New"],  "artist_name": ["Bob"],   "artist_id": ["b1"],
         "album_name": ["B1"], "album_id": ["y1"], "tag_list": ["jazz", "pop"]},
        {"track_id": "t-null", "release_date": None,             "popularity": 0.0,
         "track_name": ["Null"], "artist_name": ["Carol"], "artist_id": ["c1"],
         "album_name": ["C1"], "album_id": ["z1"], "tag_list": []},
    ]
    db.create_table("music_track_catalog", data=rows)


def test_loads_artist_and_track_names(tmp_path):
    _build_fixture_table(tmp_path)
    cat = LanceDbCatalog(db_uri=str(tmp_path), table_name="music_track_catalog")
    assert set(cat.artist_names) == {"Alice", "Bob", "Carol"}
    assert set(cat.track_names) == {"Old", "In", "New", "Null"}


def test_artist_and_track_names_are_sorted_alphabetically(tmp_path):
    _build_fixture_table(tmp_path)
    cat = LanceDbCatalog(db_uri=str(tmp_path), table_name="music_track_catalog")
    assert cat.artist_names == ["Alice", "Bob", "Carol"]
    assert cat.track_names == ["In", "New", "Null", "Old"]


def test_release_date_filter_mask_handles_malformed_hf_gracefully(tmp_path):
    """Defensive: bypass Pydantic and pass a malformed HardFilter — should not crash."""
    _build_fixture_table(tmp_path)
    cat = LanceDbCatalog(db_uri=str(tmp_path), table_name="music_track_catalog")
    bogus = HardFilter.model_construct(field="release_date", op="<", start=None, end=None)
    assert cat.release_date_filter_mask(bogus) == set()


def test_artist_id_of_name(tmp_path):
    _build_fixture_table(tmp_path)
    cat = LanceDbCatalog(db_uri=str(tmp_path), table_name="music_track_catalog")
    assert cat.artist_id_of_name("Alice") == "a1"
    assert cat.artist_id_of_name("Missing") is None


def test_track_id_of_name(tmp_path):
    _build_fixture_table(tmp_path)
    cat = LanceDbCatalog(db_uri=str(tmp_path), table_name="music_track_catalog")
    assert cat.track_id_of_name("In") == "t-in"
    assert cat.track_id_of_name("Missing") is None


def test_artist_id_of_track(tmp_path):
    _build_fixture_table(tmp_path)
    cat = LanceDbCatalog(db_uri=str(tmp_path), table_name="music_track_catalog")
    assert cat.artist_id_of("t-in") == "a1"
    assert cat.artist_id_of("missing") is None


def test_tracks_by_artist_id(tmp_path):
    _build_fixture_table(tmp_path)
    cat = LanceDbCatalog(db_uri=str(tmp_path), table_name="music_track_catalog")
    assert set(cat.tracks_by_artist_id("a1")) == {"t-old", "t-in"}
    assert cat.tracks_by_artist_id("missing") == []


def test_tag_list(tmp_path):
    _build_fixture_table(tmp_path)
    cat = LanceDbCatalog(db_uri=str(tmp_path), table_name="music_track_catalog")
    assert cat.tag_list("t-new") == ["jazz", "pop"]
    assert cat.tag_list("t-null") == []
    assert cat.tag_list("missing") == []


def test_release_date_filter_between(tmp_path):
    _build_fixture_table(tmp_path)
    cat = LanceDbCatalog(db_uri=str(tmp_path), table_name="music_track_catalog")
    hf = HardFilter(field="release_date", op="between", start="2000", end="2015")
    assert cat.release_date_filter_mask(hf) == {"t-in"}


def test_release_date_filter_lt(tmp_path):
    _build_fixture_table(tmp_path)
    cat = LanceDbCatalog(db_uri=str(tmp_path), table_name="music_track_catalog")
    hf = HardFilter(field="release_date", op="<", end="2000-01-01")
    assert cat.release_date_filter_mask(hf) == {"t-old"}


def test_release_date_filter_gt(tmp_path):
    _build_fixture_table(tmp_path)
    cat = LanceDbCatalog(db_uri=str(tmp_path), table_name="music_track_catalog")
    hf = HardFilter(field="release_date", op=">", start="2015-01-01")
    assert cat.release_date_filter_mask(hf) == {"t-new"}


def test_release_date_filter_excludes_null(tmp_path):
    _build_fixture_table(tmp_path)
    cat = LanceDbCatalog(db_uri=str(tmp_path), table_name="music_track_catalog")
    hf = HardFilter(field="release_date", op="between", start="1900", end="2100")
    mask = cat.release_date_filter_mask(hf)
    assert "t-null" not in mask
    assert {"t-old", "t-in", "t-new"} == mask


def test_all_track_ids(tmp_path):
    _build_fixture_table(tmp_path)
    cat = LanceDbCatalog(db_uri=str(tmp_path), table_name="music_track_catalog")
    assert set(cat.all_track_ids()) == {"t-old", "t-in", "t-new", "t-null"}


def test_popularity_sorted(tmp_path):
    _build_fixture_table(tmp_path)
    cat = LanceDbCatalog(db_uri=str(tmp_path), table_name="music_track_catalog")
    # 0.9 (t-in), 0.5 (t-new), 0.1 (t-old), 0.0 (t-null) — desc
    assert cat.popularity_sorted_track_ids() == ["t-in", "t-new", "t-old", "t-null"]


def test_vector_returns_none_when_column_missing(tmp_path):
    _build_fixture_table(tmp_path)
    cat = LanceDbCatalog(db_uri=str(tmp_path), table_name="music_track_catalog")
    assert cat.vector("t-in", "nonexistent_field") is None


def test_vector_returns_eager_loaded_embedding(tmp_path):
    """When eager_vector_fields includes a vector column, vector() reads from
    the in-memory cache (no per-call LanceDB query) and returns the embedding."""
    import lancedb
    import pyarrow as pa
    from datetime import date

    db = lancedb.connect(str(tmp_path))
    rows = [
        {"track_id": "t1",
         "metadata_qwen3_embedding_0_6b": [0.1, 0.2, 0.3, 0.4],
         "has_metadata_qwen3_embedding_0_6b": True,
         "release_date": date(2020, 1, 1), "popularity": 0.0,
         "track_name": ["X"], "artist_name": ["A"], "artist_id": ["a"],
         "album_name": ["Y"], "album_id": ["y"], "tag_list": []},
        {"track_id": "t2",
         "metadata_qwen3_embedding_0_6b": [0.0, 0.0, 0.0, 0.0],
         "has_metadata_qwen3_embedding_0_6b": False,
         "release_date": date(2020, 1, 1), "popularity": 0.0,
         "track_name": ["Y"], "artist_name": ["B"], "artist_id": ["b"],
         "album_name": ["Y"], "album_id": ["y"], "tag_list": []},
    ]
    schema = pa.schema([
        pa.field("track_id", pa.string()),
        pa.field("metadata_qwen3_embedding_0_6b", pa.list_(pa.float32(), 4)),
        pa.field("has_metadata_qwen3_embedding_0_6b", pa.bool_()),
        pa.field("release_date", pa.date32()),
        pa.field("popularity", pa.float64()),
        pa.field("track_name", pa.list_(pa.string())),
        pa.field("artist_name", pa.list_(pa.string())),
        pa.field("artist_id", pa.list_(pa.string())),
        pa.field("album_name", pa.list_(pa.string())),
        pa.field("album_id", pa.list_(pa.string())),
        pa.field("tag_list", pa.list_(pa.string())),
    ])
    db.create_table("music_track_catalog", data=rows, schema=schema)

    cat = LanceDbCatalog(
        db_uri=str(tmp_path),
        table_name="music_track_catalog",
        eager_vector_fields=("metadata_qwen3_embedding_0_6b",),
    )

    # Happy path: has_metadata flag True, vector loaded
    v = cat.metadata_vector("t1")
    assert v is not None
    assert v == pytest.approx([0.1, 0.2, 0.3, 0.4])

    # has_metadata=False -> vector() returns None even though row exists
    assert cat.metadata_vector("t2") is None

    # Unknown track_id -> None
    assert cat.metadata_vector("missing") is None


def test_vector_falls_back_to_lance_query_when_not_eager(tmp_path):
    """When eager_vector_fields is empty (default), vector() still works via
    on-demand LanceDB query. Verifies the cold-path behavior we already have."""
    _build_fixture_table(tmp_path)
    cat = LanceDbCatalog(
        db_uri=str(tmp_path),
        table_name="music_track_catalog",
    )
    # Fixture has no vector columns at all
    assert cat.vector("t-in", "nonexistent_field") is None


def test_multi_artist_tracks_are_indexed_under_all_credited_artists(tmp_path):
    """A collaboration track must be discoverable via either artist name AND must
    appear in tracks_by_artist_id for every credited artist_id. Earlier versions
    of LanceDbCatalog only indexed _first(artist_name) / _first(artist_id), which
    silently dropped collaborations from resolver fuzzy match + explicit-rejection
    hard-exclude (parity gap vs HFTalkPlayCatalog). Regression guard."""
    db = lancedb.connect(str(tmp_path))
    rows = [
        # Solo track by Alice
        {"track_id": "t-solo",  "release_date": date(2010, 1, 1), "popularity": 0.5,
         "track_name": ["Solo"], "artist_name": ["Alice"], "artist_id": ["a1"],
         "album_name": ["X"], "album_id": ["x1"], "tag_list": []},
        # Collab credited to BOTH Alice and Bob
        {"track_id": "t-collab", "release_date": date(2012, 1, 1), "popularity": 0.5,
         "track_name": ["Collab"], "artist_name": ["Alice", "Bob"], "artist_id": ["a1", "b1"],
         "album_name": ["Y"], "album_id": ["y1"], "tag_list": []},
        # Solo track by Bob
        {"track_id": "t-bob",   "release_date": date(2014, 1, 1), "popularity": 0.5,
         "track_name": ["BobSong"], "artist_name": ["Bob"], "artist_id": ["b1"],
         "album_name": ["Z"], "album_id": ["z1"], "tag_list": []},
    ]
    db.create_table("music_track_catalog", data=rows)
    cat = LanceDbCatalog(db_uri=str(tmp_path), table_name="music_track_catalog")

    # Both artists are known
    assert set(cat.artist_names) == {"Alice", "Bob"}
    # Name → id resolution works for either credited artist
    assert cat.artist_id_of_name("Alice") == "a1"
    assert cat.artist_id_of_name("Bob") == "b1"
    # The collab shows up under BOTH artists' track lists
    assert set(cat.tracks_by_artist_id("a1")) == {"t-solo", "t-collab"}
    assert set(cat.tracks_by_artist_id("b1")) == {"t-collab", "t-bob"}
