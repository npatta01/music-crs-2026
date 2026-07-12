"""Unit tests for the tiered phrase -> catalog-tag resolver."""

import math

import pytest

from mcrs.qu_modules.tag_resolver import (
    TIER_ALIAS,
    TIER_EMBEDDING,
    TIER_EXACT,
    TIER_SUBSTRING,
    TagEmbeddingIndex,
    TieredTagResolver,
    catalog_tag_key,
    filtered_tag_vocab,
)

VOCAB = frozenset(
    {
        "rock",
        "alternative rock",
        "post hardcore",
        "emo",
        "electronic",
        "vaporwave",
        "death metal",
        "technical death metal",
    }
)

ALIASES = {
    "alt rock": ("alternative rock",),
    "edm": ("electronic",),
}


def make_resolver(**kwargs) -> TieredTagResolver:
    defaults = dict(catalog_tag_keys=VOCAB, aliases=ALIASES)
    defaults.update(kwargs)
    return TieredTagResolver(**defaults)


def test_normalizer_matches_compiler():
    from mcrs.qu_modules.compiler import V0PlusCompiler

    for value in ("Post-Hardcore", "R&B / Soul", "  Alt  Rock ", "EDM!!!"):
        assert catalog_tag_key(value) == V0PlusCompiler._catalog_tag_key(value)


def test_exact_tier():
    res = make_resolver().resolve("Post-Hardcore")
    assert res.resolved
    assert res.matches[0].tag == "post hardcore"
    assert res.matches[0].tier == TIER_EXACT
    assert res.matches[0].score == 1.0


def test_alias_tier():
    res = make_resolver().resolve("alt rock")
    assert res.resolved
    assert res.matches[0].tag == "alternative rock"
    assert res.matches[0].tier == TIER_ALIAS
    assert res.matches[0].score == pytest.approx(0.9)


def test_substring_tier_decomposes_phrase():
    res = make_resolver().resolve("intense emotional alternative rock")
    assert res.resolved
    tags = res.tags()
    assert "alternative rock" in tags
    assert "rock" in tags
    by_tag = {m.tag: m for m in res.matches}
    assert by_tag["alternative rock"].tier == TIER_SUBSTRING
    # specific (longer) tag ordered before generic one within the tier
    assert tags.index("alternative rock") < tags.index("rock")


def test_substring_requires_word_boundary():
    # "rock" must not match inside "rockabilly-ish" as a substring fragment
    res = make_resolver().resolve("hardrock")
    assert "rock" not in res.tags()


def test_unresolved_phrase_reports_fallback():
    res = make_resolver().resolve("songs about late night drives")
    assert not res.resolved
    assert res.matches == ()


def test_embedding_tier_fires_only_when_lexical_misses():
    calls: list[list[str]] = []

    def embed_fn(texts):
        calls.append(texts)
        return [[1.0, 0.0]]

    index = TagEmbeddingIndex(
        tags=["vaporwave", "death metal"],
        vectors=[[0.96, 0.28], [0.0, 1.0]],
    )
    resolver = make_resolver(
        embedding_index=index, embed_fn=embed_fn, embedding_min_score=0.6
    )

    res = resolver.resolve("dreamy mall nostalgia music")
    assert res.resolved
    assert res.matches[0].tag == "vaporwave"
    assert res.matches[0].tier == TIER_EMBEDDING
    assert res.matches[0].score == pytest.approx(0.96, abs=1e-4)
    assert "death metal" not in res.tags()  # below threshold

    # lexical hit -> embedding must not be called
    resolver.resolve("alternative rock")
    assert len(calls) == 1


def test_embedding_threshold_gates_resolution():
    index = TagEmbeddingIndex(tags=["vaporwave"], vectors=[[1.0, 0.0]])
    resolver = make_resolver(
        embedding_index=index,
        embed_fn=lambda texts: [[0.0, 1.0]],  # orthogonal -> cosine 0
        embedding_min_score=0.6,
    )
    res = resolver.resolve("nothing similar at all")
    assert not res.resolved


def test_max_matches_cap():
    resolver = make_resolver(max_matches=1)
    res = resolver.resolve("technical death metal")
    assert len(res.matches) == 1
    assert res.matches[0].tag == "technical death metal"


def test_resolution_cached_per_normalized_phrase():
    resolver = make_resolver()
    first = resolver.resolve("Alt Rock")
    second = resolver.resolve("alt   rock!")
    assert first is second


def test_embedding_index_roundtrip(tmp_path):
    index = TagEmbeddingIndex(
        tags=["rock", "emo"], vectors=[[3.0, 4.0], [0.0, 2.0]]
    )
    path = tmp_path / "tags.npz"
    index.save(path)
    loaded = TagEmbeddingIndex.load(path)
    assert loaded.tags == ["rock", "emo"]
    # rows are L2-normalized on construction
    assert math.isclose(float((loaded.matrix[0] ** 2).sum()) ** 0.5, 1.0, rel_tol=1e-5)
    top = loaded.topk([3.0, 4.0], k=1)
    assert top[0][0] == "rock"
    assert top[0][1] == pytest.approx(1.0, abs=1e-5)


def test_filtered_tag_vocab_drops_singletons():
    df = {"rock": 25000, "weird-singleton": 1, "niche": 5}
    vocab = filtered_tag_vocab(df, min_track_count=5)
    assert vocab == frozenset({"rock", "niche"})
