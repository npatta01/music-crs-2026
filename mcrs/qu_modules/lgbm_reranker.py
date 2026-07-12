"""Online LightGBM (v10) reranker — serves the trained LambdaMART in-pipeline.

Consumes the SAME trace payload the offline feature builder reads and computes
features via the SAME `compute_turn_features` (scripts/rerank/features.py —
the feature builder kept its v9 module name across the v10 model bump),
so train/serve drift is structurally impossible. Hooked by V0PlusCompilerQU
right after trace assembly; replaces the RRF order over the branch-pool union.

Config (qu_kwargs.reranker). The model bundle is committed in-repo (ships with
the repo + the Modal image) under a path set by `model_path` in each config --
the current active bundle is models/reranker_v12_goalfree/ (see CLAUDE.md's
"Architecture notes" for which bundle is actually live; `models/reranker_v10/`
is retained only as a historical bundle). The large caches referenced below are
not committed (see docs/reproduce_reranker.md):
  enabled: true
  model_path:    <bundle>/model.txt        (LightGBM booster)
  meta_path:     <bundle>/meta.json        ({cols, cat_idx})
  cat_maps:      <bundle>/cat_maps.json    (categorical value->code)
  branch_names:  <bundle>/branch_names.json (canonical 11)
  tag_index:     .../tag_embedding_index/qwen_0_6b.npz
  embed_memo:    .../q06_memo.json         (query-text embedding cache; live
                                            DeepInfra fill for unseen strings)
  msg_store:     .../raw_msg_store         (message-embedding store; live fill)
  pool_k: 500
  top_k_out: 1000

`session_meta` (threaded from run_inference) must carry the RAW conversation
(music entries = catalog track ids) + profile/goal — the dataset-equivalent
session context. Without it the session-history block would silently zero
(the round-2 blind bug class).
"""

from __future__ import annotations

import json
import logging
import math
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
for p in (_PROJECT_ROOT, _PROJECT_ROOT / "scripts" / "rerank"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

CATEGORICALS = ["age_group", "gender", "goal_category", "goal_specificity",
                "request_type", "intent_mode", "target_artist_mode",
                "temporal_strength"]
VISUAL_RESCUE_BRANCH = "dense.siglip2_text.visual_nl.image_siglip2"
LYRIC_RESCUE_BRANCH = "dense.qwen_0_6b.lyric.lyrics_qwen3_embedding_0_6b"
logger = logging.getLogger(__name__)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, (list, tuple, set)):
        return [v for v in value if v is not None]
    return [value]


def _first(value: Any) -> Any:
    values = _as_list(value)
    return values[0] if values else None


def _parse_year(value: Any) -> int | None:
    raw = _first(value)
    if raw is None:
        return None
    if isinstance(raw, date):
        return raw.year
    text = str(raw)
    return int(text[:4]) if len(text) >= 4 and text[:4].isdigit() else None


def _float_or_nan(value: Any) -> float:
    raw = _first(value)
    if raw is None:
        return float("nan")
    try:
        return float(raw)
    except (TypeError, ValueError):
        return float("nan")


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


