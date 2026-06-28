"""Catalog and retrieval probe commands."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from typing import Any

from . import runtime
from .artifacts import catalog_search
from .formatting import _format_track_line, _parse_bm25_fields, _print_json, _track_payload, _write_json


DEFAULT_BM25_FIELDS = "track_name:3,artist_name:3,album_name:2,tag_list:1.5"


def _cmd_track(args: argparse.Namespace) -> int:
    run = runtime._optional_run(args)
    catalog = runtime._load_catalog(run, args)
    rows = catalog.feature_rows()
    out = []
    for query_id in args.track_ids:
        matches = _matching_track_rows(rows, query_id)
        if not matches:
            out.append({"query": query_id, "error": "not found"})
            continue
        for track_id, row in matches:
            out.append(_track_payload(track_id, row))

    if args.format == "json":
        _print_json(out)
        return 0

    for item in out:
        if item.get("error"):
            print(f"{item['query']}: {item['error']}")
        else:
            print(_format_track_line(item))
    return 0

def _cmd_catalog_search(args: argparse.Namespace) -> int:
    if not any((args.track, args.artist, args.album, args.text)):
        raise ValueError("provide at least one of --track, --artist, --album, or --text")
    run = runtime._optional_run(args)
    catalog = runtime._load_catalog(run, args)
    result = catalog_search(
        catalog.feature_rows(),
        track=args.track,
        artist=args.artist,
        album=args.album,
        text=args.text,
        limit=max(int(args.limit), 1),
    )
    if args.format == "json":
        _print_json(result)
        return 0

    for label, hits in (
        ("Exact", result.exact),
        ("Title/Album Only", result.title_or_album_only),
        ("Contains", result.contains),
        ("Text", result.text),
    ):
        print(f"{label}:")
        if not hits:
            print("  (none)")
        for hit in hits:
            print(f"  {_format_track_line(asdict(hit))}")
    return 0

def _cmd_bm25(args: argparse.Namespace) -> int:
    run = runtime._optional_run(args)
    db_uri = str(run.catalog_db_uri if run else args.catalog_db_uri)
    table_name = str(run.catalog_table if run else args.catalog_table)
    fields = _parse_bm25_fields(args.fields)

    from mcrs.lancedb.retriever import LanceDbRetriever
    from mcrs.retrieval_modules.base import FieldQuery

    retriever = LanceDbRetriever.from_retrieval_config(
        {
            "db_uri": db_uri,
            "table_name": table_name,
            "fusion": {"method": "weighted_rrf"},
            "device": "cpu",
        }
    )
    clauses = [FieldQuery(field=field, query=args.query, boost=boost) for field, boost in fields]
    hits = retriever.search(clauses, topk=max(int(args.limit), 1))

    catalog = runtime._load_catalog(run, args)
    rows = catalog.feature_rows()
    payload = [
        {"rank": rank, "track_id": track_id, "score": score, **_track_payload(track_id, rows.get(track_id, {}))}
        for rank, (track_id, score) in enumerate(hits, start=1)
    ]
    if args.format == "json":
        _print_json(payload)
        return 0

    for item in payload:
        print(f"{item['rank']:>2}. {_format_track_line(item)} score={item['score']:.4f}")
    return 0

def _cmd_dense_search(args: argparse.Namespace) -> int:
    query = str(args.query or "").strip()
    if not query:
        raise ValueError("--query must be non-empty")
    config = runtime._load_config_for_args(args)
    run = runtime._optional_run(args)
    encoder = runtime._build_debug_encoder_from_config(
        config,
        str(args.encoder_id),
        allow_cache_write=bool(args.allow_cache_write),
    )
    vectors = encoder.embed_batch([query])
    if not vectors:
        raise ValueError("encoder returned no vectors")
    query_vector = [float(value) for value in vectors[0]]
    retriever = runtime._build_debug_lancedb_retriever(config, run, args)
    hits = retriever.search_embedding(
        query_vector,
        vector_field=str(args.vector_field),
        topk=max(int(args.limit), 1),
        distance_type=str(args.distance_type),
        filter_missing=not bool(args.no_filter_missing),
    )
    catalog = runtime._load_debug_lancedb_catalog(config, run, args)
    rows = catalog.feature_rows()
    payload = {
        "query": query,
        "encoder_id": str(args.encoder_id),
        "vector_field": str(args.vector_field),
        "distance_type": str(args.distance_type),
        "filter_missing": not bool(args.no_filter_missing),
        "hits": [
            {
                "rank": rank,
                "track_id": track_id,
                "score": score,
                **_track_payload(track_id, rows.get(track_id, {})),
            }
            for rank, (track_id, score) in enumerate(hits, start=1)
        ],
    }
    if args.format == "json" or args.out:
        _write_json(payload, args.out)
        return 0
    _print_dense_search(payload)
    return 0

def _print_dense_search(payload: dict[str, Any]) -> None:
    print(f"Query: {payload.get('query')}")
    print(f"Encoder: {payload.get('encoder_id')} -> {payload.get('vector_field')}")
    for item in payload.get("hits") or []:
        print(f"{int(item['rank']):>2}. {_format_track_line(item)} score={float(item['score']):.4f}")

def _matching_track_rows(rows: dict[str, dict[str, Any]], query_id: str) -> list[tuple[str, dict[str, Any]]]:
    if query_id in rows:
        return [(query_id, rows[query_id])]
    matches = [(track_id, row) for track_id, row in rows.items() if str(track_id).startswith(query_id)]
    return sorted(matches, key=lambda item: item[0])
