"""Build LTR training features from a devset trace (fully local).

Per turn: candidates = union of every branch's top-`pool_k` hits. Per
candidate ~70 features across pool/catalog/session/user/organizer/state
groups, plus named crosses and within-pool percentiles. Output: parquet.

Only network use: DeepInfra Qwen3-0.6B embeddings for the per-turn dense
query strings + per-session listener_goal (memoized to disk; ~$0.05 total).

Usage:
  python scripts/rerank/build_features.py \
      --trace exp/inference/devset/<tid>_trace.jsonl \
      --ground-truth exp/ground_truth/devset.json \
      --db-uri <repo>/cache/lancedb \
      --tag-index <repo>/cache/tag_embedding_index/qwen_0_6b.npz \
      --out exp/analysis/rerank/features
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import threading
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from datetime import date
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_FEATURE_SHARDS = 12
DEFAULT_FEATURE_WORKERS = 4
LEGACY_DEFAULT_OUT = "exp/analysis/rerank/features.parquet"
DEFAULT_PARALLEL_OUT = "exp/analysis/rerank/features"

from mcrs.qu_modules.tag_resolver import (  # noqa: E402
    TagEmbeddingIndex,
    TieredTagResolver,
    catalog_tag_key,
)

import re

NEGATION_RE = re.compile(
    r"\b(no|not|don'?t|other than|different|enough|besides|except|instead of|tired of|good on)\b",
    re.I)
WANTS_NEW_RE = re.compile(
    r"\b(different|new|other|else|someone else|another artist|fresh|haven'?t heard)\b", re.I)

VECTOR_FIELDS = {
    "cf_bpr": "cf",
    "audio_laion_clap": "clap",
    "image_siglip2": "siglip",
    "metadata_qwen3_embedding_0_6b": "q06_meta",
    "attributes_qwen3_embedding_0_6b": "q06_attr",
    "lyrics_qwen3_embedding_0_6b": "q06_lyr",
    "b1_vstructpt_4b": "b1",  # 4B fine-tuned conv->track doc vec (scout_cos); L2-normed in catalog
}


@contextmanager
def _exclusive_file_lock(path: Path):
    """Best-effort cross-process lock for local cache writers."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_file = path.open("a+b")
    try:
        try:
            import fcntl
        except ImportError:  # pragma: no cover - non-POSIX fallback.
            fcntl = None
        if fcntl is not None:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        if fcntl is not None:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        lock_file.close()


def _norm_rows(mat: np.ndarray) -> np.ndarray:
    return mat / np.maximum(np.linalg.norm(mat, axis=1, keepdims=True), 1e-9)


def _load_dotenv() -> None:
    dotenv_path = PROJECT_ROOT / ".env"
    if not dotenv_path.exists():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        for line in dotenv_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))
        return
    load_dotenv(dotenv_path)


def constraint_feature_row(track_id, artists, *, played, rejected_tracks,
                           rejected_artists, target_artist_mode,
                           same_artist_session):
    """The four sidecar constraint features for ONE candidate.

    Single source of truth for the online reranker (mcrs/qu_modules/lgbm_reranker)
    and the offline sidecar builder (build_constraint_features) so they cannot
    silently drift. `played`/`rejected_*` are membership sets of track/artist ids;
    `artists` is the candidate's artist-id tuple."""
    mode = str(target_artist_mode or "")
    return {
        "is_played_track": float(track_id in played),
        "rejected_track_exact": float(track_id in rejected_tracks),
        "rejected_artist_exact": float(
            bool(rejected_artists) and any(a in rejected_artists for a in artists)),
        "violates_new_artist": float(
            ("new" in mode or "different" in mode)
            and float(same_artist_session or 0.0) > 0),
    }


