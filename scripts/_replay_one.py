"""Replay one model on one trace (serve-equivalent, no force-keep). Args: trace model [limit]."""
import json, sys
import numpy as np, pandas as pd, lightgbm as lgb
from collections import defaultdict
from mcrs.qu_modules.v0plus_catalog_lance import LanceDbCatalog
from mcrs.rerank.online import TurnReranker
from mcrs.rerank.features import catalog_metadata_frame
from mcrs.rerank.train import to_model_matrix

TRACE, MODEL = sys.argv[1], sys.argv[2]
LIMIT = int(sys.argv[3]) if len(sys.argv) > 3 else 0
GT = "exp/ground_truth/devset.json"

gt = {}
for r in json.load(open(GT)):
    gt[(r["session_id"], int(r["turn_number"]))] = r.get("ground_truth_track_id") or r.get("gt_track_id")

cat = LanceDbCatalog(db_uri="cache/lancedb_emb", table_name="music_track_catalog")
meta = catalog_metadata_frame(cat)
rr = TurnReranker.from_path(MODEL, cat, meta=meta)
cols = json.load(open(MODEL.replace("model.txt", "model.features.json")))["feature_columns"]
booster = lgb.Booster(model_file=MODEL)

def ndcg20(ranked, g):
    for i, t in enumerate(ranked[:20]):
        if t == g:
            return 1.0 / np.log2(i + 2)
    return 0.0

overall = []; by = defaultdict(list); n = 0
with open(TRACE) as fh:
    for line in fh:
        e = json.loads(line)
        k = (e["session_id"], int(e["turn_number"])); g = gt.get(k)
        intent = e["trace"].get("intent_mode", "?")
        feats = rr.features_for_entry(e)
        if feats.empty:
            continue
        tids = feats["track_id"].to_numpy()
        s = booster.predict(to_model_matrix(feats, cols))
        order = tids[np.argsort(-s, kind="stable")]
        v = ndcg20(list(order), g)
        overall.append(v); by[intent].append(v); n += 1
        if LIMIT and n >= LIMIT:
            break

print(f"trace={TRACE.split('/')[-1]}")
print(f"model={MODEL}")
print(f"OVERALL NDCG@20: {np.mean(overall):.4f}  n={len(overall)}")
for it in ["refinement", "open_explore", "playlist_build", "pivot"]:
    if by[it]:
        print(f"  {it:15s} n={len(by[it]):5d}  NDCG@20={np.mean(by[it]):.4f}")