class _FeatureCatalogFromCompilerCatalog:
    """Catalog adapter for online reranking.

    `scripts/rerank/build_features.Catalog` is optimized for offline feature
    builds: it scans LanceDB metadata and eagerly loads every vector column.
    During inference the compiler has already loaded the same track metadata,
    so this adapter reuses that in-memory catalog and fetches vectors through
    its `vector()` method.
    """

    def __init__(self, source_catalog: Any):
        from mcrs.qu_modules.tag_resolver import catalog_tag_key

        per_track = _feature_rows_from_catalog(source_catalog)

        self._source_catalog = source_catalog
        self._vector_cache: dict[str, dict[str, np.ndarray | None]] = {}
        self.vec: dict[str, np.ndarray] = {}
        self.vec_idx: dict[str, dict[str, int]] = {}
        self.meta: dict[str, dict] = {}
        pops: dict[str, float] = {}
        years: dict[str, int] = {}
        artist_track_counter: Counter = Counter()
        has_duration_column = False

        for tid_raw, row in per_track.items():
            tid = str(tid_raw)
            artists = tuple(str(a) for a in _as_list(row.get("artist_id")))
            albums = tuple(str(a) for a in _as_list(row.get("album_id")))
            year = _parse_year(row.get("release_date"))
            tags = [str(t) for t in _as_list(row.get("tag_list"))]
            tag_keys = frozenset(catalog_tag_key(t) for t in tags) - {""}
            track_name = _first(row.get("track_name")) or ""
            artist_names = _as_list(row.get("artist_name"))
            artist_name_keys = tuple(
                k for k in (catalog_tag_key(str(a or "")) for a in artist_names) if k
            )
            duration = _float_or_nan(row.get("duration"))
            has_duration_column = has_duration_column or not math.isnan(duration)
            pop = _float_or_nan(row.get("popularity"))
            if math.isnan(pop):
                pop = 0.0

            self.meta[tid] = {
                "artists": artists,
                "albums": albums,
                "year": year,
                "pop": pop,
                "tag_keys": tag_keys,
                "n_tags": len(tags),
                "name_tokens": frozenset(catalog_tag_key(str(track_name or "")).split()) - {""},
                "artist_name_keys": artist_name_keys,
                "duration": duration,
            }
            pops[tid] = pop
            if year is not None:
                years[tid] = year
            for artist_id in artists:
                artist_track_counter[artist_id] += 1

        self.has_duration = has_duration_column
        self.artist_track_count = dict(artist_track_counter)

        if pops:
            all_pop = np.sort(np.array(list(pops.values()), dtype=np.float32))
            self.pop_pct = {
                tid: float(np.searchsorted(all_pop, pop) / len(all_pop))
                for tid, pop in pops.items()
            }
        else:
            self.pop_pct = {}

        by_year: dict[int, list[float]] = defaultdict(list)
        for tid, year in years.items():
            by_year[year].append(pops[tid])
        year_pops = {year: np.sort(np.array(values, dtype=np.float32))
                     for year, values in by_year.items()}
        self.era_pop_pct = {
            tid: float(np.searchsorted(year_pops[year], pops[tid]) / len(year_pops[year]))
            for tid, year in years.items()
        }

        tag_df: Counter = Counter()
        for meta in self.meta.values():
            tag_df.update(meta["tag_keys"])
        n_tracks = len(self.meta)
        self.tag_idf = {
            tag: math.log((n_tracks + 1) / (count + 1))
            for tag, count in tag_df.items()
        }

        artist_pops: dict[str, list[float]] = defaultdict(list)
        for tid, meta in self.meta.items():
            for artist_id in meta["artists"]:
                artist_pops[artist_id].append(meta["pop"])
        artist_pop_sorted = {
            artist_id: np.sort(np.array(values, dtype=np.float32))
            for artist_id, values in artist_pops.items()
        }
        self.within_artist_pop = {}
        for tid, meta in self.meta.items():
            best = 0.0
            for artist_id in meta["artists"]:
                arr = artist_pop_sorted[artist_id]
                if len(arr) > 1:
                    best = max(best, float(np.searchsorted(arr, meta["pop"]) / (len(arr) - 1)))
                else:
                    best = max(best, 1.0)
            self.within_artist_pop[tid] = best

        durations = np.array(
            [meta["duration"] for meta in self.meta.values() if not math.isnan(meta["duration"])],
            dtype=np.float32,
        )
        self.median_duration = float(np.median(durations)) if len(durations) else 0.0
        year_values = [meta["year"] for meta in self.meta.values() if meta["year"]]
        self.median_year = int(np.median(year_values)) if year_values else 2008

    def v(self, field: str, tid: str) -> np.ndarray | None:
        field_cache = self._vector_cache.setdefault(field, {})
        if tid in field_cache:
            return field_cache[tid]
        raw = self._source_catalog.vector(tid, field)
        if raw is None:
            field_cache[tid] = None
            return None
        vec = np.asarray(raw, dtype=np.float32)
        if vec.size == 0:
            field_cache[tid] = None
            return None
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        field_cache[tid] = vec
        return vec


def _catalog_source_has_feature_rows(source_catalog: Any | None) -> bool:
    if source_catalog is None:
        return False
    return callable(getattr(source_catalog, "feature_rows", None))


def _feature_rows_from_catalog(source_catalog: Any) -> dict[str, dict[str, Any]]:
    feature_rows = getattr(source_catalog, "feature_rows", None)
    if not callable(feature_rows):
        raise TypeError("source catalog does not expose feature rows")
    rows = feature_rows()
    if not isinstance(rows, dict):
        raise TypeError("source catalog feature_rows() must return a dict")
    return rows


def _load_feature_catalog(
    *,
    catalog_source: Any | None,
    offline_catalog_cls: type,
    db_uri: str,
    table_name: str,
):
    if catalog_source is None:
        return offline_catalog_cls(db_uri, table_name)
    if not _catalog_source_has_feature_rows(catalog_source):
        logger.warning(
            "reranker catalog_source=%s does not expose feature rows; "
            "falling back to offline Catalog scan",
            type(catalog_source).__name__,
        )
        return offline_catalog_cls(db_uri, table_name)
    return _FeatureCatalogFromCompilerCatalog(catalog_source)


def _current_request_type(trace: dict) -> str:
    state = trace.get("state") or trace.get("extracted_state") or {}
    current_request = state.get("current_request") or {}
    raw = current_request.get("request_type")
    return str(getattr(raw, "value", raw) or "")


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _surface_key(value: Any) -> str:
    return str(value or "").casefold().strip()


def _same_turn_exact_request(trace: dict, current_turn: int | None) -> bool:
    if not current_turn:
        return False
    state = trace.get("state") or trace.get("extracted_state") or {}
    current_request = state.get("current_request") or {}
    return _int_or_none(current_request.get("source_turn")) == int(current_turn)


