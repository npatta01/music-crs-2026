from mcrs.qu_modules.fuzzy_matcher import RapidfuzzCatalogMatcher
from tests.v0plus_fakes import DictCatalog


def test_track_match_prefers_full_title_over_short_subset_tie():
    catalog = DictCatalog(
        tracks={
            "t-bad": {
                "artist_id": "a-jason",
                "artist_name": "Jason Aldean",
                "track_name": "Bad",
                "tag_list": ["country"],
                "popularity": 85.0,
                "release_date": "2009-01-01",
            },
            "t-johnny": {
                "artist_id": "a-sublime",
                "artist_name": "Sublime",
                "track_name": "Johnny Too Bad Freestyle - Rarities Version",
                "tag_list": ["ska punk"],
                "popularity": 45.0,
                "release_date": "2006-01-01",
            },
        }
    )

    matches = RapidfuzzCatalogMatcher(catalog).match(
        "Johnny Too Bad Freestyle - Rarities Version",
        "track",
        topk=2,
        score_cutoff=80,
    )

    assert matches[0][0] == "t-johnny"
