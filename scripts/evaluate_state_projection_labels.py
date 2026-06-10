#!/usr/bin/env python
"""Evaluate compiler-facing projection against state fact labels.

Fact labels include both extraction-level checks and compiler-facing checks.
This script scores only what the current compiler sees after deterministic
projection:

- positive `compiler_mentioned_entities`
- `compiler_style_reference_entities`
- forbidden stale positive entities
- negative `compiler_mentioned_entities`
- `compiler_explicit_rejections`
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcrs.conversation_state.state_fact_eval import _matches_value  # noqa: E402


def _load_labels(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text())
    if isinstance(data, list):
        return data
    return data.get("fact_labels") or []


def _load_jsonl(path: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        rows[row["sample_id"]] = row
    return rows


def _value_matches(
    rows: list[dict[str, Any]],
    value: Any,
    *,
    sentiment: int | None = None,
) -> bool:
    for row in rows:
        if sentiment is not None and row.get("sentiment") != sentiment:
            continue
        if _matches_value(row.get("value"), value):
            return True
    return False


def _kind_ok(actual: str | None, expected: str | None) -> bool:
    if not expected:
        return True
    return actual == expected or {actual, expected} <= {"tag", "style"}


def _rejection_matches(rows: list[dict[str, Any]], expectation: dict[str, Any]) -> bool:
    for row in rows:
        if not _kind_ok(row.get("kind"), expectation.get("type")):
            continue
        if _matches_value(row.get("value"), expectation.get("value")):
            return True
    return False


def score_projection_labels(
    labels: list[dict[str, Any]],
    audit_rows: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for label in labels:
        sample_id = label["sample_id"]
        observed = (audit_rows.get(sample_id) or {}).get("new_observed") or {}
        mentions = observed.get("compiler_mentioned_entities") or []
        style_refs = observed.get("compiler_style_reference_entities") or []
        positive_retriever_inputs = mentions + style_refs
        rejections = observed.get("compiler_explicit_rejections") or []
        missing: list[str] = []
        fact_label = label.get("fact_label") or {}

        for expectation in fact_label.get("required_entities") or []:
            value = expectation.get("value")
            if expectation.get("use_as_retrieval_seed") is True:
                if not _value_matches(positive_retriever_inputs, value, sentiment=1):
                    missing.append(f"positive:{value}")
            elif expectation.get("use_as_retrieval_seed") is False:
                if _value_matches(mentions, value, sentiment=1):
                    missing.append(f"forbidden_positive:{value}")

        for value in fact_label.get("forbidden_seed_values") or []:
            if _value_matches(mentions, value, sentiment=1):
                missing.append(f"forbidden_positive:{value}")

        for expectation in fact_label.get("required_style_references") or []:
            value = expectation.get("value")
            if not _value_matches(style_refs, value, sentiment=1):
                missing.append(f"style_reference:{value}")

        for value in fact_label.get("forbidden_style_references") or []:
            if _value_matches(style_refs, value, sentiment=1):
                missing.append(f"forbidden_style_reference:{value}")

        for expectation in fact_label.get("required_exclusions") or []:
            value = expectation.get("value")
            if not _value_matches(mentions, value, sentiment=-1):
                missing.append(f"negative_mention:{value}")
            if not _rejection_matches(rejections, expectation):
                missing.append(f"explicit_rejection:{value}")

        rows.append(
            {
                "sample_id": sample_id,
                "pack": label.get("pack"),
                "fact_class": label.get("fact_class"),
                "pass": not missing,
                "missing": missing,
                "compiler_mentioned_entities": mentions,
                "compiler_style_reference_entities": style_refs,
                "compiler_explicit_rejections": rejections,
            }
        )

    return {
        "summary": {
            "samples": len(rows),
            "pass_rate": sum(row["pass"] for row in rows) / len(rows) if rows else 0.0,
            "passes": sum(row["pass"] for row in rows),
            "failures": sum(not row["pass"] for row in rows),
        },
        "rows": rows,
        "matching": "state_fact_eval token containment; positives include exact compiler mentions plus style-reference anchors",
    }


def _write_report(path: Path, result: dict[str, Any]) -> None:
    summary = result["summary"]
    lines = [
        "# State Projection Label Evaluation",
        "",
        f"- Samples: `{summary['samples']}`",
        f"- Passes: `{summary['passes']}`",
        f"- Failures: `{summary['failures']}`",
        f"- Pass rate: `{summary['pass_rate']:.3f}`",
        "",
        "## Failures",
        "",
    ]
    failures = [row for row in result["rows"] if not row["pass"]]
    if not failures:
        lines.append("No projection failures.")
    for row in failures:
        lines.extend(
            [
                f"### `{row['sample_id']}`",
                "",
                f"- Pack: `{row['pack']}`",
                f"- Fact class: `{row['fact_class']}`",
                f"- Missing: `{', '.join(row['missing'])}`",
                "",
                "```json",
                json.dumps(
                    {
                        "compiler_mentioned_entities": row[
                            "compiler_mentioned_entities"
                        ],
                        "compiler_style_reference_entities": row[
                            "compiler_style_reference_entities"
                        ],
                        "compiler_explicit_rejections": row[
                            "compiler_explicit_rejections"
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                "```",
                "",
            ]
        )
    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--states", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--markdown-report", type=Path)
    args = parser.parse_args()

    result = score_projection_labels(_load_labels(args.labels), _load_jsonl(args.states))
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n")
    if args.markdown_report:
        args.markdown_report.parent.mkdir(parents=True, exist_ok=True)
        _write_report(args.markdown_report, result)
    print(payload)


if __name__ == "__main__":
    main()
