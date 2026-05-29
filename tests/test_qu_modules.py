from mcrs.qu_modules.base import PassthroughQU


def test_passthrough_qu_drops_track_id_line_from_music_metadata():
    query = PassthroughQU().transform_query(
        [
            {"role": "user", "content": "more like this"},
            {
                "role": "music",
                "content": (
                    "track_id: t-1\n"
                    "track_name: With Rainy Eyes\n"
                    "artist_name: Emancipator\n"
                ),
            },
        ]
    )

    assert "track_id: t-1" not in query
    assert "track_name: With Rainy Eyes" in query
    assert "artist_name: Emancipator" in query


def test_passthrough_qu_keeps_raw_music_track_id():
    query = PassthroughQU().transform_query(
        [
            {"role": "music", "content": "t-1"},
        ]
    )

    assert query == "assistant: t-1"
