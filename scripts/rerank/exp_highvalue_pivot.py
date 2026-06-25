"""Pivot model: 43-feature base + 3 free matrix columns + 5 computed pivot
features, graded labels, binary-GT eval on the pivot slice.

Computed features:
  artist_transition_prior          P(next artist=candidate | last-played artist), OOF
  artist_pivot_target_rate         global in-degree of candidate artist as a pivot
                                   target (backoff for transition_prior sparsity), OOF
  colisten_adjacency_to_abandoned  cosine(cand cf_bpr, centroid of abandoned tracks)
  artist_recency_in_session        turns since candidate's artist last played (99=never)
  x_priorfail_novelty              (prior turn DID NOT move toward goal) x (new artist)
"""
import ast
import collections
import json
import math
import sys

import lightgbm as lgb
import numpy as np
import pandas as pd

sys.path.insert(0, "scripts/rerank")
import train_v9 as T
from build_features import Catalog
from datasets import load_dataset
from features_v9 import is_pivot_turn

B = "exp/analysis/rerank/train_v9"
meta = json.load(open(f"{B}/meta.json")); cols = meta["cols"]; cat_idx = meta["cat_idx"]
cm = json.load(open(f"{B}/cat_maps_v9.json")); X = np.load(f"{B}/X.npy", mmap_mode="r")
y = np.load(f"{B}/y.npy"); n = len(y); turn = np.load(f"{B}/turn_arr.npy")
sid_codes = np.load(f"{B}/sid_codes.npy"); trk_codes = np.load(f"{B}/trk_codes.npy")
sid_uniq = np.array(json.load(open(f"{B}/sid_uniq.json")), dtype=object)
trk_uniq = np.array(json.load(open(f"{B}/trk_uniq.json")), dtype=object)
sid_fold = np.load(f"{B}/sid_fold.npy"); row_w = np.load(f"{B}/row_weights.npy")
pmask = T.pivot_mask_from_codes(X, cols, cm); row_fold = sid_fold[sid_codes]
cv_pivot = pmask & (row_fold != -1)

PIVOT_43 = T._PIVOT_DEMOTION + [
    "tag_emb_cos", "tag_overlap_idf", "pct_tag_overlap_idf", "tag_count", "n_exact_tier",
    "max_tag_match_score", "pct_lex_overlap_idf", "q06_lyric_cos", "listener_goal_cos",
    "artist_track_count", "within_artist_pop", "x_pop_within_artist", "pct_pop_pct", "pct_era_pop_pct",
    "score__centroid.anchor_tracks.audio_laion_clap", "ratio__centroid.anchor_tracks.audio_laion_clap",
    "z__score__centroid.anchor_tracks.audio_laion_clap", "score__centroid.anchor_tracks.cf_bpr",
    "z__score__centroid.anchor_tracks.cf_bpr", "rank__bm25", "score__bm25", "margin__bm25", "z__score__bm25",
    "score__dense.qwen_8b.attributes.attributes_qwen3_embedding_8b",
    "z__score__dense.qwen_8b.attributes.attributes_qwen3_embedding_8b",
]
FREE = [
    "hit__lookup.resolved_artist_discography", "rank__lookup.resolved_artist_discography",
    "score__dense.qwen_0_6b.lyric.lyrics_qwen3_embedding_0_6b",
    "rank__dense.qwen_0_6b.lyric.lyrics_qwen3_embedding_0_6b", "rank__centroid.user.cf_bpr",
]
BASE = PIVOT_43  # no free columns (they diluted on pivots)
assert all(c in cols for c in BASE), [c for c in BASE if c not in cols]

print("loading catalog...", flush=True)
cat = Catalog("cache/lancedb", "music_track_catalog")
def artists_of(tid):
    m = cat.meta.get(str(tid)); return m["artists"] if m else ()

gt_map = {(str(r["session_id"]), int(r["turn_number"])): str(r["ground_truth_track_id"])
          for r in json.load(open("exp/ground_truth/devset.json"))}
sess = collections.defaultdict(dict)
for (s, t), g in gt_map.items(): sess[s][t] = g
sess_fold = {str(s): int(sid_fold[i]) for i, s in enumerate(sid_uniq)}

# goal-progress (DOES_NOT_MOVE) — used by x_priorfail_novelty AND graded labels
ds = load_dataset("talkpl-ai/TalkPlayData-Challenge-Dataset", split="test"); dnm = set()
for r in ds:
    s = str(r["session_id"]); g = r["goal_progress_assessments"]
    if isinstance(g, str): g = ast.literal_eval(g)
    for a in g:
        if str(a.get("goal_progress_assessment")) == "DOES_NOT_MOVE_TOWARD_GOAL":
            dnm.add((s, int(a["turn_number"])))

