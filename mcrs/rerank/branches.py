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


# --- Block H: dense cross-scoring (issue #93 follow-up) -----------------------------------
# A per-candidate cosine to the turn's actual query/centroid vector in each modality, for
# EVERY union candidate -- a DENSE relevance signal that fills the sparse per-branch NaNs
# (a candidate only gets a branch's rank/score if that branch surfaced it). The compiler
# captures each branch's query vector (CompilerConfig.capture_branch_query_vectors); these
# specs map a stable feature suffix -> (catalog vector field, branch kind, centroid source)
# so features.py can find the right captured query vector and the right candidate vectors.

@dataclass(frozen=True)
class CrossScoreSpec:
    name: str           # feature suffix -> column h__xcos_{name}
    vector_field: str   # catalog vector field for the candidate side
    kind: str           # "dense" | "centroid" (which branch family captured the query vector)
    source: str | None  # centroid source ("anchor_tracks" | "user"); None for dense


CROSS_SCORE_SPECS: tuple[CrossScoreSpec, ...] = (
    CrossScoreSpec("metadata_qwen3", "metadata_qwen3_embedding_0_6b", "dense", None),
    CrossScoreSpec("attributes_qwen3", "attributes_qwen3_embedding_0_6b", "dense", None),
    CrossScoreSpec("clap_text", "audio_laion_clap", "dense", None),
    CrossScoreSpec("audio_anchor", "audio_laion_clap", "centroid", "anchor_tracks"),
    CrossScoreSpec("image_anchor", "image_siglip2", "centroid", "anchor_tracks"),
    CrossScoreSpec("cf_bpr_anchor", "cf_bpr", "centroid", "anchor_tracks"),
    CrossScoreSpec("cf_bpr_user", "cf_bpr", "centroid", "user"),
)


def xcos_col(name: str) -> str:
    return f"h__xcos_{name}"


CROSS_SCORE_COLS: tuple[str, ...] = tuple(xcos_col(s.name) for s in CROSS_SCORE_SPECS)


def parse_branch_name(name: str) -> tuple[str | None, str | None, str | None]:
    """Raw branch-trace pool name -> (kind, centroid_source, vector_field).

    ``dense.{encoder_id}.{query_id}.{vector_field}`` -> ("dense", None, vector_field)
    ``centroid.{source}.{vector_field}``             -> ("centroid", source, vector_field)
    Anything else -> (None, None, None).
    """
    parts = name.split(".")
    if parts and parts[0] == "dense" and len(parts) >= 2:
        return ("dense", None, parts[-1])
    if parts and parts[0] == "centroid" and len(parts) >= 3:
        return ("centroid", parts[1], ".".join(parts[2:]))
    return (None, None, None)
