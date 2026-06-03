from __future__ import annotations

from mcrs.bakeoff.track_lookup import TrackMetadataLookup


def _rows():
    return [
        {"track_id": "t1", "track_name": ["Buena"], "artist_name": ["Morphine"],
         "album_name": ["Yes"], "tag_list": ["smoky", "lounge"]},
        {"track_id": "t2", "track_name": ["Cure for Pain"], "artist_name": ["Morphine"],
         "album_name": ["Cure for Pain"], "tag_list": []},
    ]


def test_id_to_metadata_formats_known_track():
    lk = TrackMetadataLookup.from_rows(_rows())
    s = lk.id_to_metadata("t1")
    assert "Buena" in s and "Morphine" in s and "Yes" in s and "smoky" in s


def test_id_to_metadata_unknown_track_returns_placeholder():
    lk = TrackMetadataLookup.from_rows(_rows())
    assert lk.id_to_metadata("nope") == "track=nope"


def test_id_to_metadata_handles_empty_tags():
    lk = TrackMetadataLookup.from_rows(_rows())
    s = lk.id_to_metadata("t2")
    assert "Cure for Pain" in s and "Morphine" in s
