
"""Common retrieval evaluation metrics.
For more details regarding these metrics, see:
https://en.wikipedia.org/wiki/Evaluation_measures_(information_retrieval)#Offline_metrics
"""

from collections.abc import Collection
from typing import Any, Optional

import numpy as np
from scipy import linalg


def get_ndcg(gold, preds, k: int) -> float:
    """Returns the normalized discounted cumulative gain at k.
    Args:
        gold: Collection of ground truth items
        preds: Sequence of predicted items
        k: Number of predictions to consider
    Returns:
        float: nDCG score between 0 and 1
    """
    preds = preds[:k]
    # Calculate DCG
    dcg = 0.0
    for i, pred in enumerate(preds, start=1):
        rel = 1 if pred in gold else 0
        dcg += rel / np.log2(i + 1)
    n_rel = min(len(gold), k)
    idcg = sum(1 / np.log2(i + 1) for i in range(1, n_rel + 1))

    if idcg == 0:
        return 0.0
    return dcg / idcg


def get_hit(gold, preds, k: int) -> int:
    """Returns 1 if any of the top-k predictions are in the gold set, else 0."""
    preds = preds[:k]
    return 1 if len(set(gold).intersection(preds)) > 0 else 0


def get_reciprocal_rank(gold, preds, k: Optional[int] = None) -> float:
    """Returns the reciprocal rank at k; 0 if no relevants items are found."""
    if k is not None:
        preds = preds[:k]
    # Handle empty predictions
    if not preds:
        return 0.0

    # Find position of gold in predictions (1-based rank)
    try:
        rank = preds.index(gold) + 1
        return 1.0 / rank
    except ValueError:
        return 0.0  # Gold not found in predictions


def get_precision(gold, preds, k: int) -> float:
    """Returns the precision at k."""
    preds = preds[:k]
    num_hit = len(set(gold).intersection(preds))
    return num_hit / len(preds)


def get_recall(gold, preds, k: int) -> float:
    """Returns the recall at k."""
    preds = preds[:k]
    num_hit = len(set(gold).intersection(preds))
    return num_hit / len(gold)


def get_average_precision(gold, preds, k: int) -> float:
    """Returns the average precision at k."""
    preds = preds[:k]
    num_hit = 0
    total_precision = 0.0
    for i, pred in enumerate(preds, start=1):
        if pred in gold:
            num_hit += 1
            total_precision += num_hit / i
    return total_precision / min(len(gold), len(preds))


def _has_duplicates(values: Collection[Any]):
    """Returns True if the list has duplicates, else False."""
    return len(values) > len(set(values))


_STANDARD_METRIC_MAP = {
    "ndcg": get_ndcg,
    "hit": get_hit,
    "recall": get_recall,
    # "map": get_average_precision,
    # "precision": get_precision,
}
STANDARD_METRICS = sorted(_STANDARD_METRIC_MAP.keys())


def get_rank(gold, preds) -> "int | None":
    """Returns the 1-based rank of the first gold item in preds, or None."""
    gold_set = set(gold) if not isinstance(gold, set) else gold
    for i, p in enumerate(preds, start=1):
        if p in gold_set:
            return i
    return None

def compute_recsys_metrics(
    preds,
    gold,
    k_values,
    metrics=STANDARD_METRICS,
) -> dict[str, float]:
    """Alias for compute_metrics; used by eval_devset / eval_blindset."""
    return compute_metrics(preds, gold, k_values, metrics)


def compute_metrics(
    preds,
    gold,
    k_values,
    metrics=STANDARD_METRICS,
) -> dict[str, float]:
    """Computes retrieval metrics for 'preds' and 'golds' for 'k_values'.

    Args:
        preds: The list of retrieved items for the example.
        gold: The list of gold (i.e. relevant) items for the example.
        k_values: The list of k values to compute metrics for (e.g. recall@k).
        metrics: The list of metrics to compute.g. recall@k).

    Returns:
        A dictionary of retrieval metrics.
    """
    if _has_duplicates(preds):
        raise ValueError("Predictions should be unique. Duplicates detected.")
    if _has_duplicates(gold):
        raise ValueError("Gold item list should be unique. Duplicates detected.")
    metric_vals = {}
    for metric in metrics:
        metric_fn = _STANDARD_METRIC_MAP[metric]
        for k in k_values:
            metric_vals[f"{metric}@{k}"] = metric_fn(gold=gold, preds=preds, k=k)
    return metric_vals
