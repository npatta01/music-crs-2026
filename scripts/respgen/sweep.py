from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any, Sequence

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
from scripts.respgen.offline_judge import (
    _judge_prompt,
    _score_with_litellm,
    aggregate_judge_scores,
    build_audit,
)
from scripts.respgen.run_variant import (
    DEFAULT_DATASET,
    DEFAULT_MODEL,
    DEFAULT_TRACK_DATASET,
    _litellm_responses,
    _template_responses,
)


DEFAULT_VARIANTS = ",".join(
    [
        "anchor_replay",
        "top1_concise_qwen",
        "top1_context_qwen",
        "top1_constraint_honest_qwen",
        "top1_concise_alt_model",
    ]
)
DEFAULT_ALT_MODEL = "openrouter/anthropic/claude-sonnet-4"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run frozen-retrieval response-generation variants and write audits.")
    parser.add_argument("--base", required=True, help="Base prediction .zip or .json, e.g. submission/v10_lgbm_A.zip")
    parser.add_argument("--trace", help="Trace sidecar JSONL for state-conditioned variants and audits.")
    parser.add_argument("--out-dir", required=True, help="Directory for variant JSON, zips, audits, and report.")
    parser.add_argument("--variants", default=DEFAULT_VARIANTS, help="Comma-separated variant names.")
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument("--dataset-split", default="test")
    parser.add_argument("--track-dataset", default=DEFAULT_TRACK_DATASET)
    parser.add_argument("--track-split", default="all_tracks")
    parser.add_argument("--dry-run-template", action="store_true", help="Use deterministic templates instead of API calls.")
    parser.add_argument("--model-name", default=DEFAULT_MODEL, help="Generator model for Qwen variants.")
    parser.add_argument("--alt-model-name", default=DEFAULT_ALT_MODEL, help="Generator model for top1_concise_alt_model.")
    parser.add_argument("--temperature", type=float, default=None, help="Override all variant temperatures.")
    parser.add_argument("--max-tokens", type=int, default=None, help="Override all variant max tokens.")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--limit", type=int, default=0, help="Optional row limit for smoke tests.")
    parser.add_argument("--promote-response-track", action="store_true", help="Allow retrieval-affecting safe-candidate variants.")
    parser.add_argument("--judge-model", default="", help="Optional LLM judge model. Omit for heuristic-only audits.")
    parser.add_argument("--judge-temperature", type=float, default=0.0)
    parser.add_argument("--judge-max-tokens", type=int, default=1024)
    parser.add_argument("--judge-batch-size", type=int, default=8)
    parser.add_argument("--report-rows", type=int, default=80, help="Number of cases to render in the HTML report.")
    return parser


def _variant_names(raw: str) -> list[str]:
    names = [name.strip() for name in raw.split(",") if name.strip()]
    if not names:
        raise ValueError("--variants must include at least one variant")
    return names


def _key(row: dict[str, Any]) -> tuple[str, int]:
    return (row["session_id"], int(row["turn_number"]))


