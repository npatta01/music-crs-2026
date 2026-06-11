"""Raw-only LTR features from conversations alone — no retrieval, no LLM state.

Two modes:
  --mode train   HF `train` split; candidates per turn = GT + sampled
                 negatives built to mimic retrieval pools (cf-neighbors of
                 last played, same-session-artist tracks, era/popularity-
                 matched, random).
  --mode devset  HF `test` split; candidates = the REAL union pools read from
                 the v2 feature parquet (session_id/turn_number/track_id) so
                 stage-1 transfer can be evaluated on true candidate
                 distributions and stage-2 stacking joins 1:1.

Conversation features are proxies that need no extractor:
  - raw user-message embedding (current + last-3-context) vs candidate
    metadata/attributes/lyrics vectors (Qwen3-0.6B, disk-memoized)
  - tag resolver run directly on raw message text -> tag overlap/IDF/emb-cos
  - lexical: artist/track name mentioned verbatim, IDF token overlap,
    negation-window rejected-artist, wants-new/different cue, year/decade
    regex constraint
Shardable via --num-shards/--shard-id (session-contiguous).
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_features import Catalog, NpzEmbedStore, _norm_rows  # noqa: E402


NEGATION_RE = re.compile(
    r"\b(no|not|don'?t|other than|different|enough|besides|except|instead of|tired of|good on)\b",
    re.I)
WANTS_NEW_RE = re.compile(
    r"\b(different|new|other|else|someone else|another artist|fresh|haven'?t heard)\b", re.I)
YEAR_RE = re.compile(r"\b(19[5-9]\d|20[0-2]\d)s?\b")
DECADE_RE = re.compile(r"\b([5-9]0|[12]0)s\b")


def parse_year_constraint(text: str) -> tuple[int, int] | None:
    years = [int(y) for y in YEAR_RE.findall(text)]
    spans = []
    for y in years:
        if str(y) + "s" in text or f"{y}s" in text:
            spans.append((y, y + 9))
        else:
            spans.append((y - 1, y + 1))
    for d in DECADE_RE.findall(text):
        dd = int(d)
        base = 1900 + dd if dd >= 50 else 2000 + dd
        spans.append((base, base + 9))
    if not spans:
        return None
    return (min(s for s, _ in spans), max(e for _, e in spans))


def load_split(split: str):
    from datasets import load_dataset

    ds = load_dataset("talkpl-ai/TalkPlayData-Challenge-Dataset", split=split)
    sessions = []
    for row in ds:
        sid = str(row["session_id"])
        played_by, user_by = defaultdict(list), {}
        for m in row["conversations"]:
            tn = int(m["turn_number"])
            if m["role"] == "music":
                played_by[tn].append(str(m["content"]))
            elif m["role"] == "user":
                user_by[tn] = str(m["content"])
        p = row.get("user_profile") or {}
        g = row.get("conversation_goal") or {}
        sessions.append({
            "session_id": sid, "user_id": str(row["user_id"]),
            "played_by_turn": dict(played_by), "user_text_by_turn": user_by,
            "session_date": str(row.get("session_date") or ""),
            "age": p.get("age"), "age_group": str(p.get("age_group") or ""),
            "gender": str(p.get("gender") or ""),
            "culture": str(p.get("preferred_musical_culture") or ""),
            "goal_category": str(g.get("category") or ""),
            "goal_specificity": str(g.get("specificity") or ""),
            "listener_goal": str(g.get("listener_goal") or ""),
        })
    return sessions


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


class NegativeSampler:
    """Pool-mimicking negatives: cf-neighbors / same-artist / era-pop / random."""

    def __init__(self, cat: Catalog, seed: int):
        self.cat = cat
        self.rng = np.random.default_rng(seed)
        self.all_ids = np.array(sorted(cat.meta.keys()))
        self.cf = cat.vec["cf_bpr"]
        self.cf_ids = np.array(sorted(cat.vec_idx["cf_bpr"], key=cat.vec_idx["cf_bpr"].get))
        pop = np.array([cat.meta[t]["pop"] for t in self.all_ids])
        self.pop_order = self.all_ids[np.argsort(-pop)]
        self.by_year: dict[int, list[str]] = defaultdict(list)
        for t in self.all_ids:
            y = cat.meta[t]["year"]
            if y:
                self.by_year[y].append(t)

    def cf_neighbors(self, track_id: str, k: int) -> list[str]:
        i = self.cat.vec_idx["cf_bpr"].get(track_id)
        if i is None:
            return []
        scores = self.cf @ self.cf[i]
        top = np.argpartition(-scores, min(k + 1, len(scores) - 1))[: k + 1]
        return [t for t in self.cf_ids[top] if t != track_id][:k]

    def sample(self, gt: str, played: list[str], n_cf=100, n_artist=50,
               n_era=30, n_rand=20) -> list[str]:
        out: dict[str, None] = {}
        last = played[-1] if played else None
        if last:
            for t in self.cf_neighbors(last, n_cf):
                out.setdefault(t)
        artists = {a for p in played for a in self.cat.meta.get(p, {}).get("artists", ())}
        pool = []
        for a in artists:
            pool.extend(self._artist_tracks(a))
        if pool:
            for j in self.rng.permutation(len(pool))[:n_artist]:
                out.setdefault(pool[j])
        gt_year = self.cat.meta.get(gt, {}).get("year")
        anchor_year = gt_year or (self.cat.meta.get(last, {}).get("year") if last else None)
        if anchor_year:
            era = []
            for y in range(anchor_year - 3, anchor_year + 4):
                era.extend(self.by_year.get(y, []))
            if era:
                idx = self.rng.choice(len(era), size=min(n_era, len(era)), replace=False)
                for j in idx:
                    out.setdefault(era[j])
        # top up with populars + randoms
        for t in self.pop_order[:200]:
            if len(out) >= n_cf + n_artist + n_era:
                break
            out.setdefault(t)
        idx = self.rng.choice(len(self.all_ids), size=n_rand * 2, replace=False)
        for j in idx:
            out.setdefault(self.all_ids[j])
        out.pop(gt, None)
        for p in played:
            out.pop(p, None)
        return list(out)[: n_cf + n_artist + n_era + n_rand]

    def _artist_tracks(self, artist_id: str) -> list[str]:
        if not hasattr(self, "_artist_index"):
            self._artist_index: dict[str, list[str]] = defaultdict(list)
            for t, m in self.cat.meta.items():
                for a in m["artists"]:
                    self._artist_index[a].append(t)
        return self._artist_index.get(artist_id, [])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mode", choices=["train", "devset"], required=True)
    ap.add_argument("--db-uri", required=True)
    ap.add_argument("--tag-index", required=True)
    ap.add_argument("--devset-pools", default="exp/analysis/rerank/features_v2",
                    help="v2 parquet dir (devset mode: candidate triples source)")
    ap.add_argument("--ground-truth", default="exp/ground_truth/devset.json")
    ap.add_argument("--out", required=True)
    ap.add_argument("--embed-memo", default="exp/analysis/rerank/raw_msg_store",
                    help="Directory for the chunked npz embedding store.")
    ap.add_argument("--prefetch-only", action="store_true")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--num-shards", type=int, default=1)
    ap.add_argument("--shard-id", type=int, default=0)
    ap.add_argument("--max-sessions", type=int, default=0)
    ap.add_argument("--seed", type=int, default=13)
    args = ap.parse_args()

    split = "train" if args.mode == "train" else "test"
    sessions = load_split(split)
    sessions.sort(key=lambda s: s["session_id"])
    if args.num_shards > 1:
        sessions = [s for i, s in enumerate(sessions) if i % args.num_shards == args.shard_id]
    if args.max_sessions:
        sessions = sessions[: args.max_sessions]
    print(f"mode={args.mode} sessions={len(sessions)}", flush=True)

    memo = NpzEmbedStore(args.embed_memo)
    if args.prefetch_only:
        texts: set[str] = set()
        for s in sessions:
            for tn, txt in s["user_text_by_turn"].items():
                texts.add(txt)
                ctx = " ".join(s["user_text_by_turn"].get(k, "") for k in (tn - 2, tn - 1, tn))
                texts.add(ctx.strip())
            if s["listener_goal"]:
                texts.add(s["listener_goal"])
        ordered = sorted(t for t in texts if t)
        print(f"prefetching {len(ordered)} strings ...", flush=True)
        for start in range(0, len(ordered), 2048):
            memo.get_many(ordered[start:start + 2048])
            memo.flush()
            print(f"  {min(start+2048, len(ordered))}/{len(ordered)}", flush=True)
        memo.flush()
        return

    print("loading catalog ...", flush=True)
    cat = Catalog(args.db_uri, "music_track_catalog")
    user_cf = load_user_cf()
    tag_index = TagEmbeddingIndex.load(args.tag_index)
    tag_vec = {t: tag_index.matrix[i] for i, t in enumerate(tag_index.tags)}
    vocab = frozenset(tag_index.tags)
    resolver = TieredTagResolver(catalog_tag_keys=vocab, substring_vocab=vocab)
    sampler = NegativeSampler(cat, args.seed + args.shard_id) if args.mode == "train" else None

    # token IDF over catalog names+tags for the lexical-overlap feature
    tok_df: Counter = Counter()
    name_tokens_all: dict[str, frozenset] = {}
    for t, m in cat.meta.items():
        toks = m["name_tokens"] | m["tag_keys"]
        name_tokens_all[t] = toks
        tok_df.update(toks)
    n_docs = len(cat.meta)
    tok_idf = {t: math.log((n_docs + 1) / (c + 1)) for t, c in tok_df.items()}

    # candidate triples for devset mode
    devset_cands: dict[tuple[str, int], list[str]] = {}
    gt_map: dict[tuple[str, int], str] = {}
    if args.mode == "devset":
        import pyarrow.dataset as pds
        tbl = pds.dataset(args.devset_pools).to_table(
            columns=["session_id", "turn_number", "track_id", "label"]).to_pydict()
        for sid, tn, tid, lab in zip(tbl["session_id"], tbl["turn_number"],
                                     tbl["track_id"], tbl["label"]):
            devset_cands.setdefault((str(sid), int(tn)), []).append(str(tid))
            if lab == 1:
                gt_map[(str(sid), int(tn))] = str(tid)

    writer = None
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    buffer: list[dict] = []
    n_turns = 0

    def flush():
        nonlocal writer, buffer
        if not buffer:
            return
        table = pa.Table.from_pylist(buffer)
        if writer is None:
            writer = pq.ParquetWriter(str(out_path), table.schema)
        writer.write_table(table)
        buffer = []

    track_tag_vec_cache: dict[str, np.ndarray | None] = {}

    def track_tag_vec(tid):
        if tid in track_tag_vec_cache:
            return track_tag_vec_cache[tid]
        ks = [k for k in cat.meta.get(tid, {}).get("tag_keys", ()) if k in tag_vec]
        v = _norm_rows(np.vstack([tag_vec[k] for k in ks]).mean(axis=0, keepdims=True))[0] if ks else None
        track_tag_vec_cache[tid] = v
        return v

    for s_i, sess in enumerate(sessions):
        sid = sess["session_id"]
        uvec = user_cf.get(sess["user_id"])
        session_year = None
        try:
            session_year = int(sess["session_date"][:4])
        except Exception:
            pass
        lg_vec = memo.get_many([sess["listener_goal"]], offline=args.offline).get(sess["listener_goal"]) \
            if sess["listener_goal"] else None

        for tn in sorted(sess["played_by_turn"]):
            gts = sess["played_by_turn"][tn]
            gt = gts[0]
            if args.mode == "devset":
                cands = devset_cands.get((sid, tn))
                if not cands:
                    continue
                gt = gt_map.get((sid, tn), gt)
            played = [t for k in sorted(sess["played_by_turn"]) if k < tn
                      for t in sess["played_by_turn"][k]]
            if args.mode == "train":
                if gt not in cat.meta:
                    continue
                cands = sampler.sample(gt, played) + [gt]
            n_turns += 1

            msg = sess["user_text_by_turn"].get(tn, "")
            ctx = " ".join(sess["user_text_by_turn"].get(k, "") for k in (tn - 2, tn - 1, tn)).strip()
            emb = memo.get_many([t for t in (msg, ctx) if t], offline=args.offline)
            msg_vec, ctx_vec = emb.get(msg), emb.get(ctx)
            msg_norm = catalog_tag_key(msg)
            msg_tokens = frozenset(msg_norm.split()) - {""}
            res = resolver.resolve(msg)
            q_keys = {m.tag for m in res.matches}
            q_tagv = None
            kk = [k for k in q_keys if k in tag_vec]
            if kk:
                q_tagv = _norm_rows(np.vstack([tag_vec[k] for k in kk]).mean(axis=0, keepdims=True))[0]
            wants_new = float(bool(WANTS_NEW_RE.search(msg)))
            yr_con = parse_year_constraint(msg)

            last = played[-1] if played else None
            prev = played[-2] if len(played) > 1 else None

            def sess_vecs(field):
                vs = [cat.v(field, p) for p in played]
                vs = [v for v in vs if v is not None]
                cent = None
                if vs:
                    c = np.mean(vs, axis=0)
                    nn = np.linalg.norm(c)
                    cent = c / nn if nn > 0 else None
                return (cat.v(field, last) if last else None), cent

            cf_lastv, cf_cent = sess_vecs("cf_bpr")
            clap_lastv, clap_cent = sess_vecs("audio_laion_clap")
            _, siglip_cent = sess_vecs("image_siglip2")
            drift = None
            if cf_lastv is not None and prev:
                pv = cat.v("cf_bpr", prev)
                if pv is not None:
                    d = cf_lastv + (cf_lastv - pv)
                    nn = np.linalg.norm(d)
                    drift = d / nn if nn > 0 else None
            played_artists = set().union(*(cat.meta[p]["artists"] for p in played if p in cat.meta)) if played else set()
            played_albums = set().union(*(cat.meta[p]["albums"] for p in played if p in cat.meta)) if played else set()
            last_artists = set(cat.meta.get(last, {}).get("artists", ()))
            last_albums = set(cat.meta.get(last, {}).get("albums", ()))
            artist_counts = Counter(a for p in played for a in cat.meta.get(p, {}).get("artists", ()))
            culture_keys = {catalog_tag_key(w) for w in sess["culture"].split()} - {""}

            for tid in cands:
                m = cat.meta.get(tid)
                if m is None:
                    continue
                year = m["year"]

                def cos(vec, field="cf_bpr"):
                    cv = cat.v(field, tid)
                    return float(cv @ vec) if (vec is not None and cv is not None) else 0.0

                overlap = m["tag_keys"] & q_keys
                same_artist = float(bool(set(m["artists"]) & played_artists))
                toks = name_tokens_all.get(tid, frozenset())
                lex = sum(tok_idf.get(t, 0.0) for t in (toks & msg_tokens))
                ttv = track_tag_vec(tid)
                # artist mention + negation-window rejection proxy
                artist_mention = 0.0
                rejected_artist = 0.0
                for ak in m.get("artist_name_keys", ()):
                    pos = msg_norm.find(ak)
                    if pos >= 0:
                        artist_mention = 1.0
                        window = msg_norm[max(0, pos - 45): pos]
                        if NEGATION_RE.search(window):
                            rejected_artist = 1.0
                        break
                # title verbatim: all title tokens present in message
                title_in_msg = float(bool(m["name_tokens"]) and m["name_tokens"] <= msg_tokens)
                albums = set(m["albums"])
                in_yr = 0.0
                if yr_con and year:
                    in_yr = float(yr_con[0] <= year <= yr_con[1])
                rec = {
                    "session_id": sid, "turn_number": tn, "track_id": tid,
                    "label": int(tid == gt),
                    "pop_pct": cat.pop_pct.get(tid, 0.0),
                    "era_pop_pct": cat.era_pop_pct.get(tid, cat.pop_pct.get(tid, 0.0)),
                    "within_artist_pop": cat.within_artist_pop.get(tid, 0.0),
                    "release_year": float(year or cat.median_year),
                    "has_year": float(year is not None),
                    "tag_count": m["n_tags"], "n_artists": len(m["artists"]),
                    "artist_track_count": max((cat.artist_track_count.get(a, 0) for a in m["artists"]), default=0),
                    "duration_ms": m["duration"] if not math.isnan(m["duration"]) else cat.median_duration,
                    "cf_last": cos(cf_lastv), "cf_centroid": cos(cf_cent), "cf_drift": cos(drift),
                    "clap_last": cos(clap_lastv, "audio_laion_clap"),
                    "clap_centroid": cos(clap_cent, "audio_laion_clap"),
                    "siglip_centroid": cos(siglip_cent, "image_siglip2"),
                    "same_artist_session": same_artist,
                    "same_artist_last": float(bool(set(m["artists"]) & last_artists)),
                    "same_album_last": float(bool(albums & last_albums)),
                    "same_album_any": float(bool(albums & played_albums)),
                    "artist_played_count": max((artist_counts.get(a, 0) for a in m["artists"]), default=0),
                    "turn_number_f": tn, "n_played": len(played),
                    "has_history": float(bool(played)),
                    "user_cf": cos(uvec), "has_user_vec": float(uvec is not None),
                    "culture_match": float(len(m["tag_keys"] & culture_keys)),
                    "age_group": sess["age_group"], "gender": sess["gender"],
                    "goal_category": sess["goal_category"],
                    "goal_specificity": sess["goal_specificity"],
                    "listener_goal_cos": (float(lg_vec @ cat.v("metadata_qwen3_embedding_0_6b", tid))
                                          if lg_vec is not None and cat.v("metadata_qwen3_embedding_0_6b", tid) is not None else 0.0),
                    "session_minus_release_year": float((session_year - year) if (session_year and year) else 0.0),
                    # conversation proxies
                    "msg_meta_cos": (float(msg_vec @ cat.v("metadata_qwen3_embedding_0_6b", tid))
                                     if msg_vec is not None and cat.v("metadata_qwen3_embedding_0_6b", tid) is not None else 0.0),
                    "msg_attr_cos": (float(msg_vec @ cat.v("attributes_qwen3_embedding_0_6b", tid))
                                     if msg_vec is not None and cat.v("attributes_qwen3_embedding_0_6b", tid) is not None else 0.0),
                    "msg_lyr_cos": (float(msg_vec @ cat.v("lyrics_qwen3_embedding_0_6b", tid))
                                    if msg_vec is not None and cat.v("lyrics_qwen3_embedding_0_6b", tid) is not None else 0.0),
                    "ctx_meta_cos": (float(ctx_vec @ cat.v("metadata_qwen3_embedding_0_6b", tid))
                                     if ctx_vec is not None and cat.v("metadata_qwen3_embedding_0_6b", tid) is not None else 0.0),
                    "tag_overlap": float(len(overlap)),
                    "tag_overlap_idf": float(sum(cat.tag_idf.get(t, 0.0) for t in overlap)),
                    "tag_emb_cos": (float(q_tagv @ ttv) if q_tagv is not None and ttv is not None else 0.0),
                    "lex_overlap_idf": lex,
                    "title_in_msg": title_in_msg,
                    "artist_mention": artist_mention,
                    "rejected_artist_proxy": rejected_artist,
                    "wants_new_proxy": wants_new,
                    "x_same_artist_wants_new": same_artist * wants_new,
                    "year_in_msg_constraint": in_yr,
                    "has_msg_year_constraint": float(yr_con is not None),
                }
                age = sess.get("age")
                rec["age_era_affinity"] = 0.0
                if age and year and session_year:
                    birth = session_year - int(age)
                    rec["age_era_affinity"] = float(birth + 12 <= year <= birth + 25)
                buffer.append(rec)

        if len(buffer) >= 200_000:
            flush()
        if s_i % 200 == 0:
            print(f"  session {s_i}/{len(sessions)} turns={n_turns}", flush=True)

    flush()
    if writer:
        writer.close()
    memo.flush()
    print(f"done: turns={n_turns} -> {out_path}", flush=True)


if __name__ == "__main__":
    main()
