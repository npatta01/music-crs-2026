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
import re
import sys
from collections import Counter
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
ADDITIVE_KS = (20, 50, 100)


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
    compiler_pools: bool = True
    analysis_branches: tuple[str, ...] = ()


QWEN06_METADATA = "metadata_qwen3_embedding_0_6b"
QWEN06_ATTRIBUTES = "attributes_qwen3_embedding_0_6b"
QWEN8_METADATA = "metadata_qwen3_embedding_8b"
QWEN8_ATTRIBUTES = "attributes_qwen3_embedding_8b"
CLAP_AUDIO = "audio_laion_clap"
SIGLIP_IMAGE = "image_siglip2"


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
        centroid_fields=(SIGLIP_IMAGE,),
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
    "siglip_visual": Variant(
        "siglip_visual",
        dense_branches=(DenseSpec(SIGLIP_IMAGE, "siglip2_text", "visual"),),
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
    "tag_popularity": Variant(
        "tag_popularity",
        compiler_pools=False,
        analysis_branches=("tag_popularity",),
    ),
    "tag_popularity_alias": Variant(
        "tag_popularity_alias",
        compiler_pools=False,
        analysis_branches=("tag_popularity_alias",),
    ),
    "era_tag_popularity": Variant(
        "era_tag_popularity",
        compiler_pools=False,
        analysis_branches=("era_tag_popularity",),
    ),
    "same_album_fanout": Variant(
        "same_album_fanout",
        compiler_pools=False,
        analysis_branches=("same_album_fanout",),
    ),
    "artist_tag_neighbor_popularity": Variant(
        "artist_tag_neighbor_popularity",
        compiler_pools=False,
        analysis_branches=("artist_tag_neighbor_popularity",),
    ),
    "all_synthetic_recall": Variant(
        "all_synthetic_recall",
        compiler_pools=False,
        analysis_branches=(
            "tag_popularity_alias",
            "era_tag_popularity",
            "same_album_fanout",
            "artist_tag_neighbor_popularity",
        ),
    ),
    "query_text_tag_popularity": Variant(
        "query_text_tag_popularity",
        compiler_pools=False,
        analysis_branches=("query_text_tag_popularity",),
    ),
    "scene_era_tag_popularity_v2": Variant(
        "scene_era_tag_popularity_v2",
        compiler_pools=False,
        analysis_branches=("scene_era_tag_popularity_v2",),
    ),
    "artist_neighbor_scene_v2": Variant(
        "artist_neighbor_scene_v2",
        compiler_pools=False,
        analysis_branches=("artist_neighbor_scene_v2",),
    ),
    "artist_neighbor_scene_weighted_v3": Variant(
        "artist_neighbor_scene_weighted_v3",
        compiler_pools=False,
        analysis_branches=("artist_neighbor_scene_weighted_v3",),
    ),
    "all_synthetic_recall_v2": Variant(
        "all_synthetic_recall_v2",
        compiler_pools=False,
        analysis_branches=(
            "tag_popularity_alias",
            "era_tag_popularity",
            "same_album_fanout",
            "artist_tag_neighbor_popularity",
            "query_text_tag_popularity",
        ),
    ),
    "all_candidate_plus_synthetic": Variant(
        "all_candidate_plus_synthetic",
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
        analysis_branches=(
            "tag_popularity_alias",
            "era_tag_popularity",
            "same_album_fanout",
            "artist_tag_neighbor_popularity",
        ),
    ),
    "all_candidate_plus_synthetic_v2": Variant(
        "all_candidate_plus_synthetic_v2",
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
        analysis_branches=(
            "tag_popularity_alias",
            "era_tag_popularity",
            "same_album_fanout",
            "artist_tag_neighbor_popularity",
            "query_text_tag_popularity",
        ),
    ),
    "all_candidate_plus_synthetic_v3": Variant(
        "all_candidate_plus_synthetic_v3",
        dense_branches=(
            DenseSpec(QWEN06_METADATA, "qwen_0_6b", "metadata"),
            DenseSpec(QWEN06_METADATA, "qwen_0_6b", "intent"),
            DenseSpec(QWEN06_ATTRIBUTES, "qwen_0_6b", "attributes"),
            DenseSpec(QWEN06_ATTRIBUTES, "qwen_0_6b", "attributes_enriched"),
            DenseSpec("lyrics_qwen3_embedding_0_6b", "qwen_0_6b", "lyric"),
            DenseSpec(QWEN8_METADATA, "qwen_8b", "metadata"),
            DenseSpec(QWEN8_METADATA, "qwen_8b", "intent"),
            DenseSpec(QWEN8_ATTRIBUTES, "qwen_8b", "attributes"),
            DenseSpec(QWEN8_ATTRIBUTES, "qwen_8b", "attributes_enriched"),
            DenseSpec(CLAP_AUDIO, "clap_text", "sonic"),
            DenseSpec(CLAP_AUDIO, "clap_text", "sonic_nl"),
            DenseSpec(CLAP_AUDIO, "clap_text", "sonic_nl_enriched"),
        ),
        centroid=True,
        similar_artist_anchors=True,
        analysis_branches=(
            "tag_popularity_alias",
            "era_tag_popularity",
            "same_album_fanout",
            "artist_tag_neighbor_popularity",
            "query_text_tag_popularity",
        ),
    ),
    "all_candidate_plus_targeted_v4": Variant(
        "all_candidate_plus_targeted_v4",
        dense_branches=(
            DenseSpec(QWEN06_METADATA, "qwen_0_6b", "metadata"),
            DenseSpec(QWEN06_METADATA, "qwen_0_6b", "intent"),
            DenseSpec(QWEN06_ATTRIBUTES, "qwen_0_6b", "attributes"),
            DenseSpec(QWEN06_ATTRIBUTES, "qwen_0_6b", "attributes_enriched"),
            DenseSpec("lyrics_qwen3_embedding_0_6b", "qwen_0_6b", "lyric"),
            DenseSpec(QWEN8_METADATA, "qwen_8b", "metadata"),
            DenseSpec(QWEN8_METADATA, "qwen_8b", "intent"),
            DenseSpec(QWEN8_ATTRIBUTES, "qwen_8b", "attributes"),
            DenseSpec(QWEN8_ATTRIBUTES, "qwen_8b", "attributes_enriched"),
            DenseSpec(CLAP_AUDIO, "clap_text", "sonic"),
            DenseSpec(CLAP_AUDIO, "clap_text", "sonic_nl"),
            DenseSpec(CLAP_AUDIO, "clap_text", "sonic_nl_enriched"),
            DenseSpec(SIGLIP_IMAGE, "siglip2_text", "visual"),
        ),
        centroid=True,
        similar_artist_anchors=True,
        analysis_branches=(
            "tag_popularity_alias",
            "era_tag_popularity",
            "same_album_fanout",
            "artist_tag_neighbor_popularity",
            "query_text_tag_popularity",
            "scene_era_tag_popularity_v2",
            "artist_neighbor_scene_v2",
        ),
    ),
    "all_candidate_plus_targeted_v4_hard_drop": Variant(
        "all_candidate_plus_targeted_v4_hard_drop",
        dense_branches=(
            DenseSpec(QWEN06_METADATA, "qwen_0_6b", "metadata"),
            DenseSpec(QWEN06_METADATA, "qwen_0_6b", "intent"),
            DenseSpec(QWEN06_ATTRIBUTES, "qwen_0_6b", "attributes"),
            DenseSpec(QWEN06_ATTRIBUTES, "qwen_0_6b", "attributes_enriched"),
            DenseSpec("lyrics_qwen3_embedding_0_6b", "qwen_0_6b", "lyric"),
            DenseSpec(QWEN8_METADATA, "qwen_8b", "metadata"),
            DenseSpec(QWEN8_METADATA, "qwen_8b", "intent"),
            DenseSpec(QWEN8_ATTRIBUTES, "qwen_8b", "attributes"),
            DenseSpec(QWEN8_ATTRIBUTES, "qwen_8b", "attributes_enriched"),
            DenseSpec(CLAP_AUDIO, "clap_text", "sonic"),
            DenseSpec(CLAP_AUDIO, "clap_text", "sonic_nl"),
            DenseSpec(CLAP_AUDIO, "clap_text", "sonic_nl_enriched"),
            DenseSpec(SIGLIP_IMAGE, "siglip2_text", "visual"),
        ),
        centroid=True,
        similar_artist_anchors=True,
        analysis_branches=(
            "tag_popularity_alias",
            "era_tag_popularity",
            "same_album_fanout",
            "artist_tag_neighbor_popularity",
            "query_text_tag_popularity",
            "scene_era_tag_popularity_v2",
            "artist_neighbor_scene_v2",
        ),
        branch_local_rules=("hard_drop",),
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
    "siglip_visual",
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
    "tag_popularity",
    "tag_popularity_alias",
    "era_tag_popularity",
    "same_album_fanout",
    "artist_tag_neighbor_popularity",
    "all_synthetic_recall",
    "query_text_tag_popularity",
    "all_synthetic_recall_v2",
    "scene_era_tag_popularity_v2",
    "artist_neighbor_scene_v2",
    "all_candidate_plus_synthetic",
    "all_candidate_plus_synthetic_v2",
    "all_candidate_plus_synthetic_v3",
    "all_candidate_plus_targeted_v4",
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
    "all_synthetic_recall",
    "all_candidate_plus_synthetic",
    "all_synthetic_recall_v2",
    "all_candidate_plus_synthetic_v2",
    "all_candidate_plus_synthetic_v3",
    "all_candidate_plus_targeted_v4",
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


def _pool_to_trace_payload(pool: BranchPool, depth: int | None = None) -> dict[str, Any]:
    hits = [track_id for track_id, _score in pool.hits]
    if depth is not None:
        hits = hits[:depth]
    return {"name": pool.name, "hits": hits}


def _pool_from_trace_payload(payload: dict[str, Any]) -> BranchPool:
    hits: list[tuple[str, float]] = []
    for rank, item in enumerate(payload.get("hits", []), start=1):
        track_id = item[0] if isinstance(item, list) else item
        if track_id:
            hits.append((str(track_id), 1.0 / rank))
    return BranchPool(str(payload["name"]), hits)


def _trace_pool_from_dict(payload: dict[str, Any], *, prefix: str, depth: int) -> BranchPool:
    hits: list[tuple[str, float]] = []
    for rank, item in enumerate(payload.get("hits", [])[:depth], start=1):
        if isinstance(item, list):
            track_id = item[0]
            score = float(item[1]) if len(item) > 1 and item[1] is not None else 1.0 / rank
        else:
            track_id = item
            score = 1.0 / rank
        if track_id:
            hits.append((str(track_id), score))
    return BranchPool(prefix + str(payload["name"]), hits)


def _extract_trace_baseline_pools(
    trace_path: Path,
    turn_meta: dict[str, dict[str, Any]],
    *,
    depth: int = 100,
) -> dict[str, list[BranchPool]]:
    wanted: dict[tuple[str, int], str] = {}
    for sid, meta in turn_meta.items():
        wanted[(str(meta["session_id"]), int(meta["turn"]))] = sid

    found: dict[str, list[BranchPool]] = {}
    with trace_path.open() as handle:
        for line in handle:
            if len(found) == len(wanted):
                break
            row = json.loads(line)
            key = (str(row.get("session_id")), int(row.get("turn_number") or 0))
            sid = wanted.get(key)
            if sid is None:
                continue
            pools = (
                ((row.get("trace") or {}).get("branches") or {}).get("pools")
                or []
            )
            found[sid] = [
                _trace_pool_from_dict(pool, prefix="baseline.", depth=depth)
                for pool in pools
            ]
    return found


def _write_baseline_pools_json(
    path: Path,
    *,
    pools_by_sample: dict[str, list[BranchPool]],
    sample_ids: list[str],
    source_trace: Path,
    depth: int,
) -> None:
    payload = {
        "source_trace": str(source_trace),
        "depth": depth,
        "samples": sample_ids,
        "pools_by_sample": {
            sid: [_pool_to_trace_payload(pool, depth=depth) for pool in pools_by_sample[sid]]
            for sid in sample_ids
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, separators=(",", ":")) + "\n")


def _load_baseline_pools_json(path: Path) -> dict[str, list[BranchPool]]:
    payload = json.loads(path.read_text())
    return {
        sid: [_pool_from_trace_payload(pool) for pool in pools]
        for sid, pools in payload.get("pools_by_sample", {}).items()
    }


def _pool_payload_to_branch_pool(payload: dict[str, Any]) -> BranchPool:
    return _pool_from_trace_payload(payload)


def _serialize_variant_pools(
    *,
    variant: str,
    sample_ids: list[str],
    pools_by_sample: dict[str, list[BranchPool]],
    depth: int,
) -> dict[str, Any]:
    return {
        "variant": variant,
        "depth": depth,
        "samples": sample_ids,
        "pools_by_sample": {
            sid: [_pool_to_trace_payload(pool, depth=depth) for pool in pools_by_sample.get(sid, [])]
            for sid in sample_ids
        },
    }


def _load_variant_pools_payload(payload: dict[str, Any]) -> dict[str, list[BranchPool]]:
    return {
        sid: [_pool_payload_to_branch_pool(pool) for pool in pools]
        for sid, pools in payload.get("pools_by_sample", {}).items()
    }


def _branch_names(pools_by_sample: dict[str, list[BranchPool]]) -> list[str]:
    names = {
        pool.name
        for pools in pools_by_sample.values()
        for pool in pools
    }
    return sorted(names)


def _filter_pools_by_branch_names(
    pools: list[BranchPool],
    branch_names: set[str],
) -> list[BranchPool]:
    return [pool for pool in pools if pool.name in branch_names]


def _target_for_sample(turn_meta: dict[str, dict[str, Any]], sample_id: str) -> str:
    return str(turn_meta[sample_id]["gt_track_id"])


def _hit_count(
    *,
    sample_ids: list[str],
    turn_meta: dict[str, dict[str, Any]],
    pools_by_sample: dict[str, list[BranchPool]],
    k: int,
) -> int:
    return sum(
        _union_hit(pools_by_sample.get(sid, []), _target_for_sample(turn_meta, sid), k)
        for sid in sample_ids
    )


def _merged_pools_by_sample(
    sample_ids: list[str],
    *pool_maps: dict[str, list[BranchPool]],
) -> dict[str, list[BranchPool]]:
    return {
        sid: [
            pool
            for pools_by_sample in pool_maps
            for pool in pools_by_sample.get(sid, [])
        ]
        for sid in sample_ids
    }


def _all_on_ledger(
    *,
    sample_ids: list[str],
    turn_meta: dict[str, dict[str, Any]],
    protected_pools_by_sample: dict[str, list[BranchPool]],
    candidate_pools_by_sample: dict[str, list[BranchPool]],
    ks: tuple[int, ...] = ADDITIVE_KS,
) -> dict[str, Any]:
    all_on_pools = _merged_pools_by_sample(
        sample_ids,
        protected_pools_by_sample,
        candidate_pools_by_sample,
    )
    branches = _branch_names(candidate_pools_by_sample)
    overall: dict[str, Any] = {"n": len(sample_ids)}
    for k in ks:
        overall[f"protected_union@{k}_count"] = _hit_count(
            sample_ids=sample_ids,
            turn_meta=turn_meta,
            pools_by_sample=protected_pools_by_sample,
            k=k,
        )
        overall[f"all_on_union@{k}_count"] = _hit_count(
            sample_ids=sample_ids,
            turn_meta=turn_meta,
            pools_by_sample=all_on_pools,
            k=k,
        )

    branch_summary: list[dict[str, Any]] = []
    for branch in branches:
        row: dict[str, Any] = {"branch": branch, "n": len(sample_ids)}
        branch_only = {
            sid: _filter_pools_by_branch_names(candidate_pools_by_sample.get(sid, []), {branch})
            for sid in sample_ids
        }
        without_branch = {
            sid: _filter_pools_by_branch_names(
                candidate_pools_by_sample.get(sid, []),
                set(branches) - {branch},
            )
            for sid in sample_ids
        }
        protected_plus_without = _merged_pools_by_sample(
            sample_ids,
            protected_pools_by_sample,
            without_branch,
        )
        for k in ks:
            branch_hits = 0
            marginal = 0
            unique = 0
            leave_one_out = 0
            for sid in sample_ids:
                target = _target_for_sample(turn_meta, sid)
                protected_hit = _union_hit(protected_pools_by_sample.get(sid, []), target, k)
                branch_hit = _union_hit(branch_only.get(sid, []), target, k)
                without_hit = _union_hit(protected_plus_without.get(sid, []), target, k)
                all_on_hit = _union_hit(all_on_pools.get(sid, []), target, k)
                if branch_hit:
                    branch_hits += 1
                if branch_hit and not protected_hit:
                    marginal += 1
                if branch_hit and not protected_hit and not without_hit:
                    unique += 1
                if all_on_hit and not without_hit:
                    leave_one_out += 1
            row[f"branch_hit@{k}_count"] = branch_hits
            row[f"marginal_rescue@{k}_count"] = marginal
            row[f"unique_rescue@{k}_count"] = unique
            row[f"leave_one_out_loss@{k}_count"] = leave_one_out
        branch_summary.append(row)

    branch_summary.sort(
        key=lambda row: (
            -row.get("unique_rescue@100_count", 0),
            -row.get("marginal_rescue@100_count", 0),
            -row.get("branch_hit@20_count", 0),
            row["branch"],
        )
    )

    per_sample: dict[str, dict[str, Any]] = {}
    for sid in sample_ids:
        target = _target_for_sample(turn_meta, sid)
        best_branch, best_rank = _branch_rank(candidate_pools_by_sample.get(sid, []), target)
        sample_row: dict[str, Any] = {
            "pack": turn_meta[sid]["pack"],
            "best_branch": best_branch,
            "best_branch_rank": best_rank,
        }
        for k in ks:
            sample_row[f"protected_union@{k}"] = _union_hit(
                protected_pools_by_sample.get(sid, []),
                target,
                k,
            )
            sample_row[f"all_on_union@{k}"] = _union_hit(
                all_on_pools.get(sid, []),
                target,
                k,
            )
        per_sample[sid] = sample_row

    per_class: list[dict[str, Any]] = []
    packs: dict[str, list[str]] = {}
    for sid in sample_ids:
        packs.setdefault(turn_meta[sid]["pack"], []).append(sid)
    for pack, pack_ids in sorted(packs.items()):
        row: dict[str, Any] = {"pack": pack, "n": len(pack_ids)}
        for k in ks:
            row[f"protected_union@{k}_count"] = sum(
                per_sample[sid][f"protected_union@{k}"] for sid in pack_ids
            )
            row[f"all_on_union@{k}_count"] = sum(
                per_sample[sid][f"all_on_union@{k}"] for sid in pack_ids
            )
        per_class.append(row)

    return {
        "overall": overall,
        "branch_summary": branch_summary,
        "per_class": per_class,
        "per_sample": per_sample,
    }


def _greedy_minimal_subset(
    *,
    sample_ids: list[str],
    turn_meta: dict[str, dict[str, Any]],
    protected_pools_by_sample: dict[str, list[BranchPool]],
    candidate_pools_by_sample: dict[str, list[BranchPool]],
    ks: tuple[int, ...] = ADDITIVE_KS,
) -> dict[str, Any]:
    branches = _branch_names(candidate_pools_by_sample)
    selected: set[str] = set()
    steps: list[dict[str, Any]] = []
    all_on = _merged_pools_by_sample(sample_ids, protected_pools_by_sample, candidate_pools_by_sample)
    target_union100 = _hit_count(
        sample_ids=sample_ids,
        turn_meta=turn_meta,
        pools_by_sample=all_on,
        k=100,
    )
    current = dict(protected_pools_by_sample)

    while True:
        current_union100 = _hit_count(
            sample_ids=sample_ids,
            turn_meta=turn_meta,
            pools_by_sample=current,
            k=100,
        )
        if current_union100 >= target_union100:
            break
        best_branch = None
        best_candidate = None
        best_key = (0, 0, "")
        for branch in branches:
            if branch in selected:
                continue
            branch_only = {
                sid: _filter_pools_by_branch_names(candidate_pools_by_sample.get(sid, []), {branch})
                for sid in sample_ids
            }
            trial = _merged_pools_by_sample(sample_ids, current, branch_only)
            gain100 = _hit_count(
                sample_ids=sample_ids,
                turn_meta=turn_meta,
                pools_by_sample=trial,
                k=100,
            ) - current_union100
            gain20 = _hit_count(
                sample_ids=sample_ids,
                turn_meta=turn_meta,
                pools_by_sample=trial,
                k=20,
            ) - _hit_count(
                sample_ids=sample_ids,
                turn_meta=turn_meta,
                pools_by_sample=current,
                k=20,
            )
            key = (gain100, gain20, branch)
            if key[0] > 0 and key > best_key:
                best_key = key
                best_branch = branch
                best_candidate = trial
        if best_branch is None or best_candidate is None:
            break
        selected.add(best_branch)
        current = best_candidate
        step = {"branch": best_branch}
        for k in ks:
            step[f"subset_union@{k}_count"] = _hit_count(
                sample_ids=sample_ids,
                turn_meta=turn_meta,
                pools_by_sample=current,
                k=k,
            )
        steps.append(step)

    summary: dict[str, Any] = {
        "n": len(sample_ids),
        "selected_branches": [step["branch"] for step in steps],
    }
    for k in ks:
        summary[f"subset_union@{k}_count"] = _hit_count(
            sample_ids=sample_ids,
            turn_meta=turn_meta,
            pools_by_sample=current,
            k=k,
        )
        summary[f"all_on_union@{k}_count"] = _hit_count(
            sample_ids=sample_ids,
            turn_meta=turn_meta,
            pools_by_sample=all_on,
            k=k,
        )
    return {"summary": summary, "steps": steps}


def _additive_metrics_for_pools(
    protected_pools: list[BranchPool],
    branch_pools: list[BranchPool],
    target: str,
) -> dict[str, Any]:
    additive_pools = list(protected_pools) + list(branch_pools)
    branch_best, branch_rank = _branch_rank(branch_pools, target)
    additive_best, additive_rank = _branch_rank(additive_pools, target)
    protected_best, protected_rank = _branch_rank(protected_pools, target)
    out: dict[str, Any] = {
        "protected_best_branch": protected_best,
        "protected_best_branch_rank": protected_rank,
        "branch_only_best_branch": branch_best,
        "branch_only_best_branch_rank": branch_rank,
        "additive_best_branch": additive_best,
        "additive_best_branch_rank": additive_rank,
    }
    for k in ADDITIVE_KS:
        out[f"protected_union@{k}"] = _union_hit(protected_pools, target, k)
        out[f"branch_only@{k}"] = _union_hit(branch_pools, target, k)
        out[f"additive_union@{k}"] = _union_hit(additive_pools, target, k)
    return out


_TAG_ALIASES: dict[str, tuple[str, ...]] = {
    "hip hop": ("hip-hop", "rap"),
    "hip-hop": ("hip hop", "rap"),
    "rap": ("hip hop", "hip-hop"),
    "r&b": ("rnb", "rhythm and blues", "soul"),
    "rnb": ("r&b", "rhythm and blues", "soul"),
    "pop-punk": ("pop punk", "punk pop"),
    "pop punk": ("pop-punk", "punk pop"),
    "edm": ("electronic", "electronica", "dance"),
    "electronic": ("electronica", "edm"),
    "alt rock": ("alternative rock", "alternative"),
    "alternative rock": ("alt rock", "alternative"),
    "classic": ("popular", "hit"),
    "popular": ("classic", "hit"),
    "movie score": ("soundtrack", "score", "ost"),
    "soundtrack": ("movie score", "score", "ost"),
    "orchestral": ("orchestra", "orchestral epic", "classical"),
    "christian": ("ccm", "christian music", "christian rock", "contemporary christian"),
    "latin pop": ("latin", "pop"),
    "funk carioca": ("brazilian funk", "baile funk", "funk"),
    "tecno brega": ("technobrega", "brega", "pop"),
    "pop punk": ("pop-punk", "punk-pop", "emo rock"),
    "emo": ("emo rock", "pop-punk", "punk-pop"),
    "technical death metal": ("death metal", "progressive metal", "metal"),
    "progressive death metal": ("death metal", "progressive metal", "metal"),
    "underground hip hop": ("underground hip-hop", "east coast hip hop", "hip-hop", "rap"),
    "underground hip-hop": ("underground hip hop", "east coast hip hop", "hip-hop", "rap"),
    "golden age hip hop": ("east coast hip hop", "classic hip-hop", "hip-hop", "rap"),
    "east coast rap": ("east coast hip hop", "new york rap", "hip-hop", "rap"),
    "jazz hop": ("jazz rap", "jazz-hop", "hip hop", "hip-hop"),
    "jazz rap": ("jazz hop", "jazz-hop", "hip hop", "hip-hop"),
    "country": ("new country", "rockin country", "country songs"),
    "dance": ("Dance", "house", "freestyle mix"),
    "freestyle": ("freestyle mix", "dance", "house"),
    "freestyle mix": ("freestyle", "dance", "house"),
    "disco": ("funk", "soul", "dance"),
    "punk": ("classic punk", "hardcore punk", "proto-punk"),
    "vaporwave": ("cityvapor", "electronic", "late night lo-fi"),
    "cityvapor": ("vaporwave", "electronic", "late night lo-fi"),
    "experimental": ("avant-garde", "strange", "alternative rock", "progressive metal"),
}


_SCENE_TERM_ALIASES: dict[str, tuple[str, ...]] = {
    "latin pop": ("latin pop", "latin", "pop"),
    "latin": ("latin", "latin pop"),
    "christian": ("christian", "ccm", "christian music", "christian rock", "contemporary christian"),
    "encouraging": ("encouraging", "positive", "hopeful"),
    "soundtrack": ("soundtrack", "movie score", "score", "ost"),
    "movie score": ("movie score", "soundtrack", "score", "ost"),
    "orchestral": ("orchestral", "orchestra", "orchestral epic", "classical"),
    "epic": ("epic", "soundtrack", "trailer music"),
    "country": ("country", "new country", "rockin country", "country songs"),
    "pop punk": ("pop punk", "pop-punk", "punk-pop", "emo rock"),
    "pop-punk": ("pop punk", "pop-punk", "punk-pop", "emo rock"),
    "emo": ("emo", "emo rock", "pop-punk", "punk-pop"),
    "punk": ("punk", "classic punk", "hardcore punk", "proto-punk"),
    "proto punk": ("proto-punk", "classic punk", "punk"),
    "hip hop": ("hip hop", "hip-hop", "rap"),
    "hip-hop": ("hip hop", "hip-hop", "rap"),
    "underground": ("underground hip-hop", "east coast hip hop"),
    "east coast": ("east coast hip hop", "east coast rap", "new york rap"),
    "golden age": ("classic hip-hop", "east coast hip hop", "hip-hop"),
    "gangsta": ("gangsta", "gangsta rap attitude", "west coast hip hop"),
    "technical": ("technical death metal", "progressive metal", "metal"),
    "death metal": ("death metal", "technical death metal", "brutal death metal"),
    "progressive metal": ("progressive metal", "technical death metal", "metal"),
    "metal": ("metal", "Metal", "hard rock"),
    "electronic": ("electronic", "Electronic", "synthpop", "synthwave"),
    "cyberpunk": ("synthwave", "electronic", "soundtrack"),
    "dance": ("dance", "Dance", "house", "freestyle mix"),
    "disco": ("disco", "funk", "soul", "dance"),
    "funk": ("funk", "Funk", "soul", "groovy"),
    "r&b": ("r&b", "R&B/Soul", "soul", "pop rnb"),
    "jazz": ("jazz", "Jazz", "hard bop", "avant-garde jazz"),
    "jazzy": ("jazz", "jazz hop", "jazz rap", "jazz-hop"),
    "jazz hop": ("jazz rap", "jazz-hop", "hip hop", "hip-hop"),
    "jazz rap": ("jazz hop", "jazz-hop", "hip hop", "hip-hop"),
    "rock": ("rock", "Rock", "alternative rock", "hard rock"),
    "guitar riff": ("rock", "alternative rock", "hard rock"),
    "freestyle": ("freestyle mix", "dance", "house"),
    "freestyle mix": ("freestyle", "dance", "house"),
    "vaporwave": ("vaporwave", "cityvapor", "electronic", "late night lo-fi"),
    "lo-fi": ("lo-fi", "late night lo-fi", "vaporwave"),
    "avant-garde": ("experimental", "strange", "alternative rock", "progressive metal"),
}


_QUERY_TEXT_STOPWORDS = frozenset(
    {
        "a", "an", "and", "any", "are", "as", "but", "by", "can", "could",
        "do", "else", "for", "from", "give", "have", "i", "in", "is", "it",
        "like", "me", "more", "of", "or", "other", "play", "song", "songs",
        "something", "that", "the", "this", "to", "track", "tracks", "what",
        "with", "you",
    }
)

_SOFT_YEAR_MATCH_WEIGHT = 8


def _norm_term(value: str) -> str:
    return " ".join(value.casefold().replace("_", " ").split())


def _expanded_tag_terms(tags: list[str]) -> set[str]:
    out: set[str] = set()
    pending: list[str] = []
    for value in tags:
        term = _norm_term(value)
        if not term:
            continue
        pending.append(term)
        if "/" in term:
            pending.extend(_norm_term(part) for part in term.split("/"))
    for term in pending:
        if not term:
            continue
        out.add(term)
        out.add(term.replace("-", " "))
        if " " in term:
            out.add(term.replace(" ", "-"))
        for alias in _TAG_ALIASES.get(term, ()):
            out.add(_norm_term(alias))
    return {term for term in out if term}


def _get_text_attr(obj: Any, name: str) -> str:
    if obj is None:
        return ""
    if isinstance(obj, dict):
        value = obj.get(name)
    else:
        value = getattr(obj, name, None)
    return str(value).strip() if value else ""


def _state_query_text(state: Any) -> str:
    parts: list[str] = []
    request = getattr(state, "current_request", None)
    for value in (
        getattr(state, "turn_intent", None),
        _get_text_attr(request, "summary"),
        _get_text_attr(request, "evidence_text"),
        getattr(state, "lyrical_theme", None),
    ):
        if value:
            parts.append(str(value))
    for fact in getattr(state, "facts", []) or []:
        fact_type = _enum_value(getattr(fact, "type", None))
        relation = _enum_value(getattr(fact, "relation", None))
        role = _enum_value(getattr(fact, "role", None))
        if fact_type != "attribute" and relation not in {"query_facet", "exact_target"}:
            continue
        if role == "rejected":
            continue
        value = str(getattr(fact, "value", "") or "").strip()
        if value:
            parts.append(value)
    seen: set[str] = set()
    out: list[str] = []
    for part in parts:
        text = " ".join(part.split())
        key = text.casefold()
        if text and key not in seen:
            seen.add(key)
            out.append(text)
    return "; ".join(out)


def _scene_terms_from_text(text: str) -> set[str]:
    norm = _norm_term(text)
    out: set[str] = set()
    for phrase, aliases in _SCENE_TERM_ALIASES.items():
        if phrase in norm:
            out.update(_norm_term(alias) for alias in aliases)

    tokens = [
        token
        for token in re.findall(r"[a-z0-9&]+", norm)
        if len(token) > 3 and token not in _QUERY_TEXT_STOPWORDS
    ]
    out.update(tokens)
    for n in (2, 3):
        for idx in range(len(tokens) - n + 1):
            phrase = " ".join(tokens[idx : idx + n])
            if any(key in phrase for key in _SCENE_TERM_ALIASES):
                out.add(phrase)
    return _expanded_tag_terms(sorted(out))


def _popularity_rank_for_catalog(catalog: Any) -> dict[str, int]:
    return {
        track_id: rank
        for rank, track_id in enumerate(catalog.popularity_sorted_track_ids())
    }


def _tag_popularity_pool(
    catalog: Any,
    *,
    tags: list[str],
    name: str,
    topk: int = 1000,
    release_range: Any | None = None,
    exclude_artist_ids: set[str] | None = None,
    expand_aliases: bool = False,
) -> BranchPool:
    query_terms = _expanded_tag_terms(tags) if expand_aliases else {_norm_term(t) for t in tags}
    query_terms = {term for term in query_terms if term}
    if not query_terms:
        return BranchPool(name, [])
    pop_rank = _popularity_rank_for_catalog(catalog)
    exclude_artist_ids = exclude_artist_ids or set()
    lo = getattr(release_range, "start", None) if release_range is not None else None
    hi = getattr(release_range, "end", None) if release_range is not None else None
    scored: list[tuple[int, int, str]] = []
    for track_id in catalog.all_track_ids():
        if exclude_artist_ids:
            artist_id = catalog.artist_id_of(track_id)
            if artist_id in exclude_artist_ids:
                continue
        if lo is not None or hi is not None:
            year = catalog.release_year_of(track_id)
            if year is None:
                continue
            if lo is not None and year < lo:
                continue
            if hi is not None and year > hi:
                continue
        track_terms = _expanded_tag_terms(catalog.tag_list(track_id))
        overlap = len(query_terms & track_terms)
        if not overlap:
            continue
        scored.append((overlap, pop_rank.get(track_id, 10**9), track_id))
    scored.sort(key=lambda item: (-item[0], item[1], item[2]))
    n = min(topk, len(scored))
    return BranchPool(
        name,
        [(track_id, float(n - idx)) for idx, (_overlap, _rank, track_id) in enumerate(scored[:topk])],
    )


def _year_match_bonus(release_range: Any | None, year: int | None) -> int:
    if release_range is None or year is None:
        return 0
    lo = getattr(release_range, "start", None)
    hi = getattr(release_range, "end", None)
    if lo is None and hi is None:
        return 0
    if lo is not None and year < lo:
        return -1
    if hi is not None and year > hi:
        return -1
    return 1


def _query_text_tag_popularity_pool(
    catalog: Any,
    *,
    state: Any,
    name: str,
    topk: int = 1000,
    exclude_artist_ids: set[str] | None = None,
) -> BranchPool:
    query_text = _state_query_text(state)
    query_terms = _scene_terms_from_text(query_text)
    if not query_terms:
        return BranchPool(name, [])
    pop_rank = _popularity_rank_for_catalog(catalog)
    exclude_artist_ids = exclude_artist_ids or set()
    release_range = getattr(state, "release_year_range", None)
    scored: list[tuple[int, int, int, int, str]] = []
    for track_id in catalog.all_track_ids():
        if exclude_artist_ids:
            artist_id = catalog.artist_id_of(track_id)
            if artist_id in exclude_artist_ids:
                continue
        tag_terms = _expanded_tag_terms(catalog.tag_list(track_id))
        text = _norm_term(catalog.track_text(track_id, max_tags=20))
        overlap = query_terms & tag_terms
        phrase_hits = {
            term for term in query_terms if " " in term and term in text
        }
        if not overlap and not phrase_hits:
            continue
        tag_score = len(overlap) * 4 + len(phrase_hits) * 2
        year_bonus = _year_match_bonus(release_range, catalog.release_year_of(track_id))
        score = tag_score + year_bonus * _SOFT_YEAR_MATCH_WEIGHT
        scored.append((score, tag_score, year_bonus, pop_rank.get(track_id, 10**9), track_id))
    scored.sort(key=lambda item: (-item[0], -item[1], -item[2], item[3], item[4]))
    n = min(topk, len(scored))
    return BranchPool(
        name,
        [
            (track_id, float(n - idx))
            for idx, (_score, _tag_score, _year_bonus, _rank, track_id) in enumerate(scored[:topk])
        ],
    )


_GENERIC_SCENE_TERMS = {
    "alternative",
    "dance",
    "electronic",
    "hip hop",
    "hip-hop",
    "metal",
    "pop",
    "rap",
    "rock",
}


def _scene_term_weight(term: str) -> int:
    if term in _GENERIC_SCENE_TERMS:
        return 2
    if " " in term or "-" in term or "&" in term:
        return 8
    return 4


def _scene_era_tag_popularity_v2_pool(
    catalog: Any,
    *,
    state: Any,
    name: str,
    topk: int = 1000,
    exclude_artist_ids: set[str] | None = None,
    extra_terms: set[str] | None = None,
) -> BranchPool:
    query_terms = _scene_terms_from_text(_state_query_text(state))
    if extra_terms:
        query_terms |= _expanded_tag_terms(sorted(extra_terms))
    query_terms = {term for term in query_terms if term}
    if not query_terms:
        return BranchPool(name, [])

    pop_rank = _popularity_rank_for_catalog(catalog)
    exclude_artist_ids = exclude_artist_ids or set()
    release_range = getattr(state, "release_year_range", None)
    scored: list[tuple[int, int, int, int, str]] = []
    for track_id in catalog.all_track_ids():
        if exclude_artist_ids:
            artist_id = catalog.artist_id_of(track_id)
            if artist_id in exclude_artist_ids:
                continue

        tag_terms = _expanded_tag_terms(catalog.tag_list(track_id))
        text = _norm_term(catalog.track_text(track_id, max_tags=40))
        overlap = query_terms & tag_terms
        phrase_hits = {
            term for term in query_terms if " " in term and term in text
        }
        if not overlap and not phrase_hits:
            continue

        term_score = sum(_scene_term_weight(term) for term in overlap)
        phrase_score = sum(_scene_term_weight(term) for term in phrase_hits)
        specificity_bonus = 5 if len(overlap | phrase_hits) >= 2 else 0
        year_bonus = _year_match_bonus(release_range, catalog.release_year_of(track_id))
        score = term_score + phrase_score + specificity_bonus + year_bonus * 5
        scored.append((score, term_score + phrase_score, year_bonus, pop_rank.get(track_id, 10**9), track_id))

    scored.sort(key=lambda item: (-item[0], -item[1], -item[2], item[3], item[4]))
    n = min(topk, len(scored))
    return BranchPool(
        name,
        [
            (track_id, float(n - idx))
            for idx, (_score, _term_score, _year_bonus, _rank, track_id) in enumerate(scored[:topk])
        ],
    )


def _state_positive_tags(qu, rs, *, include_anchor_tags: bool = True) -> list[str]:
    tags = list(qu.compiler._positive_mention_values(rs.state, "tag"))
    if include_anchor_tags:
        tags.extend(qu.compiler._top_anchor_tags(rs, n=8))
    seen: set[str] = set()
    out: list[str] = []
    for tag in tags:
        key = _norm_term(tag)
        if key and key not in seen:
            seen.add(key)
            out.append(tag)
    return out


def _same_album_fanout_pool(qu, rs, *, topk: int = 1000) -> BranchPool:
    anchor_ids = qu.compiler._anchor_track_ids(rs.state)
    album_ids = {
        album_id
        for track_id in anchor_ids
        if (album_id := qu.compiler.catalog.album_id_of(track_id))
    }
    if not album_ids:
        return BranchPool("analysis.same_album_fanout", [])
    pop_rank = qu.compiler._popularity_rank()
    hits: list[tuple[int, str]] = []
    anchor_set = set(anchor_ids)
    for track_id in qu.compiler.catalog.all_track_ids():
        if track_id in anchor_set:
            continue
        if qu.compiler.catalog.album_id_of(track_id) in album_ids:
            hits.append((pop_rank.get(track_id, 10**9), track_id))
    hits.sort(key=lambda item: (item[0], item[1]))
    n = min(topk, len(hits))
    return BranchPool(
        "analysis.same_album_fanout",
        [(track_id, float(n - idx)) for idx, (_rank, track_id) in enumerate(hits[:topk])],
    )


def _artist_tag_neighbor_pool(qu, rs, *, topk: int = 1000) -> BranchPool:
    artist_ids: list[str] = []
    seen: set[str] = set()
    for target in getattr(rs, "resolved_targets", []) or []:
        if getattr(target, "kind", None) != "artist":
            continue
        artist_id = getattr(target, "entity_id", None)
        if artist_id and artist_id not in seen:
            seen.add(artist_id)
            artist_ids.append(artist_id)
    if not artist_ids:
        return BranchPool("analysis.artist_tag_neighbor_popularity", [])
    counter: dict[str, int] = {}
    pop_rank = qu.compiler._popularity_rank()
    for artist_id in artist_ids[:5]:
        tracks = sorted(
            qu.compiler.catalog.tracks_by_artist_id(artist_id),
            key=lambda tid: pop_rank.get(tid, 10**9),
        )[:20]
        for track_id in tracks:
            for tag in qu.compiler.catalog.tag_list(track_id):
                key = _norm_term(tag)
                if key:
                    counter[key] = counter.get(key, 0) + 1
    tags = [
        tag for tag, _count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:12]
    ]
    target_mode = _enum_value(getattr(rs.state, "target_artist_mode", ""))
    exclude_artists = set(artist_ids) if target_mode == "new_artist" else set()
    return _tag_popularity_pool(
        qu.compiler.catalog,
        tags=tags,
        name="analysis.artist_tag_neighbor_popularity",
        topk=topk,
        exclude_artist_ids=exclude_artists,
        expand_aliases=True,
    )


def _artist_neighbor_scene_v2_pool(qu, rs, *, topk: int = 1000) -> BranchPool:
    artist_ids: list[str] = []
    seen_artists: set[str] = set()
    for target in getattr(rs, "resolved_targets", []) or []:
        if getattr(target, "kind", None) != "artist":
            continue
        artist_id = getattr(target, "entity_id", None)
        if artist_id and artist_id not in seen_artists:
            seen_artists.add(artist_id)
            artist_ids.append(artist_id)
    for track_id in qu.compiler._anchor_track_ids(rs.state):
        artist_id = qu.compiler.catalog.artist_id_of(track_id)
        if artist_id and artist_id not in seen_artists:
            seen_artists.add(artist_id)
            artist_ids.append(artist_id)

    if not artist_ids:
        return BranchPool("analysis.artist_neighbor_scene_v2", [])

    pop_rank = qu.compiler._popularity_rank()
    artist_terms: set[str] = set()
    for artist_id in artist_ids[:6]:
        tracks = sorted(
            qu.compiler.catalog.tracks_by_artist_id(artist_id),
            key=lambda tid: pop_rank.get(tid, 10**9),
        )[:25]
        for track_id in tracks:
            artist_terms.update(_expanded_tag_terms(qu.compiler.catalog.tag_list(track_id)))

    target_mode = _enum_value(getattr(rs.state, "target_artist_mode", ""))
    exclude_artists = set(artist_ids) if target_mode == "new_artist" else set()
    return _scene_era_tag_popularity_v2_pool(
        qu.compiler.catalog,
        state=rs.state,
        name="analysis.artist_neighbor_scene_v2",
        topk=topk,
        exclude_artist_ids=exclude_artists,
        extra_terms=artist_terms,
    )


def _artist_ids_from_resolved_and_anchors(qu, rs) -> list[str]:
    artist_ids: list[str] = []
    seen_artists: set[str] = set()
    for target in getattr(rs, "resolved_targets", []) or []:
        if getattr(target, "kind", None) != "artist":
            continue
        artist_id = getattr(target, "entity_id", None)
        if artist_id and artist_id not in seen_artists:
            seen_artists.add(artist_id)
            artist_ids.append(artist_id)
    for track_id in qu.compiler._anchor_track_ids(rs.state):
        artist_id = qu.compiler.catalog.artist_id_of(track_id)
        if artist_id and artist_id not in seen_artists:
            seen_artists.add(artist_id)
            artist_ids.append(artist_id)
    return artist_ids


def _artist_neighbor_scene_weighted_v3_pool(qu, rs, *, topk: int = 1000) -> BranchPool:
    artist_ids = _artist_ids_from_resolved_and_anchors(qu, rs)
    if not artist_ids:
        return BranchPool("analysis.artist_neighbor_scene_weighted_v3", [])

    pop_rank = qu.compiler._popularity_rank()
    anchor_counter: Counter[str] = Counter()
    for artist_id in artist_ids[:6]:
        tracks = sorted(
            qu.compiler.catalog.tracks_by_artist_id(artist_id),
            key=lambda tid: pop_rank.get(tid, 10**9),
        )[:25]
        for track_id in tracks:
            anchor_counter.update(_expanded_tag_terms(qu.compiler.catalog.tag_list(track_id)))
    if not anchor_counter:
        return BranchPool("analysis.artist_neighbor_scene_weighted_v3", [])

    state_terms = _scene_terms_from_text(_state_query_text(rs.state))
    target_mode = _enum_value(getattr(rs.state, "target_artist_mode", ""))
    exclude_artists = set(artist_ids) if target_mode == "new_artist" else set()
    anchor_track_ids = set(qu.compiler._anchor_track_ids(rs.state))
    release_range = getattr(rs.state, "release_year_range", None)
    scored: list[tuple[int, int, int, int, str]] = []
    for track_id in qu.compiler.catalog.all_track_ids():
        if track_id in anchor_track_ids:
            continue
        if exclude_artists:
            artist_id = qu.compiler.catalog.artist_id_of(track_id)
            if artist_id in exclude_artists:
                continue
        tag_terms = _expanded_tag_terms(qu.compiler.catalog.tag_list(track_id))
        anchor_overlap = tag_terms & set(anchor_counter)
        state_overlap = tag_terms & state_terms
        if not anchor_overlap and not state_overlap:
            continue

        anchor_score = sum(
            min(anchor_counter[term], 8) * _scene_term_weight(term)
            for term in anchor_overlap
        )
        state_score = sum(_scene_term_weight(term) for term in state_overlap)
        specific_overlap = {
            term
            for term in anchor_overlap | state_overlap
            if term not in _GENERIC_SCENE_TERMS
        }
        specificity_bonus = 8 if len(specific_overlap) >= 2 else 0
        year_bonus = _year_match_bonus(release_range, qu.compiler.catalog.release_year_of(track_id))
        score = anchor_score + state_score + specificity_bonus + year_bonus * 3
        scored.append((score, anchor_score + state_score, year_bonus, pop_rank.get(track_id, 10**9), track_id))

    scored.sort(key=lambda item: (-item[0], -item[1], -item[2], item[3], item[4]))
    n = min(topk, len(scored))
    return BranchPool(
        "analysis.artist_neighbor_scene_weighted_v3",
        [
            (track_id, float(n - idx))
            for idx, (_score, _term_score, _year_bonus, _rank, track_id) in enumerate(scored[:topk])
        ],
    )


def _analysis_branch_pools(qu, rs, variant: Variant) -> list[BranchPool]:
    pools: list[BranchPool] = []
    for branch in variant.analysis_branches:
        if branch == "tag_popularity":
            pools.append(
                _tag_popularity_pool(
                    qu.compiler.catalog,
                    tags=_state_positive_tags(qu, rs),
                    name="analysis.tag_popularity",
                )
            )
        elif branch == "tag_popularity_alias":
            pools.append(
                _tag_popularity_pool(
                    qu.compiler.catalog,
                    tags=_state_positive_tags(qu, rs),
                    name="analysis.tag_popularity_alias",
                    expand_aliases=True,
                )
            )
        elif branch == "era_tag_popularity":
            pools.append(
                _tag_popularity_pool(
                    qu.compiler.catalog,
                    tags=_state_positive_tags(qu, rs),
                    name="analysis.era_tag_popularity",
                    release_range=rs.state.release_year_range,
                    expand_aliases=True,
                )
            )
        elif branch == "same_album_fanout":
            pools.append(_same_album_fanout_pool(qu, rs))
        elif branch == "artist_tag_neighbor_popularity":
            pools.append(_artist_tag_neighbor_pool(qu, rs))
        elif branch == "query_text_tag_popularity":
            target_mode = _enum_value(getattr(rs.state, "target_artist_mode", ""))
            exclude_artists = _anchor_artist_ids(qu, rs) if target_mode == "new_artist" else set()
            pools.append(
                _query_text_tag_popularity_pool(
                    qu.compiler.catalog,
                    state=rs.state,
                    name="analysis.query_text_tag_popularity",
                    exclude_artist_ids=exclude_artists,
                )
            )
        elif branch == "scene_era_tag_popularity_v2":
            target_mode = _enum_value(getattr(rs.state, "target_artist_mode", ""))
            exclude_artists = _anchor_artist_ids(qu, rs) if target_mode == "new_artist" else set()
            pools.append(
                _scene_era_tag_popularity_v2_pool(
                    qu.compiler.catalog,
                    state=rs.state,
                    name="analysis.scene_era_tag_popularity_v2",
                    exclude_artist_ids=exclude_artists,
                )
            )
        elif branch == "artist_neighbor_scene_v2":
            pools.append(_artist_neighbor_scene_v2_pool(qu, rs))
        elif branch == "artist_neighbor_scene_weighted_v3":
            pools.append(_artist_neighbor_scene_weighted_v3_pool(qu, rs))
        else:
            raise KeyError(f"unknown analysis branch: {branch}")
    return pools


def _analysis_branch_pools_for_variant(qu, rs, variant: Variant) -> list[BranchPool]:
    return _rerank_branch_pools(
        qu,
        rs,
        _analysis_branch_pools(qu, rs, variant),
        variant.branch_local_rules,
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
        centroid_fields = [CLAP_AUDIO, SIGLIP_IMAGE, "cf_bpr"]
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
    base_encoders = copy.deepcopy(dict(base_qu_kwargs.get("encoders") or {}))
    if "siglip2_text" not in base_encoders and "clap_text" in base_encoders:
        clap_cfg = base_encoders["clap_text"]
        if clap_cfg.get("backend") == "modal_multimodal":
            siglip_cfg = copy.deepcopy(clap_cfg)
            siglip_cfg["method"] = "embed_siglip_text"
            base_encoders["siglip2_text"] = siglip_cfg
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
    protected_pools: list[BranchPool] | None = None,
    include_branch_pools: bool = False,
) -> dict[str, Any]:
    state = _state_from_audit(row)
    played = [tf.track_id for tf in state.track_feedback]
    rs = qu.resolver.resolve(state, played_track_ids=played)
    use_compiler_pools = variant is None or variant.compiler_pools
    if use_compiler_pools:
        result = qu.compiler._compile(rs, user_id=None)
        branch_pools = _rerank_branch_pools(
            qu,
            rs,
            result.branch_pools,
            () if variant is None else variant.branch_local_rules,
        )
        final_rank = _rank(result.ranked, target)
        fused_rank = _rank([track_id for track_id, _score in result.fused], target)
    else:
        branch_pools = []
        final_rank = None
        fused_rank = None
    if variant is not None and variant.analysis_branches:
        branch_pools.extend(_analysis_branch_pools_for_variant(qu, rs, variant))
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
    if protected_pools is not None:
        out.update(_additive_metrics_for_pools(protected_pools, branch_pools, target))
    if include_branch_pools:
        out["_branch_pools"] = branch_pools
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


def _additive_summary(rows: list[dict[str, Any]], variant: str) -> dict[str, Any]:
    scoped = [row for row in rows if row["variant"] == variant]
    n = len(scoped)
    out: dict[str, Any] = {"variant": variant, "n": n}
    if n == 0:
        return out
    for k in ADDITIVE_KS:
        out[f"protected_union@{k}"] = sum(row[f"protected_union@{k}"] for row in scoped) / n
        out[f"branch_only@{k}"] = sum(row[f"branch_only@{k}"] for row in scoped) / n
        out[f"additive_union@{k}"] = sum(row[f"additive_union@{k}"] for row in scoped) / n
    out["additive_rescued@20"] = sum(
        (not row["protected_union@20"]) and row["branch_only@20"] for row in scoped
    )
    out["additive_regressed@20"] = sum(
        row["protected_union@20"] and not row["additive_union@20"] for row in scoped
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
    additive_fields = [
        "protected_best_branch",
        "protected_best_branch_rank",
        "branch_only_best_branch",
        "branch_only_best_branch_rank",
        "additive_best_branch",
        "additive_best_branch_rank",
    ]
    additive_fields.extend(f"protected_union@{k}" for k in ADDITIVE_KS)
    additive_fields.extend(f"branch_only@{k}" for k in ADDITIVE_KS)
    additive_fields.extend(f"additive_union@{k}" for k in ADDITIVE_KS)
    if any(any(field in row for field in additive_fields) for row in rows):
        fieldnames.extend(additive_fields)
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


def _summary_metric(row: dict[str, Any], metric: str) -> Any:
    value = row.get(metric)
    if value is not None:
        return value
    if metric.startswith("union@"):
        return row.get(f"additive_{metric}")
    return None


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
                union20=_fmt(_summary_metric(row, "union@20")),
                union50=_fmt(_summary_metric(row, "union@50")),
                union100=_fmt(_summary_metric(row, "union@100")),
                union200=_fmt(_summary_metric(row, "union@200")),
                union1000=_fmt(_summary_metric(row, "union@1000")),
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
    parser.add_argument("--baseline-pools-json", type=Path)
    parser.add_argument("--baseline-trace", type=Path)
    parser.add_argument("--write-baseline-pools-json", type=Path)
    parser.add_argument("--baseline-pool-depth", type=int, default=100)
    parser.add_argument("--write-branch-pools-json", type=Path)
    parser.add_argument("--branch-pool-depth", type=int, default=1000)
    parser.add_argument("--write-ledger-json", type=Path)
    parser.add_argument("--write-minimal-subset-json", type=Path)
    parser.add_argument("--extract-baseline-only", action="store_true")
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

    baseline_pools_by_sample: dict[str, list[BranchPool]] = {}
    if args.baseline_trace:
        if not args.baseline_trace.exists():
            raise SystemExit(f"missing baseline trace: {args.baseline_trace}")
        baseline_pools_by_sample = _extract_trace_baseline_pools(
            args.baseline_trace,
            selected_turn_meta,
            depth=args.baseline_pool_depth,
        )
        missing_baseline = [
            sid for sid in sample_ids if sid not in baseline_pools_by_sample
        ]
        if missing_baseline:
            raise SystemExit(f"missing baseline trace rows: {missing_baseline}")
        if args.write_baseline_pools_json:
            _write_baseline_pools_json(
                args.write_baseline_pools_json,
                pools_by_sample=baseline_pools_by_sample,
                sample_ids=sample_ids,
                source_trace=args.baseline_trace,
                depth=args.baseline_pool_depth,
            )
    if args.baseline_pools_json:
        if not args.baseline_pools_json.exists():
            raise SystemExit(f"missing baseline pools JSON: {args.baseline_pools_json}")
        baseline_pools_by_sample = _load_baseline_pools_json(args.baseline_pools_json)
        missing_baseline = [
            sid for sid in sample_ids if sid not in baseline_pools_by_sample
        ]
        if missing_baseline:
            raise SystemExit(f"missing baseline pools rows: {missing_baseline}")
    if args.extract_baseline_only:
        if not args.baseline_trace:
            raise SystemExit("--extract-baseline-only requires --baseline-trace")
        if not args.write_baseline_pools_json:
            raise SystemExit("--extract-baseline-only requires --write-baseline-pools-json")
        print(
            json.dumps(
                {
                    "samples": len(sample_ids),
                    "baseline_pools_json": str(args.write_baseline_pools_json),
                    "depth": args.baseline_pool_depth,
                },
                indent=2,
            )
        )
        return

    if not args.lancedb_uri.exists():
        raise SystemExit(f"missing LanceDB URI: {args.lancedb_uri}")

    variant_names = args.variants or list(DEFAULT_VARIANTS)
    base_cfg = OmegaConf.load(args.config)
    base_qu_kwargs = OmegaConf.to_container(base_cfg["qu_kwargs"], resolve=True)
    _resolve_vllm_endpoints_in_qu_kwargs(base_qu_kwargs)

    rows: list[dict[str, Any]] = []
    capture_branch_pools = bool(
        args.write_branch_pools_json
        or args.write_ledger_json
        or args.write_minimal_subset_json
    )
    candidate_pools_by_variant: dict[str, dict[str, list[BranchPool]]] = {}
    for variant_name in variant_names:
        variant = VARIANTS[variant_name]
        if not args.quiet:
            print(f"building variant: {variant.name}", flush=True)
        qu_kwargs = _variant_qu_kwargs(base_qu_kwargs, variant, args.lancedb_uri)
        qu = build_v0plus_compiler_qu(qu_kwargs)
        if capture_branch_pools:
            candidate_pools_by_variant[variant.name] = {}
        for idx, sid in enumerate(sample_ids, start=1):
            meta = turn_meta[sid]
            if not args.quiet:
                print(f"  [{idx}/{len(sample_ids)}] {sid}", flush=True)
            result = _compile_variant(
                qu,
                audit_rows[sid],
                meta["gt_track_id"],
                variant,
                protected_pools=baseline_pools_by_sample.get(sid),
                include_branch_pools=capture_branch_pools,
            )
            branch_pools = result.pop("_branch_pools", None)
            if branch_pools is not None:
                candidate_pools_by_variant[variant.name][sid] = branch_pools
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

    additive_mode = bool(baseline_pools_by_sample)
    summary = [_baseline_summary(selected_turn_meta, sample_ids)]
    if additive_mode:
        summary.extend(_additive_summary(rows, name) for name in variant_names)
    else:
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
        "additive_mode": additive_mode,
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

    if args.write_branch_pools_json:
        args.write_branch_pools_json.parent.mkdir(parents=True, exist_ok=True)
        if len(variant_names) == 1:
            variant = variant_names[0]
            pools_payload = _serialize_variant_pools(
                variant=variant,
                sample_ids=sample_ids,
                pools_by_sample=candidate_pools_by_variant.get(variant, {}),
                depth=args.branch_pool_depth,
            )
        else:
            pools_payload = {
                "depth": args.branch_pool_depth,
                "samples": sample_ids,
                "variants": {
                    variant: _serialize_variant_pools(
                        variant=variant,
                        sample_ids=sample_ids,
                        pools_by_sample=candidate_pools_by_variant.get(variant, {}),
                        depth=args.branch_pool_depth,
                    )
                    for variant in variant_names
                },
            }
        args.write_branch_pools_json.write_text(
            json.dumps(pools_payload, ensure_ascii=False, indent=2) + "\n"
        )

    ledger_payload: dict[str, Any] | None = None
    subset_payload: dict[str, Any] | None = None
    if args.write_ledger_json or args.write_minimal_subset_json:
        if not baseline_pools_by_sample:
            raise SystemExit("--write-ledger-json requires --baseline-pools-json")
        if len(variant_names) != 1:
            raise SystemExit("ledger/subset output requires exactly one --variant")
        variant = variant_names[0]
        candidate_pools_by_sample = candidate_pools_by_variant.get(variant, {})
        ledger_payload = _all_on_ledger(
            sample_ids=sample_ids,
            turn_meta=selected_turn_meta,
            protected_pools_by_sample=baseline_pools_by_sample,
            candidate_pools_by_sample=candidate_pools_by_sample,
            ks=ADDITIVE_KS,
        )
        ledger_payload["variant"] = variant
        if args.write_ledger_json:
            args.write_ledger_json.parent.mkdir(parents=True, exist_ok=True)
            args.write_ledger_json.write_text(
                json.dumps(ledger_payload, ensure_ascii=False, indent=2) + "\n"
            )
        subset_payload = _greedy_minimal_subset(
            sample_ids=sample_ids,
            turn_meta=selected_turn_meta,
            protected_pools_by_sample=baseline_pools_by_sample,
            candidate_pools_by_sample=candidate_pools_by_sample,
            ks=ADDITIVE_KS,
        )
        subset_payload["variant"] = variant
        if args.write_minimal_subset_json:
            args.write_minimal_subset_json.parent.mkdir(parents=True, exist_ok=True)
            args.write_minimal_subset_json.write_text(
                json.dumps(subset_payload, ensure_ascii=False, indent=2) + "\n"
            )

    print(
        json.dumps(
            {
                "summary": payload["summary"],
                "json": str(output_json),
                "md": str(output_md),
                "csv": str(output_csv),
                "branch_pools_json": (
                    str(args.write_branch_pools_json)
                    if args.write_branch_pools_json
                    else None
                ),
                "ledger_json": str(args.write_ledger_json) if args.write_ledger_json else None,
                "minimal_subset_json": (
                    str(args.write_minimal_subset_json)
                    if args.write_minimal_subset_json
                    else None
                ),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
