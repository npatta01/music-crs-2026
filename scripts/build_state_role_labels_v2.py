#!/usr/bin/env python
"""Convert v1 fact labels into role-specific v2 state labels.

The conversion is intentionally based on the v1 label semantics, not on
conversation text. It separates compiler-input roles that v1 compressed into
`required_entities.use_as_retrieval_seed`.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


_REQUEST_EQUIVALENTS = {
    "attribute_search": ["attribute_search", "similar_to_prior"],
    "similar_to_prior": ["similar_to_prior", "attribute_search"],
    "exact_artist": ["exact_artist", "same_artist"],
    "same_artist": ["same_artist", "exact_artist"],
    "exact_album": ["exact_album", "same_album", "hidden_target", "attribute_search"],
    "same_album": ["same_album", "exact_album", "hidden_target", "attribute_search"],
    "new_artist": ["new_artist", "attribute_search", "similar_to_prior"],
}

_EXACT_REQUEST_TYPES = {
    "exact_track",
    "exact_album",
    "same_album",
    "exact_artist",
    "same_artist",
}

_STYLE_REQUEST_TYPES = {
    "similar_to_prior",
    "new_artist",
}

_ROLE_MAP = {
    "satisfied": "satisfied_prior",
    "satisfied_prior": "satisfied_prior",
    "history": "history",
    "contrast": "contrast",
    "rejected": "rejected",
}


def _load_labels(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text())
    if isinstance(data, list):
        return data
    return data.get("fact_labels") or []


def _dedupe_dicts(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        key = json.dumps(item, sort_keys=True, ensure_ascii=False)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _allowed_request_types(request_type: str | None) -> list[str]:
    if not request_type:
        return []
    return _REQUEST_EQUIVALENTS.get(request_type, [request_type])


def _normalize_temporal_constraint(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    out = dict(value)
    allowed_kinds = set(_as_list(out.get("kind")))
    if allowed_kinds and "release_date" not in allowed_kinds:
        out["apply_as_filter"] = False
        out["strength"] = "soft"
    return out


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _context_roles(allowed_roles: list[str]) -> list[str]:
    roles = [
        mapped
        for role in allowed_roles
        if (mapped := _ROLE_MAP.get(str(role))) is not None
    ]
    return sorted(set(roles))


def _convert_entity(expectation: dict[str, Any], request_type: str | None) -> dict[str, list[dict[str, Any]]]:
    out = {
        "required_exact_seeds": [],
        "required_style_references": [],
        "required_query_facets": [],
        "required_context_entities": [],
        "forbidden_exact_seeds": [],
    }
    entity_type = expectation.get("type")
    value = expectation.get("value")
    if not value:
        return out

    if entity_type == "tag":
        out["required_query_facets"].append(
            {
                "type": "tag",
                "value": value,
                **({"facet": expectation["facet"]} if expectation.get("facet") else {}),
            }
        )
        return out

    if expectation.get("use_as_retrieval_seed") is True:
        payload = {"type": entity_type, "value": value}
        if request_type in _STYLE_REQUEST_TYPES or request_type == "attribute_search":
            out["required_style_references"].append(payload)
        elif request_type in _EXACT_REQUEST_TYPES:
            out["required_exact_seeds"].append(payload)
        else:
            out["required_exact_seeds"].append(payload)
        return out

    allowed_roles = _context_roles(expectation.get("allowed_roles") or [])
    if allowed_roles:
        out["required_context_entities"].append(
            {"type": entity_type, "value": value, "allowed_roles": allowed_roles}
        )
    if entity_type in {"artist", "album", "track"}:
        out["forbidden_exact_seeds"].append({"type": entity_type, "value": value})
    return out


def convert_label(label: dict[str, Any]) -> dict[str, Any]:
    fact_label = label.get("fact_label") or {}
    request_type = fact_label.get("request_type")
    state_label: dict[str, Any] = {
        "allowed_request_types": _allowed_request_types(request_type),
        "required_exact_seeds": [],
        "required_style_references": [],
        "required_query_facets": [],
        "required_context_entities": [],
        "required_exclusions": list(fact_label.get("required_exclusions") or []),
        "forbidden_exact_seeds": [],
    }
    score_temporal = fact_label.get("request_type") not in {
        "exact_track",
        "exact_artist",
        "exact_album",
        "same_artist",
        "same_album",
    }
    if score_temporal and fact_label.get("temporal_constraint") is not None:
        state_label["temporal_constraint"] = _normalize_temporal_constraint(
            fact_label["temporal_constraint"]
        )

    for expectation in fact_label.get("required_entities") or []:
        converted = _convert_entity(expectation, request_type)
        for key, values in converted.items():
            state_label[key].extend(values)

    for value in fact_label.get("forbidden_seed_values") or []:
        state_label["forbidden_exact_seeds"].append({"value": value})

    for key in (
        "required_exact_seeds",
        "required_style_references",
        "required_query_facets",
        "required_context_entities",
        "required_exclusions",
        "forbidden_exact_seeds",
    ):
        state_label[key] = _dedupe_dicts(state_label[key])

    return {
        "sample_id": label["sample_id"],
        "pack": label.get("pack"),
        "fact_class": label.get("fact_class"),
        "state_label": state_label,
        "source_fact_label": fact_label,
        "label_version": "state_roles_v2",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    labels = [convert_label(label) for label in _load_labels(args.input)]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps({"state_labels": labels}, ensure_ascii=False, indent=2) + "\n"
    )
    print(f"wrote {args.output} labels={len(labels)}")


if __name__ == "__main__":
    main()
