from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.respgen.common import (
    build_variant_rows,
    distinct_n,
    label_for_track,
    load_dataset_rows_by_session,
    load_predictions,
    load_track_metadata,
    load_traces,
    response_risk_flags,
    summarize_audits,
    variant_flags_for_name,
    write_predictions,
    write_submission_zip,
)


DEFAULT_DATASET = "talkpl-ai/TalkPlayData-Challenge-Blind-A"
DEFAULT_TRACK_DATASET = "talkpl-ai/TalkPlayData-Challenge-Track-Metadata"
DEFAULT_MODEL = "openrouter/qwen/qwen3-30b-a3b-instruct-2507"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Regenerate only predicted_response from a frozen prediction file.")
    parser.add_argument("--base", required=True, help="Base prediction .zip or .json, e.g. submission/v10_lgbm_A.zip")
    parser.add_argument("--out", required=True, help="Output prediction JSON path.")
    parser.add_argument("--zip-out", help="Optional CodaBench zip output path.")
    parser.add_argument(
        "--variant",
        default="top1_concise_qwen",
        help=(
            "Variant name, e.g. phase2_best_qwen, anchor_replay, top1_concise_qwen, "
            "top1_context_qwen, top1_constraint_honest_qwen, top1_concise_alt_model."
        ),
    )
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument("--dataset-split", default="test")
    parser.add_argument("--track-dataset", default=DEFAULT_TRACK_DATASET)
    parser.add_argument("--track-split", default="all_tracks")
    parser.add_argument("--trace", help="Optional trace sidecar JSONL.")
    parser.add_argument("--use-trace-state", action="store_true", help="Append extracted trace state to response context.")
    parser.add_argument("--promote-response-track", action="store_true", help="Move the selected safe response track to rank 1.")
    parser.add_argument("--dry-run-template", action="store_true", help="Use deterministic template responses instead of LiteLLM.")
    parser.add_argument("--model-name", default=DEFAULT_MODEL)
    parser.add_argument("--temperature", type=float, default=None, help="Override variant/default generation temperature.")
    parser.add_argument("--max-tokens", type=int, default=None, help="Override variant/default max tokens.")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--limit", type=int, default=0, help="Optional row limit for smoke tests.")
    parser.add_argument("--metadata-out", help="Optional JSON sidecar with run summary.")
    return parser


def _load_dotenv_quietly() -> None:
    try:
        from dotenv import load_dotenv
    except Exception:
        return
    load_dotenv()


def _system_prompt() -> str:
    root = Path(__file__).resolve().parents[2]
    role = (root / "mcrs/system_prompts/roleplay.txt").read_text(encoding="utf-8")
    response = (root / "mcrs/system_prompts/response_generation.txt").read_text(encoding="utf-8")
    return role + response


def _template_responses(requests: list[dict[str, Any]]) -> list[str]:
    responses: list[str] = []
    for req in requests:
        label = req.get("selected_track_label") or "this track"
        latest = (req.get("latest_user") or "").strip()
        if len(latest) > 110:
            latest = latest[:107].rstrip() + "..."
        responses.append(
            f"Try {label}. It keeps close to your latest request"
            + (f" ({latest})" if latest else "")
            + " while giving you a concrete next direction."
        )
    return responses


def _litellm_responses(
    requests: list[dict[str, Any]],
    *,
    model_name: str,
    temperature: float,
    max_tokens: int,
    batch_size: int,
    echo_retries: int = 0,
) -> list[str]:
    _load_dotenv_quietly()
    from mcrs.lm_modules.litellm_chat import LITELLM_LM
    from mcrs.response_context import is_metadata_echo

    lm = LITELLM_LM(model_name=model_name, temperature=temperature, max_tokens=max_tokens)
    sys_prompt = _system_prompt()
    outputs: list[str] = []
    for start in range(0, len(requests), batch_size):
        batch = requests[start : start + batch_size]
        contexts = [[{"role": "user", "content": req["context"]}] for req in batch]
        items = [req["recommend_item"] for req in batch]
        batch_outputs = lm.batch_response_generation([sys_prompt] * len(batch), contexts, items)
        if echo_retries > 0:
            for i, response in enumerate(batch_outputs):
                attempts = 0
                while is_metadata_echo(response) and attempts < echo_retries:
                    response = lm.response_generation(sys_prompt, contexts[i], items[i])
                    attempts += 1
                batch_outputs[i] = response
        outputs.extend(batch_outputs)
    return outputs


def _all_track_ids(rows: list[dict[str, Any]]) -> list[str]:
    seen: set[str] = set()
    ids: list[str] = []
    for row in rows:
        for track_id in row.get("predicted_track_ids") or []:
            if track_id and track_id not in seen:
                seen.add(track_id)
                ids.append(track_id)
    return ids


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    base_rows = load_predictions(args.base)
    if args.limit:
        base_rows = base_rows[: args.limit]

    flags = variant_flags_for_name(args.variant)
    if args.use_trace_state:
        flags["trace_state"] = True
    temperature = args.temperature if args.temperature is not None else float(flags.get("temperature", 0.0))
    max_tokens = args.max_tokens if args.max_tokens is not None else int(flags.get("max_tokens", 512))
    echo_retries = int(flags.get("echo_retries", 0))

    dataset_rows = load_dataset_rows_by_session(args.dataset, split=args.dataset_split)
    metadata = load_track_metadata(_all_track_ids(base_rows), dataset_name=args.track_dataset, split=args.track_split)
    traces = load_traces(args.trace) if args.trace else None

    captured_requests: list[dict[str, Any]] = []

    def generate(requests: list[dict[str, Any]]) -> list[str]:
        captured_requests[:] = requests
        if args.dry_run_template:
            return _template_responses(requests)
        return _litellm_responses(
            requests,
            model_name=args.model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            batch_size=args.batch_size,
            echo_retries=echo_retries,
        )

    rows = build_variant_rows(
        base_rows,
        dataset_rows,
        metadata,
        flags,
        generate,
        promote_response_track=args.promote_response_track,
        trace_rows_by_key=traces,
    )
    write_predictions(rows, args.out)
    if args.zip_out:
        write_submission_zip(rows, args.zip_out)

    risk_summary: dict[str, int] = {}
    for row in rows:
        top_id = (row.get("predicted_track_ids") or [None])[0]
        top_label = label_for_track(top_id, metadata) if top_id else ""
        for key, value in response_risk_flags(row, top_label).items():
            if value:
                risk_summary[key] = risk_summary.get(key, 0) + 1
    summary = {
        "base": args.base,
        "out": args.out,
        "zip_out": args.zip_out,
        "variant": args.variant,
        "rows": len(rows),
        "dry_run_template": args.dry_run_template,
        "model_name": None if args.dry_run_template else args.model_name,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "echo_retries": echo_retries,
        "promote_response_track": args.promote_response_track,
        "trace": args.trace,
        "trace_state": bool(flags.get("trace_state")),
        "selection_changed": sum(1 for req in captured_requests if req.get("selection_changed")),
        "lexical_diversity": distinct_n((row.get("predicted_response") or "" for row in rows), n=2),
        "heuristic_summary": summarize_audits(rows),
        "risk_summary": risk_summary,
    }
    if args.metadata_out:
        Path(args.metadata_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.metadata_out).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
