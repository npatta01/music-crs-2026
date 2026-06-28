"""State extraction and replay commands."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from . import runtime
from .artifacts import load_audit_index, trace_row
from .formatting import _dedupe, _write_json
from .rerank import _OFFLINE_UNCHANGED, _restore_reranker_debug_policy, _set_reranker_debug_policy


def _cmd_extract_state(args: argparse.Namespace) -> int:
    config = runtime._load_config_for_args(args)
    conversation, played = _extract_conversation_and_played(
        args.conversation,
        extra_played=args.played_track_id,
    )
    extractor = runtime._build_extractor_from_config(config)
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
    run = runtime._require_trace_run(args)
    session_id = runtime._resolve_session(run, args.session_id)
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
    config = runtime._debug_config_for_cache_policy(
        runtime._load_config_for_args(args),
        allow_cache_write=bool(getattr(args, "allow_cache_write", False)),
    )
    qu = runtime._build_state_ranker_from_config(config)
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
