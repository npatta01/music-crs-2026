"""Trace diff, bundle, and target-audit commands."""

from __future__ import annotations

import argparse
import shlex
from pathlib import Path
from typing import Any

from . import runtime
from .artifacts import catalog_search, load_audit_index, load_prediction_index, trace_row
from .formatting import (
    _dedupe,
    _format_track_line,
    _jsonable,
    _print_json,
    _short_json,
    _track_payload,
    _write_json,
)
from .rerank import _feature_trace_for_reranker, _hard_drop_ids, _load_trace_document, _scored_track_id


def _cmd_diff_trace(args: argparse.Namespace) -> int:
    _, before = _load_trace_document(args.before)
    _, after = _load_trace_document(args.after)
    payload = _trace_diff(before, after, target_track_id=args.target_track_id)
    if args.format == "json":
        _print_json(payload)
    else:
        _print_trace_diff(payload)
    return 0

def _cmd_bundle_case(args: argparse.Namespace) -> int:
    run = runtime._require_trace_run(args)
    session_id = runtime._resolve_session(run, args.session_id)
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
    catalog = runtime._load_catalog(runtime._optional_run(args), args)
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