class Catalog:
    def __init__(self, db_uri: str, table_name: str):
        import lancedb

        db = lancedb.connect(db_uri)
        table = db.open_table(table_name)
        self._arrow_table = None
        try:
            self.ds = table.to_lance()
            names = set(self.ds.schema.names)
        except ImportError:
            # Local replay does not require the optional pylance package.
            # LanceDB can still materialize the 47k-row catalog as Arrow; use
            # that as a fallback and project columns from the in-memory table.
            self.ds = None
            self._arrow_table = table.to_arrow()
            names = set(self._arrow_table.schema.names)
        scalars = ["track_id", "track_name", "artist_name", "popularity",
                   "release_date", "artist_id", "album_id", "tag_list", "duration"]
        cols = [c for c in scalars if c in names]
        tbl = self._to_pydict(cols)
        n = len(tbl["track_id"])
        self.meta: dict[str, dict] = {}
        self.has_duration = "duration" in tbl
        pops, years = {}, {}
        artist_track_counter: Counter = Counter()
        for i in range(n):
            tid = str(tbl["track_id"][i])
            artists = tuple(str(a) for a in (tbl["artist_id"][i] or []))
            albums = tuple(str(a) for a in (tbl["album_id"][i] or []))
            rd = tbl["release_date"][i]
            year = None
            try:
                year = (rd if isinstance(rd, date) else date.fromisoformat(str(rd)[:10])).year
            except Exception:
                pass
            tags = [str(t) for t in (tbl["tag_list"][i] or [])]
            tag_keys = frozenset(catalog_tag_key(t) for t in tags) - {""}
            name_raw = tbl["track_name"][i] if "track_name" in tbl else ""
            if isinstance(name_raw, (list, tuple)):
                name_raw = " ".join(str(x) for x in name_raw)
            a_raw = tbl["artist_name"][i] if "artist_name" in tbl else []
            if not isinstance(a_raw, (list, tuple, np.ndarray)):
                a_raw = [a_raw]
            artist_name_keys = tuple(
                k for k in (catalog_tag_key(str(a or "")) for a in a_raw) if k)
            self.meta[tid] = {
                "artists": artists, "albums": albums, "year": year,
                "pop": float(tbl["popularity"][i] or 0.0),
                "tag_keys": tag_keys, "n_tags": len(tags),
                "name_tokens": frozenset(catalog_tag_key(str(name_raw or "")).split()) - {""},
                "artist_name_keys": artist_name_keys,
                "duration": float(tbl["duration"][i]) if self.has_duration and tbl["duration"][i] is not None else np.nan,
            }
            pops[tid] = self.meta[tid]["pop"]
            if year is not None:
                years[tid] = year
            for a in artists:
                artist_track_counter[a] += 1
        self.artist_track_count = dict(artist_track_counter)

        all_pop = np.sort(np.array(list(pops.values())))
        self.pop_pct = {t: float(np.searchsorted(all_pop, p) / len(all_pop)) for t, p in pops.items()}
        by_year = defaultdict(list)
        for t, y in years.items():
            by_year[y].append(pops[t])
        ys = {y: np.sort(np.array(v)) for y, v in by_year.items()}
        self.era_pop_pct = {t: float(np.searchsorted(ys[y], pops[t]) / len(ys[y])) for t, y in years.items()}

        dfc: Counter = Counter()
        for m in self.meta.values():
            dfc.update(m["tag_keys"])
        self.tag_idf = {t: math.log((n + 1) / (c + 1)) for t, c in dfc.items()}

        # within-artist popularity percentile: how famous is this track among
        # its (most prolific) artist's tracks — head-ordering discriminator.
        artist_pops: dict[str, list[float]] = defaultdict(list)
        for tid, m in self.meta.items():
            for a in m["artists"]:
                artist_pops[a].append(m["pop"])
        artist_pop_sorted = {a: np.sort(np.array(v)) for a, v in artist_pops.items()}
        self.within_artist_pop = {}
        for tid, m in self.meta.items():
            best = 0.0
            for a in m["artists"]:
                arr = artist_pop_sorted[a]
                if len(arr) > 1:
                    best = max(best, float(np.searchsorted(arr, m["pop"]) / (len(arr) - 1)))
                else:
                    best = max(best, 1.0)
            self.within_artist_pop[tid] = best

        durs = np.array([m["duration"] for m in self.meta.values() if not math.isnan(m["duration"])])
        self.median_duration = float(np.median(durs)) if len(durs) else 0.0
        yrs = [m["year"] for m in self.meta.values() if m["year"]]
        self.median_year = int(np.median(yrs)) if yrs else 2008

        self.vec: dict[str, np.ndarray] = {}
        self.vec_idx: dict[str, dict[str, int]] = {}
        for field in VECTOR_FIELDS:
            if field not in names:
                continue
            t = self._to_pydict(["track_id", field])
            ids, rows = [], []
            for tid, v in zip(t["track_id"], t[field]):
                if v is not None and len(v):
                    ids.append(str(tid))
                    rows.append(np.asarray(v, dtype=np.float32))
            self.vec[field] = _norm_rows(np.vstack(rows))
            self.vec_idx[field] = {t_: i for i, t_ in enumerate(ids)}


    def _to_pydict(self, columns: list[str]) -> dict:
        if self.ds is not None:
            return self.ds.to_table(columns=columns).to_pydict()
        return self._arrow_table.select(columns).to_pydict()

    def v(self, field: str, tid: str) -> np.ndarray | None:
        i = self.vec_idx.get(field, {}).get(tid)
        return self.vec[field][i] if i is not None else None


