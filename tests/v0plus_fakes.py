"""In-memory fakes for the v0+ Catalog and Retriever Protocols.

Used by `test_v0plus_resolver.py` and `test_v0plus_compiler.py`. Kept here
(not in `mcrs/`) so production code can't accidentally import them.

The fakes are intentionally narrow — only the catalog/retriever surface
the Resolver and Compiler actually call. If a test fails because the fake
is missing a method, the test should be updated to a richer fake, not the
production Protocol relaxed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from mcrs.retrieval_modules.base import FieldQuery


# ----------------------------------------------------------------------
# Embedding client fake
# ----------------------------------------------------------------------


@dataclass
class FakeEmbeddingClient:
    """Implements EmbeddingClient with a fixed vector. Tests assert what the
    compiler does WITH the vector, not the vector's contents."""

    vector: list[float] = field(default_factory=lambda: [0.5, 0.5, 0.5])
    calls: list[list[str]] = field(default_factory=list)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [list(self.vector) for _ in texts]


# ----------------------------------------------------------------------
# Catalog fake
# ----------------------------------------------------------------------


@dataclass
class DictCatalog:
    """In-memory catalog backed by plain dicts. Implements CompilerCatalog.

    Construct with track-level data; the fake derives name->id reverse maps
    and the popularity sort lazily.
    """

    tracks: dict[str, dict] = field(default_factory=dict)
    """track_id -> dict with keys:
       artist_id, artist_name, track_name, album_id, album_name,
       tag_list, popularity, release_date, metadata_vector
    """

    def __post_init__(self) -> None:
        self._artist_name_to_id: dict[str, str] = {}
        self._track_name_to_id: dict[str, str] = {}
        self._tracks_by_artist: dict[str, list[str]] = {}
        for tid, meta in self.tracks.items():
            if meta.get("artist_name") and meta.get("artist_id"):
                self._artist_name_to_id[meta["artist_name"]] = meta["artist_id"]
                self._tracks_by_artist.setdefault(meta["artist_id"], []).append(tid)
            if meta.get("track_name"):
                self._track_name_to_id[meta["track_name"]] = tid

    # ----- Resolver-facing -----

    @property
    def artist_names(self) -> list[str]:
        return list(self._artist_name_to_id.keys())

    @property
    def track_names(self) -> list[str]:
        return list(self._track_name_to_id.keys())

    def artist_id_of_name(self, name: str) -> str | None:
        return self._artist_name_to_id.get(name)

    def track_id_of_name(self, name: str) -> str | None:
        return self._track_name_to_id.get(name)

    # ----- Track-side -----

    def artist_id_of(self, track_id: str) -> str | None:
        meta = self.tracks.get(track_id)
        return meta.get("artist_id") if meta else None

    def tracks_by_artist_id(self, artist_id: str) -> list[str]:
        return list(self._tracks_by_artist.get(artist_id, []))

    def tag_list(self, track_id: str) -> list[str]:
        meta = self.tracks.get(track_id)
        return list(meta.get("tag_list", []) if meta else [])

    def track_label(self, track_id: str) -> str:
        meta = self.tracks.get(track_id)
        if not meta:
            return ""
        track = str(meta.get("track_name") or "").strip()
        artist = str(meta.get("artist_name") or "").strip()
        if artist and track:
            return f"{artist} - {track}"
        return track or artist

    # ----- Embeddings -----

    def vector(self, track_id: str, vector_field: str) -> list[float] | None:
        """Multi-field vector lookup. Looks for `vectors[vector_field]` first,
        then falls back to the legacy `metadata_vector` key when the requested
        field is the metadata column."""
        meta = self.tracks.get(track_id)
        if not meta:
            return None
        vectors = meta.get("vectors") or {}
        vec = vectors.get(vector_field)
        if vec:
            return list(vec)
        # Legacy single-vector fallback: only matches the metadata channel.
        if vector_field == "metadata_qwen3_embedding_0_6b":
            legacy = meta.get("metadata_vector")
            return list(legacy) if legacy else None
        return None

    def metadata_vector(self, track_id: str) -> list[float] | None:
        return self.vector(track_id, "metadata_qwen3_embedding_0_6b")

    # ----- Catalog-wide -----

    def release_date_filter_mask(self, hf) -> set[str]:
        out: set[str] = set()
        for tid, meta in self.tracks.items():
            rd_str = meta.get("release_date") or ""
            try:
                rd = date.fromisoformat(rd_str)
            except ValueError:
                continue
            if hf.op == "<" and rd < hf.end:
                out.add(tid)
            elif hf.op == ">" and rd > hf.start:
                out.add(tid)
            elif hf.op == "between" and hf.start <= rd <= hf.end:
                out.add(tid)
        return out

    def release_year_of(self, track_id: str) -> int | None:
        meta = self.tracks.get(track_id)
        if meta is None:
            return None
        rd_str = str(meta.get("release_date") or "").strip()
        if len(rd_str) >= 4 and rd_str[:4].isdigit():
            return int(rd_str[:4])
        return None

    def all_track_ids(self) -> list[str]:
        return list(self.tracks.keys())

    def popularity_sorted_track_ids(self) -> list[str]:
        return sorted(
            self.tracks.keys(),
            key=lambda tid: -float(self.tracks[tid].get("popularity", 0.0)),
        )

    def release_year_of(self, track_id: str) -> int | None:
        meta = self.tracks.get(track_id)
        if meta is None:
            return None
        rd = str(meta.get("release_date") or "").strip()
        return int(rd[:4]) if len(rd) >= 4 and rd[:4].isdigit() else None


