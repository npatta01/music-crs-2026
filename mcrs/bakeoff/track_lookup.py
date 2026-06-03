"""Lightweight track-metadata lookup for the response bake-off.

Provides `id_to_metadata(track_id) -> str`, the interface `chat_history_parser`
(mcrs/inference_utils.py) expects on `music_crs.item_db`. Backed by the HF
`TalkPlayData-Challenge-Track-Metadata` rows so the bake-off does not require a
local LanceDB build. The metadata string carries the track facts the LM needs;
exact formatting need not byte-match the LanceDB catalog.
"""
from __future__ import annotations

from typing import Any, Iterable


def _first(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return str(value[0]).strip() if value else ""
    return str(value).strip() if value is not None else ""


class TrackMetadataLookup:
    def __init__(self, by_id: dict[str, dict]):
        self._by_id = by_id

    @classmethod
    def from_rows(cls, rows: Iterable[dict]) -> "TrackMetadataLookup":
        by_id = {str(r["track_id"]): r for r in rows}
        return cls(by_id)

    @classmethod
    def from_hf(cls, dataset_name: str = "talkpl-ai/TalkPlayData-Challenge-Track-Metadata",
                split: str = "all_tracks") -> "TrackMetadataLookup":
        from datasets import load_dataset
        ds = load_dataset(dataset_name, split=split)
        return cls.from_rows(ds)

    def id_to_metadata(self, track_id: str) -> str:
        meta = self._by_id.get(str(track_id))
        if meta is None:
            return f"track={track_id}"
        title = _first(meta.get("track_name"))
        artist = _first(meta.get("artist_name"))
        album = _first(meta.get("album_name"))
        tags = meta.get("tag_list") or []
        tag_str = ", ".join(str(t) for t in tags if t)
        parts = []
        if title:
            parts.append(f"title: {title}")
        if artist:
            parts.append(f"artist: {artist}")
        if album:
            parts.append(f"album: {album}")
        if tag_str:
            parts.append(f"tags: {tag_str}")
        return " | ".join(parts) if parts else f"track={track_id}"