class EmbedMemo:
    """Disk-memoized Qwen3-0.6B text embeddings (DeepInfra)."""

    def __init__(self, memo_path: Path):
        self.path = memo_path
        self.memo: dict[str, list[float]] = {}
        if memo_path.exists():
            self.memo = json.loads(memo_path.read_text())
        self._client = None
        self._dirty = 0
        # In-process thread safety: the online reranker shares one store across
        # rerank() calls fanned out via asyncio.to_thread (max_in_flight). The
        # file lock in flush() only coordinates across processes — it does not
        # serialize the in-memory read-modify-write of `memo`/`_dirty` between
        # threads of one process. Reentrant: get_many() calls flush() under it.
        self._lock = threading.RLock()

    def _embed_remote(self, texts: list[str]) -> list[list[float]]:
        if self._client is None:
            from mcrs.embeddings.litellm_client import LiteLLMEmbeddingClient
            self._client = LiteLLMEmbeddingClient(
                model_name="openai/Qwen/Qwen3-Embedding-0.6B",
                api_base="https://api.deepinfra.com/v1/openai",
                api_key=os.environ.get("DEEPINFRA_API_KEY"),
                batch_size=64, encoding_format="float")
        return self._client.embed_batch(texts)

    def get_many(self, texts: list[str], offline: bool = False) -> dict[str, np.ndarray]:
        with self._lock:
            if not offline:
                missing = [t for t in texts if t and hashlib.sha1(t.encode()).hexdigest() not in self.memo]
                missing = list(dict.fromkeys(missing))
                for start in range(0, len(missing), 64):
                    chunk = missing[start:start + 64]
                    for text, vec in zip(chunk, self._embed_remote(chunk)):
                        self.memo[hashlib.sha1(text.encode()).hexdigest()] = vec
                        self._dirty += 1
                if self._dirty >= 500:
                    self.flush()
            out = {}
            for t in texts:
                if not t:
                    continue
                v = self.memo.get(hashlib.sha1(t.encode()).hexdigest())
                if v:
                    a = np.asarray(v, dtype=np.float32)
                    out[t] = a / max(float(np.linalg.norm(a)), 1e-9)
            return out

    def flush(self):
        with self._lock:
            if self._dirty:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with _exclusive_file_lock(self.path.with_suffix(self.path.suffix + ".lock")):
                    latest = {}
                    if self.path.exists():
                        latest = json.loads(self.path.read_text(encoding="utf-8") or "{}")
                    latest.update(self.memo)
                    tmp = self.path.with_name(f".{self.path.name}.{os.getpid()}.tmp")
                    tmp.write_text(json.dumps(latest), encoding="utf-8")
                    os.replace(tmp, self.path)
                    self.memo = latest
                self._dirty = 0


