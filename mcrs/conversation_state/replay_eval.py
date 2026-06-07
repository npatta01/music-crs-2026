"""Replay-pack evaluator for conversation-state extraction experiments."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from mcrs.conversation_state.schema import ConversationStateV0Plus


FOCUSED_PACKS = (
    "P0_roleless_stale_entity_failure",
    "P0_novelty_prior_anchor_failure",
    "P0_new_artist_union20_gap_failure",
    "P1_temporal_constraint_failure",
    "P1_rejection_guardrail_failure",
    "POS_exact_entity_success_control",
    "POS_clean_final_hit_control",
)


CHECKS = (
    "schema_valid",
    "request_type_correct",
    "role_correct",
    "target_artist_mode_correct",
    "retrieval_profile_correct",
    "temporal_semantics_correct",
    "rejection_normalization_correct",
    "positive_control_preserved",
)


def _policy_to_target_artist_mode(policy: Any) -> str | None:
    value = _norm(policy)
    if value == "exploit":
        return "same_artist"
    if value in {"diversify_artists", "diversify_albums"}:
        return "new_artist"
    if value == "balanced":
        return "unknown"
    return None


def _legacy_retrieval_profile(snapshot: dict[str, Any]) -> str | None:
    routing = set(snapshot.get("routing") or [])
    policy = _norm(snapshot.get("policy"))
    intent_mode = _norm(snapshot.get("intent_mode"))
    if "exact_entity_probe" in routing:
        return "exact_probe"
    if "hidden_target_search" in routing:
        return "hidden_target_search"
    if policy in {"diversify_artists", "diversify_albums"} or intent_mode == "pivot":
        return "novelty"
    if intent_mode in {"refinement", "playlist_build"}:
        return "continuation"
    if "feature_articulation" in routing or "lyric_search" in routing:
        return "feature_search"
    return None


def load_replay_pack(path: str | Path, packs: tuple[str, ...] | list[str] | None = None) -> list[dict[str, Any]]:
    data = json.loads(Path(path).read_text())
    turns = data.get("turns") or []
    if packs == ():
        return turns
    selected = set(packs or FOCUSED_PACKS)
    return [turn for turn in turns if turn.get("pack") in selected]


def limit_samples_per_pack(samples: list[dict[str, Any]], limit: int | None) -> list[dict[str, Any]]:
    if limit is None:
        return samples
    if limit <= 0:
        raise ValueError("limit_per_pack must be positive")
    counts: dict[str, int] = defaultdict(int)
    selected: list[dict[str, Any]] = []
    for sample in samples:
        pack = sample.get("pack") or ""
        if counts[pack] >= limit:
            continue
        selected.append(sample)
        counts[pack] += 1
    return selected


def apply_expected_state_overrides(
    samples: list[dict[str, Any]],
    overrides: dict[str, dict[str, Any]],
    *,
    filter_to_overrides: bool = False,
) -> list[dict[str, Any]]:
    """Apply human-reviewed expected state checks to replay samples.

    The original replay pack contains GT/ranker-derived ideal labels. These
    overlays define the smaller extractor-state contract that is safe to score.
    """

    reviewed: list[dict[str, Any]] = []
    for sample in samples:
        sample_id = sample["sample_id"]
        override = overrides.get(sample_id)
        if override is None:
            if not filter_to_overrides:
                reviewed.append(sample)
            continue
        merged = dict(sample)
        merged.update(override)
        reviewed.append(merged)
    return reviewed


def trim_messages_for_extraction(sample: dict[str, Any]) -> list[dict[str, Any]]:
    """Keep only conversation evidence visible at extraction time.

    The checked-in replay examples include the current GT music/assistant rows
    for human diagnosis. The extractor must not see those rows.
    """
    turn = int(sample["turn"])
    trimmed: list[dict[str, Any]] = []
    for msg in sample.get("recent_messages") or []:
        msg_turn = int(msg.get("turn", 0))
        if msg_turn < turn:
            trimmed.append(msg)
        elif msg_turn == turn and msg.get("role") == "user":
            trimmed.append(msg)
            break
    return trimmed


def _turn_number(value: Any) -> int:
    text = str(value or "").lstrip("t")
    return int(text) if text.isdigit() else 0


def build_full_history_messages_for_extraction(
    sample: dict[str, Any],
    session_messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build extractor-visible full history for a replay sample.

    Includes every role from earlier turns and only the current user message
    from the target turn. The target music/assistant rows are the hidden answer
    and must not be visible to the extractor.
    """

    target_turn = _turn_number(sample.get("turn"))
    if target_turn <= 0:
        return trim_messages_for_extraction(sample)

    messages: list[dict[str, Any]] = []
    for _, raw in sorted(
        enumerate(session_messages),
        key=lambda item: _turn_number(item[1].get("turn_number", item[1].get("turn"))),
    ):
        turn = _turn_number(raw.get("turn_number", raw.get("turn")))
        role = raw.get("role")
        if turn <= 0 or turn > target_turn:
            continue
        if turn == target_turn and role != "user":
            continue
        content = raw.get("content", raw.get("text", ""))
        messages.append({"role": role, "content": content})
    return messages


