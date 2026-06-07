#!/usr/bin/env python
"""Evaluate state extraction against role-specific v2 labels."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcrs.conversation_state.replay_eval import observed_from_state  # noqa: E402
from mcrs.conversation_state.schema import ConversationStateV0Plus  # noqa: E402
from mcrs.conversation_state.state_role_eval import evaluate_role_labels  # noqa: E402


def _load_labels(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text())
    if isinstance(data, list):
        return data
    return data.get("state_labels") or data.get("fact_labels") or []


def _load_jsonl_rows(path: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        rows[row["sample_id"]] = row
    return rows


def _observed_from_row(row: dict[str, Any]) -> dict[str, Any]:
    raw_state = row.get("new_state", row.get("state", row))
    try:
        state = ConversationStateV0Plus.model_validate(raw_state)
    except Exception as exc:
        if row.get("new_observed"):
            return row["new_observed"]
        if row.get("observed"):
            return row["observed"]
        return {"schema_valid": False, "error": str(exc)}
    return observed_from_state(state)


def _load_observed(path: Path) -> dict[str, dict[str, Any]]:
    return {
        sample_id: _observed_from_row(row)
        for sample_id, row in _load_jsonl_rows(path).items()
    }


def _write_report(path: Path, result: dict[str, Any], *, labels_path: Path, states_path: Path) -> None:
    summary = result["summary"]
    lines = [
        "# State Role Label Evaluation",
        "",
        f"- Labels: `{labels_path}`",
        f"- States: `{states_path}`",
        f"- Samples: `{summary['samples']}`",
        f"- All-pass: `{summary['all_pass_rate']:.3f}`",
        "",
        "## Checks",
        "",
        "| Check | Rate |",
        "|---|---:|",
    ]
    for key, value in summary.items():
        if key.endswith("_rate") and key != "all_pass_rate":
            lines.append(f"| {key.removesuffix('_rate')} | `{value:.3f}` |")

    failures = [row for row in result["rows"] if not row["all_pass"]]
    lines.extend(["", "## Failures", ""])
    if not failures:
        lines.append("No failing role labels.")
    for row in failures[:80]:
        lines.extend(
            [
                f"### `{row['sample_id']}`",
                "",
                f"- Pack: `{row.get('pack')}`",
                f"- Fact class: `{row.get('fact_class')}`",
                f"- Missing: `{', '.join(row['missing_facts'])}`",
                "",
                "```json",
                json.dumps(
                    {
                        "expected": row["expected_read"],
                        "observed": row["observed_read"],
                        "checks": row["checks"],
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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--states", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--markdown-report", type=Path)
    args = parser.parse_args()

    result = evaluate_role_labels(_load_labels(args.labels), _load_observed(args.states))
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n")
    if args.markdown_report:
        _write_report(
            args.markdown_report,
            result,
            labels_path=args.labels,
            states_path=args.states,
        )
    print(payload)


if __name__ == "__main__":
    main()