class NpzEmbedStore:
    """Chunked float16 embedding store — replaces the JSON memo at train-split
    scale (250k strings would need ~14GB+ as a Python dict; this caps RAM at
    the hash index plus lazily-loaded chunks)."""

    def __init__(self, dir_path):
        import hashlib
        self._sha = lambda t: hashlib.sha1(t.encode()).hexdigest()
        self.dir = Path(dir_path)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.index: dict[str, tuple[str, int]] = {}
        self._chunks: dict[str, np.ndarray] = {}
        self._load_index_from_disk()
        self._pend_keys: list[str] = []
        self._pend_vecs: list[np.ndarray] = []
        self._client = None
        # In-process thread safety (see EmbedMemo): the file lock in flush()
        # serializes across processes, but the in-memory pending buffer / index
        # are mutated by add()/get_many() with no lock. Without this a flush()
        # that resets _pend_keys/_pend_vecs can race a concurrent get_many()
        # reading pend_idx -> IndexError. Reentrant: get_many() calls flush().
        self._lock = threading.RLock()

    def _load_index_from_disk(self) -> None:
        self.index = {}
        for f in sorted(self.dir.glob("chunk_*.npz")):
            keys = np.load(f, allow_pickle=False)["keys"]
            cid = f.stem
            for i, k in enumerate(keys):
                self.index[str(k)] = (cid, i)

    def _next_chunk_id(self) -> str:
        max_id = -1
        for f in self.dir.glob("chunk_*.npz"):
            try:
                max_id = max(max_id, int(f.stem.rsplit("_", 1)[1]))
            except (IndexError, ValueError):
                continue
        return f"chunk_{max_id + 1:05d}"

    def _matrix(self, cid: str) -> np.ndarray:
        if cid not in self._chunks:
            self._chunks[cid] = np.load(self.dir / f"{cid}.npz", allow_pickle=False)["vectors"]
        return self._chunks[cid]

    def _embed_remote(self, texts: list[str]) -> list[list[float]]:
        if self._client is None:
            import os

            from mcrs.embeddings.litellm_client import LiteLLMEmbeddingClient
            self._client = LiteLLMEmbeddingClient(
                model_name="openai/Qwen/Qwen3-Embedding-0.6B",
                api_base="https://api.deepinfra.com/v1/openai",
                api_key=os.environ.get("DEEPINFRA_API_KEY"),
                batch_size=64, encoding_format="float")
        return self._client.embed_batch(texts)

    def add(self, text: str, vec) -> None:
        with self._lock:
            h = self._sha(text)
            if h in self.index or h in set(self._pend_keys):
                return
            self._pend_keys.append(h)
            self._pend_vecs.append(np.asarray(vec, dtype=np.float16))

    def add_hashed(self, h: str, vec) -> None:
        with self._lock:
            if h in self.index or h in set(self._pend_keys):
                return
            self._pend_keys.append(h)
            self._pend_vecs.append(np.asarray(vec, dtype=np.float16))

    def get_many(self, texts: list[str], offline: bool = False) -> dict[str, np.ndarray]:
        with self._lock:
            pend_idx = {k: i for i, k in enumerate(self._pend_keys)}
            if not offline:
                missing = list(dict.fromkeys(
                    t for t in texts
                    if t and self._sha(t) not in self.index and self._sha(t) not in pend_idx))
                for start in range(0, len(missing), 64):
                    chunk = missing[start:start + 64]
                    for text, vec in zip(chunk, self._embed_remote(chunk)):
                        self.add(text, vec)
                pend_idx = {k: i for i, k in enumerate(self._pend_keys)}
                if len(self._pend_keys) >= 8192:
                    self.flush()
                    pend_idx = {}
            out: dict[str, np.ndarray] = {}
            for t in texts:
                if not t:
                    continue
                h = self._sha(t)
                v = None
                if h in self.index:
                    cid, row = self.index[h]
                    v = self._matrix(cid)[row].astype(np.float32)
                elif h in pend_idx:
                    v = self._pend_vecs[pend_idx[h]].astype(np.float32)
                if v is not None:
                    n = float(np.linalg.norm(v))
                    out[t] = v / n if n > 0 else v
            return out

    def flush(self) -> None:
        with self._lock:
            if not self._pend_keys:
                return
            with _exclusive_file_lock(self.dir / ".npz_embed_store.lock"):
                self._load_index_from_disk()
                fresh_keys = []
                fresh_vecs = []
                pending_seen = set()
                for key, vec in zip(self._pend_keys, self._pend_vecs):
                    if key in self.index or key in pending_seen:
                        continue
                    pending_seen.add(key)
                    fresh_keys.append(key)
                    fresh_vecs.append(vec)
                if not fresh_keys:
                    self._pend_keys, self._pend_vecs = [], []
                    return

                cid = self._next_chunk_id()
                final_path = self.dir / f"{cid}.npz"
                tmp_path = self.dir / f".{cid}.{os.getpid()}.tmp.npz"
                with tmp_path.open("wb") as handle:
                    np.savez_compressed(
                        handle,
                        keys=np.asarray(fresh_keys),
                        vectors=np.vstack(fresh_vecs).astype(np.float16))
                os.replace(tmp_path, final_path)
                for i, k in enumerate(fresh_keys):
                    self.index[k] = (cid, i)
            self._pend_keys, self._pend_vecs = [], []
