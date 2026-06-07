#!/usr/bin/env python
"""Focused retriever matrix for V1 state projection.

This reuses saved live V1 extraction output, projects it through the current
bridge, and compiles a focused pack through candidate-generation variants.

The goal is to measure branch-pool recall, especially union@20 and union@50.
Those metrics only improve when a branch's own top-k changes, so this script
tests query templates and branch composition separately from RRF/ranker tuning.
"""

from __future__ import annotations

import argparse
import copy
import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from omegaconf import OmegaConf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcrs.conversation_state.schema import (  # noqa: E402
    ConversationStateV1,
    project_v1_to_v0plus,
)
from mcrs.qu_modules.compiler_v0plus import BranchPool  # noqa: E402
from mcrs.qu_modules.compiler_v0plus_qu import build_v0plus_compiler_qu  # noqa: E402


V1_KEYS = {
    "current_request",
    "facts",
    "exclusions",
    "track_feedback",
    "referenced_track_ids",
    "temporal_constraint",
    "lyrical_theme",
}

DEFAULT_ANALYSIS_DIR = Path(
    "experiments/analysis/devset_recall_gap_v0plus_all_retrievers_2026_06_06"
)
DEFAULT_CONFIG = Path("configs/v0plus_compiler_all_retrievers_devset.yaml")
DEFAULT_MAIN_LANCEDB = Path("cache/lancedb")

KS = (20, 50, 100, 200, 1000)


@dataclass(frozen=True)
class DenseSpec:
    vector_field: str
    encoder_id: str
    query_id: str
    weight: float = 1.0
    distance_type: str = "cosine"

    def to_config(self) -> dict[str, Any]:
        return {
            "vector_field": self.vector_field,
            "encoder_id": self.encoder_id,
            "query_id": self.query_id,
            "weight": self.weight,
            "distance_type": self.distance_type,
        }


@dataclass(frozen=True)
class Variant:
    name: str
    dense_branches: tuple[DenseSpec, ...] = ()
    centroid: bool = False
    centroid_fields: tuple[str, ...] = ()
    centroid_weight: float = 1.0
    similar_artist_anchors: bool = False
    similar_artist_intents: tuple[str, ...] = ("open_explore", "pivot", "refinement")
    lookups: bool = True
    discography: bool | None = None
    era_popularity: bool | None = None
    use_base_config: bool = False
    branch_local_rules: tuple[str, ...] = ()


QWEN06_METADATA = "metadata_qwen3_embedding_0_6b"
QWEN06_ATTRIBUTES = "attributes_qwen3_embedding_0_6b"
QWEN8_METADATA = "metadata_qwen3_embedding_8b"
QWEN8_ATTRIBUTES = "attributes_qwen3_embedding_8b"
CLAP_AUDIO = "audio_laion_clap"


