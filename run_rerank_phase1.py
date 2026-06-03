"""Phase-1 orchestrator for the v0+ LambdaMART reranker (GH #93).

Runs the full pipeline end-to-end on a branch trace:

    build_dataset -> features -> train (session CV) -> evaluate (vs RRF) -> interpret (gate)

and writes a single ``phase1_report.json`` with the headline NDCG@20 comparison and the
popularity-prior acceptance gate. Stages can be skipped to iterate quickly:

    # quick smoke on the 1000-turn sample
    python run_rerank_phase1.py --trace exp/inference/trace/devset_trace_first1000.json \
        --out-root exp/rerank/smoke

    # full devset gate (cap the negative union so it fits in memory; golden always kept)
    python run_rerank_phase1.py --max-pool-depth 250 --out-root exp/rerank/devset
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from mcrs.rerank import build_dataset as bd
from mcrs.rerank import evaluate as ev
from mcrs.rerank import features as ft
from mcrs.rerank import interpret as it
from mcrs.rerank import train as tr


def _catalog(db_uri: str, table_name: str):
    from mcrs.qu_modules.v0plus_catalog_lance import LanceDbCatalog
    eager = tuple(ft.G_MODALITIES.values())
    return LanceDbCatalog(db_uri=db_uri, table_name=table_name, eager_vector_fields=eager)


def run(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.out_root)
    dataset_dir = root / "dataset"
    model_dir = root / "model"
    root.mkdir(parents=True, exist_ok=True)
    timings: dict[str, float] = {}

    if not args.skip_build:
        t = time.time()
        build_summary = bd.build_dataset(
            trace_path=args.trace, ground_truth_path=args.ground_truth,
            out_dir=dataset_dir, limit=args.limit,
            max_pool_depth=args.max_pool_depth, max_neg_per_group=args.max_neg_per_group)
        timings["build"] = time.time() - t
        print(f"[build] {build_summary['n_candidate_rows']:,} rows, "
              f"gt_in_union_rate={build_summary['gt_in_union_rate']}")

    features_path = dataset_dir / "features.parquet"
    if not args.skip_features:
        t = time.time()
        import pandas as pd
        catalog = _catalog(args.db_uri, args.table_name)
        frame = ft.build_features(dataset_dir, catalog)
        frame.to_parquet(features_path, index=False)
        with open(dataset_dir / "features.meta.json", "w") as fh:
            json.dump(ft.feature_meta(frame), fh, indent=2)
        timings["features"] = time.time() - t
        print(f"[features] {len(frame):,} rows x {ft.feature_meta(frame)['n_features']} features")
        del frame
        import gc
        gc.collect()

    if not args.skip_train:
        import pandas as pd
        t = time.time()
        frame = pd.read_parquet(features_path)
        train_summary = tr.train_cv(frame, model_dir, n_splits=args.n_splits)
        timings["train"] = time.time() - t
        print(f"[train] mean inner-val ndcg@20={train_summary['mean_inner_val_ndcg@20']:.4f}")
        del frame

    eval_report = ev.evaluate(model_dir / "oof.parquet", dataset_dir / "groups.jsonl",
                              ground_truth_path=args.ground_truth)
    interp_report = it.interpret(model_dir, model_dir, features_path,
                                 pop_share_threshold=args.pop_share_threshold,
                                 run_shap=not args.no_shap)

    report = {
        "out_root": str(root),
        "config": {
            "trace": args.trace, "max_pool_depth": args.max_pool_depth,
            "max_neg_per_group": args.max_neg_per_group, "n_splits": args.n_splits,
        },
        "timings_sec": timings,
        "evaluation": eval_report,
        "acceptance_gate": interp_report["acceptance_gate"],
        "phase1_verdict": {
            "ndcg@20_reranker": eval_report["primary_ndcg@20"]["reranker"],
            "ndcg@20_rrf": eval_report["primary_ndcg@20"]["rrf"],
            "ndcg@20_delta": eval_report["primary_ndcg@20"]["delta"],
            "beats_rrf": eval_report["primary_ndcg@20"]["beats_baseline"],
            "gate_passes": interp_report["acceptance_gate"]["passes_intent_conditioned_check"],
        },
    }
    with open(root / "phase1_report.json", "w") as fh:
        json.dump(report, fh, indent=2)
    print("\n=== PHASE 1 VERDICT ===")
    print(json.dumps(report["phase1_verdict"], indent=2))
    return report


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run the Phase-1 reranker pipeline end-to-end.")
    p.add_argument("--trace", default=bd.DEFAULT_TRACE)
    p.add_argument("--ground-truth", default=bd.DEFAULT_GROUND_TRUTH)
    p.add_argument("--out-root", default="exp/rerank/devset")
    p.add_argument("--db-uri", default="cache/lancedb")
    p.add_argument("--table-name", default="music_track_catalog")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--max-pool-depth", type=int, default=None)
    p.add_argument("--max-neg-per-group", type=int, default=None)
    p.add_argument("--n-splits", type=int, default=5)
    p.add_argument("--pop-share-threshold", type=float, default=0.5)
    p.add_argument("--no-shap", action="store_true")
    p.add_argument("--skip-build", action="store_true")
    p.add_argument("--skip-features", action="store_true")
    p.add_argument("--skip-train", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    run(build_parser().parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
