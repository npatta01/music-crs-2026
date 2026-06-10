"""Fact-level evaluator for state extraction.

This evaluator intentionally avoids GT/ranker-derived policy checks. It scores
only facts visible in the conversation: entities, seed usage, exclusions, and
temporal semantics.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any


CHECKS = (
    "schema_valid",
    "request_type",
    "required_entities",
    "forbidden_seeds",
    "required_exclusions",
    "temporal_constraint",
)

COMPILER_CORE_CHECKS = tuple(check for check in CHECKS if check != "request_type")


def _norm(value: Any) -> str:
    text = str(value or "").casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _tokens(value: Any) -> list[str]:
    stopwords = {"a", "an", "and", "in", "of", "or", "the", "to"}
    return [token for token in _norm(value).split() if token not in stopwords]


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _matches_value(actual: Any, expected: Any) -> bool:
    actual_norm = _norm(actual)
    expected_norm = _norm(expected)
    if not actual_norm or not expected_norm:
        return False
    if actual_norm == expected_norm:
        return True
    actual_tokens = set(_tokens(actual))
    expected_tokens = set(_tokens(expected))
    if actual_tokens and expected_tokens and (
        actual_tokens.issubset(expected_tokens)
        or expected_tokens.issubset(actual_tokens)
    ):
        return True
    if len(actual_norm) < 4 or len(expected_norm) < 4:
        return False
    return expected_norm in actual_norm or actual_norm in expected_norm


def _matches_allowed(actual: Any, expected: Any) -> bool:
    allowed = _as_list(expected)
    return not allowed or actual in allowed


def _score_request_type(
    fact_label: dict[str, Any],
    observed: dict[str, Any],
) -> tuple[bool, list[str]]:
    expected = fact_label.get("request_type")
    if expected is None:
        return True, []
    current_request = observed.get("current_request") or {}
    actual = current_request.get("request_type")
    return actual == expected, [] if actual == expected else ["request_type"]


def _entity_type_allowed(entity: dict[str, Any], expectation: dict[str, Any]) -> bool:
    allowed_types = _as_list(expectation.get("type") or expectation.get("allowed_types"))
    return not allowed_types or entity.get("type") in allowed_types


def _find_entity(
    entities: list[dict[str, Any]],
    expectation: dict[str, Any],
) -> dict[str, Any] | None:
    expected_value = expectation.get("value")
    for entity in entities:
        if not _entity_type_allowed(entity, expectation):
            continue
        if _matches_value(entity.get("value"), expected_value):
            return entity
    return None


def _score_required_entities(
    fact_label: dict[str, Any],
    observed: dict[str, Any],
) -> tuple[bool, list[str]]:
    entities = observed.get("entities") or []
    missing: list[str] = []
    for expectation in fact_label.get("required_entities") or []:
        entity = _find_entity(entities, expectation)
        value = expectation.get("value")
        if entity is None:
            missing.append(str(value))
            continue
        allowed_roles = set(expectation.get("allowed_roles") or [])
        if allowed_roles and entity.get("role") not in allowed_roles:
            missing.append(str(value))
            missing.append(f"{value} role in {sorted(allowed_roles)}")
        if (
            "use_as_retrieval_seed" in expectation
            and entity.get("use_as_retrieval_seed")
            != expectation["use_as_retrieval_seed"]
        ):
            missing.append(str(value))
            missing.append(
                f"{value} use_as_retrieval_seed={expectation['use_as_retrieval_seed']}"
            )
    return not missing, missing


def _score_forbidden_seeds(
    fact_label: dict[str, Any],
    observed: dict[str, Any],
) -> tuple[bool, list[str]]:
    forbidden = fact_label.get("forbidden_seed_values") or []
    if not forbidden:
        return True, []
    bad = []
    for entity in observed.get("entities") or []:
        if not entity.get("use_as_retrieval_seed"):
            continue
        for value in forbidden:
            if _matches_value(entity.get("value"), value):
                bad.append(str(value))
    return not bad, bad


def _observed_exclusions(observed: dict[str, Any]) -> list[dict[str, Any]]:
    exclusions: list[dict[str, Any]] = []
    for rejection in observed.get("rejections") or []:
        exclusions.append(
            {
                "value": rejection.get("value"),
                "type": rejection.get("kind"),
                "scope": rejection.get("scope", "hard"),
            }
        )
    for entity in observed.get("entities") or []:
        if entity.get("role") == "rejected":
            exclusions.append(
                {
                    "value": entity.get("value"),
                    "type": entity.get("type"),
                    "scope": "hard",
                }
            )
    return exclusions


def _score_required_exclusions(
    fact_label: dict[str, Any],
    observed: dict[str, Any],
) -> tuple[bool, list[str]]:
    expectations = fact_label.get("required_exclusions") or []
    if not expectations:
        return True, []
    exclusions = _observed_exclusions(observed)
    missing: list[str] = []
    for expectation in expectations:
        expected_scope = expectation.get("scope")
        matched = False
        for exclusion in exclusions:
            if expected_scope and exclusion.get("scope") != expected_scope:
                continue
            if not _entity_type_allowed(exclusion, expectation):
                continue
            if _matches_value(exclusion.get("value"), expectation.get("value")):
                matched = True
                break
        if not matched:
            missing.append(str(expectation.get("value")))
    return not missing, missing


def _score_temporal_constraint(
    fact_label: dict[str, Any],
    observed: dict[str, Any],
) -> tuple[bool, list[str]]:
    expected = fact_label.get("temporal_constraint")
    if expected is None:
        return True, []
    actual = observed.get("temporal_constraint") or {}
    if not actual:
        return False, ["temporal_constraint"]
    mismatches = []
    for field in ("kind", "strength", "apply_as_filter"):
        if field in expected and not _matches_allowed(actual.get(field), expected.get(field)):
            mismatches.append(field)
    return not mismatches, mismatches


def score_fact_label(label: dict[str, Any], observed: dict[str, Any] | None) -> dict[str, Any]:
    observed = observed or {}
    fact_label = label.get("fact_label") or {}
    request_type_ok, request_type_mismatches = _score_request_type(fact_label, observed)
    entity_ok, missing_entities = _score_required_entities(fact_label, observed)
    forbidden_ok, bad_seeds = _score_forbidden_seeds(fact_label, observed)
    exclusions_ok, missing_exclusions = _score_required_exclusions(fact_label, observed)
    temporal_ok, temporal_mismatches = _score_temporal_constraint(fact_label, observed)
    checks = {
        "schema_valid": bool(observed.get("schema_valid")),
        "request_type": request_type_ok,
        "required_entities": entity_ok,
        "forbidden_seeds": forbidden_ok,
        "required_exclusions": exclusions_ok,
        "temporal_constraint": temporal_ok,
    }
    missing_facts = (
        request_type_mismatches
        + missing_entities
        + [f"forbidden seed: {value}" for value in bad_seeds]
        + [f"exclusion: {value}" for value in missing_exclusions]
        + [f"temporal: {field}" for field in temporal_mismatches]
    )
    return {
        "sample_id": label["sample_id"],
        "pack": label.get("pack"),
        "fact_class": label.get("fact_class"),
        "request_type": fact_label.get("request_type"),
        "checks": checks,
        "all_pass": all(checks.values()),
        "compiler_core_pass": all(checks[check] for check in COMPILER_CORE_CHECKS),
        "missing_facts": missing_facts,
        "observed_read": {
            "current_request": observed.get("current_request"),
            "facts": observed.get("facts") or [],
            "entities": observed.get("entities") or [],
            "exclusions": observed.get("exclusions") or [],
            "rejections": observed.get("rejections") or [],
            "temporal_constraint": observed.get("temporal_constraint"),
        },
        "expected_read": fact_label,
    }


def _group_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"samples": 0, "all_pass_rate": 0.0}
    stats = {
        "samples": len(rows),
        "all_pass_rate": sum(row["all_pass"] for row in rows) / len(rows),
        "compiler_core_pass_rate": (
            sum(row["compiler_core_pass"] for row in rows) / len(rows)
        ),
    }
    for check in CHECKS:
        stats[f"{check}_rate"] = (
            sum(row["checks"].get(check, False) for row in rows) / len(rows)
        )
    return stats


def evaluate_fact_labels(
    labels: list[dict[str, Any]],
    observed_by_sample_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    rows = [
        score_fact_label(label, observed_by_sample_id.get(label["sample_id"]))
        for label in labels
    ]
    by_pack_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_fact_class_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_pack_rows[str(row.get("pack") or "unknown")].append(row)
        by_fact_class_rows[str(row.get("fact_class") or "unknown")].append(row)
    return {
        "summary": _group_stats(rows),
        "by_pack": {
            pack: _group_stats(pack_rows)
            for pack, pack_rows in sorted(by_pack_rows.items())
        },
        "by_fact_class": {
            fact_class: _group_stats(class_rows)
            for fact_class, class_rows in sorted(by_fact_class_rows.items())
        },
        "rows": rows,
    }
