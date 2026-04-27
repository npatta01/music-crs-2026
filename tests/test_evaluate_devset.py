import math
import sys
from pathlib import Path

import pandas as pd
import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evaluator"))

from evaluate_devset import evaluate  # noqa: E402


def _prediction_row(session_id: str, turn_number: int, gt_id: str, rank: int, depth: int):
    preds = [f"{session_id}-track-{i}" for i in range(depth)]
    preds[rank - 1] = gt_id
    return {
        "session_id": session_id,
        "turn_number": turn_number,
        "predicted_track_ids": preds,
        "predicted_response": f"response for {session_id}",
    }


def test_evaluate_rejects_prediction_pools_shallower_than_required_diagnostics():
    df_predictions = pd.DataFrame([
        _prediction_row("s1", 1, "gt-1", rank=80, depth=100),
    ])
    df_ground_truth = pd.DataFrame([
        {"session_id": "s1", "turn_number": 1, "ground_truth_track_id": "gt-1"},
    ])

    with pytest.raises(ValueError, match="top-1000 diagnostics"):
        evaluate(df_predictions, df_ground_truth)


def test_evaluate_reports_deep_cutoff_metrics_when_prediction_pool_is_large_enough():
    df_predictions = pd.DataFrame([
        _prediction_row("s1", 1, "gt-1", rank=150, depth=1000),
        _prediction_row("s2", 1, "gt-2", rank=700, depth=1000),
    ])
    df_ground_truth = pd.DataFrame([
        {"session_id": "s1", "turn_number": 1, "ground_truth_track_id": "gt-1"},
        {"session_id": "s2", "turn_number": 1, "ground_truth_track_id": "gt-2"},
    ])

    _, metrics = evaluate(df_predictions, df_ground_truth)

    assert metrics["max_pool_depth"] == 1000
    assert metrics["hit@200"] == pytest.approx(0.5)
    assert metrics["hit@500"] == pytest.approx(0.5)
    assert metrics["hit@1000"] == pytest.approx(1.0)
    assert metrics["pct_gt_not_in_top200"] == pytest.approx(0.5)
    assert metrics["pct_gt_not_in_top500"] == pytest.approx(0.5)
    assert metrics["pct_gt_not_in_top1000"] == pytest.approx(0.0)
    assert metrics["mrr@200"] == pytest.approx((1 / 150) / 2)
    assert metrics["mrr@500"] == pytest.approx((1 / 150) / 2)
    assert metrics["mrr@1000"] == pytest.approx((1 / 150 + 1 / 700) / 2)
    assert metrics["mrr"] == pytest.approx((1 / 150 + 1 / 700) / 2)
    assert metrics["ndcg@1000"] == pytest.approx(
        (1 / math.log2(151) + 1 / math.log2(701)) / 2
    )
