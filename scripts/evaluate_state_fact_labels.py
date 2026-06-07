#!/usr/bin/env python
"""Evaluate live/existing state extraction against hand-labeled facts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcrs.conversation_state.replay_eval import observed_from_state  # noqa: E402
from mcrs.conversation_state.schema import ConversationStateV0Plus  # noqa: E402
from mcrs.conversation_state.state_fact_eval import evaluate_fact_labels  # noqa: E402


def _load_labels(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text())
    if isinstance(data, list):
        return data
    return data.get("fact_labels") or []


def _load_jsonl_rows(path: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        sample_id = row.get("sample_id")
        if not sample_id:
            raise ValueError(f"state row missing sample_id: {row}")
        rows[sample_id] = row
    return rows


def _observed_from_jsonl_row(row: dict[str, Any]) -> dict[str, Any]:
    if row.get("new_observed"):
        return row["new_observed"]
    if row.get("observed"):
        return row["observed"]
    raw_state = row.get("new_state", row.get("state", row))
    try:
        state = ConversationStateV0Plus.model_validate(raw_state)
    except Exception as exc:
        return {"schema_valid": False, "error": str(exc)}
    return observed_from_state(state)


def _load_observed(path: Path) -> dict[str, dict[str, Any]]:
    return {
        sample_id: _observed_from_jsonl_row(row)
        for sample_id, row in _load_jsonl_rows(path).items()
    }


def _write_markdown(path: Path, result: dict[str, Any], *, labels_path: Path, states_path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# State Fact Label Evaluation",
        "",
        f"- Labels: `{labels_path}`",
        f"- States: `{states_path}`",
        f"- Samples: `{result['summary']['samples']}`",
        f"- All-pass: `{result['summary']['all_pass_rate']:.3f}`",
        "",
        "## Fact Classes",
        "",
        "| Fact class | N | All pass | Compiler core | Request type | Entities | Forbidden seeds | Exclusions | Temporal |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for fact_class, stats in result["by_fact_class"].items():
        lines.append(
            "| {fact_class} | {samples} | {all_pass:.3f} | {compiler_core:.3f} | {request_type:.3f} | {entities:.3f} | {forbidden:.3f} | {exclusions:.3f} | {temporal:.3f} |".format(
                fact_class=fact_class,
                samples=stats["samples"],
                all_pass=stats["all_pass_rate"],
                compiler_core=stats["compiler_core_pass_rate"],
                request_type=stats["request_type_rate"],
                entities=stats["required_entities_rate"],
                forbidden=stats["forbidden_seeds_rate"],
                exclusions=stats["required_exclusions_rate"],
                temporal=stats["temporal_constraint_rate"],
            )
        )
    lines.extend(
        [
            "",
            "## Packs",
            "",
            "| Pack | N | All pass | Compiler core | Request type | Entities | Forbidden seeds | Exclusions | Temporal |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for pack, stats in result["by_pack"].items():
        lines.append(
            "| {pack} | {samples} | {all_pass:.3f} | {compiler_core:.3f} | {request_type:.3f} | {entities:.3f} | {forbidden:.3f} | {exclusions:.3f} | {temporal:.3f} |".format(
                pack=pack,
                samples=stats["samples"],
                all_pass=stats["all_pass_rate"],
                compiler_core=stats["compiler_core_pass_rate"],
                request_type=stats["request_type_rate"],
                entities=stats["required_entities_rate"],
                forbidden=stats["forbidden_seeds_rate"],
                exclusions=stats["required_exclusions_rate"],
                temporal=stats["temporal_constraint_rate"],
            )
        )
    failures = [row for row in result["rows"] if not row["all_pass"]]
    lines.extend(["", "## Failures", ""])
    if not failures:
        lines.append("No failing fact labels.")
    for row in failures[:80]:
        lines.extend(
            [
                f"### `{row['sample_id']}`",
                "",
                f"- Pack: `{row.get('pack')}`",
                f"- Fact class: `{row.get('fact_class')}`",
                f"- Missing facts: `{', '.join(row['missing_facts'])}`",
                "",
                "```json",
                json.dumps(
                    {
                        "expected": row["expected_read"],
                        "observed": row["observed_read"],
                        "checks": row["checks"],
                        "compiler_core_pass": row["compiler_core_pass"],
                    },
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                ),
                "```",
                "",
            ]
        )
    if len(failures) > 80:
        lines.append(f"Only the first 80 of {len(failures)} failures are shown.")
    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--states", type=Path, required=True, help="JSONL live/audit states")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--markdown-report", type=Path)
    args = parser.parse_args()

    labels = _load_labels(args.labels)
    observed = _load_observed(args.states)
    result = evaluate_fact_labels(labels, observed)
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n")
    if args.markdown_report:
        _write_markdown(
            args.markdown_report,
            result,
            labels_path=args.labels,
            states_path=args.states,
        )
    print(payload)


if __name__ == "__main__":
    main()
