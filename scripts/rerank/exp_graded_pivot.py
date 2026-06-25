"""One-off experiment: graded-label pivot model on the 30-feature set.

Holds features + rows + eval fixed vs the binary baseline; the ONLY change is the
training label, which becomes a 4-level integer grade:

    3  candidate == GT and GT moved toward goal (next-turn assessment != DOES_NOT)
    2  candidate != GT but is a tag-NEIGHBOR of the GT  (>= K shared tag_keys)
    1  candidate == GT but GT did NOT move toward goal
    0  everything else

Eval is still against the TRUE binary GT (tie-averaged NDCG@20), so the number is
directly comparable to the binary 30-feat run (0.176) and v10 (0.235).
"""
import ast, json, math, sys, collections
import numpy as np, pandas as pd, lightgbm as lgb

sys.path.insert(0, "scripts/rerank")
import train_v9 as T
from build_features import Catalog

B = "exp/analysis/rerank/train_v9"
NEIGHBOR_K = 6
ROUNDS = 300
DEPTHS = [50, 100, 150, 200, 300]

meta = json.load(open(f"{B}/meta.json")); cols = meta["cols"]; cat_idx = meta["cat_idx"]
cm = json.load(open(f"{B}/cat_maps_v9.json"))
X = np.load(f"{B}/X.npy", mmap_mode="r")
biny = np.load(f"{B}/y.npy")                      # binary GT indicator (EVAL only)
turn = np.load(f"{B}/turn_arr.npy"); sidc = np.load(f"{B}/sid_codes.npy"); trkc = np.load(f"{B}/trk_codes.npy")
sid_uniq = json.load(open(f"{B}/sid_uniq.json")); trk_uniq = json.load(open(f"{B}/trk_uniq.json"))
sid_fold = np.load(f"{B}/sid_fold.npy"); row_w = np.load(f"{B}/row_weights.npy")
pmask = T.pivot_mask_from_codes(X, cols, cm); row_fold = sid_fold[sidc]

# 30 features = original demotion(18) + original Tier-1(12)
TIER1 = ["pct_cf_centroid", "pct_user_cf", "pct_pop_pct", "pct_era_pop_pct",
         "tag_emb_cos", "pct_tag_overlap_idf", "n_exact_tier", "max_tag_match_score",
         "q06_lyric_cos", "listener_goal_cos",
         "score__dense.qwen_8b.metadata.metadata_qwen3_embedding_8b",
         "z__score__dense.qwen_8b.metadata.metadata_qwen3_embedding_8b"]
FEATS = list(T._PIVOT_DEMOTION) + TIER1
ci, feat_cols, feat_cat = T.select_feature_columns(cols, cat_idx, FEATS)
print(f"features: {len(feat_cols)} (expect 30)", flush=True)

gt_map = {(str(r["session_id"]), int(r["turn_number"])): str(r["ground_truth_track_id"])
          for r in json.load(open("exp/ground_truth/devset.json"))}
from datasets import load_dataset
ds = load_dataset("talkpl-ai/TalkPlayData-Challenge-Dataset", split="test")
assess = {}
for row in ds:
    sid = str(row["session_id"]); g = row["goal_progress_assessments"]
    if isinstance(g, str): g = ast.literal_eval(g)
    for a in g:
        assess[(sid, int(a["turn_number"]))] = str(a.get("goal_progress_assessment"))
cat = Catalog("cache/lancedb", "music_track_catalog")
def tagkeys(tid):
    m = cat.meta.get(tid); return m["tag_keys"] if m else frozenset()

# ---- build graded label for pivot rows ----
ygr = np.zeros(len(biny), dtype=np.float32)
piv_idx = np.flatnonzero(pmask)
pdf = pd.DataFrame({"i": piv_idx, "sid": sidc[piv_idx], "turn": turn[piv_idx].astype(int), "trk": trkc[piv_idx]})
n3 = n1 = n2 = 0
for (s, t), grp in pdf.groupby(["sid", "turn"], sort=False):
    sid = str(sid_uniq[s]); key = (sid, int(t)); gt = gt_map.get(key)
    if gt is None: continue
    gt_tags = tagkeys(gt)
    moves = (t >= 8) or (assess.get((sid, t + 1)) != "DOES_NOT_MOVE_TOWARD_GOAL")
    for i, trk in zip(grp.i.values, grp.trk.values):
        tid = trk_uniq[trk]
        if tid == gt:
            ygr[i] = 3.0 if moves else 1.0
            n3 += int(moves); n1 += int(not moves)
        elif gt_tags and len(tagkeys(tid) & gt_tags) >= NEIGHBOR_K:
            ygr[i] = 2.0; n2 += 1
print(f"graded labels on pivot rows: GT-moves(3)={n3}  GT-not(1)={n1}  neighbors(2)={n2}  "
      f"(avg neighbors/turn={n2/max(n3+n1,1):.1f})", flush=True)

# ---- 5-fold CV: train on graded label, score test pivot rows ----
mono = [(-1 if c == "is_played_track" else 0) for c in feat_cols]
params = dict(T.LGB_PARAMS, monotone_constraints=mono)
oofd = {d: np.full(len(biny), np.nan) for d in DEPTHS}
for fold in range(5):
    tr = np.flatnonzero((row_fold != fold) & (row_fold != -1) & pmask)
    te = np.flatnonzero((row_fold == fold) & pmask)
    tr, trg = T._grouped(tr, sidc, turn)
    Xtr = np.ascontiguousarray(X[np.ix_(tr, ci)])
    d = lgb.Dataset(Xtr, label=ygr[tr], group=trg, weight=row_w[tr],
                    feature_name=feat_cols, categorical_feature=feat_cat, free_raw_data=True)
    d.construct(); del Xtr
    bst = lgb.train(params, d, num_boost_round=ROUNDS, callbacks=[lgb.log_evaluation(0)])
    Xte = np.ascontiguousarray(X[np.ix_(te, ci)])
    for dep in DEPTHS:
        oofd[dep][te] = bst.predict(Xte, num_iteration=dep)
    print(f"fold {fold} done", flush=True)

# ---- eval vs TRUE binary GT ----
cv_pivot = pmask & (row_fold != -1)
def ndcg(scores, rm):
    df = pd.DataFrame({"sid": sidc, "turn": turn.astype(int), "y": biny, "score": scores})[rm]
    denom = df.groupby(["sid", "turn"]).ngroups; nd = 0.0
    for _, g in df.groupby(["sid", "turn"], sort=False):
        gg = g[g.y == 1]
        if not len(gg): continue
        r = T.gt_tie_averaged_rank(g.score.to_numpy(), float(gg.score.iloc[0]))
        nd += (1 / math.log2(r + 1)) if r <= 20 else 0
    return nd / denom
print("\nGRADED-label 30-feat pivot, NDCG@20 vs trees (CV pivot turns, eval=binary GT):", flush=True)
for dep in DEPTHS:
    print(f"  {dep:4d} trees: {ndcg(oofd[dep], cv_pivot & ~np.isnan(oofd[dep])):.4f}", flush=True)
print("baselines on this same slice:  binary 30-feat=0.176   v10(general,148)=0.2351", flush=True)
print("GRADED_DONE", flush=True)
