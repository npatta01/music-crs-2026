"""Local debug CLI for Music CRS artifacts."""

from __future__ import annotations

import argparse
import copy
import json
import math
import os
import shlex
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from mcrs.debug_tools import (
    DEFAULT_CATALOG_DB_URI,
    DEFAULT_CATALOG_TABLE,
    DEFAULT_RUN_FILE,
    RunArtifacts,
    catalog_search,
    load_audit_index,
    load_prediction_index,
    load_run_aliases,
    resolve_run_alias,
    resolve_session_prefix,
    trace_row,
    trace_session_ids,
    trace_turns,
)


DEFAULT_BM25_FIELDS = "track_name:3,artist_name:3,album_name:2,tag_list:1.5"
_OFFLINE_UNCHANGED = object()


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args) or 0)
    except Exception as exc:  # pragma: no cover - argparse-facing guardrail
        print(f"error: {exc}", file=sys.stderr)
        return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mcrs-debug",
        description="Inspect saved Music CRS traces, audits, predictions, and retrieval probes.",
    )
    parser.add_argument("--run-file", default=DEFAULT_RUN_FILE)
    parser.add_argument("--run")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--catalog-db-uri", default=DEFAULT_CATALOG_DB_URI)
    parser.add_argument("--catalog-table", default=DEFAULT_CATALOG_TABLE)

    sub = parser.add_subparsers(dest="command", required=True)

    session = sub.add_parser("session", help="Show the turns available for one session.")
    session.add_argument("session_id", help="Full session id or unique prefix.")
    session.set_defaults(func=_cmd_session)

    case = sub.add_parser("case", help="Show a focused turn with state, retrieval, and judgment.")
    case.add_argument("session_id", help="Full session id or unique prefix.")
    case.add_argument("turn", type=int)
    case.set_defaults(func=_cmd_case)

    state = sub.add_parser("state", help="Show the extracted/resolved state for one turn.")
    state.add_argument("session_id", help="Full session id or unique prefix.")
    state.add_argument("turn", type=int)
    state.set_defaults(func=_cmd_state)

    track = sub.add_parser("track", help="Show catalog metadata for one or more track ids.")
    track.add_argument("track_ids", nargs="+")
    track.set_defaults(func=_cmd_track)

    search = sub.add_parser("catalog-search", help="Search catalog metadata by exact surface text.")
    search.add_argument("--track")
    search.add_argument("--artist")
    search.add_argument("--album")
    search.add_argument("--text")
    search.add_argument("--limit", type=int, default=25)
    search.set_defaults(func=_cmd_catalog_search)

    bm25 = sub.add_parser("bm25", help="Run an ad hoc BM25 query through the LanceDB retriever.")
    bm25.add_argument("--query", required=True)
    bm25.add_argument("--fields", default=DEFAULT_BM25_FIELDS)
    bm25.add_argument("--limit", type=int, default=20)
    bm25.set_defaults(func=_cmd_bm25)

    dense = sub.add_parser("dense-search", help="Run an ad hoc dense vector search against one LanceDB vector field.")
    _add_config_args(dense)
    dense.add_argument("--query", required=True)
    dense.add_argument("--encoder-id", default="siglip2_text")
    dense.add_argument("--vector-field", default="image_siglip2")
    dense.add_argument("--limit", type=int, default=20)
    dense.add_argument("--distance-type", default="cosine")
    dense.add_argument("--no-filter-missing", action="store_true")
    dense.add_argument(
        "--allow-cache-write",
        action="store_true",
        help="Use the configured encoder cache and allow cache fills; disabled by default.",
    )
    dense.add_argument("--out", help="Write dense-search result JSON to this path; stdout when omitted.")
    dense.set_defaults(func=_cmd_dense_search)

    extract = sub.add_parser("extract-state", help="Extract ConversationState JSON from a conversation file.")
    _add_config_args(extract)
    extract.add_argument("--conversation", required=True, help="JSON conversation/session-memory file.")
    extract.add_argument("--played-track-id", action="append", default=[])
    extract.add_argument("--out", help="Write extracted state JSON to this path; stdout when omitted.")
    extract.set_defaults(func=_cmd_extract_state)

    retrieve = sub.add_parser("retrieve-state", help="Replay retrieval/ranking from an extracted state JSON file.")
    _add_config_args(retrieve)
    retrieve.add_argument("--state", required=True, help="ConversationState JSON to replay.")
    retrieve.add_argument("--conversation", help="Optional JSON session-memory file for played tracks/history.")
    retrieve.add_argument("--played-track-id", action="append", default=[])
    retrieve.add_argument("--latest-user-text", default="")
    retrieve.add_argument("--session-id")
    retrieve.add_argument("--turn", type=int)
    retrieve.add_argument("--user-id")
    retrieve.add_argument("--topk", type=int, default=20)
    retrieve.add_argument(
        "--allow-cache-write",
        action="store_true",
        help="Allow encoder/reranker cache fills while replaying; default avoids cache writes where supported.",
    )
    retrieve.add_argument("--trace-out", help="Write full replay trace JSON to this path; stdout when omitted.")
    retrieve.add_argument("--compiled-out", help="Write replayed compiled_state JSON to this path.")
    retrieve.set_defaults(func=_cmd_retrieve_state)

    replay = sub.add_parser("replay-turn", help="Replay retrieval/ranking from a saved trace row state.")
    _add_config_args(replay)
    replay.add_argument("session_id", help="Full session id or unique prefix.")
    replay.add_argument("turn", type=int)
    replay.add_argument("--state", help="Optional edited state JSON; defaults to trace.extracted_state.")
    replay.add_argument("--played-track-id", action="append", default=[])
    replay.add_argument("--latest-user-text", default="")
    replay.add_argument("--user-id")
    replay.add_argument("--topk", type=int, default=20)
    replay.add_argument(
        "--allow-cache-write",
        action="store_true",
        help="Allow encoder/reranker cache fills while replaying; default avoids cache writes where supported.",
    )
    replay.add_argument("--trace-out", help="Write full replay trace JSON to this path; stdout when omitted.")
    replay.add_argument("--compiled-out", help="Write replayed compiled_state JSON to this path.")
    replay.set_defaults(func=_cmd_replay_turn)

    rerank = sub.add_parser("rerank-subset", help="Replay the LGBM reranker over a supplied candidate subset.")
    _add_config_args(rerank)
    rerank.add_argument("--trace", required=True, help="Trace JSON/JSONL row to rerank.")
    rerank.add_argument("--candidate", action="append", default=[])
    rerank.add_argument("--candidates", help="JSON list or newline-delimited candidate ids.")
    rerank.add_argument("--inject-missing", action="store_true")
    rerank.add_argument("--inject-branch", default="debug_subset")
    rerank.add_argument("--inject-score", type=float, default=1e-9)
    rerank.add_argument("--session-id")
    rerank.add_argument("--turn", type=int)
    rerank.add_argument("--user-id")
    rerank.add_argument("--topk", type=int, default=20)
    rerank.add_argument(
        "--allow-cache-write",
        action="store_true",
        help="Allow live reranker cache fills while replaying; default is offline/cache-only.",
    )
    rerank.add_argument("--out", help="Write rerank result JSON to this path; stdout when omitted.")
    rerank.add_argument("--feature-trace-out", help="Write the subset feature trace passed to reranker.")
    rerank.set_defaults(func=_cmd_rerank_subset)

    features = sub.add_parser("rerank-features", help="Show LGBM feature rows and scores for selected candidates.")
    _add_config_args(features)
    features.add_argument("--trace", required=True, help="Trace JSON/JSONL row to inspect.")
    features.add_argument("--candidate", action="append", default=[])
    features.add_argument("--candidates", help="JSON list or newline-delimited candidate ids.")
    features.add_argument("--inject-missing", action="store_true")
    features.add_argument("--inject-branch", default="debug_subset")
    features.add_argument("--inject-score", type=float, default=1e-9)
    features.add_argument("--session-id")
    features.add_argument("--turn", type=int)
    features.add_argument("--user-id")
    features.add_argument("--contrib", action="store_true", help="Include LightGBM pred_contrib values.")
    features.add_argument("--diff", nargs=2, metavar=("LEFT_TRACK_ID", "RIGHT_TRACK_ID"))
    features.add_argument("--diff-limit", type=int, default=25)
    features.add_argument(
        "--allow-cache-write",
        action="store_true",
        help="Allow live reranker cache fills while computing features; default is offline/cache-only.",
    )
    features.add_argument("--out", help="Write feature payload JSON to this path; stdout when omitted.")
    features.set_defaults(func=_cmd_rerank_features)

    diff = sub.add_parser("diff-trace", help="Compare two traces for state, retrieval, and rank movement.")
    diff.add_argument("before")
    diff.add_argument("after")
    diff.add_argument("--target-track-id")
    diff.set_defaults(func=_cmd_diff_trace)

    bundle = sub.add_parser("bundle-case", help="Write a focused case bundle for manual replay/debugging.")
    bundle.add_argument("session_id", help="Full session id or unique prefix.")
    bundle.add_argument("turn", type=int)
    bundle.add_argument("--out", required=True, help="Output directory for bundle files.")
    bundle.add_argument("--config", help="Config path to include in generated commands.sh.")
    bundle.add_argument("--tid", help="Config tid to include in generated commands.sh.")
    bundle.add_argument("--config-dir", default="configs")
    bundle.add_argument("--target-track-id")
    bundle.set_defaults(func=_cmd_bundle_case)

    target = sub.add_parser("target-audit", help="Audit where a target track appears in catalog/retrieval/ranking.")
    target.add_argument("--trace", required=True)
    target.add_argument("--target-track-id", required=True)
    target.add_argument("--track")
    target.add_argument("--artist")
    target.add_argument("--album")
    target.add_argument("--surface-limit", type=int, default=25)
    target.set_defaults(func=_cmd_target_audit)

    return parser


