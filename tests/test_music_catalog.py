"""Unit tests for MusicCatalogDB.id_to_metadata.

These tests instantiate MusicCatalogDB via __new__ to bypass the HuggingFace
dataset load in __init__ — the function under test only reads metadata_dict
and corpus_types, both of which we set directly.
"""

from __future__ import annotations

from mcrs.db_item import MusicCatalogDB


def _bare_db(metadata_dict: dict, corpus_types: list[str]) -> MusicCatalogDB:
    db = MusicCatalogDB.__new__(MusicCatalogDB)
    db.metadata_dict = metadata_dict
    db.corpus_types = corpus_types
    return db


def test_id_to_metadata_keeps_string_release_date_intact():
    """Per docs/data.md, release_date is `str` (e.g. '2006-12-06'), not a list.
    Treating it as a list character-tokenizes the date — bug. The function must
    pass scalar string fields through unchanged."""
    track = {
        "track_id": "t-1",
        "track_name": ["With Rainy Eyes"],
        "artist_name": ["Emancipator"],
        "release_date": "2006-12-06",
    }
    db = _bare_db(
        metadata_dict={"t-1": track},
        corpus_types=["track_name", "artist_name", "release_date"],
    )

    out = db.id_to_metadata("t-1")

    assert out == (
        "track_id: t-1\n"
        "track_name: With Rainy Eyes\n"
        "artist_name: Emancipator\n"
        "release_date: 2006-12-06\n"
    )
    # The buggy version produces "2, 0, 0, 6, -, 1, 2, -, 0, 6"
    assert "2, 0, 0, 6" not in out


def test_id_to_metadata_joins_list_fields():
    track = {
        "track_id": "t-2",
        "track_name": ["Abbey Road"],
        "artist_name": ["The Beatles", "John Lennon"],
    }
    db = _bare_db(
        metadata_dict={"t-2": track},
        corpus_types=["track_name", "artist_name"],
    )

    out = db.id_to_metadata("t-2")

    assert out == (
        "track_id: t-2\n"
        "track_name: Abbey Road\n"
        "artist_name: The Beatles, John Lennon\n"
    )
