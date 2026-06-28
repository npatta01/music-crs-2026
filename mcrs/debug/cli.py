"""Argparse entry point for the Music CRS debug CLI."""

from __future__ import annotations

import argparse
import sys

from .artifacts import DEFAULT_CATALOG_DB_URI, DEFAULT_CATALOG_TABLE, DEFAULT_RUN_FILE
from .audit import _cmd_bundle_case, _cmd_diff_trace, _cmd_target_audit
from .catalog import DEFAULT_BM25_FIELDS, _cmd_bm25, _cmd_catalog_search, _cmd_dense_search, _cmd_track
from .inspect import _cmd_case, _cmd_session, _cmd_state
from .replay import _cmd_extract_state, _cmd_replay_turn, _cmd_retrieve_state
from .rerank import _cmd_rerank_features, _cmd_rerank_subset
from .runtime import _add_config_args


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


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
