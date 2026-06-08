"""Canonical branch registry for the v0+ reranker.

The branch-trace JSON records each retriever pool under a *long* name whose exact
spelling depends on the encoder id / query id / vector field (e.g.
``dense.default.intent.metadata_qwen3_embedding_0_6b``). The reranker needs **stable**
feature-column prefixes that are independent of those incidental tokens, so this module
is the single source of truth mapping raw pool names -> 11 canonical branch keys, their
signal group, and the monotone-trust direction of each branch's raw score.

Verified against the live ``v0plus_compiler_all_retrievers_devset`` trace (the 11 pool
names that appear; see ``mcrs/qu_modules/compiler_v0plus.py`` branch-name builders).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Branch:
    """One canonical retriever branch.

    Attributes:
        key: stable short feature prefix (used for ``{key}_rank`` / ``{key}_score`` / ...).
        group: signal family -- ``"lexical"`` | ``"content"`` | ``"behavioral"``.
        score_monotone: monotone constraint for ``{key}_score`` in LightGBM
            (+1 = higher score is more relevant; 0 = unconstrained). Cosine / BM25 scores
            are trustworthy-increasing; ``lookup.*`` scores are inverted popularity rank
            and are left unconstrained (popularity is SHAP-gated, not assumed monotone).
    """

    key: str
    group: str
    score_monotone: int


# Canonical branches, in a stable column order. Keys mirror the issue's catalog (§A).
BRANCHES: tuple[Branch, ...] = (
    Branch("bm25", "lexical", +1),
    Branch("dense.metadata_qwen3", "content", +1),
    Branch("dense.attributes_qwen3", "content", +1),
    Branch("dense.lyrics_qwen3", "content", +1),
    Branch("dense.clap_text.sonic", "content", +1),
    Branch("centroid.image_siglip2", "content", +1),
    Branch("centroid.audio_clap", "content", +1),
    Branch("centroid.cf_bpr", "behavioral", +1),
    Branch("centroid.user.cf_bpr", "behavioral", +1),
    Branch("lookup.resolved_artist_discography", "lexical", 0),
    Branch("lookup.era_popularity", "lexical", 0),
)

BRANCH_KEYS: tuple[str, ...] = tuple(b.key for b in BRANCHES)
BRANCH_BY_KEY: dict[str, Branch] = {b.key: b for b in BRANCHES}
GROUPS: tuple[str, ...] = ("lexical", "content", "behavioral")


def _canonical_branch_key(pool_name: str) -> str | None:
    """Map a raw branch-trace pool name to its canonical key, or None if unknown.

    Matching is token-based and tolerant of encoder-size variants (``_0_6b`` vs ``_8b``)
    and ``query_id`` differences, so a config change that swaps the 0.6B encoder for the
    8B one keeps landing in the same ``dense.metadata_qwen3`` column.
    """

    name = pool_name.lower()

    if name == "bm25":
        return "bm25"
    if name.startswith("lookup."):
        if "discography" in name:
            return "lookup.resolved_artist_discography"
        if "era_popularity" in name or "era" in name:
            return "lookup.era_popularity"
        return None
    if name.startswith("dense."):
        if "metadata_qwen3" in name:
            return "dense.metadata_qwen3"
        if "attributes_qwen3" in name:
            return "dense.attributes_qwen3"
        if "lyrics_qwen3" in name or "lyric" in name:
            return "dense.lyrics_qwen3"
        if "clap" in name:
            return "dense.clap_text.sonic"
        return None
    if name.startswith("centroid."):
        if "image_siglip2" in name or "siglip" in name:
            return "centroid.image_siglip2"
        if "cf_bpr" in name:
            return "centroid.user.cf_bpr" if "user" in name else "centroid.cf_bpr"
        if "audio_laion_clap" in name or "clap" in name or "audio" in name:
            return "centroid.audio_clap"
        return None
    return None


def canonical_branch_key(pool_name: str) -> str | None:
    """Public wrapper around :func:`_canonical_branch_key`."""

    return _canonical_branch_key(pool_name)


# --- feature-column name helpers (single source of truth for column spelling) ---

def rank_col(key: str) -> str:
    return f"{key}__rank"


def norm_rank_col(key: str) -> str:
    return f"{key}__norm_rank"


def score_col(key: str) -> str:
    return f"{key}__score"


def hit_col(key: str) -> str:
    return f"{key}__hit"


def score_gap_col(key: str) -> str:
    return f"{key}__score_gap_to_top"


def score_ratio_col(key: str) -> str:
    return f"{key}__score_ratio_to_top"


# Raw per-candidate columns emitted by build_dataset (rank + score only; everything else
# is derived in features.py). pool_depth / top_score are carried per group.
def raw_rank_col(key: str) -> str:
    return f"raw__{key}__rank"


def raw_score_col(key: str) -> str:
    return f"raw__{key}__score"