def _cmd_session(args: argparse.Namespace) -> int:
    run = _require_trace_run(args)
    session_id = _resolve_session(run, args.session_id)
    turns = trace_turns(run.trace, session_id)
    audit = load_audit_index(run.audit)
    rows = [
        {
            "turn_number": turn,
            "latest_user_text": audit.get((session_id, turn), {}).get("latest_user_text", ""),
            "request_type": audit.get((session_id, turn), {}).get("request_type", ""),
        }
        for turn in turns
    ]
    if args.format == "json":
        _print_json({"run": run.name, "session_id": session_id, "turns": rows})
        return 0

    print(f"Run: {run.name}")
    print(f"Session: {session_id}")
    for row in rows:
        label = f"turn {row['turn_number']}"
        if row["request_type"]:
            label += f" | {row['request_type']}"
        if row["latest_user_text"]:
            label += f" | {row['latest_user_text']}"
        print(label)
    return 0


def _cmd_case(args: argparse.Namespace) -> int:
    run = _require_trace_run(args)
    session_id = _resolve_session(run, args.session_id)
    row = trace_row(run.trace, session_id, args.turn)
    key = (session_id, int(args.turn))
    audit_row = load_audit_index(run.audit).get(key, {})
    prediction_row = load_prediction_index(run.prediction).get(key, {})

    payload = {
        "run": run.name,
        "session_id": session_id,
        "turn_number": int(args.turn),
        "trace": row.get("trace") or {},
        "audit": audit_row,
        "prediction": prediction_row,
    }
    if args.format == "json":
        _print_json(payload)
        return 0

    _print_case(payload)
    return 0


def _cmd_state(args: argparse.Namespace) -> int:
    run = _require_trace_run(args)
    session_id = _resolve_session(run, args.session_id)
    row = trace_row(run.trace, session_id, args.turn)
    trace = row.get("trace") or {}
    payload = {
        "session_id": session_id,
        "turn_number": int(args.turn),
        "extracted_state": trace.get("extracted_state") or {},
        "compiled_state": trace.get("compiled_state") or {},
        "resolver": trace.get("resolver") or {},
        "routing_tags": trace.get("routing_tags") or {},
    }
    if args.format == "json":
        _print_json(payload)
        return 0

    print(f"Session: {session_id}")
    print(f"Turn: {args.turn}")
    _print_block("Extracted State", payload["extracted_state"])
    _print_block("Compiled State", payload["compiled_state"])
    _print_block("Resolver", payload["resolver"])
    _print_block("Routing Tags", payload["routing_tags"])
    return 0


def _cmd_track(args: argparse.Namespace) -> int:
    run = _optional_run(args)
    catalog = _load_catalog(run, args)
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
    run = _optional_run(args)
    catalog = _load_catalog(run, args)
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
    run = _optional_run(args)
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

    catalog = _load_catalog(run, args)
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
    config = _load_config_for_args(args)
    run = _optional_run(args)
    encoder = _build_debug_encoder_from_config(
        config,
        str(args.encoder_id),
        allow_cache_write=bool(args.allow_cache_write),
    )
    vectors = encoder.embed_batch([query])
    if not vectors:
        raise ValueError("encoder returned no vectors")
    query_vector = [float(value) for value in vectors[0]]
    retriever = _build_debug_lancedb_retriever(config, run, args)
    hits = retriever.search_embedding(
        query_vector,
        vector_field=str(args.vector_field),
        topk=max(int(args.limit), 1),
        distance_type=str(args.distance_type),
        filter_missing=not bool(args.no_filter_missing),
    )
    catalog = _load_debug_lancedb_catalog(config, run, args)
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


def _cmd_extract_state(args: argparse.Namespace) -> int:
    config = _load_config_for_args(args)
    conversation, played = _extract_conversation_and_played(
        args.conversation,
        extra_played=args.played_track_id,
    )
    extractor = _build_extractor_from_config(config)
    state = extractor.extract(conversation, played)
    if state is None:
        raise ValueError("extractor returned None")
    payload = state.model_dump(mode="json") if hasattr(state, "model_dump") else state
    _write_json(payload, args.out)
    return 0


def _cmd_retrieve_state(args: argparse.Namespace) -> int:
    state = _load_state(args.state)
    trace = _retrieve_state_trace(
        args,
        state,
        played_track_ids=args.played_track_id,
        latest_user_text=args.latest_user_text,
        session_id=args.session_id,
        turn_number=args.turn,
        user_id=args.user_id,
        conversation_path=args.conversation,
        source_meta=None,
    )
    _write_replay_outputs(trace, args.trace_out, args.compiled_out)
    return 0


def _cmd_replay_turn(args: argparse.Namespace) -> int:
    run = _require_trace_run(args)
    session_id = _resolve_session(run, args.session_id)
    row = trace_row(run.trace, session_id, args.turn)
    trace = row.get("trace") or {}
    if args.state:
        state = _load_state(args.state)
    else:
        raw_state = trace.get("extracted_state") or trace.get("state")
        if not isinstance(raw_state, dict):
            raise ValueError("trace row does not contain extracted_state; pass --state")
        state = _state_from_dict(raw_state)
    resolver = trace.get("resolver") if isinstance(trace.get("resolver"), dict) else {}
    played = args.played_track_id or [str(x) for x in resolver.get("played_track_ids") or []]
    user_id = args.user_id or row.get("user_id")
    latest_user_text = args.latest_user_text
    if not latest_user_text and run.audit is not None:
        audit = load_audit_index(run.audit).get((session_id, int(args.turn)), {})
        latest_user_text = str(audit.get("latest_user_text") or "")
    replayed = _retrieve_state_trace(
        args,
        state,
        played_track_ids=played,
        latest_user_text=latest_user_text,
        session_id=session_id,
        turn_number=int(args.turn),
        user_id=str(user_id) if user_id else None,
        conversation_path=None,
        source_meta={**trace, **row},
    )
    _write_replay_outputs(replayed, args.trace_out, args.compiled_out)
    return 0


def _cmd_rerank_subset(args: argparse.Namespace) -> int:
    wrapper, trace = _load_trace_document(args.trace)
    candidate_ids = _load_candidate_ids(args.candidate, args.candidates)
    if not candidate_ids:
        raise ValueError("provide at least one --candidate or --candidates file")
    feature_trace, injected = _subset_feature_trace(
        trace,
        candidate_ids,
        inject_missing=args.inject_missing,
        inject_branch=args.inject_branch,
        inject_score=float(args.inject_score),
    )
    config = _debug_config_for_cache_policy(
        _load_config_for_args(args),
        allow_cache_write=bool(args.allow_cache_write),
    )
    qu = _build_state_ranker_from_config(config)
    get_reranker = getattr(qu, "_get_reranker", None)
    reranker = get_reranker() if callable(get_reranker) else getattr(qu, "reranker", None)
    if reranker is None:
        raise ValueError("configured state ranker does not expose a reranker")
    session_meta = _session_meta_from_wrapper(wrapper, args.session_id, args.turn)
    user_id = args.user_id or wrapper.get("user_id")
    hard_drop = _hard_drop_ids(feature_trace)
    previous_policy = _set_reranker_debug_policy(
        reranker,
        allow_cache_write=bool(args.allow_cache_write),
    )
    try:
        ranked = reranker.rerank(
            feature_trace,
            session_meta,
            str(user_id) if user_id else None,
            hard_drop,
            candidate_ids,
        )
    finally:
        _restore_reranker_debug_policy(reranker, previous_policy)
    payload = {
        "candidate_ids": candidate_ids,
        "ranked_track_ids": list(ranked)[: max(int(args.topk), 1)],
        "injected_missing_ids": injected,
        "session_meta": session_meta,
    }
    if args.feature_trace_out:
        _write_json(feature_trace, args.feature_trace_out)
    _write_json(payload, args.out)
    return 0


