"""Small helpers for the local Music CRS debug CLI.

The helpers in this module are deliberately read-only and artifact-oriented.
They make it cheap to inspect saved traces, predictions, audits, and catalog
metadata without pulling debug behavior into the production pipeline.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


DEFAULT_RUN_FILE = "mcrs_debug_runs.json"
DEFAULT_CATALOG_DB_URI = "cache/lancedb"
DEFAULT_CATALOG_TABLE = "music_track_catalog"


@dataclass(frozen=True)
class RunArtifacts:
    name: str
    trace: Path | None = None
    prediction: Path | None = None
    audit: Path | None = None
    split: str = ""
    catalog_db_uri: Path = Path(DEFAULT_CATALOG_DB_URI)
    catalog_table: str = DEFAULT_CATALOG_TABLE


@dataclass(frozen=True)
class CatalogHit:
    track_id: str
    track_name: str
    artist_names: tuple[str, ...] = ()
    album_name: str = ""
    tags: tuple[str, ...] = ()
    score: float = 0.0


@dataclass(frozen=True)
class CatalogSearchResult:
    exact: list[CatalogHit] = field(default_factory=list)
    title_or_album_only: list[CatalogHit] = field(default_factory=list)
    contains: list[CatalogHit] = field(default_factory=list)
    text: list[CatalogHit] = field(default_factory=list)


def load_run_aliases(path: str | Path = DEFAULT_RUN_FILE) -> dict[str, dict[str, Any]]:
    run_path = Path(path)
    data = json.loads(run_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"run file must be a JSON object: {run_path}")
    for name, raw in data.items():
        if not isinstance(raw, dict):
            raise ValueError(f"run alias {name!r} must be a JSON object")
    return data


def resolve_run_alias(
    aliases: dict[str, dict[str, Any]],
    name: str,
    *,
    base_dir: str | Path = ".",
) -> RunArtifacts:
    if name not in aliases:
        available = ", ".join(sorted(aliases)) or "(none)"
        raise ValueError(f"unknown run alias {name!r}; available: {available}")
    base = Path(base_dir)
    raw = aliases[name]

    def opt_path(key: str) -> Path | None:
        value = raw.get(key)
        if value is None or str(value).strip() == "":
            return None
        path = Path(str(value))
        return path if path.is_absolute() else base / path

    catalog_db_uri = Path(str(raw.get("catalog_db_uri") or DEFAULT_CATALOG_DB_URI))
    if not catalog_db_uri.is_absolute():
        catalog_db_uri = base / catalog_db_uri

    return RunArtifacts(
        name=name,
        trace=opt_path("trace"),
        prediction=opt_path("prediction"),
        audit=opt_path("audit"),
        split=str(raw.get("split") or ""),
        catalog_db_uri=catalog_db_uri,
        catalog_table=str(raw.get("catalog_table") or DEFAULT_CATALOG_TABLE),
    )


def resolve_session_prefix(session_ids: Iterable[str], prefix: str) -> str:
    cleaned = str(prefix or "").strip()
    if not cleaned:
        raise ValueError("session prefix must be non-empty")
    matches = sorted({sid for sid in session_ids if str(sid).startswith(cleaned)})
    if not matches:
        raise ValueError(f"no session id starts with {cleaned!r}")
    if len(matches) > 1:
        sample = ", ".join(matches[:8])
        raise ValueError(f"ambiguous session prefix {cleaned!r}; matches: {sample}")
    return matches[0]


def iter_trace_rows(path: str | Path) -> Iterable[dict[str, Any]]:
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def trace_session_ids(path: str | Path) -> set[str]:
    return {str(row.get("session_id") or "") for row in iter_trace_rows(path)}


def trace_turns(path: str | Path, session_id: str) -> list[int]:
    turns: list[int] = []
    for row in iter_trace_rows(path):
        if str(row.get("session_id") or "") != session_id:
            continue
        try:
            turns.append(int(row.get("turn_number")))
        except (TypeError, ValueError):
            continue
    return sorted(set(turns))


def trace_row(path: str | Path, session_id: str, turn_number: int) -> dict[str, Any]:
    for row in iter_trace_rows(path):
        if (
            str(row.get("session_id") or "") == session_id
            and int(row.get("turn_number") or 0) == int(turn_number)
        ):
            return row
    turns = trace_turns(path, session_id)
    raise ValueError(
        f"no trace row for session={session_id!r} turn={turn_number}; "
        f"available turns: {turns}"
    )


def load_prediction_index(path: str | Path | None) -> dict[tuple[str, int], dict[str, Any]]:
    if path is None or not Path(path).exists():
        return {}
    rows = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        return {}
    out: dict[tuple[str, int], dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            key = (str(row.get("session_id") or ""), int(row.get("turn_number") or 0))
        except (TypeError, ValueError):
            continue
        out[key] = row
    return out


def load_audit_index(path: str | Path | None) -> dict[tuple[str, int], dict[str, Any]]:
    if path is None or not Path(path).exists():
        return {}
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = data.get("rows") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        return {}
    out: dict[tuple[str, int], dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            key = (str(row.get("session_id") or ""), int(row.get("turn_number") or 0))
        except (TypeError, ValueError):
            continue
        out[key] = row
    return out


def catalog_search(
    rows: dict[str, dict[str, Any]],
    *,
    track: str | None = None,
    artist: str | None = None,
    album: str | None = None,
    text: str | None = None,
    limit: int = 25,
) -> CatalogSearchResult:
    track_key = _surface_key(track)
    artist_key = _surface_key(artist)
    album_key = _surface_key(album)
    text_tokens = tuple(tok for tok in _surface_key(text).split() if tok)
    artist_only = bool(artist_key and not track_key and not album_key and not text_tokens)

    exact: list[CatalogHit] = []
    title_or_album_only: list[CatalogHit] = []
    contains: list[CatalogHit] = []
    text_hits: list[CatalogHit] = []

    for track_id, row in rows.items():
        hit = _catalog_hit(str(track_id), row)
        title_key = _surface_key(hit.track_name)
        album_row_key = _surface_key(hit.album_name)
        artist_keys = {_surface_key(name) for name in hit.artist_names}
        haystack = _surface_key(
            " ".join([hit.track_name, hit.album_name, *hit.artist_names, *hit.tags])
        )

        title_matches = bool(track_key and title_key == track_key)
        album_matches = bool(album_key and album_row_key == album_key)
        entity_matches = title_matches or album_matches
        artist_matches = not artist_key or artist_key in artist_keys

        if artist_only and artist_matches:
            exact.append(hit)
            continue

        if entity_matches and artist_matches:
            exact.append(hit)
            continue
        if entity_matches:
            title_or_album_only.append(hit)
            continue

        contains_entity = (
            bool(track_key and (track_key in title_key or title_key in track_key))
            or bool(album_key and (album_key in album_row_key or album_row_key in album_key))
        )
        if contains_entity and artist_matches:
            contains.append(hit)
            continue

        if text_tokens and all(token in haystack for token in text_tokens):
            text_hits.append(hit)

    return CatalogSearchResult(
        exact=exact[:limit],
        title_or_album_only=title_or_album_only[:limit],
        contains=contains[:limit],
        text=text_hits[:limit],
    )


def _catalog_hit(track_id: str, row: dict[str, Any]) -> CatalogHit:
    return CatalogHit(
        track_id=track_id,
        track_name=_first_str(row.get("track_name")),
        artist_names=tuple(_str_values(row.get("artist_name"))),
        album_name=_first_str(row.get("album_name")),
        tags=tuple(_str_values(row.get("tag_list"))),
    )


def _surface_key(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).lower().replace("'", "").replace("’", "")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _first_str(value: Any) -> str:
    values = _str_values(value)
    return values[0] if values else ""


def _str_values(value: Any) -> list[str]:
    if value is None:
        return []
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if item is not None and str(item).strip()]
    text = str(value).strip()
    return [text] if text else []