from mcrs.qu_modules.tag_resolver import (  # noqa: E402
    TagEmbeddingIndex,
    TieredTagResolver,
    catalog_tag_key,
)


def load_sessions(dataset_name: str = "talkpl-ai/TalkPlayData-Challenge-Dataset",
                  split: str = "test"):
    """Session context (played history, user text, goal, profile) per session.

    MUST point at the dataset being SERVED: blind sessions are absent from the
    devset dataset, and a miss silently zeroes the whole session-history block
    (heard-artist machinery, msg cosines, goal/demographics) — the round-2
    blind-serving bug."""
    import ast

    from datasets import load_dataset

    ds = load_dataset(dataset_name, split=split)
    out = {}
    for row in ds:
        if isinstance(row.get("conversations"), str):
            row = dict(row)
            row["conversations"] = ast.literal_eval(row["conversations"])
            for k in ("user_profile", "conversation_goal"):
                if isinstance(row.get(k), str):
                    try:
                        row[k] = ast.literal_eval(row[k])
                    except Exception:
                        row[k] = {}
        sid = str(row["session_id"])
        played, user_text = defaultdict(list), {}
        for msg in row["conversations"]:
            if msg["role"] == "music":
                played[int(msg["turn_number"])].append(str(msg["content"]))
            elif msg["role"] == "user":
                user_text[int(msg["turn_number"])] = str(msg["content"])
        p = row.get("user_profile") or {}
        g = row.get("conversation_goal") or {}
        out[sid] = {
            "played_by_turn": dict(played),
            "user_text_by_turn": user_text,
            "session_date": str(row.get("session_date") or ""),
            "age": p.get("age"), "age_group": str(p.get("age_group") or ""),
            "gender": str(p.get("gender") or ""),
            "culture": str(p.get("preferred_musical_culture") or ""),
            "goal_category": str(g.get("category") or ""),
            "goal_specificity": str(g.get("specificity") or ""),
            "listener_goal": str(g.get("listener_goal") or ""),
        }
    return out


def load_user_cf():
    from mcrs.qu_modules.user_embeddings import UserEmbeddings

    ue = UserEmbeddings()
    fields = tuple(ue.available_fields)
    field = "cf_bpr" if "cf_bpr" in fields else (fields[0] if fields else None)
    out = {}
    if field:
        for uid, vec in ue._vectors.get(field, {}).items():
            v = np.asarray(vec, dtype=np.float32)
            n = np.linalg.norm(v)
            if n > 0:
                out[str(uid)] = v / n
    return out


def _track_id_from_scored_item(item) -> str | None:
    if not isinstance(item, (list, tuple)) or not item:
        return None
    return str(item[0])


def _feature_drop_ids(trace: dict) -> set[str]:
    drop: set[str] = set()
    retrieval = trace.get("retrieval") or {}
    branches = trace.get("branches") or {}
    resolver = trace.get("resolver") or {}
    for source in (retrieval, branches):
        drop.update(str(track_id) for track_id in source.get("hard_drop") or [])
    for key in ("played_track_ids", "rejected_track_ids"):
        drop.update(str(track_id) for track_id in resolver.get(key) or [])
    return drop


def _filter_feature_branches(branches: dict, drop: set[str]) -> dict:
    if not drop:
        return branches

    out = dict(branches)
    pools = []
    for pool in branches.get("pools") or []:
        if not isinstance(pool, dict):
            pools.append(pool)
            continue
        kept_hits = [
            hit for hit in (pool.get("hits") or [])
            if _track_id_from_scored_item(hit) not in drop
        ]
        pools.append({**pool, "hits": kept_hits})
    out["pools"] = pools
    out["fused"] = [
        item for item in (branches.get("fused") or [])
        if _track_id_from_scored_item(item) not in drop
    ]
    final = branches.get("final")
    if isinstance(final, dict):
        out["final"] = {
            **final,
            "track_ids": [
                str(track_id)
                for track_id in (final.get("track_ids") or [])
                if str(track_id) not in drop
            ],
        }
    return out


