"""Offline↔online feature parity on real Phase-B turns (cap-500 both sides).

Offline = the already-built cap-500 features.parquet. Online = TurnReranker.features_for_entry
on the same trace entries (uses cap-500 from the model card). Compares every numeric feature,
with focus on block H. Both sides cap-500, so set-dependent features line up.
"""
import json
import numpy as np
import pandas as pd

from mcrs.qu_modules.v0plus_catalog_lance import LanceDbCatalog
from mcrs.rerank.online import TurnReranker
from mcrs.rerank.features import catalog_metadata_frame, CATEGORICAL_FEATURES

TRACE = "exp/inference/devset/v0plus_compiler_all_retrievers_devset_phaseB_trace.jsonl"
MODEL = "exp/rerank/devset_phaseB/model_single/model.txt"
FEATS = "exp/rerank/devset_phaseB/features.parquet"
N = 40

cat = LanceDbCatalog(db_uri="cache/lancedb_emb", table_name="music_track_catalog")
meta = catalog_metadata_frame(cat)
rr = TurnReranker.from_path(MODEL, cat, meta=meta)
print("serve max_pool_depth:", rr.max_pool_depth)

# First N trace entries.
entries = []
with open(TRACE) as fh:
    for line in fh:
        entries.append(json.loads(line))
        if len(entries) >= N:
            break
keys = {(e["session_id"], int(e["turn_number"])) for e in entries}

# Online features for those turns.
online = pd.concat([rr.features_for_entry(e) for e in entries], ignore_index=True)
online = online[online.apply(lambda r: (r["session_id"], int(r["turn_number"])) in keys, axis=1)]

# Offline features for those turns (filter the full parquet).
off = pd.read_parquet(FEATS)
off = off[off.apply(lambda r: (r["session_id"], int(r["turn_number"])) in keys, axis=1)].copy()

feat_cols = [c for c in online.columns
             if c not in {"session_id", "turn_number", "track_id", "label"}
             and c not in CATEGORICAL_FEATURES]
key = ["session_id", "turn_number", "track_id"]
m = off.merge(online, on=key, suffixes=("_off", "_on"))
print(f"online rows={len(online)} offline(subset)={len(off)} merged={len(m)}")

worst = {}
for c in feat_cols:
    a = pd.to_numeric(m[f"{c}_off"], errors="coerce").to_numpy(float)
    b = pd.to_numeric(m[f"{c}_on"], errors="coerce").to_numpy(float)
    d = np.where(np.isnan(a) & np.isnan(b), 0.0, np.abs(a - b))
    worst[c] = float(np.nanmax(d, initial=0.0))

hcols = {c: v for c, v in worst.items() if c.startswith("h__xcos_")}
top = dict(sorted(worst.items(), key=lambda kv: -kv[1])[:8])
print("\nblock H max abs diff:")
for c, v in hcols.items():
    print(f"  {c:28s} {v:.2e}")
print("\ntop-8 worst features overall:")
for c, v in top.items():
    print(f"  {c:34s} {v:.2e}")
print(f"\nMAX ABS DIFF (all features): {max(worst.values()):.2e}  -> parity {'OK' if max(worst.values())<1e-4 else 'FAIL'}")
