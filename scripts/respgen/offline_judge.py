from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from scripts.respgen.common import (
    distinct_n,
    heuristic_audit_row,
    label_for_track,
    load_dataset_rows_by_session,
    load_predictions,
    load_track_metadata,
    load_traces,
    response_risk_flags,
    summarize_audits,
)


DEFAULT_DATASET = "talkpl-ai/TalkPlayData-Challenge-Blind-A"
DEFAULT_TRACK_DATASET = "talkpl-ai/TalkPlayData-Challenge-Track-Metadata"
DEFAULT_JUDGE = "openrouter/google/gemini-2.5-flash"
JUDGE_SCORE_KEYS = (
    "top1_faithfulness",
    "latest_request_alignment",
    "constraint_respect",
    "grounded_explanation",
    "language_match",
    "response_quality",
)
LEGACY_SCORE_MAP = {
    "personalization": "latest_request_alignment",
    "explanation": "grounded_explanation",
    "constraint_following": "constraint_respect",
}


def parse_judge_response(text: str) -> dict[str, Any] | None:
    """Parse strict judge JSON, returning None on malformed/out-of-range output."""
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I | re.S).strip()
    if not raw.startswith("{"):
        match = re.search(r"\{.*\}", raw, flags=re.S)
        raw = match.group(0) if match else raw
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if all(key in data for key in JUDGE_SCORE_KEYS):
        source_keys = JUDGE_SCORE_KEYS
        key_map = {key: key for key in JUDGE_SCORE_KEYS}
    elif all(key in data for key in LEGACY_SCORE_MAP):
        source_keys = tuple(LEGACY_SCORE_MAP)
        key_map = LEGACY_SCORE_MAP
    else:
        return None
    parsed: dict[str, Any] = {}
    for key in source_keys:
        try:
            value = float(data[key])
        except Exception:
            return None
        if value < 1.0 or value > 5.0:
            return None
        parsed[key_map[key]] = value
    if source_keys != JUDGE_SCORE_KEYS:
        for key in JUDGE_SCORE_KEYS:
            parsed.setdefault(key, 3.0)
    risk_flags = data.get("risk_flags") or {}
    if isinstance(risk_flags, list):
        risk_flags = {str(key): True for key in risk_flags}
    if not isinstance(risk_flags, dict):
        risk_flags = {}
    parsed["risk_flags"] = risk_flags
    parsed["notes"] = str(data.get("notes", ""))
    return parsed