def _cmd_rerank_features(args: argparse.Namespace) -> int:
    wrapper, trace = _load_trace_document(args.trace)
    candidate_ids = _load_candidate_ids(args.candidate, args.candidates)
    if not candidate_ids and args.diff:
        candidate_ids = list(args.diff)
    if not candidate_ids:
        raise ValueError("provide at least one --candidate, --candidates file, or --diff pair")
    feature_trace, injected = _subset_feature_trace(
        trace,
        candidate_ids,
        inject_missing=args.inject_missing,
        inject_branch=args.inject_branch,
        inject_score=float(args.inject_score),
    )
    config = _debug_config_for_cache_policy(
        _load_config_for_args(args),
        allow_cache_write=bool(args.allow_cache_write),
    )
    qu = _build_state_ranker_from_config(config)
    get_reranker = getattr(qu, "_get_reranker", None)
    reranker = get_reranker() if callable(get_reranker) else getattr(qu, "reranker", None)
    if reranker is None:
        raise ValueError("configured state ranker does not expose a reranker")
    session_meta = _session_meta_from_wrapper(wrapper, args.session_id, args.turn)
    user_id = args.user_id or wrapper.get("user_id")
    hard_drop = _hard_drop_ids(feature_trace)
    previous_policy = _set_reranker_debug_policy(
        reranker,
        allow_cache_write=bool(args.allow_cache_write),
    )
    try:
        computed = _compute_rerank_feature_payload(
            reranker,
            feature_trace,
            session_meta,
            str(user_id) if user_id else None,
            hard_drop,
            bool(args.contrib),
        )
    finally:
        _restore_reranker_debug_policy(reranker, previous_policy)
    candidates = [dict(item) for item in computed.get("candidates") or []]
    candidates.sort(key=_rerank_score_sort_key, reverse=True)
    for rank, item in enumerate(candidates, start=1):
        item["rerank_rank"] = rank
    candidates_by_id = {str(item.get("track_id")): item for item in candidates}
    payload = {
        "candidate_ids": candidate_ids,
        "ranked_track_ids": [str(item.get("track_id")) for item in candidates],
        "columns": list(computed.get("columns") or []),
        "candidates": candidates,
        "candidates_by_id": candidates_by_id,
        "injected_missing_ids": injected,
        "session_meta": session_meta,
    }
    if args.diff:
        payload["diff"] = _rerank_feature_diff(
            candidates_by_id,
            args.diff[0],
            args.diff[1],
            columns=payload["columns"],
            limit=max(int(args.diff_limit), 1),
        )
    _write_json(payload, args.out)
    return 0


def _compute_rerank_feature_payload(
    reranker: Any,
    feature_trace: dict[str, Any],
    session_meta: dict[str, Any] | None,
    user_id: str | None,
    hard_drop: set[str],
    include_contrib: bool,
) -> dict[str, Any]:
    rows = _compute_rerank_feature_rows(reranker, feature_trace, session_meta, user_id, hard_drop)
    cols = list(getattr(reranker, "cols", []) or [])
    if not rows:
        return {"columns": cols, "candidates": []}
    assemble = getattr(reranker, "_assemble", None)
    booster = getattr(reranker, "booster", None)
    if not callable(assemble) or booster is None or not callable(getattr(booster, "predict", None)):
        raise ValueError("configured reranker does not expose _assemble() and booster.predict()")
    matrix = assemble(rows)
    matrix_rows = _matrix_rows(matrix)
    scores = list(booster.predict(matrix))
    if include_contrib:
        raw_contrib = booster.predict(matrix, pred_contrib=True)
        contrib_rows = [list(row) for row in raw_contrib]
    else:
        contrib_rows = [None] * len(rows)

    candidates = []
    for row_index, (row, score, contrib) in enumerate(zip(rows, scores, contrib_rows)):
        encoded_values = matrix_rows[row_index] if row_index < len(matrix_rows) else []
        model_features = {
            col: _debug_json_value(encoded_values[idx])
            for idx, col in enumerate(cols)
            if idx < len(encoded_values)
        }
        raw_model_features = {col: _debug_json_value(row.get(col)) for col in cols}
        item = {
            "track_id": str(row.get("track_id")),
            "rerank_score": _debug_json_value(_finite_float(score)),
            "features": _debug_json_value(row),
            "model_features": model_features,
            "raw_model_features": raw_model_features,
        }
        if contrib is not None:
            values = list(contrib)
            contrib_payload = {
                col: _debug_json_value(_finite_float(values[idx]))
                for idx, col in enumerate(cols)
                if idx < len(values)
            }
            if len(values) > len(cols):
                contrib_payload["bias"] = _debug_json_value(_finite_float(values[len(cols)]))
            item["contrib"] = contrib_payload
        candidates.append(item)
    return {"columns": cols, "candidates": candidates}


def _matrix_rows(matrix: Any) -> list[list[Any]]:
    values = matrix.tolist() if hasattr(matrix, "tolist") else matrix
    return [list(row) for row in values]


class _ReadOnlyCachedTextEmbedder:
    def __init__(self, wrapped: Any) -> None:
        self._store = wrapped._store
        self._namespace = wrapped._namespace

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        from mcrs.embeddings.embedding_cache import make_key

        out: list[list[float]] = []
        missing: list[str] = []
        for text in texts:
            hit = self._store.get(make_key(self._namespace, text))
            if hit is None:
                missing.append(text)
                continue
            out.append(hit)
        if missing:
            raise ValueError(
                "read-only debug mode found missing b1 query embedding cache entries; "
                "rerun with --allow-cache-write to allow live fills"
            )
        return out


def _set_reranker_debug_policy(reranker: Any, *, allow_cache_write: bool) -> dict[str, Any]:
    previous: dict[str, Any] = {
        "offline": _set_reranker_offline(reranker, offline=not allow_cache_write),
        "b1_enc": _OFFLINE_UNCHANGED,
    }
    if allow_cache_write:
        return previous
    b1 = getattr(reranker, "b1", None)
    enc = getattr(b1, "enc", None)
    if enc is not None and all(hasattr(enc, attr) for attr in ("_store", "_namespace")):
        previous["b1_enc"] = enc
        b1.enc = _ReadOnlyCachedTextEmbedder(enc)
    return previous


def _restore_reranker_debug_policy(reranker: Any, previous: dict[str, Any]) -> None:
    _restore_reranker_offline(reranker, previous.get("offline", _OFFLINE_UNCHANGED))
    b1_enc = previous.get("b1_enc", _OFFLINE_UNCHANGED)
    if b1_enc is not _OFFLINE_UNCHANGED:
        b1 = getattr(reranker, "b1", None)
        if b1 is not None:
            b1.enc = b1_enc


def _set_reranker_offline(reranker: Any, *, offline: bool) -> Any:
    ctx = getattr(reranker, "ctx", None)
    if ctx is None or not hasattr(ctx, "offline"):
        return _OFFLINE_UNCHANGED
    previous = getattr(ctx, "offline")
    setattr(ctx, "offline", bool(offline))
    return previous


def _restore_reranker_offline(reranker: Any, previous: Any) -> None:
    if previous is _OFFLINE_UNCHANGED:
        return
    ctx = getattr(reranker, "ctx", None)
    if ctx is not None:
        setattr(ctx, "offline", previous)