def observed_from_state(state: ConversationStateV0Plus) -> dict[str, Any]:
    return {
        "schema_valid": True,
        "current_request": (
            None if state.current_request is None else state.current_request.model_dump(mode="json")
        ),
        "target_artist_mode": state.target_artist_mode.value,
        "retrieval_profile": state.retrieval_profile.value,
        "facts": [fact.model_dump(mode="json") for fact in state.facts],
        "entities": [
            {
                "type": entity.type,
                "value": entity.value,
                "role": entity.role.value,
                "use_as_retrieval_seed": entity.use_as_retrieval_seed,
            }
            for entity in state.entities
        ],
        "exclusions": [
            exclusion.model_dump(mode="json") for exclusion in state.exclusions
        ],
        "rejections": [
            {
                "kind": rejection.kind,
                "value": rejection.value,
                "scope": rejection.scope.value,
            }
            for rejection in state.rejections
        ],
        "compiler_mentioned_entities": [
            {
                "type": entity.type,
                "value": entity.value,
                "sentiment": entity.sentiment,
            }
            for entity in state.mentioned_entities
        ],
        "compiler_style_reference_entities": [
            {
                "type": entity.type,
                "value": entity.value,
                "sentiment": entity.sentiment,
            }
            for entity in state.style_reference_entities
        ],
        "compiler_explicit_rejections": [
            {
                "kind": rejection.kind,
                "value": rejection.value,
                "source_turn": rejection.source_turn,
            }
            for rejection in state.explicit_rejections
        ],
        "temporal_constraint": (
            None
            if state.temporal_constraint is None
            else {
                "kind": state.temporal_constraint.kind.value,
                "strength": state.temporal_constraint.strength.value,
                "apply_as_filter": state.temporal_constraint.apply_as_filter,
                "range": [
                    state.temporal_constraint.start_year,
                    state.temporal_constraint.end_year,
                ],
            }
        ),
    }


def observed_from_state_snapshot(sample: dict[str, Any]) -> dict[str, Any]:
    """Normalize the original trace state snapshot into the replay-check shape."""

    snapshot = sample.get("state_snapshot") or {}
    anchors = {_norm(value) for value in snapshot.get("anchors") or []}
    stale = {_norm(value) for value in snapshot.get("stale_entities") or []}
    entities = []
    seen: set[tuple[str, str]] = set()
    for value in snapshot.get("positive_entities") or []:
        norm_value = _norm(value)
        if not norm_value:
            continue
        is_anchor = norm_value in anchors
        is_stale = norm_value in stale
        role = "current_target" if is_anchor else "history"
        entity = {
            "type": "unknown",
            "value": value,
            "role": role,
            "use_as_retrieval_seed": is_anchor,
            "was_stale_in_trace": is_stale,
        }
        key = (entity["type"], norm_value)
        if key not in seen:
            entities.append(entity)
            seen.add(key)
    for tag in snapshot.get("positive_tags") or []:
        norm_tag = _norm(tag)
        if not norm_tag:
            continue
        key = ("tag", norm_tag)
        if key not in seen:
            entities.append(
                {
                    "type": "tag",
                    "value": tag,
                    "role": "current_target",
                    "use_as_retrieval_seed": True,
                }
            )
            seen.add(key)
    rejections = []
    for rejection in snapshot.get("explicit_rejections") or []:
        if isinstance(rejection, dict):
            value = rejection.get("value")
            kind = rejection.get("kind", "unknown")
        else:
            value = rejection
            kind = "unknown"
        if value:
            rejections.append({"kind": kind, "value": value, "scope": "hard"})
    year_range = snapshot.get("year_range")
    temporal_constraint = None
    if isinstance(year_range, list) and len(year_range) == 2:
        temporal_constraint = {
            "kind": "style_era",
            "strength": "soft",
            "apply_as_filter": False,
            "range": year_range,
        }
    return {
        "schema_valid": True,
        "target_artist_mode": _policy_to_target_artist_mode(snapshot.get("policy")),
        "retrieval_profile": _legacy_retrieval_profile(snapshot),
        "entities": entities,
        "rejections": rejections,
        "temporal_constraint": temporal_constraint,
    }


