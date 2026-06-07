"""Offline replay of reranker serving (no force-keep) to compare models without Modal.

The reranker scores each turn's NATURAL branch-pool union (no golden force-keep) and ranks it —
identical to live serving (parity proven). For each trace turn we build features once, score
with both the with-block-H and no-block-H boosters, and compute NDCG@20 (overall + per intent).
A match to the Modal live number (with-H 0.2092) validates the replay; the no-H number then tells
us, for free, what dropping block H would score live.
"""
import json
import sys
import numpy as np
import pandas as pd
import lightgbm as lgb

from mcrs.qu_modules.v0plus_catalog_lance import LanceDbCatalog
from mcrs.rerank.online import TurnReranker
from mcrs.rerank.features import catalog_metadata_frame

TRACE = "exp/inference/devset/v0plus_compiler_all_retrievers_devset_phaseB_trace.jsonl"
WITH_H = "exp/rerank/devset_phaseB/model_single/model.txt"
NO_H = "exp/rerank/devset_phaseB/model_noH/model.txt"
GT = "exp/ground_truth/devset.json"
LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 else 0  # 0 = all

gt = {}
for r in json.load(open(GT)):
    gt[(r["session_id"], int(r["turn_number"]))] = r.get("ground_truth_track_id") or r.get("gt_track_id")

cat = LanceDbCatalog(db_uri="cache/lancedb_emb", table_name="music_track_catalog")
meta = catalog_metadata_frame(cat)
rr = TurnReranker.from_path(WITH_H, cat, meta=meta)  # builds with-H features (superset)
cols_with = json.load(open(WITH_H.replace("model.txt", "model.features.json")))["feature_columns"]
cols_no = json.load(open(NO_H.replace("model.txt", "model.features.json")))["feature_columns"]
b_with = lgb.Booster(model_file=WITH_H)
b_no = lgb.Booster(model_file=NO_H)
from mcrs.rerank.train import to_model_matrix

def ndcg20(ranked, g):
    for i, t in enumerate(ranked[:20]):
        if t == g:
            return 1.0 / np.log2(i + 2)
    return 0.0

from collections import defaultdict
res = {"with": defaultdict(list), "no": defaultdict(list)}
overall = {"with": [], "no": []}
n = 0
with open(TRACE) as fh:
    for line in fh:
        e = json.loads(line)
        k = (e["session_id"], int(e["turn_number"]))
        g = gt.get(k)
        intent = e["trace"].get("intent_mode", "?")
        feats = rr.features_for_entry(e)
        if feats.empty:
            continue
        tids = feats["track_id"].to_numpy()
        for tag, booster, cols in (("with", b_with, cols_with), ("no", b_no, cols_no)):
            X = to_model_matrix(feats, cols)
            s = booster.predict(X)
            order = tids[np.argsort(-s, kind="stable")]
            v = ndcg20(list(order), g)
            overall[tag].append(v); res[tag][intent].append(v)
        n += 1
        if LIMIT and n >= LIMIT:
            break

for tag in ("with", "no"):
    print(f"\n=== {'WITH block H' if tag=='with' else 'NO block H'} (offline serve-replay) ===")
    print(f"OVERALL NDCG@20: {np.mean(overall[tag]):.4f}  n={len(overall[tag])}")
    for it in ["refinement", "open_explore", "playlist_build", "pivot"]:
        if res[tag][it]:
            print(f"  {it:15s} n={len(res[tag][it]):5d}  NDCG@20={np.mean(res[tag][it]):.4f}")
