#!/usr/bin/env python
"""Evaluate state extraction on the focused replay pack.

Examples:
  uv run python scripts/evaluate_state_replay_pack.py --state-source ideal
  uv run python scripts/evaluate_state_replay_pack.py --state-source jsonl --states scripts/states.jsonl
  OPENROUTER_API_KEY=... uv run python scripts/evaluate_state_replay_pack.py --state-source live
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcrs.conversation_state.replay_eval import (  # noqa: E402
    FOCUSED_PACKS,
    apply_expected_state_overrides,
    build_full_history_messages_for_extraction,
    compare_state_change,
    evaluate_observed_states,
    limit_samples_per_pack,
    load_replay_pack,
    observed_from_ideal,
    observed_from_state,
    observed_from_state_snapshot,
    trim_messages_for_extraction,
)
from mcrs.conversation_state.schema import ConversationStateV0Plus  # noqa: E402
from mcrs.qu_modules.compiler_v0plus_qu import (  # noqa: E402
    LiteLLMExtractor,
    session_memory_to_conversation,
)


DEFAULT_PACK = Path(
    "experiments/analysis/devset_recall_gap_v0plus_all_retrievers_2026_06_06/"
    "state_experiment_pack.json"
)
HF_CONVERSATION_DATASET = "talkpl-ai/TalkPlayData-Challenge-Dataset"


def _pack_names(value: str) -> tuple[str, ...] | None:
    if value == "all":
        return ()
    if value == "focused":
        return FOCUSED_PACKS
    return tuple(part.strip() for part in value.split(",") if part.strip())


def _load_jsonl_states(path: Path) -> dict[str, dict[str, Any]]:
    return {
        sample_id: _observed_from_jsonl_row(row)
        for sample_id, row in _load_jsonl_rows(path).items()
    }


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


def _load_expected_overrides(path: Path) -> dict[str, dict[str, Any]]:
    data = json.loads(path.read_text())
    if "overrides" in data:
        return data["overrides"]
    return data


def _observed_from_jsonl_row(row: dict[str, Any]) -> dict[str, Any]:
    raw_state = row.get("new_state", row.get("state", row))
    if raw_state is None:
        if row.get("observed"):
            return row["observed"]
        return {"schema_valid": False, "error": row.get("error") or "state is null"}
    try:
        state = ConversationStateV0Plus.model_validate(raw_state)
    except Exception as exc:
        if row.get("observed"):
            return row["observed"]
        return {"schema_valid": False, "error": str(exc)}
    return observed_from_state(state)


def _new_state_from_jsonl_row(row: dict[str, Any] | None) -> Any:
    if not row:
        return None
    return row.get("new_state", row.get("state"))


def _audit_row(
    sample: dict[str, Any],
    *,
    state_source: str,
    observed: dict[str, Any] | None,
    new_state: Any,
    model: str | None = None,
    error: str | None = None,
    source_row: dict[str, Any] | None = None,
) -> dict[str, Any]:
    previous_observed = observed_from_state_snapshot(sample)
    comparison = compare_state_change(sample, previous_observed, observed)
    return {
        "sample_id": sample["sample_id"],
        "pack": sample["pack"],
        "class_type": sample.get("class_type"),
        "state_source": state_source,
        "source_row_state_source": (source_row or {}).get("state_source"),
        "model": model,
        "current_user": sample.get("current_user"),
        "previous_state": sample.get("state_snapshot"),
        "previous_observed": previous_observed,
        "new_state": new_state,
        "new_observed": observed,
        "desired_state": sample.get("ideal_state"),
        "evaluation": comparison,
        # Backward-compatible aliases for older scripts and existing notebooks.
        "state": new_state,
        "observed": observed,
        "ideal_state": sample.get("ideal_state"),
        "error": error,
    }


def _credential_error(args: argparse.Namespace) -> str | None:
    if args.api_base:
        return None
    if args.model.startswith("openrouter/") and not os.environ.get("OPENROUTER_API_KEY"):
        return "OPENROUTER_API_KEY is required for direct OpenRouter live extraction"
    if args.model.startswith("openai/") and not os.environ.get("OPENAI_API_KEY"):
        return "OPENAI_API_KEY is required for direct OpenAI live extraction"
    return None


def _load_full_history_by_session(dataset_name: str) -> dict[str, list[dict[str, Any]]]:
    from datasets import load_dataset

    dataset = load_dataset(dataset_name, split="test")
    return {
        row["session_id"]: (row.get("conversations") or [])
        for row in dataset
        if row.get("session_id")
    }


def _run_live(
    samples: list[dict[str, Any]],
    args: argparse.Namespace,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    if error := _credential_error(args):
        raise SystemExit(error)

    extractor = LiteLLMExtractor(
        model_name=args.model,
        api_base=args.api_base,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        timeout_s=args.timeout_s,
        prompt_version=args.prompt_version,
    )
    full_history_by_session = (
        _load_full_history_by_session(args.hf_dataset)
        if args.history_source == "full"
        else {}
    )
    observed: dict[str, dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []
    for idx, sample in enumerate(samples, start=1):
        history_source = "window"
        session_memory = trim_messages_for_extraction(sample)
        if args.history_source == "full":
            full_messages = full_history_by_session.get(sample.get("session_id"))
            if full_messages:
                session_memory = build_full_history_messages_for_extraction(
                    sample,
                    full_messages,
                )
                history_source = "full"
        conversation, played = session_memory_to_conversation(session_memory, catalog=None)
        state = None
        error = None
        try:
            state = extractor.extract(conversation, played)
        except Exception as exc:
            error = f"{type(exc).__name__}: {str(exc).splitlines()[0][:1000]}"
        if state is None:
            row_observed = {
                "schema_valid": False,
                "error": error or "extractor returned None",
            }
            row_state = None
        else:
            row_observed = observed_from_state(state)
            row_state = state.model_dump(mode="json")
        observed[sample["sample_id"]] = row_observed
        rows.append(
            _audit_row(
                sample,
                state_source="live",
                observed=row_observed,
                new_state=row_state,
                model=args.model,
                error=error,
            )
        )
        rows[-1]["prompt_version"] = args.prompt_version
        rows[-1]["history_source"] = history_source
        print(f"[{idx}/{len(samples)}] {sample['sample_id']}", file=sys.stderr)
    return observed, rows


def _rows_for_source(
    samples: list[dict[str, Any]],
    observed: dict[str, dict[str, Any]],
    source: str,
    *,
    raw_rows_by_id: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    rows = []
    for sample in samples:
        source_row = (raw_rows_by_id or {}).get(sample["sample_id"])
        if source == "ideal":
            new_state = sample.get("ideal_state")
        else:
            new_state = _new_state_from_jsonl_row(source_row)
        rows.append(
            _audit_row(
                sample,
                state_source=source,
                observed=observed.get(sample["sample_id"]),
                new_state=new_state,
                source_row=source_row,
                error=(source_row or {}).get("error"),
            )
        )
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _markdown_json_block(value: Any) -> str:
    return "```json\n" + json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n```"


def _write_markdown_report(
    path: Path,
    result: dict[str, Any],
    *,
    state_source: str,
    model: str | None,
    samples: list[dict[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = result["rows"]
    captured = sum(row.get("captured_expected_info") for row in rows)
    improved_rows = sum(bool(row.get("improved_checks")) for row in rows)
    regressed_rows = sum(bool(row.get("regressed_checks")) for row in rows)
    lines = [
        "# State Replay Extraction Report",
        "",
        f"- State source: `{state_source}`",
        f"- Model: `{model or 'n/a'}`",
        f"- Samples: `{result['summary']['samples']}`",
        f"- Overall all-pass rate: `{result['summary']['all_pass_rate']:.3f}`",
        f"- New state captures expected information: `{captured}/{len(rows)}`",
        f"- Improved vs previous trace state: `{improved_rows}/{len(rows)}`",
        f"- Regressed vs previous trace state: `{regressed_rows}/{len(rows)}`",
        "",
        "## Pack Results",
        "",
        "| Pack | N | All Pass | Request Type | Role | Artist Mode | Profile | Temporal | Rejection | Positive Control |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for pack, stats in result["by_pack"].items():
        lines.append(
            "| {pack} | {samples} | {all_pass:.3f} | {request_type:.3f} | {role:.3f} | {artist:.3f} | {profile:.3f} | {temporal:.3f} | {rejection:.3f} | {positive:.3f} |".format(
                pack=pack,
                samples=stats["samples"],
                all_pass=stats["all_pass_rate"],
                request_type=stats["request_type_correct_rate"],
                role=stats["role_correct_rate"],
                artist=stats["target_artist_mode_correct_rate"],
                profile=stats["retrieval_profile_correct_rate"],
                temporal=stats["temporal_semantics_correct_rate"],
                rejection=stats["rejection_normalization_correct_rate"],
                positive=stats["positive_control_preserved_rate"],
            )
        )
    failures = [row for row in rows if not row["all_pass"]]
    sample_by_id = {sample["sample_id"]: sample for sample in samples}
    lines.extend(
        [
            "",
            "## State Change Evaluation",
            "",
            "Each row compares the previous trace state snapshot against the new extracted state and the desired state contract for the replay example.",
            "",
            "## Failures",
            "",
        ]
    )
    if not failures:
        lines.append("No failing checks.")
    else:
        for row in failures[:50]:
            failed = [
                key
                for key, value in row.items()
                if key.endswith("_correct") or key in {"schema_valid", "positive_control_preserved"}
                if value is False
            ]
            sample = sample_by_id.get(row["sample_id"], {})
            evaluation_read = {
                "previous_all_pass": row.get("previous_all_pass"),
                "new_all_pass": row.get("new_all_pass"),
                "captured_expected_info": row.get("captured_expected_info"),
                "improved_checks": row.get("improved_checks"),
                "regressed_checks": row.get("regressed_checks"),
                "still_missing_checks": row.get("still_missing_checks"),
            }
            current_user = str(sample.get("current_user") or "")
            state_change_read = {
                "previous_state_read": row.get("previous_read"),
                "new_state_read": row.get("new_read"),
                "desired_state_read": row.get("desired_read"),
                "evaluation": evaluation_read,
            }
            lines.extend(
                [
                    f"### `{row['sample_id']}`",
                    "",
                    f"- Pack: `{row['pack']}`",
                    f"- Failed checks: `{', '.join(failed)}`",
                    f"- Current user: {current_user[:500]}",
                    "",
                    _markdown_json_block(state_change_read),
                    "",
                ]
            )
        if len(failures) > 50:
            lines.append(f"\nOnly the first 50 of {len(failures)} failures are shown.")
    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pack", type=Path, default=DEFAULT_PACK)
    parser.add_argument("--packs", default="focused")
    parser.add_argument("--limit-per-pack", type=int)
    parser.add_argument("--expected-overrides", type=Path, help="JSON overlay with human-reviewed expected_state_checks")
    parser.add_argument("--only-overrides", action="store_true", help="Evaluate only samples listed in --expected-overrides")
    parser.add_argument("--state-source", choices=["ideal", "jsonl", "live"], required=True)
    parser.add_argument("--states", type=Path, help="JSONL with sample_id and state fields for --state-source jsonl")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--observed-output", type=Path, help="JSONL audit rows with observed/raw states")
    parser.add_argument("--markdown-report", type=Path, help="Human-readable extraction report")
    parser.add_argument("--model", default="openrouter/deepseek/deepseek-v4-flash")
    parser.add_argument("--prompt-version", default="current")
    parser.add_argument("--api-base", default=None)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=8000)
    parser.add_argument("--timeout-s", type=int, default=120)
    parser.add_argument(
        "--history-source",
        choices=["window", "full"],
        default="window",
        help="For live extraction, use replay recent_messages or full HF session history.",
    )
    parser.add_argument("--hf-dataset", default=HF_CONVERSATION_DATASET)
    args = parser.parse_args()

    samples = load_replay_pack(args.pack, packs=_pack_names(args.packs))
    if args.expected_overrides:
        samples = apply_expected_state_overrides(
            samples,
            _load_expected_overrides(args.expected_overrides),
            filter_to_overrides=args.only_overrides,
        )
    samples = limit_samples_per_pack(samples, args.limit_per_pack)
    if args.state_source == "ideal":
        observed = {sample["sample_id"]: observed_from_ideal(sample) for sample in samples}
        observed_rows = _rows_for_source(samples, observed, "ideal")
    elif args.state_source == "jsonl":
        if args.states is None:
            raise SystemExit("--states is required for --state-source jsonl")
        raw_rows_by_id = _load_jsonl_rows(args.states)
        observed = {
            sample_id: _observed_from_jsonl_row(row)
            for sample_id, row in raw_rows_by_id.items()
        }
        observed_rows = _rows_for_source(
            samples,
            observed,
            "jsonl",
            raw_rows_by_id=raw_rows_by_id,
        )
    else:
        observed, observed_rows = _run_live(samples, args)

    result = evaluate_observed_states(samples, observed)
    if args.observed_output:
        _write_jsonl(args.observed_output, observed_rows)
    if args.markdown_report:
        _write_markdown_report(
            args.markdown_report,
            result,
            state_source=args.state_source,
            model=(
                f"{args.model} / prompt={args.prompt_version}"
                if args.state_source == "live"
                else None
            ),
            samples=samples,
        )
    payload = json.dumps(result, indent=2)
    if args.output:
        args.output.write_text(payload + "\n")
    print(payload)


if __name__ == "__main__":
    main()
