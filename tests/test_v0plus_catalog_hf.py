"""Unit tests for HFTalkPlayCatalog. Uses synthetic rows — no HF fetch."""

from __future__ import annotations

from mcrs.conversation_state.schema import (
    HardFilter,
)
from mcrs.qu_modules.v0plus_catalog import CompilerCatalog
from mcrs.qu_modules.v0plus_catalog_hf import (
    DEFAULT_VECTOR_COLUMN,
    HFTalkPlayCatalog,
)


def _metadata_rows():
    """Mirrors the real `TalkPlayData-Challenge-Track-Metadata` schema:
    list[str] for name/id columns, scalar float for popularity, str for
    release_date."""
    return [
        {
            "track_id": "t-morphine-1",
            "track_name": ["Cure for Pain"],
            "artist_name": ["Morphine"],
            "album_name": ["Cure for Pain"],
            "tag_list": ["smoky", "lounge", "low-rock"],
            "popularity": 70.0,
            "release_date": "1993-09-14",
            "artist_id": ["a-morphine"],
            "album_id": ["al-morphine-1"],
        },
        {
            "track_id": "t-morphine-2",
            "track_name": ["Buena"],
            "artist_name": ["Morphine"],
            "album_name": ["Yes"],
            "tag_list": ["smoky", "lounge"],
            "popularity": 55.0,
            "release_date": "1995-02-21",
            "artist_id": ["a-morphine"],
            "album_id": ["al-morphine-2"],
        },
        {
            "track_id": "t-fugazi-1",
            "track_name": ["Waiting Room"],
            "artist_name": ["Fugazi"],
            "album_name": ["13 Songs"],
            "tag_list": ["post-hardcore", "punk"],
            "popularity": 80.0,
            "release_date": "1988-11-04",
            "artist_id": ["a-fugazi"],
            "album_id": ["al-fugazi-1"],
        },
        {
            "track_id": "t-collab-1",
            "track_name": ["Some Collab"],
            "artist_name": ["Morphine", "Fugazi"],  # multi-artist
            "album_name": ["Compilation"],
            "tag_list": ["weird"],
            "popularity": 10.0,
            "release_date": "2001-01-01",
            "artist_id": ["a-morphine", "a-fugazi"],
            "album_id": ["al-comp"],
        },
        {
            "track_id": "t-noembed-1",
            "track_name": ["No Vector Track"],
            "artist_name": ["NoEmbed"],
            "album_name": ["X"],
            "tag_list": [],
            "popularity": 0.0,
            "release_date": "2020-01-01",
            "artist_id": ["a-noembed"],
            "album_id": ["al-x"],
        },
    ]


def _embedding_rows():
    return [
        {"track_id": "t-morphine-1", DEFAULT_VECTOR_COLUMN: [1.0, 0.0, 0.0]},
        {"track_id": "t-morphine-2", DEFAULT_VECTOR_COLUMN: [0.9, 0.1, 0.0]},
        {"track_id": "t-fugazi-1",   DEFAULT_VECTOR_COLUMN: [0.0, 1.0, 0.0]},
        {"track_id": "t-collab-1",   DEFAULT_VECTOR_COLUMN: [0.5, 0.5, 0.0]},
        # t-noembed-1 deliberately missing — covers the "empty vector" path
    ]


def _catalog() -> HFTalkPlayCatalog:
    return HFTalkPlayCatalog.from_rows(
        metadata_rows=_metadata_rows(),
        embedding_rows=_embedding_rows(),
    )


def test_hf_catalog_satisfies_compiler_catalog_protocol():
    cat = _catalog()
    assert isinstance(cat, CompilerCatalog)


def test_all_track_ids_round_trips_metadata():
    cat = _catalog()
    assert set(cat.all_track_ids()) == {
        "t-morphine-1", "t-morphine-2", "t-fugazi-1", "t-collab-1", "t-noembed-1",
    }


def test_artist_and_track_names_deduped_and_sorted():
    cat = _catalog()
    # Morphine appears in 3 tracks; should be deduped
    assert cat.artist_names == sorted({"Morphine", "Fugazi", "NoEmbed"})
    assert cat.track_names == sorted({
        "Cure for Pain", "Buena", "Waiting Room", "Some Collab", "No Vector Track",
    })


def test_artist_id_of_name_round_trips():
    cat = _catalog()
    assert cat.artist_id_of_name("Morphine") == "a-morphine"
    assert cat.artist_id_of_name("Fugazi") == "a-fugazi"
    assert cat.artist_id_of_name("Nonexistent") is None


def test_track_id_of_name_round_trips():
    cat = _catalog()
    assert cat.track_id_of_name("Waiting Room") == "t-fugazi-1"
    assert cat.track_id_of_name("Nonexistent") is None


