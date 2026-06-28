"""Rerank replay and feature-inspection commands."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from . import runtime
from .formatting import _dedupe, _write_json


_OFFLINE_UNCHANGED = object()


def _cmd_rerank_subset(args: argparse.Namespace) -> int:
    wrapper, trace = _load_trace_document(args.trace, session_id=args.session_id, turn_number=args.turn)
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
    config = runtime._debug_config_for_cache_policy(
        runtime._load_config_for_args(args),
        allow_cache_write=bool(args.allow_cache_write),
    )
    qu = runtime._build_state_ranker_from_config(config)
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
    wrapper, trace = _load_trace_document(args.trace, session_id=args.session_id, turn_number=args.turn)
    candidate_ids = _load_candidate_ids(args.candidate, args.candidates)
    if args.diff:
        candidate_ids = _dedupe([*candidate_ids, *args.diff])
    if not candidate_ids:
        raise ValueError("provide at least one --candidate, --candidates file, or --diff pair")
    feature_trace, injected = _subset_feature_trace(
        trace,
        candidate_ids,
        inject_missing=args.inject_missing,
        inject_branch=args.inject_branch,
        inject_score=float(args.inject_score),
    )
    config = runtime._debug_config_for_cache_policy(
        runtime._load_config_for_args(args),
        allow_cache_write=bool(args.allow_cache_write),
    )
    qu = runtime._build_state_ranker_from_config(config)
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

def _set_reranker_debug_policy(reranker: Any, *, allow_cache_write: bool) -> dict[str, Any]:
    del reranker, allow_cache_write
    # Preserve the configured online/read-through behavior: local caches are
    # checked first and misses fall through to the configured remote encoder.
    return {"offline": _OFFLINE_UNCHANGED, "b1_enc": _OFFLINE_UNCHANGED}

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

def _load_trace_document(
    path: str | Path,
    *,
    session_id: str | None = None,
    turn_number: int | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    raw_text = Path(path).read_text(encoding="utf-8").strip()
    if not raw_text:
        raise ValueError(f"empty trace file: {path}")
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        docs = [json.loads(line) for line in raw_text.splitlines() if line.strip()]
        doc = _select_trace_document(
            docs,
            path=path,
            session_id=session_id,
            turn_number=turn_number,
        )
    else:
        if isinstance(parsed, list):
            doc = _select_trace_document(
                parsed,
                path=path,
                session_id=session_id,
                turn_number=turn_number,
            )
        else:
            doc = parsed
    if not isinstance(doc, dict):
        raise ValueError(f"trace file must contain a JSON object: {path}")
    trace = doc.get("trace") if isinstance(doc.get("trace"), dict) else doc
    return doc, trace


def _select_trace_document(
    docs: list[Any],
    *,
    path: str | Path,
    session_id: str | None,
    turn_number: int | None,
) -> dict[str, Any]:
    rows = [doc for doc in docs if isinstance(doc, dict)]
    if len(rows) != len(docs):
        raise ValueError(f"trace rows must be JSON objects: {path}")
    if not rows:
        raise ValueError(f"empty trace file: {path}")
    if session_id is None and turn_number is None:
        if len(rows) == 1:
            return rows[0]
        raise ValueError(
            f"trace file contains {len(rows)} rows; pass --session-id and/or --turn to select one"
        )
    matches = [
        row
        for row in rows
        if _trace_row_matches(row, session_id=session_id, turn_number=turn_number)
    ]
    if len(matches) != 1:
        raise ValueError(
            f"expected one trace row for session_id={session_id!r} turn={turn_number!r}; "
            f"found {len(matches)} in {path}"
        )
    return matches[0]


def _trace_row_matches(
    row: dict[str, Any],
    *,
    session_id: str | None,
    turn_number: int | None,
) -> bool:
    if session_id is not None and str(row.get("session_id") or "") != str(session_id):
        return False
    if turn_number is not None:
        try:
            row_turn = int(row.get("turn_number"))
        except (TypeError, ValueError):
            return False
        if row_turn != int(turn_number):
            return False
    return True

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