VARIANTS: dict[str, Variant] = {
    "current_config": Variant("current_config", use_base_config=True),
    "bm25_only": Variant("bm25_only", lookups=False),
    "bm25_lookup": Variant("bm25_lookup", lookups=True),
    "bm25_discography": Variant(
        "bm25_discography",
        lookups=False,
        discography=True,
    ),
    "bm25_era_popularity": Variant(
        "bm25_era_popularity",
        lookups=False,
        era_popularity=True,
    ),
    "centroid_style": Variant(
        "centroid_style",
        centroid=True,
        similar_artist_anchors=True,
    ),
    "centroid_audio": Variant(
        "centroid_audio",
        centroid=True,
        centroid_fields=(CLAP_AUDIO,),
    ),
    "centroid_image": Variant(
        "centroid_image",
        centroid=True,
        centroid_fields=("image_siglip2",),
    ),
    "centroid_cf": Variant(
        "centroid_cf",
        centroid=True,
        centroid_fields=("cf_bpr",),
    ),
    "centroid_all": Variant(
        "centroid_all",
        centroid=True,
    ),
    "centroid_all_similar": Variant(
        "centroid_all_similar",
        centroid=True,
        similar_artist_anchors=True,
    ),
    "clap_sonic": Variant(
        "clap_sonic",
        dense_branches=(DenseSpec(CLAP_AUDIO, "clap_text", "sonic"),),
    ),
    "clap_sonic_nl": Variant(
        "clap_sonic_nl",
        dense_branches=(DenseSpec(CLAP_AUDIO, "clap_text", "sonic_nl"),),
    ),
    "clap_sonic_nl_enriched": Variant(
        "clap_sonic_nl_enriched",
        dense_branches=(DenseSpec(CLAP_AUDIO, "clap_text", "sonic_nl_enriched"),),
    ),
    "clap_all": Variant(
        "clap_all",
        dense_branches=(
            DenseSpec(CLAP_AUDIO, "clap_text", "sonic"),
            DenseSpec(CLAP_AUDIO, "clap_text", "sonic_nl"),
            DenseSpec(CLAP_AUDIO, "clap_text", "sonic_nl_enriched"),
        ),
    ),
    "clap_centroid": Variant(
        "clap_centroid",
        dense_branches=(
            DenseSpec(CLAP_AUDIO, "clap_text", "sonic"),
            DenseSpec(CLAP_AUDIO, "clap_text", "sonic_nl"),
            DenseSpec(CLAP_AUDIO, "clap_text", "sonic_nl_enriched"),
        ),
        centroid=True,
        similar_artist_anchors=True,
    ),
    "qwen06_metadata": Variant(
        "qwen06_metadata",
        dense_branches=(DenseSpec(QWEN06_METADATA, "qwen_0_6b", "metadata"),),
    ),
    "qwen06_metadata_intent": Variant(
        "qwen06_metadata_intent",
        dense_branches=(DenseSpec(QWEN06_METADATA, "qwen_0_6b", "intent"),),
    ),
    "qwen06_attributes": Variant(
        "qwen06_attributes",
        dense_branches=(DenseSpec(QWEN06_ATTRIBUTES, "qwen_0_6b", "attributes"),),
    ),
    "qwen06_attributes_enriched": Variant(
        "qwen06_attributes_enriched",
        dense_branches=(
            DenseSpec(QWEN06_ATTRIBUTES, "qwen_0_6b", "attributes_enriched"),
        ),
    ),
    "qwen06_lyrics": Variant(
        "qwen06_lyrics",
        dense_branches=(
            DenseSpec("lyrics_qwen3_embedding_0_6b", "qwen_0_6b", "lyric"),
        ),
    ),
    "qwen06_intent_attr_enriched": Variant(
        "qwen06_intent_attr_enriched",
        dense_branches=(
            DenseSpec(QWEN06_METADATA, "qwen_0_6b", "intent"),
            DenseSpec(QWEN06_ATTRIBUTES, "qwen_0_6b", "attributes_enriched"),
        ),
    ),
    "qwen8_metadata": Variant(
        "qwen8_metadata",
        dense_branches=(DenseSpec(QWEN8_METADATA, "qwen_8b", "metadata"),),
    ),
    "qwen8_metadata_intent": Variant(
        "qwen8_metadata_intent",
        dense_branches=(DenseSpec(QWEN8_METADATA, "qwen_8b", "intent"),),
    ),
    "qwen8_attributes": Variant(
        "qwen8_attributes",
        dense_branches=(DenseSpec(QWEN8_ATTRIBUTES, "qwen_8b", "attributes"),),
    ),
    "qwen8_attributes_enriched": Variant(
        "qwen8_attributes_enriched",
        dense_branches=(
            DenseSpec(QWEN8_ATTRIBUTES, "qwen_8b", "attributes_enriched"),
        ),
    ),
    "qwen8_intent_attr_enriched": Variant(
        "qwen8_intent_attr_enriched",
        dense_branches=(
            DenseSpec(QWEN8_METADATA, "qwen_8b", "intent"),
            DenseSpec(QWEN8_ATTRIBUTES, "qwen_8b", "attributes_enriched"),
        ),
    ),
    "qwen06_clap_centroid": Variant(
        "qwen06_clap_centroid",
        dense_branches=(
            DenseSpec(QWEN06_METADATA, "qwen_0_6b", "metadata"),
            DenseSpec(QWEN06_METADATA, "qwen_0_6b", "intent"),
            DenseSpec(QWEN06_ATTRIBUTES, "qwen_0_6b", "attributes_enriched"),
            DenseSpec(CLAP_AUDIO, "clap_text", "sonic"),
            DenseSpec(CLAP_AUDIO, "clap_text", "sonic_nl"),
            DenseSpec(CLAP_AUDIO, "clap_text", "sonic_nl_enriched"),
        ),
        centroid=True,
        similar_artist_anchors=True,
    ),
    "qwen06_clap_centroid_branch_rules": Variant(
        "qwen06_clap_centroid_branch_rules",
        dense_branches=(
            DenseSpec(QWEN06_METADATA, "qwen_0_6b", "metadata"),
            DenseSpec(QWEN06_METADATA, "qwen_0_6b", "intent"),
            DenseSpec(QWEN06_ATTRIBUTES, "qwen_0_6b", "attributes_enriched"),
            DenseSpec(CLAP_AUDIO, "clap_text", "sonic"),
            DenseSpec(CLAP_AUDIO, "clap_text", "sonic_nl"),
            DenseSpec(CLAP_AUDIO, "clap_text", "sonic_nl_enriched"),
        ),
        centroid=True,
        similar_artist_anchors=True,
        branch_local_rules=(
            "hard_drop",
            "new_artist_demote",
            "anchor_tag_boost",
            "explicit_popularity_boost",
            "negative_tag_demote",
            "temporal_soft",
        ),
    ),
    "all_candidate_recall": Variant(
        "all_candidate_recall",
        dense_branches=(
            DenseSpec(QWEN06_METADATA, "qwen_0_6b", "metadata"),
            DenseSpec(QWEN06_METADATA, "qwen_0_6b", "intent"),
            DenseSpec(QWEN06_ATTRIBUTES, "qwen_0_6b", "attributes_enriched"),
            DenseSpec(QWEN8_METADATA, "qwen_8b", "metadata"),
            DenseSpec(QWEN8_METADATA, "qwen_8b", "intent"),
            DenseSpec(QWEN8_ATTRIBUTES, "qwen_8b", "attributes_enriched"),
            DenseSpec(CLAP_AUDIO, "clap_text", "sonic"),
            DenseSpec(CLAP_AUDIO, "clap_text", "sonic_nl"),
            DenseSpec(CLAP_AUDIO, "clap_text", "sonic_nl_enriched"),
        ),
        centroid=True,
        similar_artist_anchors=True,
    ),
    "all_candidate_branch_rules": Variant(
        "all_candidate_branch_rules",
        dense_branches=(
            DenseSpec(QWEN06_METADATA, "qwen_0_6b", "metadata"),
            DenseSpec(QWEN06_METADATA, "qwen_0_6b", "intent"),
            DenseSpec(QWEN06_ATTRIBUTES, "qwen_0_6b", "attributes_enriched"),
            DenseSpec(QWEN8_METADATA, "qwen_8b", "metadata"),
            DenseSpec(QWEN8_METADATA, "qwen_8b", "intent"),
            DenseSpec(QWEN8_ATTRIBUTES, "qwen_8b", "attributes_enriched"),
            DenseSpec(CLAP_AUDIO, "clap_text", "sonic"),
            DenseSpec(CLAP_AUDIO, "clap_text", "sonic_nl"),
            DenseSpec(CLAP_AUDIO, "clap_text", "sonic_nl_enriched"),
        ),
        centroid=True,
        similar_artist_anchors=True,
        branch_local_rules=(
            "hard_drop",
            "new_artist_demote",
            "anchor_tag_boost",
            "explicit_popularity_boost",
            "negative_tag_demote",
            "temporal_soft",
        ),
    ),
}


