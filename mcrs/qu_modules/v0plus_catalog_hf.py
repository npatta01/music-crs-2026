"""HuggingFace-backed `CompilerCatalog` for the v0+ pipeline.

Loads the TalkPlayData challenge metadata + embedding datasets and builds the
in-memory indices the Resolver / Compiler / FuzzyMatcher need. Indexes are
**pre-built on init** so every per-turn lookup is RAM-only.

Splits / source datasets (see `docs/data.md`):
- `talkpl-ai/TalkPlayData-Challenge-Track-Metadata` split `all_tracks` (47k)
- `talkpl-ai/TalkPlayData-Challenge-Track-Embeddings` split `all_tracks` (47k)

Memory footprint (47k tracks):
- metadata + reverse maps:                    ~25 MB
- 1024-dim float32 metadata embeddings:      ~190 MB
- Total:                                     ~215 MB

For multi-worker Modal serving this is fine; if it ever becomes a problem,
the embedding store is the obvious memory-map candidate.

The constructor splits cleanly into a HF-loader (`__init__`) and a pure
`from_rows` classmethod, so tests can build catalogs from in-memory rows
without network IO.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Iterable, Mapping

DEFAULT_METADATA_DATASET = "talkpl-ai/TalkPlayData-Challenge-Track-Metadata"
DEFAULT_EMBEDDINGS_DATASET = "talkpl-ai/TalkPlayData-Challenge-Track-Embeddings"
DEFAULT_METADATA_SPLIT = "all_tracks"
DEFAULT_EMBEDDINGS_SPLIT = "all_tracks"
DEFAULT_VECTOR_COLUMN = "metadata-qwen3_embedding_0.6b"

# Default vector columns to load from the HF embeddings dataset. The v0+ compiler
# currently uses metadata + attributes + lyrics as 3 separate dense branches; the
# audio/image/cf columns aren't ANN-queryable in the current LanceDB index (see
# docs/talkplay_embedding_specs.md), so we skip them at load time to save memory.
DEFAULT_VECTOR_COLUMNS_FOR_V0PLUS = (
    "metadata-qwen3_embedding_0.6b",
    "attributes-qwen3_embedding_0.6b",
    "lyrics-qwen3_embedding_0.6b",
)


def hf_column_to_lance_field(hf_column: str) -> str:
    """Convert an HF embeddings dataset column name to the LanceDB-safe
    column name used as `vector_field` in the Retriever Protocol."""
    return hf_column.replace("-", "_").replace(".", "_")


def _first_or_none(value: Any) -> Any:
    """HF metadata uses list[str] for name/id columns even when there's only
    one entry. Take the first element, or None if missing/empty."""
    if value is None:
        return None
    if isinstance(value, list):
        return value[0] if value else None
    return value


@dataclass
class HFTalkPlayCatalog:
    """In-memory snapshot of the TalkPlayData track catalog + metadata embeddings.

    Implements the `CompilerCatalog` Protocol. Prefer `__init__` for production
    (loads from HF); use `from_rows` for tests / synthetic data.
    """

    # ---- Per-track storage ----
    metadata: dict[str, dict[str, Any]] = field(default_factory=dict)
    """track_id -> raw metadata dict (track_name, artist_name, etc.)."""

    # New multi-field vector store keyed by Lance-safe field name (e.g.
    # `metadata_qwen3_embedding_0_6b`). `embeddings` kept as a single-field
    # alias for back-compat with rev-1 construction paths.
    vectors_by_field: dict[str, dict[str, list[float]]] = field(default_factory=dict)
    embeddings: dict[str, list[float]] = field(default_factory=dict)

    # ---- Pre-built derived indices (populated by _build_indices) ----
    _artist_names: list[str] = field(default_factory=list, init=False, repr=False)
    _track_names: list[str] = field(default_factory=list, init=False, repr=False)
    _artist_name_to_id: dict[str, str] = field(default_factory=dict, init=False, repr=False)
    _track_name_to_id: dict[str, str] = field(default_factory=dict, init=False, repr=False)
    _tracks_by_artist_id: dict[str, list[str]] = field(default_factory=dict, init=False, repr=False)
    _popularity_sorted: list[str] = field(default_factory=list, init=False, repr=False)
    _vectors_by_field: dict[str, dict[str, list[float]]] = field(
        default_factory=dict, init=False, repr=False
    )

    def __post_init__(self) -> None:
        # Merge legacy single-field `embeddings` arg into the multi-field store
        # under the default metadata-qwen3 Lance field name. Tests / older code
        # that passed `embeddings=...` keep working.
        merged: dict[str, dict[str, list[float]]] = {
            field_name: dict(by_tid) for field_name, by_tid in (self.vectors_by_field or {}).items()
        }
        if self.embeddings:
            metadata_field = hf_column_to_lance_field(DEFAULT_VECTOR_COLUMN)
            merged.setdefault(metadata_field, {}).update(
                {tid: list(vec) for tid, vec in self.embeddings.items() if vec}
            )
        self._vectors_by_field = merged
        self._build_indices()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def from_hf(
        cls,
        metadata_dataset: str = DEFAULT_METADATA_DATASET,
        embeddings_dataset: str = DEFAULT_EMBEDDINGS_DATASET,
        metadata_split: str = DEFAULT_METADATA_SPLIT,
        embeddings_split: str = DEFAULT_EMBEDDINGS_SPLIT,
        vector_columns: tuple[str, ...] | list[str] = DEFAULT_VECTOR_COLUMNS_FOR_V0PLUS,
    ) -> "HFTalkPlayCatalog":
        """Load both datasets and build the catalog. Triggers network IO and
        any cached HF dataset materialization.

        `vector_columns` is the list of HF-side embedding column names to keep
        in memory (e.g. ``metadata-qwen3_embedding_0.6b``). Loading only the
        columns we'll actually use saves ~hundreds of MB on the multi-modal
        embeddings dataset.
        """
        from datasets import load_dataset

        meta_ds = load_dataset(metadata_dataset, split=metadata_split)
        emb_ds = load_dataset(embeddings_dataset, split=embeddings_split)
        return cls.from_rows(
            metadata_rows=meta_ds,
            embedding_rows=emb_ds,
            vector_columns=vector_columns,
        )

    @classmethod
    def from_rows(
        cls,
        metadata_rows: Iterable[Mapping[str, Any]],
        embedding_rows: Iterable[Mapping[str, Any]] | None = None,
        vector_column: str | None = None,  # legacy single-field path
        vector_columns: tuple[str, ...] | list[str] | None = None,  # multi-field path
    ) -> "HFTalkPlayCatalog":
        """Build from arbitrary iterables — useful for tests and synthetic data.

        Either `vector_column` (single field, legacy) or `vector_columns`
        (multiple fields) may be supplied. When both are None, defaults to the
        v0+ multi-field set.
        """
        if vector_column is not None and vector_columns is not None:
            raise ValueError("Pass either `vector_column` or `vector_columns`, not both")
        if vector_column is not None:
            wanted_hf_columns: list[str] = [vector_column]
        else:
            wanted_hf_columns = list(vector_columns or DEFAULT_VECTOR_COLUMNS_FOR_V0PLUS)

        metadata: dict[str, dict[str, Any]] = {}
        for row in metadata_rows:
            tid = row.get("track_id")
            if not tid:
                continue
            metadata[str(tid)] = dict(row)

        vectors_by_field: dict[str, dict[str, list[float]]] = {
            hf_column_to_lance_field(name): {} for name in wanted_hf_columns
        }
        if embedding_rows is not None:
            for row in embedding_rows:
                tid = row.get("track_id")
                if not tid:
                    continue
                tid_str = str(tid)
                for hf_col in wanted_hf_columns:
                    vec = row.get(hf_col)
                    if vec is None:
                        continue
                    # Empty list means the embedding is missing for this track.
                    if isinstance(vec, list) and not vec:
                        continue
                    vectors_by_field[hf_column_to_lance_field(hf_col)][tid_str] = [
                        float(x) for x in vec
                    ]

        return cls(metadata=metadata, vectors_by_field=vectors_by_field)

    def _build_indices(self) -> None:
        """Walk the per-track metadata once to materialize the reverse maps."""
        artist_names_seen: set[str] = set()
        track_names_seen: set[str] = set()
        tracks_by_artist: dict[str, list[str]] = defaultdict(list)

        artist_name_to_id: dict[str, str] = {}
        track_name_to_id: dict[str, str] = {}

        for tid, meta in self.metadata.items():
            # Track name (single canonical) → id
            track_name = _first_or_none(meta.get("track_name"))
            if track_name and track_name not in track_names_seen:
                track_names_seen.add(track_name)
                track_name_to_id[track_name] = tid

            # Artists: this track can have multiple — index ALL of them so
            # tracks_by_artist_id is complete, but the reverse name→id map
            # only takes the first per name (deterministic = last-write-wins
            # over insertion order in dict).
            artist_names = meta.get("artist_name") or []
            artist_ids = meta.get("artist_id") or []
            if not isinstance(artist_names, list):
                artist_names = [artist_names]
            if not isinstance(artist_ids, list):
                artist_ids = [artist_ids]
            for name, aid in zip(artist_names, artist_ids):
                if not name or not aid:
                    continue
                if name not in artist_names_seen:
                    artist_names_seen.add(name)
                    artist_name_to_id[name] = aid
                tracks_by_artist[aid].append(tid)

        self._artist_names = sorted(artist_names_seen)
        self._track_names = sorted(track_names_seen)
        self._artist_name_to_id = artist_name_to_id
        self._track_name_to_id = track_name_to_id
        self._tracks_by_artist_id = dict(tracks_by_artist)
        self._popularity_sorted = sorted(
            self.metadata.keys(),
            key=lambda tid: -_popularity_of(self.metadata[tid]),
        )

    # ------------------------------------------------------------------
    # CompilerCatalog Protocol implementation
    # ------------------------------------------------------------------

    @property
    def artist_names(self) -> list[str]:
        return self._artist_names

    @property
    def track_names(self) -> list[str]:
        return self._track_names

    def artist_id_of_name(self, name: str) -> str | None:
        return self._artist_name_to_id.get(name)

    def track_id_of_name(self, name: str) -> str | None:
        return self._track_name_to_id.get(name)

    def artist_id_of(self, track_id: str) -> str | None:
        meta = self.metadata.get(track_id)
        if not meta:
            return None
        return _first_or_none(meta.get("artist_id"))

    def tracks_by_artist_id(self, artist_id: str) -> list[str]:
        return list(self._tracks_by_artist_id.get(artist_id, []))

    def tag_list(self, track_id: str) -> list[str]:
        meta = self.metadata.get(track_id)
        if not meta:
            return []
        tags = meta.get("tag_list") or []
        if not isinstance(tags, list):
            return [str(tags)]
        return [str(t) for t in tags if t]

    def vector(self, track_id: str, vector_field: str) -> list[float] | None:
        store = self._vectors_by_field.get(vector_field)
        if store is None:
            return None
        vec = store.get(track_id)
        if vec is None or not vec:
            return None
        return list(vec)

    def metadata_vector(self, track_id: str) -> list[float] | None:
        # Convenience wrapper; back-compat with single-branch v0+ design.
        return self.vector(track_id, "metadata_qwen3_embedding_0_6b")

    # Assumes meta["release_date"] is a zero-padded "YYYY-MM-DD" string.
    # Year-only or year-month catalog values would be silently dropped (date.fromisoformat raises).
    def release_date_filter_mask(self, hf) -> set[str]:
        out: set[str] = set()
        for tid, meta in self.metadata.items():
            rd_str = meta.get("release_date")
            if not isinstance(rd_str, str) or not rd_str:
                continue
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

    def all_track_ids(self) -> list[str]:
        return list(self.metadata.keys())

    def popularity_sorted_track_ids(self) -> list[str]:
        return list(self._popularity_sorted)


def _popularity_of(meta: Mapping[str, Any]) -> float:
    try:
        return float(meta.get("popularity") or 0.0)
    except (TypeError, ValueError):
        return 0.0
