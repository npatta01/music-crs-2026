"""Conversation-conditioned helpers for semantic retrieval experiments."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence

import numpy as np

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9'_-]*", re.I)


def _clean(value: object) -> str:
    return " ".join(str(value or "").split())


def _trace_state(trace_or_state: Mapping) -> Mapping:
    if "extracted_state" in trace_or_state or "compiled_state" in trace_or_state:
        state = trace_or_state.get("extracted_state") or trace_or_state.get("state") or {}
        if isinstance(state, Mapping):
            return state
        return {}
    return trace_or_state


def _trace_intent(trace_or_state: Mapping, state: Mapping) -> str:
    return _clean(
        trace_or_state.get("intent_mode")
        or state.get("intent_mode")
        or (trace_or_state.get("compiled_state") or {}).get("intent_mode")
    )


def state_to_text(trace_or_state: Mapping) -> str:
    """Convert extracted/compiled state into a compact deterministic text view."""

    state = _trace_state(trace_or_state)
    parts: list[str] = []

    request = state.get("current_request") or {}
    if isinstance(request, Mapping):
        summary = _clean(request.get("summary") or state.get("turn_intent"))
    else:
        summary = _clean(state.get("turn_intent"))
    if summary:
        parts.append(f"request: {summary}")

    intent = _trace_intent(trace_or_state, state)
    if intent:
        parts.append(f"intent: {intent}")

    facts = []
    for fact in state.get("facts") or []:
        if not isinstance(fact, Mapping):
            continue
        typ = _clean(fact.get("type"))
        value = _clean(fact.get("value"))
        role = _clean(fact.get("role"))
        if typ and value:
            facts.append(f"{typ}={value}" + (f" ({role})" if role else ""))
    if facts:
        parts.append("facts: " + "; ".join(facts[:12]))

    exclusions = []
    for item in state.get("exclusions") or state.get("explicit_rejections") or []:
        if isinstance(item, Mapping):
            value = _clean(item.get("value") or item.get("text"))
        else:
            value = _clean(item)
        if value:
            exclusions.append(value)
    if exclusions:
        parts.append("avoid: " + "; ".join(exclusions[:8]))

    temporal = state.get("temporal_constraint") or {}
    if isinstance(temporal, Mapping):
        start = temporal.get("start_year")
        end = temporal.get("end_year")
        strength = _clean(temporal.get("strength"))
        if start or end:
            span = f"{start or ''}-{end or ''}".strip("-")
            parts.append("years: " + " ".join(v for v in (span, strength) if v))

    routing = (
        state.get("routing_tags")
        or trace_or_state.get("routing_tags")
        or (trace_or_state.get("compiled_state") or {}).get("routing_tags")
        or {}
    )
    if isinstance(routing, Mapping):
        active = sorted(str(name) for name, enabled in routing.items() if enabled)
        if active:
            parts.append("routes: " + ", ".join(active))

    return " | ".join(parts)


def _prior_track_ids(session: Mapping, turn_number: int) -> list[str]:
    played_by_turn = session.get("played_by_turn") or {}
    out: list[str] = []
    for raw_turn in sorted(played_by_turn):
        try:
            turn = int(raw_turn)
        except Exception:
            continue
        if turn >= int(turn_number):
            continue
        out.extend(str(track_id) for track_id in played_by_turn.get(raw_turn) or [])
    return out


def _track_names(track_ids: Sequence[str], track_lookup: Mapping[str, str], max_tracks: int = 8) -> list[str]:
    names = []
    for track_id in track_ids[-max_tracks:]:
        names.append(_clean(track_lookup.get(str(track_id)) or str(track_id)))
    return [name for name in names if name]


def conversation_input_text(
    session: Mapping,
    trace: Mapping,
    *,
    turn_number: int,
    view: str,
    track_lookup: Mapping[str, str],
) -> str:
    """Build a deterministic text input for a conversation turn."""

    user_text_by_turn = session.get("user_text_by_turn") or {}
    current_user = _clean(user_text_by_turn.get(int(turn_number)) or user_text_by_turn.get(str(turn_number)))
    state_text = state_to_text(trace)
    prior_names = _track_names(_prior_track_ids(session, int(turn_number)), track_lookup)
    listener_goal = _clean(session.get("listener_goal"))

    parts: list[str] = []
    if view == "last_turn":
        if current_user:
            parts.append(f"current user: {current_user}")
    elif view == "state":
        if state_text:
            parts.append(f"state: {state_text}")
    elif view in {"last_turn_state", "last_turn_state_prior"}:
        if current_user:
            parts.append(f"current user: {current_user}")
        if state_text:
            parts.append(f"state: {state_text}")
    elif view == "full_conversation_state_prior":
        turns = []
        for raw_turn in sorted(user_text_by_turn):
            try:
                turn = int(raw_turn)
            except Exception:
                continue
            if turn <= int(turn_number):
                text = _clean(user_text_by_turn.get(raw_turn))
                if text:
                    turns.append(f"turn {turn}: {text}")
        if turns:
            parts.append("conversation: " + " | ".join(turns))
        if state_text:
            parts.append(f"state: {state_text}")
    else:
        raise ValueError(f"unknown conversation input view: {view}")

    if view in {"last_turn_state_prior", "full_conversation_state_prior"}:
        if prior_names:
            parts.append("prior tracks: " + " | ".join(prior_names))
        if listener_goal:
            parts.append(f"listener goal: {listener_goal}")

    return " || ".join(parts)


def hashed_text_vector(text: str, *, dim: int = 512) -> np.ndarray:
    """Stable signed hashing vectorizer with L2 normalization."""

    if dim <= 0:
        raise ValueError("dim must be positive")
    vec = np.zeros(dim, dtype=np.float32)
    for token in _TOKEN_RE.findall(text.lower()):
        digest = hashlib.sha1(token.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "little") % dim
        sign = 1.0 if digest[4] & 1 else -1.0
        vec[idx] += sign
    norm = float(np.linalg.norm(vec))
    if norm > 0:
        vec /= norm
    return vec


def _normalise(vector: np.ndarray) -> np.ndarray:
    arr = np.asarray(vector, dtype=np.float32)
    norm = float(np.linalg.norm(arr))
    if norm > 0:
        return arr / norm
    return arr


def prior_track_centroid(
    session: Mapping,
    *,
    turn_number: int,
    track_to_code: Mapping[str, int],
    item_vectors: np.ndarray,
) -> np.ndarray:
    """Normalized centroid of tracks played before `turn_number`."""

    vectors = []
    for track_id in _prior_track_ids(session, int(turn_number)):
        code = track_to_code.get(str(track_id))
        if code is None:
            continue
        vec = item_vectors[int(code)]
        if np.isfinite(vec).all():
            vectors.append(vec)
    if not vectors:
        return np.zeros(item_vectors.shape[1], dtype=np.float32)
    return _normalise(np.mean(np.vstack(vectors), axis=0)).astype(np.float32, copy=False)


def combine_text_and_prior_vectors(text_vector: np.ndarray, prior_vector: np.ndarray) -> np.ndarray:
    """Concatenate independently normalized text and prior-track blocks."""

    return np.concatenate([_normalise(text_vector), _normalise(prior_vector)]).astype(np.float32, copy=False)


def semantic_leaf_map(rows: Sequence[Mapping]) -> dict[tuple[int, int], list[str]]:
    """Group track IDs by valid two-level semantic code."""

    out: dict[tuple[int, int], list[str]] = {}
    for row in rows:
        try:
            key = (int(row["sid_l1"]), int(row["sid_l2"]))
        except Exception:
            continue
        out.setdefault(key, []).append(str(row["track_id"]))
    return out