def _same_turn_exact_track_fact(
    trace: dict,
    *,
    source_text: str,
    current_turn: int | None,
) -> bool:
    if not current_turn:
        return False
    source_key = _surface_key(source_text)
    state = trace.get("state") or trace.get("extracted_state") or {}
    for fact in state.get("facts") or []:
        if not isinstance(fact, dict):
            continue
        if _int_or_none(fact.get("source_turn")) != int(current_turn):
            continue
        if _surface_key(fact.get("value")) != source_key:
            continue
        if str(fact.get("type") or "") != "track":
            continue
        if str(fact.get("role") or "") != "current_target":
            continue
        if str(fact.get("anchor_use") or "") != "must_use":
            continue
        if str(fact.get("relation") or "") != "exact_target":
            continue
        if str(fact.get("reuse") or "") != "must_reuse":
            continue
        if fact.get("mentioned_current_turn") is not True:
            continue
        return True
    return False


def _routing_tag_enabled(trace: dict, tag: str) -> bool:
    for block in (
        trace.get("routing_tags"),
        (trace.get("compiled_state") or {}).get("routing_tags"),
        (trace.get("state") or trace.get("extracted_state") or {}).get("routing_tags"),
    ):
        if isinstance(block, dict) and tag in block:
            return _as_bool(block[tag])
    return False


def _branch_hits(trace: dict, branch_name: str) -> list[tuple[str, float]]:
    branches = trace.get("branches") or {}
    for pool in branches.get("pools") or []:
        if not isinstance(pool, dict) or pool.get("name") != branch_name:
            continue
        hits = []
        for hit in pool.get("hits") or []:
            track_id: Any = None
            score: Any = 0.0
            if isinstance(hit, dict):
                track_id = hit.get("track_id") or hit.get("id")
                score = hit.get("score", hit.get("distance", 0.0))
            elif isinstance(hit, (list, tuple)) and hit:
                track_id = hit[0]
                score = hit[1] if len(hit) > 1 else 0.0
            track_id = str(track_id or "")
            if not track_id:
                continue
            try:
                score_f = float(score)
            except (TypeError, ValueError):
                score_f = 0.0
            hits.append((track_id, score_f))
        return hits
    return []


def _word_count(text: Any) -> int:
    return len(re.findall(r"[A-Za-z0-9']+", str(text or "")))


def _lyric_phrase_like_request(trace: dict) -> bool:
    state = trace.get("state") or trace.get("extracted_state") or {}
    resolver = trace.get("resolver") or {}
    phrase_candidates: list[str] = []
    context_candidates: list[str] = []

    if state.get("lyrical_theme"):
        phrase_candidates.append(str(state["lyrical_theme"]))
    if state.get("turn_intent"):
        context_candidates.append(str(state["turn_intent"]))

    current_request = state.get("current_request") or {}
    current_summary = str(current_request.get("summary") or "")
    if current_summary:
        context_candidates.append(current_summary)

    for fact in state.get("facts") or []:
        if not isinstance(fact, dict):
            continue
        if fact.get("facet") == "lyrical_theme" or fact.get("type") == "lyrical_theme":
            if fact.get("value"):
                phrase_candidates.append(str(fact["value"]))

    phrase_candidates.extend(
        str(tag) for tag in _as_list(resolver.get("positive_tags")) if tag
    )
    if not phrase_candidates:
        return False

    marker_text = " ".join([*phrase_candidates, *context_candidates]).lower()
    has_exact_phrase_marker = any(
        marker in marker_text
        for marker in (
            "exact lyric",
            "exact lyrical phrase",
            "exact phrase",
            "contains the exact",
            "containing the exact",
            "quoted lyric",
            "lyric phrase",
        )
    )
    has_quoted_lyric_marker = bool(
        re.search(r"(lyric|lyrics|says|saying|phrase).{0,60}[\"']", marker_text)
    )
    if not (has_exact_phrase_marker or has_quoted_lyric_marker):
        return False
    for text in phrase_candidates:
        words = _word_count(text)
        if words >= 4:
            return True
    return False


def _artist_switch_marker(text: str) -> bool:
    lowered = text.casefold()
    return any(
        marker in lowered
        for marker in (
            "different artist",
            "new artist",
            "another artist",
            "other artist",
            "break away",
            "no more",
            "not ",
            "without ",
            "avoid ",
            "away from",
            "stop",
        )
    )


