"""Formatting and JSON helpers for the Music CRS debug CLI."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any


def _write_json(payload: Any, path: str | None) -> None:
    text = json.dumps(_jsonable(payload), indent=2, sort_keys=True) + "\n"
    if path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    else:
        print(text, end="")

def _track_payload(track_id: str, row: dict[str, Any]) -> dict[str, Any]:
    return {
        "track_id": track_id,
        "track_name": _first(row.get("track_name")),
        "artist_name": _join(row.get("artist_name")),
        "album_name": _first(row.get("album_name")),
        "tags": _list(_row_value(row, "tag_list", "tags")),
        "popularity": row.get("popularity"),
    }

def _print_case(payload: dict[str, Any]) -> None:
    trace = payload.get("trace") or {}
    audit = payload.get("audit") or {}
    prediction = payload.get("prediction") or {}
    judgment = audit.get("llm_judgment") if isinstance(audit.get("llm_judgment"), dict) else {}

    print(f"Run: {payload.get('run')}")
    print(f"Session: {payload.get('session_id')}")
    print(f"Turn: {payload.get('turn_number')}")
    _print_value("User", audit.get("latest_user_text"))
    _print_value("Summary", audit.get("current_request_summary"))
    _print_value("Request Type", audit.get("request_type"))
    _print_value("Judgment", judgment.get("verdict"))
    _print_value("Reason", judgment.get("reason"))

    _print_block("Extracted State", trace.get("extracted_state") or {})
    _print_block("Compiled State", trace.get("compiled_state") or {})
    _print_block("Resolver", trace.get("resolver") or {})
    _print_retrieval(trace.get("retrieval") or {})
    _print_ranking(trace.get("ranking") or {})

    items = audit.get("items") if isinstance(audit.get("items"), list) else []
    if items:
        print("Top Recommendations:")
        for item in items[:20]:
            rank = item.get("rank", "?")
            track = item.get("track") if isinstance(item.get("track"), dict) else {}
            text = _format_track_line(_track_payload(str(track.get("track_id") or ""), track))
            extras = _rank_extras(item)
            print(f"  {rank}. {text}{extras}")
    elif prediction:
        print("Prediction:")
        _print_json(prediction)

def _print_retrieval(retrieval: dict[str, Any]) -> None:
    print("Retrieval:")
    for name, status in sorted((retrieval.get("branch_status") or {}).items()):
        if isinstance(status, dict):
            fired = status.get("fired")
            hits = status.get("n_raw_hits")
            print(f"  {name}: fired={fired} n_raw_hits={hits}")
    branch_queries = retrieval.get("branch_queries") or {}
    if branch_queries:
        print("  branch_queries:")
        for name, query in sorted(branch_queries.items()):
            print(f"    {name}: {_short_json(query)}")

def _print_ranking(ranking: dict[str, Any]) -> None:
    print("Ranking:")
    final_stage = ranking.get("final_stage")
    if final_stage:
        print(f"  final_stage: {final_stage}")
    for stage in ranking.get("stages") or []:
        if not isinstance(stage, dict):
            continue
        track_ids = stage.get("track_ids") if isinstance(stage.get("track_ids"), list) else []
        print(f"  {stage.get('name', '(stage)')}: {len(track_ids)} ids")

def _print_block(label: str, value: Any) -> None:
    print(f"{label}:")
    text = json.dumps(_jsonable(value), indent=2, sort_keys=True)
    for line in text.splitlines():
        print(f"  {line}")

def _print_value(label: str, value: Any) -> None:
    if value not in (None, ""):
        print(f"{label}: {value}")

def _rank_extras(item: dict[str, Any]) -> str:
    extras = []
    for key in ("candidate_fusion_rank", "lgbm_rank", "retrieval_rank"):
        if item.get(key) not in (None, ""):
            extras.append(f"{key}={item[key]}")
    return f" ({', '.join(extras)})" if extras else ""

def _format_track_line(item: dict[str, Any]) -> str:
    title = item.get("track_name") or "(unknown title)"
    artist = item.get("artist_name") or _join(item.get("artist_names")) or "(unknown artist)"
    track_id = item.get("track_id") or "(unknown id)"
    album = item.get("album_name")
    tags = item.get("tags") or ()
    bits = [f"{title} / {artist}", f"[{track_id}]"]
    if album:
        bits.append(f"album={album}")
    if tags:
        bits.append("tags=" + ", ".join(str(tag) for tag in tags[:5]))
    return " ".join(bits)

def _parse_bm25_fields(raw: str) -> list[tuple[str, float]]:
    fields: list[tuple[str, float]] = []
    for part in str(raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        if ":" in part:
            name, boost_text = part.split(":", 1)
            boost = float(boost_text)
        else:
            name, boost = part, 1.0
        fields.append((name.strip(), boost))
    if not fields:
        raise ValueError("--fields must include at least one field")
    return fields

def _print_json(value: Any) -> None:
    print(json.dumps(_jsonable(value), indent=2, sort_keys=True))

def _short_json(value: Any) -> str:
    text = json.dumps(_jsonable(value), sort_keys=True)
    return text if len(text) <= 240 else text[:237] + "..."

def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    if hasattr(value, "tolist"):
        try:
            return value.tolist()
        except Exception:
            pass
    return value

def _row_value(row: dict[str, Any], primary: str, fallback: str) -> Any:
    value = row.get(primary)
    return row.get(fallback) if value is None else value

def _first(value: Any) -> str:
    values = _list(value)
    return values[0] if values else ""

def _join(value: Any) -> str:
    return ", ".join(_list(value))

def _list(value: Any) -> list[str]:
    if value is None:
        return []
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if item is not None and str(item).strip()]
    text = str(value).strip()
    return [text] if text else []

def _dedupe(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out
