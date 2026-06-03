"""Evaluate the reranker's OOF ranking against the RRF baseline using the official metric.

Reuses ``evaluator/metrics/metrics_recsys.py`` so the offline number is literally the
leaderboard number. For each (session, turn) group it turns the OOF candidate scores into a
top-20 ranked list and compares against the existing RRF ``fused`` ordering captured by
``build_dataset.py`` -- on the *same* turns, so the delta is attributable to ordering alone.

Groups whose golden track never entered the union are kept (they score 0 for both rankers),
giving the honest, coverage-bounded number rather than a recall-inflated one.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from evaluator.metrics.metrics_recsys import get_hit, get_ndcg, get_reciprocal_rank

DEFAULT_GROUND_TRUTH = "evaluator/exp/ground_truth/devset.json"
HEADLINE_K = 20


def load_ground_truth(path: str | Path) -> dict[tuple[str, int], str]:
    with open(path) as fh:
        rows = json.load(fh)
    return {(r["session_id"], int(r["turn_number"])): r["ground_truth_track_id"] for r in rows}


def load_rrf_orderings(groups_path: str | Path) -> dict[tuple[str, int], list[str]]:
    out: dict[tuple[str, int], list[str]] = {}
    for line in open(groups_path):
        g = json.loads(line)
        out[(g["session_id"], int(g["turn_number"]))] = g.get("rrf_fused_topk", [])
    return out


def _metrics_for_ranking(gold: str, preds: list[str]) -> dict[str, float]:
    return {
        "ndcg@20": get_ndcg([gold], preds, 20),
        "ndcg@1": get_ndcg([gold], preds, 1),
        "mrr@20": get_reciprocal_rank(gold, preds, 20),
        "hit@20": float(get_hit([gold], preds, 20)),
    }


def reranker_top_preds(oof: pd.DataFrame, top_k: int = HEADLINE_K) -> dict[tuple[str, int], list[str]]:
    """Per-(session,turn) top-k track_ids ordered by descending reranker score."""
    ordered = oof.sort_values(["session_id", "turn_number", "score"],
                              ascending=[True, True, False], kind="stable")
    preds: dict[tuple[str, int], list[str]] = {}
    for (sid, turn), sub in ordered.groupby(["session_id", "turn_number"], sort=False):
        preds[(sid, turn)] = sub["track_id"].head(top_k).tolist()
    return preds


def evaluate(
    oof_path: str | Path,
    groups_path: str | Path,
    ground_truth_path: str | Path = DEFAULT_GROUND_TRUTH,
) -> dict[str, Any]:
    oof = pd.read_parquet(oof_path)
    gt = load_ground_truth(ground_truth_path)
    rrf = load_rrf_orderings(groups_path)

    rr_preds = reranker_top_preds(oof, HEADLINE_K)
    keys = sorted(rr_preds.keys())

    rr_rows, rrf_rows = [], []
    n_no_gold = 0
    for key in keys:
        gold = gt.get(key)
        if gold is None:
            continue
        if key not in rrf:
            n_no_gold += 1
        rr_rows.append(_metrics_for_ranking(gold, rr_preds[key]))
        rrf_rows.append(_metrics_for_ranking(gold, rrf.get(key, [])))

    rr_mean = pd.DataFrame(rr_rows).mean().to_dict()
    rrf_mean = pd.DataFrame(rrf_rows).mean().to_dict()
    delta = {m: rr_mean[m] - rrf_mean[m] for m in rr_mean}

    return {
        "n_groups": len(rr_rows),
        "reranker": rr_mean,
        "rrf_baseline": rrf_mean,
        "delta_reranker_minus_rrf": delta,
        "primary_ndcg@20": {
            "reranker": rr_mean.get("ndcg@20"),
            "rrf": rrf_mean.get("ndcg@20"),
            "delta": delta.get("ndcg@20"),
            "beats_baseline": delta.get("ndcg@20", 0.0) > 0,
        },
        "groups_missing_rrf_ordering": n_no_gold,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Evaluate reranker OOF vs RRF baseline (metrics_recsys).")
    p.add_argument("--oof", default="exp/rerank/model/oof.parquet")
    p.add_argument("--groups", default="exp/rerank/dataset/groups.jsonl")
    p.add_argument("--ground-truth", default=DEFAULT_GROUND_TRUTH)
    p.add_argument("--out", default=None, help="Optional JSON path to write the report.")
    args = p.parse_args(argv)

    report = evaluate(args.oof, args.groups, args.ground_truth)
    text = json.dumps(report, indent=2)
    print(text)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        with open(args.out, "w") as fh:
            fh.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