def _compute_rerank_feature_rows(
    reranker: Any,
    feature_trace: dict[str, Any],
    session_meta: dict[str, Any] | None,
    user_id: str | None,
    hard_drop: set[str],
) -> list[dict[str, Any]]:
    from mcrs.qu_modules.lgbm_reranker import session_entry_from_meta

    from build_features import constraint_feature_row
    from features_v9 import compute_turn_features

    ctx = getattr(reranker, "ctx", None)
    if ctx is None:
        raise ValueError("configured reranker does not expose ctx")
    dropped = {str(track_id) for track_id in hard_drop}
    sid = str((session_meta or {}).get("session_id") or "")
    tn = int((session_meta or {}).get("turn_number") or 0)
    if session_meta:
        ctx.sessions[sid] = session_entry_from_meta(session_meta)
    trace_for_features = feature_trace
    if dropped:
        branches = dict(feature_trace.get("branches") or {})
        existing_drop = {str(track_id) for track_id in branches.get("hard_drop") or []}
        branches["hard_drop"] = sorted(existing_drop | dropped)
        trace_for_features = {**feature_trace, "branches": branches}
    row = {"session_id": sid, "turn_number": tn, "user_id": user_id, "trace": trace_for_features}
    b1 = getattr(reranker, "b1", None)
    if b1 is not None:
        session_entry = ctx.sessions.get(sid)
        if session_entry is not None:
            row["b1_qvec"] = b1.query_vecs([b1.query_text(session_entry, tn)])[0]
    rows, _ = compute_turn_features(row, ctx, gt=None)
    if not rows:
        return []

    resolver = feature_trace.get("resolver") or {}
    played = frozenset(str(x) for x in resolver.get("played_track_ids") or [])
    rejected_tracks = frozenset(str(x) for x in resolver.get("rejected_track_ids") or [])
    rejected_artists = frozenset(str(x) for x in resolver.get("rejected_artist_ids") or [])
    for feature_row in rows:
        track_id = str(feature_row.get("track_id"))
        artists = ctx.cat.meta.get(track_id, {}).get("artists", ())
        feature_row.update(
            constraint_feature_row(
                track_id,
                artists,
                played=played,
                rejected_tracks=rejected_tracks,
                rejected_artists=rejected_artists,
                target_artist_mode=feature_row.get("target_artist_mode"),
                same_artist_session=feature_row.get("same_artist_session"),
            )
        )
    return rows


def _rerank_score_sort_key(item: dict[str, Any]) -> float:
    value = _finite_float(item.get("rerank_score"))
    return value if value is not None else float("-inf")


def _finite_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _debug_json_value(value: Any) -> Any:
    item = getattr(value, "item", None)
    if callable(item):
        try:
            value = item()
        except Exception:
            pass
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(k): _debug_json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_debug_json_value(v) for v in value]
    return str(value)


def _rerank_feature_diff(
    candidates_by_id: dict[str, dict[str, Any]],
    left_track_id: str,
    right_track_id: str,
    *,
    columns: list[str],
    limit: int,
) -> dict[str, Any]:
    left = candidates_by_id.get(str(left_track_id))
    right = candidates_by_id.get(str(right_track_id))
    if left is None or right is None:
        missing = [track_id for track_id, item in ((left_track_id, left), (right_track_id, right)) if item is None]
        raise ValueError(f"diff candidate(s) missing from feature rows: {', '.join(missing)}")
    left_features = left.get("model_features") or {}
    right_features = right.get("model_features") or {}
    feature_order = list(columns) if columns else sorted(set(left_features) | set(right_features))
    rows = []
    for feature in feature_order:
        left_value = _finite_float(left_features.get(feature))
        right_value = _finite_float(right_features.get(feature))
        if left_value is None or right_value is None:
            continue
        delta = left_value - right_value
        if delta == 0.0:
            continue
        rows.append(
            {
                "feature": feature,
                "left": left_value,
                "right": right_value,
                "delta": delta,
                "abs_delta": abs(delta),
            }
        )
    rows.sort(key=lambda row: (-row["abs_delta"], row["feature"]))
    return {
        "left_track_id": str(left_track_id),
        "right_track_id": str(right_track_id),
        "left_score": left.get("rerank_score"),
        "right_score": right.get("rerank_score"),
        "left_rank": left.get("rerank_rank"),
        "right_rank": right.get("rerank_rank"),
        "features": rows[:limit],
    }


def _cmd_diff_trace(args: argparse.Namespace) -> int:
    _, before = _load_trace_document(args.before)
    _, after = _load_trace_document(args.after)
    payload = _trace_diff(before, after, target_track_id=args.target_track_id)
    if args.format == "json":
        _print_json(payload)
    else:
        _print_trace_diff(payload)
    return 0


def _load_trace_document(path: str | Path) -> tuple[dict[str, Any], dict[str, Any]]:
    raw_text = Path(path).read_text(encoding="utf-8").strip()
    if not raw_text:
        raise ValueError(f"empty trace file: {path}")
    if raw_text.startswith("{"):
        doc = json.loads(raw_text)
    else:
        first = next((line for line in raw_text.splitlines() if line.strip()), "")
        doc = json.loads(first)
    if not isinstance(doc, dict):
        raise ValueError(f"trace file must contain a JSON object: {path}")
    trace = doc.get("trace") if isinstance(doc.get("trace"), dict) else doc
    return doc, trace


def _load_candidate_ids(inline: list[str], path: str | None) -> list[str]:
    values: list[str] = [str(item) for item in inline or []]
    if path:
        text = Path(path).read_text(encoding="utf-8").strip()
        if text:
            if text.startswith("["):
                data = json.loads(text)
                if not isinstance(data, list):
                    raise ValueError("--candidates JSON must be a list")
                values.extend(str(item) for item in data)
            else:
                values.extend(line.strip() for line in text.splitlines())
    return _dedupe(values)


def _feature_trace_for_reranker(trace: dict[str, Any]) -> dict[str, Any]:
    out = dict(trace)
    branches = trace.get("branches")
    if isinstance(branches, dict) and branches.get("pools") is not None:
        out["branches"] = dict(branches)
    else:
        retrieval = trace.get("retrieval") or {}
        ranking = trace.get("ranking") or {}
        stages = ranking.get("stages") or []
        candidate_stage = next(
            (stage for stage in stages if isinstance(stage, dict) and stage.get("name") == "candidate_fusion"),
            stages[0] if stages else {},
        )
        fused = candidate_stage.get("scores")
        if fused is None:
            fused = [
                [track_id, 1.0 / rank]
                for rank, track_id in enumerate(candidate_stage.get("track_ids") or [], 1)
            ]
        out["branches"] = {
            "pools": list(retrieval.get("branches") or []),
            "branch_queries": dict(retrieval.get("branch_queries") or {}),
            "fused": list(fused or []),
        }
    state = trace.get("state") or trace.get("extracted_state") or {}
    compiled_state = trace.get("compiled_state") or {}
    out.setdefault("state", state)
    out.setdefault(
        "routing_tags",
        trace.get("routing_tags") or state.get("routing_tags") or compiled_state.get("routing_tags") or {},
    )
    out.setdefault(
        "intent_mode",
        trace.get("intent_mode") or state.get("intent_mode") or compiled_state.get("intent_mode") or "",
    )
    return out


def _subset_feature_trace(
    trace: dict[str, Any],
    candidate_ids: list[str],
    *,
    inject_missing: bool,
    inject_branch: str,
    inject_score: float,
) -> tuple[dict[str, Any], list[str]]:
    feature_trace = _feature_trace_for_reranker(trace)
    branches = dict(feature_trace.get("branches") or {})
    candidate_set = set(candidate_ids)
    present: set[str] = set()
    pools = []
    for pool in branches.get("pools") or []:
        if not isinstance(pool, dict):
            continue
        hits = []
        for hit in pool.get("hits") or []:
            track_id = _scored_track_id(hit)
            if track_id in candidate_set:
                hits.append(hit)
                present.add(track_id)
        pools.append({**pool, "hits": hits})
    fused = []
    for item in branches.get("fused") or []:
        track_id = _scored_track_id(item)
        if track_id in candidate_set:
            fused.append(item)
            present.add(track_id)
    missing = [track_id for track_id in candidate_ids if track_id not in present]
    if inject_missing and missing:
        target_pool = next((pool for pool in pools if pool.get("name") == inject_branch), None)
        if target_pool is None:
            target_pool = {"name": inject_branch, "hits": []}
            pools.append(target_pool)
        target_pool["hits"] = list(target_pool.get("hits") or []) + [
            [track_id, float(inject_score)] for track_id in missing
        ]
        fused.extend([track_id, float(inject_score)] for track_id in missing)
    branches["pools"] = pools
    branches["fused"] = fused
    feature_trace["branches"] = branches
    return feature_trace, missing if inject_missing else []


def _scored_track_id(item: Any) -> str | None:
    if isinstance(item, (list, tuple)) and item:
        return str(item[0])
    if isinstance(item, dict):
        value = item.get("track_id") or item.get("id")
        return str(value) if value is not None else None
    return None


