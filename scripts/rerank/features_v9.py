"""Feature set v9 — shared per-turn feature computation (offline + online).

The single source of truth for reranker features: `TurnContext` bundles the
catalog/session/embedding state; `compute_turn_features(row, ctx, gt)` turns one
trace row into per-candidate feature dicts. The offline builder
(build_features.py --v9) and the online compiler hook both call THIS function —
train/serve drift is structurally impossible (the −70% incident class).

v9 changes vs the v7b feature set (user-locked 2026-06-12):
- REMOVED fusion proxies: n_branches, best_branch_rank, margin_min,
  pct_margin_min (rrf_rank/rrf_score still EMITTED for the eval baseline but
  are excluded from model features by the trainer, as before).
- REMOVED weak q06 cosines: q06_metadata_cos, q06_attributes_cos,
  pct_q06_metadata_cos (the 8B branch scores carry those fields); q06_lyric_cos
  stays (lyrics IS a 0.6B field).
- REMOVED stage1_score (two-tower dropped).
- NaN-missing encoding: per-branch rank/score/margin when the candidate is
  absent from that branch -> NaN (hit__ carries presence); similarity cosines
  with no vector (cold user / no history / no query) -> NaN. No silent 0-fill.
- ADDED (semih cherry-picks): z__score__{branch} (within-pool z over hits),
  ratio__{branch} (score/top, hits only; margin__ already = gap-to-top),
  n_same_artist_in_union, artist_best_rank_in_union,
  same_artist_as_abandoned + tag_overlap_abandoned (pivot-away resemblance from
  CURRENT state's negative feedback/rejections — serving-safe, no cross-turn
  carry).
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict

import numpy as np

from mcrs.qu_modules.tag_resolver import TieredTagResolver, catalog_tag_key

from build_features import (  # noqa: E402  (sibling module)
    NEGATION_RE,
    WANTS_NEW_RE,
    Catalog,
    EmbedMemo,
    NpzEmbedStore,
    feature_trace_view,
    _norm_rows,
    grounded_tags,
)

# within-pool percentile features (NaN-aware: NaN rows get NaN pct)
PCT_FEATURES_V9 = [
    "pop_pct", "era_pop_pct", "cf_last", "cf_centroid", "user_cf",
    "tag_overlap_idf", "msg_meta_cos", "lex_overlap_idf",
]

NAN = float("nan")


class TurnContext:
    """Everything compute_turn_features needs, built once per process."""

    def __init__(self, cat: Catalog, sessions: dict, user_cf: dict,
                 resolver: TieredTagResolver, tag_vec: dict, memo,
                 msg_store, branch_names: list[str], pool_k: int,
                 offline: bool = True):
        self.cat = cat
        self.sessions = sessions
        self.user_cf = user_cf
        self.resolver = resolver
        self.tag_vec = tag_vec
        self.memo = memo
        self.msg_store = msg_store
        self.branch_names = list(branch_names)
        self.pool_k = pool_k
        self.offline = offline

        tok_df: Counter = Counter()
        self.name_tokens_all: dict[str, frozenset] = {}
        for t_, m_ in cat.meta.items():
            toks_ = m_["name_tokens"] | m_["tag_keys"]
            self.name_tokens_all[t_] = toks_
            tok_df.update(toks_)
        self.tok_idf = {t_: math.log((len(cat.meta) + 1) / (c_ + 1))
                        for t_, c_ in tok_df.items()}
        self._track_tag_vec: dict[str, np.ndarray | None] = {}

    def track_tag_vec(self, tid: str):
        if tid in self._track_tag_vec:
            return self._track_tag_vec[tid]
        keys = [k for k in self.cat.meta.get(tid, {}).get("tag_keys", ())
                if k in self.tag_vec]
        v = None
        if keys:
            v = _norm_rows(np.vstack([self.tag_vec[k] for k in keys])
                           .mean(axis=0, keepdims=True))[0]
        self._track_tag_vec[tid] = v
        return v


def is_pivot_turn(intent_mode, target_artist_mode) -> bool:
    """Shared pivot gate — single source of truth for the offline training-row
    filter and the online reranker router (they must never diverge).

    A turn is a pivot when the canonical intent is ``pivot`` OR the requested
    artist mode wants a new/different artist. NOTE (verified 2026-06-18): in the
    current state schema these two arms are collinear (``intent_mode=='pivot'`` and
    ``target_artist_mode=='new_artist'`` coincide, and ``'different'`` never occurs),
    so the union equals ``intent_mode=='pivot'`` today; the union is kept as
    future-proofing for a schema where they diverge. Inputs may be ``None``."""
    if str(intent_mode or "") == "pivot":
        return True
    mode = str(target_artist_mode or "")
    return ("new" in mode) or ("different" in mode)


def _abandoned_sets(state: dict, resolver_block: dict, cat: Catalog):
    """Pivot-away targets from CURRENT state only (serving-safe).

    Returns (abandoned_artist_ids, abandoned_tag_keys). Matching is by catalog
    artist_id (UUID), NOT name-key: the catalog's artist_id/artist_name arrays are
    not reliably pair-aligned (collaboration rows; ~3.3k length-mismatch rows; ~12%
    of UUIDs map to >1 name), so a UUID->name map mis-resolves. Both
    resolver.rejected_artist_ids and cat.meta[*]["artists"] are artist UUIDs, so we
    compare those directly.

    abandoned artist ids:
      - resolver.rejected_artist_ids (explicit artist rejections);
      - artists of negatively-rated feedback tracks (role 'rejected' or
        overall_sentiment < 0);
      - on a pivot (target_artist_mode wants a new/different artist) the artists of
        previously *satisfied* tracks — schema: role 'satisfied' = "met a prior
        request, should not automatically carry forward", the leave-behind role.
        'accepted' ("default for any liked track") is deliberately NOT treated as
        leaving — demoting a still-liked artist on a pivot is too aggressive.
    abandoned tags = resolver.rejected_tags (resolved to catalog tag keys).

    track_feedback schema (mcrs.conversation_state.schema.TrackFeedback):
      {track_id, overall_sentiment: int, role: 'accepted'|'rejected'|'seed'|
       'neutral'|'satisfied'|'contrast'}."""
    mode = str(state.get("target_artist_mode") or "")
    pivot = is_pivot_turn(None, mode)

    artist_ids: set[str] = {str(a) for a in (resolver_block.get("rejected_artist_ids") or [])}
    for fb in (state.get("track_feedback") or []):
        role = str(fb.get("role") or "").lower()
        try:
            sentiment = float(fb.get("overall_sentiment"))
        except (TypeError, ValueError):
            sentiment = 0.0
        negative = role == "rejected" or sentiment < 0
        leaving = pivot and role == "satisfied"
        if negative or leaving:
            m = cat.meta.get(str(fb.get("track_id") or ""))
            if m:
                artist_ids.update(str(a) for a in m["artists"])
    tags: set[str] = set()
    for t in (resolver_block.get("rejected_tags") or []):
        k = catalog_tag_key(str(t))
        if k:
            tags.add(k)
    return artist_ids, tags


def compute_turn_features(row: dict, ctx: TurnContext, gt: str | None = None):
    """One trace row -> (rows_out, playable). rows carry label iff gt given."""
    cat = ctx.cat
    sid, tn = str(row["session_id"]), int(row["turn_number"])
    trace = feature_trace_view(row.get("trace") or {})
    br = trace["branches"]
    pools = br["pools"]

    cand_rank: dict[str, dict[str, tuple[int, float]]] = defaultdict(dict)
    for p in pools:
        for rank, (tid_, score) in enumerate(p["hits"][: ctx.pool_k], 1):
            cand_rank[str(tid_)][p["name"]] = (rank, float(score))
    playable = gt is not None and gt in cand_rank

    fused_pos = {str(t): (r, float(s)) for r, (t, s) in enumerate(br["fused"], 1)}
    sess = ctx.sessions.get(sid, {})
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
    uvec = ctx.user_cf.get(str(row.get("user_id") or ""))

    played_artists = set().union(*(cat.meta[p]["artists"] for p in played if p in cat.meta)) if played else set()
    played_albums = set().union(*(cat.meta[p]["albums"] for p in played if p in cat.meta)) if played else set()
    last_albums = set(cat.meta.get(last, {}).get("albums", ()))
    last_artists = set(cat.meta.get(last, {}).get("artists", ()))
    artist_play_counts = Counter(a for p in played for a in cat.meta.get(p, {}).get("artists", ()))
    album_played_counts = Counter(al for p in played for al in cat.meta.get(p, {}).get("albums", ()))

    state = trace.get("state") or {}
    resolver_block = trace.get("resolver") or {}
    q_keys, n_exact_tier, max_match = grounded_tags({**row, "trace": trace}, ctx.resolver)
    q_tagv = None
    kk = [k for k in q_keys if k in ctx.tag_vec]
    if kk:
        q_tagv = _norm_rows(np.vstack([ctx.tag_vec[k] for k in kk])
                            .mean(axis=0, keepdims=True))[0]
    tc = state.get("temporal_constraint") or {}
    routing = trace.get("routing_tags") or {}
    tam = str(state.get("target_artist_mode") or "")
    wants_new = float("new" in tam or "different" in tam)
    abandoned_artist_ids, abandoned_tag_keys = _abandoned_sets(state, resolver_block, cat)

    queries = br.get("branch_queries") or {}
    q_texts = {}
    for bname, q in queries.items():
        if isinstance(q, dict) and q.get("kind") == "dense" and q.get("query_text"):
            q_texts[bname] = str(q["query_text"])
    lg_text = sess.get("listener_goal", "")
    emb = ctx.memo.get_many(list(q_texts.values()) + ([lg_text] if lg_text else []),
                            offline=ctx.offline)
    lg_vec = emb.get(lg_text)

    def qcos(branch_substr, cand_field, tid_):
        for bname, qtext in q_texts.items():
            if branch_substr in bname:
                qv = emb.get(qtext)
                cv = cat.v(cand_field, tid_)
                if qv is not None and cv is not None and len(qv) == len(cv):
                    return float(qv @ cv)
        return NAN

    session_year = None
    try:
        session_year = int(sess.get("session_date", "")[:4])
    except Exception:
        pass

    branch_top_score = {p["name"]: (float(p["hits"][0][1]) if p["hits"] else NAN)
                        for p in pools}
    has_history = float(bool(played))
    has_user_vec = float(uvec is not None)
    request_tokens = set()
    for qt in q_texts.values():
        request_tokens.update(catalog_tag_key(qt).split())
    request_tokens -= {""}
    has_constraint = float(bool(tc and (tc.get("start_year") or tc.get("end_year"))))
    msg = sess.get("user_text_by_turn", {}).get(tn, "")
    ctx3 = " ".join(sess.get("user_text_by_turn", {}).get(k, "")
                    for k in (tn - 2, tn - 1, tn)).strip()
    memb = ctx.msg_store.get_many([t for t in (msg, ctx3) if t], offline=ctx.offline)
    msg_vec, ctx_vec = memb.get(msg), memb.get(ctx3)
    msg_norm = catalog_tag_key(msg)
    msg_tokens = frozenset(msg_norm.split()) - {""}
    wants_new_rx = float(bool(WANTS_NEW_RE.search(msg)))

    # union-level artist concentration (semih F): per artist-key, count + best
    # within-branch rank across the whole candidate union
    artist_union_count: Counter = Counter()
    artist_union_best: dict[str, float] = {}
    for tid_, bh in cand_rank.items():
        m_ = cat.meta.get(tid_)
        if m_ is None:
            continue
        best_r = min((r for r, _ in bh.values()), default=None)
        for a in m_["artists"]:
            artist_union_count[a] += 1
            if best_r is not None:
                cur = artist_union_best.get(a)
                artist_union_best[a] = float(best_r) if cur is None else min(cur, float(best_r))

    rows_out = []
    for tid_, branch_hits in cand_rank.items():
        m = cat.meta.get(tid_)
        if m is None:
            continue
        year = m["year"]

        def cos(vec, field="cf_bpr"):
            cv = cat.v(field, tid_)
            return float(cv @ vec) if (vec is not None and cv is not None) else NAN

        in_constraint = 0.0
        if has_constraint and year:
            s, e = tc.get("start_year"), tc.get("end_year")
            in_constraint = float((s is None or year >= s) and (e is None or year <= e))
        overlap = m["tag_keys"] & q_keys
        same_artist = float(bool(set(m["artists"]) & played_artists))
        ttv = ctx.track_tag_vec(tid_)
        fr = fused_pos.get(tid_, (1001.0, 0.0))
        albums = set(m["albums"])
        name_tokens = m["name_tokens"]
        title_overlap = (len(name_tokens & request_tokens) / len(name_tokens)) if name_tokens else 0.0
        cf_last_c = cos(cf_lastv)
        cf_centroid_c = cos(cf_cent)
        cf_drift_c = cos(drift)
        clap_last_c = cos(clap_lastv, "audio_laion_clap")
        clap_centroid_c = cos(clap_cent, "audio_laion_clap")
        siglip_centroid_c = cos(siglip_cent, "image_siglip2")
        user_cf_c = cos(uvec)
        listener_goal_c = cos(lg_vec, "metadata_qwen3_embedding_0_6b")
        q06_lyric_c = qcos("lyric", "lyrics_qwen3_embedding_0_6b", tid_)
        msg_meta_c = cos(msg_vec, "metadata_qwen3_embedding_0_6b")
        msg_attr_c = cos(msg_vec, "attributes_qwen3_embedding_0_6b")
        msg_lyr_c = cos(msg_vec, "lyrics_qwen3_embedding_0_6b")
        ctx_meta_c = cos(ctx_vec, "metadata_qwen3_embedding_0_6b")
        rec = {
            "session_id": sid, "turn_number": tn, "track_id": tid_,
            "label": int(tid_ == gt) if gt is not None else 0,
            # eval-only (excluded from model features by the trainer)
            "rrf_rank": fr[0], "rrf_score": fr[1],
            # catalog
            "pop_pct": cat.pop_pct.get(tid_, 0.0),
            "era_pop_pct": cat.era_pop_pct.get(tid_, cat.pop_pct.get(tid_, 0.0)),
            "within_artist_pop": cat.within_artist_pop.get(tid_, 0.0),
            "release_year": float(year or cat.median_year),
            "has_year": float(year is not None),
            "tag_count": m["n_tags"],
            "n_artists": len(m["artists"]),
            "artist_track_count": max((cat.artist_track_count.get(a, 0) for a in m["artists"]), default=0),
            "duration_ms": m["duration"] if not math.isnan(m["duration"]) else cat.median_duration,
            # session (NaN when no history)
            "cf_last": cf_last_c, "cf_centroid": cf_centroid_c,
            "cf_drift": cf_drift_c,
            "clap_last": clap_last_c,
            "clap_centroid": clap_centroid_c,
            "siglip_centroid": siglip_centroid_c,
            "same_artist_session": same_artist,
            "same_artist_last": float(bool(set(m["artists"]) & last_artists)),
            "same_album_last": float(bool(albums & last_albums)),
            "same_album_any": float(bool(albums & played_albums)),
            "album_played_count": max((album_played_counts.get(a, 0) for a in albums), default=0),
            "artist_played_count": max((artist_play_counts.get(a, 0) for a in m["artists"]), default=0),
            "artist_share": (max((artist_play_counts.get(a, 0) for a in m["artists"]), default=0) / max(len(played), 1)),
            "turn_number_f": tn, "n_played": len(played),
            "has_history": has_history,
            # user (NaN when cold; has_user_vec carries presence)
            "user_cf": user_cf_c,
            "has_user_vec": has_user_vec,
            "age_era_affinity": 0.0,
            "culture_match": float(len(m["tag_keys"] & {catalog_tag_key(w) for w in sess.get("culture", "").split()} - {""})),
            "age_group": sess.get("age_group", ""), "gender": sess.get("gender", ""),
            # organizer
            "goal_category": sess.get("goal_category", ""),
            "goal_specificity": sess.get("goal_specificity", ""),
            "listener_goal_cos": listener_goal_c,
            "session_minus_release_year": float((session_year - year) if (session_year and year) else 0.0),
            # state
            "tag_overlap": float(len(overlap)),
            "tag_overlap_idf": float(sum(cat.tag_idf.get(t, 0.0) for t in overlap)),
            "n_exact_tier": n_exact_tier, "max_tag_match_score": max_match,
            "tag_emb_cos": (float(q_tagv @ ttv) if q_tagv is not None and ttv is not None else NAN),
            "title_request_overlap": title_overlap,
            "has_constraint": has_constraint,
            "request_type": str((state.get("current_request") or {}).get("request_type") or ""),
            "intent_mode": str(trace.get("intent_mode") or ""),
            "target_artist_mode": tam,
            "routing_lyric": float(bool(routing.get("lyric_search"))),
            "routing_visual": float(bool(routing.get("image_or_visual_search"))),
            "routing_exact": float(bool(routing.get("exact_entity_probe"))),
            "temporal_strength": str(tc.get("strength") or ""),
            "year_in_constraint": in_constraint,
            "n_facts": len(state.get("facts") or []),
            # `wants_new_artist` dropped: deterministic projection of
            # target_artist_mode (kept as `wants_new` for x_same_artist_wants_new).
            # dense fill-in: lyric only (8B branch scores carry metadata/attrs)
            "q06_lyric_cos": q06_lyric_c,
            # conversation proxies (NaN when no message embedding)
            "msg_meta_cos": msg_meta_c,
            "msg_attr_cos": msg_attr_c,
            "msg_lyr_cos": msg_lyr_c,
            "ctx_meta_cos": ctx_meta_c,
            "lex_overlap_idf": float(sum(ctx.tok_idf.get(t_, 0.0)
                                         for t_ in (ctx.name_tokens_all.get(tid_, frozenset()) & msg_tokens))),
            "title_in_msg": float(bool(m["name_tokens"]) and m["name_tokens"] <= msg_tokens),
            "wants_new_proxy": wants_new_rx,
            # crosses (x_cflast_turn kept: cf_last x turn, NOT fusion-derived)
            "x_same_artist_wants_new": same_artist * wants_new,
            "x_cflast_turn": (cf_last_c * tn / 8.0) if not math.isnan(cf_last_c) else NAN,
            "x_era_hard": (in_constraint * float(tc.get("strength") == "hard")),
            "x_pop_within_artist": cat.pop_pct.get(tid_, 0.0) * cat.within_artist_pop.get(tid_, 0.0),
            # union artist concentration (semih F)
            "n_same_artist_in_union": float(max((artist_union_count.get(a, 0) for a in m["artists"]), default=0)),
            "artist_best_rank_in_union": float(min((artist_union_best.get(a, float("inf")) for a in m["artists"]),
                                                   default=float("inf"))),
            # pivot-away resemblance (semih P, current-state-only)
            "same_artist_as_abandoned": float(bool(set(m["artists"]) & abandoned_artist_ids)),
            "tag_overlap_abandoned": float(len(m["tag_keys"] & abandoned_tag_keys)),
        }
        if math.isinf(rec["artist_best_rank_in_union"]):
            rec["artist_best_rank_in_union"] = NAN
        # artist mention + negation-window rejection proxy
        rec["artist_mention"] = 0.0
        rec["rejected_artist_proxy"] = 0.0
        for ak in m.get("artist_name_keys", ()):
            pos = msg_norm.find(ak)
            if pos >= 0:
                rec["artist_mention"] = 1.0
                if NEGATION_RE.search(msg_norm[max(0, pos - 45): pos]):
                    rec["rejected_artist_proxy"] = 1.0
                break
        age = sess.get("age")
        if age and year and session_year:
            birth = session_year - int(age)
            rec["age_era_affinity"] = float(birth + 12 <= year <= birth + 25)
        # per-branch: NaN when absent (hit__ carries presence); margin = gap-to-top
        for b in ctx.branch_names:
            r_s = branch_hits.get(b)
            top = branch_top_score.get(b, NAN)
            if r_s:
                rec[f"rank__{b}"] = float(r_s[0])
                rec[f"score__{b}"] = float(r_s[1])
                rec[f"margin__{b}"] = (top - float(r_s[1])) if not math.isnan(top) else NAN
                rec[f"ratio__{b}"] = (float(r_s[1]) / top) if (not math.isnan(top) and abs(top) > 1e-12) else NAN
            else:
                rec[f"rank__{b}"] = NAN
                rec[f"score__{b}"] = NAN
                rec[f"margin__{b}"] = NAN
                rec[f"ratio__{b}"] = NAN
            rec[f"hit__{b}"] = float(bool(r_s))
        rows_out.append(rec)

    # within-pool z-scores of branch scores (hits only)
    for b in ctx.branch_names:
        col = np.array([r[f"score__{b}"] for r in rows_out], dtype=np.float64)
        ok = ~np.isnan(col)
        if ok.sum() > 1:
            mu, sd = float(col[ok].mean()), float(col[ok].std())
            for i, r in enumerate(rows_out):
                r[f"z__score__{b}"] = ((col[i] - mu) / sd) if (ok[i] and sd > 1e-12) else (0.0 if ok[i] else NAN)
        else:
            for i, r in enumerate(rows_out):
                r[f"z__score__{b}"] = 0.0 if ok[i] else NAN

    # within-pool percentiles, NaN-aware
    for feat in PCT_FEATURES_V9:
        vals = np.array([r.get(feat, NAN) for r in rows_out], dtype=np.float64)
        ok = ~np.isnan(vals)
        n_ok = int(ok.sum())
        if n_ok > 1:
            order = np.full(len(vals), NAN)
            order[ok] = vals[ok].argsort().argsort() / (n_ok - 1)
            for i, r in enumerate(rows_out):
                r[f"pct_{feat}"] = float(order[i]) if ok[i] else NAN
        else:
            for i, r in enumerate(rows_out):
                r[f"pct_{feat}"] = 0.5 if ok[i] else NAN

    return rows_out, playable
