"""Compatibility wrapper for the Music CRS debug CLI."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any


def _prefer_repo_root_imports() -> None:
    """Avoid script-directory shadowing when run as ``python mcrs/debug_cli.py``."""
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent
    cleaned: list[str] = []
    for entry in sys.path:
        resolved = Path(entry or ".").resolve()
        if resolved in {script_dir, repo_root}:
            continue
        cleaned.append(entry)
    sys.path[:] = [str(repo_root), *cleaned]


_prefer_repo_root_imports()

from mcrs.debug import audit as _audit
from mcrs.debug import catalog as _catalog
from mcrs.debug import cli as _cli
from mcrs.debug import inspect as _inspect
from mcrs.debug import replay as _replay
from mcrs.debug import rerank as _rerank
from mcrs.debug import runtime as _runtime
from mcrs.debug.artifacts import (
    DEFAULT_CATALOG_DB_URI,
    DEFAULT_CATALOG_TABLE,
    DEFAULT_RUN_FILE,
    CatalogHit,
    CatalogSearchResult,
    RunArtifacts,
    catalog_search,
    iter_trace_rows,
    load_audit_index,
    load_prediction_index,
    load_run_aliases,
    resolve_run_alias,
    resolve_session_prefix,
    trace_row,
    trace_session_ids,
    trace_turns,
)
from mcrs.debug.audit import (
    _branch_summary,
    _bundle_commands,
    _bundle_config_args,
    _bundle_conversation,
    _candidate_ids_from_trace,
    _cmd_bundle_case,
    _cmd_diff_trace,
    _cmd_target_audit,
    _final_track_ids,
    _flatten_json,
    _hard_drop_sources,
    _object_changes,
    _print_target_audit,
    _print_trace_diff,
    _rank_position_changes,
    _scored_score,
    _stage_ranks,
    _target_audit_payload,
    _target_branch_positions,
    _target_fused_rank,
    _target_rank_changes,
    _top20_from_trace_or_audit,
    _trace_diff,
)
from mcrs.debug.catalog import (
    DEFAULT_BM25_FIELDS,
    _cmd_bm25,
    _cmd_catalog_search,
    _cmd_dense_search,
    _cmd_track,
    _matching_track_rows,
    _print_dense_search,
)
from mcrs.debug.cli import _build_parser
from mcrs.debug.formatting import (
    _dedupe,
    _first,
    _format_track_line,
    _join,
    _jsonable,
    _list,
    _parse_bm25_fields,
    _print_block,
    _print_case,
    _print_json,
    _print_ranking,
    _print_retrieval,
    _print_value,
    _rank_extras,
    _row_value,
    _short_json,
    _track_payload,
    _write_json,
)
from mcrs.debug.inspect import _cmd_case, _cmd_session, _cmd_state
from mcrs.debug.replay import (
    _StaticExtractor,
    _cmd_extract_state,
    _cmd_replay_turn,
    _cmd_retrieve_state,
    _conversation_for_extractor,
    _conversation_items_and_played,
    _conversation_items_to_dataset_messages,
    _extract_conversation_and_played,
    _items_to_session_memory,
    _load_state,
    _message_text,
    _restore_qu_reranker_debug_policy,
    _retrieve_state_trace,
    _reranker_from_qu,
    _session_memory_for_replay,
    _session_meta_for_replay,
    _set_qu_reranker_debug_policy,
    _state_from_dict,
    _write_replay_outputs,
)
from mcrs.debug.rerank import (
    _OFFLINE_UNCHANGED,
    _ReadOnlyCachedTextEmbedder,
    _cmd_rerank_features,
    _cmd_rerank_subset,
    _compute_rerank_feature_payload,
    _compute_rerank_feature_rows,
    _debug_json_value,
    _feature_trace_for_reranker,
    _finite_float,
    _hard_drop_ids,
    _load_candidate_ids,
    _load_trace_document,
    _matrix_rows,
    _rerank_feature_diff,
    _rerank_score_sort_key,
    _restore_reranker_debug_policy,
    _restore_reranker_offline,
    _scored_track_id,
    _session_meta_from_wrapper,
    _set_reranker_debug_policy,
    _set_reranker_offline,
    _subset_feature_trace,
)
from mcrs.debug.runtime import (
    _add_config_args,
    _build_debug_encoder_from_config,
    _build_debug_lancedb_retriever,
    _build_extractor_from_config,
    _build_state_ranker_from_config,
    _debug_config_for_cache_policy,
    _debug_lancedb_params,
    _load_catalog,
    _load_config_for_args,
    _load_debug_lancedb_catalog,
    _optional_run,
    _require_run,
    _require_trace_run,
    _resolve_run,
    _resolve_session,
)


_MISSING = object()
_COMPAT_TARGETS = {
    "_build_parser": ((_cli, "_build_parser"),),
    "_cmd_session": ((_cli, "_cmd_session"),),
    "_cmd_case": ((_cli, "_cmd_case"),),
    "_cmd_state": ((_cli, "_cmd_state"),),
    "_cmd_track": ((_cli, "_cmd_track"),),
    "_cmd_catalog_search": ((_cli, "_cmd_catalog_search"),),
    "_cmd_bm25": ((_cli, "_cmd_bm25"),),
    "_cmd_dense_search": ((_cli, "_cmd_dense_search"),),
    "_cmd_extract_state": ((_cli, "_cmd_extract_state"),),
    "_cmd_retrieve_state": ((_cli, "_cmd_retrieve_state"),),
    "_cmd_replay_turn": ((_cli, "_cmd_replay_turn"),),
    "_cmd_rerank_subset": ((_cli, "_cmd_rerank_subset"),),
    "_cmd_rerank_features": ((_cli, "_cmd_rerank_features"),),
    "_cmd_diff_trace": ((_cli, "_cmd_diff_trace"),),
    "_cmd_bundle_case": ((_cli, "_cmd_bundle_case"),),
    "_cmd_target_audit": ((_cli, "_cmd_target_audit"),),
    "_load_config_for_args": ((_runtime, "_load_config_for_args"),),
    "_build_debug_encoder_from_config": ((_runtime, "_build_debug_encoder_from_config"),),
    "_build_debug_lancedb_retriever": ((_runtime, "_build_debug_lancedb_retriever"),),
    "_load_debug_lancedb_catalog": ((_runtime, "_load_debug_lancedb_catalog"),),
    "_build_extractor_from_config": ((_runtime, "_build_extractor_from_config"),),
    "_build_state_ranker_from_config": ((_runtime, "_build_state_ranker_from_config"),),
    "_load_catalog": ((_runtime, "_load_catalog"),),
    "catalog_search": ((_catalog, "catalog_search"), (_audit, "catalog_search")),
    "_compute_rerank_feature_payload": ((_rerank, "_compute_rerank_feature_payload"),),
    "_compute_rerank_feature_rows": ((_rerank, "_compute_rerank_feature_rows"),),
    "_set_reranker_debug_policy": ((_rerank, "_set_reranker_debug_policy"),),
    "_restore_reranker_debug_policy": ((_rerank, "_restore_reranker_debug_policy"),),
    "_session_meta_from_wrapper": ((_rerank, "_session_meta_from_wrapper"),),
}
_COMPAT_ORIGINALS = {name: globals().get(name, _MISSING) for name in _COMPAT_TARGETS}


def main(argv: list[str] | None = None) -> int:
    patches = _apply_compat_patches()
    try:
        return _cli.main(argv)
    finally:
        _restore_compat_patches(patches)


def _apply_compat_patches() -> list[tuple[Any, str, Any]]:
    patches: list[tuple[Any, str, Any]] = []
    for name, targets in _COMPAT_TARGETS.items():
        value = globals().get(name, _MISSING)
        if value is _MISSING or value is _COMPAT_ORIGINALS.get(name, _MISSING):
            continue
        for module, attr in targets:
            previous = getattr(module, attr, _MISSING)
            if previous is value:
                continue
            patches.append((module, attr, previous))
            setattr(module, attr, value)
    return patches


def _restore_compat_patches(patches: list[tuple[Any, str, Any]]) -> None:
    for module, attr, previous in reversed(patches):
        if previous is _MISSING:
            try:
                delattr(module, attr)
            except AttributeError:
                pass
        else:
            setattr(module, attr, previous)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