# ----------------------------------------------------------------------
# Retriever fake
# ----------------------------------------------------------------------


@dataclass
class FakeRetriever:
    """Fake Retriever. Records calls; returns scripted hits.

    `text_hits_by_field`: bm25_field -> list of (track_id, score) returned by
        the search() call when that single clause is present. If multiple
        clauses are given, the fake unions all the per-field hits and ranks
        them by sum-of-scores (NOT the production RRF behavior, but adequate
        for compiler-level tests where we just need to verify the right
        clauses were sent).

    `embedding_hits`: list of (track_id, similarity) returned by every
        search_embedding() call. The vector arg is recorded for assertions.
    """

    text_hits_by_field: dict[str, list[tuple[str, float]]] = field(default_factory=dict)
    embedding_hits: list[tuple[str, float]] = field(default_factory=list)
    search_calls: list[list[FieldQuery]] = field(default_factory=list)
    embedding_calls: list[dict] = field(default_factory=list)

    @property
    def supported_text_fields(self) -> frozenset[str]:
        return frozenset({
            "track_name",
            "artist_name",
            "album_name",
            "tag_list",
            "release_date",
            "release_year",
            "release_decade",
        })

    @property
    def supported_vector_fields(self) -> frozenset[str]:
        return frozenset({
            "metadata_qwen3_embedding_0_6b",
            "attributes_qwen3_embedding_0_6b",
            "lyrics_qwen3_embedding_0_6b",
            "audio_laion_clap",
            "image_siglip2",
            "cf_bpr",
            "vec_a",
            "vec_b",
            "vec_c",
        })

    def search(self, clauses: list[FieldQuery], *, topk: int = 1000) -> list[tuple[str, float]]:
        # Record (drop blanks like the real one does)
        valid = [c for c in clauses if c.query.strip()]
        self.search_calls.append(list(valid))
        # Union per-field hits, sum scores for duplicates, sort desc
        scores: dict[str, float] = {}
        for c in valid:
            for tid, s in self.text_hits_by_field.get(c.field, []):
                scores[tid] = scores.get(tid, 0.0) + s * c.boost
        ranked = sorted(scores.items(), key=lambda kv: -kv[1])
        return ranked[:topk]

    def search_embedding(
        self,
        query_vector: list[float],
        *,
        vector_field: str,
        topk: int = 1000,
        distance_type: str = "cosine",
        filter_missing: bool = True,
    ) -> list[tuple[str, float]]:
        self.embedding_calls.append(
            {
                "query_vector": list(query_vector),
                "vector_field": vector_field,
                "topk": topk,
                "distance_type": distance_type,
                "filter_missing": filter_missing,
            }
        )
        return list(self.embedding_hits)[:topk]