DEFAULT_VARIANTS = (
    "current_config",
    "bm25_only",
    "bm25_lookup",
    "bm25_discography",
    "bm25_era_popularity",
    "centroid_style",
    "centroid_audio",
    "centroid_image",
    "centroid_cf",
    "centroid_all",
    "centroid_all_similar",
    "clap_sonic",
    "clap_sonic_nl",
    "clap_sonic_nl_enriched",
    "clap_all",
    "clap_centroid",
    "qwen06_metadata",
    "qwen06_metadata_intent",
    "qwen06_attributes",
    "qwen06_attributes_enriched",
    "qwen06_lyrics",
    "qwen06_intent_attr_enriched",
    "qwen8_metadata",
    "qwen8_metadata_intent",
    "qwen8_attributes",
    "qwen8_attributes_enriched",
    "qwen8_intent_attr_enriched",
    "qwen06_clap_centroid",
    "all_candidate_recall",
    "qwen06_clap_centroid_branch_rules",
    "all_candidate_branch_rules",
)

COMBINED_VARIANTS = {
    "current_config",
    "bm25_lookup",
    "centroid_style",
    "centroid_all",
    "centroid_all_similar",
    "clap_all",
    "clap_centroid",
    "qwen06_intent_attr_enriched",
    "qwen8_intent_attr_enriched",
    "qwen06_clap_centroid",
    "all_candidate_recall",
    "qwen06_clap_centroid_branch_rules",
    "all_candidate_branch_rules",
}


