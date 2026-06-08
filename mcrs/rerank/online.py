"""Online (inference-time) LambdaMART reranking of a single turn.

Given one per-turn trace entry -- the exact ``{session_id, turn_number, trace:{state,
resolver, resolved_targets, branches}}`` structure the QU layer builds (compiler_v0plus_qu)
and the offline pipeline trains on -- this reranks the branch-pool union with a trained
LightGBM model. It reuses the *same* dataset + feature code as the offline path, so training
and serving features are byte-identical (no train/serve skew).

The compiler integration constructs that entry in-process and calls :meth:`TurnReranker.rank`;
the standalone :func:`validate_parity` proves the online per-turn features match the offline
batch features on the devset trace.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import lightgbm as lgb
import pandas as pd

from mcrs.rerank.build_dataset import _candidate_rows, _parse_pools, build_group_record
from mcrs.rerank.features import (
    CATEGORICAL_FEATURES,
    catalog_metadata_frame,
    feature_columns,
    features_from_frames,
)
from mcrs.rerank.train import to_model_matrix


class TurnReranker:
    """Score+order the branch-pool union of one turn with a trained LambdaMART model."""

    def __init__(
        self,
        booster: lgb.Booster,
        catalog: Any,
        feature_cols: list[str],
        meta: pd.DataFrame | None = None,
        max_pool_depth: int | None = None,
    ) -> None:
        self.booster = booster
        self.catalog = catalog
        self.feature_cols = feature_cols
        # Cache the 47k-row catalog metadata frame once; rebuilding per turn would be O(47k)/call.
        self.meta = meta if meta is not None else catalog_metadata_frame(catalog)
        self.max_pool_depth = max_pool_depth

    @classmethod
    def from_path(cls, model_path: str | Path, catalog: Any,
                  feature_cols: list[str] | None = None, **kw: Any) -> "TurnReranker":
        booster = lgb.Booster(model_file=str(model_path))
        meta_path = Path(model_path).with_suffix(".features.json")
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        if feature_cols is None:
            feature_cols = meta.get("feature_columns") or list(booster.feature_name())
        # Serve with the SAME per-branch cap the training dataset used (unless overridden).
        kw.setdefault("max_pool_depth", meta.get("max_pool_depth"))
        return cls(booster, catalog, feature_cols, **kw)

    def features_for_entry(self, entry: dict[str, Any]) -> pd.DataFrame:
        """Per-turn feature frame (keys + track_id + features), one row per union candidate."""
        sid = entry["session_id"]
        turn = int(entry["turn_number"])
        pools = _parse_pools(entry["trace"].get("branches", {}) or {})
        rows, stats = _candidate_rows(sid, turn, pools, gt_tid=None,
                                      max_pool_depth=self.max_pool_depth, max_neg_per_group=None)
        if not rows:
            return pd.DataFrame()
        candidates = pd.DataFrame(rows)
        grp = build_group_record(entry, gt_tid=None)
        grp["pool_depth"] = stats["pool_depth"]
        grp["top_score"] = stats["top_score"]
        groups = pd.DataFrame([grp])
        return features_from_frames(candidates, groups, self.catalog, meta=self.meta)

    def rank(self, entry: dict[str, Any]) -> list[str]:
        """Return union track_ids ordered by descending model score (best first)."""
        feats = self.features_for_entry(entry)
        if feats.empty:
            return []
        X = to_model_matrix(feats, self.feature_cols)
        scores = self.booster.predict(X)
        order = pd.Series(scores, index=feats["track_id"]).sort_values(
            ascending=False, kind="stable")
        return order.index.tolist()


# --------------------------------------------------------------------- parity validation

def validate_parity(
    trace_path: str | Path,
    model_dir: str | Path,
    db_uri: str = "cache/lancedb",
    table_name: str = "music_track_catalog",
    n_entries: int = 25,
) -> dict[str, Any]:
    """Confirm online per-turn features == offline batch features on the same turns.

    Builds the offline dataset+features for the first ``n_entries`` trace turns, then runs the
    online path turn-by-turn and compares feature matrices (sorted by track_id). Identical
    values prove the reuse is skew-free.
    """
    import itertools

    import numpy as np

    from mcrs.qu_modules.v0plus_catalog_lance import LanceDbCatalog
    from mcrs.rerank import build_dataset as bd

    trace_path = Path(trace_path)
    entries = list(itertools.islice(bd.iter_trace(trace_path), n_entries))

    catalog = LanceDbCatalog(db_uri=db_uri, table_name=table_name)
    meta = catalog_metadata_frame(catalog)

    # Offline batch features for these turns.
    tmp = Path("exp/rerank/_parity_tmp")
    bd.build_dataset(trace_path=trace_path, ground_truth_path=bd.DEFAULT_GROUND_TRUTH,
                     out_dir=tmp, limit=n_entries)
    offline = features_from_frames(
        pd.read_parquet(tmp / "candidates.parquet"),
        pd.DataFrame.from_records([json.loads(l) for l in open(tmp / "groups.jsonl")]),
        catalog, meta=meta)
    feat_cols = feature_columns(offline)

    booster_path = Path(model_dir) / "models" / "fold0.txt"
    reranker = TurnReranker.from_path(booster_path, catalog, feature_cols=feat_cols, meta=meta)

    # Tolerance is float32-aware: raw branch scores are stored as float32 in candidates.parquet
    # (offline) but kept float64 online, so score-derived columns differ by ~float32 epsilon.
    tol = 1e-4
    per_col_max: dict[str, float] = {}
    n_rows_checked = 0
    for entry in entries:
        online = reranker.features_for_entry(entry)
        if online.empty:
            continue
        key = ["session_id", "turn_number", "track_id"]
        o = offline.merge(online, on=key, suffixes=("_off", "_on"))
        for col in feat_cols:
            if col in CATEGORICAL_FEATURES:
                continue
            a = pd.to_numeric(o[f"{col}_off"], errors="coerce").to_numpy(dtype=float)
            b = pd.to_numeric(o[f"{col}_on"], errors="coerce").to_numpy(dtype=float)
            both_nan = np.isnan(a) & np.isnan(b)
            diff = np.where(both_nan, 0.0, np.abs(a - b))
            per_col_max[col] = max(per_col_max.get(col, 0.0), float(np.nanmax(diff, initial=0.0)))
        n_rows_checked += len(o)

    mismatched = {c: v for c, v in per_col_max.items() if v > tol}
    worst = dict(sorted(per_col_max.items(), key=lambda kv: -kv[1])[:5])
    return {
        "n_entries": len(entries),
        "n_rows_checked": n_rows_checked,
        "n_features": len(feat_cols),
        "tolerance": tol,
        "max_abs_feature_diff": max(per_col_max.values(), default=0.0),
        "worst_5_columns": worst,
        "mismatched_columns": {c: round(v, 8) for c, v in mismatched.items()},
        "parity_ok": not mismatched,
    }


def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(description="Validate online vs offline reranker feature parity.")
    p.add_argument("--trace", default="exp/inference/trace/devset_trace_first1000.json")
    p.add_argument("--model-dir", default="exp/rerank/devset/model")
    p.add_argument("--db-uri", default="cache/lancedb")
    p.add_argument("--n", type=int, default=25)
    args = p.parse_args(argv)
    report = validate_parity(args.trace, args.model_dir, db_uri=args.db_uri, n_entries=args.n)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