def observed_from_ideal(sample: dict[str, Any]) -> dict[str, Any]:
    expected = sample.get("expected_state_checks")
    if isinstance(expected, dict):
        request_type = _first_allowed(expected.get("request_type"))
        target_artist_mode = _first_allowed(expected.get("target_artist_mode"))
        retrieval_profile = _first_allowed(expected.get("retrieval_profile"))
        entities = []
        for entity in expected.get("entities") or []:
            roles = entity.get("allowed_roles") or ["current_target"]
            entities.append(
                {
                    "type": entity.get("type", "artist"),
                    "value": entity.get("value"),
                    "role": roles[0],
                    "use_as_retrieval_seed": bool(entity.get("use_as_retrieval_seed")),
                }
            )
        rejections = []
        for value in expected.get("hard_rejection_values") or []:
            rejections.append({"kind": "artist", "value": value, "scope": "hard"})
        for value in expected.get("soft_rejection_values") or []:
            rejections.append({"kind": "tag", "value": value, "scope": "soft"})
        if expected.get("requires_hard_rejection") and not rejections:
            rejections.append({"kind": "artist", "value": "required", "scope": "hard"})
        return {
            "schema_valid": True,
            "current_request": (
                None
                if request_type is None
                else {
                    "request_type": request_type,
                    "summary": sample.get("current_user") or "",
                }
            ),
            "target_artist_mode": target_artist_mode,
            "retrieval_profile": retrieval_profile,
            "entities": entities,
            "rejections": rejections,
            "temporal_constraint": _first_allowed_mapping(
                expected.get("temporal_constraint")
            ),
        }

    ideal = sample.get("ideal_state") or {}
    target_artist_mode = ideal.get("target_artist_mode")
    retrieval_profile = ideal.get("retrieval_profile")
    if sample.get("pack") == "POS_exact_entity_success_control":
        target_artist_mode = "same_artist"
        retrieval_profile = "exact_probe"
    entities = []
    for target_entity in ideal.get("current_target_entities") or []:
        entities.append(
            {
                "type": target_entity.get("type", "artist"),
                "value": target_entity.get("value"),
                "role": target_entity.get("role", "current_target"),
                "use_as_retrieval_seed": bool(target_entity.get("use_as_retrieval_seed", True)),
            }
        )
    for prior in ideal.get("prior_entities") or []:
        entities.append(
            {
                "type": prior.get("type", "artist"),
                "value": prior.get("value"),
                "role": prior.get("role", "history"),
                "use_as_retrieval_seed": bool(prior.get("use_as_retrieval_seed")),
            }
        )
    target = ideal.get("target") or {}
    if target.get("artist") and not entities:
        entities.append(
            {
                "type": "artist",
                "value": target["artist"],
                "role": "current_target",
                "use_as_retrieval_seed": True,
            }
        )
    return {
        "schema_valid": True,
        "current_request": None,
        "target_artist_mode": target_artist_mode,
        "retrieval_profile": retrieval_profile,
        "entities": entities,
        "rejections": [
            {"kind": "artist", "value": "strict_ids", "scope": "hard"}
        ]
        if "normalized_rejections" in ideal
        else [],
        "temporal_constraint": ideal.get("temporal_constraint"),
    }


def _norm(text: Any) -> str:
    text = str(text or "").casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _expected_checks(sample: dict[str, Any]) -> dict[str, Any] | None:
    expected = sample.get("expected_state_checks")
    return expected if isinstance(expected, dict) else None


