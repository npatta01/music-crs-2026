"""LanceDB-backed implementation of CompilerCatalog.

The HF-backed `HFTalkPlayCatalog` is retained for unit tests; production v0+
inference reads from this class so LanceDB is the canonical metadata source.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as _date
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from experiments.analysis.conversation_state_extraction_bakeoff.schema import (
        HardFilter,
    )


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
            if "embedding" in name and not name.startswith("has_"):
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
            artist_name = _first(row.get("artist_name"))
            track_name = _first(row.get("track_name"))
            artist_id = _first(row.get("artist_id"))
            if artist_name and artist_name not in artist_seen:
                artist_seen.add(artist_name)
                self._artist_names.append(artist_name)
                if artist_id:
                    self._artist_name_to_id[artist_name] = artist_id
            if track_name and track_name not in track_seen:
                track_seen.add(track_name)
                self._track_names.append(track_name)
                self._track_name_to_id[track_name] = tid
            if artist_id:
                self._tracks_by_artist_id.setdefault(artist_id, []).append(tid)
            rd = row.get("release_date")
            if isinstance(rd, _date):
                self._release_date_by_tid[tid] = rd

        self._popularity_sorted = sorted(
            self._per_track.keys(),
            key=lambda t: (-(float(self._per_track[t].get("popularity") or 0.0)), t),
        )

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

    def tracks_by_artist_id(self, artist_id: str) -> list[str]:
        return list(self._tracks_by_artist_id.get(artist_id, []))

    def tag_list(self, track_id: str) -> list[str]:
        row = self._per_track.get(track_id)
        if row is None:
            return []
        return _list_of_str(row.get("tag_list"))

    def vector(self, track_id: str, vector_field: str) -> list[float] | None:
        if vector_field not in self._vector_columns_available:
            return None
        # lancedb 0.30.2: use the search builder for column projection +
        # where-filtering. `.limit(0)` returns all matching rows.
        df = (
            self._table.search()
            .select(["track_id", vector_field])
            .where(f"track_id = '{track_id}'")
            .limit(0)
            .to_pandas()
        )
        if df.empty:
            return None
        v = df.iloc[0][vector_field]
        if v is None:
            return None
        return [float(x) for x in v]

    def metadata_vector(self, track_id: str) -> list[float] | None:
        return self.vector(track_id, "metadata_qwen3_embedding_0_6b")

    def release_date_filter_mask(self, hf: "HardFilter") -> set[str]:
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