def _same_turn_artist_guard_targets(
    trace: dict,
    *,
    current_turn: int | None,
) -> list[dict[str, str]]:
    if not current_turn:
        return []
    state = trace.get("state") or trace.get("extracted_state") or {}
    current_request = state.get("current_request") or {}
    if _int_or_none(current_request.get("source_turn")) != int(current_turn):
        return []

    request_type = _current_request_type(trace)
    target_artist_mode = str(
        state.get("target_artist_mode")
        or current_request.get("target_artist_mode")
        or ""
    )
    if request_type not in {"new_artist", "different_artist"} and target_artist_mode not in {
        "new_artist",
        "different_artist",
    }:
        return []

    from mcrs.qu_modules.tag_resolver import catalog_tag_key

    request_text = " ".join(
        str(value or "")
        for value in (
            current_request.get("summary"),
            current_request.get("evidence_text"),
            state.get("turn_intent"),
        )
    )
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for fact in state.get("facts") or []:
        if not isinstance(fact, dict):
            continue
        if _int_or_none(fact.get("source_turn")) != int(current_turn):
            continue
        if fact.get("mentioned_current_turn") is not True:
            continue
        if str(fact.get("type") or "") != "artist":
            continue
        name = str(fact.get("value") or "").strip()
        name_key = catalog_tag_key(name)
        if not name_key or name_key in seen:
            continue

        role = str(fact.get("role") or "")
        anchor_use = str(fact.get("anchor_use") or "")
        relation = str(fact.get("relation") or "")
        reuse = str(fact.get("reuse") or "")
        evidence_text = str(fact.get("evidence_text") or "")
        fact_text = f"{request_text} {evidence_text}"
        is_hard_rejection = (
            role == "rejected"
            and anchor_use == "do_not_use"
            and (relation == "exclude" or reuse == "must_exclude")
        )
        is_different_artist_reference = (
            role == "satisfied_prior"
            and anchor_use == "do_not_use"
            and reuse in {"avoid_exact", "must_exclude"}
            and _artist_switch_marker(fact_text)
        )
        if not (is_hard_rejection or is_different_artist_reference):
            continue
        seen.add(name_key)
        out.append(
            {
                "artist_name": name,
                "artist_name_key": name_key,
                "role": role,
                "relation": relation,
            }
        )
    return out


def _exact_pin_ids(trace: dict) -> set[str]:
    pinned: set[str] = set()
    for action in trace.get("ranking_guard_actions") or []:
        if not isinstance(action, dict):
            continue
        if action.get("type") != "exact_track_pin":
            continue
        track_id = str(action.get("track_id") or "")
        if track_id:
            pinned.add(track_id)
    return pinned


def _artist_guard_match(
    track_id: str,
    *,
    catalog_meta: dict[str, dict],
    targets: list[dict[str, str]],
    resolver_rejected_artist_ids: set[str],
) -> dict[str, str] | None:
    meta = catalog_meta.get(track_id) or {}
    artist_name_keys = set(str(key) for key in meta.get("artist_name_keys") or [])
    if not artist_name_keys:
        return None
    artists = [str(artist_id) for artist_id in meta.get("artists") or []]
    matched_artist_id = ""
    for artist_id in artists:
        if artist_id in resolver_rejected_artist_ids:
            matched_artist_id = artist_id
            break
    for target in targets:
        if target["artist_name_key"] not in artist_name_keys:
            continue
        return {
            "matched_artist_id": matched_artist_id,
            "matched_artist_name": target["artist_name"],
            "evidence_role": target["role"],
            "evidence_relation": target["relation"],
        }
    return None


def _apply_final_artist_guard(
    ranked: list[str],
    trace: dict,
    *,
    catalog_meta: dict[str, dict],
    top_k_out: int,
    enabled: bool,
    guard_top_k: int,
    current_turn: int | None,
) -> list[str]:
    """Demote any track by an artist this turn just switched away from/rejected,
    out of the top `guard_top_k` slots.

    Last-resort safety net for the case the reranker's own artist features miss:
    an unpinned track in the guarded window whose artist matches a same-turn
    switch-away/rejection target gets pushed to the bottom of `ranked` (not
    dropped outright) and logged as a `ranking_guard_actions` trace entry.
    """
    if not enabled or guard_top_k <= 0:
        return ranked[:top_k_out]
    targets = _same_turn_artist_guard_targets(trace, current_turn=current_turn)
    if not targets:
        return ranked[:top_k_out]

    resolver = trace.get("resolver") or {}
    resolver_rejected_artist_ids = {
        str(artist_id) for artist_id in resolver.get("rejected_artist_ids") or []
    }
    pinned = _exact_pin_ids(trace)
    original_rank = {str(track_id): idx + 1 for idx, track_id in enumerate(ranked)}
    offender_records = []
    offender_ids: set[str] = set()
    for track_id in ranked[:guard_top_k]:
        track_id = str(track_id)
        if track_id in pinned:
            continue
        match = _artist_guard_match(
            track_id,
            catalog_meta=catalog_meta,
            targets=targets,
            resolver_rejected_artist_ids=resolver_rejected_artist_ids,
        )
        if match is None:
            continue
        offender_ids.add(track_id)
        offender_records.append({"track_id": track_id, **match})

    if not offender_records:
        return ranked[:top_k_out]
    kept = [track_id for track_id in ranked if str(track_id) not in offender_ids]
    if not kept:
        return ranked[:top_k_out]

    reranked = kept + [record["track_id"] for record in offender_records]
    request_type = _current_request_type(trace)
    actions = []
    for offset, record in enumerate(offender_records, start=1):
        track_id = record["track_id"]
        to_rank = len(kept) + offset
        from_rank = original_rank.get(track_id)
        if from_rank == to_rank:
            continue
        action = {
            "type": "final_artist_guard",
            "track_id": track_id,
            "from_rank": from_rank,
            "to_rank": to_rank,
            "request_type": request_type,
            "matched_artist_name": record["matched_artist_name"],
            "evidence_role": record["evidence_role"],
            "evidence_relation": record["evidence_relation"],
        }
        if record.get("matched_artist_id"):
            action["matched_artist_id"] = record["matched_artist_id"]
        actions.append(action)
    if actions:
        trace.setdefault("ranking_guard_actions", []).extend(actions)
    return reranked[:top_k_out]