# OOF artist-transition counts + global in-degree (target rate)
def build_trans(exclude_fold):
    cnt = collections.defaultdict(collections.Counter); indeg = collections.Counter(); tot = 0
    for s, tg in sess.items():
        if sess_fold.get(s) == exclude_fold: continue
        ts = sorted(tg)
        for i in range(1, len(ts)):
            for ap in artists_of(tg[ts[i - 1]]):
                for an in artists_of(tg[ts[i]]):
                    cnt[ap][an] += 1; indeg[an] += 1; tot += 1
    return cnt, indeg, max(tot, 1)
trans_by_fold = {f: build_trans(f) for f in range(5)}
trans_all = build_trans(-99)
def trans_feats(fold, prev_art, cand_art):
    cnt, indeg, tot = trans_by_fold.get(fold, trans_all) if fold >= 0 else trans_all
    cond = 0.0
    for ap in prev_art:
        d = cnt.get(ap)
        if not d: continue
        dt = sum(d.values())
        for ac in cand_art:
            if ac in d: cond = max(cond, d[ac] / dt)
    rate = max((indeg.get(ac, 0) / tot for ac in cand_art), default=0.0)
    return cond, rate

# abandoned cf-centroid per pivot turn (from trace)
print("parsing trace...", flush=True)
TRACE = ("exp/pipeline/runs/full-local-devset-20260617/retrieval/inference/devset/"
         "state_ranker_v10_rrf_devset_trace.jsonl")
abandoned = {}
with open(TRACE) as f:
    for line in f:
        r = json.loads(line); t = r["trace"]
        es = t.get("extracted_state") or {}
        if not is_pivot_turn(t.get("intent_mode"), str(es.get("target_artist_mode") or "")): continue
        k = (str(r["session_id"]), int(r["turn_number"])); vecs = []
        for fb in (es.get("track_feedback") or []):
            role = str(fb.get("role") or "").lower()
            try: sent = float(fb.get("overall_sentiment"))
            except (TypeError, ValueError): sent = 0.0
            if role in ("rejected", "satisfied") or sent < 0:
                v = cat.v("cf_bpr", str(fb.get("track_id") or ""))
                if v is not None: vecs.append(v)
        if vecs:
            c = np.mean(vecs, axis=0); nrm = np.linalg.norm(c)
            abandoned[k] = (c / nrm).astype(np.float32) if nrm > 0 else None

# per-session artist last-seen turn (for recency) and played-artist set (for novelty)
last_seen = {}  # (sid) -> {artist: last turn played}
played_artists_upto = {}  # (sid,t) -> set of artists played at turns < t
for s, tg in sess.items():
    seen = {}; cum = set()
    for t in sorted(tg):
        played_artists_upto[(s, t)] = set(cum)
        for a in artists_of(tg[t]):
            seen[a] = t; cum.add(a)
    last_seen[s] = seen  # final; we recompute per turn below

# ---- compute features for pivot rows ----
pidx = np.flatnonzero(pmask)
f_trans = np.zeros(n, np.float32); f_rate = np.zeros(n, np.float32); f_coli = np.zeros(n, np.float32)
f_recency = np.full(n, 99.0, np.float32); f_pfn = np.zeros(n, np.float32)
for i in pidx:
    sid = str(sid_uniq[sid_codes[i]]); t = int(turn[i]); trk = str(trk_uniq[trk_codes[i]])
    cand = artists_of(trk); fold = int(row_fold[i])
    prev = gt_map.get((sid, t - 1))
    f_trans[i], f_rate[i] = trans_feats(fold, artists_of(prev) if prev else (), cand)
    ab = abandoned.get((sid, t))
    if ab is not None:
        cv = cat.v("cf_bpr", trk)
        if cv is not None: f_coli[i] = float(np.dot(cv, ab))
    played = played_artists_upto.get((sid, t), set())
    # recency: turns since any cand artist last played before t
    rec = 99.0
    for a in cand:
        for tt in range(t - 1, 0, -1):
            if a in artists_of(gt_map.get((sid, tt), "")):
                rec = min(rec, t - tt); break
    f_recency[i] = rec
    novelty = 0.0 if (cand and any(a in played for a in cand)) else 1.0
    f_pfn[i] = novelty if (sid, t) in dnm else 0.0
