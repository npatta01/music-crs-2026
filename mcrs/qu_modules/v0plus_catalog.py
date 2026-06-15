"""Catalog Protocol for the v0+ Resolver and Compiler.

This is the contract the Resolver and Compiler use to talk to the underlying
track catalog (metadata + precomputed embeddings). Production wires
`LanceDbCatalog` (`mcrs/qu_modules/v0plus_catalog_lance.py`), which opens the
same LanceDB table used for retrieval and builds per-track caches at init.
Tests use the `HFTalkPlayCatalog.from_rows(...)` synthetic-data fake
(`mcrs/qu_modules/v0plus_catalog_hf.py`) or the smaller `DictCatalog` fake
in `tests/v0plus_fakes.py`.

Keeping the contract narrow lets us swap catalog implementations (in-memory
dict for tests, LanceDB-backed for production) without touching Resolver /
Compiler code.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from mcrs.conversation_state.schema import (
        HardFilter,
    )


@runtime_checkable
class CompilerCatalog(Protocol):
    """All catalog lookups the v0+ Resolver and Compiler need."""

    # ----- name → id reverse lookups (Resolver fuzzy match) -----

    @property
    def artist_names(self) -> list[str]:
        """All known artist names. Resolver fuzzy-matches against this list."""
        ...

    @property
    def track_names(self) -> list[str]:
        """All known track names. Resolver fuzzy-matches against this list."""
        ...

    def artist_id_of_name(self, name: str) -> str | None:
        """Resolve an exact artist_name to its artist_id. Returns None if no match."""
        ...

    def track_id_of_name(self, name: str) -> str | None:
        """Resolve an exact track_name to its track_id. Returns None if no match."""
        ...

    # ----- track-side lookups (Resolver + Compiler) -----

    def artist_id_of(self, track_id: str) -> str | None:
        """Primary artist_id for the track, or None if the track has no artist record."""
        ...

    def album_id_of(self, track_id: str) -> str | None:
        """Primary album_id for the track, or None if the track has no album record.
        Used by post-fusion features (e.g. `exploration_policy=diversify_albums`)
        to demote tracks sharing an album with prior-played anchors."""
        ...

    def tracks_by_artist_id(self, artist_id: str) -> list[str]:
        """All track_ids attributed to this artist_id."""
        ...

    def tag_list(self, track_id: str) -> list[str]:
        """Genre / mood tags for the track (lowercase, deduped). Empty list if none."""
        ...

    def track_text(self, track_id: str) -> str:
        """Rich text representation for cross-encoder rerankers.

        Format: `"{artist} - {track} | {album} | tag1, tag2, ..."` (tag count capped).
        Empty string if the track is unknown. Used as the candidate-doc side of
        (query, doc) pairs scored by a cross-encoder.
        """
        ...

    def track_label(self, track_id: str) -> str:
        """Human-readable "artist - track" label for prompt rendering. Empty
        string if the track is unknown. Used by the extractor prompt's music
        turns so the labels in real conversations match the few-shot format
        the model was tuned on (mismatched label formats caused the model to
        hallucinate stringified row dumps as track_ids)."""
        ...

    # ----- embedding lookups (Compiler centroid mixing) -----

    def vector(self, track_id: str, vector_field: str) -> list[float] | None:
        """Precomputed vector for the given column, or None if missing for that
        track. `vector_field` is the LanceDB-safe column name
        (e.g. ``"metadata_qwen3_embedding_0_6b"``)."""
        ...

    def metadata_vector(self, track_id: str) -> list[float] | None:
        """Convenience wrapper for the metadata-qwen3 column. Equivalent to
        ``self.vector(track_id, "metadata_qwen3_embedding_0_6b")``. Kept for
        backwards-compat with the single-branch v0+ design."""
        ...

    def feature_rows(self) -> dict[str, dict]:
        """Track metadata rows for train/serve parity adapters.

        Returned rows are read-only from the caller's perspective. This avoids
        feature-serving code depending on private catalog internals.
        """
        ...

    # ----- catalog-wide ops (Compiler filters / backfill) -----

    def release_date_filter_mask(self, hf: "HardFilter") -> set[str]:
        """Return the set of track_ids passing the structured release_date filter.

        For op='<' includes tracks with release_date < hf.end.
        For op='>' includes tracks with release_date > hf.start.
        For op='between' includes tracks with hf.start <= release_date <= hf.end.
        Tracks with missing or unparseable release_date are excluded.
        """
        ...

    def release_year_of(self, track_id: str) -> int | None:
        """Release year as an int, or None when the track has no parseable date."""
        ...

    def all_track_ids(self) -> list[str]:
        """All track_ids in the catalog. Used for empty-filter and backfill paths."""
        ...

    def popularity_sorted_track_ids(self) -> list[str]:
        """All track_ids ordered by `popularity` desc. Used for backfill when
        post-filter retrieval pool is short of topk."""
        ...