def feature_trace_view(trace: dict) -> dict:
    """Return the feature-builder view for legacy and state-ranker v10 traces."""
    if not isinstance(trace, dict):
        return {"branches": {"pools": [], "branch_queries": {}, "fused": []}, "state": {}}
    branches = trace.get("branches")
    if isinstance(branches, dict) and branches.get("pools") is not None:
        drop = _feature_drop_ids(trace)
        if not drop:
            return trace
        out = dict(trace)
        out["branches"] = _filter_feature_branches(branches, drop)
        return out

    retrieval = trace.get("retrieval") or {}
    ranking = trace.get("ranking") or {}
    stages = ranking.get("stages") or []
    candidate_stage = next(
        (s for s in stages if isinstance(s, dict) and s.get("name") == "candidate_fusion"),
        stages[0] if stages else {},
    )
    fused = candidate_stage.get("scores")
    if fused is None:
        fused = [
            [track_id, 1.0 / rank]
            for rank, track_id in enumerate(candidate_stage.get("track_ids") or [], 1)
        ]

    state = trace.get("state") or trace.get("extracted_state") or {}
    compiled_state = trace.get("compiled_state") or {}
    out = dict(trace)
    out["branches"] = _filter_feature_branches({
        "pools": retrieval.get("branches") or [],
        "branch_queries": retrieval.get("branch_queries") or {},
        "fused": fused,
    }, _feature_drop_ids(trace))
    out["state"] = state
    out["routing_tags"] = (
        trace.get("routing_tags")
        or state.get("routing_tags")
        or compiled_state.get("routing_tags")
        or {}
    )
    out["intent_mode"] = (
        trace.get("intent_mode")
        or state.get("intent_mode")
        or compiled_state.get("intent_mode")
        or ""
    )
    return out


def grounded_tags(row: dict, resolver: TieredTagResolver) -> tuple[set[str], int, float]:
    keys: set[str] = set()
    n_exact = 0
    max_score = 0.0
    trace = feature_trace_view(row.get("trace") or {})
    sources = list((trace.get("resolver") or {}).get("positive_tags") or [])
    for fact in (trace.get("state") or {}).get("facts") or []:
        if fact.get("type") == "attribute" and fact.get("value"):
            sources.append(str(fact["value"]))
    for phrase in sources:
        r = resolver.resolve(str(phrase))
        for m in r.matches:
            keys.add(m.tag)
            max_score = max(max_score, m.score)
            if m.tier == "exact":
                n_exact += 1
    return keys - {""}, n_exact, max_score


def _safe_log_name(path: Path) -> str:
    digest = hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:8]
    stem = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in path.name)
    return f"{stem or 'features'}-{digest}"


def _resolve_default_out(args: argparse.Namespace) -> None:
    if args.out is not None:
        return
    if args.shard_id is not None and args.num_shards > 1:
        args.out = str(Path(DEFAULT_PARALLEL_OUT) / f"shard_{args.shard_id}.parquet")
    elif args.num_shards > 1 and not args.prefetch_only:
        args.out = DEFAULT_PARALLEL_OUT
    else:
        args.out = LEGACY_DEFAULT_OUT


def _validate_sharding(args: argparse.Namespace) -> None:
    if args.num_shards < 1:
        raise ValueError("--num-shards must be >= 1")
    if args.num_workers < 1:
        raise ValueError("--num-workers must be >= 1")
    args.num_workers = min(args.num_workers, args.num_shards)
    if args.shard_id is not None and not (0 <= args.shard_id < args.num_shards):
        raise ValueError("--shard-id must satisfy 0 <= shard_id < num_shards")


def _worker_command(args: argparse.Namespace, shard_id: int, out_path: Path) -> list[str]:
    cmd = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--trace",
        str(args.trace),
        "--ground-truth",
        str(args.ground_truth),
        "--db-uri",
        str(args.db_uri),
        "--table-name",
        str(args.table_name),
        "--tag-index",
        str(args.tag_index),
        "--pool-k",
        str(args.pool_k),
        "--out",
        str(out_path),
        "--embed-memo",
        str(args.embed_memo),
        "--branch-names",
        str(args.branch_names),
        "--msg-store",
        str(args.msg_store),
        "--num-shards",
        str(args.num_shards),
        "--shard-id",
        str(shard_id),
    ]
    if args.max_turns:
        cmd.extend(["--max-turns", str(args.max_turns)])
    if args.offline:
        cmd.append("--offline")
    return cmd