def _load_jsonl(path: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        rows[row["sample_id"]] = row
    return rows


def _rank(ids: list[str], target: str) -> int | None:
    try:
        return ids.index(target) + 1
    except ValueError:
        return None


def _branch_rank(branch_pools, target: str) -> tuple[str | None, int | None]:
    best_name: str | None = None
    best_rank: int | None = None
    for pool in branch_pools:
        ids = [track_id for track_id, _score in pool.hits]
        rank = _rank(ids, target)
        if rank is not None and (best_rank is None or rank < best_rank):
            best_name = pool.name
            best_rank = rank
    return best_name, best_rank


def _union_hit(branch_pools, target: str, k: int) -> bool:
    return any(
        target in {track_id for track_id, _score in pool.hits[:k]}
        for pool in branch_pools
    )


def _variant_qu_kwargs(
    base_qu_kwargs: dict[str, Any],
    variant: Variant,
    lancedb_uri: Path,
) -> dict[str, Any]:
    qu_kwargs = copy.deepcopy(base_qu_kwargs)
    qu_kwargs.setdefault("lancedb", {})
    qu_kwargs["lancedb"]["db_uri"] = str(lancedb_uri)
    # Keep local runs RAM-light. Dense ANN search does not require
    # LanceDbCatalog eager vectors; only centroid construction does. Loading
    # every vector column for every matrix variant can exhaust a laptop.
    centroid_fields = list(variant.centroid_fields)
    if variant.centroid and not centroid_fields:
        centroid_fields = [CLAP_AUDIO, "image_siglip2", "cf_bpr"]
    eager_vector_fields: list[str] = []
    if variant.use_base_config:
        for branch in qu_kwargs.get("compiler", {}).get("centroid_only_branches", []):
            field = branch.get("vector_field")
            if field and field not in eager_vector_fields:
                eager_vector_fields.append(field)
    elif variant.centroid:
        eager_vector_fields = list(centroid_fields)
    qu_kwargs["lancedb"]["eager_vector_fields"] = eager_vector_fields

    # Avoid instantiating unused remote encoder clients in each variant.
    base_encoders = dict(base_qu_kwargs.get("encoders") or {})
    if variant.use_base_config:
        needed_encoder_ids = {
            branch.get("encoder_id")
            for branch in qu_kwargs.get("compiler", {}).get("dense_branches", [])
            if branch.get("encoder_id")
        }
    else:
        needed_encoder_ids = {branch.encoder_id for branch in variant.dense_branches}
    if not needed_encoder_ids:
        fallback = base_encoders.get("qwen_0_6b") or next(iter(base_encoders.values()))
        qu_kwargs["encoders"] = {"qwen_0_6b": fallback}
    else:
        missing = sorted(needed_encoder_ids - set(base_encoders))
        if missing:
            raise KeyError(f"variant {variant.name!r} needs missing encoders {missing}")
        qu_kwargs["encoders"] = {
            encoder_id: base_encoders[encoder_id]
            for encoder_id in sorted(needed_encoder_ids)
        }

    comp = qu_kwargs.setdefault("compiler", {})
    comp["branch_trace_topk"] = 1000
    comp["bm25_k"] = 1000
    comp["dense_k"] = 1000
    comp["final_topk"] = 1000
    if variant.use_base_config:
        return qu_kwargs

    comp["enable_dense"] = bool(variant.dense_branches)
    comp["dense_branches"] = [branch.to_config() for branch in variant.dense_branches]
    comp["enable_era_popularity"] = (
        variant.lookups if variant.era_popularity is None else variant.era_popularity
    )
    comp["enable_resolved_artist_discography"] = (
        variant.lookups if variant.discography is None else variant.discography
    )
    comp["enable_similar_artist_anchors"] = variant.similar_artist_anchors
    comp["similar_artist_anchor_intents"] = list(variant.similar_artist_intents)
    comp["similar_artist_anchor_topk"] = 3
    comp["similar_artist_max_artists"] = 5
    comp["centroid_only_branches"] = []
    if variant.centroid:
        comp["centroid_only_branches"] = [
            {
                "vector_field": field,
                "weight": variant.centroid_weight,
                "topk": 1000,
                "distance_type": "cosine",
            }
            for field in centroid_fields
        ]
    return qu_kwargs


def _state_from_audit(row: dict[str, Any]):
    raw = row["new_state"]
    v1_payload = {key: raw[key] for key in V1_KEYS if key in raw}
    return project_v1_to_v0plus(ConversationStateV1.model_validate(v1_payload))


def _enum_value(value: Any) -> str:
    raw = getattr(value, "value", value)
    return str(raw) if raw is not None else ""


def _state_values(state: Any, fact_type: str, facet: str | None = None) -> list[str]:
    values: list[str] = []
    for fact in getattr(state, "facts", []) or []:
        if _enum_value(getattr(fact, "type", None)) != fact_type:
            continue
        if facet is not None and _enum_value(getattr(fact, "facet", None)) != facet:
            continue
        value = str(getattr(fact, "value", "") or "").strip()
        if value:
            values.append(value)
    return values


def _has_explicit_popularity_request(state: Any) -> bool:
    request_type = _enum_value(getattr(getattr(state, "current_request", None), "request_type", ""))
    if request_type == "hidden_target":
        return "popularity" in {
            _enum_value(getattr(fact, "facet", None))
            for fact in getattr(state, "facts", []) or []
        }
    return bool(_state_values(state, "attribute", "popularity"))


def _negative_tag_values(state: Any) -> set[str]:
    values: set[str] = set()
    for rejection in getattr(state, "explicit_rejections", []) or []:
        if getattr(rejection, "kind", "") == "tag":
            value = str(getattr(rejection, "value", "") or "").strip().casefold()
            if value:
                values.add(value)
    for fact in getattr(state, "facts", []) or []:
        if _enum_value(getattr(fact, "type", None)) != "attribute":
            continue
        if _enum_value(getattr(fact, "role", None)) != "rejected":
            continue
        value = str(getattr(fact, "value", "") or "").strip().casefold()
        if value:
            values.add(value)
    return values


def _anchor_artist_ids(qu, rs) -> set[str]:
    ids: set[str] = set()
    for track_id in qu.compiler._anchor_track_ids(rs.state):
        artist_id = qu.compiler.catalog.artist_id_of(track_id)
        if artist_id:
            ids.add(artist_id)
    return ids


def _branch_local_multiplier(qu, rs, track_id: str, rules: tuple[str, ...]) -> float:
    """Analysis-only branch reordering from compiled state.

    This is deliberately conservative and scoped to matrix variants. It never
    reads raw user text, and it only hard-drops through the compiler's resolved
    entity/playback drop set. Other state signals are soft branch-local rank
    adjustments.
    """

    state = rs.state
    if "hard_drop" in rules and track_id in qu.compiler._hard_drop_set(rs):
        return 0.0

    mult = 1.0

    if "new_artist_demote" in rules and _enum_value(state.target_artist_mode) == "new_artist":
        artist_id = qu.compiler.catalog.artist_id_of(track_id)
        if artist_id is not None and artist_id in _anchor_artist_ids(qu, rs):
            mult *= 0.45

    tags = {tag.casefold() for tag in qu.compiler.catalog.tag_list(track_id)}

    if "anchor_tag_boost" in rules and tags:
        anchor_tags = {tag.casefold() for tag in qu.compiler._top_anchor_tags(rs, n=6)}
        positive_tags = {
            value.casefold()
            for value in qu.compiler._positive_mention_values(state, "tag")
        }
        overlap = len(tags & (anchor_tags | positive_tags))
        if overlap:
            mult *= min(1.8, 1.0 + 0.18 * overlap)

    if "negative_tag_demote" in rules and tags:
        overlap = len(tags & _negative_tag_values(state))
        if overlap:
            mult *= 0.65 ** overlap

    if "explicit_popularity_boost" in rules and _has_explicit_popularity_request(state):
        pop_rank = qu.compiler._popularity_rank().get(track_id)
        if pop_rank is not None:
            if pop_rank < 200:
                mult *= 1.45
            elif pop_rank < 1000:
                mult *= 1.25
            elif pop_rank < 3000:
                mult *= 1.10

    if "temporal_soft" in rules and state.release_year_range is not None:
        year = qu.compiler.catalog.release_year_of(track_id)
        ryr = state.release_year_range
        if year is not None:
            lo = ryr.start if ryr.start is not None else -10**9
            hi = ryr.end if ryr.end is not None else 10**9
            if lo <= year <= hi:
                mult *= 1.15
            else:
                mult *= 0.75

    return mult


def _rerank_branch_pools(qu, rs, branch_pools, rules: tuple[str, ...]) -> list[BranchPool]:
    if not rules:
        return list(branch_pools)

    out: list[BranchPool] = []
    for pool in branch_pools:
        adjusted: list[tuple[str, float, int]] = []
        seen: set[str] = set()
        for rank, (track_id, _score) in enumerate(pool.hits, start=1):
            if track_id in seen:
                continue
            seen.add(track_id)
            mult = _branch_local_multiplier(qu, rs, track_id, rules)
            if mult <= 0.0:
                continue
            # Rank-normalized score keeps the test about local branch ordering,
            # not incomparable raw BM25/cosine score scales.
            adjusted.append((track_id, mult / (60.0 + rank), rank))
        adjusted.sort(key=lambda item: (-item[1], item[2]))
        out.append(BranchPool(pool.name, [(track_id, score) for track_id, score, _ in adjusted]))
    return out


def _compile_variant(
    qu,
    row: dict[str, Any],
    target: str,
    variant: Variant | None = None,
) -> dict[str, Any]:
    state = _state_from_audit(row)
    played = [tf.track_id for tf in state.track_feedback]
    rs = qu.resolver.resolve(state, played_track_ids=played)
    result = qu.compiler._compile(rs, user_id=None)
    branch_pools = _rerank_branch_pools(
        qu,
        rs,
        result.branch_pools,
        () if variant is None else variant.branch_local_rules,
    )
    final_rank = _rank(result.ranked, target)
    fused_rank = _rank([track_id for track_id, _score in result.fused], target)
    best_branch, best_branch_rank = _branch_rank(branch_pools, target)
    out: dict[str, Any] = {
        "final_rank": final_rank,
        "fused_rank": fused_rank,
        "best_branch": best_branch,
        "best_branch_rank": best_branch_rank,
        "n_branch_pools": len(branch_pools),
    }
    for k in KS:
        out[f"final@{k}"] = final_rank is not None and final_rank <= k
        out[f"union@{k}"] = _union_hit(branch_pools, target, k)
    return out


def _summary(rows: list[dict[str, Any]], variant: str) -> dict[str, Any]:
    scoped = [row for row in rows if row["variant"] == variant]
    n = len(scoped)
    out: dict[str, Any] = {"variant": variant, "n": n}
    if n == 0:
        return out
    for k in KS:
        out[f"final@{k}"] = sum(row[f"final@{k}"] for row in scoped) / n
        out[f"union@{k}"] = sum(row[f"union@{k}"] for row in scoped) / n
        out[f"best_branch@{k}"] = (
            sum((row["best_branch_rank"] or 10**9) <= k for row in scoped) / n
        )
    return out


def _rate(values: list[bool]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _baseline_union_at(baseline: dict[str, Any], k: int) -> bool | None:
    direct = baseline.get(f"union{k}")
    if direct is not None:
        return bool(direct)
    # The saved packs predate union@50. When union@20 and union@100 agree for a
    # row, monotonicity makes union@50 inferable for that row.
    if k == 50 and baseline.get("union20") is not None and baseline.get("union100") is not None:
        u20 = bool(baseline["union20"])
        u100 = bool(baseline["union100"])
        if u20 == u100:
            return u20
    return None


def _baseline_summary(turn_meta: dict[str, dict[str, Any]], sample_ids: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {"variant": "official_trace_baseline", "n": len(sample_ids)}
    for k in KS:
        union_values = [
            _baseline_union_at(turn_meta[sid]["baseline"], k) for sid in sample_ids
        ]
        if all(value is not None for value in union_values):
            out[f"union@{k}"] = sum(bool(value) for value in union_values) / len(sample_ids)
        out[f"final@{k}"] = sum(
            (turn_meta[sid]["baseline"].get("final_rank") or 10**9) <= k
            for sid in sample_ids
        ) / len(sample_ids)
    return out


def _baseline_rate(
    turn_meta: dict[str, dict[str, Any]],
    sample_ids: list[str],
    metric: str,
) -> float | None:
    if metric.startswith("union@"):
        k = int(metric.split("@", 1)[1])
        values = [_baseline_union_at(turn_meta[sid]["baseline"], k) for sid in sample_ids]
        if any(value is None for value in values):
            return None
        return _rate([bool(value) for value in values])
    if metric.startswith("final@"):
        k = int(metric.split("@", 1)[1])
        return _rate([
            (turn_meta[sid]["baseline"].get("final_rank") or 10**9) <= k
            for sid in sample_ids
        ])
    raise KeyError(metric)


def _variant_rate(
    rows_by_variant_sample: dict[tuple[str, str], dict[str, Any]],
    sample_ids: list[str],
    variant: str,
    metric: str,
) -> float | None:
    values: list[bool] = []
    for sid in sample_ids:
        row = rows_by_variant_sample.get((variant, sid))
        if row is None:
            return None
        values.append(bool(row[metric]))
    return _rate(values)


def _class_summaries(
    rows: list[dict[str, Any]],
    turn_meta: dict[str, dict[str, Any]],
    *,
    variant_names: list[str],
    combined_variant_names: set[str],
) -> list[dict[str, Any]]:
    rows_by_variant_sample = {
        (row["variant"], row["sample_id"]): row
        for row in rows
    }
    packs: dict[str, list[str]] = {}
    for sid, meta in turn_meta.items():
        packs.setdefault(meta["pack"], []).append(sid)

    out: list[dict[str, Any]] = []
    for pack, sample_ids in sorted(packs.items()):
        row: dict[str, Any] = {
            "pack": pack,
            "n": len(sample_ids),
            "baseline_union@20": _baseline_rate(turn_meta, sample_ids, "union@20"),
            "baseline_union@50": _baseline_rate(turn_meta, sample_ids, "union@50"),
            "baseline_union@100": _baseline_rate(turn_meta, sample_ids, "union@100"),
            "baseline_final@20": _baseline_rate(turn_meta, sample_ids, "final@20"),
        }

        single_candidates = [
            variant for variant in variant_names if variant not in combined_variant_names
        ]
        best_single = None
        best_single_key = (-1.0, -1.0, -1.0)
        for variant in single_candidates:
            u20 = _variant_rate(rows_by_variant_sample, sample_ids, variant, "union@20")
            u50 = _variant_rate(rows_by_variant_sample, sample_ids, variant, "union@50")
            u100 = _variant_rate(rows_by_variant_sample, sample_ids, variant, "union@100")
            if u20 is None or u50 is None or u100 is None:
                continue
            key = (u20, u50, u100)
            if key > best_single_key:
                best_single = variant
                best_single_key = key
        row["best_single_variant"] = best_single
        row["best_single_union@20"] = None if best_single is None else best_single_key[0]
        row["best_single_union@50"] = None if best_single is None else best_single_key[1]
        row["best_single_union@100"] = None if best_single is None else best_single_key[2]

        best_combined = None
        best_combined_key = (-1.0, -1.0, -1.0)
        for variant in variant_names:
            if variant not in combined_variant_names:
                continue
            u20 = _variant_rate(rows_by_variant_sample, sample_ids, variant, "union@20")
            u50 = _variant_rate(rows_by_variant_sample, sample_ids, variant, "union@50")
            u100 = _variant_rate(rows_by_variant_sample, sample_ids, variant, "union@100")
            if u20 is None or u50 is None or u100 is None:
                continue
            key = (u20, u50, u100)
            if key > best_combined_key:
                best_combined = variant
                best_combined_key = key
        row["combined_variant"] = best_combined
        row["combined_union@20"] = None if best_combined is None else best_combined_key[0]
        row["combined_union@50"] = None if best_combined is None else best_combined_key[1]
        row["combined_union@100"] = None if best_combined is None else best_combined_key[2]
        out.append(row)
    return out


def _miss_reason(row: dict[str, Any], meta: dict[str, Any]) -> str:
    if row.get("union@20"):
        return "rescued_at_union20"
    best_rank = row.get("best_branch_rank")
    if best_rank is None:
        return "existing_retrievers_do_not_surface_gt"
    if best_rank <= 50:
        return "branch_local_ranking_gap_21_50"
    if best_rank <= 100:
        return "branch_local_ranking_gap_51_100"
    if best_rank <= 1000:
        return "deep_candidate_ranking_gap"
    state_failure_packs = (
        "P0_roleless",
        "P0_novelty",
        "P1_temporal",
        "P1_rejection",
    )
    if any(meta["pack"].startswith(prefix) for prefix in state_failure_packs):
        return "state_wrong_or_incomplete_for_existing_retrievers"
    return "gt_not_in_existing_retriever_pool"


def _examples_for_variant(
    rows: list[dict[str, Any]],
    turn_meta: dict[str, dict[str, Any]],
    variant: str,
    *,
    limit: int = 12,
) -> dict[str, list[dict[str, Any]]]:
    scoped = [row for row in rows if row["variant"] == variant]
    rescued: list[dict[str, Any]] = []
    still_missed: list[dict[str, Any]] = []
    for row in scoped:
        meta = turn_meta[row["sample_id"]]
        baseline_u20 = _baseline_union_at(meta["baseline"], 20)
        item = {
            "sample_id": row["sample_id"],
            "pack": meta["pack"],
            "gt_track": row["gt_track"],
            "gt_artist": row["gt_artist"],
            "best_branch": row.get("best_branch"),
            "best_branch_rank": row.get("best_branch_rank"),
            "final_rank": row.get("final_rank"),
            "why": _miss_reason(row, meta),
            "current_user": meta.get("current_user"),
            "what_should_change": meta.get("what_should_change"),
        }
        if baseline_u20 is False and row["union@20"]:
            rescued.append(item)
        elif not row["union@20"]:
            still_missed.append(item)
    return {
        "rescued_union20": rescued[:limit],
        "still_missed_union20": still_missed[:limit],
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "sample_id",
        "pack",
        "class_type",
        "variant",
        "gt_track",
        "gt_artist",
        "final_rank",
        "fused_rank",
        "best_branch_rank",
        "best_branch",
        "n_branch_pools",
    ] + [f"union@{k}" for k in KS] + [f"final@{k}" for k in KS]
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in fieldnames})


def _fmt(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.3f}"
    if value is None:
        return ""
    return str(value)


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# State V1 Retriever Matrix",
        "",
        "Focused candidate-generation matrix over saved V1 extraction states.",
        "The main gate is branch union@20/50; RRF/final ranking is reported separately.",
        "",
        "## Summary",
        "",
        "| Variant | n | final@20 | final@50 | union@20 | union@50 | union@100 | union@200 | union@1000 | best branch@50 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["summary"]:
        lines.append(
            "| `{variant}` | {n} | {final20} | {final50} | {union20} | {union50} | {union100} | {union200} | {union1000} | {best50} |".format(
                variant=row["variant"],
                n=row["n"],
                final20=_fmt(row.get("final@20")),
                final50=_fmt(row.get("final@50")),
                union20=_fmt(row.get("union@20")),
                union50=_fmt(row.get("union@50")),
                union100=_fmt(row.get("union@100")),
                union200=_fmt(row.get("union@200")),
                union1000=_fmt(row.get("union@1000")),
                best50=_fmt(row.get("best_branch@50")),
            )
        )

    lines.extend([
        "",
        "## Per-Class Summary",
        "",
        "| Pack | n | baseline u@20 | baseline u@50 | best single | single u@20 | single u@50 | combined | combined u@20 | combined u@50 |",
        "|---|---:|---:|---:|---|---:|---:|---|---:|---:|",
    ])
    for row in payload.get("class_summary", []):
        lines.append(
            "| {pack} | {n} | {bu20} | {bu50} | `{single}` | {su20} | {su50} | `{combined}` | {cu20} | {cu50} |".format(
                pack=row["pack"],
                n=row["n"],
                bu20=_fmt(row.get("baseline_union@20")),
                bu50=_fmt(row.get("baseline_union@50")),
                single=row.get("best_single_variant") or "",
                su20=_fmt(row.get("best_single_union@20")),
                su50=_fmt(row.get("best_single_union@50")),
                combined=row.get("combined_variant") or "",
                cu20=_fmt(row.get("combined_union@20")),
                cu50=_fmt(row.get("combined_union@50")),
            )
        )

    if payload.get("examples"):
        lines.extend([
            "",
            "## Examples",
            "",
        ])
        for variant, example_payload in payload["examples"].items():
            lines.extend([
                f"### `{variant}` Rescued union@20",
                "",
            ])
            for item in example_payload.get("rescued_union20", []):
                lines.append(
                    "- `{sample_id}` ({pack}): GT={gt_track} by {gt_artist}; best_branch=`{best_branch}` rank={best_rank}; why={why}".format(
                        sample_id=item["sample_id"],
                        pack=item["pack"],
                        gt_track=item["gt_track"],
                        gt_artist=item["gt_artist"],
                        best_branch=item.get("best_branch") or "",
                        best_rank=item.get("best_branch_rank") or "",
                        why=item["why"],
                    )
                )
            lines.extend([
                "",
                f"### `{variant}` Still Missed union@20",
                "",
            ])
            for item in example_payload.get("still_missed_union20", []):
                lines.append(
                    "- `{sample_id}` ({pack}): GT={gt_track} by {gt_artist}; best_branch=`{best_branch}` rank={best_rank}; why={why}; change={change}".format(
                        sample_id=item["sample_id"],
                        pack=item["pack"],
                        gt_track=item["gt_track"],
                        gt_artist=item["gt_artist"],
                        best_branch=item.get("best_branch") or "",
                        best_rank=item.get("best_branch_rank") or "",
                        why=item["why"],
                        change=item.get("what_should_change") or "",
                    )
                )
            lines.append("")

    lines.extend([
        "",
        "## Per-Sample Rows",
        "",
        "| Sample | Pack | GT | Variant | final rank | best branch rank | best branch | union@20 | union@50 | union@100 |",
        "|---|---|---|---|---:|---:|---|---:|---:|---:|",
    ])
    for row in payload["rows"]:
        lines.append(
            "| `{sample_id}` | `{pack}` | {gt_track} / {gt_artist} | `{variant}` | {final_rank} | {best_branch_rank} | `{best_branch}` | {u20} | {u50} | {u100} |".format(
                sample_id=row["sample_id"],
                pack=row["pack"],
                gt_track=row["gt_track"],
                gt_artist=row["gt_artist"],
                variant=row["variant"],
                final_rank=row["final_rank"] or "",
                best_branch_rank=row["best_branch_rank"] or "",
                best_branch=row["best_branch"] or "",
                u20=int(bool(row["union@20"])),
                u50=int(bool(row["union@50"])),
                u100=int(bool(row["union@100"])),
            )
        )
    path.write_text("\n".join(lines) + "\n")


def _encoder_has_vllm_endpoint(value: Any) -> bool:
    return isinstance(value, dict) and bool(value.get("vllm_endpoint"))


def _qu_kwargs_has_vllm_endpoint(qu_kwargs: dict[str, Any]) -> bool:
    if _encoder_has_vllm_endpoint(qu_kwargs.get("encoder")):
        return True
    encoders = qu_kwargs.get("encoders")
    if not isinstance(encoders, dict):
        return False
    return any(_encoder_has_vllm_endpoint(value) for value in encoders.values())


def _resolve_vllm_endpoints_in_qu_kwargs(qu_kwargs: dict[str, Any]) -> None:
    if not _qu_kwargs_has_vllm_endpoint(qu_kwargs):
        return
    import importlib.util

    vllm_path = Path(__file__).resolve().parent.parent / "modal" / "vllm_serve.py"
    spec = importlib.util.spec_from_file_location("mcrs_vllm_serve", vllm_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load vLLM endpoint resolver from {vllm_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.resolve_vllm_endpoints_in_qu_kwargs(qu_kwargs)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis-dir", type=Path, default=DEFAULT_ANALYSIS_DIR)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--lancedb-uri", type=Path, default=DEFAULT_MAIN_LANCEDB)
    parser.add_argument("--audit-jsonl", type=Path)
    parser.add_argument("--pack-json", type=Path)
    parser.add_argument("--variant", action="append", dest="variants")
    parser.add_argument("--sample-id", action="append", dest="sample_ids")
    parser.add_argument("--sample-id-file", type=Path)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-md", type=Path)
    parser.add_argument("--output-csv", type=Path)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    audit_path = args.audit_jsonl or (
        args.analysis_dir / "state_v1_goal_current_all110_reprojected_audit.jsonl"
    )
    pack_path = args.pack_json or (args.analysis_dir / "state_experiment_pack.json")
    if not audit_path.exists():
        raise SystemExit(f"missing audit path: {audit_path}")
    if not pack_path.exists():
        raise SystemExit(f"missing pack path: {pack_path}")
    if not args.lancedb_uri.exists():
        raise SystemExit(f"missing LanceDB URI: {args.lancedb_uri}")

    unknown_variants = sorted(set(args.variants or ()) - set(VARIANTS))
    if unknown_variants:
        raise SystemExit(
            f"unknown variants {unknown_variants}; available: {sorted(VARIANTS)}"
        )

    audit_rows = _load_jsonl(audit_path)
    pack = json.loads(pack_path.read_text())
    turn_meta = {turn["sample_id"]: turn for turn in pack["turns"]}
    sample_ids: list[str] = []
    if args.sample_ids:
        sample_ids.extend(args.sample_ids)
    if args.sample_id_file:
        sample_ids.extend(
            line.strip()
            for line in args.sample_id_file.read_text().splitlines()
            if line.strip()
        )
    if not sample_ids:
        sample_ids = list(turn_meta)
    if args.limit is not None:
        sample_ids = sample_ids[: args.limit]
    missing = [sid for sid in sample_ids if sid not in audit_rows or sid not in turn_meta]
    if missing:
        raise SystemExit(f"sample ids missing from audit/pack: {missing}")
    selected_turn_meta = {sid: turn_meta[sid] for sid in sample_ids}

    variant_names = args.variants or list(DEFAULT_VARIANTS)
    base_cfg = OmegaConf.load(args.config)
    base_qu_kwargs = OmegaConf.to_container(base_cfg["qu_kwargs"], resolve=True)
    _resolve_vllm_endpoints_in_qu_kwargs(base_qu_kwargs)

    rows: list[dict[str, Any]] = []
    for variant_name in variant_names:
        variant = VARIANTS[variant_name]
        if not args.quiet:
            print(f"building variant: {variant.name}", flush=True)
        qu_kwargs = _variant_qu_kwargs(base_qu_kwargs, variant, args.lancedb_uri)
        qu = build_v0plus_compiler_qu(qu_kwargs)
        for idx, sid in enumerate(sample_ids, start=1):
            meta = turn_meta[sid]
            if not args.quiet:
                print(f"  [{idx}/{len(sample_ids)}] {sid}", flush=True)
            result = _compile_variant(qu, audit_rows[sid], meta["gt_track_id"], variant)
            rows.append(
                {
                    "sample_id": sid,
                    "pack": meta["pack"],
                    "class_type": meta.get("class_type"),
                    "variant": variant.name,
                    "gt_track": meta["gt_track"],
                    "gt_artist": meta["gt_artist"],
                    **result,
                }
            )

    summary = [_baseline_summary(selected_turn_meta, sample_ids)]
    summary.extend(_summary(rows, name) for name in variant_names)
    class_summary = _class_summaries(
        rows,
        selected_turn_meta,
        variant_names=variant_names,
        combined_variant_names=COMBINED_VARIANTS,
    )
    example_variants = [
        variant
        for variant in ("current_config", "all_candidate_recall")
        if variant in variant_names
    ]
    if not example_variants and variant_names:
        example_variants = [variant_names[-1]]
    examples = {
        variant: _examples_for_variant(rows, selected_turn_meta, variant)
        for variant in example_variants
    }
    payload = {
        "samples": sample_ids,
        "variants": variant_names,
        "summary": summary,
        "class_summary": class_summary,
        "examples": examples,
        "rows": rows,
    }

    output_json = args.output_json or args.analysis_dir / "state_v1_retriever_matrix.json"
    output_md = args.output_md or args.analysis_dir / "state_v1_retriever_matrix.md"
    output_csv = args.output_csv or args.analysis_dir / "state_v1_retriever_matrix.csv"
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    _write_csv(output_csv, rows)
    _write_report(output_md, payload)
    print(
        json.dumps(
            {
                "summary": payload["summary"],
                "json": str(output_json),
                "md": str(output_md),
                "csv": str(output_csv),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
