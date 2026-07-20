"""Hard-negative helpers for semantic-representation experiments."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class TurnTrainingExample:
    query_vector: np.ndarray
    positive_code: int
    negative_codes: np.ndarray


def _rank_order(base_ranks: np.ndarray) -> np.ndarray:
    ranks = np.nan_to_num(
        np.asarray(base_ranks, dtype=np.float32),
        nan=np.inf,
        posinf=np.inf,
        neginf=-np.inf,
    )
    return np.argsort(ranks, kind="mergesort")


def _unique_codes_by_rank(
    *,
    labels: np.ndarray,
    track_codes: np.ndarray,
    base_ranks: np.ndarray,
    max_codes: int,
    include_labels: bool,
) -> list[int]:
    out: list[int] = []
    seen: set[int] = set()
    positive_codes = {int(code) for code in track_codes[np.asarray(labels) > 0]}
    for idx in _rank_order(base_ranks):
        is_label = bool(labels[idx] > 0)
        if is_label != include_labels:
            continue
        code = int(track_codes[idx])
        if code < 0 or code in seen:
            continue
        if not include_labels and code in positive_codes:
            continue
        seen.add(code)
        out.append(code)
        if len(out) >= max_codes:
            break
    return out


def choose_hard_negatives(
    *,
    labels: np.ndarray,
    track_codes: np.ndarray,
    base_ranks: np.ndarray,
    max_negatives: int,
) -> np.ndarray:
    """Return unique non-label track codes ordered by strongest base rank."""

    labels = np.asarray(labels)
    track_codes = np.asarray(track_codes)
    if len(labels) != len(track_codes) or len(labels) != len(base_ranks):
        raise ValueError("labels, track_codes, and base_ranks must have the same length")
    if max_negatives <= 0:
        return np.zeros(0, dtype=np.int32)
    return np.asarray(
        _unique_codes_by_rank(
            labels=labels,
            track_codes=track_codes,
            base_ranks=base_ranks,
            max_codes=max_negatives,
            include_labels=False,
        ),
        dtype=np.int32,
    )


def _normalise(vector: np.ndarray) -> np.ndarray:
    arr = np.asarray(vector, dtype=np.float32)
    norm = float(np.linalg.norm(arr))
    if norm <= 0:
        return arr
    return arr / norm


def build_turn_example(
    *,
    item_vectors: np.ndarray,
    labels: np.ndarray,
    track_codes: np.ndarray,
    base_ranks: np.ndarray,
    context_topn: int,
    max_negatives: int,
) -> TurnTrainingExample | None:
    """Create one contrastive training example from a v10 candidate turn."""

    labels = np.asarray(labels)
    track_codes = np.asarray(track_codes)
    if len(labels) != len(track_codes) or len(labels) != len(base_ranks):
        raise ValueError("labels, track_codes, and base_ranks must have the same length")

    positives = _unique_codes_by_rank(
        labels=labels,
        track_codes=track_codes,
        base_ranks=base_ranks,
        max_codes=1,
        include_labels=True,
    )
    if not positives:
        return None
    positive_code = int(positives[0])

    negative_codes = choose_hard_negatives(
        labels=labels,
        track_codes=track_codes,
        base_ranks=base_ranks,
        max_negatives=max_negatives,
    )
    if len(negative_codes) == 0:
        return None

    context_codes = _unique_codes_by_rank(
        labels=labels,
        track_codes=track_codes,
        base_ranks=base_ranks,
        max_codes=max(1, int(context_topn)),
        include_labels=False,
    )
    vectors = [
        item_vectors[code]
        for code in context_codes
        if 0 <= code < len(item_vectors) and np.isfinite(item_vectors[code]).all()
    ]
    if not vectors:
        return None

    query_vector = _normalise(np.mean(np.vstack(vectors), axis=0))
    return TurnTrainingExample(
        query_vector=query_vector.astype(np.float32, copy=False),
        positive_code=positive_code,
        negative_codes=negative_codes.astype(np.int32, copy=False),
    )


def session_split(session_id: str) -> str:
    """Deterministic 62.5/18.75/18.75 session split for diagnostics."""

    first_byte = hashlib.sha1(str(session_id).encode("utf-8")).digest()[0]
    if first_byte < 160:
        return "train"
    if first_byte < 208:
        return "tune"
    return "test"