def _run_command_logged(cmd: list[str], log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as log_file:
        log_file.write("$ " + " ".join(str(part) for part in cmd) + "\n")
        log_file.flush()
        subprocess.run(cmd, stdout=log_file, stderr=subprocess.STDOUT, check=True)


def run_sharded_build(args: argparse.Namespace) -> None:
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    log_dir = PROJECT_ROOT / "logs" / "build_features" / _safe_log_name(out_dir)
    commands: list[tuple[int, list[str], Path]] = []
    skipped = 0
    for shard_id in range(args.num_shards):
        shard_out = out_dir / f"shard_{shard_id}.parquet"
        if shard_out.exists() and shard_out.stat().st_size > 0:
            skipped += 1
            continue
        commands.append((shard_id, _worker_command(args, shard_id, shard_out), shard_out))

    if skipped:
        print(f"skipping {skipped}/{args.num_shards} completed feature shard(s)", flush=True)
    if not commands:
        print(f"all {args.num_shards} feature shards already exist -> {out_dir}", flush=True)
        return

    print(
        f"building features in parallel: {args.num_shards} shards, "
        f"{args.num_workers} workers -> {out_dir}",
        flush=True,
    )
    with ThreadPoolExecutor(max_workers=args.num_workers) as executor:
        futures = {}
        for shard_id, cmd, _ in commands:
            log_path = log_dir / f"shard_{shard_id}.log"
            futures[executor.submit(_run_command_logged, cmd, log_path)] = log_path

        for future in as_completed(futures):
            log_path = futures[future]
            try:
                future.result()
            except subprocess.CalledProcessError:
                print(f"[build_features] shard failed; see log: {log_path}", file=sys.stderr)
                raise
    print(f"done: feature shards -> {out_dir}", flush=True)


def main():
    _load_dotenv()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--trace", required=True)
    ap.add_argument("--ground-truth", default="exp/ground_truth/devset.json")
    ap.add_argument("--db-uri", required=True)
    ap.add_argument("--table-name", default="music_track_catalog")
    ap.add_argument("--tag-index", required=True)
    ap.add_argument("--pool-k", type=int, default=500,
                    help="Branch-pool truncation before feature computation. "
                         "Must match the serving reranker pool_k (rr2 = 500) "
                         "for train/serve parity of per-pool features.")
    ap.add_argument("--out", default=None)
    ap.add_argument("--embed-memo", default="exp/analysis/rerank/q06_memo.json")
    ap.add_argument("--branch-names", default="exp/analysis/rerank/branch_names.json",
                    help="Canonical branch list (pre-pass over the full trace). "
                         "Fixes the per-shard schema-drift bug.")
    ap.add_argument("--msg-store", default="exp/analysis/rerank/raw_msg_store",
                    help="NpzEmbedStore dir with raw message/context embeddings.")
    ap.add_argument("--max-turns", type=int, default=0)
    ap.add_argument("--prefetch-only", action="store_true",
                    help="Pass 1: collect every unique query/listener_goal string "
                         "from the trace, embed in large batches, save memo, exit.")
    ap.add_argument("--offline", action="store_true",
                    help="Cache-only mode: never call the embedding API; use memo only. "
                         "By default, missing feature embeddings are filled and cached.")
    ap.add_argument("--num-shards", "--num_shards", dest="num_shards", type=int,
                    default=DEFAULT_FEATURE_SHARDS,
                    help="Number of feature shards to build. Defaults to 12 for "
                         "checkpointed local parallelism. Use 1 for legacy inline output.")
    ap.add_argument("--num-workers", "--num_workers", dest="num_workers", type=int,
                    default=DEFAULT_FEATURE_WORKERS,
                    help="Parallel feature worker processes for top-level sharded builds.")
    ap.add_argument("--shard-id", "--shard_id", dest="shard_id", type=int, default=None,
                    help="Internal worker mode: build only this shard id.")
    args = ap.parse_args()
    _resolve_default_out(args)
    _validate_sharding(args)

    if not args.prefetch_only and args.shard_id is None and args.num_shards > 1:
        run_sharded_build(args)
        return

    if args.prefetch_only:
        memo = EmbedMemo(Path(args.embed_memo))
        sessions = load_sessions()
        texts: set[str] = set()
        for s in sessions.values():
            if s.get("listener_goal"):
                texts.add(s["listener_goal"])
        with open(args.trace) as f:
            for line in f:
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                trace = feature_trace_view(row.get("trace") or {})
                for q in (trace["branches"].get("branch_queries") or {}).values():
                    if isinstance(q, dict) and q.get("kind") == "dense" and q.get("query_text"):
                        texts.add(str(q["query_text"]))
        ordered = sorted(texts)
        print(f"prefetching {len(ordered)} unique strings ...", flush=True)
        for start in range(0, len(ordered), 2048):
            memo.get_many(ordered[start:start + 2048])
            memo.flush()
            print(f"  {min(start + 2048, len(ordered))}/{len(ordered)}", flush=True)
        memo.flush()
        print("prefetch done", flush=True)
        return

    print("loading catalog (scalars + 6 vector fields) ...", flush=True)
    cat = Catalog(args.db_uri, args.table_name)
    print(f"  {len(cat.meta)} tracks; vectors: {sorted(cat.vec)}; duration={cat.has_duration}", flush=True)
    sessions = load_sessions()
    user_cf = load_user_cf()
    print(f"  {len(sessions)} sessions, {len(user_cf)} user vectors", flush=True)

    tag_index = TagEmbeddingIndex.load(args.tag_index)
    tag_vec = {t: tag_index.matrix[i] for i, t in enumerate(tag_index.tags)}
    vocab = frozenset(tag_index.tags)
    resolver = TieredTagResolver(catalog_tag_keys=vocab, substring_vocab=vocab)
    memo = EmbedMemo(Path(args.embed_memo))

    gt_map = {(r["session_id"], int(r["turn_number"])): r["ground_truth_track_id"]
              for r in json.load(open(args.ground_truth))}

    branch_names = json.load(open(args.branch_names))
    msg_store = NpzEmbedStore(args.msg_store)

    # Single source of truth: build the training parquet through the SAME
    # compute_turn_features the online reranker calls at serving time
    # (mcrs/qu_modules/lgbm_reranker.py). Routing both the trainer and the
    # server through one function makes train/serve feature parity
    # structural — there is no parallel offline schema that can drift.
    # Imported lazily because features_v9 imports Catalog/EmbedMemo/... back
    # from this module, so a module-level import would be circular.
    from features_v9 import TurnContext, compute_turn_features
    ctx = TurnContext(
        cat, sessions, user_cf, resolver, tag_vec, memo, msg_store,
        branch_names=branch_names, pool_k=args.pool_k, offline=args.offline,
    )

    writer: pq.ParquetWriter | None = None
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    buffer: list[dict] = []
    n_turns = n_playable = 0

    def flush_buffer():
        nonlocal writer, buffer
        if not buffer:
            return
        table = pa.Table.from_pylist(buffer)
        nonlocal_writer = writer
        if nonlocal_writer is None:
            writer = pq.ParquetWriter(str(out_path), table.schema)
        writer.write_table(table)
        buffer = []

    with open(args.trace) as f:
        for line_no, line in enumerate(f):
            if args.shard_id is not None and line_no % args.num_shards != args.shard_id:
                continue
            if args.max_turns and n_turns >= args.max_turns:
                break
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            sid, tn = str(row["session_id"]), int(row["turn_number"])
            gt = gt_map.get((sid, tn))
            if gt is None:
                continue
            n_turns += 1
            rows_out, playable = compute_turn_features(row, ctx, gt=gt)
            if not playable:
                continue  # no positive in the pool — useless for lambdarank
            n_playable += 1
            buffer.extend(rows_out)
            if len(buffer) >= 200_000:
                flush_buffer()
            if line_no % 500 == 0:
                print(f"  line {line_no}: turns={n_turns} playable={n_playable} buffered={len(buffer)}", flush=True)

    flush_buffer()
    if writer:
        writer.close()
    memo.flush()
    msg_store.flush()
    print(f"done: turns={n_turns} playable={n_playable} -> {out_path}", flush=True)


if __name__ == "__main__":
    main()
