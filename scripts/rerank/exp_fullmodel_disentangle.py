"""Full-model disentangle + dual. 4 arms (binary / colisten-only / graded-only /
both) on the 148-feature model, all rows. Then the explicit dual: binary v10 on
non-pivot turns + best arm on pivot turns. Eval overall + pivot (binary-GT)."""
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

B = "exp/analysis/rerank/train_v9"
meta = json.load(open(f"{B}/meta.json")); cols = meta["cols"]; cat_idx = meta["cat_idx"]
cm = json.load(open(f"{B}/cat_maps_v9.json")); X = np.load(f"{B}/X.npy", mmap_mode="r")
y = np.load(f"{B}/y.npy"); n = len(y); turn = np.load(f"{B}/turn_arr.npy")
sid_codes = np.load(f"{B}/sid_codes.npy"); trk_codes = np.load(f"{B}/trk_codes.npy")
sid_uniq = np.array(json.load(open(f"{B}/sid_uniq.json")), dtype=object)
trk_uniq = np.array(json.load(open(f"{B}/trk_uniq.json")), dtype=object)
sid_fold = np.load(f"{B}/sid_fold.npy"); row_w = np.load(f"{B}/row_weights.npy")
pmask = T.pivot_mask_from_codes(X, cols, cm); row_fold = sid_fold[sid_codes]
cv = row_fold != -1; cv_pivot = cv & pmask

print("loading catalog...", flush=True)
cat = Catalog("cache/lancedb", "music_track_catalog")
def artists_of(tid):
    m = cat.meta.get(str(tid)); return m["artists"] if m else ()
gt_map = {(str(r["session_id"]), int(r["turn_number"])): str(r["ground_truth_track_id"])
          for r in json.load(open("exp/ground_truth/devset.json"))}
sess = collections.defaultdict(dict)
for (s, t), g in gt_map.items(): sess[s][t] = g
ds = load_dataset("talkpl-ai/TalkPlayData-Challenge-Dataset", split="test"); dnm = set()
for r in ds:
    s = str(r["session_id"]); g = r["goal_progress_assessments"]
    if isinstance(g, str): g = ast.literal_eval(g)
    for a in g:
        if str(a.get("goal_progress_assessment")) == "DOES_NOT_MOVE_TOWARD_GOAL":
            dnm.add((s, int(a["turn_number"])))

print("parsing trace...", flush=True)
TRACE = ("exp/pipeline/runs/full-local-devset-20260617/retrieval/inference/devset/"
         "state_ranker_v10_rrf_devset_trace.jsonl")
abandoned = {}
with open(TRACE) as f:
    for line in f:
        r = json.loads(line); es = (r["trace"].get("extracted_state") or {})
        vecs = []
        for fb in (es.get("track_feedback") or []):
            role = str(fb.get("role") or "").lower()
            try: sent = float(fb.get("overall_sentiment"))
            except (TypeError, ValueError): sent = 0.0
            if role in ("rejected", "satisfied") or sent < 0:
                v = cat.v("cf_bpr", str(fb.get("track_id") or ""))
                if v is not None: vecs.append(v)
        if vecs:
            c = np.mean(vecs, axis=0); nrm = np.linalg.norm(c)
            if nrm > 0:
                abandoned[(str(r["session_id"]), int(r["turn_number"]))] = (c / nrm).astype(np.float32)

f_coli = np.zeros(n, np.float32)
sid_all = sid_uniq[sid_codes]; trk_all = trk_uniq[trk_codes]
for i in range(n):
    ab = abandoned.get((str(sid_all[i]), int(turn[i])))
    if ab is None: continue
    v = cat.v("cf_bpr", str(trk_all[i]))
    if v is not None: f_coli[i] = float(np.dot(v, ab))

future = set()
for s, tg in sess.items():
    ts = sorted(tg)
    for i, t in enumerate(ts):
        for t2 in ts[i + 1:]: future.add((s, t, tg[t2]))