def _all_track_ids(rows: Sequence[dict[str, Any]]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for row in rows:
        for track_id in row.get("predicted_track_ids") or []:
            if track_id and track_id not in seen:
                seen.add(track_id)
                out.append(track_id)
    return out


def _resolve_generation_args(
    name: str,
    flags: dict[str, Any],
    args: argparse.Namespace,
) -> tuple[str, float, int, int]:
    model_name = args.alt_model_name if name == "top1_concise_alt_model" else args.model_name
    temperature = args.temperature if args.temperature is not None else float(flags.get("temperature", 0.0))
    max_tokens = args.max_tokens if args.max_tokens is not None else int(flags.get("max_tokens", 512))
    echo_retries = int(flags.get("echo_retries", 0))
    return model_name, temperature, max_tokens, echo_retries


def _score_rows(
    rows: list[dict[str, Any]],
    dataset_rows: dict[str, dict[str, Any]],
    metadata: dict[str, dict[str, Any]],
    traces: dict[tuple[str, int], dict[str, Any]] | None,
    args: argparse.Namespace,
) -> list[dict[str, Any] | None] | None:
    if not args.judge_model:
        return None
    prompts: list[str] = []
    for row in rows:
        key = _key(row)
        dataset_row = dataset_rows[row["session_id"]]
        trace = ((traces or {}).get(key) or {}).get("trace")
        top_id = (row.get("predicted_track_ids") or [None])[0]
        top_label = label_for_track(top_id, metadata) if top_id else ""
        prompts.append(_judge_prompt(row, dataset_row, top_label, trace))
    return _score_with_litellm(
        prompts,
        model_name=args.judge_model,
        temperature=args.judge_temperature,
        max_tokens=args.judge_max_tokens,
        batch_size=args.judge_batch_size,
    )


def _risk_summary(rows: Sequence[dict[str, Any]], metadata: dict[str, dict[str, Any]]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for row in rows:
        top_id = (row.get("predicted_track_ids") or [None])[0]
        top_label = label_for_track(top_id, metadata) if top_id else ""
        for key, value in response_risk_flags(row, top_label).items():
            if value:
                summary[key] = summary.get(key, 0) + 1
    return summary


def _aggregate_for(
    name: str,
    rows: Sequence[dict[str, Any]],
    metadata: dict[str, dict[str, Any]],
    judge_scores: list[dict[str, Any] | None] | None,
    *,
    out_json: Path | None = None,
    out_zip: Path | None = None,
    model_name: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    echo_retries: int | None = None,
) -> dict[str, Any]:
    responses = [row.get("predicted_response") or "" for row in rows]
    word_counts = [len(response.split()) for response in responses]
    char_counts = [len(response) for response in responses]
    return {
        "name": name,
        "rows": len(rows),
        "json": str(out_json) if out_json else None,
        "zip": str(out_zip) if out_zip else None,
        "model_name": model_name,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "echo_retries": echo_retries,
        "mean_response_words": (sum(word_counts) / len(word_counts)) if word_counts else 0.0,
        "mean_response_chars": (sum(char_counts) / len(char_counts)) if char_counts else 0.0,
        "lexical_diversity": distinct_n(responses, n=2),
        "heuristic_summary": summarize_audits(rows),
        "risk_summary": _risk_summary(rows, metadata),
        "judge_summary": aggregate_judge_scores(judge_scores) if judge_scores is not None else None,
    }


def _delta(anchor: dict[str, Any] | None, base: dict[str, Any] | None) -> dict[str, Any] | None:
    if not anchor or not base:
        return None
    risk_keys = sorted(set(anchor["risk_summary"]) | set(base["risk_summary"]))
    anchor_judge = anchor.get("judge_summary") or {}
    base_judge = base.get("judge_summary") or {}
    return {
        "mean_response_words": anchor["mean_response_words"] - base["mean_response_words"],
        "mean_response_chars": anchor["mean_response_chars"] - base["mean_response_chars"],
        "lexical_diversity": anchor["lexical_diversity"] - base["lexical_diversity"],
        "risk_summary": {
            key: anchor["risk_summary"].get(key, 0) - base["risk_summary"].get(key, 0)
            for key in risk_keys
        },
        "mean_combined_judge": (
            anchor_judge.get("mean_combined") - base_judge.get("mean_combined")
            if anchor_judge.get("mean_combined") is not None and base_judge.get("mean_combined") is not None
            else None
        ),
    }


def _state_for_report(trace_row: dict[str, Any] | None) -> dict[str, Any]:
    trace = (trace_row or {}).get("trace") or {}
    state = trace.get("extracted_state") or trace.get("state") or {}
    if not isinstance(state, dict):
        return {}
    return {
        "turn_intent": state.get("turn_intent"),
        "mentioned_entities": state.get("mentioned_entities"),
        "explicit_rejections": state.get("explicit_rejections"),
        "release_year_range": state.get("release_year_range"),
        "lyrical_theme": state.get("lyrical_theme"),
    }


def _html_json(value: Any) -> str:
    return html.escape(json.dumps(value, ensure_ascii=False, indent=2))


def _write_html_report(
    path: Path,
    *,
    base_rows: list[dict[str, Any]],
    variant_rows_by_name: dict[str, list[dict[str, Any]]],
    summaries: list[dict[str, Any]],
    comparison: dict[str, Any],
    dataset_rows: dict[str, dict[str, Any]],
    metadata: dict[str, dict[str, Any]],
    traces: dict[tuple[str, int], dict[str, Any]] | None,
    audit_by_name: dict[str, dict[str, Any]],
    report_rows: int,
) -> None:
    rows_by_name = {"base_v10_lgbm_A": base_rows, **variant_rows_by_name}
    audit_rows_by_name = {
        name: {_key(row): row for row in (audit.get("rows") or [])}
        for name, audit in audit_by_name.items()
    }
    parts = [
        "<!doctype html><html><head><meta charset='utf-8'>",
        "<title>Top-1 Response Sweep</title>",
        "<style>body{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;margin:24px;line-height:1.35;color:#172033}"
        "table{border-collapse:collapse;width:100%;margin:12px 0 28px}th,td{border:1px solid #dde3ec;padding:7px;vertical-align:top}"
        "th{background:#eef5fb;text-align:left}.case{border-top:3px solid #8aa9c5;padding-top:18px;margin-top:24px}"
        "pre{white-space:pre-wrap;background:#f7f9fb;border:1px solid #dde3ec;padding:8px;max-height:320px;overflow:auto}"
        ".response{max-width:560px}.small{color:#5d6b7a;font-size:12px}</style></head><body>",
        "<h1>Top-1 Response Sweep</h1>",
        "<h2>Aggregate</h2><table><tr><th>Name</th><th>Rows</th><th>Model</th><th>Temp</th><th>Max tokens</th>"
        "<th>Mean words</th><th>Distinct-2</th><th>Risks</th><th>Judge</th><th>Zip</th></tr>",
    ]
    for summary in summaries:
        judge = summary.get("judge_summary") or {}
        parts.append(
            "<tr>"
            f"<td>{html.escape(summary['name'])}</td>"
            f"<td>{summary['rows']}</td>"
            f"<td>{html.escape(str(summary.get('model_name') or 'existing'))}</td>"
            f"<td>{html.escape(str(summary.get('temperature')))}</td>"
            f"<td>{html.escape(str(summary.get('max_tokens')))}</td>"
            f"<td>{summary['mean_response_words']:.1f}</td>"
            f"<td>{summary['lexical_diversity']:.3f}</td>"
            f"<td><pre>{_html_json(summary.get('risk_summary') or {})}</pre></td>"
            f"<td>{html.escape(str(judge.get('mean_combined')))}</td>"
            f"<td>{html.escape(str(summary.get('zip') or ''))}</td>"
            "</tr>"
        )
    parts.append("</table>")
    parts.append("<h2>Anchor Vs Base</h2>")
    parts.append(f"<pre>{_html_json(comparison)}</pre>")
    parts.append("<h2>Cases</h2>")
    for base_row in base_rows[:report_rows]:
        key = _key(base_row)
        dataset_row = dataset_rows.get(base_row["session_id"], {})
        latest_user = ""
        previous_user = ""
        for turn in dataset_row.get("conversations") or []:
            if turn.get("role") == "user":
                previous_user = latest_user
                latest_user = str(turn.get("content") or "")
        top_id = (base_row.get("predicted_track_ids") or [None])[0]
        top_label = label_for_track(top_id, metadata) if top_id else ""
        parts.append("<div class='case'>")
        parts.append(
            f"<h3>{html.escape(base_row['session_id'])} / turn {html.escape(str(base_row['turn_number']))}</h3>"
            f"<div><b>Top-1:</b> {html.escape(str(top_id))} - {html.escape(top_label)}</div>"
            f"<div><b>Latest user:</b> {html.escape(latest_user)}</div>"
            f"<div class='small'><b>Previous user:</b> {html.escape(previous_user)}</div>"
            f"<details><summary>State</summary><pre>{_html_json(_state_for_report((traces or {}).get(key)))}</pre></details>"
        )
        parts.append("<table><tr><th>Name</th><th>Response</th><th>Risks</th><th>Judge</th></tr>")
        for name, rows in rows_by_name.items():
            row_by_key = {_key(row): row for row in rows}
            row = row_by_key.get(key)
            if not row:
                continue
            audit_row = (audit_rows_by_name.get(name) or {}).get(key) or {}
            response = html.escape(row.get("predicted_response") or "")
            parts.append(
                "<tr>"
                f"<td>{html.escape(name)}</td>"
                f"<td class='response'>{response}</td>"
                f"<td><pre>{_html_json(audit_row.get('risk_flags') or {})}</pre></td>"
                f"<td><pre>{_html_json(audit_row.get('judge'))}</pre></td>"
                "</tr>"
            )
        parts.append("</table></div>")
    parts.append("</body></html>")
    path.write_text("\n".join(parts), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    variant_names = _variant_names(args.variants)

    base_rows = load_predictions(args.base)
    if args.limit:
        base_rows = base_rows[: args.limit]
    dataset_rows = load_dataset_rows_by_session(args.dataset, split=args.dataset_split)
    metadata = load_track_metadata(_all_track_ids(base_rows), dataset_name=args.track_dataset, split=args.track_split)
    traces = load_traces(args.trace) if args.trace else None

    base_judge_scores = _score_rows(base_rows, dataset_rows, metadata, traces, args)
    base_audit = build_audit(base_rows, dataset_rows, metadata, traces, base_judge_scores)
    base_summary = _aggregate_for("base_v10_lgbm_A", base_rows, metadata, base_judge_scores)

    summaries = [base_summary]
    audits: dict[str, dict[str, Any]] = {"base_v10_lgbm_A": base_audit}
    variant_rows_by_name: dict[str, list[dict[str, Any]]] = {}

    for name in variant_names:
        flags = variant_flags_for_name(name)
        model_name, temperature, max_tokens, echo_retries = _resolve_generation_args(name, flags, args)
        captured_requests: list[dict[str, Any]] = []

        def generate(requests: list[dict[str, Any]]) -> list[str]:
            captured_requests[:] = requests
            if args.dry_run_template:
                return _template_responses(requests)
            return _litellm_responses(
                requests,
                model_name=model_name,
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
        out_json = out_dir / f"{name}.json"
        out_zip = out_dir / f"{name}.zip"
        write_predictions(rows, out_json)
        write_submission_zip(rows, out_zip)

        judge_scores = _score_rows(rows, dataset_rows, metadata, traces, args)
        audit = build_audit(rows, dataset_rows, metadata, traces, judge_scores)
        audit["variant"] = name
        audit["selection_changed"] = sum(1 for req in captured_requests if req.get("selection_changed"))
        audit_path = out_dir / f"{name}.audit.json"
        audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")

        variant_rows_by_name[name] = rows
        audits[name] = audit
        summaries.append(
            _aggregate_for(
                name,
                rows,
                metadata,
                judge_scores,
                out_json=out_json,
                out_zip=out_zip,
                model_name=None if args.dry_run_template else model_name,
                temperature=temperature,
                max_tokens=max_tokens,
                echo_retries=echo_retries,
            )
        )

    summary_by_name = {summary["name"]: summary for summary in summaries}
    comparison = {
        "anchor_replay_vs_base_v10_lgbm_A": _delta(
            summary_by_name.get("anchor_replay"),
            summary_by_name.get("base_v10_lgbm_A"),
        )
    }
    report_path = out_dir / "top1_response_sweep.html"
    _write_html_report(
        report_path,
        base_rows=base_rows,
        variant_rows_by_name=variant_rows_by_name,
        summaries=summaries,
        comparison=comparison,
        dataset_rows=dataset_rows,
        metadata=metadata,
        traces=traces,
        audit_by_name=audits,
        report_rows=args.report_rows,
    )

    summary = {
        "base": args.base,
        "trace": args.trace,
        "out_dir": str(out_dir),
        "dry_run_template": args.dry_run_template,
        "judge_model": args.judge_model or None,
        "variants": variant_names,
        "summaries": summaries,
        "comparison": comparison,
        "report": str(report_path),
    }
    summary_path = out_dir / "sweep_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "summaries"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
