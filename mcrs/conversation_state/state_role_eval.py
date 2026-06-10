"""Role-specific evaluator for conversation-state extraction.

This evaluator scores the state contract the compiler actually needs:
exact entity seeds, style references, query facets, exclusions, and temporal
guardrails. It deliberately keeps `request_type` as an allowed-set hint rather
than a single brittle class label.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from mcrs.conversation_state.state_fact_eval import _matches_allowed, _matches_value, _tokens


CHECKS = (
    "schema_valid",
    "request_type",
    "exact_seeds",
    "style_references",
    "query_facets",
    "context_entities",
    "exclusions",
    "forbidden_exact_seeds",
    "temporal_constraint",
)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _label(label: dict[str, Any]) -> dict[str, Any]:
    return label.get("state_label") or label.get("fact_label") or {}


def _fact_matches_type(fact: dict[str, Any], expectation: dict[str, Any]) -> bool:
    expected = expectation.get("type")
    return not expected or fact.get("type") == expected or (
        expected == "tag" and fact.get("type") == "attribute"
    )


def _fact_matches_facet(fact: dict[str, Any], expectation: dict[str, Any]) -> bool:
    expected = expectation.get("facet")
    return not expected or fact.get("facet") == expected


def _fact_matches_value(fact: dict[str, Any], expectation: dict[str, Any]) -> bool:
    return _matches_value(fact.get("value"), expectation.get("value"))


def _find_fact(
    facts: list[dict[str, Any]],
    expectation: dict[str, Any],
    *,
    relation: str | None = None,
    reuse: str | None = None,
) -> dict[str, Any] | None:
    for fact in facts:
        if relation is not None and fact.get("relation") != relation:
            continue
        if reuse is not None and fact.get("reuse") != reuse:
            continue
        if not _fact_matches_type(fact, expectation):
            continue
        if not _fact_matches_facet(fact, expectation):
            continue
        if _fact_matches_value(fact, expectation):
            return fact
    return None


def _is_exact_seed(fact: dict[str, Any]) -> bool:
    return (
        fact.get("type") in {"artist", "album", "track"}
        and fact.get("role") == "current_target"
        and fact.get("anchor_use") == "must_use"
        and fact.get("relation") == "exact_target"
        and fact.get("reuse") == "must_reuse"
    )


def _find_exact_seed(
    facts: list[dict[str, Any]],
    expectation: dict[str, Any],
) -> dict[str, Any] | None:
    for fact in facts:
        if not _is_exact_seed(fact):
            continue
        if not _fact_matches_type(fact, expectation):
            continue
        if _fact_matches_value(fact, expectation):
            return fact
    return None


def _score_request_type(
    state_label: dict[str, Any],
    observed: dict[str, Any],
) -> tuple[bool, list[str]]:
    allowed = (
        state_label.get("allowed_request_types")
        or _as_list(state_label.get("request_type"))
    )
    if not allowed:
        return True, []
    current_request = observed.get("current_request") or {}
    actual = current_request.get("request_type")
    actual_types = [actual]
    for candidate in current_request.get("candidate_types") or []:
        try:
            confidence = float(candidate.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        if confidence >= 0.5:
            actual_types.append(candidate.get("request_type"))
    ok = any(request_type in allowed for request_type in actual_types)
    return ok, [] if ok else [f"request_type: {actual} not in {allowed}"]


def _score_exact_seeds(
    state_label: dict[str, Any],
    observed: dict[str, Any],
) -> tuple[bool, list[str]]:
    facts = observed.get("facts") or []
    missing = []
    for expectation in state_label.get("required_exact_seeds") or []:
        if _find_exact_seed(facts, expectation) is None:
            missing.append(f"exact_seed: {expectation.get('value')}")
    return not missing, missing


def _score_style_references(
    state_label: dict[str, Any],
    observed: dict[str, Any],
) -> tuple[bool, list[str]]:
    facts = observed.get("facts") or []
    projected = observed.get("compiler_style_reference_entities") or []
    missing = []
    for expectation in state_label.get("required_style_references") or []:
        relation_match = _find_fact(
            facts,
            expectation,
            relation="style_reference",
            reuse=expectation.get("reuse"),
        )
        projected_match = any(
            _fact_matches_type(entity, expectation)
            and _fact_matches_value(entity, expectation)
            and entity.get("sentiment", 1) > 0
            for entity in projected
        )
        if relation_match is None and not projected_match:
            missing.append(f"style_reference: {expectation.get('value')}")
    return not missing, missing


def _score_query_facets(
    state_label: dict[str, Any],
    observed: dict[str, Any],
) -> tuple[bool, list[str]]:
    facts = observed.get("facts") or []
    missing = []
    for expectation in state_label.get("required_query_facets") or []:
        query_match = _find_fact(facts, expectation, relation="query_facet")
        if query_match is None and not _query_facet_parts_match(facts, expectation):
            missing.append(f"query_facet: {expectation.get('value')}")
    return not missing, missing


def _query_facet_parts_match(
    facts: list[dict[str, Any]],
    expectation: dict[str, Any],
) -> bool:
    """Allow decomposed retriever-equivalent query facts.

    Example: an expected label of "90s dance hits" is satisfied by separate
    query_facet facts for "1990s dance" and popularity="iconic". The compiler
    sees the same retrieval surfaces even though the model chose atomic facets.
    """

    expected_tokens = set(_query_facet_tokens(expectation.get("value")))
    if not expected_tokens:
        return False
    popularity_tokens = {
        "hit",
        "hits",
        "classic",
        "iconic",
        "famous",
        "popular",
        "well",
        "known",
    }
    needs_popularity = bool(expected_tokens & popularity_tokens)
    expected_content = expected_tokens - popularity_tokens

    observed_tokens: set[str] = set()
    has_popularity = False
    for fact in facts:
        if fact.get("relation") != "query_facet":
            continue
        fact_tokens = set(_query_facet_tokens(fact.get("value")))
        if fact.get("facet") in {"energy", "mood", "genre", "sonic", "performer"}:
            fact_tokens.add(str(fact.get("facet")))
        observed_tokens.update(fact_tokens)
        if fact.get("facet") == "popularity" or fact_tokens & popularity_tokens:
            has_popularity = True

    if expected_content and not expected_content.issubset(observed_tokens):
        return False
    return has_popularity if needs_popularity else bool(expected_content)


def _query_facet_tokens(value: Any) -> list[str]:
    aliases = {
        "90s": "1990s",
        "80s": "1980s",
        "70s": "1970s",
        "energetic": "energy",
        "energizing": "energy",
        "energising": "energy",
    }
    non_retrieval_actions = {
        "boost",
        "boosts",
        "boosting",
        "get",
        "gets",
        "make",
        "makes",
        "making",
        "me",
        "my",
        "put",
        "puts",
        "putting",
    }
    out = []
    for token in _tokens(value):
        canonical = aliases.get(token, token)
        if canonical in non_retrieval_actions:
            continue
        out.append(canonical)
    return out


def _score_context_entities(
    state_label: dict[str, Any],
    observed: dict[str, Any],
) -> tuple[bool, list[str]]:
    facts = observed.get("facts") or []
    exclusions = observed.get("exclusions") or []
    rejections = observed.get("rejections") or []
    missing = []
    for expectation in state_label.get("required_context_entities") or []:
        allowed_roles = set(expectation.get("allowed_roles") or [])
        matched = False
        for fact in facts:
            if not _fact_matches_type(fact, expectation):
                continue
            if not _fact_matches_value(fact, expectation):
                continue
            if (
                fact.get("relation") == "style_reference"
                and not _is_exact_seed(fact)
                and "rejected" not in allowed_roles
            ):
                matched = True
                break
            if allowed_roles and fact.get("role") not in allowed_roles:
                continue
            matched = True
            break
        if not matched:
            matched = any(
                _fact_matches_type(exclusion, expectation)
                and _fact_matches_value(exclusion, expectation)
                for exclusion in exclusions
            ) or any(
                _fact_matches_type(rejection, expectation)
                and _fact_matches_value(rejection, expectation)
                for rejection in rejections
            )
        if not matched:
            missing.append(f"context_entity: {expectation.get('value')}")
    return not missing, missing


def _score_exclusions(
    state_label: dict[str, Any],
    observed: dict[str, Any],
) -> tuple[bool, list[str]]:
    facts = observed.get("facts") or []
    exclusions = observed.get("exclusions") or []
    rejections = observed.get("rejections") or []
    missing = []
    for expectation in state_label.get("required_exclusions") or []:
        value = expectation.get("value")
        matched_fact = _find_fact(facts, expectation, relation="exclude")
        matched_exclusion = any(
            _fact_matches_type(exclusion, expectation)
            and _fact_matches_value(exclusion, expectation)
            for exclusion in exclusions
        )
        matched_rejection = any(
            _matches_value(rejection.get("value"), value)
            and (
                not expectation.get("type")
                or rejection.get("kind") == expectation.get("type")
                or {rejection.get("kind"), expectation.get("type")} <= {"tag", "style"}
            )
            for rejection in rejections
        )
        if not (matched_fact or matched_exclusion or matched_rejection):
            missing.append(f"exclusion: {value}")
    return not missing, missing


def _score_forbidden_exact_seeds(
    state_label: dict[str, Any],
    observed: dict[str, Any],
) -> tuple[bool, list[str]]:
    facts = observed.get("facts") or []
    bad = []
    for expectation in state_label.get("forbidden_exact_seeds") or []:
        if isinstance(expectation, str):
            expectation = {"value": expectation}
        if _find_exact_seed(facts, expectation) is not None:
            bad.append(f"forbidden_exact_seed: {expectation.get('value')}")
    return not bad, bad


def _score_temporal_constraint(
    state_label: dict[str, Any],
    observed: dict[str, Any],
) -> tuple[bool, list[str]]:
    expected = state_label.get("temporal_constraint")
    if expected is None:
        return True, []
    actual = observed.get("temporal_constraint") or {}
    if not actual:
        return False, ["temporal_constraint"]
    mismatches = []
    for field in ("kind", "strength", "apply_as_filter"):
        if field in expected and not _matches_allowed(actual.get(field), expected.get(field)):
            mismatches.append(f"temporal: {field}")
    return not mismatches, mismatches


def score_role_label(label: dict[str, Any], observed: dict[str, Any] | None) -> dict[str, Any]:
    observed = observed or {}
    state_label = _label(label)
    checks_and_missing = {
        "schema_valid": (bool(observed.get("schema_valid")), []),
        "request_type": _score_request_type(state_label, observed),
        "exact_seeds": _score_exact_seeds(state_label, observed),
        "style_references": _score_style_references(state_label, observed),
        "query_facets": _score_query_facets(state_label, observed),
        "context_entities": _score_context_entities(state_label, observed),
        "exclusions": _score_exclusions(state_label, observed),
        "forbidden_exact_seeds": _score_forbidden_exact_seeds(state_label, observed),
        "temporal_constraint": _score_temporal_constraint(state_label, observed),
    }
    checks = {name: ok for name, (ok, _) in checks_and_missing.items()}
    missing_facts = [
        item
        for _, (_, missing) in checks_and_missing.items()
        for item in missing
    ]
    return {
        "sample_id": label["sample_id"],
        "pack": label.get("pack"),
        "fact_class": label.get("fact_class"),
        "checks": checks,
        "all_pass": all(checks.values()),
        "missing_facts": missing_facts,
        "observed_read": {
            "current_request": observed.get("current_request"),
            "facts": observed.get("facts") or [],
            "exclusions": observed.get("exclusions") or [],
            "rejections": observed.get("rejections") or [],
            "temporal_constraint": observed.get("temporal_constraint"),
        },
        "expected_read": state_label,
    }


def _group_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"samples": 0, "all_pass_rate": 0.0}
    stats = {
        "samples": len(rows),
        "all_pass_rate": sum(row["all_pass"] for row in rows) / len(rows),
    }
    for check in CHECKS:
        stats[f"{check}_rate"] = (
            sum(row["checks"].get(check, False) for row in rows) / len(rows)
        )
    return stats


def evaluate_role_labels(
    labels: list[dict[str, Any]],
    observed_by_sample_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    rows = [
        score_role_label(label, observed_by_sample_id.get(label["sample_id"]))
        for label in labels
    ]
    by_pack: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_fact_class: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_pack[str(row.get("pack") or "unknown")].append(row)
        by_fact_class[str(row.get("fact_class") or "unknown")].append(row)
    return {
        "summary": _group_stats(rows),
        "by_pack": {key: _group_stats(value) for key, value in sorted(by_pack.items())},
        "by_fact_class": {
            key: _group_stats(value) for key, value in sorted(by_fact_class.items())
        },
        "rows": rows,
        "matching": "role-specific exact_seed/style_reference/query_facet/exclusion evaluation",
    }