def test_artist_id_of_takes_first_when_track_has_multi_artist():
    cat = _catalog()
    # t-collab-1 has [a-morphine, a-fugazi]; first wins for the "primary" role
    assert cat.artist_id_of("t-collab-1") == "a-morphine"
    assert cat.artist_id_of("unknown-tid") is None


def test_tracks_by_artist_id_indexes_all_co_credited_tracks():
    cat = _catalog()
    morphine_tracks = set(cat.tracks_by_artist_id("a-morphine"))
    # Should include both solo Morphine tracks AND the collab
    assert morphine_tracks == {"t-morphine-1", "t-morphine-2", "t-collab-1"}
    fugazi_tracks = set(cat.tracks_by_artist_id("a-fugazi"))
    assert fugazi_tracks == {"t-fugazi-1", "t-collab-1"}


def test_tag_list_lookup():
    cat = _catalog()
    assert cat.tag_list("t-morphine-1") == ["smoky", "lounge", "low-rock"]
    assert cat.tag_list("t-noembed-1") == []
    assert cat.tag_list("unknown-tid") == []


def test_metadata_vector_present_for_indexed_tracks():
    cat = _catalog()
    assert cat.metadata_vector("t-morphine-1") == [1.0, 0.0, 0.0]


def test_metadata_vector_none_when_missing_or_empty():
    cat = _catalog()
    # t-noembed-1 has no embedding row at all
    assert cat.metadata_vector("t-noembed-1") is None
    assert cat.metadata_vector("unknown-tid") is None


def test_metadata_vector_skips_empty_list_rows():
    cat = HFTalkPlayCatalog.from_rows(
        metadata_rows=_metadata_rows(),
        embedding_rows=[
            {"track_id": "t-morphine-1", DEFAULT_VECTOR_COLUMN: []},  # empty
        ],
    )
    assert cat.metadata_vector("t-morphine-1") is None


def test_release_date_between_filter():
    cat = _catalog()
    hf = HardFilter(
        field="release_date", op="between", start="1990-01-01", end="2000-12-31"
    )
    mask = cat.release_date_filter_mask(hf)
    assert mask == {"t-morphine-1", "t-morphine-2"}  # 1988 too old, 2001 too new


def test_release_date_less_than_filter():
    cat = _catalog()
    hf = HardFilter(field="release_date", op="<", end="1990-01-01")
    mask = cat.release_date_filter_mask(hf)
    assert mask == {"t-fugazi-1"}


def test_release_date_greater_than_filter():
    cat = _catalog()
    hf = HardFilter(field="release_date", op=">", start="2000-01-01")
    mask = cat.release_date_filter_mask(hf)
    assert mask == {"t-collab-1", "t-noembed-1"}


def test_release_date_filter_mask_between_yields_dated_tracks():
    from datetime import date  # noqa: F401  (kept for parity with plan)

    rows = [
        {"track_id": "t-old",  "release_date": "1985-06-12", "popularity": 0.0,
         "track_name": ["Old"], "artist_name": ["A"], "artist_id": ["a1"], "album_name": ["X"], "album_id": ["x1"], "tag_list": []},
        {"track_id": "t-in",   "release_date": "2010-03-08", "popularity": 0.0,
         "track_name": ["In"],  "artist_name": ["A"], "artist_id": ["a1"], "album_name": ["X"], "album_id": ["x1"], "tag_list": []},
        {"track_id": "t-new",  "release_date": "2020-01-01", "popularity": 0.0,
         "track_name": ["New"], "artist_name": ["A"], "artist_id": ["a1"], "album_name": ["X"], "album_id": ["x1"], "tag_list": []},
        {"track_id": "t-bad",  "release_date": "",           "popularity": 0.0,
         "track_name": ["Bad"], "artist_name": ["A"], "artist_id": ["a1"], "album_name": ["X"], "album_id": ["x1"], "tag_list": []},
    ]
    catalog = HFTalkPlayCatalog.from_rows(metadata_rows=rows, embedding_rows=[], vector_columns=[])
    hf = HardFilter(field="release_date", op="between", start="2000", end="2015")
    assert catalog.release_date_filter_mask(hf) == {"t-in"}


def test_popularity_sorted_track_ids_orders_by_pop_desc():
    cat = _catalog()
    order = cat.popularity_sorted_track_ids()
    assert order[0] == "t-fugazi-1"   # 80
    assert order[1] == "t-morphine-1"  # 70
    assert order[2] == "t-morphine-2"  # 55
    assert order[-1] == "t-noembed-1"  # 0


def test_works_without_embeddings():
    """Construction without embedding rows should still produce a usable catalog
    for the Resolver / BM25 paths (just no centroid mixing)."""
    cat = HFTalkPlayCatalog.from_rows(metadata_rows=_metadata_rows(), embedding_rows=None)
    assert cat.metadata_vector("t-morphine-1") is None
    # Resolver-facing surface still works
    assert cat.artist_id_of_name("Morphine") == "a-morphine"
    assert cat.tracks_by_artist_id("a-morphine")