print(f"transition_prior nz {100*(f_trans[pidx]>0).mean():.1f}% | target_rate nz {100*(f_rate[pidx]>0).mean():.1f}% | "
      f"colisten nz {100*(f_coli[pidx]!=0).mean():.1f}% | recency<99 {100*(f_recency[pidx]<99).mean():.1f}% | "
      f"priorfail_nov nz {100*(f_pfn[pidx]>0).mean():.1f}%", flush=True)

# graded labels
trk_s = trk_uniq[trk_codes[pidx]]
gt_arr = np.array([gt_map.get((str(sid_uniq[sid_codes[i]]), int(turn[i]))) for i in pidx], dtype=object)
is_gt = (gt_arr == trk_s)
future = set()
for s, tg in sess.items():
    ts = sorted(tg)
    for i, t in enumerate(ts):
        for t2 in ts[i + 1:]: future.add((s, t, tg[t2]))
key = list(zip([str(x) for x in sid_uniq[sid_codes[pidx]]], turn[pidx].astype(int).tolist()))
fk = list(zip([k[0] for k in key], [k[1] for k in key], [str(x) for x in trk_s]))
is_fut = np.array([k in future for k in fk]); moves = np.array([(k[0], k[1] + 1) not in dnm for k in key])
grades = np.where(is_gt, np.where(moves, 3, 1), np.where(is_fut, 2, 0)).astype(np.int32)
y_graded = np.zeros(n, np.int32); y_graded[pidx] = grades
print("grade dist:", dict(collections.Counter(grades.tolist())), flush=True)

def ndcg_bin(scores, rm):
    df = pd.DataFrame({"sid": sid_codes, "turn": turn.astype(int), "y": y, "score": scores})[rm]
    denom = df.groupby(["sid", "turn"]).ngroups; nd = 0.0
    for _, g in df.groupby(["sid", "turn"], sort=False):
        gt = g[g.y == 1]
        if not len(gt): continue
        r = T.gt_tie_averaged_rank(g.score.to_numpy(), float(gt.score.iloc[0]))
        nd += (1 / math.log2(r + 1)) if r <= 20 else 0
    return nd / denom

ci, fc, fcat = T.select_feature_columns(cols, cat_idx, BASE)
EXTRA = ["artist_transition_prior", "colisten_adjacency_to_abandoned"]
extra = np.column_stack([f_trans, f_coli])
ROUNDS = 300; depths = [50, 100, 150, 200, 300]
arms = {"base43_graded": False, "base43+2new_graded": True}
res = {a: {d: np.full(n, np.nan) for d in depths} for a in arms}
bst_t = None
for fold in range(5):
    tr = np.flatnonzero((row_fold != fold) & (row_fold != -1) & pmask)
    te = np.flatnonzero((row_fold == fold) & pmask)
    tr, trg = T._grouped(tr, sid_codes, turn)
    for arm, add in arms.items():
        names = fc + (EXTRA if add else [])
        def mat(idx):
            base = X[np.ix_(idx, ci)]
            return np.ascontiguousarray(np.hstack([base, extra[idx]]) if add else base).astype(np.float32)
        mono = [(-1 if c == "is_played_track" else 0) for c in names]
        d = lgb.Dataset(mat(tr), label=y_graded[tr], group=trg, weight=row_w[tr],
                        feature_name=names, categorical_feature=fcat, free_raw_data=False)
        d.construct()
        bst = lgb.train(dict(T.LGB_PARAMS, monotone_constraints=mono), d,
                        num_boost_round=ROUNDS, callbacks=[lgb.log_evaluation(0)])
        for dep in depths:
            res[arm][dep][te] = bst.predict(mat(te), num_iteration=dep)
        if add: bst_t = bst
    print(f"fold {fold} done", flush=True)

print("\n43 graded | base vs +2 new computed | NDCG@20 (binary-GT, CV pivot turns):", flush=True)
print(f"{'trees':>6s} {'base43':>10s} {'+2new':>10s}", flush=True)
for dep in depths:
    a = ndcg_bin(res["base43_graded"][dep], cv_pivot & ~np.isnan(res["base43_graded"][dep]))
    bb = ndcg_bin(res["base43+2new_graded"][dep], cv_pivot & ~np.isnan(res["base43+2new_graded"][dep]))
    print(f"{dep:6d} {a:10.4f} {bb:10.4f}", flush=True)
print("ref: 30+2hv graded 0.1951 | 43 graded 0.1845 | v10 0.2351", flush=True)
imp = dict(zip(bst_t.feature_name(), bst_t.feature_importance(importance_type="gain"))); tot = sum(imp.values()) or 1
for nm in EXTRA:
    print(f"  {nm}: gain {100*imp.get(nm,0)/tot:.1f}%", flush=True)
print("DONE_HV2", flush=True)
