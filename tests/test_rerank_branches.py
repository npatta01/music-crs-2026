"""Tests for the reranker branch registry name canonicalisation.

A silent miss here would route a branch's rank/score into the wrong (or no) feature column,
so it is covered explicitly against the live trace pool names and encoder-size variants.
"""

from mcrs.rerank.branches import BRANCH_KEYS, GROUPS, canonical_branch_key


def test_live_devset_pool_names_map_to_canonical_keys():
    # The exact 11 pool names observed in v0plus_compiler_all_retrievers_devset.
    expected = {
        "bm25": "bm25",
        "dense.default.intent.metadata_qwen3_embedding_0_6b": "dense.metadata_qwen3",
        "dense.default.attributes.attributes_qwen3_embedding_0_6b": "dense.attributes_qwen3",
        "dense.default.lyric.lyrics_qwen3_embedding_0_6b": "dense.lyrics_qwen3",
        "dense.clap_text.sonic.audio_laion_clap": "dense.clap_text.sonic",
        "centroid.anchor_tracks.image_siglip2": "centroid.image_siglip2",
        "centroid.anchor_tracks.audio_laion_clap": "centroid.audio_clap",
        "centroid.anchor_tracks.cf_bpr": "centroid.cf_bpr",
        "centroid.user.cf_bpr": "centroid.user.cf_bpr",
        "lookup.resolved_artist_discography": "lookup.resolved_artist_discography",
        "lookup.era_popularity": "lookup.era_popularity",
    }
    for raw, key in expected.items():
        assert canonical_branch_key(raw) == key, raw
    # every canonical key is reachable and the set is exactly the 11 registry keys
    assert set(expected.values()) == set(BRANCH_KEYS)


def test_encoder_size_variants_collapse_to_same_key():
    assert canonical_branch_key("dense.default.intent.metadata_qwen3_embedding_8b") == "dense.metadata_qwen3"
    assert canonical_branch_key("dense.default.attributes.attributes_qwen3_embedding_4b") == "dense.attributes_qwen3"


def test_anchor_vs_user_cf_bpr_disambiguation():
    assert canonical_branch_key("centroid.anchor_tracks.cf_bpr") == "centroid.cf_bpr"
    assert canonical_branch_key("centroid.user.cf_bpr") == "centroid.user.cf_bpr"


def test_unknown_pool_names_return_none():
    assert canonical_branch_key("dense.something.brand_new_field") is None
    assert canonical_branch_key("totally_unknown") is None
    assert canonical_branch_key("") is None


def test_group_tags_partition_all_branches():
    from mcrs.rerank.branches import BRANCH_BY_KEY
    assert {b.group for b in BRANCH_BY_KEY.values()} == set(GROUPS)