def _as_allowed_values(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _first_allowed(value: Any) -> Any:
    values = _as_allowed_values(value)
    return values[0] if values else None


def _first_allowed_mapping(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    return {key: _first_allowed(field_value) for key, field_value in value.items()}


def _matches_value(actual: Any, expected: Any) -> bool:
    actual_norm = _norm(actual)
    expected_norm = _norm(expected)
    if actual_norm == expected_norm:
        return True
    if len(actual_norm) < 4 or len(expected_norm) < 4:
        return False
    return expected_norm in actual_norm or actual_norm in expected_norm


def _matches_allowed(actual: Any, expected: Any) -> bool:
    allowed = _as_allowed_values(expected)
    return not allowed or actual in allowed


def _rejection_value_matches(actual: Any, expected: Any) -> bool:
    actual_norm = _norm(actual)
    expected_norm = _norm(expected)
    if actual_norm == expected_norm:
        return True
    if len(actual_norm) < 4 or len(expected_norm) < 4:
        return False
    return expected_norm in actual_norm or actual_norm in expected_norm


def _role_correct(sample: dict[str, Any], observed: dict[str, Any]) -> bool:
    expected = _expected_checks(sample)
    if expected is not None:
        entities = observed.get("entities") or []
        for entity_expectation in expected.get("entities") or []:
            expected_value = entity_expectation.get("value")
            entity = next(
                (
                    candidate
                    for candidate in entities
                    if _matches_value(candidate.get("value"), expected_value)
                ),
                None,
            )
            if entity_expectation.get("required", True) and entity is None:
                return False
            if entity is None:
                continue
            allowed_roles = set(entity_expectation.get("allowed_roles") or [])
            if allowed_roles and entity.get("role") not in allowed_roles:
                return False
            if (
                "use_as_retrieval_seed" in entity_expectation
                and entity.get("use_as_retrieval_seed")
                != entity_expectation["use_as_retrieval_seed"]
            ):
                return False
        forbidden_seed_values = expected.get("forbidden_seed_values") or []
        for entity in entities:
            if not entity.get("use_as_retrieval_seed"):
                continue
            if any(_matches_value(entity.get("value"), value) for value in forbidden_seed_values):
                return False
        return True

    ideal = sample.get("ideal_state") or {}
    current_targets = ideal.get("current_target_entities") or []
    entities = observed.get("entities") or []
    by_value = {_norm(entity.get("value")): entity for entity in entities}
    for target in current_targets:
        entity = by_value.get(_norm(target.get("value")))
        if entity is None:
            return False
        if entity.get("role") not in {"current_target", "seed"}:
            return False
        if target.get("use_as_retrieval_seed") is True and not entity.get("use_as_retrieval_seed"):
            return False

    priors = ideal.get("prior_entities") or []
    if not priors:
        return True
    for prior in priors:
        entity = by_value.get(_norm(prior.get("value")))
        if entity is None:
            continue
        if prior.get("use_as_retrieval_seed") is False and entity.get("use_as_retrieval_seed"):
            return False
        if entity.get("role") in {"current_target", "seed"}:
            return False
    return True


def _request_type_correct(sample: dict[str, Any], observed: dict[str, Any]) -> bool:
    expected_checks = _expected_checks(sample)
    if expected_checks is None:
        return True
    allowed = _as_allowed_values(expected_checks.get("request_type"))
    if not allowed:
        return True
    current_request = observed.get("current_request") or {}
    return current_request.get("request_type") in allowed


def _target_artist_mode_correct(sample: dict[str, Any], observed: dict[str, Any]) -> bool:
    expected_checks = _expected_checks(sample)
    if expected_checks is not None:
        allowed = _as_allowed_values(expected_checks.get("target_artist_mode"))
        return not allowed or observed.get("target_artist_mode") in allowed

    # Exact named-entity requests are governed by retrieval_profile=exact_probe;
    # the same/new/any artist axis is not well-defined for "play Numb by Linkin
    # Park" because the artist is specified rather than a continuation policy.
    if sample.get("pack") == "POS_exact_entity_success_control":
        return True
    if sample.get("pack") == "P1_rejection_guardrail_failure":
        return True
    expected = (sample.get("ideal_state") or {}).get("target_artist_mode")
    actual = observed.get("target_artist_mode")
    if expected == "new_artist" and actual in {"any_artist", "unknown"}:
        # The critical state property for these novelty gaps is "do not keep
        # fanning out the prior artist." any_artist plus retrieval_profile=novelty
        # satisfies that extractor contract.
        return observed.get("retrieval_profile") == "novelty"
    return expected is None or actual == expected


def _retrieval_profile_correct(sample: dict[str, Any], observed: dict[str, Any]) -> bool:
    expected_checks = _expected_checks(sample)
    if expected_checks is not None:
        allowed = _as_allowed_values(expected_checks.get("retrieval_profile"))
        return not allowed or observed.get("retrieval_profile") in allowed

    if sample.get("pack") == "POS_exact_entity_success_control":
        return observed.get("retrieval_profile") == "exact_probe"
    if sample.get("pack") == "P1_rejection_guardrail_failure":
        return True
    expected = (sample.get("ideal_state") or {}).get("retrieval_profile")
    return expected is None or observed.get("retrieval_profile") == expected


def _temporal_correct(sample: dict[str, Any], observed: dict[str, Any]) -> bool:
    expected_checks = _expected_checks(sample)
    if expected_checks is not None:
        expected = expected_checks.get("temporal_constraint")
        if expected is None:
            return True
        actual = observed.get("temporal_constraint") or {}
        return (
            _matches_allowed(actual.get("kind"), expected.get("kind"))
            and _matches_allowed(actual.get("strength"), expected.get("strength"))
            and _matches_allowed(
                actual.get("apply_as_filter"),
                expected.get("apply_as_filter"),
            )
        )

    expected = (sample.get("ideal_state") or {}).get("temporal_constraint")
    if not expected:
        return True
    actual = observed.get("temporal_constraint") or {}
    return (
        actual.get("kind") == expected.get("kind")
        and actual.get("strength") == expected.get("strength")
        and actual.get("apply_as_filter") == expected.get("apply_as_filter")
    )


def _rejection_correct(sample: dict[str, Any], observed: dict[str, Any]) -> bool:
    expected_checks = _expected_checks(sample)
    if expected_checks is not None:
        soft_values = expected_checks.get("soft_rejection_values") or []
        hard_required = expected_checks.get("requires_hard_rejection")
        hard_values = expected_checks.get("hard_rejection_values") or []
        if not hard_required and not hard_values and not soft_values:
            return True
        rejections = [
            rejection
            for rejection in observed.get("rejections") or []
            if rejection.get("scope") == "hard"
        ]
        soft_rejections = [
            rejection
            for rejection in observed.get("rejections") or []
            if rejection.get("scope") == "soft"
        ]
        hard_ok = True
        if hard_required or hard_values:
            hard_ok = (
                bool(rejections)
                if not hard_values
                else any(
                    _rejection_value_matches(rejection.get("value"), value)
                    for rejection in rejections
                    for value in hard_values
                )
            )
        soft_ok = True
        if soft_values:
            soft_ok = any(
                _rejection_value_matches(rejection.get("value"), value)
                for rejection in soft_rejections
                for value in soft_values
            )
        return hard_ok and soft_ok

    ideal = sample.get("ideal_state") or {}
    if "normalized_rejections" not in ideal and "rejection" not in sample.get("pack", ""):
        return True
    rejections = observed.get("rejections") or []
    return any(rejection.get("scope") == "hard" for rejection in rejections)


def _positive_control_preserved(sample: dict[str, Any], observed: dict[str, Any]) -> bool:
    if sample.get("class_type") != "positive_control":
        return True
    return bool(observed.get("schema_valid")) and _target_artist_mode_correct(sample, observed)


def _score_checks(sample: dict[str, Any], observed: dict[str, Any] | None) -> dict[str, bool]:
    observed = observed or {"schema_valid": False}
    return {
        "schema_valid": bool(observed.get("schema_valid")),
        "request_type_correct": _request_type_correct(sample, observed),
        "role_correct": _role_correct(sample, observed),
        "target_artist_mode_correct": _target_artist_mode_correct(sample, observed),
        "retrieval_profile_correct": _retrieval_profile_correct(sample, observed),
        "temporal_semantics_correct": _temporal_correct(sample, observed),
        "rejection_normalization_correct": _rejection_correct(sample, observed),
        "positive_control_preserved": _positive_control_preserved(sample, observed),
    }


def compact_state_read(observed: dict[str, Any] | None) -> dict[str, Any]:
    observed = observed or {}
    return {
        "current_request": observed.get("current_request"),
        "target_artist_mode": observed.get("target_artist_mode"),
        "retrieval_profile": observed.get("retrieval_profile"),
        "entities": (observed.get("entities") or [])[:8],
        "rejections": observed.get("rejections") or [],
        "temporal_constraint": observed.get("temporal_constraint"),
    }


def desired_state_read(sample: dict[str, Any]) -> dict[str, Any]:
    expected = _expected_checks(sample)
    if expected is not None:
        return {
            "expected_check_source": "expected_state_checks",
            "request_type": _as_allowed_values(expected.get("request_type")),
            "target_artist_mode": _as_allowed_values(expected.get("target_artist_mode")),
            "retrieval_profile": _as_allowed_values(expected.get("retrieval_profile")),
            "entities": expected.get("entities") or [],
            "forbidden_seed_values": expected.get("forbidden_seed_values") or [],
            "temporal_constraint": expected.get("temporal_constraint"),
            "requires_hard_rejection": expected.get("requires_hard_rejection", False),
            "hard_rejection_values": expected.get("hard_rejection_values") or [],
            "soft_rejection_values": expected.get("soft_rejection_values") or [],
            "notes": expected.get("notes"),
        }

    ideal = sample.get("ideal_state") or {}
    return {
        "target_artist_mode": ideal.get("target_artist_mode"),
        "retrieval_profile": ideal.get("retrieval_profile"),
        "current_target_entities": ideal.get("current_target_entities") or [],
        "prior_entities": ideal.get("prior_entities") or ideal.get("entities") or [],
        "temporal_constraint": ideal.get("temporal_constraint"),
        "normalized_rejections": ideal.get("normalized_rejections"),
        "state_to_retriever_contract": ideal.get("state_to_retriever_contract"),
    }


def compare_state_change(
    sample: dict[str, Any],
    previous: dict[str, Any] | None,
    new: dict[str, Any] | None,
) -> dict[str, Any]:
    previous_checks = _score_checks(sample, previous)
    new_checks = _score_checks(sample, new)
    improved = [
        check for check in CHECKS
        if not previous_checks[check] and new_checks[check]
    ]
    regressed = [
        check for check in CHECKS
        if previous_checks[check] and not new_checks[check]
    ]
    still_missing = [
        check for check in CHECKS
        if not previous_checks[check] and not new_checks[check]
    ]
    return {
        "previous_all_pass": all(previous_checks.values()),
        "new_all_pass": all(new_checks.values()),
        "captured_expected_info": all(new_checks.values()),
        "improved_checks": improved,
        "regressed_checks": regressed,
        "still_missing_checks": still_missing,
        "previous_checks": previous_checks,
        "new_checks": new_checks,
        "previous_read": compact_state_read(previous),
        "new_read": compact_state_read(new),
        "desired_read": desired_state_read(sample),
    }


def score_sample(sample: dict[str, Any], observed: dict[str, Any] | None) -> dict[str, Any]:
    observed = observed or {"schema_valid": False}
    checks = _score_checks(sample, observed)
    previous = observed_from_state_snapshot(sample)
    comparison = compare_state_change(sample, previous, observed)
    return {
        "sample_id": sample["sample_id"],
        "pack": sample["pack"],
        "class_type": sample.get("class_type"),
        "observed_target_artist_mode": observed.get("target_artist_mode"),
        "observed_retrieval_profile": observed.get("retrieval_profile"),
        "observed_temporal_constraint": observed.get("temporal_constraint"),
        "observed_rejections": observed.get("rejections"),
        "previous_all_pass": comparison["previous_all_pass"],
        "new_all_pass": comparison["new_all_pass"],
        "captured_expected_info": comparison["captured_expected_info"],
        "improved_checks": comparison["improved_checks"],
        "regressed_checks": comparison["regressed_checks"],
        "still_missing_checks": comparison["still_missing_checks"],
        "previous_read": comparison["previous_read"],
        "new_read": comparison["new_read"],
        "desired_read": comparison["desired_read"],
        **checks,
        "all_pass": all(checks.values()),
    }


def evaluate_observed_states(
    samples: list[dict[str, Any]],
    observed_by_sample_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    rows = [
        score_sample(sample, observed_by_sample_id.get(sample["sample_id"]))
        for sample in samples
    ]
    by_pack: dict[str, dict[str, Any]] = {}
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["pack"]].append(row)
    for pack, pack_rows in sorted(grouped.items()):
        by_pack[pack] = {
            "samples": len(pack_rows),
            "all_pass_rate": sum(row["all_pass"] for row in pack_rows) / len(pack_rows),
            **{
                f"{check}_rate": sum(row[check] for row in pack_rows) / len(pack_rows)
                for check in CHECKS
            },
        }
    summary = {
        "samples": len(rows),
        "all_pass_rate": (
            sum(row["all_pass"] for row in rows) / len(rows)
            if rows
            else 0.0
        ),
    }
    return {"summary": summary, "by_pack": by_pack, "rows": rows}
