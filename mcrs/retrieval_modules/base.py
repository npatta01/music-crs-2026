"""Shared Retriever Protocol for v0+ compiler-facing backends.

Every backend that the v0+ compiler talks to implements this Protocol. Backends
that pre-date the v0+ work (e.g., the deprecated Milvus retriever) keep their
own legacy APIs untouched — only new code targets this interface.

Design points:

- `field` is always declared. There is no "default field" magic — backends
  raise ValueError if asked for an unsupported field.
- BM25 takes a list of `FieldQuery` clauses. Backends with native multi-field
  BM25 (Tantivy, Milvus 2.4+) execute it in one call; others simulate via
  per-field calls + internal weighted RRF. Either way the caller sees a single
  ranked list of (track_id, score) pairs.
- Scores are always "higher = better". Distance-based backends flip
  internally (cosine -> 1 - d; L2 -> 1 / (1 + d); inner product -> as-is).
  This means the compiler never has to remember which backend uses which
  convention; for RRF, only rank order matters anyway.
- The Protocol exposes `supported_text_fields` and `supported_vector_fields`
  so the compiler can introspect at construction time.

The compiler issues exactly two retrieval calls per turn: one `search` (with
N field clauses) and one `search_embedding`. Cross-modal fusion of those two
ranked lists is the compiler's job — not the retriever's.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class FieldQuery:
    """One field-targeted BM25 clause.

    Attributes:
        field: indexed text field name (must be in the backend's
            `supported_text_fields`).
        query: query string. Whitespace-only / empty queries are dropped by
            backends before any backend call is issued.
        boost: positive multiplier on this clause's contribution to the
            backend-internal fusion when more than one clause is present.
            Defaults to 1.0.
    """

    field: str
    query: str
    boost: float = 1.0

    def __post_init__(self) -> None:
        if not isinstance(self.field, str) or not self.field.strip():
            raise ValueError("FieldQuery.field must be a non-empty string")
        if not isinstance(self.query, str):
            raise ValueError("FieldQuery.query must be a string")
        if not isinstance(self.boost, (int, float)) or self.boost <= 0:
            raise ValueError(f"FieldQuery.boost must be positive, got {self.boost!r}")


@runtime_checkable
class Retriever(Protocol):
    """Shared interface for v0+ compiler-facing retrievers."""

    @property
    def supported_text_fields(self) -> frozenset[str]:
        """Text fields this backend can BM25/FTS over."""
        ...

    @property
    def supported_vector_fields(self) -> frozenset[str]:
        """Vector columns this backend can ANN over."""
        ...

    def search(
        self,
        clauses: list[FieldQuery],
        *,
        topk: int = 1000,
    ) -> list[tuple[str, float]]:
        """BM25/FTS retrieval over one or more field-targeted clauses.

        Returns a ranked list of (track_id, score) pairs. Higher score = more
        relevant. The backend decides how to combine multiple clauses
        internally (native multi-field where supported, internal weighted RRF
        as a fallback).

        Raises ValueError if any clause.field is not in
        `supported_text_fields`. Empty clauses (whitespace-only query) are
        skipped; a fully-empty or all-empty clause list returns [].
        """
        ...

    def search_embedding(
        self,
        query_vector: list[float],
        *,
        vector_field: str,
        topk: int = 1000,
        distance_type: str = "cosine",
        filter_missing: bool = True,
    ) -> list[tuple[str, float]]:
        """Dense ANN against one vector column with a caller-supplied query
        vector (so the compiler can do centroid mixing before calling).

        Returns a ranked list of (track_id, similarity) pairs. Higher = more
        similar — backend converts native distances to similarities per
        `distance_type` (cosine -> 1 - d; L2 -> 1 / (1 + d); inner product
        passes through).

        Raises ValueError if `vector_field` is not in
        `supported_vector_fields`.
        """
        ...
