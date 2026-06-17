"""Shared catalog readers for reranker sidecar scripts."""

from __future__ import annotations


def catalog_artist_ids(db_uri: str, table_name: str = "music_track_catalog") -> dict:
    """Load track_id/artist_id columns without requiring optional pylance."""
    import lancedb

    table = lancedb.connect(db_uri).open_table(table_name)
    columns = ["track_id", "artist_id"]
    try:
        return table.to_lance().to_table(columns=columns).to_pydict()
    except ImportError:
        return table.to_arrow().select(columns).to_pydict()