def _resolved_exact_track_ids(
    trace: dict,
    *,
    min_confidence: float,
    current_turn: int | None = None,
) -> list[str]:
    if _current_request_type(trace) != "exact_track":
        return []
    if not _same_turn_exact_request(trace, current_turn):
        return []
    resolver = trace.get("resolver") or {}
    seen: set[str] = set()
    out: list[str] = []
    target_records = resolver.get("exact_track_targets") or []
    for target in target_records:
        if not isinstance(target, dict):
            continue
        track_id = str(target.get("track_id") or target.get("entity_id") or "")
        source_text = str(target.get("source_text") or "")
        try:
            confidence = float(target.get("confidence") or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0
        if not track_id or track_id in seen or confidence < min_confidence:
            continue
        if not _same_turn_exact_track_fact(
            trace,
            source_text=source_text,
            current_turn=current_turn,
        ):
            continue
        seen.add(track_id)
        out.append(track_id)
    return out


def _apply_branch_rescue(
    ranked: list[str],
    trace: dict,
    *,
    dropped: set[str],
    top_k_out: int,
    enabled: bool,
    guard_type: str,
    routing_tag: str,
    branch_name: str,
    top_n: int,
    target_rank: int,
    require_lyric_phrase: bool = False,
) -> list[str]:
    """Promote a top hit from one specific branch into the top `target_rank` slots.

    Guards against the reranker burying a track a routing-tagged branch (visual
    or lyric) surfaced strongly, when the turn's own signal (`routing_tag`, and
    for lyrics an actual lyric-phrase-like request) says that branch should be
    trusted. Only fires if `enabled` and the routing tag/phrase check pass; a
    no-op copy-and-truncate otherwise. `guard_type` only labels the trace entry
    this leaves behind, both calls below share this one implementation.
    """
    if not enabled or top_n <= 0 or target_rank <= 0:
        return ranked[:top_k_out]
    if not _routing_tag_enabled(trace, routing_tag):
        return ranked[:top_k_out]
    if require_lyric_phrase and not _lyric_phrase_like_request(trace):
        return ranked[:top_k_out]

    rescue_records = []
    seen: set[str] = set()
    branch_hits = _branch_hits(trace, branch_name)
    for branch_rank, (track_id, branch_score) in enumerate(branch_hits, start=1):
        if track_id in seen or track_id in dropped:
            continue
        seen.add(track_id)
        rescue_records.append(
            {
                "track_id": track_id,
                "branch_rank": branch_rank,
                "branch_score": branch_score,
            }
        )
        if len(rescue_records) >= top_n:
            break
    if not rescue_records:
        return ranked[:top_k_out]

    original_rank = {str(track_id): idx + 1 for idx, track_id in enumerate(ranked)}
    moving = []
    for record in rescue_records:
        track_id = record["track_id"]
        from_rank = original_rank.get(track_id)
        if from_rank is not None and from_rank <= target_rank:
            continue
        moving.append(record)
    if not moving:
        return ranked[:top_k_out]

    moving_ids = {record["track_id"] for record in moving}
    base = [track_id for track_id in ranked if track_id not in moving_ids]
    insert_at = min(max(target_rank - 1, 0), len(base))
    inserted = [record["track_id"] for record in moving]
    reranked = base[:insert_at] + inserted + base[insert_at:]

    request_type = _current_request_type(trace)
    actions = []
    for offset, record in enumerate(moving, start=0):
        track_id = record["track_id"]
        to_rank = insert_at + offset + 1
        from_rank = original_rank.get(track_id)
        if from_rank == to_rank:
            continue
        actions.append(
            {
                "type": guard_type,
                "track_id": track_id,
                "from_rank": from_rank,
                "to_rank": to_rank,
                "request_type": request_type,
                "routing_tag": routing_tag,
                "branch_name": branch_name,
                "branch_rank": record["branch_rank"],
                "branch_score": record["branch_score"],
            }
        )
    if actions:
        trace.setdefault("ranking_guard_actions", []).extend(actions)
    return reranked[:top_k_out]


def _apply_exact_track_pins(
    ranked: list[str],
    trace: dict,
    *,
    dropped: set[str],
    top_k_out: int,
    pin_limit: int,
    min_confidence: float,
    current_turn: int | None = None,
) -> list[str]:
    """Pin high-confidence exact-track resolver targets to the very top of `ranked`.

    Guards against the reranker outranking a track the user named outright
    (e.g. "play Yesterday by the Beatles") in favor of a merely similar one.
    Up to `pin_limit` targets at or above `min_confidence` get pinned, skipping
    ones already hard-dropped unless they were actually played and not rejected.
    """
    if pin_limit <= 0:
        return ranked[:top_k_out]
    resolver = trace.get("resolver") or {}
    played = {str(track_id) for track_id in resolver.get("played_track_ids") or []}
    rejected = {str(track_id) for track_id in resolver.get("rejected_track_ids") or []}
    pins: list[str] = []
    drop_overrides: dict[str, str] = {}
    for track_id in _resolved_exact_track_ids(
        trace,
        min_confidence=min_confidence,
        current_turn=current_turn,
    )[:pin_limit]:
        if track_id in dropped:
            if track_id not in played or track_id in rejected:
                continue
            drop_overrides[track_id] = "played_exact_request"
        pins.append(track_id)
    if not pins:
        return ranked[:top_k_out]

    original_rank = {str(track_id): idx + 1 for idx, track_id in enumerate(ranked)}
    pin_set = set(pins)
    reranked = pins + [track_id for track_id in ranked if str(track_id) not in pin_set]

    actions = []
    request_type = _current_request_type(trace)
    for idx, track_id in enumerate(pins, start=1):
        from_rank = original_rank.get(track_id)
        if from_rank == idx:
            continue
        actions.append(
            {
                "type": "exact_track_pin",
                "track_id": track_id,
                "from_rank": from_rank,
                "to_rank": idx,
                "request_type": request_type,
                **(
                    {"drop_override": drop_override}
                    if (drop_override := drop_overrides.get(track_id))
                    else {}
                ),
            }
        )
    if actions:
        trace.setdefault("ranking_guard_actions", []).extend(actions)
    return reranked[:top_k_out]


def session_entry_from_meta(meta: dict) -> dict:
    """Build the load_sessions()-shaped entry from a raw dataset row (parity
    with scripts/rerank/build_features.load_sessions)."""
    import ast
    from collections import defaultdict

    meta = dict(meta)
    for k in ("conversations", "user_profile", "conversation_goal"):
        if isinstance(meta.get(k), str):  # some HF caches store literals
            try:
                meta[k] = ast.literal_eval(meta[k])
            except Exception:
                meta[k] = [] if k == "conversations" else {}

    played, user_text = defaultdict(list), {}
    for msg in meta.get("conversations") or []:
        role = msg.get("role")
        tn = int(msg.get("turn_number") or 0)
        if role == "music":
            played[tn].append(str(msg.get("content")))
        elif role == "user":
            user_text[tn] = str(msg.get("content"))
    p = meta.get("user_profile") or {}
    g = meta.get("conversation_goal") or {}
    return {
        "played_by_turn": dict(played),
        "user_text_by_turn": user_text,
        "session_date": str(meta.get("session_date") or ""),
        "age": p.get("age"), "age_group": str(p.get("age_group") or ""),
        "gender": str(p.get("gender") or ""),
        "culture": str(p.get("preferred_musical_culture") or ""),
        "goal_category": str(g.get("category") or ""),
        "goal_specificity": str(g.get("specificity") or ""),
        "listener_goal": str(g.get("listener_goal") or ""),
    }


class LgbmOnlineReranker:
    def __init__(
        self,
        cfg: dict,
        db_uri: str,
        table_name: str = "music_track_catalog",
        catalog_source: Any | None = None,
    ):
        load_timings: dict[str, float] = {}
        total_start = time.perf_counter()

        def add_elapsed(key: str, start: float) -> None:
            load_timings[key] = load_timings.get(key, 0.0) + (time.perf_counter() - start)

        start = time.perf_counter()
        import lightgbm as lgb
        add_elapsed("import_lightgbm", start)

        start = time.perf_counter()
        from mcrs.qu_modules.tag_resolver import TagEmbeddingIndex, TieredTagResolver

        from build_features import Catalog, EmbedMemo, NpzEmbedStore, load_user_cf
        from features import TurnContext
        add_elapsed("import_feature_helpers", start)

        start = time.perf_counter()
        self.booster = lgb.Booster(model_file=str(cfg["model_path"]))
        add_elapsed("booster", start)
        start = time.perf_counter()
        meta = json.load(open(cfg["meta_path"]))
        self.cols: list[str] = meta["cols"]
        self.cat_maps: dict = json.load(open(cfg["cat_maps"]))
        branch_names = json.load(open(cfg["branch_names"]))
        add_elapsed("metadata", start)
        n_model = self.booster.num_feature()
        assert n_model == len(self.cols), (
            f"model expects {n_model} features, meta has {len(self.cols)}")

        start = time.perf_counter()
        cat = _load_feature_catalog(
            catalog_source=catalog_source,
            offline_catalog_cls=Catalog,
            db_uri=db_uri,
            table_name=table_name,
        )
        add_elapsed("catalog", start)
        start = time.perf_counter()
        tag_index = TagEmbeddingIndex.load(str(cfg["tag_index"]))
        add_elapsed("tag_index", start)
        start = time.perf_counter()
        tag_vec = {t: tag_index.matrix[i] for i, t in enumerate(tag_index.tags)}
        vocab = frozenset(tag_index.tags)
        add_elapsed("tag_vectors", start)
        start = time.perf_counter()
        resolver = TieredTagResolver(catalog_tag_keys=vocab, substring_vocab=vocab)
        add_elapsed("resolver", start)
        start = time.perf_counter()
        memo = EmbedMemo(Path(cfg["embed_memo"]))
        add_elapsed("embed_memo", start)
        start = time.perf_counter()
        msg_store = NpzEmbedStore(cfg["msg_store"])
        add_elapsed("msg_store", start)
        start = time.perf_counter()
        user_cf = load_user_cf()
        add_elapsed("user_cf", start)
        start = time.perf_counter()
        self.ctx = TurnContext(
            cat, sessions={}, user_cf=user_cf, resolver=resolver,
            tag_vec=tag_vec, memo=memo, msg_store=msg_store,
            branch_names=branch_names, pool_k=int(cfg.get("pool_k", 500)),
            offline=False)  # live-embed unseen query/message strings
        add_elapsed("turn_context", start)
        # b1_cos (4B fine-tuned bi-encoder cosine) — load the encoder ONLY if the
        # model uses the feature. Per turn we build the goal-free v_struct_pt query
        # from the session, encode (local 4B), and pass the vec via the per-call
        # row["b1_qvec"] (thread-local); b1_cos then computes via cat.v("b1_vstructpt_4b").
        # No retrieval branch, no pool change.
        self.b1 = None
        if "b1_cos" in self.cols:
            start = time.perf_counter()
            from b1_live import B1Live
            self.b1 = B1Live(cat, db_uri=db_uri, table_name=table_name)
            add_elapsed("b1_encoder", start)
        self.top_k_out = int(cfg.get("top_k_out", 1000))
        self.exact_pin_top_n = int(cfg.get("exact_pin_top_n", 2))
        self.exact_pin_min_confidence = float(cfg.get("exact_pin_min_confidence", 90.0))
        self.visual_rescue_enabled = _as_bool(cfg.get("visual_rescue_enabled", False))
        self.visual_rescue_top_n = int(cfg.get("visual_rescue_top_n", 1))
        self.visual_rescue_target_rank = int(cfg.get("visual_rescue_target_rank", 10))
        self.lyric_rescue_enabled = _as_bool(cfg.get("lyric_rescue_enabled", False))
        self.lyric_rescue_top_n = int(cfg.get("lyric_rescue_top_n", 1))
        self.lyric_rescue_target_rank = int(cfg.get("lyric_rescue_target_rank", 10))
        self.lyric_rescue_require_phrase = _as_bool(
            cfg.get("lyric_rescue_require_phrase", True)
        )
        self.final_artist_guard_enabled = _as_bool(
            cfg.get("final_artist_guard_enabled", False)
        )
        self.final_artist_guard_top_k = int(cfg.get("final_artist_guard_top_k", 1))
        add_elapsed("total", total_start)
        self.load_timings = load_timings

    def flush(self) -> None:
        """Persist any live-filled reranker embedding caches."""
        for store in (getattr(self.ctx, "memo", None), getattr(self.ctx, "msg_store", None)):
            flush = getattr(store, "flush", None)
            if callable(flush):
                flush()

    def _assemble(self, rows: list[dict]) -> np.ndarray:
        X = np.empty((len(rows), len(self.cols)), dtype=np.float32)
        for j, c in enumerate(self.cols):
            if c in CATEGORICALS:
                m = self.cat_maps[c]
                X[:, j] = [float(m.get(str(r.get(c, "")), -1)) for r in rows]
            else:
                X[:, j] = [float(r[c]) if (c in r and r[c] == r[c]) else np.nan
                           for r in rows]
        return X

    def rerank(self, trace: dict, session_meta: dict | None,
               user_id: str | None, hard_drop: set[str],
               fallback: list[str]) -> list[str]:
        """Score+order the branch-pool union with the LightGBM booster, then run it
        through `finalize()`'s post-score guard chain (see each guard's own
        docstring): exact-track pins, then visual/lyric branch rescue, then the
        final-artist demotion guard -- each a narrow, config-gated correction for
        a failure mode the learned score alone doesn't reliably catch. Keeps hard
        drops out of the RRF fallback path used on reranker failure.
        """
        from features import compute_turn_features
        dropped = {str(track_id) for track_id in hard_drop}
        pin_limit = int(getattr(self, "exact_pin_top_n", 2))
        min_confidence = float(getattr(self, "exact_pin_min_confidence", 90.0))
        visual_rescue_enabled = _as_bool(getattr(self, "visual_rescue_enabled", False))
        visual_rescue_top_n = int(getattr(self, "visual_rescue_top_n", 1))
        visual_rescue_target_rank = int(getattr(self, "visual_rescue_target_rank", 10))
        lyric_rescue_enabled = _as_bool(getattr(self, "lyric_rescue_enabled", False))
        lyric_rescue_top_n = int(getattr(self, "lyric_rescue_top_n", 1))
        lyric_rescue_target_rank = int(getattr(self, "lyric_rescue_target_rank", 10))
        lyric_rescue_require_phrase = _as_bool(
            getattr(self, "lyric_rescue_require_phrase", True)
        )
        final_artist_guard_enabled = _as_bool(
            getattr(self, "final_artist_guard_enabled", False)
        )
        final_artist_guard_top_k = int(getattr(self, "final_artist_guard_top_k", 1))
        current_turn = int((session_meta or {}).get("turn_number") or 0)

        def filtered_fallback() -> list[str]:
            return [
                str(track_id)
                for track_id in fallback
                if str(track_id) not in dropped
            ][: self.top_k_out]

        def finalize(ranked: list[str]) -> list[str]:
            guarded = _apply_exact_track_pins(
                [str(track_id) for track_id in ranked],
                trace,
                dropped=dropped,
                top_k_out=self.top_k_out,
                pin_limit=pin_limit,
                min_confidence=min_confidence,
                current_turn=current_turn,
            )
            guarded = _apply_branch_rescue(
                guarded,
                trace,
                dropped=dropped,
                top_k_out=self.top_k_out,
                enabled=visual_rescue_enabled,
                guard_type="visual_branch_rescue",
                routing_tag="image_or_visual_search",
                branch_name=VISUAL_RESCUE_BRANCH,
                top_n=visual_rescue_top_n,
                target_rank=visual_rescue_target_rank,
            )
            guarded = _apply_branch_rescue(
                guarded,
                trace,
                dropped=dropped,
                top_k_out=self.top_k_out,
                enabled=lyric_rescue_enabled,
                guard_type="lyric_branch_rescue",
                routing_tag="lyric_search",
                branch_name=LYRIC_RESCUE_BRANCH,
                top_n=lyric_rescue_top_n,
                target_rank=lyric_rescue_target_rank,
                require_lyric_phrase=lyric_rescue_require_phrase,
            )
            return _apply_final_artist_guard(
                guarded,
                trace,
                catalog_meta=self.ctx.cat.meta,
                top_k_out=self.top_k_out,
                enabled=final_artist_guard_enabled,
                guard_top_k=final_artist_guard_top_k,
                current_turn=current_turn,
            )

        try:
            if not (trace.get("branches") or {}).get("pools"):
                return finalize(filtered_fallback())
            sid = str((session_meta or {}).get("session_id") or "")
            tn = current_turn
            if session_meta:
                self.ctx.sessions[sid] = session_entry_from_meta(session_meta)
            trace_for_features = trace
            if dropped:
                branches = dict(trace.get("branches") or {})
                existing_drop = {str(track_id) for track_id in branches.get("hard_drop") or []}
                branches["hard_drop"] = sorted(existing_drop | dropped)
                trace_for_features = {**trace, "branches": branches}
            row = {"session_id": sid, "turn_number": tn,
                   "user_id": user_id, "trace": trace_for_features}
            # b1_cos: encode the per-turn query and pass the vec THROUGH THE ROW
            # (thread-local) — never stash on the shared self.ctx (concurrent
            # rerank() threads would clobber each other -> NaN b1_cos). getattr so
            # rerankers built via __new__ (tests) without __init__ don't AttributeError.
            b1 = getattr(self, "b1", None)
            if b1 is not None:
                sent = self.ctx.sessions.get(sid)
                if sent is not None:
                    row["b1_qvec"] = b1.query_vecs([b1.query_text(sent, tn)])[0]
            rows, _ = compute_turn_features(row, self.ctx, gt=None)
            if not rows:
                return finalize(filtered_fallback())
            # sidecar constraint features — shared helper with the offline builder
            # (build_features.constraint_feature_row) so train/serve cannot drift
            from build_features import constraint_feature_row

            res = trace.get("resolver") or {}
            played = frozenset(str(x) for x in res.get("played_track_ids") or [])
            rej_tracks = frozenset(str(x) for x in res.get("rejected_track_ids") or [])
            rej_artists = frozenset(str(x) for x in res.get("rejected_artist_ids") or [])
            for r in rows:
                tid = r["track_id"]
                arts = self.ctx.cat.meta.get(tid, {}).get("artists", ())
                r.update(constraint_feature_row(
                    tid, arts, played=played, rejected_tracks=rej_tracks,
                    rejected_artists=rej_artists,
                    target_artist_mode=r.get("target_artist_mode"),
                    same_artist_session=r.get("same_artist_session")))
            X = self._assemble(rows)
            scores = self.booster.predict(X)
            order = np.argsort(-scores)
            ranked = [rows[i]["track_id"] for i in order
                      if str(rows[i]["track_id"]) not in dropped]
            seen = set(ranked)
            for t in fallback:  # preserve depth for downstream consumers
                if t not in seen and str(t) not in dropped:
                    ranked.append(t)
                    seen.add(t)
            return finalize(ranked)
        except Exception as e:  # serving must never hard-fail a turn
            print(f"[lgbm_reranker] fallback (turn {session_meta}): {e!r}",
                  flush=True)
            return finalize(filtered_fallback())
