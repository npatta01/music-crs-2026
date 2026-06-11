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
      --out exp/analysis/rerank/features.parquet
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from mcrs.qu_modules.tag_resolver import (  # noqa: E402
    TagEmbeddingIndex,
    TieredTagResolver,
    catalog_tag_key,
)

VECTOR_FIELDS = {
    "cf_bpr": "cf",
    "audio_laion_clap": "clap",
    "image_siglip2": "siglip",
    "metadata_qwen3_embedding_0_6b": "q06_meta",
    "attributes_qwen3_embedding_0_6b": "q06_attr",
    "lyrics_qwen3_embedding_0_6b": "q06_lyr",
}

PCT_FEATURES = [
    "pop_pct", "era_pop_pct", "cf_last", "cf_centroid", "user_cf",
    "tag_overlap_idf", "q06_metadata_cos", "rrf_score",
]


def _norm_rows(mat: np.ndarray) -> np.ndarray:
    return mat / np.maximum(np.linalg.norm(mat, axis=1, keepdims=True), 1e-9)


class Catalog:
    def __init__(self, db_uri: str, table_name: str):
        import lancedb

        db = lancedb.connect(db_uri)
        self.ds = db.open_table(table_name).to_lance()
        scalars = ["track_id", "popularity", "release_date", "artist_id",
                   "album_id", "tag_list", "duration"]
        names = set(self.ds.schema.names)
        cols = [c for c in scalars if c in names]
        tbl = self.ds.to_table(columns=cols).to_pydict()
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
            self.meta[tid] = {
                "artists": artists, "albums": albums, "year": year,
                "pop": float(tbl["popularity"][i] or 0.0),
                "tag_keys": tag_keys, "n_tags": len(tags),
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

        self.vec: dict[str, np.ndarray] = {}
        self.vec_idx: dict[str, dict[str, int]] = {}
        for field in VECTOR_FIELDS:
            if field not in names:
                continue
            t = self.ds.to_table(columns=["track_id", field]).to_pydict()
            ids, rows = [], []
            for tid, v in zip(t["track_id"], t[field]):
                if v is not None and len(v):
                    ids.append(str(tid))
                    rows.append(np.asarray(v, dtype=np.float32))
            self.vec[field] = _norm_rows(np.vstack(rows))
            self.vec_idx[field] = {t_: i for i, t_ in enumerate(ids)}

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
        if self._dirty:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.memo))
            self._dirty = 0


