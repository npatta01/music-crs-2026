"""LanceDB indexing must store release_date as pyarrow date32, with empty -> null."""
from datetime import date

import pyarrow as pa
import lancedb

from mcrs.lancedb.indexing import build_track_record, build_track_lancedb_table


def _minimal_metadata_row(track_id: str, release_date: str | None) -> dict:
    """Build a minimal valid metadata row for build_track_record."""
    return {
        "track_id": track_id,
        "release_date": release_date,
        "track_name": ["X"], "artist_name": ["A"], "artist_id": ["a"],
        "album_name": ["X"], "album_id": ["x"], "tag_list": [],
        "popularity": 0.5, "duration": 200,
    }


def test_build_track_record_full_iso_becomes_date_object():
    rec = build_track_record(_minimal_metadata_row("t1", "2016-03-08"), include_embeddings=False)
    assert rec["release_date"] == date(2016, 3, 8)


def test_build_track_record_empty_string_becomes_none():
    rec = build_track_record(_minimal_metadata_row("t2", ""), include_embeddings=False)
    assert rec["release_date"] is None


def test_build_track_record_none_becomes_none():
    rec = build_track_record(_minimal_metadata_row("t3", None), include_embeddings=False)
    assert rec["release_date"] is None


def test_build_track_record_malformed_becomes_none():
    rec = build_track_record(_minimal_metadata_row("t4", "January 2010"), include_embeddings=False)
    assert rec["release_date"] is None


def test_build_track_record_year_only_becomes_none_or_jan1():
    """LanceDB indexing should not silently 'guess' a year-only date — it's a malformed
    catalog value. Return None so the row is excluded from date filters."""
    rec = build_track_record(_minimal_metadata_row("t5", "2010"), include_embeddings=False)
    assert rec["release_date"] is None


def test_lancedb_table_schema_has_date32_release_date(tmp_path):
    """Write a tiny table via lancedb directly using the same dict shape build_track_record
    produces, and verify pyarrow infers date32 for release_date."""
    db = lancedb.connect(str(tmp_path))
    rows = [
        build_track_record(_minimal_metadata_row("t1", "2016-03-08"), include_embeddings=False),
        build_track_record(_minimal_metadata_row("t2", ""), include_embeddings=False),
    ]
    tbl = db.create_table("t", data=rows)
    rd = tbl.schema.field("release_date")
    assert pa.types.is_date32(rd.type), f"expected date32, got {rd.type}"
