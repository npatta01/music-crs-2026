"""LanceDB-backed implementation of CompilerCatalog.

The HF-backed `HFTalkPlayCatalog` is retained for unit tests; production v0+
inference reads from this class so LanceDB is the canonical metadata source.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as _date
from typing import Any, TYPE_CHECKING

# Vector columns that don't follow the `*_embedding_*` naming convention but
# are still per-track precomputed vectors we want to load. Add new
# alternative-modality columns here as the LanceDB index grows.
#
# All three are stored as `fixed_size_list<float32>[dim]` (pinned by
# `mcrs.lancedb.indexing.build_track_lancedb_table`) so they are ANN-queryable
# via the LanceDB retriever just like the qwen3 columns.
_NON_EMBEDDING_VECTOR_COLUMNS = (
    "cf_bpr",            # 128-d collaborative-filtering BPR vector
    "audio_laion_clap",  # 512-d LAION CLAP audio embedding
    "image_siglip2",     # 768-d SigLIP-2 cover-image embedding
)

if TYPE_CHECKING:
    from mcrs.conversation_state.schema import (
        HardFilter,
    )


import re as _re

# "Safe identifier" shape: bare ASCII letters / digits / hyphens / underscores.
# Matches both UUID v4 and test fixtures like "t-fugazi-1"; rejects the row-
# dump-shaped strings the LLM extractor occasionally emits (those contain
# quotes / colons / whitespace that would break the SQL WHERE clause in
# `LanceDbCatalog.vector`). Schema-level validation in
# `mcrs.conversation_state.schema` enforces the same rule so bad ids never reach
# this code path in production; this is defense in depth for callers that bypass
# the schema.
_SAFE_ID_RE = _re.compile(r"^[A-Za-z0-9_\-]+$")


def _looks_like_track_id(value: Any) -> bool:
    return isinstance(value, str) and bool(_SAFE_ID_RE.match(value))


def _is_sequence(value: Any) -> bool:
    """True for python list or numpy ndarray. LanceDB returns list<...> columns
    as numpy ndarrays through pandas, but plain lists are also possible when
    callers construct the catalog from in-memory rows in tests."""
    if isinstance(value, list):
        return True
    # Avoid importing numpy at module load; rely on duck-typing instead.
    return hasattr(value, "__len__") and hasattr(value, "__iter__") and not isinstance(value, (str, bytes, dict))


def _first(value: Any) -> str | None:
    """Pluck the first non-empty string from a single-value or list field, or None."""
    if value is None:
        return None
    if _is_sequence(value):
        if len(value) == 0:
            return None
        head = value[0]
        if head is None:
            return None
        s = str(head).strip()
        return s or None
    s = str(value).strip()
    return s or None


def _list_of_str(value: Any) -> list[str]:
    """Coerce a scalar/list/None field into a list[str], dropping None entries."""
    if value is None:
        return []
    if _is_sequence(value):
        return [str(v) for v in value if v is not None]
    return [str(value)]


@dataclass
class LanceDbCatalog:
    """CompilerCatalog backed by a LanceDB table opened at init time.

    Scans the table once at init and materializes derived caches (artist names,
    track names, popularity-sorted ids, etc.) so per-call lookups stay O(1).
    Vector reads stay on-demand until eager-loading is added in Task 5.
    """

    db_uri: str
    table_name: str = "music_track_catalog"
    eager_vector_fields: tuple[str, ...] = ()

    # Populated from the LanceDB scan in __post_init__
    _per_track: dict[str, dict[str, Any]] = field(default_factory=dict, init=False, repr=False)
    _artist_names: list[str] = field(default_factory=list, init=False, repr=False)
    _track_names: list[str] = field(default_factory=list, init=False, repr=False)
    _artist_name_to_id: dict[str, str] = field(default_factory=dict, init=False, repr=False)
    _track_name_to_id: dict[str, str] = field(default_factory=dict, init=False, repr=False)
    _tracks_by_artist_id: dict[str, list[str]] = field(default_factory=dict, init=False, repr=False)
    _popularity_sorted: list[str] = field(default_factory=list, init=False, repr=False)
    _release_date_by_tid: dict[str, _date] = field(default_factory=dict, init=False, repr=False)
    _vector_columns_available: set[str] = field(default_factory=set, init=False, repr=False)
    _vectors: dict[str, dict[str, list[float]]] = field(default_factory=dict, init=False, repr=False)
    _table: Any = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        import lancedb

        db = lancedb.connect(self.db_uri)
        self._table = db.open_table(self.table_name)

        # Identify vector columns available for on-demand reads. We match by
        # "embedding" substring and exclude `has_*` presence flags. Eager
        # loading of these columns is Task 5.
        existing = {f.name for f in self._table.schema}
        for name in existing:
            if name.startswith("has_"):
                continue
            if "embedding" in name or name in _NON_EMBEDDING_VECTOR_COLUMNS:
                self._vector_columns_available.add(name)

        wanted = [
            "track_id", "release_date", "popularity",
            "track_name", "artist_name", "artist_id", "album_name", "album_id",
            "tag_list",
        ]
        wanted = [c for c in wanted if c in existing]

        # lancedb 0.30.2 does not accept `columns` on `Table.to_pandas`. Use
        # the search builder's `.select(...).limit(0)` to project columns and
        # return all rows.
        df = self._table.search().select(wanted).limit(0).to_pandas()
        artist_seen: set[str] = set()
        track_seen: set[str] = set()
        for row in df.to_dict(orient="records"):
            tid = str(row["track_id"])
            self._per_track[tid] = row
            # Index ALL co-credited artists (parity with HFTalkPlayCatalog) —
            # taking only the first artist would silently drop collaborations
            # from resolver fuzzy match + explicit-rejection hard-exclude.
            artist_names = _list_of_str(row.get("artist_name"))
            artist_ids = _list_of_str(row.get("artist_id"))
            track_name = _first(row.get("track_name"))
            from itertools import zip_longest
            # zip() truncated to the shorter list, silently dropping 6,533
            # artist credits on 3,342 tracks (source data ships mismatched
            # artist_name/artist_id lengths). Ids are authoritative.
            for name, aid in zip_longest(artist_names, artist_ids, fillvalue=""):
                name = name.strip()
                if name and name not in artist_seen:
                    artist_seen.add(name)
                    self._artist_names.append(name)
                    if aid:
                        self._artist_name_to_id[name] = aid
                if aid:
                    self._tracks_by_artist_id.setdefault(aid, []).append(tid)
            if track_name and track_name not in track_seen:
                track_seen.add(track_name)
                self._track_names.append(track_name)
                self._track_name_to_id[track_name] = tid
            rd = row.get("release_date")
            if isinstance(rd, _date):
                self._release_date_by_tid[tid] = rd

        self._artist_names.sort()
        self._track_names.sort()

        self._popularity_sorted = sorted(
            self._per_track.keys(),
            key=lambda t: (-(float(self._per_track[t].get("popularity") or 0.0)), t),
        )

        # Eager-load any vector columns the caller opted into. Scans each named
        # column once so subsequent vector() lookups are an O(1) dict hit.
        schema_field_names = {f.name for f in self._table.schema}
        for vf in self.eager_vector_fields:
            if vf not in self._vector_columns_available:
                continue
            has_col = f"has_{vf}"
            cols = ["track_id", vf]
            if has_col in schema_field_names:
                cols.append(has_col)
            vdf = self._table.search().select(cols).limit(0).to_pandas()
            store: dict[str, list[float]] = {}
            for row in vdf.to_dict(orient="records"):
                tid = str(row["track_id"])
                if has_col in row and not row.get(has_col):
                    continue
                vec = row.get(vf)
                if vec is None:
                    continue
                store[tid] = [float(x) for x in vec]
            self._vectors[vf] = store

    # ----- Protocol methods -----

    @property
    def artist_names(self) -> list[str]:
        return list(self._artist_names)

    @property
    def track_names(self) -> list[str]:
        return list(self._track_names)

    def artist_id_of_name(self, name: str) -> str | None:
        return self._artist_name_to_id.get(name)

    def track_id_of_name(self, name: str) -> str | None:
        return self._track_name_to_id.get(name)

    def artist_id_of(self, track_id: str) -> str | None:
        row = self._per_track.get(track_id)
        if row is None:
            return None
        return _first(row.get("artist_id"))

    def album_id_of(self, track_id: str) -> str | None:
        """Return the canonical album_id for a track. None if the catalog
        row is missing or has no album_id (some tracks legitimately lack one)."""
        row = self._per_track.get(track_id)
        if row is None:
            return None
        return _first(row.get("album_id"))

    def tracks_by_artist_id(self, artist_id: str) -> list[str]:
        return list(self._tracks_by_artist_id.get(artist_id, []))

    def tag_list(self, track_id: str) -> list[str]:
        row = self._per_track.get(track_id)
        if row is None:
            return []
        return _list_of_str(row.get("tag_list"))

    def release_year_of(self, track_id: str) -> int | None:
        """Year (int) of the track's release_date, or None if unknown/unparseable.
        Used by the release_year_range post-fusion feature for soft date boosting."""
        row = self._per_track.get(track_id)
        if row is None:
            return None
        rd = _first(row.get("release_date")) if isinstance(row.get("release_date"), list) else row.get("release_date")
        if not rd:
            return None
        s = str(rd).strip()
        if len(s) >= 4 and s[:4].isdigit():
            return int(s[:4])
        return None

    def track_label(self, track_id: str) -> str:
        row = self._per_track.get(track_id)
        if row is None:
            return ""
        track = _first(row.get("track_name")) or ""
        artist = _first(row.get("artist_name")) or ""
        if artist and track:
            return f"{artist} - {track}"
        return track or artist

    def track_text(self, track_id: str, *, max_tags: int = 5) -> str:
        """Rich text representation for cross-encoder rerankers.

        Format: `"{artist} - {track} | {album} | tag1, tag2, ..."`. Used by
        the cross-encoder reranker as the candidate side of a (query, doc)
        pair. Tags are capped to keep input length manageable.

        Empty string if the track is unknown.
        """
        row = self._per_track.get(track_id)
        if row is None:
            return ""
        artist = _first(row.get("artist_name")) or ""
        track = _first(row.get("track_name")) or ""
        album = _first(row.get("album_name")) or ""
        tags = _list_of_str(row.get("tag_list"))[:max_tags]
        parts: list[str] = []
        if artist and track:
            parts.append(f"{artist} - {track}")
        elif track:
            parts.append(track)
        elif artist:
            parts.append(artist)
        else:
            return ""
        if album and album not in parts[0]:
            parts.append(album)
        if tags:
            parts.append(", ".join(tags))
        return " | ".join(parts)

    def vector(self, track_id: str, vector_field: str) -> list[float] | None:
        # Eager path: O(1) dict lookup if this field was preloaded at init.
        cached = self._vectors.get(vector_field)
        if cached is not None:
            return cached.get(track_id)
        # Cold path: per-call LanceDB query. Preserved for backward-compat and
        # for tests/callers that don't opt into eager loading.
        if vector_field not in self._vector_columns_available:
            return None
        # Defense in depth: the LLM extractor occasionally hallucinates a
        # whole stringified track record as a `track_id` (e.g. a yaml dump
        # of the row's metadata). Such values contain quotes and break the
        # SQL WHERE clause below. Catch malformed inputs by shape first,
        # then escape single quotes for valid-looking ids, and finally fall
        # back to None on any LanceDB error so a single bad anchor doesn't
        # crash an entire shard.
        if not _looks_like_track_id(track_id):
            return None
        escaped = track_id.replace("'", "''")
        try:
            # lancedb 0.30.2: use the search builder for column projection +
            # where-filtering. `.limit(0)` returns all matching rows.
            df = (
                self._table.search()
                .select(["track_id", vector_field])
                .where(f"track_id = '{escaped}'")
                .limit(0)
                .to_pandas()
            )
        except Exception:
            return None
        if df.empty:
            return None
        v = df.iloc[0][vector_field]
        if v is None:
            return None
        return [float(x) for x in v]

    def metadata_vector(self, track_id: str) -> list[float] | None:
        return self.vector(track_id, "metadata_qwen3_embedding_0_6b")

    def release_date_filter_mask(self, hf: "HardFilter") -> set[str]:
        # Defensive: a malformed HardFilter (e.g., constructed by bypassing Pydantic
        # validation) could have None bounds. Skip rather than crash.
        if hf.op == "<" and hf.end is None:
            return set()
        if hf.op == ">" and hf.start is None:
            return set()
        if hf.op == "between" and (hf.start is None or hf.end is None):
            return set()
        out: set[str] = set()
        for tid, rd in self._release_date_by_tid.items():
            if hf.op == "<" and rd < hf.end:
                out.add(tid)
            elif hf.op == ">" and rd > hf.start:
                out.add(tid)
            elif hf.op == "between" and hf.start <= rd <= hf.end:
                out.add(tid)
        return out

    def all_track_ids(self) -> list[str]:
        return list(self._per_track.keys())

    def popularity_sorted_track_ids(self) -> list[str]:
        return list(self._popularity_sorted)
