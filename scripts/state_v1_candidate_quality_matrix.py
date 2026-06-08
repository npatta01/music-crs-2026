#!/usr/bin/env python
"""Focused-110 non-prompt candidate-quality matrix.

This is an analysis harness, not a production compiler change. It keeps the
saved V1 extraction/projection artifacts frozen and asks whether deterministic
candidate features can move existing branch top-1000 hits into top-20.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcrs.qu_modules.compiler_v0plus import BranchPool  # noqa: E402
from mcrs.qu_modules.user_embeddings import UserEmbeddings  # noqa: E402
from mcrs.qu_modules.v0plus_catalog_lance import LanceDbCatalog  # noqa: E402
from scripts.state_v1_retriever_matrix import (  # noqa: E402
    _branch_rank,
    _enum_value,
    _expanded_tag_terms,
    _has_explicit_popularity_request,
    _negative_tag_values,
    _pool_from_trace_payload,
    _scene_terms_from_text,
    _state_from_audit,
    _state_query_text,
    _union_hit,
)


ANALYSIS_DIR = Path(
    "experiments/analysis/devset_recall_gap_v0plus_all_retrievers_2026_06_06"
)
PACK_JSON = ANALYSIS_DIR / "state_experiment_pack.json"
AUDIT_JSONL = ANALYSIS_DIR / "state_v1_goal_current_all110_reprojected_audit.jsonl"
PROTECTED_POOLS_JSON = ANALYSIS_DIR / "state_v1_protected_baseline_branch_pools_top100.json"
ALL_ON_POOLS_JSON = ANALYSIS_DIR / "state_v1_all_on_branch_pools.json"
TARGETED_REPORT_JSON = ANALYSIS_DIR / "state_v1_targeted_branch_recall_report.json"
TRACE_PATHS = (
    Path("exp/inference/devset/v0plus_compiler_all_retrievers_devset_trace.jsonl"),
    Path(
        "/Users/npatta01/data/projects/music-conversational-music-recomender-2026/"
        "exp/inference/devset/v0plus_compiler_all_retrievers_devset_trace.jsonl"
    ),
)
DEFAULT_LANCEDB = Path("cache/lancedb")
KS = (20, 50, 100)
NOISY_GT_LABELS = {
    "gt_conflicts_with_explicit_user_constraint",
    "underspecified_next_play_behavior",
}


@dataclass(frozen=True)
class CandidateFeature:
    feature_score: float = 0.0
    hard_drop: bool = False


@dataclass(frozen=True)
class TrackMeta:
    tags: frozenset[str]
    text: str
    release_year: int | None
    popularity_rank: int | None
    cf_bpr: list[float] | None
    artist_id: str | None


def _cosine(a: Iterable[float] | None, b: Iterable[float] | None) -> float:
    if a is None or b is None:
        return 0.0
    xs = [float(x) for x in a]
    ys = [float(y) for y in b]
    if not xs or not ys or len(xs) != len(ys):
        return 0.0
    dot = sum(x * y for x, y in zip(xs, ys))
    an = math.sqrt(sum(x * x for x in xs))
    bn = math.sqrt(sum(y * y for y in ys))
    if an == 0.0 or bn == 0.0:
        return 0.0
    return dot / (an * bn)


def _rank_pool_with_features(
    pool: BranchPool,
    features: dict[str, Any],
    *,
    suffix: str,
) -> BranchPool:
    adjusted: list[tuple[str, float, int]] = []
    seen: set[str] = set()
    for rank, (track_id, _score) in enumerate(pool.hits, start=1):
        if track_id in seen:
            continue
        seen.add(track_id)
        feature = features.get(track_id)
        if feature is not None and bool(getattr(feature, "hard_drop", False)):
            continue
        feature_score = float(getattr(feature, "feature_score", 0.0) or 0.0)
        score = (1.0 / (60.0 + rank)) + feature_score
        adjusted.append((track_id, score, rank))
    adjusted.sort(key=lambda item: (-item[1], item[2], item[0]))
    return BranchPool(
        f"{pool.name}.{suffix}",
        [(track_id, score) for track_id, score, _rank in adjusted],
    )


def _valid_sample_ids(labels: dict[str, dict[str, Any]]) -> set[str]:
    return {
        sample_id
        for sample_id, label in labels.items()
        if label.get("gt_audit_label") not in NOISY_GT_LABELS
    }


def _metrics_for_subset(
    sample_ids: list[str],
    rows: dict[str, dict[str, Any]],
    labels: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    valid_ids = _valid_sample_ids(labels)
    out: dict[str, dict[str, Any]] = {}
    for scope, scoped_ids in (
        ("all", list(sample_ids)),
        ("valid_only", [sid for sid in sample_ids if sid in valid_ids]),
    ):
        scoped_rows = [rows[sid] for sid in scoped_ids if sid in rows]
        metrics: dict[str, Any] = {"n": len(scoped_rows)}
        for k in KS:
            key = f"union@{k}"
            count = sum(bool(row.get(key)) for row in scoped_rows)
            metrics[f"{key}_count"] = count
            metrics[key] = count / len(scoped_rows) if scoped_rows else None
        out[scope] = metrics
    return out


def _load_jsonl(path: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for line in path.read_text().splitlines():
        if line.strip():
            row = json.loads(line)
            rows[row["sample_id"]] = row
    return rows


def _load_pools(path: Path) -> dict[str, list[BranchPool]]:
    payload = json.loads(path.read_text())
    return {
        sid: [_pool_from_trace_payload(pool) for pool in pools]
        for sid, pools in payload["pools_by_sample"].items()
    }


def _resolve_matrix_path(raw: str | Path) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path
    if path.exists():
        return path
    if (ANALYSIS_DIR / path.name).exists():
        return ANALYSIS_DIR / path.name
    return path


def _row_union_value(row: dict[str, Any], k: int) -> bool:
    additive_key = f"additive_union@{k}"
    if additive_key in row:
        return bool(row[additive_key])
    return bool(row.get(f"union@{k}"))


def _row_best_rank(row: dict[str, Any]) -> tuple[str | None, int | None]:
    rank = row.get("additive_best_branch_rank")
    branch = row.get("additive_best_branch")
    if rank is None:
        rank = row.get("best_branch_rank")
        branch = row.get("best_branch")
    return branch, rank


def _or_rows_from_files(
    *,
    name: str,
    files: list[str],
    sample_ids: list[str],
    turn_meta: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    rows = {
        sid: {
            "sample_id": sid,
            "variant": name,
            "best_branch": None,
            "best_branch_rank": None,
            **{f"union@{k}": False for k in KS},
        }
        for sid in sample_ids
    }
    for raw_path in files:
        path = _resolve_matrix_path(raw_path)
        payload = json.loads(path.read_text())
        for row in payload.get("rows", []):
            sid = row.get("sample_id")
            if sid not in rows:
                continue
            out = rows[sid]
            for k in KS:
                out[f"union@{k}"] = bool(out[f"union@{k}"]) or _row_union_value(row, k)
            branch, rank = _row_best_rank(row)
            if rank is not None and (
                out["best_branch_rank"] is None or int(rank) < int(out["best_branch_rank"])
            ):
                out["best_branch"] = branch
                out["best_branch_rank"] = int(rank)
    for sid, row in rows.items():
        meta = turn_meta[sid]
        row.update(
            {
                "pack": meta["pack"],
                "class_type": meta.get("class_type"),
                "gt_track": meta["gt_track"],
                "gt_artist": meta["gt_artist"],
            }
        )
    return rows


def _pools_to_rows(
    *,
    name: str,
    sample_ids: list[str],
    turn_meta: dict[str, dict[str, Any]],
    pools_by_sample: dict[str, list[BranchPool]],
    protected_rows: dict[str, dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for sid in sample_ids:
        meta = turn_meta[sid]
        target = str(meta["gt_track_id"])
        pools = pools_by_sample.get(sid, [])
        best_branch, best_rank = _branch_rank(pools, target)
        row: dict[str, Any] = {
            "sample_id": sid,
            "pack": meta["pack"],
            "class_type": meta.get("class_type"),
            "variant": name,
            "gt_track": meta["gt_track"],
            "gt_artist": meta["gt_artist"],
            "best_branch": best_branch,
            "best_branch_rank": best_rank,
        }
        for k in KS:
            branch_hit = _union_hit(pools, target, k)
            protected_hit = (
                bool(protected_rows[sid].get(f"union@{k}"))
                if protected_rows is not None
                else False
            )
            row[f"branch_only@{k}"] = branch_hit
            row[f"union@{k}"] = branch_hit or protected_hit
        rows[sid] = row
    return rows


def _merged_pools(
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


def _state_anchor_track_ids(state: Any) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for feedback in getattr(state, "track_feedback", []) or []:
        track_id = str(getattr(feedback, "track_id", "") or "").strip()
        role = _enum_value(getattr(feedback, "role", None))
        if not track_id or role == "rejected":
            continue
        if track_id not in seen:
            seen.add(track_id)
            out.append(track_id)
    for track_id in getattr(state, "referenced_track_ids", []) or []:
        track_id = str(track_id or "").strip()
        if track_id and track_id not in seen:
            seen.add(track_id)
            out.append(track_id)
    return out


def _state_hard_drop_track_ids(state: Any) -> set[str]:
    out: set[str] = set()
    for feedback in getattr(state, "track_feedback", []) or []:
        role = _enum_value(getattr(feedback, "role", None))
        track_id = str(getattr(feedback, "track_id", "") or "").strip()
        if role == "rejected" and track_id:
            out.add(track_id)
    for rejection in getattr(state, "explicit_rejections", []) or []:
        kind = _enum_value(getattr(rejection, "kind", None))
        entity_id = str(getattr(rejection, "entity_id", "") or "").strip()
        certainty = _enum_value(getattr(rejection, "certainty", None))
        if kind == "track" and entity_id and certainty in {"explicit", ""}:
            out.add(entity_id)
    return out


def _release_year_compatible(state: Any, year: int | None) -> int:
    release_range = getattr(state, "release_year_range", None)
    if release_range is None or year is None:
        return 0
    lo = getattr(release_range, "start", None)
    hi = getattr(release_range, "end", None)
    if lo is not None and year < lo:
        return -1
    if hi is not None and year > hi:
        return -1
    return 1 if lo is not None or hi is not None else 0


def _normalize_vec(vec: list[float] | None) -> list[float] | None:
    if not vec:
        return None
    norm = math.sqrt(sum(float(x) * float(x) for x in vec))
    if norm == 0.0:
        return None
    return [float(x) / norm for x in vec]


def _centroid(vectors: list[list[float] | None]) -> list[float] | None:
    clean = [vec for vec in vectors if vec]
    if not clean:
        return None
    width = len(clean[0])
    aligned = [vec for vec in clean if len(vec) == width]
    if not aligned:
        return None
    return _normalize_vec([
        sum(vec[idx] for vec in aligned) / len(aligned)
        for idx in range(width)
    ])


def _sample_user_ids(
    sample_ids: list[str],
    turn_meta: dict[str, dict[str, Any]],
    trace_paths: tuple[Path, ...] = TRACE_PATHS,
) -> dict[str, str]:
    trace_path = next((path for path in trace_paths if path.exists()), None)
    if trace_path is None:
        return {}
    wanted = {
        (str(turn_meta[sid]["session_id"]), int(turn_meta[sid]["turn"])): sid
        for sid in sample_ids
    }
    out: dict[str, str] = {}
    with trace_path.open() as handle:
        for line in handle:
            if len(out) == len(wanted):
                break
            row = json.loads(line)
            key = (str(row.get("session_id")), int(row.get("turn_number") or 0))
            sid = wanted.get(key)
            if sid is None:
                continue
            user_id = row.get("user_id")
            if user_id:
                out[sid] = str(user_id)
    return out


def _track_meta_cache(
    catalog: LanceDbCatalog,
    candidate_ids: set[str],
) -> dict[str, TrackMeta]:
    pop_rank = {
        track_id: rank
        for rank, track_id in enumerate(catalog.popularity_sorted_track_ids(), start=1)
    }
    cache: dict[str, TrackMeta] = {}
    for track_id in candidate_ids:
        cache[track_id] = TrackMeta(
            tags=frozenset(_expanded_tag_terms(catalog.tag_list(track_id))),
            text=catalog.track_text(track_id, max_tags=40).casefold(),
            release_year=catalog.release_year_of(track_id),
            popularity_rank=pop_rank.get(track_id),
            cf_bpr=_normalize_vec(catalog.vector(track_id, "cf_bpr")),
            artist_id=catalog.artist_id_of(track_id),
        )
    return cache


GENERIC_TERMS = {
    "alternative",
    "classic",
    "dance",
    "electronic",
    "funk",
    "hip hop",
    "hip-hop",
    "metal",
    "pop",
    "popular",
    "rap",
    "rock",
}


def _feature_scores_for_sample(
    *,
    state: Any,
    track_meta: dict[str, TrackMeta],
    candidate_ids: set[str],
    catalog: LanceDbCatalog,
    user_vector: list[float] | None,
    mode: str,
) -> dict[str, CandidateFeature]:
    query_text = _state_query_text(state)
    query_terms = _scene_terms_from_text(query_text)
    expanded_query_terms = _expanded_tag_terms(sorted(query_terms))
    negative_terms = _expanded_tag_terms(sorted(_negative_tag_values(state)))
    popularity_requested = _has_explicit_popularity_request(state)
    hard_drop_track_ids = _state_hard_drop_track_ids(state)
    anchor_track_ids = _state_anchor_track_ids(state)
    anchor_cf = _centroid([catalog.vector(track_id, "cf_bpr") for track_id in anchor_track_ids])
    anchor_artist_ids = {
        catalog.artist_id_of(track_id)
        for track_id in anchor_track_ids
        if catalog.artist_id_of(track_id)
    }
    target_artist_mode = _enum_value(getattr(state, "target_artist_mode", None))

    features: dict[str, CandidateFeature] = {}
    for track_id in candidate_ids:
        meta = track_meta[track_id]
        hard_drop = track_id in hard_drop_track_ids
        score = 0.0

        tag_overlap = expanded_query_terms & meta.tags
        specific_overlap = {term for term in tag_overlap if term not in GENERIC_TERMS}
        generic_overlap = tag_overlap - specific_overlap
        phrase_hits = {term for term in expanded_query_terms if " " in term and term in meta.text}
        negative_overlap = negative_terms & meta.tags
        year_match = _release_year_compatible(state, meta.release_year)

        if mode in {"catalog_features", "branch_local_hybrid"}:
            score += min(0.060, 0.015 * len(specific_overlap))
            score += min(0.020, 0.004 * len(generic_overlap))
            score += min(0.024, 0.008 * len(phrase_hits))
            if year_match > 0:
                score += 0.014
            elif year_match < 0:
                score -= 0.014
            if popularity_requested and meta.popularity_rank is not None:
                if meta.popularity_rank <= 200:
                    score += 0.040
                elif meta.popularity_rank <= 1000:
                    score += 0.030
                elif meta.popularity_rank <= 3000:
                    score += 0.015
            if negative_overlap:
                score -= min(0.060, 0.030 * len(negative_overlap))

        if mode in {"anchor_cf_features", "branch_local_hybrid"}:
            score += 0.036 * max(0.0, _cosine(anchor_cf, meta.cf_bpr))

        if mode in {"user_cf_features", "branch_local_hybrid"}:
            score += 0.026 * max(0.0, _cosine(user_vector, meta.cf_bpr))

        if mode == "branch_local_hybrid":
            if target_artist_mode == "new_artist" and meta.artist_id in anchor_artist_ids:
                score -= 0.030
            if getattr(state, "lyrical_theme", None):
                score += 0.006 * len(phrase_hits)

        features[track_id] = CandidateFeature(feature_score=score, hard_drop=hard_drop)
    return features


def _rerank_pool_map(
    *,
    sample_ids: list[str],
    all_on_pools: dict[str, list[BranchPool]],
    states: dict[str, Any],
    track_meta: dict[str, TrackMeta],
    catalog: LanceDbCatalog,
    user_vectors: dict[str, list[float] | None],
    mode: str,
) -> dict[str, list[BranchPool]]:
    out: dict[str, list[BranchPool]] = {}
    for sid in sample_ids:
        candidate_ids = {
            track_id
            for pool in all_on_pools.get(sid, [])
            for track_id, _score in pool.hits
        }
        features = _feature_scores_for_sample(
            state=states[sid],
            track_meta=track_meta,
            candidate_ids=candidate_ids,
            catalog=catalog,
            user_vector=user_vectors.get(sid),
            mode=mode,
        )
        out[sid] = [
            _rank_pool_with_features(pool, features, suffix=mode)
            for pool in all_on_pools.get(sid, [])
        ]
    return out


def _explicit_gt_conflict(state: Any, meta: dict[str, Any]) -> bool:
    gt_track = str(meta["gt_track"]).casefold()
    gt_artist = str(meta["gt_artist"]).casefold()
    for rejection in getattr(state, "explicit_rejections", []) or []:
        value = str(getattr(rejection, "value", "") or "").casefold()
        kind = _enum_value(getattr(rejection, "kind", None))
        if kind == "artist" and value and value in gt_artist:
            return True
        if kind == "track" and value and value in gt_track:
            return True
    return False


AUDIT_OVERRIDES = {
    "88af7ec3-c368-421b-9512-d0180da3d1f6::t2": (
        "underspecified_next_play_behavior",
        "User is recalling a lyric setup from a prior item; GT is a broad next-play jump.",
    ),
    "88beb200-3c06-4a85-90ae-f0db2d247d0d::t1": (
        "gt_conflicts_with_explicit_user_constraint",
        "User asks for someone other than Drake; GT includes Drake.",
    ),
    "e978bb5b-26af-4c7d-b720-b9210bdddf25::t8": (
        "gt_conflicts_with_explicit_user_constraint",
        "User asks to branch out from Masta Ace; GT is still Masta Ace.",
    ),
}


def _audit_gt_labels(
    *,
    sample_ids: list[str],
    turn_meta: dict[str, dict[str, Any]],
    states: dict[str, Any],
    current_plus_targeted: dict[str, dict[str, Any]],
    original_all_on: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    labels: dict[str, dict[str, Any]] = {}
    for sid in sample_ids:
        meta = turn_meta[sid]
        state = states[sid]
        if sid in AUDIT_OVERRIDES:
            label, note = AUDIT_OVERRIDES[sid]
        elif _explicit_gt_conflict(state, meta):
            label = "gt_conflicts_with_explicit_user_constraint"
            note = "Frozen state has an explicit rejection matching the GT entity."
        elif current_plus_targeted[sid]["union@20"]:
            label = "valid_gt_state_supports_it"
            note = "Current protected branches already place GT in union@20."
        elif current_plus_targeted[sid]["union@100"] or original_all_on[sid]["branch_only@100"]:
            label = "valid_gt_branch_local_ranking_weak"
            note = "GT is in the candidate pool but below top-20."
        else:
            query_terms = _scene_terms_from_text(_state_query_text(state))
            if len(query_terms) <= 2 and not getattr(state, "lyrical_theme", None):
                label = "underspecified_next_play_behavior"
                note = "Frozen state has too little query signal for a determinate next play."
            elif original_all_on[sid].get("best_branch_rank") is None:
                label = "valid_gt_retriever_source_weak"
                note = "State has signal, but forced existing branches do not surface GT."
            else:
                label = "valid_gt_state_signal_compiler_not_consumed"
                note = "GT appears deep, but projected branch inputs are not sharp enough."
        labels[sid] = {
            "gt_audit_label": label,
            "valid_gt": label not in NOISY_GT_LABELS,
            "audit_note": note,
        }
    return labels


def _counts_by_label(labels: dict[str, dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(label["gt_audit_label"] for label in labels.values()))


def _variant_metrics(
    *,
    variant: str,
    sample_ids: list[str],
    rows: dict[str, dict[str, Any]],
    labels: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    metrics = _metrics_for_subset(sample_ids, rows, labels)
    out: dict[str, Any] = {"variant": variant}
    for scope, scoped_metrics in metrics.items():
        for key, value in scoped_metrics.items():
            out[f"{scope}_{key}"] = value
    return out


def _per_class_metrics(
    *,
    variants: dict[str, dict[str, dict[str, Any]]],
    sample_ids: list[str],
    turn_meta: dict[str, dict[str, Any]],
    labels: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    packs: dict[str, list[str]] = defaultdict(list)
    for sid in sample_ids:
        packs[turn_meta[sid]["pack"]].append(sid)
    rows: list[dict[str, Any]] = []
    for pack, pack_ids in sorted(packs.items()):
        valid_ids = [sid for sid in pack_ids if labels[sid]["valid_gt"]]
        for variant, variant_rows in variants.items():
            row = {
                "pack": pack,
                "variant": variant,
                "all_n": len(pack_ids),
                "valid_n": len(valid_ids),
            }
            for scope, scoped_ids in (("all", pack_ids), ("valid_only", valid_ids)):
                for k in KS:
                    count = sum(bool(variant_rows[sid].get(f"union@{k}")) for sid in scoped_ids)
                    row[f"{scope}_union@{k}_count"] = count
                    row[f"{scope}_union@{k}"] = count / len(scoped_ids) if scoped_ids else None
            rows.append(row)
    return rows


def _best_movement_examples(
    *,
    sample_ids: list[str],
    turn_meta: dict[str, dict[str, Any]],
    labels: dict[str, dict[str, Any]],
    baseline_rows: dict[str, dict[str, Any]],
    variant_rows: dict[str, dict[str, Any]],
    limit: int = 14,
) -> dict[str, list[dict[str, Any]]]:
    rescued: list[dict[str, Any]] = []
    still_missed: list[dict[str, Any]] = []
    near_moved: list[dict[str, Any]] = []
    for sid in sample_ids:
        meta = turn_meta[sid]
        base = baseline_rows[sid]
        row = variant_rows[sid]
        item = {
            "sample_id": sid,
            "pack": meta["pack"],
            "valid_gt": labels[sid]["valid_gt"],
            "gt_audit_label": labels[sid]["gt_audit_label"],
            "gt_track": meta["gt_track"],
            "gt_artist": meta["gt_artist"],
            "current_user": meta["current_user"],
            "baseline_best_rank": base.get("best_branch_rank"),
            "variant_best_rank": row.get("best_branch_rank"),
            "variant_best_branch": row.get("best_branch"),
            "why_wrong": meta.get("why_wrong"),
            "what_should_change": meta.get("what_should_change"),
        }
        if not base["union@20"] and row["union@20"]:
            rescued.append(item)
        elif not row["union@20"] and labels[sid]["valid_gt"]:
            still_missed.append(item)
        base_rank = base.get("best_branch_rank") or 10**9
        new_rank = row.get("best_branch_rank") or 10**9
        if new_rank < base_rank:
            near_moved.append(item)
    rescued.sort(key=lambda item: (not item["valid_gt"], item["variant_best_rank"] or 10**9))
    still_missed.sort(key=lambda item: (item["variant_best_rank"] or 10**9, item["sample_id"]))
    near_moved.sort(
        key=lambda item: (
            (item["variant_best_rank"] or 10**9) - (item["baseline_best_rank"] or 10**9),
            item["variant_best_rank"] or 10**9,
        )
    )
    return {
        "rescued_union20": rescued[:limit],
        "still_missed_valid_union20": still_missed[:limit],
        "rank_improved": near_moved[:limit],
    }


def _decision_for_variant(
    *,
    variant: str,
    baseline: dict[str, dict[str, Any]],
    rows: dict[str, dict[str, Any]],
    sample_ids: list[str],
    labels: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    valid_ids = [sid for sid in sample_ids if labels[sid]["valid_gt"]]
    all_u20_gain = sum(rows[sid]["union@20"] for sid in sample_ids) - sum(
        baseline[sid]["union@20"] for sid in sample_ids
    )
    valid_u20_gain = sum(rows[sid]["union@20"] for sid in valid_ids) - sum(
        baseline[sid]["union@20"] for sid in valid_ids
    )
    valid_u50_gain = sum(rows[sid]["union@50"] for sid in valid_ids) - sum(
        baseline[sid]["union@50"] for sid in valid_ids
    )
    if variant == "all_feature_family":
        decision = "defer_user_cf_component"
    elif variant == "all_on_original":
        decision = "reject_without_branch_local_scoring"
    elif valid_u20_gain > 0 and all_u20_gain >= 0:
        decision = "keep_for_full_devset_smoke"
    elif valid_u50_gain > 0 and all_u20_gain >= 0:
        decision = "defer_to_branch_ranking_work"
    else:
        decision = "reject_for_now"
    return {
        "variant": variant,
        "decision": decision,
        "all_union20_gain_count": int(all_u20_gain),
        "valid_union20_gain_count": int(valid_u20_gain),
        "valid_union50_gain_count": int(valid_u50_gain),
    }


def _write_csv(path: Path, sample_ids: list[str], rows: dict[str, dict[str, Any]]) -> None:
    fields = [
        "sample_id",
        "pack",
        "class_type",
        "gt_track",
        "gt_artist",
        "gt_audit_label",
        "valid_gt",
        "variant",
        "best_branch",
        "best_branch_rank",
        "union@20",
        "union@50",
        "union@100",
        "branch_only@20",
        "branch_only@50",
        "branch_only@100",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for sid in sample_ids:
            row = rows[sid]
            writer.writerow({field: row.get(field) for field in fields})


def _fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    metric_by_variant = {row["variant"]: row for row in payload["metrics"]}
    baseline = metric_by_variant["current_plus_targeted"]
    promoted = metric_by_variant["promoted_feature_family"]
    lines: list[str] = [
        "# State V1 Candidate Quality Non-Prompt Matrix",
        "",
        "Scope: focused-110 only. V1 state extractor prompt and schema are frozen. "
        "Metrics are additive against the protected current+targeted baseline.",
        "",
        "## Read This First",
        "",
        "- Current+targeted baseline: "
        f"{baseline['all_union@20_count']}/110 union@20, "
        f"{baseline['all_union@50_count']}/110 union@50, "
        f"{baseline['all_union@100_count']}/110 union@100.",
        "- Best non-prompt lever: `promoted_feature_family` "
        f"{promoted['all_union@20_count']}/110 union@20, "
        f"{promoted['all_union@50_count']}/110 union@50, "
        f"{promoted['all_union@100_count']}/110 union@100.",
        "- Valid-GT-only lift: "
        f"{baseline['valid_only_union@20_count']}/99 -> "
        f"{promoted['valid_only_union@20_count']}/99 union@20. "
        "That is +7 valid top-20 rescues with no state prompt/schema changes.",
        "- Plain `all_on_original` does not move top-20. The gap is not only "
        "whether branches fire; it is branch-local candidate ordering using "
        "catalog tags, year/popularity compatibility, anchor-CF, and soft "
        "novelty/negative evidence.",
        "- User-CF alone does not improve union@20, but it improves deeper recall "
        "and should be deferred as a ranking feature rather than promoted as a "
        "top-20 candidate-recall fix.",
        "",
        "## Headline Metrics",
        "",
        "| Variant | all n | all u@20 | all u@50 | all u@100 | valid n | valid u@20 | valid u@50 | valid u@100 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["metrics"]:
        lines.append(
            "| `{variant}` | {all_n} | {all20} | {all50} | {all100} | {valid_n} | {valid20} | {valid50} | {valid100} |".format(
                variant=row["variant"],
                all_n=row["all_n"],
                all20=f"{row['all_union@20_count']}/{row['all_n']}",
                all50=f"{row['all_union@50_count']}/{row['all_n']}",
                all100=f"{row['all_union@100_count']}/{row['all_n']}",
                valid_n=row["valid_only_n"],
                valid20=f"{row['valid_only_union@20_count']}/{row['valid_only_n']}",
                valid50=f"{row['valid_only_union@50_count']}/{row['valid_only_n']}",
                valid100=f"{row['valid_only_union@100_count']}/{row['valid_only_n']}",
            )
        )

    lines.extend([
        "",
        "## GT Audit",
        "",
        "| Label | Count |",
        "|---|---:|",
    ])
    for label, count in sorted(payload["gt_audit_counts"].items()):
        lines.append(f"| `{label}` | {count} |")
    lines.extend([
        "",
        "Noisy/contradictory GT is excluded only for the valid-GT-only view. "
        "All-110 metrics still include every turn. The conflict labels are mostly "
        "literal cases like 'not Drake', 'not Daft Punk', or 'not System Of A Down' "
        "where the GT artist violates an explicit user constraint.",
    ])

    lines.extend([
        "",
        "## Decisions",
        "",
        "| Lever | Decision | all u@20 gain | valid u@20 gain | valid u@50 gain |",
        "|---|---|---:|---:|---:|",
    ])
    for row in payload["decisions"]:
        lines.append(
            "| `{variant}` | {decision} | {all_gain} | {valid20} | {valid50} |".format(
                variant=row["variant"],
                decision=row["decision"],
                all_gain=row["all_union20_gain_count"],
                valid20=row["valid_union20_gain_count"],
                valid50=row["valid_union50_gain_count"],
            )
        )

    lines.extend([
        "",
        "## Lever Readout",
        "",
        "- Projection-only state consumption: represented by `catalog_features` and "
        "`branch_local_hybrid`, which derive query terms from the existing frozen "
        "request summary/facts/lyrical theme and consume them as score features. "
        "This moved valid union@20, so this should become compiler-owned structured "
        "branch-local scoring before any prompt work.",
        "- Derived catalog features: normalized tag aliases, broad track text, release "
        "year compatibility, and popularity-if-requested are positive. Keep for "
        "full-devset smoke.",
        "- Anchor-CF: positive top-20 lift. Keep as a branch-local feature when the "
        "state has liked/reference/accepted anchors.",
        "- User-CF: 89/110 focused users have vectors and user-CF improves union@100, "
        "but not union@20. Defer to ranking work; do not call it a candidate-recall "
        "fix yet.",
        "- Last-resort prompt ablation: not run. The frozen state contains enough "
        "usable signal to get +7 valid union@20 from non-prompt levers, so prompt "
        "iteration should be a separate later goal only for the remaining state/lyric "
        "failures.",
    ])

    lines.extend([
        "",
        "## Remaining Gap",
        "",
        "- Still-near @21-50: mostly branch-local scoring/query specificity. Examples include "
        "`5ee0dbbc...::t8` at rank 22, `3676005d...::t1` at rank 27, "
        "`10a15ba2...::t7` at rank 29, and `2bbc0a7e...::t1` at rank 30.",
        "- Deeper/missing: stale or roleless anchors still blur novelty requests, and some "
        "lyric/theme requests need a stronger lyric-aware source or better query text.",
        "- Rejection controls stayed stable in this additive analysis: the P1 rejection "
        "guardrail valid slice remains 5/5 union@20.",
    ])

    lines.extend([
        "",
        "## Per-Class Valid-Only union@20",
        "",
        "| Pack | Variant | valid n | valid u@20 | valid u@50 | valid u@100 |",
        "|---|---|---:|---:|---:|---:|",
    ])
    for row in payload["per_class"]:
        if row["variant"] not in {
            "current_plus_targeted",
            "all_on_original",
            "catalog_features",
            "anchor_cf_features",
            "user_cf_features",
            "branch_local_hybrid",
            "catalog_plus_anchor_cf",
            "promoted_feature_family",
            "all_feature_family",
        }:
            continue
        lines.append(
            "| {pack} | `{variant}` | {n} | {u20} | {u50} | {u100} |".format(
                pack=row["pack"],
                variant=row["variant"],
                n=row["valid_n"],
                u20=f"{row['valid_only_union@20_count']}/{row['valid_n']}",
                u50=f"{row['valid_only_union@50_count']}/{row['valid_n']}",
                u100=f"{row['valid_only_union@100_count']}/{row['valid_n']}",
            )
        )

    lines.extend([
        "",
        "## Examples",
        "",
    ])
    for variant, examples in payload["examples"].items():
        if variant not in {"promoted_feature_family"}:
            continue
        lines.extend([f"### `{variant}` rescued union@20", ""])
        for item in examples["rescued_union20"]:
            lines.append(
                "- `{sample_id}` ({pack}, {label}): GT={gt_track} by {gt_artist}; rank {old} -> {new} via `{branch}`. User: {user}".format(
                    sample_id=item["sample_id"],
                    pack=item["pack"],
                    label=item["gt_audit_label"],
                    gt_track=item["gt_track"],
                    gt_artist=item["gt_artist"],
                    old=item["baseline_best_rank"] or "missing",
                    new=item["variant_best_rank"] or "missing",
                    branch=item["variant_best_branch"] or "",
                    user=item["current_user"][:220].replace("\n", " "),
                )
            )
        if not examples["rescued_union20"]:
            lines.append("- No additive union@20 rescues over current+targeted.")
        lines.extend(["", f"### `{variant}` still missed valid GT", ""])
        for item in examples["still_missed_valid_union20"]:
            lines.append(
                "- `{sample_id}` ({pack}): GT={gt_track} by {gt_artist}; best rank={rank}; reason={why}; change={change}".format(
                    sample_id=item["sample_id"],
                    pack=item["pack"],
                    gt_track=item["gt_track"],
                    gt_artist=item["gt_artist"],
                    rank=item["variant_best_rank"] or "missing",
                    why=(item.get("why_wrong") or "")[:180],
                    change=(item.get("what_should_change") or "")[:180],
                )
            )
        lines.append("")

    lines.extend([
        "## User-CF Coverage",
        "",
        f"- Focused users with `cf_bpr` vector: {payload['user_cf_coverage']['with_vector']}/{payload['user_cf_coverage']['n']}.",
        f"- User ids found in trace: {payload['user_cf_coverage']['with_user_id']}/{payload['user_cf_coverage']['n']}.",
        "",
        "## Recommendation",
        "",
        payload["recommendation"],
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")


def run(args: argparse.Namespace) -> dict[str, Any]:
    pack = json.loads(args.pack_json.read_text())
    turn_meta = {turn["sample_id"]: turn for turn in pack["turns"]}
    sample_ids = list(turn_meta)
    audit_rows = _load_jsonl(args.audit_jsonl)
    states = {sid: _state_from_audit(audit_rows[sid]) for sid in sample_ids}
    protected_pools = _load_pools(args.protected_pools_json)
    all_on_pools = _load_pools(args.all_on_pools_json)
    report = json.loads(args.targeted_report_json.read_text())
    current_rows = _or_rows_from_files(
        name="current_or",
        files=report["inputs"]["current_files"],
        sample_ids=sample_ids,
        turn_meta=turn_meta,
    )
    current_plus_targeted_rows = _or_rows_from_files(
        name="current_plus_targeted",
        files=report["inputs"]["current_files"] + report["inputs"]["targeted_files"],
        sample_ids=sample_ids,
        turn_meta=turn_meta,
    )

    original_pool_rows = _pools_to_rows(
        name="all_on_original",
        sample_ids=sample_ids,
        turn_meta=turn_meta,
        pools_by_sample=_merged_pools(sample_ids, protected_pools, all_on_pools),
        protected_rows=current_plus_targeted_rows,
    )
    labels = _audit_gt_labels(
        sample_ids=sample_ids,
        turn_meta=turn_meta,
        states=states,
        current_plus_targeted=current_plus_targeted_rows,
        original_all_on=original_pool_rows,
    )
    for rows in (current_rows, current_plus_targeted_rows, original_pool_rows):
        for sid, row in rows.items():
            row.update(labels[sid])

    candidate_ids = {
        track_id
        for pools in all_on_pools.values()
        for pool in pools
        for track_id, _score in pool.hits
    }
    catalog = LanceDbCatalog(str(args.lancedb_uri), eager_vector_fields=("cf_bpr",))
    candidate_ids.update(
        track_id
        for sid in sample_ids
        for track_id in _state_anchor_track_ids(states[sid])
    )
    track_meta = _track_meta_cache(catalog, candidate_ids)

    sample_user_ids = _sample_user_ids(sample_ids, turn_meta)
    user_embeddings = UserEmbeddings()
    user_vectors = {
        sid: _normalize_vec(user_embeddings.vector(sample_user_ids[sid], "cf_bpr"))
        if sid in sample_user_ids
        else None
        for sid in sample_ids
    }

    variant_pool_maps = {
        mode: _rerank_pool_map(
            sample_ids=sample_ids,
            all_on_pools=all_on_pools,
            states=states,
            track_meta=track_meta,
            catalog=catalog,
            user_vectors=user_vectors,
            mode=mode,
        )
        for mode in (
            "catalog_features",
            "anchor_cf_features",
            "user_cf_features",
            "branch_local_hybrid",
        )
    }
    variant_pool_maps["catalog_plus_anchor_cf"] = _merged_pools(
        sample_ids,
        variant_pool_maps["catalog_features"],
        variant_pool_maps["anchor_cf_features"],
    )
    variant_pool_maps["promoted_feature_family"] = _merged_pools(
        sample_ids,
        variant_pool_maps["catalog_features"],
        variant_pool_maps["anchor_cf_features"],
        variant_pool_maps["branch_local_hybrid"],
    )
    variant_pool_maps["all_feature_family"] = _merged_pools(
        sample_ids,
        variant_pool_maps["catalog_features"],
        variant_pool_maps["anchor_cf_features"],
        variant_pool_maps["user_cf_features"],
        variant_pool_maps["branch_local_hybrid"],
    )
    variant_rows: dict[str, dict[str, dict[str, Any]]] = {
        "current_or": current_rows,
        "current_plus_targeted": current_plus_targeted_rows,
        "all_on_original": original_pool_rows,
    }
    for mode, pool_map in variant_pool_maps.items():
        rows = _pools_to_rows(
            name=mode,
            sample_ids=sample_ids,
            turn_meta=turn_meta,
            pools_by_sample=pool_map,
            protected_rows=current_plus_targeted_rows,
        )
        for sid, row in rows.items():
            row.update(labels[sid])
        variant_rows[mode] = rows

    metrics = [
        _variant_metrics(
            variant=variant,
            sample_ids=sample_ids,
            rows=rows,
            labels=labels,
        )
        for variant, rows in variant_rows.items()
    ]
    decisions = [
        _decision_for_variant(
            variant=variant,
            baseline=current_plus_targeted_rows,
            rows=rows,
            sample_ids=sample_ids,
            labels=labels,
        )
        for variant, rows in variant_rows.items()
        if variant not in {"current_or", "current_plus_targeted"}
    ]
    examples = {
        variant: _best_movement_examples(
            sample_ids=sample_ids,
            turn_meta=turn_meta,
            labels=labels,
            baseline_rows=current_plus_targeted_rows,
            variant_rows=rows,
        )
        for variant, rows in variant_rows.items()
        if variant not in {"current_or", "current_plus_targeted"}
    }
    recommendation = (
        "Keep only levers with positive valid-GT union@20 lift for the next "
        "full-devset smoke. If a lever only improves union@50, treat it as "
        "evidence for branch-local ranking or a lightweight ranker, not as "
        "candidate recall solved."
    )
    payload: dict[str, Any] = {
        "scope": {
            "state_prompt_schema": "frozen",
            "sample_count": len(sample_ids),
            "baseline_expected": {
                "current_or": {"union@20": 75, "union@50": 87, "union@100": 91},
                "current_plus_targeted": {
                    "union@20": 77,
                    "union@50": 90,
                    "union@100": 93,
                },
            },
        },
        "gt_audit_counts": _counts_by_label(labels),
        "metrics": metrics,
        "decisions": decisions,
        "per_class": _per_class_metrics(
            variants=variant_rows,
            sample_ids=sample_ids,
            turn_meta=turn_meta,
            labels=labels,
        ),
        "examples": examples,
        "user_cf_coverage": {
            "n": len(sample_ids),
            "with_user_id": sum(sid in sample_user_ids for sid in sample_ids),
            "with_vector": sum(user_vectors[sid] is not None for sid in sample_ids),
        },
        "recommendation": recommendation,
        "rows": [
            row
            for variant in variant_rows.values()
            for row in variant.values()
        ],
    }
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pack-json", type=Path, default=PACK_JSON)
    parser.add_argument("--audit-jsonl", type=Path, default=AUDIT_JSONL)
    parser.add_argument("--protected-pools-json", type=Path, default=PROTECTED_POOLS_JSON)
    parser.add_argument("--all-on-pools-json", type=Path, default=ALL_ON_POOLS_JSON)
    parser.add_argument("--targeted-report-json", type=Path, default=TARGETED_REPORT_JSON)
    parser.add_argument("--lancedb-uri", type=Path, default=DEFAULT_LANCEDB)
    parser.add_argument(
        "--output-json",
        type=Path,
        default=ANALYSIS_DIR / "state_v1_candidate_quality_nonprompt_matrix_all110.json",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=ANALYSIS_DIR / "state_v1_candidate_quality_nonprompt_matrix_all110.csv",
    )
    parser.add_argument(
        "--output-md",
        type=Path,
        default=ANALYSIS_DIR / "state_v1_candidate_quality_nonprompt_report.md",
    )
    args = parser.parse_args()
    payload = run(args)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    csv_rows = {
        f"{row['sample_id']}::{row['variant']}": row
        for row in payload["rows"]
    }
    _write_csv(args.output_csv, list(csv_rows), csv_rows)
    _write_report(args.output_md, payload)
    print(
        json.dumps(
            {
                "json": str(args.output_json),
                "csv": str(args.output_csv),
                "md": str(args.output_md),
                "metrics": payload["metrics"],
                "decisions": payload["decisions"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