def aggregate_judge_scores(scores: list[dict[str, Any] | None]) -> dict[str, Any]:
    valid = [score for score in scores if score is not None]
    failed = len(scores) - len(valid)

    def mean(key: str) -> float | None:
        if not valid:
            return None
        return sum(float(score[key]) for score in valid) / len(valid)

    means = {f"mean_{key}": mean(key) for key in JUDGE_SCORE_KEYS}
    present_means = [value for value in means.values() if value is not None]
    combined = sum(present_means) / len(present_means) if present_means else None
    risk_counts: dict[str, int] = {}
    for score in valid:
        for key, value in (score.get("risk_flags") or {}).items():
            if value:
                risk_counts[key] = risk_counts.get(key, 0) + 1
    return {
        "n": len(scores),
        "n_scored": len(valid),
        "n_failed": failed,
        **means,
        "mean_combined": combined,
        "risk_counts": risk_counts,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Score response predictions with heuristics and optional LLM judge.")
    parser.add_argument("--predictions", required=True, help="Prediction .zip or .json to audit.")
    parser.add_argument("--out", required=True, help="Output audit JSON path.")
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument("--dataset-split", default="test")
    parser.add_argument("--track-dataset", default=DEFAULT_TRACK_DATASET)
    parser.add_argument("--track-split", default="all_tracks")
    parser.add_argument("--trace", help="Optional trace sidecar JSONL.")
    parser.add_argument("--heuristic-only", action="store_true")
    parser.add_argument("--model-name", default=DEFAULT_JUDGE)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--limit", type=int, default=0)
    return parser


def _load_dotenv_quietly() -> None:
    try:
        from dotenv import load_dotenv
    except Exception:
        return
    load_dotenv()


def _latest_user(dataset_row: dict[str, Any]) -> str:
    for turn in reversed(dataset_row.get("conversations") or []):
        if turn.get("role") == "user":
            return str(turn.get("content", ""))
    return ""


def _previous_user(dataset_row: dict[str, Any]) -> str:
    users = [turn for turn in dataset_row.get("conversations") or [] if turn.get("role") == "user"]
    return str(users[-2].get("content", "")) if len(users) >= 2 else ""


def _prior_music(dataset_row: dict[str, Any]) -> list[str]:
    return [
        str(turn.get("content", ""))
        for turn in dataset_row.get("conversations") or []
        if turn.get("role") == "music" and turn.get("content")
    ][-4:]


def _judge_prompt(row: dict[str, Any], dataset_row: dict[str, Any], top_label: str, trace: dict[str, Any] | None) -> str:
    goal = (dataset_row.get("conversation_goal") or {}).get("listener_goal") or ""
    state = ""
    if trace:
        extracted = trace.get("extracted_state") or trace.get("state") or {}
        if extracted:
            state = json.dumps(
                {
                    "turn_intent": extracted.get("turn_intent"),
                    "mentioned_entities": extracted.get("mentioned_entities"),
                    "explicit_rejections": extracted.get("explicit_rejections"),
                    "release_year_range": extracted.get("release_year_range"),
                    "lyrical_theme": extracted.get("lyrical_theme"),
                },
                ensure_ascii=False,
            )
    return (
        "You are evaluating a music recommender's listener-facing reply. "
        "The response should explain exactly the submitted top recommendation, not the whole top-20 list. "
        "Use 1-5 integers or half-points.\n"
        "Rubric:\n"
        "- top1_faithfulness: reply names/explains the selected top track, not another track or a queue.\n"
        "- latest_request_alignment: addresses the latest user request, not stale history.\n"
        "- constraint_respect: respects avoid/new-artist/language/year/style constraints; do not reward confident praise of a clear violation.\n"
        "- grounded_explanation: gives a supported reason from the selected track/context, with no invented facts.\n"
        "- language_match: matches the user's language when detectable.\n"
        "- response_quality: concise, natural, useful, and not a metadata dump.\n"
        "Also return risk_flags as an object of booleans for: non_top_explanation, playlist_or_queue_framing, "
        "unsupported_fact, apology_or_system_confession, overclaiming, generic_followup_question.\n"
        "Return only JSON with keys top1_faithfulness, latest_request_alignment, constraint_respect, "
        "grounded_explanation, language_match, response_quality, risk_flags, notes.\n\n"
        f"Listener goal: {goal}\n"
        f"Previous user request: {_previous_user(dataset_row)}\n"
        f"Latest user request: {_latest_user(dataset_row)}\n"
        f"Recent prior music track IDs: {json.dumps(_prior_music(dataset_row), ensure_ascii=False)}\n"
        f"Selected top track: {top_label}\n"
        f"Extracted state: {state}\n"
        f"Reply: {row.get('predicted_response') or ''}\n"
    )


def _all_track_ids(rows: list[dict[str, Any]]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for row in rows:
        for track_id in row.get("predicted_track_ids") or []:
            if track_id and track_id not in seen:
                seen.add(track_id)
                out.append(track_id)
    return out


def _score_with_litellm(
    prompts: list[str],
    *,
    model_name: str,
    temperature: float,
    max_tokens: int,
    batch_size: int,
) -> list[dict[str, Any] | None]:
    _load_dotenv_quietly()
    import litellm

    parsed: list[dict[str, Any] | None] = []
    for start in range(0, len(prompts), batch_size):
        batch = prompts[start : start + batch_size]
        messages = [[{"role": "user", "content": prompt}] for prompt in batch]
        responses = litellm.batch_completion(
            model=model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        for response in responses:
            try:
                text = response.choices[0].message.content or ""
            except Exception:
                text = ""
            parsed.append(parse_judge_response(text))
    return parsed


def build_audit(
    rows: list[dict[str, Any]],
    dataset_rows: dict[str, dict[str, Any]],
    metadata: dict[str, dict[str, Any]],
    traces: dict[tuple[str, int], dict[str, Any]] | None,
    judge_scores: list[dict[str, Any] | None] | None = None,
) -> dict[str, Any]:
    audit_rows: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        key = (row["session_id"], int(row["turn_number"]))
        dataset_row = dataset_rows.get(row["session_id"], {})
        trace_row = (traces or {}).get(key)
        top_id = (row.get("predicted_track_ids") or [None])[0]
        top_label = label_for_track(top_id, metadata) if top_id else ""
        joined = {
            **row,
            "latest_user": _latest_user(dataset_row),
        }
        audit = heuristic_audit_row(joined)
        risks = response_risk_flags(row, top_label)
        audit_rows.append(
            {
                "session_id": row["session_id"],
                "turn_number": row["turn_number"],
                "top_track_id": top_id,
                "top_track_label": top_label,
                "latest_user": joined["latest_user"],
                "listener_goal": (dataset_row.get("conversation_goal") or {}).get("listener_goal"),
                "heuristics": audit,
                "risk_flags": risks,
                "judge": judge_scores[idx] if judge_scores is not None else None,
                "has_trace": bool(trace_row),
            }
        )
    risk_summary: dict[str, int] = {}
    for row in audit_rows:
        for key, value in row["risk_flags"].items():
            if value:
                risk_summary[key] = risk_summary.get(key, 0) + 1
    return {
        "n_rows": len(rows),
        "lexical_diversity": distinct_n((row.get("predicted_response") or "" for row in rows), n=2),
        "heuristic_summary": summarize_audits(rows),
        "risk_summary": risk_summary,
        "judge_summary": aggregate_judge_scores(judge_scores or []) if judge_scores is not None else None,
        "rows": audit_rows,
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    rows = load_predictions(args.predictions)
    if args.limit:
        rows = rows[: args.limit]
    dataset_rows = load_dataset_rows_by_session(args.dataset, split=args.dataset_split)
    metadata = load_track_metadata(_all_track_ids(rows), dataset_name=args.track_dataset, split=args.track_split)
    traces = load_traces(args.trace) if args.trace else None

    judge_scores = None
    if not args.heuristic_only:
        prompts = []
        for row in rows:
            key = (row["session_id"], int(row["turn_number"]))
            dataset_row = dataset_rows[row["session_id"]]
            trace = ((traces or {}).get(key) or {}).get("trace")
            top_id = (row.get("predicted_track_ids") or [None])[0]
            prompts.append(_judge_prompt(row, dataset_row, label_for_track(top_id, metadata) if top_id else "", trace))
        judge_scores = _score_with_litellm(
            prompts,
            model_name=args.model_name,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            batch_size=args.batch_size,
        )

    audit = build_audit(rows, dataset_rows, metadata, traces, judge_scores)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in audit.items() if k != "rows"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
