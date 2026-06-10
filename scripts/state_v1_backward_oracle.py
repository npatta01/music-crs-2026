#!/usr/bin/env python
"""Backward oracle for focused V1 candidate-recall misses.

This is an analysis-only worksheet.  It starts from the GT of each missed turn
and asks which signal would have made the GT visible in top-20.  Any probe that
uses GT tags is marked as an oracle diagnostic, not a production retriever.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from omegaconf import OmegaConf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcrs.qu_modules.compiler_v0plus_qu import build_v0plus_compiler_qu  # noqa: E402
from scripts.state_v1_retriever_matrix import (  # noqa: E402
    DEFAULT_ANALYSIS_DIR,
    DEFAULT_CONFIG,
    DEFAULT_MAIN_LANCEDB,
    _GENERIC_SCENE_TERMS,
    _artist_ids_from_compiled_references,
    _catalog_feature_rows,
    _expanded_tag_terms,
    _rank,
    _reference_artist_discography_pool,
    _same_album_fanout_pool,
    _scene_term_weight,
    _scene_terms_from_text,
    _soft_temporal_score,
    _state_fact_query_text,
    _state_from_audit,
    _state_positive_tags,
    _state_query_text,
    _year_match_bonus,
)


DEFAULT_QUALITY_JSON = DEFAULT_ANALYSIS_DIR / "overnight_candidate_quality_repro.json"
DEFAULT_AUDIT_JSONL = DEFAULT_ANALYSIS_DIR / "state_v1_goal_current_all110_reprojected_audit.jsonl"
DEFAULT_PACK_JSON = DEFAULT_ANALYSIS_DIR / "state_experiment_pack.json"
DEFAULT_OUTPUT_STEM = DEFAULT_ANALYSIS_DIR / "backward_oracle_promoted_misses"


class _NoopEmbeddingClient:
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("backward oracle should not call dense encoders")


@dataclass(frozen=True)
class ProbeRank:
    name: str
    rank: int | None
    production_valid: bool
    note: str


def _load_jsonl(path: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        rows[str(row["sample_id"])] = row
    return rows


def _norm_text(value: str | None) -> str:
    chars = [ch.casefold() if ch.isalnum() else " " for ch in (value or "")]
    return " ".join("".join(chars).split())


def _contains_phrase(haystack: str, needle: str | None) -> bool:
    norm_hay = f" {_norm_text(haystack)} "
    norm_needle = _norm_text(needle)
    return bool(norm_needle and f" {norm_needle} " in norm_hay)


def _hit_rank(pool: Any, target: str) -> int | None:
    return _rank([track_id for track_id, _score in pool.hits], target)


def _short(value: str | None, n: int = 180) -> str:
    text = " ".join((value or "").split())
    if len(text) <= n:
        return text
    return text[: n - 3].rstrip() + "..."


def _minimal_qu_kwargs(config_path: Path, lancedb_uri: Path) -> dict[str, Any]:
    cfg = OmegaConf.load(config_path)
    qu_kwargs = OmegaConf.to_container(cfg.qu_kwargs, resolve=True)
    assert isinstance(qu_kwargs, dict)
    lancedb_cfg = dict(qu_kwargs.get("lancedb") or {})
    lancedb_cfg["db_uri"] = str(lancedb_uri)
    lancedb_cfg["eager_vector_fields"] = []
    qu_kwargs["lancedb"] = lancedb_cfg

    compiler_cfg = dict(qu_kwargs.get("compiler") or {})
    compiler_cfg["enable_dense"] = False
    compiler_cfg["dense_branches"] = []
    compiler_cfg["centroid_only_branches"] = []
    qu_kwargs["compiler"] = compiler_cfg
    qu_kwargs["encoders"] = {}
    return qu_kwargs


def _build_analysis_qu(config_path: Path, lancedb_uri: Path):
    return build_v0plus_compiler_qu(
        _minimal_qu_kwargs(config_path, lancedb_uri),
        _overrides={"encoders": {"default": _NoopEmbeddingClient()}},
    )


def _resolve_state(qu: Any, audit_row: dict[str, Any]):
    state = _state_from_audit(audit_row)
    played = [tf.track_id for tf in state.track_feedback]
    rs = qu.resolver.resolve(state, played_track_ids=played)
    return state, rs


def _catalog_tags(catalog: Any, track_id: str, *, limit: int = 16) -> list[str]:
    return [str(tag) for tag in catalog.tag_list(track_id)[:limit]]


_TAG_NOISE_SUBSTRINGS = {
    "awesome",
    "awful",
    "beautiful",
    "boring",
    "favorite",
    "favorites",
    "favourite",
    "favourites",
    "faves",
    "fucking",
    "genius",
    "lastfm",
    "last fm",
    "loved",
    "lovedtrack",
    "my top",
    "playlist",
    "radio",
    "seen live",
    "unlistenable",
    "winamp",
}


def _clean_gt_music_tags(tags: list[str], *, gt_track: str | None, gt_artist: str | None) -> list[str]:
    track_norm = _norm_text(gt_track)
    artist_norm = _norm_text(gt_artist)
    out: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        norm = _norm_text(tag)
        if not norm or len(norm) < 3 or len(norm) > 48:
            continue
        if any(noise in norm for noise in _TAG_NOISE_SUBSTRINGS):
            continue
        if norm == track_norm or norm == artist_norm:
            continue
        if artist_norm and (norm in artist_norm or artist_norm in norm):
            continue
        if track_norm and (norm in track_norm or track_norm in norm):
            continue
        if norm in seen:
            continue
        seen.add(norm)
        out.append(tag)
    return out


def _rank_scored(scored: list[tuple[Any, ...]], gt_track_id: str) -> int | None:
    for idx, item in enumerate(scored, start=1):
        if item[-1] == gt_track_id:
            return idx
    return None


def _rank_tag_overlap(
    catalog: Any,
    *,
    query_terms: set[str],
    gt_track_id: str,
    release_range: Any | None = None,
    include_phrase_hits: bool = False,
    weighted: bool = False,
    temporal_soft: bool = False,
) -> int | None:
    query_terms = {term for term in query_terms if term}
    if not query_terms:
        return None
    scored: list[tuple[int, int, int, int, str]] = []
    for row in _catalog_feature_rows(catalog):
        overlap = query_terms & set(row.tag_terms)
        phrase_hits = {
            term for term in query_terms if include_phrase_hits and " " in term and term in row.text
        }
        if not overlap and not phrase_hits:
            continue
        if weighted:
            term_score = sum(_scene_term_weight(term) for term in overlap)
            phrase_score = sum(_scene_term_weight(term) + 2 for term in phrase_hits)
            specific = {term for term in overlap | phrase_hits if term not in _GENERIC_SCENE_TERMS}
            specificity_bonus = 8 if len(specific) >= 2 else 0
            temporal_score = (
                _soft_temporal_score(release_range, row.year)
                if temporal_soft
                else _year_match_bonus(release_range, row.year)
            )
            score = term_score + phrase_score + specificity_bonus + temporal_score * 4
            scored.append((score, term_score + phrase_score, temporal_score, row.pop_rank, row.track_id))
        else:
            term_score = len(overlap) * 4 + len(phrase_hits) * 2
            year_bonus = _year_match_bonus(release_range, row.year)
            score = term_score + year_bonus * 2
            scored.append((score, term_score, year_bonus, row.pop_rank, row.track_id))
    scored.sort(key=lambda item: (-item[0], -item[1], -item[2], item[3], item[4]))
    return _rank_scored(scored, gt_track_id)


def _rank_artist_neighbor_scene_fact(qu: Any, rs: Any, gt_track_id: str) -> int | None:
    artist_ids = _artist_ids_from_compiled_references(qu, rs)
    if not artist_ids:
        return None
    catalog = qu.compiler.catalog
    pop_rank = qu.compiler._popularity_rank()
    anchor_counter: Counter[str] = Counter()
    for artist_id in artist_ids[:6]:
        tracks = sorted(
            catalog.tracks_by_artist_id(artist_id),
            key=lambda tid: pop_rank.get(tid, 10**9),
        )[:25]
        for track_id in tracks:
            anchor_counter.update(_expanded_tag_terms(catalog.tag_list(track_id)))
    if not anchor_counter:
        return None

    state_terms = _scene_terms_from_text(_state_fact_query_text(rs.state)) | _scene_terms_from_text(
        _state_query_text(rs.state)
    )
    anchor_terms = set(anchor_counter)
    scored: list[tuple[int, int, int, int, str]] = []
    for row in _catalog_feature_rows(catalog):
        tag_terms = set(row.tag_terms)
        anchor_overlap = tag_terms & anchor_terms
        state_overlap = tag_terms & state_terms
        if not anchor_overlap and not state_overlap:
            continue
        anchor_score = sum(min(anchor_counter[term], 8) * _scene_term_weight(term) for term in anchor_overlap)
        state_score = sum(_scene_term_weight(term) for term in state_overlap)
        specific = {term for term in anchor_overlap | state_overlap if term not in _GENERIC_SCENE_TERMS}
        specificity_bonus = 8 if len(specific) >= 2 else 0
        year_bonus = _year_match_bonus(getattr(rs.state, "release_year_range", None), row.year)
        score = anchor_score + state_score + specificity_bonus + year_bonus * 3
        scored.append((score, anchor_score + state_score, year_bonus, row.pop_rank, row.track_id))
    scored.sort(key=lambda item: (-item[0], -item[1], -item[2], item[3], item[4]))
    return _rank_scored(scored, gt_track_id)


def _probe_ranks(
    qu: Any,
    rs: Any,
    gt_track_id: str,
    *,
    gt_track: str | None,
    gt_artist: str | None,
) -> list[ProbeRank]:
    catalog = qu.compiler.catalog
    state_tag_terms = _expanded_tag_terms(_state_positive_tags(qu, rs))
    query_terms = _scene_terms_from_text(_state_query_text(rs.state))
    fact_terms = _scene_terms_from_text(_state_fact_query_text(rs.state))
    clean_gt_tags = _clean_gt_music_tags(
        _catalog_tags(catalog, gt_track_id, limit=40),
        gt_track=gt_track,
        gt_artist=gt_artist,
    )
    gt_tag_terms = _expanded_tag_terms(clean_gt_tags)
    probes = [
        ProbeRank(
            "state_tag_popularity_alias",
            _rank_tag_overlap(
                catalog,
                query_terms=state_tag_terms,
                gt_track_id=gt_track_id,
            ),
            True,
            "Current projected tags plus catalog alias expansion.",
        ),
        ProbeRank(
            "state_query_text_tag_popularity",
            _rank_tag_overlap(
                catalog,
                query_terms=query_terms,
                gt_track_id=gt_track_id,
                release_range=getattr(rs.state, "release_year_range", None),
                include_phrase_hits=True,
            ),
            True,
            "Current request/query text mapped to catalog tags and popularity.",
        ),
        ProbeRank(
            "state_scene_era_tag_popularity",
            _rank_tag_overlap(
                catalog,
                query_terms=query_terms,
                gt_track_id=gt_track_id,
                release_range=getattr(rs.state, "release_year_range", None),
                include_phrase_hits=True,
                weighted=True,
            ),
            True,
            "State query terms plus soft era compatibility and popularity.",
        ),
        ProbeRank(
            "state_fact_only_scene_era",
            _rank_tag_overlap(
                catalog,
                query_terms=fact_terms,
                gt_track_id=gt_track_id,
                release_range=rs.state,
                include_phrase_hits=True,
                weighted=True,
                temporal_soft=True,
            ),
            True,
            "Structured attribute facts only; avoids summary/entity pollution.",
        ),
        ProbeRank(
            "same_album_fanout",
            _hit_rank(_same_album_fanout_pool(qu, rs), gt_track_id),
            True,
            "Fan out tracks from albums already anchored by accepted/reference tracks.",
        ),
        ProbeRank(
            "reference_artist_discography",
            _hit_rank(_reference_artist_discography_pool(qu, rs), gt_track_id),
            True,
            "Fan out resolved reference artists; should be gated/demoted for novelty.",
        ),
        ProbeRank(
            "artist_neighbor_scene_fact",
            _rank_artist_neighbor_scene_fact(qu, rs, gt_track_id),
            True,
            "Reference-artist tag neighborhoods plus current structured facts.",
        ),
        ProbeRank(
            "oracle_gt_clean_music_tags",
            _rank_tag_overlap(
                catalog,
                query_terms=gt_tag_terms,
                gt_track_id=gt_track_id,
            ),
            False,
            "Uses the GT track's cleaned genre/scene tags. Diagnostic for catalog-tag expressiveness only.",
        ),
    ]
    return probes


def _rank_bucket(rank: int | None, union50: bool, union100: bool) -> str:
    if rank is None:
        if union50:
            return "unexplained_union50"
        if union100:
            return "unexplained_union100"
        return "absent_from_promoted_top100"
    if rank <= 20:
        return "already_top20"
    if rank <= 50:
        return "order_gap_21_50"
    if rank <= 100:
        return "order_gap_51_100"
    return "deep_or_source_gap_gt_rank_gt100"


def _best_probe(probes: list[ProbeRank], *, production_valid: bool | None = None) -> ProbeRank | None:
    scoped = [
        probe
        for probe in probes
        if probe.rank is not None
        and (production_valid is None or probe.production_valid is production_valid)
    ]
    if not scoped:
        return None
    return min(scoped, key=lambda probe: probe.rank or 10**9)


def _infer_lever(
    *,
    row: dict[str, Any],
    turn: dict[str, Any],
    state: Any,
    rs: Any,
    probes: list[ProbeRank],
    gt_artist_in_request: bool,
    gt_title_in_request: bool,
    gt_artist_is_reference: bool,
    same_album_anchor: bool,
    state_gt_tag_overlap: list[str],
) -> tuple[str, str, str]:
    if not row.get("valid_gt", True):
        return (
            "do_not_optimize_invalid_or_contradictory_gt",
            "Do not chase this with retrieval. Keep it as a guardrail/audit case.",
            "GT audit marks this noisy or contradictory.",
        )

    rank = row.get("best_branch_rank")
    if isinstance(rank, int) and 20 < rank <= 50:
        return (
            "branch_local_rerank_existing_branch",
            f"GT is already close at rank {rank} in {row.get('best_branch')}; rescore within that branch/pool.",
            "Candidate source works; top-20 ordering is the gap.",
        )
    if isinstance(rank, int) and 50 < rank <= 100:
        return (
            "branch_local_rerank_or_survivor_slots",
            f"GT is visible at rank {rank}; use branch-local hybrid scoring or reserve survivor slots.",
            "Candidate source partially works; rank depth is the gap.",
        )

    best_prod = _best_probe(probes, production_valid=True)
    best_oracle = _best_probe(probes, production_valid=False)

    if gt_title_in_request:
        return (
            "exact_track_lookup_protection",
            "Use exact track lookup/protection; the user named the GT title.",
            "This should not depend on semantic retrieval.",
        )
    if gt_artist_in_request:
        return (
            "exact_artist_discography_or_artist_bm25",
            "Use exact artist resolution plus discography/artist BM25, then rank by request facets.",
            "The user named the GT artist.",
        )
    if same_album_anchor:
        return (
            "same_album_or_album_affinity_branch",
            "Fan out same-album candidates from accepted/reference tracks, then score with current request facets.",
            "The GT shares an album with an anchored track.",
        )
    if gt_artist_is_reference:
        return (
            "reference_artist_fanout_with_novelty_demote",
            "Include reference-artist discography as recall but demote when the request asks for a different artist.",
            "The compiler can resolve the GT artist as a reference/anchor artist.",
        )
    if best_prod and best_prod.rank is not None and best_prod.rank <= 50:
        return (
            f"promote_{best_prod.name}",
            f"{best_prod.name} would put GT at rank {best_prod.rank}; promote/tune this production-valid branch.",
            best_prod.note,
        )
    if best_prod and best_prod.rank is not None and best_prod.rank <= 100:
        return (
            f"tune_{best_prod.name}",
            f"{best_prod.name} sees GT at rank {best_prod.rank}; needs better local scoring, not a new source.",
            best_prod.note,
        )
    if state_gt_tag_overlap:
        return (
            "sharper_tag_hybrid_scoring",
            "The state and GT tags overlap, but the GT remains deep/absent; use BM25-tag plus dense-attribute hybrid and specificity weighting.",
            "The current tag surface has signal but too much noise.",
        )
    if best_oracle and best_oracle.rank is not None and best_oracle.rank <= 50:
        return (
            "state_to_catalog_tag_mapping_gap",
            f"GT's own catalog tags rank it at {best_oracle.rank}, but state terms do not. Need better query-to-canonical-tag mapping.",
            "Oracle tag probe says the catalog can express the target; projection/query terms are the gap.",
        )

    facets = {
        str(getattr(fact, "facet", "") or "")
        for fact in getattr(state, "facts", []) or []
        if str(getattr(fact, "type", "") or "") == "attribute"
    }
    request_type = str(getattr(getattr(state, "current_request", None), "request_type", "") or "")
    if "lyrical_theme" in facets or getattr(state, "lyrical_theme", None):
        return (
            "new_or_better_lyric_theme_source",
            "Existing lyric branch did not surface this class; need a better lyric/theme representation or lyric-aware hybrid.",
            "The state has lyric/theme evidence but current lyric retrieval is weak.",
        )
    if "visual" in facets or "cover" in _norm_text(turn.get("current_user")):
        return (
            "new_or_better_visual_source",
            "Existing SigLIP cover-art branch is too weak; need cover-art concept labels or visual-tag hybrid.",
            "The state has visual evidence but current visual retrieval is weak.",
        )
    if "popularity" in facets or any(word in _norm_text(turn.get("current_user")) for word in ("popular", "classic", "hit")):
        return (
            "genre_era_popularity_hybrid",
            "Use catalog tag/scene + era + popularity with sharper concept mapping; popularity alone is too broad.",
            "Request asks for popular/classic behavior, but current branch is noisy.",
        )
    if request_type in {"similar_to_prior", "attribute_search"}:
        return (
            "semantic_neighbor_or_anchor_cf_source",
            "Need stronger anchor-neighbor retrieval: combine accepted-track CF/audio/tag neighborhoods before fusion.",
            "The state is valid but current sources do not put GT near top100.",
        )
    return (
        "underspecified_or_new_source_needed",
        "No current production-valid probe sees the GT well; keep as candidate for new source audit.",
        "The request/GT connection is weak in available metadata.",
    )


def _state_summary(state: Any, rs: Any, qu: Any) -> dict[str, Any]:
    facts = []
    for fact in getattr(state, "facts", []) or []:
        facts.append(
            {
                "type": str(getattr(fact, "type", "") or ""),
                "facet": str(getattr(fact, "facet", "") or ""),
                "value": str(getattr(fact, "value", "") or ""),
                "role": str(getattr(fact, "role", "") or ""),
                "relation": str(getattr(fact, "relation", "") or ""),
                "anchor_use": str(getattr(fact, "anchor_use", "") or ""),
            }
        )
    return {
        "request_type": str(getattr(getattr(state, "current_request", None), "request_type", "") or ""),
        "request_summary": str(getattr(getattr(state, "current_request", None), "summary", "") or ""),
        "target_artist_mode": str(getattr(state, "target_artist_mode", "") or ""),
        "retrieval_profile": str(getattr(state, "retrieval_profile", "") or ""),
        "turn_intent": str(getattr(state, "turn_intent", "") or ""),
        "query_text": _state_query_text(state),
        "fact_query_text": _state_fact_query_text(state),
        "positive_tags": _state_positive_tags(qu, rs),
        "anchor_track_ids": qu.compiler._anchor_track_ids(state),
        "reference_artist_ids": _artist_ids_from_compiled_references(qu, rs),
        "facts": facts[:18],
    }


def analyze(args: argparse.Namespace) -> dict[str, Any]:
    quality = json.loads(args.quality_json.read_text())
    audit_rows = _load_jsonl(args.audit_jsonl)
    pack = json.loads(args.pack_json.read_text())
    turns = {row["sample_id"]: row for row in pack["turns"]}
    source_gap_rows = {
        row["sample_id"]: row
        for row in (quality.get("source_gap") or {}).get("rows", [])
        if isinstance(row, dict) and "sample_id" in row
    }

    misses = [
        row
        for row in quality["rows"]
        if row.get("variant") == args.variant and not row.get("union@20")
    ]
    if args.limit:
        misses = misses[: args.limit]

    qu = _build_analysis_qu(args.config, args.lancedb_uri)
    catalog = qu.compiler.catalog
    pop_rank = {tid: rank + 1 for rank, tid in enumerate(catalog.popularity_sorted_track_ids())}

    rows: list[dict[str, Any]] = []
    detailed: list[dict[str, Any]] = []
    lever_counts: Counter[str] = Counter()
    rank_bucket_counts: Counter[str] = Counter()
    pack_counts: Counter[str] = Counter()

    for row in misses:
        sample_id = row["sample_id"]
        turn = turns[sample_id]
        audit_row = audit_rows[sample_id]
        state, rs = _resolve_state(qu, audit_row)
        gt_track_id = turn["gt_track_id"]
        gt_artist_id = catalog.artist_id_of(gt_track_id)
        gt_album_id = catalog.album_id_of(gt_track_id)
        anchor_track_ids = qu.compiler._anchor_track_ids(state)
        anchor_album_ids = {
            album_id
            for tid in anchor_track_ids
            if (album_id := catalog.album_id_of(tid))
        }
        reference_artist_ids = set(_artist_ids_from_compiled_references(qu, rs))
        gt_tags = _catalog_tags(catalog, gt_track_id, limit=20)
        clean_gt_tags = _clean_gt_music_tags(
            _catalog_tags(catalog, gt_track_id, limit=40),
            gt_track=turn.get("gt_track"),
            gt_artist=turn.get("gt_artist"),
        )
        clean_gt_tag_terms = _expanded_tag_terms(clean_gt_tags)
        state_terms = _scene_terms_from_text(_state_query_text(state))
        state_fact_terms = _scene_terms_from_text(_state_fact_query_text(state))
        state_positive_tag_terms = _expanded_tag_terms(_state_positive_tags(qu, rs))
        tag_overlap = sorted(
            (state_terms | state_fact_terms | state_positive_tag_terms) & clean_gt_tag_terms
        )[:16]
        probes = _probe_ranks(
            qu,
            rs,
            gt_track_id,
            gt_track=turn.get("gt_track"),
            gt_artist=turn.get("gt_artist"),
        )
        probe_dict = {
            probe.name: {
                "rank": probe.rank,
                "production_valid": probe.production_valid,
                "note": probe.note,
            }
            for probe in probes
        }
        gt_artist_in_request = _contains_phrase(turn.get("current_user", ""), turn.get("gt_artist"))
        gt_title_in_request = _contains_phrase(turn.get("current_user", ""), turn.get("gt_track"))
        gt_artist_is_reference = bool(gt_artist_id and gt_artist_id in reference_artist_ids)
        same_album_anchor = bool(gt_album_id and gt_album_id in anchor_album_ids)
        lever, ideal_pull_up, rationale = _infer_lever(
            row=row,
            turn=turn,
            state=state,
            rs=rs,
            probes=probes,
            gt_artist_in_request=gt_artist_in_request,
            gt_title_in_request=gt_title_in_request,
            gt_artist_is_reference=gt_artist_is_reference,
            same_album_anchor=same_album_anchor,
            state_gt_tag_overlap=tag_overlap,
        )
        bucket = _rank_bucket(row.get("best_branch_rank"), bool(row.get("union@50")), bool(row.get("union@100")))
        best_prod = _best_probe(probes, production_valid=True)
        best_oracle = _best_probe(probes, production_valid=False)
        query_builders = {
            "metadata": qu.compiler._build_metadata_query_string(rs),
            "attributes": qu.compiler._build_attributes_query_string(rs),
            "attributes_enriched": qu.compiler._build_attributes_enriched_query_string(rs),
            "sonic_nl": qu.compiler._build_sonic_nl_query_string(rs),
            "sonic_nl_enriched": qu.compiler._build_sonic_nl_enriched_query_string(rs),
            "visual": qu.compiler._build_visual_query_string(rs),
            "lyric": qu.compiler._build_lyric_query_string(rs),
        }
        source_gap = source_gap_rows.get(sample_id, {})

        compact = {
            "sample_id": sample_id,
            "pack": row.get("pack"),
            "valid_gt": row.get("valid_gt"),
            "gt": f"{row.get('gt_track')} / {row.get('gt_artist')}",
            "rank_bucket": bucket,
            "current_best_branch": row.get("best_branch"),
            "current_best_rank": row.get("best_branch_rank"),
            "union@50": row.get("union@50"),
            "union@100": row.get("union@100"),
            "ideal_lever": lever,
            "ideal_pull_up": ideal_pull_up,
            "rationale": rationale,
            "best_production_probe": None if best_prod is None else best_prod.name,
            "best_production_probe_rank": None if best_prod is None else best_prod.rank,
            "gt_tag_oracle_rank": None if best_oracle is None else best_oracle.rank,
            "state_gt_tag_overlap": ", ".join(tag_overlap),
            "gt_year": catalog.release_year_of(gt_track_id),
            "gt_pop_rank": pop_rank.get(gt_track_id),
            "gt_tags": ", ".join(gt_tags[:10]),
            "gt_clean_tags": ", ".join(clean_gt_tags[:10]),
            "current_user": _short(turn.get("current_user"), 260),
            "audit_note": row.get("audit_note"),
            "source_gap_reason": source_gap.get("reason") or source_gap.get("worksheet_reason"),
        }
        detail = {
            **compact,
            "turn": {
                "session_id": turn.get("session_id"),
                "turn": turn.get("turn"),
                "gt_track_id": gt_track_id,
                "current_user": turn.get("current_user"),
                "why_wrong": turn.get("why_wrong"),
                "what_should_change": turn.get("what_should_change"),
                "recent_messages": turn.get("recent_messages", [])[-6:],
            },
            "state_summary": _state_summary(state, rs, qu),
            "gt_catalog": {
                "track_text": catalog.track_text(gt_track_id, max_tags=30),
                "artist_id": gt_artist_id,
                "album_id": gt_album_id,
                "release_year": catalog.release_year_of(gt_track_id),
                "popularity_rank": pop_rank.get(gt_track_id),
                "tags": gt_tags,
                "clean_music_tags": clean_gt_tags,
            },
            "query_builders": query_builders,
            "probe_ranks": probe_dict,
            "flags": {
                "gt_title_in_current_user": gt_title_in_request,
                "gt_artist_in_current_user": gt_artist_in_request,
                "gt_artist_is_compiled_reference": gt_artist_is_reference,
                "gt_album_matches_anchor_album": same_album_anchor,
            },
        }
        rows.append(compact)
        detailed.append(detail)
        lever_counts[lever] += 1
        rank_bucket_counts[bucket] += 1
        pack_counts[str(row.get("pack"))] += 1

    return {
        "scope": {
            "variant": args.variant,
            "miss_count": len(rows),
            "quality_json": str(args.quality_json),
            "audit_jsonl": str(args.audit_jsonl),
            "pack_json": str(args.pack_json),
            "note": "GT-tag probes are backward diagnostics and are not production-valid retrievers.",
        },
        "summary": {
            "ideal_lever_counts": dict(lever_counts.most_common()),
            "rank_bucket_counts": dict(rank_bucket_counts.most_common()),
            "pack_counts": dict(pack_counts.most_common()),
        },
        "rows": rows,
        "details": detailed,
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    lines: list[str] = []
    scope = payload["scope"]
    summary = payload["summary"]
    lines.append("# Backward Oracle: What Would Pull Focused Misses Up?")
    lines.append("")
    lines.append(
        f"Variant audited: `{scope['variant']}`. Misses audited: **{scope['miss_count']}**."
    )
    lines.append("")
    lines.append(
        "This report works backward from the GT for each promoted-family `union@20` miss. "
        "Production-valid probes use only current state/projection plus catalog metadata. "
        "`oracle_gt_clean_music_tags` uses cleaned genre/scene tags from the GT track and is only a diagnostic for whether the catalog tag surface could express the target."
    )
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("### Ideal lever counts")
    for lever, count in summary["ideal_lever_counts"].items():
        lines.append(f"- `{lever}`: {count}")
    lines.append("")
    lines.append("### Rank bucket counts")
    for bucket, count in summary["rank_bucket_counts"].items():
        lines.append(f"- `{bucket}`: {count}")
    lines.append("")
    lever_counts = summary["ideal_lever_counts"]
    near_miss_count = (
        lever_counts.get("branch_local_rerank_existing_branch", 0)
        + lever_counts.get("branch_local_rerank_or_survivor_slots", 0)
    )
    tag_hybrid_count = sum(
        count
        for lever, count in lever_counts.items()
        if "tag" in lever or lever == "sharper_tag_hybrid_scoring"
    )
    source_gap_count = sum(
        count
        for lever, count in lever_counts.items()
        if "source" in lever or "lyric" in lever or "visual" in lever
    )
    invalid_count = lever_counts.get("do_not_optimize_invalid_or_contradictory_gt", 0)
    lines.append("## Build Order From The Backward Pass")
    lines.append("")
    lines.append(
        f"1. **Branch-local ordering / survivor slots first**: {near_miss_count} misses are already in an existing branch around ranks 21-100. The ideal retriever is not new; the GT needs a per-branch scorer using branch rank, state-tag overlap, year compatibility, popularity-if-requested, anchor-CF/audio evidence, and hard resolved exclusions."
    )
    lines.append(
        f"2. **Tag hybrid second**: {tag_hybrid_count} misses show state/catalog tag overlap or a useful tag-popularity probe, but the tag surface is noisy. The ideal branch is a hybrid of BM25 tag/search text plus dense attributes over cleaned/canonical tag concepts, with specificity weighting."
    )
    lines.append(
        f"3. **Do not optimize noisy GTs**: {invalid_count} misses are marked invalid or contradictory by the audit. They can test guardrails, but should not drive candidate recall work."
    )
    lines.append(
        f"4. **New source only for residuals**: {source_gap_count} miss is still poorly expressed after production-valid and cleaned-tag probes. That is the right place to consider catalog enrichment or a specialized embedding/source."
    )
    lines.append("")
    lines.append("## Reading")
    lines.append("")
    lines.append(
        "- If `current_best_rank` is 21-50 or 51-100, the problem is mostly branch-local ordering or survivor slots, not state extraction."
    )
    lines.append(
        "- If a production probe is <=20, we likely already have a retriever branch that can rescue the turn with better routing or promotion."
    )
    lines.append(
        "- If only the GT-tag oracle is good, the missing piece is query-to-catalog tag mapping, not a brand-new embedding by default."
    )
    lines.append(
        "- If neither production probes nor GT-tag oracle are good, this is a real source/representation gap or a noisy GT."
    )
    lines.append("")
    lines.append("## Miss Worksheet")
    lines.append("")
    header = (
        "| sample | GT | bucket | current best | ideal lever | best production probe | "
        "GT-tag oracle | overlap | read |"
    )
    lines.append(header)
    lines.append("|---|---|---|---|---|---|---:|---|---|")
    for row in payload["rows"]:
        sample = row["sample_id"].split("::", 1)[0][:8] + "::" + row["sample_id"].split("::", 1)[1]
        current = f"{row['current_best_branch']} @ {row['current_best_rank']}"
        prod = f"{row['best_production_probe']} @ {row['best_production_probe_rank']}"
        lines.append(
            "| "
            + " | ".join(
                [
                    sample,
                    row["gt"].replace("|", "/"),
                    row["rank_bucket"],
                    current.replace("|", "/"),
                    f"`{row['ideal_lever']}`",
                    prod.replace("|", "/"),
                    str(row["gt_tag_oracle_rank"] or ""),
                    _short(row["state_gt_tag_overlap"], 80).replace("|", "/"),
                    _short(row["ideal_pull_up"], 180).replace("|", "/"),
                ]
            )
            + " |"
        )
    lines.append("")
    lines.append("## Per-Example Notes")
    lines.append("")
    for detail in payload["details"]:
        lines.append(f"### {detail['sample_id']} — {detail['gt']}")
        lines.append("")
        lines.append(f"- Pack: `{detail['pack']}`; valid_gt={detail['valid_gt']}; bucket=`{detail['rank_bucket']}`.")
        lines.append(
            f"- Current best: `{detail['current_best_branch']}` rank `{detail['current_best_rank']}`; union@50={detail['union@50']}; union@100={detail['union@100']}."
        )
        lines.append(f"- Ideal pull-up: **{detail['ideal_pull_up']}**")
        lines.append(f"- Why: {detail['rationale']}")
        lines.append(
            f"- GT catalog: year={detail['gt_year']}; popularity_rank={detail['gt_pop_rank']}; tags={_short(detail['gt_tags'], 220)}."
        )
        lines.append(
            f"- State/read: request_type=`{detail['state_summary']['request_type']}`; target_artist_mode=`{detail['state_summary']['target_artist_mode']}`; positive_tags={_short(', '.join(detail['state_summary']['positive_tags']), 180)}."
        )
        lines.append(
            f"- Query builders: attributes={_short(detail['query_builders'].get('attributes_enriched'), 170)}; sonic={_short(detail['query_builders'].get('sonic_nl_enriched'), 170)}; lyric={_short(detail['query_builders'].get('lyric'), 120)}."
        )
        lines.append(
            f"- Probes: production_best=`{detail['best_production_probe']}` @ `{detail['best_production_probe_rank']}`; gt_tag_oracle @ `{detail['gt_tag_oracle_rank']}`; overlap={detail['state_gt_tag_overlap'] or 'none'}."
        )
        lines.append(f"- User: {detail['current_user']}")
        lines.append("")
    path.write_text("\n".join(lines) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quality-json", type=Path, default=DEFAULT_QUALITY_JSON)
    parser.add_argument("--audit-jsonl", type=Path, default=DEFAULT_AUDIT_JSONL)
    parser.add_argument("--pack-json", type=Path, default=DEFAULT_PACK_JSON)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--lancedb-uri", type=Path, default=DEFAULT_MAIN_LANCEDB)
    parser.add_argument("--variant", default="promoted_feature_family")
    parser.add_argument("--output-stem", type=Path, default=DEFAULT_OUTPUT_STEM)
    parser.add_argument("--limit", type=int, default=0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = analyze(args)
    json_path = args.output_stem.with_suffix(".json")
    csv_path = args.output_stem.with_suffix(".csv")
    md_path = args.output_stem.with_suffix(".md")
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    _write_csv(csv_path, payload["rows"])
    _write_report(md_path, payload)
    print(json.dumps({"json": str(json_path), "csv": str(csv_path), "md": str(md_path)}, indent=2))


if __name__ == "__main__":
    main()
