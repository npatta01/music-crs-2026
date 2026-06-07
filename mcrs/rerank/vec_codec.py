"""Compact, lossless-at-float32 codec for per-branch query vectors in the trace.

The v0+ compiler captures the actual query/centroid vector each retrieval branch searched
with (see ``CompilerConfig.capture_branch_query_vectors``). The dense cross-scoring features
(block H in ``mcrs.rerank.features``) cosine every union candidate against these vectors, so
they must round-trip through the JSON(L) trace identically to what the online compiler holds
in memory.

We serialize each vector as base64-encoded little-endian float32. float32 is the key: the
online path casts query vectors to float32 before scoring, and the trace stores float32, so
offline (decoded float32) and online (cast float32) see byte-identical inputs — no train/serve
skew. base64 keeps the trace ~3x smaller than JSON float arrays.
"""

from __future__ import annotations

import base64
from typing import Any

import numpy as np


def encode_vector(vec: Any) -> str:
    """One vector -> base64 little-endian float32 string."""
    arr = np.asarray(vec, dtype="<f4").ravel()
    return base64.b64encode(arr.tobytes()).decode("ascii")


def decode_vector(s: str) -> np.ndarray:
    """base64 little-endian float32 string -> float32 ndarray."""
    return np.frombuffer(base64.b64decode(s), dtype="<f4")


def encode_branch_vectors(vectors: dict[str, Any]) -> dict[str, str]:
    """{branch_name -> vector} -> {branch_name -> base64 float32}. Skips empty/None vectors."""
    out: dict[str, str] = {}
    for name, vec in (vectors or {}).items():
        if vec is None:
            continue
        arr = np.asarray(vec, dtype="<f4").ravel()
        if arr.size == 0:
            continue
        out[name] = base64.b64encode(arr.tobytes()).decode("ascii")
    return out


def decode_branch_vectors(encoded: dict[str, str] | None) -> dict[str, np.ndarray]:
    """{branch_name -> base64 float32} -> {branch_name -> float32 ndarray}.

    Tolerates values that are already plain float lists (e.g. an online entry that passed
    vectors through without base64) so the online and offline paths can share this decoder.
    """
    out: dict[str, np.ndarray] = {}
    for name, val in (encoded or {}).items():
        if val is None:
            continue
        if isinstance(val, str):
            arr = np.frombuffer(base64.b64decode(val), dtype="<f4")
        else:
            arr = np.asarray(val, dtype="<f4").ravel()
        if arr.size:
            out[name] = arr
    return out
