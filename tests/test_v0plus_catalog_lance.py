"""LanceDbCatalog implements CompilerCatalog backed by a LanceDB table."""
from datetime import date

import pytest
import pyarrow as pa
import lancedb

from experiments.analysis.conversation_state_extraction_bakeoff.schema import HardFilter
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
