"""Semantic ID helpers for offline generative-retrieval experiments.

The functions here intentionally stay independent of the production retrieval
path. They let experiment scripts build hierarchical item codes from catalog
vectors and test whether those codes add ranking signal before wiring anything
into serving.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TypeAlias

import numpy as np
from scipy.cluster.vq import kmeans2

SemanticId: TypeAlias = tuple[int, ...]


def _normalise_rows(vectors: np.ndarray) -> np.ndarray:
    arr = np.nan_to_num(np.asarray(vectors, dtype=np.float32), copy=True)
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    np.divide(arr, norms, out=arr, where=norms > 0)
    return arr


def _stable_relabel(labels: np.ndarray, centroids: np.ndarray) -> np.ndarray:
    order = sorted(range(len(centroids)), key=lambda i: tuple(float(v) for v in centroids[i]))
    remap = {old: new for new, old in enumerate(order)}
    return np.asarray([remap[int(label)] for label in labels], dtype=np.int32)


def _cluster_labels(
    vectors: np.ndarray,
    k: int,
    *,
    iterations: int,
    rng: np.random.Generator,
) -> np.ndarray:
    n_rows = len(vectors)
    if n_rows == 0:
        return np.zeros(0, dtype=np.int32)
    unique_vectors, inverse = np.unique(vectors, axis=0, return_inverse=True)
    effective_k = min(max(1, int(k)), len(unique_vectors))
    if effective_k == 1:
        return np.zeros(n_rows, dtype=np.int32)

    centroids, labels = kmeans2(
        unique_vectors,
        effective_k,
        iter=iterations,
        minit="++",
        missing="warn",
        rng=rng,
    )
    unique_labels = _stable_relabel(labels, centroids)
    return unique_labels[inverse]


def build_hierarchical_semantic_ids(
    track_ids: Sequence[str],
    vectors: np.ndarray,
    *,
    level_sizes: Sequence[int] = (64, 16),
    iterations: int = 25,
    seed: int = 13,
) -> dict[str, SemanticId]:
    """Assign deterministic hierarchical semantic IDs to tracks.

    Each level clusters within the parent cluster from the previous level, so a
    two-level `(64, 16)` setup yields up to 1,024 leaf codes while preserving a
    coarser first prefix.
    """

    if not level_sizes:
        raise ValueError("level_sizes must contain at least one level")
    if len(track_ids) != len(vectors):
        raise ValueError("track_ids and vectors must have the same length")
    if len(set(track_ids)) != len(track_ids):
        raise ValueError("track_ids must be unique")

    arr = _normalise_rows(vectors)
    rng = np.random.default_rng(seed)
    codes = np.zeros((len(track_ids), len(level_sizes)), dtype=np.int32)
    parent_groups: list[np.ndarray] = [np.arange(len(track_ids), dtype=np.int32)]

    for level, branch_factor in enumerate(level_sizes):
        next_groups: list[np.ndarray] = []
        for group in parent_groups:
            labels = _cluster_labels(
                arr[group],
                int(branch_factor),
                iterations=iterations,
                rng=rng,
            )
            codes[group, level] = labels
            for label in sorted(set(int(v) for v in labels)):
                next_groups.append(group[labels == label])
        parent_groups = next_groups

    return {
        str(track_id): tuple(int(v) for v in codes[row_idx])
        for row_idx, track_id in enumerate(track_ids)
    }


def common_prefix_depth(left: SemanticId, right: SemanticId) -> int:
    depth = 0
    for a, b in zip(left, right):
        if a != b:
            break
        depth += 1
    return depth


def semantic_branch_ranks(
    base_order: Sequence[str],
    semantic_ids: dict[str, SemanticId],
    *,
    seed_topn: int,
    level: int,
) -> dict[str, int]:
    """Rank candidates that share semantic prefixes with top base candidates."""

    if level <= 0:
        raise ValueError("level must be positive")
    cluster_best_rank: dict[SemanticId, int] = {}
    for base_rank, track_id in enumerate(base_order[:seed_topn], start=1):
        code = semantic_ids.get(str(track_id))
        if code is None:
            continue
        cluster = code[:level]
        cluster_best_rank[cluster] = min(base_rank, cluster_best_rank.get(cluster, base_rank))

    ranked: list[tuple[int, int, str]] = []
    for base_rank, track_id in enumerate(base_order, start=1):
        code = semantic_ids.get(str(track_id))
        if code is None:
            continue
        cluster = code[:level]
        if cluster not in cluster_best_rank:
            continue
        ranked.append((cluster_best_rank[cluster], base_rank, str(track_id)))

    ranked.sort()
    return {track_id: rank for rank, (_, _, track_id) in enumerate(ranked, start=1)}


def rrf_score(
    *,
    base_rank: int,
    semantic_rank: int | None,
    semantic_weight: float,
    rrf_k: int = 60,
) -> float:
    score = 1.0 / (rrf_k + base_rank)
    if semantic_rank is not None:
        score += float(semantic_weight) / (rrf_k + semantic_rank)
    return score