keys = list(zip([str(x) for x in sid_all], turn.astype(int).tolist()))
gt_arr = np.array([gt_map.get(k) for k in keys], dtype=object)
is_gt = (gt_arr == trk_all)
is_fut = np.fromiter(((keys[i][0], keys[i][1], str(trk_all[i])) in future for i in range(n)), bool, n)
moves = np.fromiter(((k[0], k[1] + 1) not in dnm for k in keys), bool, n)
y_graded = np.where(is_gt, np.where(moves, 3, 1), np.where(is_fut, 2, 0)).astype(np.int32)
print("features ready. colisten nz %.1f%%" % (100 * (f_coli != 0).mean()), flush=True)

def ndcg(scores, rm):
    df = pd.DataFrame({"sid": sid_codes, "turn": turn.astype(int), "y": y, "score": scores})[rm]
    denom = df.groupby(["sid", "turn"]).ngroups; nd = 0.0
    for _, g in df.groupby(["sid", "turn"], sort=False):
        gt = g[g.y == 1]
        if not len(gt): continue
        r = T.gt_tie_averaged_rank(g.score.to_numpy(), float(gt.score.iloc[0]))
        nd += (1 / math.log2(r + 1)) if r <= 20 else 0
    return nd / denom

allcols = T.training_feature_subset(cols, "all")
ci = [cols.index(c) for c in allcols]; cset = set(cat_idx)
fcat = [j for j, c in enumerate(allcols) if cols.index(c) in cset]
ROUNDS = 150
arms = {"binary": (y, False), "colisten_only": (y, True),
        "graded_only": (y_graded, False), "both": (y_graded, True)}
res = {a: np.full(n, np.nan) for a in arms}
for fold in range(5):
    tr = np.flatnonzero((row_fold != fold) & (row_fold != -1)); te = np.flatnonzero(row_fold == fold)
    tr, trg = T._grouped(tr, sid_codes, turn)
    for arm, (yy, add) in arms.items():
        names = allcols + (["colisten"] if add else [])
        def mat(idx):
            base = X[np.ix_(idx, ci)]
            return np.ascontiguousarray(np.hstack([base, f_coli[idx, None]]) if add else base).astype(np.float32)
        mono = [(-1 if c == "is_played_track" else 0) for c in names]
        d = lgb.Dataset(mat(tr), label=yy[tr], group=trg, weight=row_w[tr],
                        feature_name=names, categorical_feature=fcat, free_raw_data=False)
        d.construct()
        bst = lgb.train(dict(T.LGB_PARAMS, monotone_constraints=mono), d,
                        num_boost_round=ROUNDS, callbacks=[lgb.log_evaluation(0)])
        res[arm][te] = bst.predict(mat(te), num_iteration=ROUNDS)
    print(f"fold {fold} done", flush=True)

print("\nFULL MODEL (all rows, 150 trees) | overall vs pivot NDCG@20 (binary-GT, CV):", flush=True)
print(f"{'arm':16s} {'overall':>9s} {'pivot':>9s}", flush=True)
for a in arms:
    print(f"{a:16s} {ndcg(res[a], cv & ~np.isnan(res[a])):9.4f} {ndcg(res[a], cv_pivot & ~np.isnan(res[a])):9.4f}", flush=True)

# DUAL: binary on non-pivot turns + best pivot arm on pivot turns
for pivot_arm in ["both", "graded_only", "colisten_only"]:
    dual = res["binary"].copy(); dual[pmask] = res[pivot_arm][pmask]
    o = ndcg(dual, cv & ~np.isnan(dual)); p = ndcg(dual, cv_pivot & ~np.isnan(dual))
    print(f"DUAL(binary + {pivot_arm} on pivot)   overall {o:.4f}  pivot {p:.4f}  vs binary overall "
          f"{ndcg(res['binary'], cv & ~np.isnan(res['binary'])):.4f}", flush=True)
print("DONE_DIS", flush=True)
