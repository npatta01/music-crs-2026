"""LLM listwise-reranker pilot — prep stage.

Scores held-out test turns with model_v5_500/model_full.txt (reproducing the
trainer's exact feature packing: same best_branch_rank<=500 filter, same
sorted-factorize categorical codes computed over the FULL filtered dataset),
then selects 120 random turns in the head-ordering failure zone
(GT in GBDT top-50 but not top-3) and dumps each turn's GBDT top-25.

Output: exp/analysis/rerank/llm_rerank/pilot_turns.json
"""
from __future__ import annotations

import gc
import json
import random
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
import pyarrow.compute as pc
import pyarrow.dataset as pds

ROOT = Path("/Users/npatta01/data/projects/music-conversational-music-recomender-2026/.claude/worktrees/busy-ishizaka-f3d4a7")
FEATURES = ROOT / "exp/analysis/rerank/features_v3"
MODEL = ROOT / "exp/analysis/rerank/model_v5_500/model_full.txt"
GT = ROOT / "exp/ground_truth/devset.json"
OUT = ROOT / "exp/analysis/rerank/llm_rerank/pilot_turns.json"

CATEGORICALS = ["age_group", "gender", "goal_category", "goal_specificity",
                "request_type", "intent_mode", "target_artist_mode",
                "temporal_strength"]
MAX_POOL_RANK = 500

# --- split (exactly as specified / as train_lgbm.py seed=13) ---
sess_user = {str(r["session_id"]): str(r["user_id"]) for r in json.load(open(GT))}
dataset = pds.dataset(str(FEATURES))
filt = pc.field("best_branch_rank") <= MAX_POOL_RANK
sids_all = sorted(set(dataset.to_table(columns=["session_id"]).column(0).to_pylist()))
users = sorted({sess_user.get(s, s) for s in sids_all})
rng = random.Random(13)
rng.shuffle(users)
n_u = len(users)
tr_u = set(users[:int(0.7 * n_u)])
va_u = set(users[int(0.7 * n_u):int(0.85 * n_u)])
test_sids = sorted(s for s in sids_all
                   if sess_user.get(s, s) not in tr_u and sess_user.get(s, s) not in va_u)
print(f"users={n_u} test sessions={len(test_sids)}", flush=True)

# --- categorical code maps from the FULL filtered dataset (matches factorize sort=True) ---
cat_maps = {}
for c in CATEGORICALS:
    col = dataset.to_table(columns=[c], filter=filt).column(0)
    vals = col.to_pandas().fillna("")
    uniq = sorted(pd.unique(vals))
    cat_maps[c] = {v: i for i, v in enumerate(uniq)}
    del col, vals
    gc.collect()
print("cat maps built", flush=True)

# --- load test rows ---
tfilt = filt & pc.field("session_id").isin(test_sids)
tbl = dataset.to_table(filter=tfilt)
print(f"test rows: {tbl.num_rows:,}", flush=True)

booster = lgb.Booster(model_file=str(MODEL))
feat_names = booster.feature_name()
assert all(f in tbl.schema.names for f in feat_names), "model feature missing from parquet"

n = tbl.num_rows
X = np.empty((n, len(feat_names)), dtype=np.float32)
for j, c in enumerate(feat_names):
    col = tbl.column(c)
    if c in CATEGORICALS:
        vals = col.to_pandas().fillna("")
        X[:, j] = vals.map(cat_maps[c]).fillna(-1).to_numpy(dtype=np.float32)
    else:
        X[:, j] = np.nan_to_num(
            col.to_numpy(zero_copy_only=False).astype(np.float32, copy=False), nan=0.0)

ids = tbl.select(["session_id", "turn_number", "track_id", "label"]).to_pandas()
del tbl
gc.collect()
ids["score"] = booster.predict(X)
del X
gc.collect()
print("scored", flush=True)

# --- per-turn GBDT ranking; select failure-zone turns ---
turns = []
for (sid, tn), g in ids.groupby(["session_id", "turn_number"], sort=False):
    if g["label"].max() != 1:
        continue
    g = g.sort_values("score", ascending=False, kind="mergesort").reset_index(drop=True)
    gt_pos = int(np.flatnonzero(g["label"].to_numpy() == 1)[0]) + 1  # 1-based
    turns.append({
        "session_id": sid, "turn_number": int(tn),
        "user_id": sess_user.get(sid, sid),
        "gt_track_id": str(g.loc[g["label"] == 1, "track_id"].iloc[0]),
        "gt_rank_gbdt": gt_pos,
        "n_pool": int(len(g)),
        "top25": [{"track_id": str(t), "score": float(s)}
                  for t, s in zip(g["track_id"].head(25), g["score"].head(25))],
        "top50_gbdt": [str(t) for t in g["track_id"].head(50)],
    })

df = pd.DataFrame([{k: t[k] for k in ("gt_rank_gbdt",)} for t in turns])
nd = (1.0 / np.log2(df.gt_rank_gbdt + 1)).where(df.gt_rank_gbdt <= 20, 0.0)
print(f"REPRO CHECK vs model_v5_500 report (ndcg20=0.23503, hit1=0.09209): "
      f"ndcg20={nd.mean():.5f} hit1={(df.gt_rank_gbdt <= 1).mean():.5f}", flush=True)
print(f"playable test turns: {len(turns)}", flush=True)
print(f"  gt in top3: {(df.gt_rank_gbdt <= 3).sum()}, in (3,50]: "
      f"{((df.gt_rank_gbdt > 3) & (df.gt_rank_gbdt <= 50)).sum()}, "
      f"in (3,25]: {((df.gt_rank_gbdt > 3) & (df.gt_rank_gbdt <= 25)).sum()}", flush=True)

eligible = [t for t in turns if 3 < t["gt_rank_gbdt"] <= 50]
sel_rng = random.Random(13)
sample = sel_rng.sample(eligible, min(120, len(eligible)))
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps({"n_test_turns": len(turns), "n_eligible": len(eligible),
                           "turns": sample}, indent=1))
print(f"wrote {OUT} with {len(sample)} turns", flush=True)
