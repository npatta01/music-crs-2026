"""Online LightGBM (v9) reranker — serves the trained LambdaMART in-pipeline.

Consumes the SAME trace payload the offline feature builder reads and computes
features via the SAME `compute_turn_features` (scripts/rerank/features_v9.py),
so train/serve drift is structurally impossible. Hooked by V0PlusCompilerQU
right after trace assembly; replaces the RRF order over the branch-pool union.

Config (qu_kwargs.reranker). The model bundle is committed under
models/reranker_v9/ (ships in the repo + the Modal image); the large caches are
not committed (see docs/reproduce_reranker.md):
  enabled: true
  model_path:    models/reranker_v9/model.txt        (LightGBM booster)
  meta_path:     models/reranker_v9/meta.json        ({cols, cat_idx})
  cat_maps:      models/reranker_v9/cat_maps.json    (categorical value->code)
  branch_names:  models/reranker_v9/branch_names.json (canonical 11)
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
        self.artist_id_to_name_key: dict[str, str] = {}
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
            for aid, nm in zip(artists, artist_names):
                k = catalog_tag_key(str(nm or ""))
                if aid and k:
                    self.artist_id_to_name_key.setdefault(str(aid), k)
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
        from features_v9 import TurnContext
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
        self.top_k_out = int(cfg.get("top_k_out", 1000))
        add_elapsed("total", total_start)
        self.load_timings = load_timings

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
        """Re-order the branch-pool union; returns top_k_out ids (backfilled
        from `fallback` to preserve depth). Any failure -> fallback unchanged."""
        from features_v9 import compute_turn_features

        try:
            if not (trace.get("branches") or {}).get("pools"):
                return fallback
            sid = str((session_meta or {}).get("session_id") or "")
            tn = int((session_meta or {}).get("turn_number") or 0)
            if session_meta:
                self.ctx.sessions[sid] = session_entry_from_meta(session_meta)
            row = {"session_id": sid, "turn_number": tn,
                   "user_id": user_id, "trace": trace}
            rows, _ = compute_turn_features(row, self.ctx, gt=None)
            if not rows:
                return fallback
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
                      if rows[i]["track_id"] not in hard_drop]
            seen = set(ranked)
            for t in fallback:  # preserve depth for downstream consumers
                if t not in seen and t not in hard_drop:
                    ranked.append(t)
                    seen.add(t)
            return ranked[: self.top_k_out]
        except Exception as e:  # serving must never hard-fail a turn
            print(f"[lgbm_reranker] fallback (turn {session_meta}): {e!r}",
                  flush=True)
            return fallback