def load_sessions():
    from datasets import load_dataset

    ds = load_dataset("talkpl-ai/TalkPlayData-Challenge-Dataset", split="test")
    out = {}
    for row in ds:
        sid = str(row["session_id"])
        played, _user_text = defaultdict(list), {}
        for msg in row["conversations"]:
            if msg["role"] == "music":
                played[int(msg["turn_number"])].append(str(msg["content"]))
        p = row.get("user_profile") or {}
        g = row.get("conversation_goal") or {}
        out[sid] = {
            "played_by_turn": dict(played),
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


def grounded_tags(row: dict, resolver: TieredTagResolver) -> tuple[set[str], int, float]:
    keys: set[str] = set()
    n_exact = 0
    max_score = 0.0
    sources = list((row["trace"].get("resolver") or {}).get("positive_tags") or [])
    for fact in (row["trace"].get("state") or {}).get("facts") or []:
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


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--trace", required=True)
    ap.add_argument("--ground-truth", default="exp/ground_truth/devset.json")
    ap.add_argument("--db-uri", required=True)
    ap.add_argument("--table-name", default="music_track_catalog")
    ap.add_argument("--tag-index", required=True)
    ap.add_argument("--pool-k", type=int, default=200)
    ap.add_argument("--out", default="exp/analysis/rerank/features.parquet")
    ap.add_argument("--embed-memo", default="exp/analysis/rerank/q06_memo.json")
    ap.add_argument("--max-turns", type=int, default=0)
    ap.add_argument("--prefetch-only", action="store_true",
                    help="Pass 1: collect every unique query/listener_goal string "
                         "from the trace, embed in large batches, save memo, exit.")
    ap.add_argument("--offline", action="store_true",
                    help="Pass 2: never call the embedding API; use memo only.")
    args = ap.parse_args()

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
                for q in (row["trace"]["branches"].get("branch_queries") or {}).values():
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

    track_tag_vec_cache: dict[str, np.ndarray | None] = {}

    def track_tag_vec(tid: str) -> np.ndarray | None:
        if tid in track_tag_vec_cache:
            return track_tag_vec_cache[tid]
        keys = [k for k in cat.meta.get(tid, {}).get("tag_keys", ()) if k in tag_vec]
        v = None
        if keys:
            v = _norm_rows(np.vstack([tag_vec[k] for k in keys]).mean(axis=0, keepdims=True))[0]
        track_tag_vec_cache[tid] = v
        return v

    writer: pq.ParquetWriter | None = None
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    buffer: list[dict] = []
    branch_names: list[str] = []
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
            br = row["trace"]["branches"]
            pools = br["pools"]
            if not branch_names:
                branch_names = [p["name"] for p in pools]

            cand_rank: dict[str, dict[str, tuple[int, float]]] = defaultdict(dict)
            for p in pools:
                for rank, (tid_, score) in enumerate(p["hits"][: args.pool_k], 1):
                    cand_rank[str(tid_)][p["name"]] = (rank, float(score))
            if gt not in cand_rank:
                continue  # non-playable at this pool depth
            n_playable += 1

            fused_pos = {str(t): (r, float(s)) for r, (t, s) in enumerate(br["fused"], 1)}
            sess = sessions.get(sid, {})
            played = [t for k in sorted(sess.get("played_by_turn", {})) if k < tn
                      for t in sess["played_by_turn"][k]]
            last = played[-1] if played else None
            prev = played[-2] if len(played) > 1 else None

            def sess_vecs(field):
                vs = [cat.v(field, p) for p in played]
                vs = [v for v in vs if v is not None]
                cent = None
                if vs:
                    cent = np.mean(vs, axis=0)
                    n = np.linalg.norm(cent)
                    cent = cent / n if n > 0 else None
                lastv = cat.v(field, last) if last else None
                return lastv, cent

            cf_lastv, cf_cent = sess_vecs("cf_bpr")
            clap_lastv, clap_cent = sess_vecs("audio_laion_clap")
            _, siglip_cent = sess_vecs("image_siglip2")
            drift = None
            if cf_lastv is not None and prev:
                pv = cat.v("cf_bpr", prev)
                if pv is not None:
                    d = cf_lastv + (cf_lastv - pv)
                    n = np.linalg.norm(d)
                    drift = d / n if n > 0 else None
            uvec = user_cf.get(str(row.get("user_id") or ""))

            played_artists = set().union(*(cat.meta[p]["artists"] for p in played if p in cat.meta)) if played else set()
            played_albums = set().union(*(cat.meta[p]["albums"] for p in played if p in cat.meta)) if played else set()
            last_albums = set(cat.meta.get(last, {}).get("albums", ()))
            last_artists = set(cat.meta.get(last, {}).get("artists", ()))
            artist_play_counts = Counter(a for p in played for a in cat.meta.get(p, {}).get("artists", ()))
            album_played_counts = Counter(al for p in played for al in cat.meta.get(p, {}).get("albums", ()))

            state = row["trace"].get("state") or {}
            q_keys, n_exact_tier, max_match = grounded_tags(row, resolver)
            q_tagv = None
            kk = [k for k in q_keys if k in tag_vec]
            if kk:
                q_tagv = _norm_rows(np.vstack([tag_vec[k] for k in kk]).mean(axis=0, keepdims=True))[0]
            tc = state.get("temporal_constraint") or {}
            routing = row["trace"].get("routing_tags") or {}
            tam = str(state.get("target_artist_mode") or "")
            wants_new = float("new" in tam or "different" in tam)

            queries = row["trace"]["branches"].get("branch_queries") or {}
            q_texts = {}
            for bname, q in queries.items():
                if isinstance(q, dict) and q.get("kind") == "dense" and q.get("query_text"):
                    q_texts[bname] = str(q["query_text"])
            lg_text = sess.get("listener_goal", "")
            emb = memo.get_many(list(q_texts.values()) + ([lg_text] if lg_text else []),
                                offline=args.offline)
            lg_vec = emb.get(lg_text)

            def qcos(branch_substr, cand_field, tid_):
                for bname, qtext in q_texts.items():
                    if branch_substr in bname:
                        qv = emb.get(qtext)
                        cv = cat.v(cand_field, tid_)
                        if qv is not None and cv is not None and len(qv) == len(cv):
                            return float(qv @ cv)
                return np.nan

            session_year = None
            try:
                session_year = int(sess.get("session_date", "")[:4])
            except Exception:
                pass

            rows_out = []
            for tid_, branch_hits in cand_rank.items():
                m = cat.meta.get(tid_)
                if m is None:
                    continue
                year = m["year"]

                def cos(vec, field="cf_bpr"):
                    cv = cat.v(field, tid_)
                    return float(cv @ vec) if (vec is not None and cv is not None) else np.nan

                in_constraint = np.nan
                if tc and (tc.get("start_year") or tc.get("end_year")) and year:
                    s, e = tc.get("start_year"), tc.get("end_year")
                    in_constraint = float((s is None or year >= s) and (e is None or year <= e))
                overlap = m["tag_keys"] & q_keys
                same_artist = float(bool(set(m["artists"]) & played_artists))
                ttv = track_tag_vec(tid_)
                fr = fused_pos.get(tid_, (np.nan, np.nan))
                albums = set(m["albums"])
                rec = {
                    "session_id": sid, "turn_number": tn, "track_id": tid_,
                    "label": int(tid_ == gt),
                    # pool
                    "n_branches": len(branch_hits),
                    "rrf_rank": fr[0], "rrf_score": fr[1],
                    "best_branch_rank": min(r for r, _ in branch_hits.values()),
                    # catalog
                    "pop_pct": cat.pop_pct.get(tid_, 0.0),
                    "era_pop_pct": cat.era_pop_pct.get(tid_, np.nan),
                    "release_year": year or np.nan,
                    "tag_count": m["n_tags"],
                    "n_artists": len(m["artists"]),
                    "artist_track_count": max((cat.artist_track_count.get(a, 0) for a in m["artists"]), default=0),
                    "duration_ms": m["duration"],
                    # session
                    "cf_last": cos(cf_lastv), "cf_centroid": cos(cf_cent),
                    "cf_drift": cos(drift),
                    "clap_last": cos(clap_lastv, "audio_laion_clap"),
                    "clap_centroid": cos(clap_cent, "audio_laion_clap"),
                    "siglip_centroid": cos(siglip_cent, "image_siglip2"),
                    "same_artist_session": same_artist,
                    "same_artist_last": float(bool(set(m["artists"]) & last_artists)),
                    "same_album_last": float(bool(albums & last_albums)),
                    "same_album_any": float(bool(albums & played_albums)),
                    "album_played_count": max((album_played_counts.get(a, 0) for a in albums), default=0),
                    "artist_played_count": max((artist_play_counts.get(a, 0) for a in m["artists"]), default=0),
                    "artist_share": (max((artist_play_counts.get(a, 0) for a in m["artists"]), default=0) / max(len(played), 1)),
                    "turn_number_f": tn, "n_played": len(played),
                    # user
                    "user_cf": cos(uvec),
                    "age_era_affinity": np.nan,
                    "culture_match": float(len(m["tag_keys"] & {catalog_tag_key(w) for w in sess.get("culture", "").split()} - {""})),
                    "age_group": sess.get("age_group", ""), "gender": sess.get("gender", ""),
                    # organizer
                    "goal_category": sess.get("goal_category", ""),
                    "goal_specificity": sess.get("goal_specificity", ""),
                    "listener_goal_cos": (float(lg_vec @ cat.v("metadata_qwen3_embedding_0_6b", tid_))
                                          if lg_vec is not None and cat.v("metadata_qwen3_embedding_0_6b", tid_) is not None else np.nan),
                    "session_minus_release_year": (session_year - year) if (session_year and year) else np.nan,
                    # state
                    "tag_overlap": float(len(overlap)),
                    "tag_overlap_idf": float(sum(cat.tag_idf.get(t, 0.0) for t in overlap)),
                    "n_exact_tier": n_exact_tier, "max_tag_match_score": max_match,
                    "tag_emb_cos": (float(q_tagv @ ttv) if q_tagv is not None and ttv is not None else np.nan),
                    "request_type": str((state.get("current_request") or {}).get("request_type") or ""),
                    "intent_mode": str(row["trace"].get("intent_mode") or ""),
                    "target_artist_mode": tam,
                    "routing_lyric": float(bool(routing.get("lyric_search"))),
                    "routing_visual": float(bool(routing.get("image_or_visual_search"))),
                    "routing_exact": float(bool(routing.get("exact_entity_probe"))),
                    "temporal_strength": str(tc.get("strength") or ""),
                    "year_in_constraint": in_constraint,
                    "n_facts": len(state.get("facts") or []),
                    "wants_new_artist": wants_new,
                    # dense fill-in
                    "q06_metadata_cos": qcos("metadata", "metadata_qwen3_embedding_0_6b", tid_),
                    "q06_attributes_cos": qcos("attributes", "attributes_qwen3_embedding_0_6b", tid_),
                    "q06_lyric_cos": qcos("lyric", "lyrics_qwen3_embedding_0_6b", tid_),
                    # crosses
                    "x_same_artist_wants_new": same_artist * wants_new,
                    "x_cflast_turn": (cos(cf_lastv) * tn / 8.0),
                    "x_era_hard": ((0.0 if math.isnan(in_constraint) else in_constraint) * float(tc.get("strength") == "hard")),
                }
                # age-era
                age = sess.get("age")
                if age and year and session_year:
                    birth = session_year - int(age)
                    rec["age_era_affinity"] = float(birth + 12 <= year <= birth + 25)
                # per-branch ranks/scores
                for b in branch_names:
                    r_s = branch_hits.get(b)
                    rec[f"rank__{b}"] = float(r_s[0]) if r_s else np.nan
                    rec[f"score__{b}"] = float(r_s[1]) if r_s else np.nan
                    rec[f"hit__{b}"] = float(bool(r_s))
                rows_out.append(rec)

            # within-pool percentiles
            for feat in PCT_FEATURES:
                vals = np.array([r.get(feat, np.nan) for r in rows_out], dtype=np.float64)
                ok = ~np.isnan(vals)
                if ok.sum() > 1:
                    order = vals[ok].argsort().argsort() / max(ok.sum() - 1, 1)
                    j = 0
                    for i, r in enumerate(rows_out):
                        if ok[i]:
                            r[f"pct_{feat}"] = float(order[j]); j += 1
                        else:
                            r[f"pct_{feat}"] = np.nan
                else:
                    for r in rows_out:
                        r[f"pct_{feat}"] = np.nan

            buffer.extend(rows_out)
            if len(buffer) >= 200_000:
                flush_buffer()
            if line_no % 500 == 0:
                print(f"  line {line_no}: turns={n_turns} playable={n_playable} buffered={len(buffer)}", flush=True)

    flush_buffer()
    if writer:
        writer.close()
    memo.flush()
    print(f"done: turns={n_turns} playable={n_playable} -> {out_path}", flush=True)


if __name__ == "__main__":
    main()