def _session_meta_from_wrapper(
    wrapper: dict[str, Any],
    session_id: str | None,
    turn_number: int | None,
) -> dict[str, Any] | None:
    sid = session_id or wrapper.get("session_id")
    turn = turn_number if turn_number is not None else wrapper.get("turn_number")
    if sid is None and turn is None:
        return None
    out = {"session_id": str(sid or ""), "turn_number": int(turn or 0)}
    for key in (
        "conversation",
        "conversations",
        "messages",
        "session_memory",
        "listener_profile",
        "listener_goal",
        "user_profile",
        "conversation_goal",
        "session_date",
    ):
        if key in wrapper:
            out[key] = wrapper[key]
    return out


def _hard_drop_ids(trace: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for source in (trace.get("retrieval") or {}, trace.get("branches") or {}):
        out.update(str(track_id) for track_id in source.get("hard_drop") or [])
    return out


def _trace_diff(
    before: dict[str, Any],
    after: dict[str, Any],
    *,
    target_track_id: str | None,
) -> dict[str, Any]:
    before_branches = _branch_summary(before)
    after_branches = _branch_summary(after)
    before_ranks = _stage_ranks(before)
    after_ranks = _stage_ranks(after)
    return {
        "extracted_state_changes": _object_changes(
            before.get("extracted_state") or before.get("state") or {},
            after.get("extracted_state") or after.get("state") or {},
        ),
        "compiled_state_changes": _object_changes(
            before.get("compiled_state") or {},
            after.get("compiled_state") or {},
        ),
        "branch_changes": {
            "added": sorted(set(after_branches) - set(before_branches)),
            "removed": sorted(set(before_branches) - set(after_branches)),
            "hit_count_delta": {
                name: int(after_branches.get(name, 0)) - int(before_branches.get(name, 0))
                for name in sorted(set(before_branches) | set(after_branches))
                if int(after_branches.get(name, 0)) != int(before_branches.get(name, 0))
            },
        },
        "rank_changes": _rank_position_changes(before_ranks, after_ranks),
        "target_rank_changes": _target_rank_changes(before_ranks, after_ranks, target_track_id),
        "final_added": [
            track_id for track_id in _final_track_ids(after) if track_id not in set(_final_track_ids(before))
        ],
        "final_removed": [
            track_id for track_id in _final_track_ids(before) if track_id not in set(_final_track_ids(after))
        ],
    }


def _object_changes(before: Any, after: Any) -> list[dict[str, Any]]:
    b = _flatten_json(before)
    a = _flatten_json(after)
    changes = []
    for path in sorted(set(b) | set(a)):
        if b.get(path) != a.get(path):
            changes.append({"path": path, "before": b.get(path), "after": a.get(path)})
    return changes


def _flatten_json(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            out.update(_flatten_json(child, child_prefix))
        return out
    return {prefix or "$": _jsonable(value)}


def _branch_summary(trace: dict[str, Any]) -> dict[str, int]:
    retrieval = trace.get("retrieval") or {}
    out: dict[str, int] = {}
    for branch in retrieval.get("branches") or []:
        if isinstance(branch, dict):
            name = str(branch.get("name") or "")
            if name:
                out[name] = len(branch.get("hits") or [])
    for name, status in (retrieval.get("branch_status") or {}).items():
        if isinstance(status, dict):
            out.setdefault(str(name), int(status.get("n_raw_hits") or 0))
    return out


def _stage_ranks(trace: dict[str, Any]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    ranking = trace.get("ranking") or {}
    for stage in ranking.get("stages") or []:
        if isinstance(stage, dict):
            ids = [str(track_id) for track_id in stage.get("track_ids") or []]
            if stage.get("name"):
                out[str(stage["name"])] = {track_id: rank for rank, track_id in enumerate(ids, 1)}
    final_ids = _final_track_ids(trace)
    if final_ids:
        out["final"] = {track_id: rank for rank, track_id in enumerate(final_ids, 1)}
    return out


def _final_track_ids(trace: dict[str, Any]) -> list[str]:
    final = trace.get("final_recommendation") or {}
    if isinstance(final, dict) and final.get("track_ids"):
        return [str(track_id) for track_id in final.get("track_ids") or []]
    stages = (trace.get("ranking") or {}).get("stages") or []
    if stages:
        last = stages[-1]
        if isinstance(last, dict):
            return [str(track_id) for track_id in last.get("track_ids") or []]
    return []


def _rank_position_changes(
    before: dict[str, dict[str, int]],
    after: dict[str, dict[str, int]],
) -> dict[str, dict[str, dict[str, int | None]]]:
    out: dict[str, dict[str, dict[str, int | None]]] = {}
    for stage in sorted(set(before) | set(after)):
        b = before.get(stage, {})
        a = after.get(stage, {})
        stage_changes = {}
        for track_id in sorted(set(b) | set(a)):
            if b.get(track_id) != a.get(track_id):
                stage_changes[track_id] = {"before": b.get(track_id), "after": a.get(track_id)}
        if stage_changes:
            out[stage] = stage_changes
    return out


def _target_rank_changes(
    before: dict[str, dict[str, int]],
    after: dict[str, dict[str, int]],
    target_track_id: str | None,
) -> dict[str, dict[str, int | None]]:
    if not target_track_id:
        return {}
    target = str(target_track_id)
    return {
        stage: {"before": before.get(stage, {}).get(target), "after": after.get(stage, {}).get(target)}
        for stage in sorted(set(before) | set(after))
        if before.get(stage, {}).get(target) != after.get(stage, {}).get(target)
    }


def _print_trace_diff(payload: dict[str, Any]) -> None:
    print("Trace Diff")
    for label, key in (("Extracted State", "extracted_state_changes"), ("Compiled State", "compiled_state_changes")):
        changes = payload.get(key) or []
        print(f"{label}: {len(changes)} changes")
        for change in changes[:20]:
            print(f"  {change['path']}: {change.get('before')!r} -> {change.get('after')!r}")
    branch = payload.get("branch_changes") or {}
    print(f"Branches added: {branch.get('added') or []}")
    print(f"Branches removed: {branch.get('removed') or []}")
    if branch.get("hit_count_delta"):
        print(f"Branch hit deltas: {branch['hit_count_delta']}")
    if payload.get("target_rank_changes"):
        print("Target rank changes:")
        for stage, change in payload["target_rank_changes"].items():
            print(f"  {stage}: {change.get('before')} -> {change.get('after')}")
    print(f"Final added: {payload.get('final_added') or []}")
    print(f"Final removed: {payload.get('final_removed') or []}")


def _cmd_bundle_case(args: argparse.Namespace) -> int:
    run = _require_trace_run(args)
    session_id = _resolve_session(run, args.session_id)
    row = trace_row(run.trace, session_id, args.turn)
    trace = row.get("trace") or {}
    audit = load_audit_index(run.audit).get((session_id, int(args.turn)), {})
    prediction = load_prediction_index(run.prediction).get((session_id, int(args.turn)), {})

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    state = trace.get("extracted_state") or trace.get("state") or {}
    compiled = trace.get("compiled_state") or {}
    candidates = _candidate_ids_from_trace(trace)
    top20 = _top20_from_trace_or_audit(trace, audit)
    conversation = _bundle_conversation(row, trace, audit)

    _write_json(state, str(out_dir / "state.json"))
    _write_json(compiled, str(out_dir / "compiled.json"))
    _write_json(trace, str(out_dir / "trace.json"))
    _write_json(conversation, str(out_dir / "conversation.json"))
    _write_json(top20, str(out_dir / "top20.json"))
    _write_json(
        {
            "session_id": session_id,
            "turn_number": int(args.turn),
            "user_id": row.get("user_id"),
            "audit": audit,
            "prediction": prediction,
        },
        str(out_dir / "case.json"),
    )
    (out_dir / "candidates.txt").write_text("\n".join(candidates) + ("\n" if candidates else ""), encoding="utf-8")
    (out_dir / "commands.sh").write_text(
        _bundle_commands(args, session_id=session_id, turn_number=int(args.turn), user_id=row.get("user_id")),
        encoding="utf-8",
    )
    print(f"Wrote case bundle to {out_dir}")
    return 0


def _cmd_target_audit(args: argparse.Namespace) -> int:
    _, trace = _load_trace_document(args.trace)
    catalog = _load_catalog(_optional_run(args), args)
    rows = catalog.feature_rows()
    payload = _target_audit_payload(
        trace,
        rows,
        target_track_id=args.target_track_id,
        track=args.track,
        artist=args.artist,
        album=args.album,
        surface_limit=max(int(args.surface_limit), 1),
    )
    if args.format == "json":
        _print_json(payload)
    else:
        _print_target_audit(payload)
    return 0


def _bundle_conversation(
    row: dict[str, Any],
    trace: dict[str, Any],
    audit: dict[str, Any],
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for holder in (row, trace, audit):
        if not isinstance(holder, dict):
            continue
        for key in (
            "conversations",
            "user_profile",
            "conversation_goal",
            "session_date",
            "session_memory",
            "conversation",
            "messages",
        ):
            value = holder.get(key)
            if key not in payload and value not in (None, ""):
                payload[key] = value
    if any(isinstance(payload.get(key), list) for key in ("conversations", "session_memory", "conversation", "messages")):
        return payload

    resolver = trace.get("resolver") if isinstance(trace.get("resolver"), dict) else {}
    played = [str(track_id) for track_id in resolver.get("played_track_ids") or []]
    latest_user = str(audit.get("latest_user_text") or "")
    session_memory = [{"role": "music", "content": track_id} for track_id in played]
    if latest_user:
        session_memory.append({"role": "user", "content": latest_user})
    payload.update({
        "latest_user_text": latest_user,
        "played_track_ids": played,
        "session_memory": session_memory,
    })
    return payload


def _candidate_ids_from_trace(trace: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    ranking = trace.get("ranking") or {}
    stages = ranking.get("stages") or []
    candidate_stage = next(
        (stage for stage in stages if isinstance(stage, dict) and stage.get("name") == "candidate_fusion"),
        None,
    )
    if isinstance(candidate_stage, dict):
        ids.extend(str(track_id) for track_id in candidate_stage.get("track_ids") or [])
    for stage in stages:
        if isinstance(stage, dict):
            ids.extend(str(track_id) for track_id in stage.get("track_ids") or [])
    for track_id in _final_track_ids(trace):
        ids.append(track_id)
    feature_trace = _feature_trace_for_reranker(trace)
    for item in (feature_trace.get("branches") or {}).get("fused") or []:
        track_id = _scored_track_id(item)
        if track_id:
            ids.append(track_id)
    return _dedupe(ids)


def _top20_from_trace_or_audit(trace: dict[str, Any], audit: dict[str, Any]) -> list[dict[str, Any]]:
    items = audit.get("items") if isinstance(audit.get("items"), list) else []
    if items:
        out = []
        for item in items[:20]:
            track = item.get("track") if isinstance(item.get("track"), dict) else {}
            out.append({
                "rank": item.get("rank"),
                **_track_payload(str(track.get("track_id") or ""), track),
            })
        return out
    return [
        {"rank": rank, "track_id": track_id}
        for rank, track_id in enumerate(_final_track_ids(trace)[:20], 1)
    ]


def _bundle_commands(
    args: argparse.Namespace,
    *,
    session_id: str,
    turn_number: int,
    user_id: Any,
) -> str:
    config_args = _bundle_config_args(args)
    target = f" --target-track-id {shlex.quote(str(args.target_track_id))}" if args.target_track_id else ""
    user = f" --user-id {shlex.quote(str(user_id))}" if user_id else ""
    sid = shlex.quote(str(session_id))
    turn = shlex.quote(str(turn_number))
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        f"mcrs-debug retrieve-state {config_args} --state state.json --conversation conversation.json --session-id {sid} --turn {turn}{user} --trace-out replay_trace.json --compiled-out replay_compiled.json",
        f"mcrs-debug --format json diff-trace trace.json replay_trace.json{target} > trace_diff.json",
        f"mcrs-debug --format json target-audit --trace replay_trace.json{target} > target_audit.json",
        f"mcrs-debug rerank-subset {config_args} --trace replay_trace.json --candidates candidates.txt --session-id {sid} --turn {turn}{user} --out rerank_subset.json",
        f"mcrs-debug rerank-features {config_args} --trace replay_trace.json --candidates candidates.txt --session-id {sid} --turn {turn}{user} --contrib --out rerank_features.json",
    ]
    return "\n".join(lines) + "\n"


def _bundle_config_args(args: argparse.Namespace) -> str:
    if getattr(args, "config", None):
        return f"--config {shlex.quote(str(args.config))}"
    if getattr(args, "tid", None):
        return f"--tid {shlex.quote(str(args.tid))} --config-dir {shlex.quote(str(args.config_dir))}"
    return "--config ${CONFIG:?set CONFIG to a state-ranker config path}"


def _target_audit_payload(
    trace: dict[str, Any],
    rows: dict[str, dict[str, Any]],
    *,
    target_track_id: str,
    track: str | None,
    artist: str | None,
    album: str | None,
    surface_limit: int,
) -> dict[str, Any]:
    target = str(target_track_id)
    target_row = rows.get(target)
    surface = catalog_search(
        rows,
        track=track,
        artist=artist,
        album=album,
        limit=surface_limit,
    ) if any((track, artist, album)) else None
    branch_ranks, branch_scores = _target_branch_positions(trace, target)
    stage_ranks = {
        stage: ranks[target]
        for stage, ranks in _stage_ranks(trace).items()
        if target in ranks and stage != "final"
    }
    final_rank = _stage_ranks(trace).get("final", {}).get(target)
    hard_sources = _hard_drop_sources(trace, target)
    resolver = trace.get("resolver") if isinstance(trace.get("resolver"), dict) else {}
    candidate_stage_rank = stage_ranks.get("candidate_fusion")
    return {
        "target_track_id": target,
        "catalog": {
            "found": target_row is not None,
            "track": _track_payload(target, target_row) if target_row is not None else None,
            "exact_match_ids": [hit.track_id for hit in surface.exact] if surface else [],
            "title_or_album_only_ids": [hit.track_id for hit in surface.title_or_album_only] if surface else [],
            "contains_ids": [hit.track_id for hit in surface.contains] if surface else [],
        },
        "retrieval": {
            "branch_ranks": branch_ranks,
            "branch_scores": branch_scores,
            "in_any_branch": bool(branch_ranks),
            "fused_rank": _target_fused_rank(trace, target),
        },
        "ranking": {
            "stage_ranks": stage_ranks,
            "final_rank": final_rank,
            "candidate_to_final_delta": (
                None if candidate_stage_rank is None or final_rank is None else final_rank - candidate_stage_rank
            ),
        },
        "policy": {
            "hard_dropped": bool(hard_sources),
            "hard_drop_sources": hard_sources,
            "played": target in {str(x) for x in resolver.get("played_track_ids") or []},
            "rejected_track": target in {str(x) for x in resolver.get("rejected_track_ids") or []},
        },
    }


def _target_branch_positions(trace: dict[str, Any], target: str) -> tuple[dict[str, int], dict[str, float]]:
    ranks: dict[str, int] = {}
    scores: dict[str, float] = {}
    retrieval = trace.get("retrieval") or {}
    for branch in retrieval.get("branches") or []:
        if not isinstance(branch, dict):
            continue
        name = str(branch.get("name") or "")
        if not name:
            continue
        for rank, hit in enumerate(branch.get("hits") or [], 1):
            if _scored_track_id(hit) == target:
                ranks[name] = rank
                score = _scored_score(hit)
                if score is not None:
                    scores[name] = score
                break
    return ranks, scores


def _target_fused_rank(trace: dict[str, Any], target: str) -> int | None:
    feature_trace = _feature_trace_for_reranker(trace)
    fused = (feature_trace.get("branches") or {}).get("fused") or []
    for rank, item in enumerate(fused, 1):
        if _scored_track_id(item) == target:
            return rank
    return None


def _hard_drop_sources(trace: dict[str, Any], target: str) -> list[str]:
    sources: list[str] = []
    for label, source in (("retrieval.hard_drop", trace.get("retrieval") or {}), ("branches.hard_drop", trace.get("branches") or {})):
        if target in {str(track_id) for track_id in source.get("hard_drop") or []}:
            sources.append(label)
    return sources


def _scored_score(item: Any) -> float | None:
    if isinstance(item, (list, tuple)) and len(item) > 1:
        try:
            return float(item[1])
        except (TypeError, ValueError):
            return None
    if isinstance(item, dict) and item.get("score") is not None:
        try:
            return float(item["score"])
        except (TypeError, ValueError):
            return None
    return None


def _print_target_audit(payload: dict[str, Any]) -> None:
    catalog = payload.get("catalog") or {}
    retrieval = payload.get("retrieval") or {}
    ranking = payload.get("ranking") or {}
    policy = payload.get("policy") or {}
    print(f"Target: {payload.get('target_track_id')}")
    print(f"Catalog found: {catalog.get('found')}")
    if catalog.get("track"):
        print(f"Catalog track: {_format_track_line(catalog['track'])}")
    print(f"Exact surface matches: {catalog.get('exact_match_ids') or []}")
    print(f"Branch ranks: {retrieval.get('branch_ranks') or {}}")
    print(f"Fused rank: {retrieval.get('fused_rank')}")
    print(f"Stage ranks: {ranking.get('stage_ranks') or {}}")
    print(f"Final rank: {ranking.get('final_rank')}")
    print(f"Hard dropped: {policy.get('hard_dropped')} {policy.get('hard_drop_sources') or []}")

def _add_config_args(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--config", help="Path to an explicit YAML config.")
    group.add_argument("--tid", help="Task id matching configs/{tid}.yaml.")
    parser.add_argument("--config-dir", default="configs")


def _load_config_for_args(args: argparse.Namespace) -> dict[str, Any]:
    if args.config:
        path = Path(args.config)
    else:
        path = Path(args.config_dir) / f"{args.tid}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"config not found: {path}")
    try:
        from omegaconf import OmegaConf

        raw = OmegaConf.to_container(OmegaConf.load(path), resolve=True) or {}
    except ModuleNotFoundError:
        import yaml

        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"config must be a YAML object: {path}")
    return raw


def _build_debug_encoder_from_config(
    config: dict[str, Any],
    encoder_id: str,
    *,
    allow_cache_write: bool = False,
) -> Any:
    qu_kwargs = config.get("qu_kwargs") or {}
    if not isinstance(qu_kwargs, dict):
        raise ValueError("config.qu_kwargs must be a mapping")
    encoder_id = str(encoder_id or "default")
    encoders_cfg = qu_kwargs.get("encoders") or {}
    if not isinstance(encoders_cfg, dict):
        raise ValueError("config.qu_kwargs.encoders must be a mapping")
    encoder_cfg = None
    if encoder_id in encoders_cfg:
        encoder_cfg = encoders_cfg[encoder_id]
    elif encoder_id == "default" and qu_kwargs.get("encoder") is not None:
        encoder_cfg = qu_kwargs.get("encoder")
    if encoder_cfg is None:
        default_names = ["default"] if qu_kwargs.get("encoder") is not None else []
        available = sorted({*encoders_cfg.keys(), *default_names})
        raise ValueError(f"encoder_id {encoder_id!r} not found in config; available={available}")
    if not isinstance(encoder_cfg, dict):
        raise ValueError(f"encoder config for {encoder_id!r} must be a mapping")
    from mcrs.qu_modules.compiler_v0plus_qu import _build_encoder

    debug_cfg = dict(encoder_cfg)
    if not allow_cache_write:
        debug_cfg["cache"] = False
        debug_cfg["disk_cache"] = False
    return _build_encoder(debug_cfg)


def _debug_lancedb_params(
    config: dict[str, Any],
    run: RunArtifacts | None,
    args: argparse.Namespace,
) -> tuple[str, str]:
    if run is not None:
        return str(run.catalog_db_uri), str(run.catalog_table)
    qu_kwargs = config.get("qu_kwargs") or {}
    if not isinstance(qu_kwargs, dict):
        raise ValueError("config.qu_kwargs must be a mapping")
    lance_cfg = qu_kwargs.get("lancedb") or {}
    if not isinstance(lance_cfg, dict):
        raise ValueError("config.qu_kwargs.lancedb must be a mapping")
    db_uri = os.environ.get("MCRS_LANCEDB_URI") or lance_cfg.get("db_uri") or args.catalog_db_uri
    table_name = lance_cfg.get("table_name") or args.catalog_table
    return str(db_uri), str(table_name)


def _build_debug_lancedb_retriever(config: dict[str, Any], run: RunArtifacts | None, args: argparse.Namespace) -> Any:
    db_uri, table_name = _debug_lancedb_params(config, run, args)
    from mcrs.lancedb.retriever import LanceDbRetriever

    return LanceDbRetriever.from_retrieval_config(
        {
            "db_uri": db_uri,
            "table_name": table_name,
            "fusion": {"method": "weighted_rrf"},
            "device": "cpu",
        }
    )


def _load_debug_lancedb_catalog(config: dict[str, Any], run: RunArtifacts | None, args: argparse.Namespace) -> Any:
    db_uri, table_name = _debug_lancedb_params(config, run, args)
    from mcrs.qu_modules.v0plus_catalog_lance import LanceDbCatalog

    return LanceDbCatalog(db_uri=db_uri, table_name=table_name)


def _build_extractor_from_config(config: dict[str, Any]) -> Any:
    from scripts.extract_state import build_extractor, extractor_config_from_config

    return build_extractor(extractor_config_from_config(config))


def _build_state_ranker_from_config(config: dict[str, Any]) -> Any:
    from mcrs.qu_modules.state_ranker_qu import build_state_ranker_qu

    qu_kwargs = config.get("qu_kwargs") or {}
    if not isinstance(qu_kwargs, dict):
        raise ValueError("config.qu_kwargs must be a mapping")
    return build_state_ranker_qu(qu_kwargs=qu_kwargs)


def _extract_conversation_and_played(
    path: str | Path,
    *,
    extra_played: list[str] | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    raw, played = _conversation_items_and_played(data)
    played.extend(str(x) for x in extra_played or [] if str(x).strip())
    conversation, music_played = _conversation_for_extractor(raw)
    return conversation, _dedupe([*played, *music_played])


def _conversation_items_and_played(data: Any) -> tuple[list[dict[str, Any]], list[str]]:
    played: list[str] = []
    if isinstance(data, dict):
        raw = (
            data.get("conversations")
            or data.get("conversation")
            or data.get("messages")
            or data.get("session_memory")
        )
        played = [str(x) for x in data.get("played_track_ids") or [] if str(x).strip()]
    else:
        raw = data
    if not isinstance(raw, list):
        raise ValueError("conversation file must be a list or contain conversation/messages/session_memory")
    items = [item for item in raw if isinstance(item, dict)]
    if len(items) != len(raw):
        raise ValueError("conversation items must be JSON objects")
    return items, played


def _conversation_for_extractor(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    out: list[dict[str, Any]] = []
    played: list[str] = []
    turn = 0
    for item in items:
        role = str(item.get("role") or "").strip()
        if role == "user":
            turn = int(item.get("turn") or item.get("turn_number") or (turn + 1))
            out.append({"turn": turn, "role": "user", "text": _message_text(item)})
        elif role == "assistant":
            msg_turn = int(item.get("turn") or item.get("turn_number") or turn or 1)
            out.append({"turn": msg_turn, "role": "assistant", "text": _message_text(item)})
        elif role == "music":
            track_id = str(item.get("track_id") or item.get("content") or "").strip()
            if not track_id:
                continue
            played.append(track_id)
            msg_turn = int(item.get("turn") or item.get("turn_number") or turn or 1)
            label = str(item.get("label") or f"track={track_id[:8]}")
            out.append({"turn": msg_turn, "role": "music", "track_id": track_id, "label": label})
    if not out:
        raise ValueError("conversation file did not contain any supported messages")
    return out, played


def _message_text(item: dict[str, Any]) -> str:
    return str(item.get("text") if item.get("text") is not None else item.get("content") or "")


def _conversation_items_to_dataset_messages(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    turn = 0
    for item in items:
        role = str(item.get("role") or "").strip()
        if role == "user":
            turn = int(item.get("turn_number") or item.get("turn") or (turn + 1))
            out.append({"role": "user", "turn_number": turn, "content": _message_text(item)})
        elif role == "assistant":
            msg_turn = int(item.get("turn_number") or item.get("turn") or turn or 1)
            out.append({"role": "assistant", "turn_number": msg_turn, "content": _message_text(item)})
        elif role == "music":
            track_id = str(item.get("track_id") or item.get("content") or "").strip()
            if not track_id:
                continue
            msg_turn = int(item.get("turn_number") or item.get("turn") or turn or 1)
            out.append({"role": "music", "turn_number": msg_turn, "content": track_id})
    return out


def _session_memory_for_replay(
    *,
    played_track_ids: list[str],
    latest_user_text: str = "",
    conversation_path: str | None = None,
    turn_number: int | None = None,
) -> list[dict[str, Any]]:
    if conversation_path:
        data = json.loads(Path(conversation_path).read_text(encoding="utf-8"))
        raw, explicit_played = _conversation_items_and_played(data)
        session_memory = _items_to_session_memory(raw)
        if session_memory:
            return session_memory
        played_track_ids = [*explicit_played, *played_track_ids]
    current_turn = int(turn_number or 1)
    previous_turn = max(current_turn - 1, 1)
    memory = [
        {"role": "music", "content": track_id, "turn_number": previous_turn}
        for track_id in _dedupe(played_track_ids)
    ]
    memory.append({"role": "user", "content": latest_user_text or "", "turn_number": current_turn})
    return memory


def _items_to_session_memory(items: list[dict[str, Any]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for item in items:
        role = str(item.get("role") or "").strip()
        if role in {"user", "assistant"}:
            payload = {"role": role, "content": _message_text(item)}
            if item.get("turn_number") is not None or item.get("turn") is not None:
                payload["turn_number"] = int(item.get("turn_number") or item.get("turn") or 0)
            out.append(payload)
        elif role == "music":
            track_id = str(item.get("track_id") or item.get("content") or "").strip()
            if track_id:
                payload = {"role": "music", "content": track_id}
                if item.get("turn_number") is not None or item.get("turn") is not None:
                    payload["turn_number"] = int(item.get("turn_number") or item.get("turn") or 0)
                out.append(payload)
    return out


def _load_state(path: str | Path) -> Any:
    return _state_from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def _state_from_dict(raw: dict[str, Any]) -> Any:
    from mcrs.conversation_state.schema import ConversationStateV0Plus

    return ConversationStateV0Plus.model_validate(raw)


class _StaticExtractor:
    def __init__(self, state: Any) -> None:
        self.state = state

    def extract(self, conversation: list[dict[str, Any]], played_track_ids: list[str]) -> Any:
        return self.state

    async def aextract(self, conversation: list[dict[str, Any]], played_track_ids: list[str]) -> Any:
        return self.state


def _session_meta_for_replay(
    *,
    session_id: str | None,
    turn_number: int | None,
    user_id: str | None,
    conversation_path: str | None,
    session_memory: list[dict[str, Any]],
    source_meta: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if session_id is None and turn_number is None and not conversation_path and not source_meta:
        return None
    meta: dict[str, Any] = {"session_id": str(session_id or ""), "turn_number": int(turn_number or 0)}
    if user_id:
        meta["user_id"] = str(user_id)

    raw_items = session_memory
    if isinstance(source_meta, dict):
        for key in ("conversations", "user_profile", "conversation_goal", "session_date"):
            if key in source_meta:
                meta[key] = source_meta[key]
    if conversation_path:
        data = json.loads(Path(conversation_path).read_text(encoding="utf-8"))
        if isinstance(data, dict):
            for key in ("conversations", "user_profile", "conversation_goal", "session_date"):
                if key in data:
                    meta[key] = data[key]
        raw_items, _ = _conversation_items_and_played(data)

    if "conversations" not in meta:
        conversations = _conversation_items_to_dataset_messages(raw_items)
        if conversations:
            meta["conversations"] = conversations
    return meta


def _debug_config_for_cache_policy(config: dict[str, Any], *, allow_cache_write: bool) -> dict[str, Any]:
    if allow_cache_write:
        return config
    out = copy.deepcopy(config)
    qu_kwargs = out.get("qu_kwargs")
    if not isinstance(qu_kwargs, dict):
        return out

    def disable_encoder_cache(encoder_cfg: Any) -> None:
        if isinstance(encoder_cfg, dict):
            encoder_cfg["cache"] = False
            encoder_cfg["disk_cache"] = False

    disable_encoder_cache(qu_kwargs.get("encoder"))
    encoders = qu_kwargs.get("encoders")
    if isinstance(encoders, dict):
        for encoder_cfg in encoders.values():
            disable_encoder_cache(encoder_cfg)
    return out


def _reranker_from_qu(qu: Any) -> Any:
    get_reranker = getattr(qu, "_get_reranker", None)
    return get_reranker() if callable(get_reranker) else getattr(qu, "reranker", None)


def _set_qu_reranker_debug_policy(qu: Any, *, allow_cache_write: bool) -> tuple[Any, dict[str, Any]]:
    reranker = _reranker_from_qu(qu)
    if reranker is None:
        return None, {"offline": _OFFLINE_UNCHANGED, "b1_enc": _OFFLINE_UNCHANGED}
    return reranker, _set_reranker_debug_policy(reranker, allow_cache_write=allow_cache_write)


def _restore_qu_reranker_debug_policy(reranker: Any, previous: dict[str, Any]) -> None:
    if reranker is not None:
        _restore_reranker_debug_policy(reranker, previous)


def _retrieve_state_trace(
    args: argparse.Namespace,
    state: Any,
    *,
    played_track_ids: list[str],
    latest_user_text: str,
    session_id: str | None,
    turn_number: int | None,
    user_id: str | None,
    conversation_path: str | None,
    source_meta: dict[str, Any] | None,
) -> dict[str, Any]:
    config = _debug_config_for_cache_policy(
        _load_config_for_args(args),
        allow_cache_write=bool(getattr(args, "allow_cache_write", False)),
    )
    qu = _build_state_ranker_from_config(config)
    qu.extractor = _StaticExtractor(state)
    session_memory = _session_memory_for_replay(
        played_track_ids=played_track_ids,
        latest_user_text=latest_user_text,
        conversation_path=conversation_path,
        turn_number=turn_number,
    )
    meta = _session_meta_for_replay(
        session_id=session_id,
        turn_number=turn_number,
        user_id=user_id,
        conversation_path=conversation_path,
        session_memory=session_memory,
        source_meta=source_meta,
    )
    reranker, previous_policy = _set_qu_reranker_debug_policy(
        qu,
        allow_cache_write=bool(getattr(args, "allow_cache_write", False)),
    )
    try:
        qu.batch_compile_track_ids(
            [session_memory],
            topk=max(int(args.topk), 1),
            user_ids=[user_id],
            session_meta=[meta] if meta is not None else None,
        )
    finally:
        _restore_qu_reranker_debug_policy(reranker, previous_policy)
    if not qu.last_traces:
        raise ValueError("state replay produced no trace")
    trace = dict(qu.last_traces[0])
    if meta is not None:
        for key, value in meta.items():
            trace.setdefault(key, value)
    return trace


def _write_replay_outputs(
    trace: dict[str, Any],
    trace_out: str | None,
    compiled_out: str | None,
) -> None:
    if compiled_out:
        _write_json(trace.get("compiled_state"), compiled_out)
    _write_json(trace, trace_out)


def _write_json(payload: Any, path: str | None) -> None:
    text = json.dumps(_jsonable(payload), indent=2, sort_keys=True) + "\n"
    if path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    else:
        print(text, end="")


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

def _require_trace_run(args: argparse.Namespace) -> RunArtifacts:
    run = _require_run(args)
    if run.trace is None:
        raise ValueError(f"run alias {run.name!r} does not define a trace path")
    return run


def _require_run(args: argparse.Namespace) -> RunArtifacts:
    if not args.run:
        raise ValueError("--run is required for this command")
    return _resolve_run(args)


def _optional_run(args: argparse.Namespace) -> RunArtifacts | None:
    return _resolve_run(args) if args.run else None


def _resolve_run(args: argparse.Namespace) -> RunArtifacts:
    run_file = Path(args.run_file)
    aliases = load_run_aliases(run_file)
    return resolve_run_alias(aliases, args.run, base_dir=run_file.resolve().parent)


def _resolve_session(run: RunArtifacts, value: str) -> str:
    if run.trace is None:
        raise ValueError(f"run alias {run.name!r} does not define a trace path")
    return resolve_session_prefix(trace_session_ids(run.trace), value)


def _load_catalog(run: RunArtifacts | None, args: argparse.Namespace) -> Any:
    db_uri = str(run.catalog_db_uri if run else args.catalog_db_uri)
    table_name = str(run.catalog_table if run else args.catalog_table)
    from mcrs.qu_modules.v0plus_catalog_lance import LanceDbCatalog

    return LanceDbCatalog(db_uri=db_uri, table_name=table_name)


def _matching_track_rows(rows: dict[str, dict[str, Any]], query_id: str) -> list[tuple[str, dict[str, Any]]]:
    if query_id in rows:
        return [(query_id, rows[query_id])]
    matches = [(track_id, row) for track_id, row in rows.items() if str(track_id).startswith(query_id)]
    return sorted(matches, key=lambda item: item[0])


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


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
